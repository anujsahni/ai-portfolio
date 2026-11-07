# WeekendWise demo data

This folder contains original, short-form demo guides and deterministic evaluation fixtures for the local prototype. Text and cost ranges are synthetic/illustrative and are not verified travel advice. They exist to support UI review, ingestion development, and later RAG tests.

- `guides/`: 47 source documents with stable `source_id`, city, type, and last-reviewed metadata: 17 San Francisco (3 are test fixtures for stale/conflicting, prompt-injection, and inactive content, marked with `test_fixture`), 10 Portland, 10 Santa Cruz, and 10 Napa Valley. Every city has guides for every UI interest plus weather-planning, accessibility, and budget guides.
- `evaluation_cases.json`: 30 local evaluation records with expected sources, forbidden sources, expected tool use/arguments, and abstention rules; not yet run against Gemini or Firestore.
- `seed/`: Firestore-ready JSON for every collection the app uses (`<collection>/<docId>.json`). See [seed/README.md](seed/README.md). Rebuild and validate with `python3 scripts/build_seed_data.py`.

When Firestore is wired, the ingestion job should chunk each guide, embed it with the configured Vertex AI model, and upsert the chunk/vector records. Never replace the synthetic fixtures with employer/customer data or unlicensed travel-guide content.
