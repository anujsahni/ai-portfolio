"""`make build`: dbt build (models and tests), source freshness, docs and lineage, the semantic layer check, the Iceberg publish,
and finally the read-only serving copy for the long-running services.

`make break TRAP=T1|T4` runs the same build with one trap's handling removed, so a named dbt test fails live; the next
`make build` restores everything.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

from contextloop import config
from contextloop.warehouse import publish_serving

TARGET = Path(os.environ.get("DBT_TARGET_PATH", config.DBT_PROJECT_DIR / "target"))


def dbt(*args: str, check: bool = True, quiet: bool = False) -> subprocess.CompletedProcess:
    cmd = ["dbt", "--no-use-colors", *args, "--project-dir", str(config.DBT_PROJECT_DIR), "--profiles-dir", str(config.DBT_PROJECT_DIR)]
    env = os.environ | {"DBT_SEND_ANONYMOUS_USAGE_STATS": "false", "DO_NOT_TRACK": "1",
                        "DBT_LOG_PATH": str(TARGET.parent / "dbt_logs"), "DBT_TARGET_PATH": str(TARGET)}
    proc = subprocess.run(cmd, cwd=config.DBT_PROJECT_DIR, env=env, capture_output=True, text=True)
    if not quiet:
        print(_summary(proc.stdout))
    if check and proc.returncode != 0:
        print(proc.stdout[-6000:], proc.stderr[-2000:])
        raise SystemExit(f"✗ dbt {args[0]} failed")
    return proc


def _summary(out: str) -> str:
    marks = ("Done.", "Completed", "PASS=", "ERROR", "FAIL ", "WARN ", "Failure in", "Database Error")
    keep = [ln for ln in out.splitlines() if any(k in ln for k in marks)]
    return "\n".join(keep[-25:])


def failing_tests() -> list[str]:
    path = TARGET / "run_results.json"
    if not path.exists():
        return []
    results = json.loads(path.read_text())["results"]
    return sorted(r["unique_id"].split(".")[2] for r in results if r["status"] in ("fail", "error"))


def freshness() -> dict[str, str]:
    """dbt source freshness; returns source -> pass|warn|error (an error here is expected when trap T6 is on)."""
    dbt("source", "freshness", check=False, quiet=True)
    path = TARGET / "sources.json"
    out = {}
    if path.exists():
        for r in json.loads(path.read_text())["results"]:
            src = ".".join(r["unique_id"].split(".")[2:4])
            out[src] = r["status"]
    return out


def run(break_trap: str | None = None) -> int:
    if not config.WAREHOUSE_PATH.exists():
        print("✗ The warehouse is empty. Run `make sync` first.")
        return 1
    started = time.monotonic()
    if break_trap:
        print(f"Breaking trap {break_trap}: removing its handling from the dbt project for this build only…")
        proc = dbt("build", "--vars", json.dumps({"break_trap": break_trap}), check=False)
        failed = failing_tests()
        publish_serving()
        print(f"\nFailing tests with {break_trap} broken: {', '.join(failed) or 'none'}")
        print("Run `make build` to restore the trusted models.")
        return 0 if proc.returncode != 0 and failed else 1
    dbt("build")
    fresh = freshness()
    stale = sorted({s.split(".")[0] for s, st in fresh.items() if st in ("error", "warn")})
    print(f"Source freshness: {'all sources current' if not stale else 'behind: ' + ', '.join(stale)}")
    dbt("docs", "generate", quiet=True)
    from contextloop.semantic import validate

    validate()
    from contextloop.lakehouse.publish import publish

    publish()
    publish_serving()
    print(f"Build finished in {time.monotonic() - started:.0f}s")
    return 0
