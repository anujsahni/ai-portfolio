# WeekendWise: an AI trip planner on Google Cloud

WeekendWise turns a few trip preferences into a cited, budget-checked weekend itinerary. It is a small, end-to-end demo of a grounded AI agent on Google Cloud: **LangGraph** runs the workflow, **Gemini and embeddings on Vertex AI** do the AI work, **Firestore vector search** finds the relevant guide passages, and **Cloud Run** hosts the app. **Terraform** creates and removes every cloud resource.

> **Demo only.** All destination guides and local conditions are synthetic. The app makes no bookings or payments and uses no real personal data.

---

## What it does

A traveler fills in a short form: destination, dates, party size, budget and interests. For example:

> *"Three days in San Francisco for two, under $600 excluding flights. We love art and coffee, and want an indoor backup if Saturday is rainy."*

A few seconds later they get:

- **A day-by-day itinerary** with times, places and short descriptions.
- **Sources for every recommendation.** Each guide-based claim links to the passage it came from, and the app checks that every citation is real.
- **A budget estimate** across stays, food and coffee, activities and local transit, with a clear "on track" or "over budget" label.
- **Weather-aware alternatives** when a simulated rainy or hot day calls for them.
- **An honest answer when evidence is thin.** If the guides don't cover a request, the app says so or asks a question instead of inventing details.
- **A short activity trace** ("searched city guides", "reviewed sources and budget") so the user can see how the plan was made.

It covers four destinations: **San Francisco, Portland, Santa Cruz and Napa Valley**.

The app has five pages, each with its own address: `/plan`, `/itinerary`, `/sources` and `/architecture` (`/` opens the plan page). The **Architecture** page is an interactive version of the diagram below. Hover over any service to see what it does, or step through a request with the arrow keys.

---

## Architecture

![WeekendWise architecture: a traveler's browser calls the WeekendWise app on Cloud Run. A LangGraph workflow validates the request, optionally checks a simulated conditions tool, retrieves guide passages from Firestore using Vertex AI embeddings, drafts an itinerary with Gemini, reviews it in code, and returns a cited plan. Cloud Build and Artifact Registry deliver the container; an offline ingestion job loads the guides; IAM, a billing budget and Terraform form the foundation.](docs/images/architecture.png)

*Teal: Google Cloud services. Gold: open-source frameworks. Coral: WeekendWise code. The numbers match the steps below and the walkthrough on the app's Architecture page.*

### How a request flows

| Step | What happens | Where |
|---|---|---|
| **1. Traveler submits a trip** | The browser sends the form to the app over HTTPS. It never talks to Vertex AI or Firestore directly. | Browser → Cloud Run |
| **2. Understand the request** | The LangGraph workflow checks the city, dates (up to 3 days), party size and budget, and stops early on anything out of scope. | LangGraph |
| **3. Check local conditions** *(optional)* | For trips that need it, such as a rainy-day request, the agent calls one allowlisted, read-only tool that returns **simulated** conditions. Arguments are validated, and the agent gets at most one call. | Conditions tool |
| **4. Retrieve evidence (RAG)** | Vertex AI turns the request into a 768-number vector. Firestore returns the 4 closest guide passages *for that city only*. Weak matches come back as "insufficient evidence", not a guess. | Vertex AI embeddings, Firestore |
| **5. Draft the itinerary** | Gemini writes the plan using only the retrieved passages and must cite a passage for every guide-based claim. | Gemini on Vertex AI |
| **6. Review and verify** | **Plain, unit-tested code** (not another AI call) checks that every citation is real and the budget math adds up (±$1), and that dates, constraints and safety caveats are correct. If something is off, the draft goes back to Gemini **once**. | WeekendWise code |
| **7. Return a cited plan** | The browser receives the itinerary, budget, sources (kept separate from AI-generated text) and the activity trace. | Cloud Run → Browser |
| **8. Observe** | Each step writes a structured log entry (request ID, step, model, latency, error type). Prompts and personal details are not logged. | Cloud Logging |

### Behind the scenes

| | What happens |
|---|---|
| **A. Load the knowledge base** | `make seed` splits 47 synthetic Markdown guides into 95 passages, embeds them with Vertex AI and writes them to Firestore. Only changed passages are re-embedded, and content updates don't need an app redeploy. |
| **B. Build and deploy** | `make build` runs the tests, then Cloud Build packages the container and stores it in Artifact Registry. `make deploy` rolls it out to Cloud Run with Terraform. Earlier images allow a one-command rollback. |
| **C. Security and cost guardrails** | Three least-privilege service accounts with no downloadable keys, a $20/month budget with alerts, and every resource created and removed by Terraform. |

### Google Cloud services used

| Service | Role in WeekendWise |
|---|---|
| **Vertex AI: Gemini** (`gemini-3.8-flash`) | Writes the itinerary, and rewrites it once if the reviewer finds problems. At most 3 model calls per trip. |
| **Vertex AI: embeddings** (`gemini-embedding-001`, 768 dimensions) | Turns guide passages and traveler requests into vectors, so passages can be matched by meaning. |
| **Firestore** (vector search) | Stores guide passages, metadata and vectors, and returns the nearest passages for a city. The app can only read it; only the ingestion job can write. |
| **Cloud Run** | Hosts the web app and planner. Scales to zero when idle, is capped at a few instances, and is private by default. |
| **Cloud Build** and **Artifact Registry** | Build the container image and store each version for deploys and rollbacks. |
| **Cloud Logging** | Structured, privacy-conscious logs for each request step. |
| **IAM** | Separate identities for running, data loading and building, each with only the access it needs. |
| **Cloud Billing budget** | $20/month budget with four alert levels. |

Not Google Cloud: **LangGraph** (agent workflow), **Starlette/Uvicorn** (web server) and **Terraform** (infrastructure as code) are open-source tools.

---

## Built-in guardrails

- **Grounded answers only.** Recommendations must cite retrieved passages, and made-up citations are rejected.
- **Bounded agent.** Per trip: at most 3 model calls, 1 tool call, 1 revision and a 150-second deadline. Prompt size and output length are capped.
- **Safe tool use.** One allowlisted, read-only tool backed by fixed data, with no network calls, bookings or payments.
- **Safety checks.** The reviewer blocks claims that something was "booked for you" and adds a drink-driving caveat to plans that mention alcohol. The guide set includes a prompt-injection test passage.
- **No secrets in code.** Google APIs are called with service identities. There are no API keys or key files, and `.env` is git-ignored.
- **Cost and abuse controls.** Cloud Run scales to zero with a small instance cap, and the app limits request size, concurrent plans, plans per client and plans per day.

---

## Results so far

| Check | Result | Details |
|---|---|---|
| Offline unit tests | 103 passing | `make test` (no cloud calls) |
| Scripted trips (all 4 cities) | 6 / 6 pass live | [MVP-06 scenario report](docs/mvp/evidence/MVP-06-scenarios.md) |
| Evaluation set | 29 / 30 cases pass every check; citation validity 55/55; safety 12/12 | [MVP-08 evaluation report](docs/mvp/evidence/MVP-08-evaluation.md) |

These are small synthetic test sets. They show the system behaves as designed, not production accuracy. Typical plan time is about 12–16 seconds.

---

## Getting started

### Option 1: See the UI with no cloud account (free)

```bash
make mockups        # then open http://localhost:8000/plan
```

This serves the clickable HTML prototype in [`artifacts/google-cloud-ai-copilot/weekendwise-mockups/`](artifacts/google-cloud-ai-copilot/weekendwise-mockups/), including the interactive Architecture page. It uses a fixed sample itinerary, with no AI and no cloud calls.

### Option 2: Run the real app on your own Google Cloud project

**You need:** a Google Cloud billing account, [Terraform](https://developer.hashicorp.com/terraform/install), the [gcloud CLI](https://cloud.google.com/sdk/docs/install) and Python 3.

> ⚠️ This links your billing account. The $20 budget **sends alerts but does not cap spending**. Run `make destroy-all` when you're done.

```bash
# One-time sign-in
gcloud auth login
gcloud auth application-default login

make tools                                    # check Terraform, gcloud and sign-in
make configure                                # create your settings with a unique project ID
export TF_VAR_billing_account_id=XXXXXX-XXXXXX-XXXXXX   # every new terminal

make bootstrap        # project, billing link, APIs, $20 budget, state bucket
make apply            # service accounts, IAM, Firestore + vector index, registry, Cloud Run
make venv             # Python environment
cp .env.example .env  # then set GCP_PROJECT_ID to your project ID
make seed             # embed the guides and load them into Firestore (well under 1 cent)
make verify           # confirm everything exists and permissions are correct

make run              # run the real app locally: http://localhost:8080 (~1 cent per plan)
```

To deploy to Cloud Run:

```bash
make release          # test, build and deploy
make proxy            # open the private service at http://localhost:8082
make smoke-cloud      # health check plus one live plan
```

To remove everything:

```bash
make destroy-all CONFIRM=<your-project-id>
make verify-destroyed
```

The full walkthrough, with expected output and troubleshooting, is in [guide 00: Provision with Terraform](docs/mvp/guides/00-provision-with-terraform.md). Run `make help` to list every command.

### Useful commands

| Command | What it does | Cost |
|---|---|---|
| `make test` | Offline unit tests | Free |
| `make ask Q="rainy day ideas" CITY=portland` | Ask one grounded question the way the app does | < 1 cent |
| `make scenarios` | Plan the 6 scripted trips and compare them with expectations | A few cents |
| `make evaluate` | Run the 30-case evaluation set | About 20–40 cents |
| `make ui-smoke` | Drive the web UI in headless Chrome | Free with `OFFLINE=1` |
| `make images` / `make deploy IMAGE=<tag>` | List images / roll back to one | Free |

---

## Cost

Expect about **$5–$30 per month** at light demo traffic, mostly from Gemini calls and Firestore usage, and close to $0 when idle because Cloud Run scales to zero. A single trip plan costs about one cent. A $20/month budget sends alerts at four thresholds.

---

## Repository layout

```text
weekendwise/            Python app: planner (LangGraph), retrieval, review, tools, Vertex AI client
  web/                  Web server (Starlette) and the browser UI, including the Architecture page
data/
  guides/               47 synthetic destination guides (Markdown)
  seed/                 Firestore-ready seed data: cities, interests, scenarios, conditions, passages
  evaluation_cases.json 30 evaluation cases with expected and forbidden sources
infra/
  bootstrap/            Terraform: project, billing link, APIs, budget, state bucket
  stack/                Terraform: IAM, Firestore, Artifact Registry, Cloud Run
scripts/                Seeding, verification, evaluation, smoke tests, mockup server
tests/                  Offline unit tests
docs/
  mvp/                  Backlog (user stories), setup guides and evidence reports
  images/               Images used in this README
artifacts/              Planning notes, Google technology brief and the HTML UI prototype
Dockerfile, cloudbuild.yaml, Makefile
```

---

## Status and scope

Build progress, story by story, is tracked in the [MVP backlog](docs/mvp/README.md). For a plain-English guide to each Google Cloud product used here, see the [Google technology brief](artifacts/google-cloud-ai-copilot/google-tech-brief.md).

**Intentionally out of scope:** live travel data, bookings and payments, user accounts, BigQuery, Vertex AI Vector Search, Agent Engine and Kubernetes. The small four-city dataset keeps the demo cheap and easy to follow. Vertex AI Vector Search is the natural next step for a much larger dataset.

**Content notice:** guide text, prices and conditions are illustrative and are not travel advice. Don't replace the synthetic guides with customer data or copyrighted travel content.
