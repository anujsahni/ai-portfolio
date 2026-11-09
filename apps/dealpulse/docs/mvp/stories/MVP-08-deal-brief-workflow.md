# MVP-08 — LangGraph deal-brief workflow, guardrails and reviewer

**Type:** Agent workflow  
**Priority:** P0  
**Estimate:** 8–12 hours  
**Story points:** 8 (largest logic piece: graph, prompt and schema, guardrails, code reviewer, limits and tests)  

## User story

As a sales manager, I want a short brief for a deal that explains its score, lists the risks and suggests next steps, with every point backed by a source, so that I can prepare for the forecast call in minutes without trusting unsupported claims.

## Scope

- `dealpulse/workflow.py`: a typed LangGraph state (persona, deal record, score and drivers, evidence, draft, citations, review result, revision count, trace) and explicit nodes:
  1. **load** — visibility check for the persona (reps: own deals; managers: their team), then load the deal from the CRM snapshot;
  2. **score** — MVP-05;
  3. **retrieve** — MVP-07, deal and guidance scopes;
  4. **draft** — ApplyGuardrail on the evidence and question (input) → Claude with structured output → ApplyGuardrail on the result (output);
  5. **review** — code checks below; on failure, back to draft **once** with the specific problems;
  6. **respond** — package brief, sources, draft CRM update and trace.
- **Brief schema** (structured output): `summary`, `risks[] {text, driver, citations[]}`, `next_steps[] {text, owner_role, citations[]}`, `crm_update {next_step, description}`, `open_questions[]`. Field lengths capped.
- **Prompt:** deal facts, score, drivers and passages, each wrapped with its `passage_id` and marked as untrusted content to cite, never instructions. Prompts live in `dealpulse/prompts/` and are versioned.
- **Reviewer** (`dealpulse/review.py`, no LLM), per [design §6](../../design.md#code-based-review-no-llm): citation exists and is in scope; amount, close date, stage and probability match; score described as an estimate; discounts within policy or naming the required approval; no claims of CRM changes or sent messages.
- **Follow-up Q&A:** `ask(deal, question)` retrieves deal-scoped evidence and answers with citations through the same guardrails and citation checks (1 Claude call; capped per session).
- **Limits:** at most 2 Claude calls per brief, 1 SageMaker call, 3 searches, a 60-second deadline, prompt size and output caps. All in config.
- **Trace:** user-safe step summaries ("scored the deal", "searched 14 notes", "checked 9 citations"), never model reasoning.
- Write guide 05 (the deal-brief workflow).

**Out of scope:** writing to Salesforce, sending emails, multi-deal briefs, Bedrock Agents, autonomous tool choice by the model and long-term memory.

## Acceptance criteria

- [ ] The six scripted scenarios (see MVP-11) each return a brief whose every risk and next step has at least one valid, in-scope citation.
- [ ] A persona that can't see a deal is stopped at **load** with no model, endpoint or search call made.
- [ ] Guardrails run before and after each Claude call; a blocked input or output produces a safe message and no brief text from the blocked call.
- [ ] The reviewer catches, in unit tests: an invented `passage_id`, a citation from the look-alike account, a wrong amount, "this deal will close", a 35% discount without CFO approval, and "I've updated the opportunity". Each triggers exactly one revision; a second failure shows score and evidence with a notice instead of a brief.
- [ ] The planted injection email never changes the stage, forecast or recommendations, and its instruction never appears as a next step.
- [ ] Model calls, searches, revisions, deadline and output size are bounded and covered by tests.
- [ ] Draft CRM fields fit Salesforce limits (`NextStep` ≤ 255 characters).
- [ ] The trace contains only user-safe summaries.

## Dependencies and deliverables

**Dependencies:** MVP-02, MVP-05, MVP-07, IAC-05.  
**Deliverables:** `workflow.py`, `review.py`, `prompts/`, response types, workflow and reviewer tests, `make brief DEAL=<id> PERSONA=<id>`, guide 05.

## Completion evidence

`make scenarios`: the six scenarios with expected vs. actual drivers, cited sources, Claude call count, reviewer outcome, latency and cost per brief.
