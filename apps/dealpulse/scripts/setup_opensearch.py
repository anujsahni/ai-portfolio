#!/usr/bin/env python3
"""IAC-04: create the deal_passages index and the hybrid search pipeline (idempotent).

Runs as the ingest role, the only app identity allowed to change the index. Run by `make apply`
after Terraform. With --risk-check it also proves that vector + hybrid search with a deal filter
works on this domain: it embeds 4 sample passages with Titan (a fraction of a cent), searches
them in a temporary index, then deletes that index.

Usage: python scripts/setup_opensearch.py [--risk-check]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dealpulse import search_index  # noqa: E402
from dealpulse.awsenv import role_session, stack_outputs  # noqa: E402


def ensure_index(os_client, index: str) -> str:
    if not os_client.indices.exists(index=index):
        os_client.indices.create(index=index, body=search_index.INDEX_BODY)
        return "created"
    live = os_client.indices.get_mapping(index=index)[index]["mappings"]["properties"]
    wanted = search_index.INDEX_BODY["mappings"]["properties"]
    missing = sorted(set(wanted) - set(live))
    if missing:
        return f"DIFFERS (missing fields {missing}); recreate with --recreate-index (deletes passages; re-run make seed)"
    if live["embedding"].get("dimension") != search_index.EMBEDDING_DIMENSION:
        return "DIFFERS (embedding dimension); recreate with --recreate-index"
    return "unchanged"


def ensure_pipeline(os_client, name: str) -> str:
    body = search_index.pipeline_body()
    try:
        live = os_client.transport.perform_request("GET", f"/_search/pipeline/{name}")[name]
        if live.get("phase_results_processors") == body["phase_results_processors"]:
            return "unchanged"
        status = "updated"
    except Exception as exc:  # 404 when the pipeline doesn't exist yet
        if getattr(exc, "status_code", None) != 404:
            raise
        status = "created"
    os_client.transport.perform_request("PUT", f"/_search/pipeline/{name}", body=body)
    return status


def embed(session, model_id: str, text: str) -> list[float]:
    response = session.client("bedrock-runtime").invoke_model(
        modelId=model_id,
        body=json.dumps({"inputText": text, "dimensions": search_index.EMBEDDING_DIMENSION, "normalize": True}),
    )
    return json.loads(response["body"].read())["embedding"]


def risk_check(os_client, session, model_id: str, pipeline: str) -> bool:
    """Index sample passages in a temporary index and run a deal-filtered hybrid query."""
    temp = "deal_passages_riskcheck"
    docs = [
        ("A1", "OPP-A", "CFO said the FY27 budget for the platform is not approved yet; asked for a phased rollout."),
        ("A2", "OPP-A", "Demo went well with the data team. Champion is the head of analytics."),
        ("B1", "OPP-B", "Northbeam CFO approved the budget and signed the order form."),
        ("B2", "OPP-B", "Security review complete; SOC 2 report accepted by procurement."),
    ]
    if os_client.indices.exists(index=temp):
        os_client.indices.delete(index=temp)
    os_client.indices.create(index=temp, body=search_index.INDEX_BODY)
    try:
        for pid, opp, text in docs:
            os_client.index(index=temp, id=pid, body={
                "passage_id": pid, "text": text, "doc_type": "call_note", "opportunity_id": opp,
                "account_id": f"ACC-{opp}", "active": True, "embedding": embed(session, model_id, text),
            })
        os_client.indices.refresh(index=temp)
        question = "Has the budget been approved by finance?"
        query = search_index.hybrid_query(
            question, embed(session, model_id, question),
            filters=[{"term": {"opportunity_id": "OPP-A"}}], size=3,
        )
        started = time.perf_counter()
        hits = os_client.search(index=temp, body=query, params={"search_pipeline": pipeline})["hits"]["hits"]
        ms = (time.perf_counter() - started) * 1000
        ids = [hit["_id"] for hit in hits]
        print(f"  hybrid query (filter OPP-A) → {ids} in {ms:.0f} ms")
        only_scoped = bool(ids) and all(i.startswith("A") for i in ids)
        top_is_budget = bool(ids) and ids[0] == "A1"
        print(f"  {'✓' if only_scoped else '✗'} results only from the filtered deal (B1 also mentions a budget and must not appear)")
        print(f"  {'✓' if top_is_budget else '✗'} the budget note ranks first")
        return only_scoped and top_is_budget
    finally:
        os_client.indices.delete(index=temp)
        print(f"  temporary index {temp} deleted")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--risk-check", action="store_true", help="also prove deal-filtered hybrid search works (≈ $0.0001)")
    parser.add_argument("--recreate-index", action="store_true", help="delete and recreate the index (removes all passages)")
    args = parser.parse_args()

    out = stack_outputs()
    os_info = out["opensearch"]
    session = role_session("ingest", session_name="setup-opensearch")
    os_client = search_index.client(session, os_info["endpoint"])

    index, pipeline = os_info["index"], os_info["search_pipeline"]
    if args.recreate_index and os_client.indices.exists(index=index):
        os_client.indices.delete(index=index)
        print(f"  deleted index {index}")
    print(f"✓ index {index}: {ensure_index(os_client, index)}")
    print(f"✓ search pipeline {pipeline}: {ensure_pipeline(os_client, pipeline)}")
    if args.risk_check:
        print("── Risk check: deal-filtered hybrid search on this domain")
        if not risk_check(os_client, session, out["models"]["titan_model_id"], pipeline):
            print("✗ Risk check failed; see design §8 before building retrieval on this instance type")
            return 1
        print("✓ Risk check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
