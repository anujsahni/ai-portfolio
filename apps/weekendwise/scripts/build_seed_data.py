#!/usr/bin/env python3
"""Build and validate WeekendWise Firestore seed JSON.

Generated collections (rebuilt on every run):
  guide_sources, guide_chunks, corpus_manifests  <- data/guides/*.md
                                                    (+ corpusVersion per city from seed/cities)
  evaluation_cases                               <- data/evaluation_cases.json

Hand-written collections (validated only):
  cities, interests, budget_categories, app_config, local_conditions,
  trip_scenarios, sample_itineraries

Layout: data/seed/<collection>/<documentId>.json
Stdlib only. Makes no network or Firestore calls.

Usage:  python3 scripts/build_seed_data.py           # build + validate
        python3 scripts/build_seed_data.py --check   # validate only
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUIDES = ROOT / "data" / "guides"
EVAL_FILE = ROOT / "data" / "evaluation_cases.json"
SEED = ROOT / "data" / "seed"

CHUNKER_VERSION = "paragraph-v1"
GENERATED = ["guide_sources", "guide_chunks", "corpus_manifests", "evaluation_cases"]
REQUIRED_FRONT_MATTER = ["source_id", "city", "content_type", "last_reviewed"]


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_guide(path: Path) -> tuple[dict, str, list[str]]:
    raw = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", raw, re.S)
    if not m:
        raise ValueError(f"{path.name}: missing front matter")
    meta = {}
    for line in m.group(1).splitlines():
        key, _, value = line.partition(":")
        value = value.strip()
        meta[key.strip()] = {"true": True, "false": False}.get(value, value)
    missing = [k for k in REQUIRED_FRONT_MATTER if k not in meta]
    if missing:
        raise ValueError(f"{path.name}: missing {missing}")
    body = m.group(2).strip()
    title_match = re.match(r"^#\s+(.+)$", body, re.M)
    if not title_match:
        raise ValueError(f"{path.name}: missing '# Title'")
    title = title_match.group(1).strip()
    text = body[title_match.end():].strip()
    paragraphs = [" ".join(p.split()) for p in re.split(r"\n\s*\n", text) if p.strip()]
    return meta, title, paragraphs


def write(collection: str, doc_id: str, data: dict) -> None:
    folder = SEED / collection
    folder.mkdir(parents=True, exist_ok=True)
    with open(folder / f"{doc_id}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def corpus_versions() -> dict[str, str]:
    """cityId -> corpusVersion, read from the hand-written cities collection."""
    out = {}
    for path in (SEED / "cities").glob("*.json"):
        city = json.loads(path.read_text(encoding="utf-8"))
        if city.get("corpusVersion"):
            out[path.stem] = city["corpusVersion"]
    return out


def build() -> None:
    for name in GENERATED:
        shutil.rmtree(SEED / name, ignore_errors=True)

    versions = corpus_versions()
    manifest_sources = []
    for path in sorted(GUIDES.glob("*.md")):
        meta, title, paragraphs = parse_guide(path)
        source_id = meta["source_id"]
        active = meta.get("active", True)
        version = int(meta.get("version", 1))
        city_id = slug(meta["city"])
        if city_id not in versions:
            raise ValueError(f"{path.name}: city '{city_id}' has no corpusVersion in seed/cities")
        rel = path.relative_to(ROOT).as_posix()
        checksum = sha256(title + "\n" + "\n".join(paragraphs))
        source = {
            "sourceId": source_id,
            "city": meta["city"],
            "cityId": city_id,
            "title": title,
            "contentType": meta["content_type"],
            "sourceUri": rel,
            "version": version,
            "lastReviewed": meta["last_reviewed"],
            "active": active,
            "demoOnly": meta.get("demo_only", True),
            "testFixture": meta.get("test_fixture"),
            "conflictsWith": meta.get("conflicts_with"),
            "checksum": checksum,
            "chunkCount": len(paragraphs),
            "provenance": "Original synthetic text written for the WeekendWise demo.",
        }
        write("guide_sources", source_id, source)

        for i, para in enumerate(paragraphs, start=1):
            chunk_id = f"{source_id}--c{i:02d}"
            write("guide_chunks", chunk_id, {
                "chunkId": chunk_id,
                "sourceId": source_id,
                "city": meta["city"],
                "cityId": city_id,
                "title": title,
                "section": title,
                "contentType": meta["content_type"],
                "chunkIndex": i,
                "text": para,
                "textChecksum": sha256(para),
                "lastReviewed": meta["last_reviewed"],
                "active": active,
                "version": version,
                "corpusVersion": versions[city_id],
                "chunkerVersion": CHUNKER_VERSION,
                # Filled by the ingestion job with a Firestore Vector value.
                "embedding": None,
                "embeddingModel": None,
                "embeddingDimension": None,
                "embeddingStatus": "pending",
            })
        manifest_sources.append({"sourceId": source_id, "file": rel, "cityId": city_id,
                                 "active": active, "chunks": len(paragraphs), "checksum": checksum})

    for city_id, version in sorted(versions.items()):
        city_sources = [s for s in manifest_sources if s["cityId"] == city_id]
        write("corpus_manifests", version, {
            "corpusVersion": version,
            "cityId": city_id,
            "chunkerVersion": CHUNKER_VERSION,
            "sourceCount": len(city_sources),
            "activeSourceCount": sum(s["active"] for s in city_sources),
            "chunkCount": sum(s["chunks"] for s in city_sources),
            "embeddingModel": None,
            "embeddingDimension": None,
            "firestore": {"database": "(default)", "collection": "guide_chunks", "vectorField": "embedding"},
            "sources": city_sources,
        })

    suite = json.loads(EVAL_FILE.read_text(encoding="utf-8"))
    for case in suite["cases"]:
        write("evaluation_cases", case["id"], {"suite": suite["suite"], **case})


# ---------------------------------------------------------------- validation

def load(collection: str) -> dict[str, dict]:
    folder = SEED / collection
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(folder.glob("*.json"))}


def validate() -> list[str]:
    errors: list[str] = []
    c = {p.name: load(p.name) for p in SEED.iterdir() if p.is_dir()}
    sources, chunks = c.get("guide_sources", {}), c.get("guide_chunks", {})
    cities, interests = c.get("cities", {}), c.get("interests", {})
    categories, conditions = c.get("budget_categories", {}), c.get("local_conditions", {})
    scenarios, itineraries = c.get("trip_scenarios", {}), c.get("sample_itineraries", {})
    config = c.get("app_config", {}).get("default")

    def need(cond: bool, msg: str) -> None:
        if not cond:
            errors.append(msg)

    supported = [cid for cid, city in cities.items() if city["supported"]]
    for cid in supported:
        active = [s for s in sources.values() if s["cityId"] == cid and s["active"]]
        minimum = 10
        need(len(active) >= minimum, f"cities/{cid}: needs at least {minimum} active guides, has {len(active)}")
        need(cities[cid].get("corpusVersion") in c.get("corpus_manifests", {}), f"cities/{cid}: no corpus manifest")
    for s in sources.values():
        need(s["cityId"] in supported, f"guide_sources/{s['sourceId']}: city {s['cityId']} is not supported")
    for s in sources.values():
        if s.get("conflictsWith"):
            need(s["conflictsWith"] in sources, f"{s['sourceId']}: unknown conflictsWith")

    def check_sources(owner: str, ids: list[str]) -> None:
        for sid in ids:
            need(sid in sources, f"{owner}: unknown source {sid}")

    def check_chunks(owner: str, ids: list[str], city_id: str) -> None:
        for cid in ids:
            ch = chunks.get(cid)
            if ch is None:
                errors.append(f"{owner}: unknown chunk {cid}")
                continue
            need(ch["active"], f"{owner}: cites inactive chunk {cid}")
            need(ch["cityId"] == city_id, f"{owner}: cites out-of-city chunk {cid}")

    def check_by_city(owner: str, by_city: dict[str, list[str]]) -> None:
        for cid in supported:
            need(cid in by_city, f"{owner}: no entry for supported city {cid}")
        for cid, ids in by_city.items():
            check_sources(owner, ids)
            for sid in ids:
                need(sources.get(sid, {}).get("cityId") == cid, f"{owner}: {sid} is not a {cid} source")

    for iid, i in interests.items():
        check_by_city(f"interests/{iid}", i["relatedSourceIdsByCity"])
        for cid in supported:
            need(i["relatedSourceIdsByCity"].get(cid), f"interests/{iid}: no {cid} guide")
    for bid, b in categories.items():
        check_by_city(f"budget_categories/{bid}", b["relatedSourceIdsByCity"])
        for cid in supported:
            need(b["relatedSourceIdsByCity"].get(cid), f"budget_categories/{bid}: no {cid} source")
    for doc_id, cond in conditions.items():
        need(doc_id == f"{cond['cityId']}__{cond['demoDate']}", f"local_conditions/{doc_id}: id mismatch")
        need(cond["simulated"] is True, f"local_conditions/{doc_id}: must be simulated")
        need(cond["cityId"] in cities, f"local_conditions/{doc_id}: unknown city")
    for cid, city in cities.items():
        for h in city.get("highlights", []):
            need(h["interestId"] in interests, f"cities/{cid}: unknown interest {h['interestId']}")
        ready = city.get("plannerReadiness", {})
        need(city["supported"] == (not ready.get("blockers")), f"cities/{cid}: supported flag disagrees with blockers")
        for d in city["seededConditionDates"]:
            need(f"{cid}__{d}" in conditions, f"cities/{cid}: no conditions doc for {d}")

    if config is None:
        errors.append("app_config/default missing")
    else:
        for cid in config["supportedCityIds"] + config["tripForm"]["trendingCityIds"]:
            need(cid in cities, f"app_config: unknown city {cid}")
        need(sorted(config["supportedCityIds"]) == sorted(supported), "app_config: supportedCityIds differs from cities")
        for cid in supported:
            need(config["corpusVersions"].get(cid) == cities[cid]["corpusVersion"], f"app_config: corpusVersion mismatch for {cid}")
        for cat in config["budget"]["categoryIds"]:
            need(cat in categories, f"app_config: unknown budget category {cat}")
        need(config["tools"]["allowlist"] == ["check_local_conditions"], "app_config: tool allowlist changed")

    for sid, s in scenarios.items():
        req = s["request"]
        need(req["cityId"] in cities and cities[req["cityId"]]["supported"], f"trip_scenarios/{sid}: unsupported city")
        for iid in req["interestIds"]:
            need(iid in interests, f"trip_scenarios/{sid}: unknown interest {iid}")
        check_sources(f"trip_scenarios/{sid}", s["expected"]["expectedSourceIds"])
        need(s["expected"]["sampleItineraryId"] in itineraries, f"trip_scenarios/{sid}: missing sample itinerary")

    tol = config["budget"]["arithmeticTolerance"] if config else 1
    for iid, it in itineraries.items():
        owner = f"sample_itineraries/{iid}"
        need(it["scenarioId"] in scenarios, f"{owner}: unknown scenario")
        city = it["cityId"]
        listed = {x["chunkId"] for x in it["citations"]}
        check_chunks(owner, sorted(listed), city)
        for x in it["citations"]:
            need(chunks.get(x["chunkId"], {}).get("sourceId") == x["sourceId"], f"{owner}: citation source mismatch {x['chunkId']}")
        used: set[str] = set()
        itemized: dict[str, float] = {}
        for day in it["days"]:
            for a in day["activities"]:
                used.update(a["citations"])
                cat = a["estimatedCost"]["categoryId"]
                need(cat in categories, f"{owner}/{a['id']}: unknown category {cat}")
                itemized[cat] = itemized.get(cat, 0) + a["estimatedCost"]["amount"]
            if day.get("transitTip"):
                used.update(day["transitTip"]["citations"])
            if day.get("conditions"):
                need(day["conditions"]["conditionsDocId"] in conditions, f"{owner}: unknown conditions doc")
        b = it["budget"]
        for li in b["lineItems"]:
            used.update(li["citations"])
        for sub in b.get("suggestedSubstitutions", []):
            used.update(sub["citations"])
        check_chunks(owner, sorted(used), city)
        need(used <= listed, f"{owner}: chunks used but missing from citations list: {sorted(used - listed)}")
        lines = {li["categoryId"]: li["amount"] for li in b["lineItems"]}
        need(abs(sum(lines.values()) - b["total"]) <= tol, f"{owner}: line items do not sum to total")
        for cat, amount in itemized.items():
            need(amount <= lines.get(cat, 0) + tol, f"{owner}: itemized {cat} {amount} exceeds line {lines.get(cat)}")
        over = b["total"] > b["limit"]
        need(b["status"] == ("over-budget" if over else "on-track"), f"{owner}: wrong budget status")
        if "totalAfterSubstitutions" in b:
            saved = sum(s["estimatedSavings"] for s in b["suggestedSubstitutions"])
            need(abs(b["total"] - saved - b["totalAfterSubstitutions"]) <= tol, f"{owner}: substitution math")
        need(len(it["toolCalls"]) <= (config["limits"]["maxToolCallsPerRequest"] if config else 1), f"{owner}: too many tool calls")
        for call in it["toolCalls"]:
            need(call["tool"] in (config["tools"]["allowlist"] if config else []), f"{owner}: tool not allowlisted")
            need(call["resultDocId"] in conditions, f"{owner}: tool result doc missing")
        exp = scenarios.get(it["scenarioId"], {}).get("expected", {})
        if exp:
            need(len(it["toolCalls"]) == exp["toolCalls"], f"{owner}: tool call count differs from scenario")
            need(b["status"] == exp["budgetStatus"], f"{owner}: budget status differs from scenario")
            need(it["review"]["outcome"] == exp["reviewOutcome"], f"{owner}: review outcome differs from scenario")

    cases = c.get("evaluation_cases", {})
    need(15 <= len(cases) <= 40, f"evaluation set should have 15–40 cases, has {len(cases)}")
    for cid, case in cases.items():
        check_sources(f"evaluation_cases/{cid}", case["expected_sources_any"] + case.get("forbidden_sources", []))
        case_city = slug(case["city"])
        need(case_city in cities, f"evaluation_cases/{cid}: unknown city {case['city']}")
        for sid in case["expected_sources_any"]:
            need(sources.get(sid, {}).get("cityId") == case_city, f"evaluation_cases/{cid}: expected source {sid} is not in {case_city}")
        args = case.get("expected_tool_args")
        if args and case.get("expected_tool_outcome") is None:
            key = f"{slug(args['city'])}__{args['demo_date']}"
            need(key in conditions, f"evaluation_cases/{cid}: tool args have no conditions doc {key}")
        if case.get("trip_scenario_id"):
            need(case["trip_scenario_id"] in scenarios, f"evaluation_cases/{cid}: unknown scenario")
    return errors


def main() -> int:
    if "--check" not in sys.argv:
        build()
    errors = validate()
    counts = {p.name: len(list(p.glob("*.json"))) for p in sorted(SEED.iterdir()) if p.is_dir()}
    for name, n in counts.items():
        print(f"  {name:<20} {n:>3} docs")
    if errors:
        print(f"\n{len(errors)} validation error(s):")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("\nSeed data valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
