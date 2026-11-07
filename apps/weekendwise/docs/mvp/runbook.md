# WeekendWise runbook: demo, operations, and teardown

**Related story:** [MVP-09](stories/MVP-09-observability-release-demo.md) · **Commands:** [how-to 00](guides/00-provision-with-terraform.md#quick-reference)

Every command runs from the repository root. In a new terminal, first run `export TF_VAR_billing_account_id=…`. Only `make verify`, `make destroy`, and `make destroy-all` need it.

---

## Before the demo (15 minutes, the day before)

| ✓ | Check | Command | Good result |
|---|---|---|---|
| ☐ | Infrastructure has no drift | `make verify` | `no changes` twice, 29/29 retrieval cases, Cloud Run `HTTP 403 (private)` |
| ☐ | Tests pass | `make test` | all passed |
| ☐ | Cloud Run works end to end | `make smoke-cloud` | `9 of 9 checks passed` |
| ☐ | Quality hasn't regressed | `make evaluate` | 29–30 of 30 (PLAN-026 is a known limitation) |
| ☐ | Screens work in a browser | `make proxy`, then open http://localhost:8082 and run one sample trip | Plan appears in under 40 s |
| ☐ | Fallback ready | `make run` works; `reports/ui/` has screenshots from `make ui-smoke` | See [Fallback](#fallback) |
| ☐ | Spend is as expected | Console: **Billing → Reports**, filter to the project | A few cents per day of testing |

On the day: run `make smoke-cloud NO_PLAN=1` (free) about 5 minutes before, so Cloud Run has a warm instance.

---

## Demo script (3–5 minutes)

Open the app with `make proxy` (http://localhost:8082). If the service is public, use its URL.

1. **Set the scene (20 s).** "WeekendWise turns a few preferences into a cited weekend plan. Everything is sample data: fictional city guides and simulated weather. It never books anything." Point at the **LIVE AI · SAMPLE DATA** label.
2. **A preference-based plan (60 s).** San Francisco, May 14–16, 2 travelers, $600, Coffee + Art & design → **Make my weekend**. While it works, point out the live progress: "Those are the real workflow steps: it searched the guides in Firestore, then drafted with Gemini, then a code-based reviewer checked citations and budget."
3. **The itinerary (45 s).** Day tabs, the budget card ("the server adds this up itself; it doesn't trust the model's maths"), **Why this fits you**, and **How this plan came together** (one model call, five searches, time taken).
4. **Sources (30 s).** Click a **Source ↗** link: "Every activity cites a guide. Anything the model can't cite is removed, not shown."
5. **The tool and a second city (60 s).** **Edit trip** → **Try a sample: Portland rain** → **Make my weekend**. The progress list adds **Checking simulated local conditions**. On the itinerary, the meta row says *Simulated conditions for May 15 · not a forecast* and Saturday is planned indoors.
6. **A caveat or refusal (45 s).** Pick one:
   - **Napa hot day** sample: the plan includes wine tasting, and the app adds *use a designated driver, a tour, or a rideshare; never drink and drive.*
   - **SF tight budget** sample ($150): **OVER BUDGET** with cheaper swaps, and *live opening hours* listed under *Couldn't answer from the guides*.
7. **Close (20 s).** Open **Architecture** from the sidebar: "Cloud Run, Firestore vector search, Vertex AI, a bounded LangGraph workflow, all built and torn down with Terraform. There are no keys anywhere; each part has its own least-privilege identity."

Say it plainly: destination content and conditions are sample data, and no booking is made.

---

## Something is wrong

| Symptom | Check | Fix |
|---|---|---|
| Page doesn't load | `make smoke-cloud NO_PLAN=1`; console **Cloud Run → weekendwise → Revisions** | If the newest revision failed, `make deploy IMAGE=<previous tag>` (`make images` lists tags) |
| "The planner isn't available right now" | `make logs ERRORS=1` and look at `errorCategory` | `ConfigError`: an environment setting; `RefreshError`/`PermissionDenied`: identity or IAM, so run `make verify` |
| A plan fails part-way | Note the request ID (the response's `X-Request-ID` header, or `make logs`), then `make logs RID=<id>` | See below for Firestore vs model |
| **Firestore** problem | Log lines with `component=firestore` and an `errorCategory` (e.g. `FailedPrecondition` = index not ready, `PermissionDenied`) | `make verify` (index READY, read access); re-run `make seed` if the corpus is empty (`/readyz` says `corpus_empty`) |
| **Model** problem | Log lines with `component=vertex-ai`: `QuotaError` (429), `ModelTimeoutError`, `ModelAccessError` | Quota: wait a minute, or check **IAM & Admin → Quotas** for "Vertex AI … generate content requests per minute". Access: `make smoke-vertex AS=run` |
| "You've made several plans in a short time" | Per-person limit (6 per 10 minutes) | Wait, or plan from a different browser/network |
| Slow (> 40 s) | `make logs RID=<id>`: compare `latencyMs` on `model call` vs `retrieval` lines | A revision doubles the time; cold starts add a few seconds |

### Logs

Each request has one ID; every log line for it carries `requestId`. Prompts, the traveler's notes, guide text, and model output are **never** logged.

```bash
make logs                     # last hour, newest 40 lines
make logs RID=638b86398cf74f70
make logs ERRORS=1
```

In the console, **Logging → Logs Explorer** works with queries like these:

```
resource.type="cloud_run_revision" resource.labels.service_name="weekendwise"
jsonPayload.requestId="638b86398cf74f70"
```

```
resource.type="cloud_run_revision" resource.labels.service_name="weekendwise" jsonPayload.message="plan finished"
```

The fields are `stage`, `component` (`firestore` / `vertex-ai`), `modelId`, `latencyMs`, `inputTokens`, `outputTokens`, `thoughtTokens`, `resultCount`, `nearestDistance`, `toolCalls`, `modelCalls`, `status`, `budgetStatus`, `reviewOutcome`, and `errorCategory`.

### Limits that protect cost

| Limit | Where | Value |
|---|---|---|
| Instances | `max_instances` (Terraform) | min 0, max 2 |
| Plans at once / per person / per day | `PLAN_MAX_CONCURRENT` / `PLAN_RATE_PER_CLIENT` / `PLAN_DAILY_LIMIT` (per instance) | 3 / 6 per 10 min / 30 |
| Per plan | planner | ≤ 3 Gemini calls, ≤ 5 searches, 1 tool call, 150 s |
| Budget | bootstrap | $20/month, alert emails at 50/80/100% and forecast 100% (**alerts only**) |

---

## Release and rollback

```bash
make release            # tests → Cloud Build → Terraform rollout (type yes)
make smoke-cloud
```

If something's off: `make images`, then `make deploy IMAGE=<previous tag>`, then `make smoke-cloud`.

---

## Fallback

If the network or model quota fails during an interview:

1. **Local app:** `make run`, then open http://localhost:8080. This still needs Google Cloud (Firestore and Gemini), but not Cloud Run.
2. **Screenshots:** `reports/ui/` holds a desktop and phone screenshot of every sample trip (progress, itinerary, sources), from the last `make ui-smoke`. Run it the day before so they're fresh.
3. **Written evidence:** [MVP-06 scenarios](evidence/MVP-06-scenarios.md), [MVP-07 UI walkthrough](evidence/MVP-07-ui-walkthrough.md), and [MVP-08 evaluation](evidence/MVP-08-evaluation.md).
4. **No network at all:** `make mockups` serves the static mockup (sample itinerary, no AI). Say so when you show it.

---

## After the demo

| Goal | Command | Leaves |
|---|---|---|
| Stop anyone else using it | delete `allow_unauthenticated` from `infra/stack/terraform.tfvars`, then `make apply` | Private service (costs nothing while idle) |
| Remove the app but keep the project | `make destroy`, then `make verify-destroyed` | Project, budget, state bucket ($0 idle) |
| Remove everything | `make destroy-all`, then `make verify-destroyed` | Nothing; the project is pending deletion |

Check **Billing → Reports** a few days later; usage is reported with a delay.
