"""CL-03: the synthetic sources are reproducible, linked, scenario-complete, and every trap matters."""
from __future__ import annotations

import re
from collections import Counter
from functools import lru_cache

import pytest

from contextloop.config import DEFAULT_SEED
from contextloop.datagen import main as datagen
from contextloop.datagen import sources
from contextloop.datagen.truth import TRAPS, apply_feed, compute
from contextloop.datagen.world import build_world


@lru_cache(maxsize=None)
def tables(seed: int = DEFAULT_SEED):
    w = build_world(seed)
    return w, sources.sap_batch1(w), sources.saas(w), sources.carrier(w)


@lru_cache(maxsize=None)
def truth(ignore: frozenset = frozenset()):
    _, sap, saas, car = tables()
    return compute(sap, saas, car, stale_zendesk=True, ignore=ignore)


def _write(tmp_path, seed):
    import os

    out = tmp_path / str(seed)
    os.environ["CONTEXTLOOP_DATA_OUT"] = str(out)
    import importlib

    from contextloop import config

    importlib.reload(config)
    importlib.reload(datagen)
    try:
        assert datagen.run(seed=seed, seed_postgres=False) == 0
        return datagen.checksums(out)
    finally:
        os.environ.pop("CONTEXTLOOP_DATA_OUT")
        importlib.reload(config)
        importlib.reload(datagen)


def test_same_seed_gives_identical_files_and_other_seed_differs(tmp_path):
    a = _write(tmp_path / "a", DEFAULT_SEED)
    b = _write(tmp_path / "b", DEFAULT_SEED)
    c = _write(tmp_path / "c", DEFAULT_SEED + 1)
    assert a == b
    assert a != c


def test_volumes_within_ten_percent():
    _, sap, saas, car = tables()
    distinct = {t: len({tuple(r[k] for k in sources.SAP_KEYS[t]) for r in rows}) for t, (_, rows) in sap.items()}
    expected = {"KNA1": 120, "VBAK": 9000, "VBAP": 27000, "LIKP": 9500, "VBRK": 8800}
    for t, n in expected.items():
        assert abs(distinct[t] - n) <= 0.1 * n, (t, distinct[t])
    accounts = {r["id"] for r in saas["salesforce/account_history"][1]}
    assert abs(len(accounts) - 135) <= 13.5
    assert abs(len(saas["zendesk/ticket"][1]) - 3000) <= 300


def test_referential_integrity():
    _, sap, saas, car = tables()
    vbak = {k[1] for k in apply_feed("VBAK", sap["VBAK"][1])}
    likp = {k[1] for k in apply_feed("LIKP", sap["LIKP"][1])}
    kna1 = {k[1] for k in apply_feed("KNA1", sap["KNA1"][1])}
    assert {k[1] for k in apply_feed("VBAP", sap["VBAP"][1])} <= vbak  # every item has a header
    lips = apply_feed("LIPS", sap["LIPS"][1])
    assert {r["VGBEL"] for r in lips.values()} <= vbak  # every delivery links to an order
    assert {k[1] for k in lips} == likp
    ships = {s["shipment_id"]: s["delivery_number"] for s in car["shipment"][1]}
    assert set(ships.values()) <= likp
    assert {e["shipment_id"] for e in car["shipment_event"][1]} <= set(ships)  # every event links to a shipment
    mapped = [r for r in saas["salesforce/account_history"][1] if r["sap_customer_number_c"]]
    assert {r["sap_customer_number_c"] for r in mapped} <= kna1
    current = [r for r in mapped if r["valid_to"].startswith("9999")]
    assert len({r["sap_customer_number_c"] for r in current}) == len(current)  # one SF account per SAP customer


def test_history_has_exactly_one_open_row_per_account():
    _, _, saas, _ = tables()
    open_rows = Counter(r["id"] for r in saas["salesforce/account_history"][1] if r["valid_to"].startswith("9999"))
    assert set(open_rows.values()) == {1}


def test_scenario_coverage():
    t = truth()
    assert len(t["at_risk"]) >= 7
    w, *_ = tables()
    promoted = {c.kunnr for c in w.customers if c.tier_before == "Standard" and c.tier_now == "Strategic"}
    assert promoted & {r["kunnr"] for r in t["at_risk"]}, "an account promoted mid-period must be at risk"
    # at risk on rate and drivers, but not strategic
    non_strategic = [k for k, v in t["on_time_by_customer"].items()
                     if v["rate"] < 0.85 and (t["open_shipping_tickets"].get(k, 0) >= 2 or k in t["renewals_due_120d"])
                     and k not in {r["kunnr"] for r in t["at_risk"]}]
    assert non_strategic


@pytest.mark.parametrize("trap", TRAPS)
def test_each_trap_changes_a_golden_answer(trap):
    base, naive = truth()["golden"], truth(frozenset({trap}))["golden"]
    changed = [g for g in base if base[g] != naive[g]]
    assert changed, f"{trap} changes no golden answer"


def test_at_least_three_questions_are_trap_sensitive():
    base = truth()["golden"]
    sensitive = {g for t in TRAPS for g, v in truth(frozenset({t}))["golden"].items() if v != base[g]}
    assert len(sensitive) >= 3


def test_traps_present():
    w, sap, saas, _ = tables()
    feed = sap["LIKP"][1]
    deletes = {r["VBELN"] for r in feed if r["ODQ_CHANGEMODE"] == "D"}
    total = len({r["VBELN"] for r in feed})
    assert 0.03 <= len(deletes) / total <= 0.05  # T1 about 4%
    eur = sum(1 for o in w.orders if o.customer.currency == "EUR") / len(w.orders)
    assert 0.30 <= eur <= 0.42  # T3 about 35%
    names = {r["name"] for r in saas["salesforce/account_history"][1]}
    assert {"Halbrook Fluid Systems", "Halbrook Fluid Systems GmbH"} <= names  # T4
    moved = Counter(r["id"] for r in saas["salesforce/account_history"][1])
    assert sum(1 for n in moved.values() if n == 2) == 4  # T5: three promoted, one demoted


def test_no_real_contact_details():
    w, sap, saas, _ = tables()
    for u in saas["salesforce/user"][1]:
        assert u["email"].endswith("@example.com")
    for r in sap["KNA1"][1]:
        assert re.fullmatch(r"555-01\d\d", r["TELF1"])
