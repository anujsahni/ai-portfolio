#!/usr/bin/env python3
"""MVP-03 / IAC-05: smoke-test the deployed Cloud Run service.

  1. Service settings from Terraform: min 0, bounded max, runs as weekendwise-run, image is not the placeholder.
  2. Access: without a token the service answers 403 (private), unless allow_unauthenticated is on.
  3. /health as you (not /healthz, which Cloud Run's front end reserves) (identity token from gcloud): the container is up, and reports the deployed tag.
  4. /readyz: the container read Firestore as its attached identity.
  5. One live plan through /api/plan (skip with --no-plan): Vertex AI + Firestore + planner, end to end (~1 cent).

Writes docs/mvp/evidence/MVP-03-cloud-run-smoke.md (no URL: the service address stays in your private notes).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STACK = ROOT / "infra" / "stack"
PLACEHOLDER = "us-docker.pkg.dev/cloudrun/container/hello"


def tf_output(name: str):
    out = subprocess.run(["terraform", f"-chdir={STACK}", "output", "-json", name], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def http(method: str, url: str, token: str | None = None, body: dict | None = None, timeout: int = 30):
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body else None)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    if body:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace"), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), dict(e.headers)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-plan", action="store_true")
    args = ap.parse_args()

    rows, failures = [], 0

    def check(name: str, ok: bool, detail: str = "") -> bool:
        nonlocal failures
        failures += not ok
        rows.append((name, ok, detail))
        print(f"{'✓' if ok else '✗'} {name}" + (f"  ({detail})" if detail else ""))
        return ok

    run = tf_output("cloud_run")
    url = run["url"].rstrip("/")
    tag = run["image"].rsplit(":", 1)[-1] if ":" in run["image"].rsplit("/", 1)[-1] else "latest"
    check("min instances is 0 (scale to zero)", run["min_instances"] == 0, str(run["min_instances"]))
    check("max instances is bounded", 1 <= run["max_instances"] <= 5, str(run["max_instances"]))
    check("runs as the dedicated runtime identity", run["service_account"].startswith("weekendwise-run@"), run["service_account"].split("@")[0])
    if not check("app image deployed (not the placeholder)", not run["image"].startswith(PLACEHOLDER), f"tag {tag}"):
        print("  Run: make build && make deploy")
        return 1

    status, _, _ = http("GET", f"{url}/health")
    if run["public"]:
        check("public access is ON (allow_unauthenticated = true)", status == 200, f"HTTP {status} without a token")
    else:
        check("private: a request without a token is rejected", status in (401, 403), f"HTTP {status}")

    token = subprocess.run(["gcloud", "auth", "print-identity-token"], capture_output=True, text=True, check=True).stdout.strip()
    start = time.monotonic()
    status, body, _ = http("GET", f"{url}/health", token, timeout=60)
    cold = time.monotonic() - start
    version = json.loads(body).get("version") if status == 200 else None
    check("/health answers as you", status == 200, f"HTTP {status}, {cold:.1f}s incl. any cold start, version {version}")
    check("reported version matches the deployed tag", version == tag, f"{version} vs {tag}")
    status, body, _ = http("GET", f"{url}/readyz", token, timeout=60)
    check("/readyz: Firestore readable as weekendwise-run", status == 200, body[:120])

    if not args.no_plan:
        sample = json.loads((ROOT / "data" / "seed" / "trip_scenarios" / "SCENARIO-04-PORTLAND-RAINY.json").read_text())["request"]
        start = time.monotonic()
        status, body, headers = http("POST", f"{url}/api/plan", token, sample, timeout=200)
        secs = time.monotonic() - start
        result = None
        steps = 0
        for block in body.split("\n\n"):
            if block.startswith("event: step"):
                steps += 1
            if block.startswith("event: result"):
                result = json.loads(block.split("data:", 1)[1])
        ok = status == 200 and result is not None and result.get("status") == "complete"
        detail = (f"{secs:.1f}s, {steps} steps, {result['usage']['modelCalls']} model call(s), {len(result['citations'])} citations, "
                  f"budget {result['budget']['statusLabel']}, request {headers.get('X-Request-ID') or headers.get('x-request-id')}") if ok else f"HTTP {status}: {body[:200]}"
        check("live plan through Cloud Run (Vertex AI + Firestore as weekendwise-run)", ok, detail)

    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    md = [f"# MVP-03 Cloud Run smoke test — {stamp}", "",
          f"Service `{run['name']}` in `{run['latest_ready_revision']}`, image tag `{tag}`. Run by `make smoke-cloud`. "
          "The service URL is kept out of this file.", "", "| Check | Result | Detail |", "|---|---|---|"]
    md += [f"| {n} | {'✅' if ok else '❌'} | {d} |" for n, ok, d in rows]
    md += ["", "Runtime identity can't write Firestore: proven by `make verify` (scripts/verify_iam.py, IAC-03)."]
    out = ROOT / "docs" / "mvp" / "evidence"
    out.mkdir(parents=True, exist_ok=True)
    (out / "MVP-03-cloud-run-smoke.md").write_text("\n".join(md) + "\n")
    print(f"\n{len(rows) - failures} of {len(rows)} checks passed. Report: docs/mvp/evidence/MVP-03-cloud-run-smoke.md")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
