"""Command-line entry point for every ContextLoop job: python -m contextloop.cli <command>.

The Makefile and docker-compose.yml call these commands; each one belongs to a backlog story.
"""
from __future__ import annotations

import argparse
import sys


def _not_yet(story: str, what: str) -> int:
    print(f"✗ Not built yet: {what} arrives with {story} (see docs/mvp/INDEX.md).")
    return 2


def cmd_lake_init(_: argparse.Namespace) -> int:
    from contextloop.lakehouse.bucket import ensure_bucket

    ensure_bucket()
    return 0


def cmd_datagen(args: argparse.Namespace) -> int:
    from contextloop.datagen.main import run

    return run(seed=args.seed, batch=args.batch, seed_postgres=not args.no_postgres)


def cmd_sync(_: argparse.Namespace) -> int:
    from contextloop.landing.sync_all import run

    return run()


def cmd_build(args: argparse.Namespace) -> int:
    from contextloop.build import run

    return run(break_trap=args.break_trap)


def cmd_lakehouse(_: argparse.Namespace) -> int:
    from contextloop.lakehouse.compare import run

    return run()


def cmd_sdk_debug(_: argparse.Namespace) -> int:
    from contextloop.landing.sdk_debug import run

    return run()


def cmd_eval(_: argparse.Namespace) -> int:
    from contextloop.eval.run import run

    return run(record=False)


def cmd_record(_: argparse.Namespace) -> int:
    from contextloop.eval.run import run

    return run(record=True)


def cmd_touch_carrier(args: argparse.Namespace) -> int:
    """Simulates new activity in the carrier database: re-stamps a few in-transit shipments (values unchanged), so the next
    sync lands exactly those rows."""
    import psycopg

    from contextloop.config import pg_dsn

    with psycopg.connect(pg_dsn(), autocommit=True) as conn:
        rows = conn.execute("UPDATE tracking.shipment SET updated_at = now() WHERE shipment_id IN (SELECT shipment_id FROM "
                            "tracking.shipment WHERE status = 'in_transit' ORDER BY shipment_id LIMIT %s) RETURNING shipment_id",
                            [args.n]).fetchall()
    print(f"Carrier database: {len(rows)} in-transit shipments updated ({', '.join(str(r[0]) for r in rows)})")
    return 0


def cmd_export(_: argparse.Namespace) -> int:
    """Write recordings/ and reports/ from the data volume to stdout as a tar stream (the Makefile unpacks it on the host)."""
    import tarfile

    from contextloop import config as c

    with tarfile.open(fileobj=sys.stdout.buffer, mode="w|") as tar:
        for name in ("recordings", "reports"):
            if (c.DATA_OUT / name).exists():
                tar.add(c.DATA_OUT / name, arcname=name)
    return 0


def cmd_ask(args: argparse.Namespace) -> int:
    """Ask one golden question of one agent and print the trace (live mode)."""
    import json

    from contextloop import config as c
    from contextloop.agent import governed, naive

    q = next(q for q in json.loads((c.TRUTH_DIR / "golden.json").read_text()) if q["id"] == args.question)
    agent = naive.answer if args.agent == "naive" else governed.answer
    tr = agent(q["id"], q["question"], on_step=lambda s: print(f"→ {s.tool} {json.dumps(s.input)[:160]}"))
    print(json.dumps(tr.to_dict()["answer"], indent=2))
    print(f"{tr.seconds}s · {tr.usage} · error={tr.error}")
    return 0 if tr.answer else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="contextloop", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("lake-init", help="create the lakehouse bucket").set_defaults(fn=cmd_lake_init)

    p = sub.add_parser("datagen", help="generate the synthetic source systems (CL-03)")
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--batch", type=int, default=1, choices=[1, 2])
    p.add_argument("--no-postgres", action="store_true", help="write files only; skip seeding Postgres")
    p.set_defaults(fn=cmd_datagen)

    sub.add_parser("sync", help="run the connectors and landings (CL-04, CL-05)").set_defaults(fn=cmd_sync)

    p = sub.add_parser("build", help="dbt build, semantic layer, Iceberg publish (CL-06 to CL-08)")
    p.add_argument("--break", dest="break_trap", choices=["T1", "T4"], default=None)
    p.set_defaults(fn=cmd_build)

    sub.add_parser("lakehouse", help="compare DuckDB and Trino on Iceberg (CL-08)").set_defaults(fn=cmd_lakehouse)
    sub.add_parser("sdk-debug", help="run the SAP connector with `fivetran debug`").set_defaults(fn=cmd_sdk_debug)
    sub.add_parser("eval", help="score both agents (CL-11)").set_defaults(fn=cmd_eval)
    sub.add_parser("record", help="record live runs (CL-11)").set_defaults(fn=cmd_record)
    sub.add_parser("export", help="tar recordings and reports to stdout").set_defaults(fn=cmd_export)
    p = sub.add_parser("scenario", help="switch the simulated Zendesk landing: t6-on (two days behind) or t6-off (current)")
    p.add_argument("state", choices=["t6-on", "t6-off"])
    p.set_defaults(fn=lambda a: __import__("contextloop.landing.sync_all", fromlist=["x"]).set_zendesk_scenario(a.state == "t6-on"))
    p = sub.add_parser("touch-carrier", help="update a few carrier shipments so the next sync has changes")
    p.add_argument("-n", type=int, default=3)
    p.set_defaults(fn=cmd_touch_carrier)
    p = sub.add_parser("ask", help="ask one golden question of one agent (live)")
    p.add_argument("agent", choices=["naive", "governed"])
    p.add_argument("question", choices=[f"G{i}" for i in range(1, 7)])
    p.set_defaults(fn=cmd_ask)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
