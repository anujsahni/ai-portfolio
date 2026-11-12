"""`make data`: generate Northstar's four source systems, the hidden truth and the golden answers; seed Postgres.

Outputs (under data/out/, git-ignored):
  sap_s4/batch=1/<TABLE>.csv     SAP change feed read by the Connector SDK connector (batch=2 after `make data BATCH=2`)
  saas/salesforce/*.csv, saas/zendesk/*.csv   API-shaped SaaS data for the simulated landings
  carrier_pg/*.csv               the carrier tracking data, also seeded into the Postgres container
  truth/                         hidden truth, golden answers and traps (never read by the app or the agents)
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import time as clock
from pathlib import Path

from contextloop import config
from contextloop.datagen import sources
from contextloop.datagen.truth import compute
from contextloop.datagen.world import STALE_CUTOFF, TIER_CHANGE_AT, World, build_world

GOLDEN_QUESTIONS = [
    ("G1", "Which of our strategic accounts are at risk because of late shipments, and what should the account teams do this week?",
     "list", ["T1", "T2", "T4", "T5"]),
    ("G2", "What is the 90-day on-time delivery rate across all of our strategic accounts?", "number (percent, 1 decimal)", ["T1", "T2", "T5"]),
    ("G3", "What was our net revenue in USD in EMEA for Q3 2026?", "number (USD)", ["T3"]),
    ("G4", "How many strategic accounts do we have today?", "number", ["T4", "T5"]),
    ("G5", "Is our support ticket data current enough to act on today?", "yes/no with sync age", ["T6"]),
    ("G6", "How many open shipping-related support tickets do our strategic accounts have in total?", "number", ["T4", "T5"]),
]


def write_csv(path: Path, columns: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=columns, lineterminator="\n", extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
    path.write_text(buf.getvalue(), encoding="utf-8")


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def tables(world: World) -> tuple[dict, dict, dict]:
    return sources.sap_batch1(world), sources.saas(world), sources.carrier(world)


def traps(world: World, sap: dict) -> dict:
    cancelled = sorted(d.vbeln for o in world.orders for d in o.deliveries if d.cancelled_on)
    n_deliv = sum(len(o.deliveries) for o in world.orders)
    t2 = sorted(d.vbeln for o in world.orders for d in o.deliveries if d.late and d.wadat_ist and d.wadat <= o.vdatu)
    eur = sum(1 for o in world.orders if o.customer.currency == "EUR")
    h = next(c for c in world.customers if c.role == "H")
    dup = next(a for a in world.sf_accounts if a.get("is_duplicate_of"))
    moved = [c for c in world.customers if c.tier_before != c.tier_now]
    return {
        "T1": {"what": "Cancelled deliveries kept as soft-deleted rows", "deliveries": cancelled,
               "share_of_deliveries": round(len(cancelled) / n_deliv, 4)},
        "T2": {"what": "Late deliveries whose planned goods-issue date was on time", "deliveries": t2, "count": len(t2)},
        "T3": {"what": "Orders and invoices in EUR", "eur_order_share": round(eur / len(world.orders), 4)},
        "T4": {"what": "Look-alike duplicate Salesforce account, not mapped to SAP",
               "customer": {"kunnr": h.kunnr, "sf_account_id": h.sf_id, "name": "Halbrook Fluid Systems"},
               "duplicate": {"sf_account_id": dup["id"], "name": dup["name"]}},
        "T5": {"what": "Tier changed midway through the 90-day window", "changed_at": TIER_CHANGE_AT.isoformat(),
               "accounts": [{"kunnr": c.kunnr, "name": c.name, "sf_account_id": c.sf_id, "from": c.tier_before, "to": c.tier_now} for c in moved]},
        "T6": {"what": "Zendesk sync held two days behind (scenario flag CONTEXTLOOP_T6_STALE_ZENDESK)",
               "enabled": config.T6_STALE_ZENDESK, "zendesk_data_cutoff": STALE_CUTOFF.isoformat()},
    }


def run(seed: int | None = None, batch: int = 1, seed_postgres: bool = True) -> int:
    started = clock.monotonic()
    seed = config.DEFAULT_SEED if seed is None else seed
    world = build_world(seed)
    out = config.DATA_OUT
    if batch == 2:
        if not (config.SAP_DIR / "batch=1").exists():
            print("✗ Batch 1 is missing. Run `make data` first.")
            return 1
        for t, (cols, rows) in sources.sap_batch2(world).items():
            write_csv(config.SAP_DIR / "batch=2" / f"{t}.csv", cols, rows)
        print(f"Wrote SAP batch 2 (schema change: LIKP.ZZ_CARRIER_ID) in {clock.monotonic() - started:.1f}s")
        return 0

    sap, saas, carrier = tables(world)
    import shutil

    shutil.rmtree(config.SAP_DIR, ignore_errors=True)
    for t, (cols, rows) in sap.items():
        write_csv(config.SAP_DIR / "batch=1" / f"{t}.csv", cols, rows)
    for name, (cols, rows) in saas.items():
        write_csv(config.SAAS_DIR / f"{name}.csv", cols, rows)
    for name, (cols, rows) in carrier.items():
        write_csv(config.CARRIER_DIR / f"{name}.csv", cols, rows)

    truth = compute(sap, saas, carrier, stale_zendesk=config.T6_STALE_ZENDESK)
    write_json(config.TRUTH_DIR / "truth.json", truth)
    write_json(config.TRUTH_DIR / "traps.json", traps(world, sap))
    write_json(config.TRUTH_DIR / "golden.json", [
        {"id": gid, "question": q, "answer_type": at, "traps": tr, "expected": truth["golden"][gid]} for gid, q, at, tr in GOLDEN_QUESTIONS
    ])
    write_json(out / "manifest.json", {"seed": seed, "as_of": config.AS_OF.isoformat(), "files": checksums(out)})

    if seed_postgres:
        from contextloop.datagen.postgres_seed import seed as pg_seed

        pg_seed(carrier)
    counts = {f"sap_s4.{t}": len({tuple(r[k] for k in sources.SAP_KEYS[t]) for r in rows}) for t, (_, rows) in sap.items()}
    counts |= {n.replace("/", "."): len(rows) for n, (_, rows) in saas.items()}
    counts |= {f"carrier_pg.{n}": len(rows) for n, (_, rows) in carrier.items()}
    print(json.dumps(counts, indent=1))
    print(f"At-risk strategic accounts: {len(truth['at_risk'])}")
    print(f"Generated seed {seed} in {clock.monotonic() - started:.1f}s")
    return 0


def checksums(out: Path) -> dict[str, str]:
    files = sorted(p for p in out.rglob("*.csv"))
    files += sorted((out / "truth").glob("*.json"))
    return {str(p.relative_to(out)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
