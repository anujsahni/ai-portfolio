# AI Portfolio

Three working AI application demos, each built end to end on a different platform: **Google Cloud**, **AWS** and **local Docker**. Every app answers one realistic business question, uses only synthetic data, and is built and tested one story at a time.

This is an independent portfolio. It is not an official Google, AWS, Fivetran, dbt Labs or Anthropic project.

## Portfolio at a glance

| App | The question it answers | Platform | AI at its core | Status |
|---|---|---|---|---|
| [**WeekendWise**](apps/weekendwise/README.md) | "Plan me a weekend trip I can trust." | Google Cloud | A grounded agent: LangGraph, Gemini and embeddings on Vertex AI, Firestore vector search, with every claim cited | **Built and evaluated:** 29 of 30 evaluation cases pass |
| [**DealPulse**](apps/dealpulse/README.md) | "Which deals need attention before the forecast call, and why?" | AWS | Classic ML plus generative AI: an XGBoost win-probability model on SageMaker, OpenSearch retrieval, Claude on Bedrock with Guardrails | **In progress:** 18 of 83 points ([progress](apps/dealpulse/README.md#build-progress)) |
| [**ContextLoop**](apps/contextloop/README.md) | "Which strategic accounts are at risk from late shipments?" (and why the agent gets it wrong without a data foundation) | Local Docker | A Claude agent, first on raw SQL, then through MCP servers over dbt, a semantic layer and freshness checks | **[Presentation](https://d36gkxgniq3znf.cloudfront.net/):** 78 of 80 points, pitch video published |

**What they have in common:**
- **Synthetic data only.** No real customers, CRMs, bookings or travel data. Each README says what is simulated.
- **Infrastructure as code.** Terraform creates and removes every cloud resource; ContextLoop runs everything in one `docker compose` stack.
- **Guardrails built in.** Least-privilege access, budgets with alerts, prompt-injection defences, and answers that cite their evidence.
- **Story-by-story delivery.** Each app has a backlog with acceptance criteria and a completion record for every finished story.

---

## WeekendWise at a glance

*Google Cloud · grounded AI agent*

WeekendWise turns a few trip preferences (city, dates, party size, budget, interests) into a **cited, budget-checked weekend itinerary**, with weather-aware alternatives and an honest "not enough evidence" when the guides don't cover a request. It covers four destinations: San Francisco, Portland, Santa Cruz and Napa Valley.

- **How it works:** a LangGraph workflow validates the request, retrieves guide passages from Firestore vector search (Vertex AI embeddings), drafts the plan with Gemini, then checks every citation and the budget in plain, unit-tested code before returning it. It runs on Cloud Run.
- **Results:** 103 offline tests pass; 6 of 6 scripted trips pass live; 29 of 30 evaluation cases pass every check, with citation validity 55/55 and safety 12/12.
- **Cost:** about $5–30 a month at light demo traffic, about 1 cent per plan, and close to $0 when idle (Cloud Run scales to zero). A $20 budget sends alerts.
- **Explore:** [README](apps/weekendwise/README.md) · [MVP backlog](apps/weekendwise/docs/mvp/README.md) · [evaluation report](apps/weekendwise/docs/mvp/evidence/MVP-08-evaluation.md)

## DealPulse at a glance

*AWS · classic ML plus generative AI*

DealPulse helps a sales manager decide which deals need attention before the weekly forecast call. It puts a **model-based win probability** next to each rep's forecast, flags where they disagree, and explains why with **cited evidence** from the deal's own notes and the sales playbook. It never writes to the CRM.

- **How it works:** an XGBoost model trained on past deals in SageMaker scores each opportunity; OpenSearch finds the call notes and playbook passages behind the score; Claude on Amazon Bedrock, with Guardrails, writes a cited deal brief. LangGraph and Streamlit run on ECS Fargate, and Terraform provisions everything.
- **Status:** the infrastructure foundation is built and its teardown is verified. Nothing is running on AWS right now (torn down on 9 November 2026); the app runs locally in offline mode.
- **Cost:** about $50–60 a month if left running (mostly the OpenSearch node), about $30 with the app paused, and $0 after `make destroy-all`.
- **Explore:** [README](apps/dealpulse/README.md) · [interactive architecture page](apps/dealpulse/dealpulse/ui/architecture/index.html) · [design doc](apps/dealpulse/docs/design.md) · [MVP backlog](apps/dealpulse/docs/mvp/README.md)

## ContextLoop at a glance

*Local Docker · "Your AI agent is only as good as your data"*

A chief operating officer asks an AI agent which strategic accounts are at risk because of late shipments. On raw data the agent is **fluent, precise and wrong**. ContextLoop then builds the data foundation in five acts and asks the **same model the same question**: this time the answer is right, with cited metric definitions, lineage and a freshness warning, and it is pushed back into the CRM.

- **The five acts:** (1) the confident wrong answer; (2) **Move**, with Fivetran Connector SDK connectors; (3) **Transform and trust**, with dbt models, tests and contracts, a MetricFlow semantic layer, and Apache Iceberg read by two engines; (4) **Context**, with the dbt MCP server plus metrics and freshness MCP servers; (5) **Activate**, with reverse ETL to a mock Salesforce and Slack.
- **Results:** the same Claude model scores **2.7 of 6** on six golden questions with raw SQL access, and **6.0 of 6** with the governed tools, averaged over 3 recorded runs each. It needs 5 calls instead of 16.
- **Watch it:** the narrated 7-minute pitch is published at **https://d36gkxgniq3znf.cloudfront.net/** (S3 and CloudFront, created with Terraform).
- **Cost:** $0 to run: it all runs on a laptop with Docker.
- **Explore:** [README](apps/contextloop/README.md) · [getting started](apps/contextloop/docs/getting-started.md) · [talk track](apps/contextloop/docs/demo/talk-track.md) · [Q&A](apps/contextloop/docs/demo/qa.md) · [MVP backlog](apps/contextloop/docs/mvp/INDEX.md)

---

## Repository layout

Each app is self-contained: its code, data, tests, scripts, documentation, infrastructure, build configuration, dependencies and local environment all live inside its own directory under `apps/`. The repository root holds only this navigation page, repository-wide ignore rules (secrets, Terraform state, and heavy video and audio files) and optional command shortcuts.

```
apps/
├── weekendwise/   # Google Cloud: grounded trip-planning agent
├── dealpulse/     # AWS: deal-review assistant (ML + generative AI)
└── contextloop/   # Local Docker: data foundation for AI agents
```

## Local development

Open an app's README for setup details. Optional shortcuts at the root delegate into each app directory (`make help` lists them):

| App | Shortcut | What it does |
|---|---|---|
| WeekendWise | `make weekendwise-test` | Run its offline tests |
| | `make weekendwise-mockups` | Serve its static UI preview on loopback |
| | `make weekendwise-help` | Show all WeekendWise commands |
| DealPulse | `make dealpulse-test` | Run its offline tests |
| | `make dealpulse-verify` | Check its AWS resources for drift and permissions (reads only) |
| | `make dealpulse-architecture` | Render its architecture diagram to its README image |
| | `make dealpulse-help` | Show all DealPulse commands |
| ContextLoop | `make contextloop-demo` | Start the Docker stack (data, sync, build) and open the app at http://127.0.0.1:8501 |
| | `make contextloop-test` | Run its tests inside the Docker stack |
| | `make contextloop-pitch` | Publish the pitch video to its public watch page |
| | `make contextloop-help` | Show all ContextLoop commands |

For anything else, run Make from the app's directory: for example `make help` in `apps/weekendwise/`, `apps/dealpulse/` or `apps/contextloop/`.
