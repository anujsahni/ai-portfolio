#!/usr/bin/env python3
"""MVP-02 smoke test: one short Gemini call and one embedding call.

Usage:
  python scripts/smoke_vertex.py                         # as your signed-in account
  python scripts/smoke_vertex.py --as SERVICE_ACCOUNT    # impersonate a service account

Cost: one tiny prompt and three short embeddings (well under one cent).
Prints only model IDs, locations, sizes, timings, and token counts; never prompts or credentials.
"""
from __future__ import annotations

import argparse
import math
import sys
import time
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from weekendwise.config import load_settings  # noqa: E402
from weekendwise.errors import WeekendWiseError  # noqa: E402
from weekendwise.vertex import VertexClient  # noqa: E402


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--as", dest="impersonate", help="service account email to impersonate")
    args = parser.parse_args()

    try:
        settings = load_settings()
        if args.impersonate:
            settings = replace(settings, impersonate_service_account=args.impersonate)
        client = VertexClient(settings)
        who = settings.impersonate_service_account or "signed-in user (ADC)"
        print(f"project:    {settings.project_id}")
        print(f"identity:   {who}")
        print(f"limits:     prompt ≤ {settings.max_prompt_chars} chars, output ≤ {settings.max_output_tokens} tokens, "
              f"timeout {settings.request_timeout_seconds:g}s, retries {settings.model_retry_attempts}")

        print(f"\n1) Generation  {settings.generation_model_id} @ {settings.generation_location} (thinking {settings.thinking_level})")
        result = client.generate_text("Reply with exactly one word: ok", max_output_tokens=64, temperature=0)
        print(f"   ✓ reply={result.text!r} finish={result.finish_reason} tokens in/out/thought="
              f"{result.input_tokens}/{result.output_tokens}/{result.thought_tokens or 0} in {result.latency_ms} ms")

        print(f"\n2) Embeddings  {settings.embedding_model_id} @ {settings.embedding_location} (dimension {settings.embedding_dimension})")
        start = time.monotonic()
        docs = client.embed_documents([
            "A relaxed coffee stop at the Ferry Building with a short waterfront walk.",
            "A redwood loop walk in a state park a short drive inland.",
        ])
        query = client.embed_query("where can I get coffee by the water?")
        ms = int((time.monotonic() - start) * 1000)
        print(f"   ✓ 2 document vectors + 1 query vector, each {len(query)} dimensions, in {ms} ms")
        near, far = cosine(query, docs[0]), cosine(query, docs[1])
        verdict = "✓" if near > far else "✗"
        print(f"   {verdict} sanity: coffee query is closer to the coffee passage ({near:.3f}) than the redwoods one ({far:.3f})")
        print("\nSmoke test passed." if near > far else "\nEmbeddings returned but ranking looks wrong.")
        return 0 if near > far else 1
    except WeekendWiseError as err:
        print(f"\n✗ {type(err).__name__}: {err.message}")
        if err.hint:
            print(f"  Next step: {err.hint}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
