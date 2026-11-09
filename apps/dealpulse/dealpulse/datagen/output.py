"""Write a generated dataset to disk in the layout uploaded to S3.

    <out>/crm-snapshot/<Object>.jsonl, meta.json   → s3://<bucket>/crm-snapshot/
    <out>/training/rows.csv                        → s3://<bucket>/training/
    <out>/knowledge/{playbook,policy,win_loss}/*.md → s3://<bucket>/knowledge/
    <out>/eval/  hidden truth, note topics, traps   (local only: evaluation, never read by the app)
    <out>/manifest.json  SHA-256 of every file      (reproducibility check)
"""
from __future__ import annotations

import csv
import hashlib
import json
import random
import shutil
from pathlib import Path

from dealpulse import features as F

from .generator import Dataset
from .reviews import pick_reviews
from .vocab import SNAPSHOT_DATE, VENDOR

PLAYBOOKS = Path(__file__).resolve().parents[2] / "data" / "playbooks"


def _jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def training_rows(ds: Dataset) -> list[dict]:
    index = F.build_index(ds.objects)
    rows = []
    for opp_id in sorted(index):
        deal = index[opp_id]
        if not deal.opportunity["IsClosed"]:
            continue
        close = deal.history[-1]["CreatedDate"]
        for as_of in F.snapshot_dates(deal):
            feats = F.features_as_of(deal, as_of)
            rows.append({
                "opportunity_id": opp_id, "snapshot_date": as_of.isoformat(),
                "close_quarter": f"{close[:4]}Q{(int(close[5:7]) - 1) // 3 + 1}",
                "is_won": int(deal.opportunity["IsWon"]),
                "stage_probability": F.stage_probability_as_of(deal, as_of),
                **{k: round(v, 6) for k, v in feats.items()},
            })
    return rows


def write(ds: Dataset, out: Path, *, seed: int, rule: dict) -> dict:
    if out.exists() and any(out.iterdir()):
        # Only ever replace a folder this writer created before.
        if not (out / "manifest.json").exists():
            raise SystemExit(f"Refusing to overwrite {out}: it isn't a previous generator output (no manifest.json)")
        shutil.rmtree(out)
    snap = out / "crm-snapshot"
    for name, rows in sorted(ds.objects.items()):
        _jsonl(snap / f"{name}.jsonl", rows)
    meta = {"vendor": VENDOR, "snapshot_date": SNAPSHOT_DATE.isoformat(), "seed": seed,
            "counts": {k: len(v) for k, v in sorted(ds.objects.items())},
            "notice": "Synthetic data. All companies, people, deals and notes are fictional."}
    (snap / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")

    rows = training_rows(ds)
    (out / "training").mkdir(parents=True)
    with (out / "training" / "rows.csv").open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    knowledge = out / "knowledge"
    for kind in ("playbook", "policy"):
        shutil.copytree(PLAYBOOKS / kind, knowledge / kind)
    opps = {o["Id"]: o for o in ds.objects["Opportunity"]}
    accounts = {a["Id"]: a for a in ds.objects["Account"]}
    (knowledge / "win_loss").mkdir(parents=True)
    reviews = pick_reviews(ds.truth, opps, accounts, {}, random.Random(seed + 1))
    for name, text in reviews:
        (knowledge / "win_loss" / name).write_text(text)

    ev = out / "eval"
    _jsonl(ev / "truth.jsonl", ds.truth)
    _jsonl(ev / "note_topics.jsonl", ds.note_topics)
    (ev / "traps.json").write_text(json.dumps(ds.traps, indent=2, sort_keys=True) + "\n")
    (ev / "hidden_rule.json").write_text(json.dumps(rule, indent=2) + "\n")

    manifest = {str(p.relative_to(out)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(out.rglob("*")) if p.is_file()}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return {"training_rows": len(rows), "reviews": len(reviews), "files": len(manifest)}
