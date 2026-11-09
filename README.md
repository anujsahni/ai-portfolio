# AI Portfolio

An independent portfolio repository of AI application demos on Google Cloud and AWS. This is not an official Google or AWS project.

## Apps

| App | Cloud | Description | Status |
|---|---|---|---|
| [WeekendWise](apps/weekendwise/README.md) | Google Cloud | Grounded AI weekend trip planner using LangGraph, Gemini and embeddings on Vertex AI, Firestore vector search, and Cloud Run. | Implemented demo; cloud resources are configured/deployed per app instructions. |
| [DealPulse](apps/dealpulse/README.md) | AWS | AI deal-review assistant for Salesforce-style sales pipelines. A SageMaker AI model scores each deal's win probability, OpenSearch finds the call notes and playbook passages behind the score, and Claude on Amazon Bedrock (with Guardrails) writes a cited deal brief. Built with LangGraph and Streamlit on ECS Fargate; Terraform provisions everything. | In progress: 18 of 83 story points done ([build progress](apps/dealpulse/README.md#build-progress)). |

Each app is self-contained: application code, data, tests, scripts, documentation, infrastructure, build configuration, dependencies, and local environment live inside its directory. Shared root files are limited to portfolio navigation, repository-wide ignore rules, and optional command shortcuts.

### DealPulse at a glance

DealPulse helps a sales manager decide which deals need attention before the weekly forecast call. It puts a model-based win probability next to each rep's forecast, flags where they disagree, and explains why with evidence from the deal's own notes. It pairs **classic machine learning** (an XGBoost model trained on past deals in SageMaker) with **generative AI** (Claude on Bedrock), and it never writes to the CRM. All data is synthetic and Salesforce-shaped.

- [README](apps/dealpulse/README.md): what it does, architecture, AWS services explained, cost
- [Interactive architecture page](apps/dealpulse/dealpulse/ui/architecture/index.html): open in a browser; hover services, step through a request
- [Design doc](apps/dealpulse/docs/design.md): use case, data model, model design and decisions
- [MVP backlog](apps/dealpulse/docs/mvp/README.md): 19 stories with acceptance criteria and completion records

## Local development

Open an app’s README for setup details. Optional root-level shortcuts delegate into the app directory:

- `make help` — list portfolio shortcuts
- `make weekendwise-test` — run that app’s offline tests
- `make weekendwise-mockups` — serve its static UI preview on loopback
- `make dealpulse-test` — run DealPulse's offline tests
- `make dealpulse-verify` — check DealPulse's AWS resources for drift and permissions (reads only)
- `make dealpulse-architecture` — render DealPulse's architecture diagram to its README image

For app-specific commands, run Make from that app’s directory, e.g. `make test` from `apps/weekendwise/` or `make help` from `apps/dealpulse/`.
