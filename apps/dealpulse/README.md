# DealPulse: an AI deal-review assistant for Salesforce on AWS

DealPulse helps a sales team decide which deals need attention before the forecast call. For each opportunity it gives a **win probability from a model trained on past deals**, explains **why** in plain language, and writes a short **deal brief with cited evidence** and next steps from the sales playbook. It is a small, end-to-end demo of combining classic machine learning and generative AI on AWS: **SageMaker AI** trains and serves the scoring model, **OpenSearch** finds the relevant call notes and playbook passages, **Claude on Amazon Bedrock** writes the brief, **LangGraph** runs the workflow and **Streamlit** is the web app. **Terraform** creates and removes every cloud resource.

> **Demo only.** All accounts, deals, contacts and notes are synthetic, shaped like Salesforce data. DealPulse doesn't connect to a real Salesforce org, and nothing is written back to a CRM.

> **Status: in progress.** The infrastructure foundation is live on AWS; the app itself isn't built yet. See [Build progress](#build-progress). Numbers in this README are design targets, not measured results.

---

## Build progress

DealPulse is built one story at a time: **build, test, close, repeat**. Each story has acceptance criteria and a completion record in the [MVP backlog](docs/mvp/README.md).

**Points done: 18 of 83 (22%).** Stories done: 5 of 19. In progress: 2. Left: 12.

| Track | Stories | Points | Done | In progress | Left |
|---|---|---|---|---|---|
| Infrastructure (IAC) | 7 | 26 | 13 (4 stories) | 5 (IAC-05) | 8 |
| App (MVP) | 12 | 57 | 5 (1 story) | 1 (MVP-01) | 51 |
| **Total** | **19** | **83** | **18** | **6** | **59** |

| # | Story | Pts | Status |
|---|---|---|---|
| IAC-01 | [Terraform foundation, state and make commands](docs/mvp/stories/IAC-01-terraform-foundation-state.md) | 3 | ✅ Done |
| IAC-02 | [Account guardrails: budget, tags and region](docs/mvp/stories/IAC-02-account-budget-tags.md) | 2 | ✅ Done |
| MVP-01 | [AWS account, model access and guardrails](docs/mvp/stories/MVP-01-aws-account-model-access.md) | 1 | 🟡 Waiting on owner (Anthropic use-case form) |
| MVP-02 | [Bedrock access: Claude, Titan and a smoke test](docs/mvp/stories/MVP-02-bedrock-access.md) | 3 | ⬜ To do |
| IAC-03 | [Network and IAM roles](docs/mvp/stories/IAC-03-network-iam-roles.md) | 3 | ✅ Done |
| IAC-04 | [S3 data bucket and OpenSearch domain](docs/mvp/stories/IAC-04-s3-opensearch.md) | 5 | ✅ Done |
| MVP-03 | [Synthetic Salesforce data generator](docs/mvp/stories/MVP-03-synthetic-salesforce-data.md) | 5 | ✅ Done |
| IAC-05 | [SageMaker registry, serverless endpoint and Bedrock guardrail](docs/mvp/stories/IAC-05-sagemaker-guardrail.md) | 5 | 🟡 Guardrail live; endpoint failed to start (fix planned) |
| MVP-04 | [Win-probability model](docs/mvp/stories/MVP-04-win-probability-model.md) | 8 | 🟡 Code ready; waiting on the SageMaker run |
| MVP-05 | [Deal scoring and plain-language drivers](docs/mvp/stories/MVP-05-scoring-drivers.md) | 3 | ⬜ To do |
| MVP-06 | [Knowledge base ingestion](docs/mvp/stories/MVP-06-knowledge-base-ingestion.md) | 5 | ⬜ To do |
| MVP-07 | [Deal-scoped hybrid retrieval and citations](docs/mvp/stories/MVP-07-deal-scoped-retrieval.md) | 5 | ⬜ To do |
| MVP-08 | [LangGraph deal-brief workflow, guardrails and reviewer](docs/mvp/stories/MVP-08-deal-brief-workflow.md) | 8 | ⬜ To do |
| IAC-06 | [ECR, CodeBuild and private ECS service](docs/mvp/stories/IAC-06-ecr-codebuild-ecs.md) | 5 | ⬜ To do |
| MVP-09 | [App container on ECS Fargate](docs/mvp/stories/MVP-09-app-container-ecs.md) | 3 | ⬜ To do |
| MVP-10 | [Streamlit pages and interaction flow](docs/mvp/stories/MVP-10-streamlit-pages.md) | 8 | 🟡 Streamlit app runs offline (`make run`); live data to follow |
| MVP-11 | [Evaluation, safety and regression tests](docs/mvp/stories/MVP-11-evaluation-safety.md) | 5 | ⬜ To do |
| IAC-07 | [Safe, complete teardown](docs/mvp/stories/IAC-07-teardown-destroy.md) | 3 | 🟡 Teardown verified; rebuild round trip pending |
| MVP-12 | [Observability, release and demo runbook](docs/mvp/stories/MVP-12-observability-release-demo.md) | 3 | ⬜ To do |

**Live on AWS today:** nothing. Everything was torn down with `make destroy-all` on 2026-11-09 and verified with `make verify-destroyed ALL=1`. The app runs locally in offline mode (`make run`); rebuilding the cloud side is `make bootstrap`, `make apply RISK_CHECK=1`, `make data`, `make train`.

---

## What it does

A sales manager opens DealPulse before the weekly forecast call:

> *"Which of my team's Commit deals are actually at risk this quarter, and what should we do about them?"*

**On the Pipeline page** they see every open deal this quarter, each with:

- **The rep's forecast** (Salesforce forecast category and stage probability) next to **the model's win probability**.
- **A flag where the two disagree**, for example "Commit, but the model says 31%".
- **The top risk driver** in plain words, such as "no meeting with an executive in 34 days".

**On a Deal brief page**, a few seconds after picking one deal, they get:

- **A score card**: win probability, how it compares with similar deals, and the 3–5 drivers that move it up or down.
- **A short brief** covering what's happening, the main risks and recommended next steps. **Every claim links to its source**: a call note, an email, a playbook section or a past win/loss review. The app checks that every citation is real and belongs to this deal.
- **A draft Salesforce update** (Next Step and Description fields) for the rep to review and paste in. DealPulse never edits the CRM itself.
- **Follow-up questions**, such as "What did they say about pricing?", answered only from this deal's notes, with citations.
- **A short activity trace** ("scored the deal", "searched 14 notes", "checked citations") so the user can see how the brief was made.

The app has five pages, each with its own address: `/pipeline`, `/deal`, `/sources`, `/model` and `/architecture`. The **Model** page is a model card: what the model was trained on, how well it did on held-out deals and what it can't do. The **Architecture** page is an interactive version of the diagram below. Hover over any service to see what it does, or step through a deal review with the arrow keys.

### Who it's for

| Person | Question they bring | What DealPulse gives them |
|---|---|---|
| **Sales manager** (primary) | "Which deals should I worry about before the forecast call?" | Pipeline view sorted by risk, with model vs. rep disagreements flagged |
| **Account executive** | "What should I do next on this deal?" | A cited brief, next steps from the playbook and a draft CRM update |
| **RevOps analyst** | "Can we trust the score?" | The Model page: features, held-out accuracy against Salesforce's stage-based probability, known limits |

A "viewing as" selector switches between a rep (own deals only) and a manager (their team's deals), the way Salesforce sharing rules would. It's simulated and isn't a real login.

---

## Architecture

![DealPulse architecture: a sales manager's browser reaches the DealPulse Streamlit app on ECS Fargate through a private tunnel. A LangGraph workflow loads the deal from an S3 CRM snapshot, scores it with a SageMaker serverless endpoint, retrieves deal notes and playbook passages from OpenSearch using Titan embeddings, drafts a cited brief with Claude on Amazon Bedrock behind Bedrock Guardrails, verifies it in code and returns it. Offline jobs generate synthetic Salesforce data, train and register the model, and load the knowledge base. CodeBuild, ECR, IAM, AWS Budgets and Terraform form the foundation.](docs/images/architecture.png)

*Orange: AWS services. Purple: open-source frameworks. Blue: DealPulse code. Dashed grey: a future connection to a real Salesforce org. The numbers and letters match the steps below and the walkthrough on the app's Architecture page. This image is rendered from the same files as that page (`scripts/render_architecture.py`), so the two stay in sync.*

### How a deal review flows

| Step | What happens | Where |
|---|---|---|
| **1. Open the pipeline or a deal** | The browser loads the app through a private tunnel. It never talks to Bedrock, SageMaker or OpenSearch directly. | Browser → ECS |
| **2. Load the deal and check access** | The workflow confirms the "viewing as" persona may see the deal, then reads the opportunity, contact roles, stage history, activities and open support cases from the CRM snapshot. | LangGraph, S3 |
| **3. Score the deal** | Shared feature code turns the deal into about 20 numbers. The SageMaker endpoint returns a win probability and each feature's contribution, which become the plain-language drivers. The Pipeline page scores all open deals in **one batched call with no LLM**, so it stays fast and nearly free. | SageMaker AI |
| **4. Retrieve evidence (RAG)** | The top risk drivers become targeted questions ("executive sponsor", "budget approval"). Titan turns them into vectors, and OpenSearch runs **hybrid keyword + vector** searches over *this deal's* notes, plus the shared playbook and win/loss reviews. Weak matches come back as "no evidence found", not a guess. | Bedrock (Titan), OpenSearch |
| **5. Draft the brief** | Guardrails screen the evidence for prompt attacks. Claude writes a structured brief (summary, risks, next steps, draft CRM update) using only the score and the evidence, and cites a passage for every claim. Guardrails screen the answer again and mask contact details. | Bedrock Guardrails, Claude on Bedrock |
| **6. Review and verify** | **Plain, unit-tested code** (not another AI call) checks that every citation exists and belongs to this deal or the shared playbook, that amounts, dates and the score match the CRM data, and that no suggested discount breaks policy. If something is off, the draft goes back to Claude **once**. | DealPulse code |
| **7. Return the brief** | The user sees the score card, drivers, cited brief, sources (kept separate from AI text), a draft CRM update and the activity trace. | ECS → Browser |
| **8. Observe** | Each step writes a structured log entry (request ID, step, model or endpoint, latency, error type). Prompts, notes and contact details are not logged. | CloudWatch Logs |

### Behind the scenes

| | What happens |
|---|---|
| **A. Generate the CRM data** | `make data` runs a seeded generator that writes Salesforce-shaped records for a fictional software vendor to S3: accounts, opportunities, contacts, stage history, activities, cases and notes. A hidden rule decides which deals win, so we can check that the model learns the right drivers. Later, a nightly export from a real Salesforce org could fill the same bucket. |
| **B. Train and register the model** | `make train` starts a SageMaker Training job that fits an XGBoost model on point-in-time snapshots of closed deals and tests it on the newest quarter. The result is registered as *pending* in the Model Registry. After a person reads the evaluation report, `make approve-model` and `make deploy-model` point the serverless endpoint at it through Terraform. |
| **C. Load the knowledge base** | `make seed` splits notes, playbooks and win/loss reviews into about 1,000 passages, embeds them with Titan and loads them into OpenSearch. Only changed passages are re-embedded, and new notes need no redeploy. |
| **D. Build and deploy** | `make build` runs the tests, then CodeBuild packages the container and stores it in ECR. `make deploy` rolls it out to ECS with Terraform. Earlier images allow a one-command rollback. |
| **E. Security and cost guardrails** | Least-privilege IAM roles with no access keys, a $60/month budget with alerts, and every resource created and removed by Terraform. |

### AWS services used

Each row says what the service is in plain terms, then what it does in DealPulse.

| Service | What it is | Role in DealPulse |
|---|---|---|
| **Amazon SageMaker AI**: Training, Model Registry, Serverless Inference | AWS's platform for building, training and hosting your **own** machine-learning models on your own data. | Trains the XGBoost win-probability model on historical deals, keeps each version with its metrics and an approval gate, and serves it from a serverless endpoint that scales to zero. Returns per-feature contributions (SHAP values) so every score can be explained. |
| **Amazon Bedrock**: Claude (`anthropic.claude-opus-5-5`) | A managed service that offers **ready-made** foundation models through one API. There's nothing to train or host. | Writes the deal brief and the draft CRM update, and answers follow-up questions, only from evidence it is given. At most 2 calls per brief. Called with Anthropic's Python SDK (Bedrock client) using the app's IAM role, with no API key. |
| **Amazon Bedrock**: Titan Text Embeddings V2 | An embedding model: it turns text into a list of numbers (a vector) so passages with similar meaning sit close together. | Embeds every note and playbook passage (1,024 dimensions) during ingestion, and each search query at runtime. |
| **Amazon Bedrock Guardrails** | Configurable safety filters for text going into and out of a model. | Blocks prompt attacks hidden in notes or questions, masks email addresses and phone numbers in output, and refuses requests to judge individual employees. Called on its own (ApplyGuardrail) before and after each Claude call. |
| **Amazon OpenSearch Service** | A managed search engine that does keyword search and vector (nearest-neighbor) search in the same index. | Stores passages with metadata (account, opportunity, document type, date) and vectors. **Hybrid search** mixes keyword matching (names, products, competitors) with meaning-based matching. Every query is filtered to one deal, in code. |
| **Amazon ECS on AWS Fargate** | Runs containers without managing servers. | Hosts the Streamlit app and the LangGraph workflow as one small task with **no inbound access**. Operators reach it through an SSM port-forwarding tunnel (`make proxy`). |
| **Amazon S3** | Object storage. | Holds the CRM snapshot, training data, evaluation reports and model files. Versioned, with all public access blocked. |
| **AWS CodeBuild** and **Amazon ECR** | A managed build service and a private container registry. | Build and scan the container image, and store each version for deploys and rollbacks. |
| **Amazon CloudWatch Logs** | Managed log storage and search. | Structured, privacy-conscious logs for each step, kept for 14 days. |
| **AWS IAM** | Controls who, or what, can do what. | Separate roles for the app, ingestion, builds and SageMaker training, each with only the access it needs. No access keys anywhere. |
| **AWS Budgets** | Cost tracking with alerts. | $60/month budget with four alert levels. |

Not AWS: **LangGraph** (agent workflow), **Streamlit** (web app), **XGBoost** (model library) and **Terraform** (infrastructure as code) are open-source tools.

### Why both SageMaker and Bedrock?

They do different jobs, and DealPulse uses each where it is strongest.

| | SageMaker AI (the score) | Bedrock (the brief) |
|---|---|---|
| **Question it answers** | "How likely is this deal to close?" | "Why, and what should we do?" |
| **Input** | About 20 numbers per deal | Score, drivers and text passages |
| **Learns from** | *Your* history: thousands of past deals and how they ended | General knowledge; it isn't trained on your data |
| **Strengths** | Calibrated, consistent, cheap (well under a cent per score), auditable against a baseline | Reads messy notes, explains in plain language, suggests actions |
| **Weakness covered by the other** | Can't read a call note or explain itself in words | Can't produce a calibrated probability from past outcomes |

Asking an LLM to "estimate the win probability" would produce a confident-sounding number with no grounding in what actually happened to similar deals. The model provides the number, and Claude explains it.

---

## Built-in guardrails

- **Grounded answers only.** Every claim in a brief must cite a retrieved passage, and code rejects made-up citations or citations from another account.
- **Deal isolation.** Searches are filtered to the selected deal in code, never by the model. The evaluation set includes look-alike accounts to catch leaks.
- **The score is advisory.** The brief calls the probability an estimate and never changes a forecast category. Rep identity and win rate are deliberately **not** model features, so the score rates the deal, not the person.
- **Human in the loop.** DealPulse drafts CRM updates; people apply them. Nothing is written to Salesforce.
- **Bounded agent.** Per brief: at most 2 Claude calls, 1 revision, 3 searches and a 60-second deadline. Prompt size and output length are capped.
- **Prompt-injection defense.** Bedrock Guardrails screen retrieved text, and the code-based reviewer ignores instructions found inside notes. The synthetic data includes a planted email that tries to make the assistant "mark this deal Closed Won".
- **Model release gate.** A new model version serves traffic only after a person approves it in the Model Registry.
- **No secrets in code.** AWS calls use IAM roles. There are no access keys or API keys, and `.env` is git-ignored.
- **Cost and abuse controls.** Serverless model endpoint, a single small container, request limits per session, `make pause` between demos and a budget with alerts.

---

## Success criteria (targets)

Planned checks, in the style of WeekendWise's evaluation reports. These are **targets**, not results.

| Check | Target |
|---|---|
| Offline unit tests | All pass with no cloud calls (`make test`) |
| Model vs. baseline | Beats Salesforce's stage-based probability on the held-out quarter, on both ranking (AUC) and calibration (Brier score) |
| Driver recovery | The top model drivers match the generator's hidden rule |
| Retrieval | The expected passage appears in the top 5 results for at least 90% of 30 retrieval cases |
| Citations | 100% of citations valid and in scope; **zero** cross-account leaks (a hard gate) |
| Safety | The planted prompt-injection email never changes a recommendation; contact emails and phone numbers are masked |
| Speed | Pipeline page under 3 seconds when warm; a deal brief in about 15–25 seconds |

---

## Getting started (planned)

The commands mirror WeekendWise. They aren't implemented yet.

### Option 1: Run the app with no cloud account (free)

```bash
make venv           # once
make run            # the Streamlit app on saved data: http://localhost:8501/
make mockups        # or the static clickable mockup: http://localhost:8000/#pipeline
```

The app runs in offline mode: saved synthetic deals with real scores from the trained model and three hand-written sample briefs ([guide 07](docs/mvp/guides/07-web-app.md)).

This serves the [clickable mockup](artifacts/dealpulse-mockups/README.md) of all five pages (Pipeline, Deal brief, Sources, Model, Architecture), using the synthetic CRM and real scores from the trained model. No AWS calls. The Architecture page alone is also at [`dealpulse/ui/architecture/index.html`](dealpulse/ui/architecture/index.html).

### Option 2: Run the real app on your own AWS account

**You'll need:** an AWS account with Bedrock model access for Claude and Titan in `us-east-1` (Anthropic models may ask for a one-time use-case form), [Terraform](https://developer.hashicorp.com/terraform/install), the [AWS CLI](https://docs.aws.amazon.com/cli/) with the Session Manager plugin, and Python 3.

> ⚠️ The $60 budget **sends alerts but does not cap spending**. The OpenSearch domain bills by the hour even when idle. Run `make destroy-all` when you're done.

```bash
aws sso login                  # short-lived credentials; no access keys
make tools                     # check Terraform, AWS CLI, plugin and sign-in
make configure                 # create your settings with a unique name prefix

make bootstrap                 # state bucket, budget
make apply                     # network, IAM, S3, OpenSearch, guardrail, ECR, CodeBuild, ECS
make venv && cp .env.example .env
make data                      # generate synthetic Salesforce data into S3 (free)
make train                     # SageMaker training job + evaluation report (a few cents)
make approve-model             # after reading the report
make deploy-model              # point the serverless endpoint at the approved version
make seed                      # embed notes and playbooks into OpenSearch (well under 1 cent)
make verify                    # confirm resources and permissions

make run                       # run the app locally against AWS: http://localhost:8501
```

To deploy and use the hosted app:

```bash
make release                   # test, build and deploy to ECS
make proxy                     # private tunnel to the task: http://localhost:8502
make pause / make resume       # scale the app to 0 / 1 tasks
```

To remove everything:

```bash
make destroy-all CONFIRM=<your-name-prefix>
make verify-destroyed
```

---

## Cost

Estimated for `us-east-1` with light demo use. These figures are estimates; check current AWS prices before relying on them.

| Item | Approx. monthly cost |
|---|---|
| OpenSearch: one `t3.small.search` node + 10 GB storage | ~$27 (runs even when idle) |
| ECS Fargate: 0.5 vCPU, 1 GB, always on, plus one public IPv4 address | ~$22 (≈ $0 after `make pause`) |
| SageMaker Serverless Inference | Cents (pay per request; scales to zero) |
| SageMaker Training (`ml.m5.large`, a few minutes per run) | Cents per run |
| Claude on Bedrock | About 5–15 cents per deal brief |
| Titan embeddings, Guardrails, S3, ECR, CloudWatch, CodeBuild | A dollar or two |

**Expect about $50–60 per month if left running**, about $30 with the app paused, and $0 after `make destroy-all`. This is higher than WeekendWise, because a search cluster can't scale to zero the way Firestore and Cloud Run can.

**Choices made to keep cost down:** a single small managed OpenSearch node instead of OpenSearch Serverless (which has a much higher minimum charge), no load balancer and no NAT gateway (private tunnel instead), a serverless model endpoint, and an LLM only on the Deal brief page, never on the Pipeline page.

---

## Repository layout (planned)

```text
dealpulse/              Python app
  ui/                   Streamlit pages; ui/architecture/ is the interactive Architecture page
  workflow.py           LangGraph deal-brief workflow
  features.py           Feature code shared by training and serving
  scoring.py            SageMaker endpoint client
  retrieval.py          Titan embeddings + OpenSearch hybrid search
  llm.py                Claude on Bedrock + Guardrails
  review.py             Code-based citation, number and policy checks
ml/                     Training and inference scripts for SageMaker (XGBoost)
data/
  generator/            Seeded synthetic Salesforce data generator
  playbooks/            Synthetic sales playbook and pricing policy
  evaluation_cases.json Evaluation cases with expected and forbidden sources
infra/
  bootstrap/            Terraform: state bucket, budget
  stack/                Terraform: network, IAM, S3, OpenSearch, SageMaker endpoint, guardrail, ECR, CodeBuild, ECS
scripts/                Seeding, training, verification, evaluation, rendering
tests/                  Offline unit tests
docs/
  design.md             Use-case analysis and design decisions
  mvp/                  Backlog: user stories with acceptance criteria, guides and evidence
  images/               Images used in this README
Dockerfile, buildspec.yml, Makefile
```

---

## Status and scope

The use-case analysis, data model, model design and the reasons behind each choice are in [docs/design.md](docs/design.md). Build progress, story by story, is tracked in the [MVP backlog](docs/mvp/README.md).

**Intentionally out of scope for the MVP:** a live Salesforce connection and write-back, real user login (SSO), Salesforce Data Cloud, Amazon Bedrock Agents and Knowledge Bases (LangGraph and OpenSearch keep each step visible), OpenSearch Serverless, a public load balancer, and model monitoring. Each is a natural next step once the demo works end to end.

**Content notice:** all companies, people, deals and notes are fictional. Don't load real customer or CRM data into this demo.
