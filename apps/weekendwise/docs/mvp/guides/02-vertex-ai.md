# Setup guide 02 — Vertex AI Gemini and text embeddings

**Related stories:** [MVP-02](../stories/MVP-02-vertex-ai-access.md), [IAC-03](../stories/IAC-03-service-identities-iam.md)
**Purpose:** Configure and smoke-test server-side Gemini generation and text embeddings for WeekendWise.
**Time:** about 5 minutes after [how-to 00](00-provision-with-terraform.md) Steps 1–9

> The Vertex AI API and service-account permissions are provisioned by Terraform (IAC-02, IAC-03). This guide covers the model choice, local configuration, and smoke tests.

---

## Chosen models (verified 2026-11-06 on `weekendwise-demo-jytx`)

| Use | Model ID | Location | Settings | Fallback |
|---|---|---|---|---|
| Generation | `gemini-3.8-flash` | `global` | thinking level `LOW` | `gemini-3.5-flash` |
| Embeddings (documents and queries) | `gemini-embedding-001` | `us-central1` | 768 dimensions | `text-embedding-005` (768) |

How these were picked:

- Listed Google's models in `us-central1` and kept only **generally available** (GA) ones.
- Called each candidate with a one-word prompt:
  - Gemini models answered only from the **`global`** endpoint; in `us-central1` they returned 404.
  - `gemini-2.5-flash` returned 404 everywhere for this project.
  - `gemini-embedding-2` returned 404.
- `gemini-3.8-flash` is the newest GA Flash model. With thinking left at its default, a short reply used the whole token allowance on internal "thinking"; at `LOW` it answers normally.
- 768 dimensions keeps vectors well under Firestore's 2,048 limit and storage small.
- `global` means Google may serve Gemini requests from any region. That's fine for synthetic demo data; revisit it for real user data.

**Changing the embedding model or dimension later** means re-embedding every chunk and recreating the Firestore vector index (IAC-04). Documents and queries must always use the same model and dimension.

Check current pricing on the [Generative AI pricing page](https://cloud.google.com/vertex-ai/generative-ai/pricing) before heavy use. A smoke test costs well under one cent.

---

## Step 1 — Set up Python (once)

```bash
make venv
```

This creates `.venv` and installs the pinned dependencies from `requirements-dev.txt` (`google-genai`, `google-auth`, `pytest`). Expected ending: `✓ Python environment ready (Python 3.x.x)`.

## Step 2 — Configure

```bash
cp .env.example .env     # skip if .env already exists
```

Set `GCP_PROJECT_ID` to your project (from `make bootstrap`). The model values are already filled in:

| Variable | Value | Meaning |
|---|---|---|
| `VERTEX_GENERATION_MODEL_ID` | `gemini-3.8-flash` | Gemini model |
| `VERTEX_GENERATION_LOCATION` | `global` | Where Gemini is called |
| `VERTEX_THINKING_LEVEL` | `LOW` | `MINIMAL`, `LOW`, `MEDIUM`, or `HIGH` |
| `VERTEX_EMBEDDING_MODEL_ID` | `gemini-embedding-001` | Embedding model for documents and queries |
| `VERTEX_EMBEDDING_LOCATION` | `us-central1` | Where embeddings are called |
| `VERTEX_EMBEDDING_DIMENSION` | `768` | Must match the Firestore vector index (1–2048) |
| `MAX_PROMPT_CHARS` | `24000` | Prompts over this are refused before calling the model |
| `MAX_OUTPUT_TOKENS` | `2048` | Upper limit on reply length |
| `MAX_EMBEDDING_BATCH` | `50` | Texts per embedding request |
| `REQUEST_TIMEOUT_SECONDS` | `45` | Per-request timeout |
| `MODEL_RETRY_ATTEMPTS` | `1` | Retries for 429/5xx only |

Environment variables override `.env`. The app reads these through `weekendwise/config.py` only, so model IDs aren't scattered through the code. If anything is missing or out of range, every problem is listed in one error.

## Step 3 — Run the offline tests

```bash
make test
```

Expected: `18 passed`. These use a fake client and make no cloud calls. They cover limits, the shared embedding model for documents and queries, dimension checks, and error messages.

## Step 4 — Smoke test as yourself

```bash
make smoke-vertex
```

Expected:

```
1) Generation  gemini-3.8-flash @ global (thinking LOW)
   ✓ reply='ok' finish=STOP tokens in/out/thought=7/1/57 in ~4000 ms

2) Embeddings  gemini-embedding-001 @ us-central1 (dimension 768)
   ✓ 2 document vectors + 1 query vector, each 768 dimensions, in ~900 ms
   ✓ sanity: coffee query is closer to the coffee passage (0.736) than the redwoods one (0.587)

Smoke test passed.
```

## Step 5 — Smoke test as the Cloud Run identity

After `make apply` has created the service accounts (IAC-03):

```bash
make smoke-vertex AS=run
```

This runs the same test while impersonating `weekendwise-run@<project>.iam.gserviceaccount.com`, which proves the runtime identity can call both models without any key file. New permissions can take 1–2 minutes to apply; if you get "Permission denied" right after `make apply`, wait and retry.

---

## Error messages

Every failure prints a plain message and a next step, without credentials or raw API responses:

| You see | Meaning | Next step |
|---|---|---|
| `ConfigError: … VERTEX_EMBEDDING_DIMENSION is not set` | Missing/invalid setting | Fix `.env` |
| `ConfigError: No Google credentials found` / `sign-in failed or expired` | Not signed in | `gcloud auth application-default login` |
| `ModelAccessError: Permission denied … (as <identity>)` | Identity lacks Vertex AI access | Check IAC-03 roles; wait for new grants to apply |
| `ModelAccessError: … was not found or this project can't use it` | Wrong model ID or location | Check the ID; Gemini needs `global` |
| `QuotaError` | Rate or quota limit | Wait and retry; request more quota if it persists |
| `ModelTimeoutError` | No reply within the timeout | Retry; shorten the prompt |
| `ModelResponseError: … finish reason: MAX_TOKENS` | Reply cut off before any text | Raise the output limit or lower the thinking level |

## Reference

- Code: [weekendwise/config.py](../../../weekendwise/config.py), [weekendwise/vertex.py](../../../weekendwise/vertex.py), [weekendwise/errors.py](../../../weekendwise/errors.py), [scripts/smoke_vertex.py](../../../scripts/smoke_vertex.py)
- [Vertex AI generative AI overview](https://cloud.google.com/vertex-ai/generative-ai/docs/learn/overview)
- [Text embeddings](https://cloud.google.com/vertex-ai/generative-ai/docs/embeddings/get-text-embeddings)
- [Generative AI pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing)
- [Vertex AI IAM access control](https://cloud.google.com/vertex-ai/docs/general/access-control)
