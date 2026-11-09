# MVP-02 — Bedrock access: Claude, Titan and a smoke test

**Type:** AI platform integration  
**Priority:** P0  
**Estimate:** 3–5 hours  
**Story points:** 3 (two model clients, limits, error handling and a smoke test)  

## User story

As a developer, I want small, tested clients for Claude and Titan on Bedrock, with limits and clear errors, so that every later story calls the models the same safe way.

## Scope

- `dealpulse/config.py`: region, model IDs, timeouts and limits, read from environment variables with safe defaults:
  - Claude: `anthropic.claude-opus-5-5` (confirmed in MVP-01), effort `low` by default, output cap, 45 s timeout, 1 retry on throttling or 5xx.
  - Titan Text Embeddings V2: 1,024 dimensions, normalized, batch helper.
- `dealpulse/llm.py`: Claude calls through **Anthropic's Python SDK Bedrock client** (`AnthropicBedrockMantle`), signed with the caller's IAM credentials. Supports **structured output** (JSON schema), checks `stop_reason` (including `refusal` and `max_tokens`) before reading content, and records token usage per call.
- `dealpulse/embeddings.py`: Titan calls through `boto3` (`bedrock-runtime`), with input-length checks.
- Translate common failures into safe messages with a next step: model not enabled, access denied, throttled, timeout, region mismatch.
- `scripts/smoke_bedrock.py` (`make smoke-bedrock`): one short Claude call with a tiny JSON schema and one embedding call; prints model IDs, latency, token counts and vector length. Must run as the operator and, once IAC-03 exists, as the `dealpulse-run` role.
- Write guide 02 (Bedrock: Claude, Titan) with the confirmed IDs and limits.

**Out of scope:** Guardrails (IAC-05/MVP-08), prompts for the deal brief (MVP-08), streaming to the UI, prompt caching tuning and model fallbacks across providers.

## Acceptance criteria

- [ ] `make smoke-bedrock` returns a schema-valid JSON reply from Claude and a 1,024-length vector from Titan.
- [ ] Model IDs, effort, timeouts, retries and output caps come from config, not code, and are covered by unit tests.
- [ ] A `refusal` or `max_tokens` stop reason is handled without crashing and is reported clearly.
- [ ] Access denied, model-not-enabled, throttling and timeout produce actionable messages (unit-tested with stubbed errors).
- [ ] No API keys are used or stored; calls use IAM credentials only.
- [ ] Logs from the smoke test contain model ID, latency and token counts, but not prompt or response text.

## Dependencies and deliverables

**Dependencies:** MVP-01.  
**Deliverables:** `config.py`, `llm.py`, `embeddings.py`, `scripts/smoke_bedrock.py`, unit tests, guide 02 (first part).

## Completion evidence

Smoke-test output as the operator and as `dealpulse-run` (after IAC-03), with cost per call noted.
