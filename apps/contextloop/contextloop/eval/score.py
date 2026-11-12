"""Scores an agent's structured answer against the hidden truth, one golden question at a time (code, not an LLM judge).

Lists: exact set match (precision and recall shown). Numbers: 0.5 percentage points for rates, 1% for money, exact for counts.
Yes or no: exact match.
"""
from __future__ import annotations

from contextloop.datagen.truth import normalize


def _value(answer: dict) -> float | None:
    v = answer.get("value")
    return float(v) if isinstance(v, (int, float)) else None


def score(question_id: str, answer: dict | None, truth: dict) -> dict:
    expected = truth["golden"][question_id]
    if not answer:
        return {"correct": False, "expected": expected, "got": None, "note": "no answer submitted"}
    if question_id == "G1":
        names = {}
        for r in truth["at_risk"]:
            names[normalize(r["name"])] = r["name"]
            names[normalize(r["sap_name"])] = r["name"]
        got_raw = [a["account_name"] for a in answer.get("at_risk_accounts") or []]
        got = {names.get(normalize(n), n) for n in got_raw}
        want = set(expected)
        tp = len(got & want)
        precision = tp / len(got) if got else 0.0
        recall = tp / len(want) if want else 1.0
        return {"correct": got == want, "expected": sorted(want), "got": sorted(got), "precision": round(precision, 2),
                "recall": round(recall, 2), "missed": sorted(want - got), "extra": sorted(got - want)}
    if question_id == "G5":
        got = answer.get("is_current")
        return {"correct": got is expected["current"], "expected": expected["current"], "got": got}
    v = _value(answer)
    if v is None:
        return {"correct": False, "expected": expected, "got": None, "note": "no number given"}
    if question_id == "G2":
        v = v * 100 if v <= 1 else v
        return {"correct": abs(v - expected) <= 0.5, "expected": expected, "got": round(v, 2)}
    if question_id == "G3":
        return {"correct": abs(v - expected) <= 0.01 * abs(expected), "expected": expected, "got": round(v, 2)}
    return {"correct": round(v) == expected, "expected": expected, "got": v}
