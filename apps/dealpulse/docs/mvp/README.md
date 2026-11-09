# DealPulse MVP backlog

This folder is the implementation source of truth for the DealPulse demo. Each story has a bounded scope, dependencies, deliverables and testable acceptance criteria. The MVP uses synthetic, Salesforce-shaped data. It doesn't connect to a real Salesforce org, write to a CRM or use real customer data.

The *why* behind the design (use case, data model, model design, platform choices) is in [docs/design.md](../design.md). The interactive architecture is in [dealpulse/ui/architecture/](../../dealpulse/ui/architecture/index.html).

## Product outcome

A sales manager picks a "viewing as" persona and opens the Pipeline page. Every open deal this quarter shows the rep's forecast next to a **win probability from a SageMaker model** trained on past deals, with deals flagged where the two disagree. Opening a deal runs a bounded LangGraph workflow: score the deal, retrieve that deal's notes and the shared playbook from OpenSearch, have **Claude on Amazon Bedrock** (behind Bedrock Guardrails) draft a cited brief, and check it in code. The user sees the score and its drivers, the brief with sources, a draft Salesforce update to copy, and an activity trace.

## MVP stack

- **Infrastructure as code:** Terraform (two root modules: `infra/bootstrap` and `infra/stack`) driven by `make` targets. No manual console provisioning beyond sign-in and Bedrock model access.
- **AWS:** Amazon SageMaker AI (Training, Model Registry, Serverless Inference), Amazon Bedrock (Claude Opus 5.5, Titan Text Embeddings V2, Guardrails), Amazon OpenSearch Service, Amazon ECS on Fargate, Amazon S3, AWS CodeBuild, Amazon ECR, Amazon CloudWatch Logs, AWS IAM, AWS Budgets. Region `us-east-1`.
- **Application:** Python, LangGraph, Streamlit; Anthropic's Python SDK (Bedrock client) for Claude; `boto3` for SageMaker, Titan and Guardrails; `opensearch-py` for search.
- **Model:** XGBoost (SageMaker framework container, script mode) trained on point-in-time snapshots of synthetic closed deals, with SHAP contributions for explanations.
- **RAG:** synthetic activity notes, playbook, pricing policy and win/loss reviews, embedded with Titan and stored in one OpenSearch index with hybrid (keyword + vector) search, filtered per deal in code.

## Story order

Stories are listed in build order. **IAC** stories provision infrastructure with Terraform; **MVP** stories build the product on top of it.

| # | ID | Story | Depends on | Points |
|---|---|---|---|---|
| 1 | [IAC-01](stories/IAC-01-terraform-foundation-state.md) | Terraform foundation, state and make commands | — | 3 |
| 2 | [IAC-02](stories/IAC-02-account-budget-tags.md) | Account guardrails: budget, tags and region (Terraform) | IAC-01 | 2 |
| 3 | [MVP-01](stories/MVP-01-aws-account-model-access.md) | AWS account, model access and guardrails (approve and verify) | IAC-02 | 1 |
| 4 | [MVP-02](stories/MVP-02-bedrock-access.md) | Bedrock access: Claude, Titan and a smoke test | MVP-01 | 3 |
| 5 | [IAC-03](stories/IAC-03-network-iam-roles.md) | Network and IAM roles (Terraform) | IAC-02 | 3 |
| 6 | [IAC-04](stories/IAC-04-s3-opensearch.md) | S3 data bucket and OpenSearch domain (Terraform) | IAC-03 | 5 |
| 7 | [MVP-03](stories/MVP-03-synthetic-salesforce-data.md) | Synthetic Salesforce data generator (`make data`) | IAC-04 | 5 |
| 8 | [IAC-05](stories/IAC-05-sagemaker-guardrail.md) | SageMaker registry, serverless endpoint and Bedrock guardrail (Terraform) | IAC-03, IAC-04 | 5 |
| 9 | [MVP-04](stories/MVP-04-win-probability-model.md) | Win-probability model: features, training, evaluation, registry | MVP-03, IAC-05 | 8 |
| 10 | [MVP-05](stories/MVP-05-scoring-drivers.md) | Deal scoring and plain-language drivers | MVP-04 | 3 |
| 11 | [MVP-06](stories/MVP-06-knowledge-base-ingestion.md) | Knowledge base ingestion (`make seed`) | MVP-02, MVP-03, IAC-04 | 5 |
| 12 | [MVP-07](stories/MVP-07-deal-scoped-retrieval.md) | Deal-scoped hybrid retrieval and citations | MVP-06 | 5 |
| 13 | [MVP-08](stories/MVP-08-deal-brief-workflow.md) | LangGraph deal-brief workflow, guardrails and reviewer | MVP-02, MVP-05, MVP-07, IAC-05 | 8 |
| 14 | [IAC-06](stories/IAC-06-ecr-codebuild-ecs.md) | ECR, CodeBuild and private ECS service (Terraform) | IAC-03 | 5 |
| 15 | [MVP-09](stories/MVP-09-app-container-ecs.md) | App container on ECS Fargate | MVP-08, IAC-06 | 3 |
| 16 | [MVP-10](stories/MVP-10-streamlit-pages.md) | Streamlit pages and interaction flow | MVP-05, MVP-08, MVP-09 | 8 |
| 17 | [MVP-11](stories/MVP-11-evaluation-safety.md) | Evaluation, safety and regression tests | MVP-04, MVP-07, MVP-08, MVP-10 | 5 |
| 18 | [IAC-07](stories/IAC-07-teardown-destroy.md) | Safe, complete teardown (Terraform) | IAC-02 – IAC-06 | 3 |
| 19 | [MVP-12](stories/MVP-12-observability-release-demo.md) | Observability, release and demo runbook | MVP-09, MVP-11, IAC-07 | 3 |

By track: IAC 26 points (7 stories), MVP 57 points (12 stories), 83 in total.

Points use a Fibonacci scale (1, 2, 3, 5, 8) for relative size, based on each story's hour estimate, number of moving parts and risk. A story counts as done only when every acceptance criterion is met.

## Provisioning and setup guides (to be written during the build)

Each guide is delivered by the story that first needs it, as in WeekendWise.

- **[00 — Provision and destroy with Terraform](guides/00-provision-with-terraform.md)** (IAC-01, completed by IAC-07): the only supported way to create, change or remove infrastructure.
- [01 — AWS account, budget and Bedrock model access](guides/01-account-budget-model-access.md) (MVP-01)
- 02 — Bedrock: Claude, Titan and Guardrails (MVP-02, IAC-05)
- [03 — OpenSearch and the knowledge base](guides/03-opensearch-knowledge-base.md) (IAC-04, MVP-06)
- 04 — SageMaker: training, registry and serverless endpoint (MVP-04)
- 05 — The deal-brief workflow (LangGraph) (MVP-08)
- 06 — ECS deployment and the private tunnel (IAC-06, MVP-09)
- [07 — The web app](guides/07-web-app.md) (MVP-10)
- 08 — Evaluation and safety tests (MVP-11)
- **Runbook: demo, operations and teardown** (MVP-12)

Console guides are references for inspecting what Terraform creates; don't use them to change resources by hand. AWS console labels, model availability, IAM actions, quotas and pricing can change; confirm them at implementation. Enabling model access, creating paid resources or making anything public requires the account owner's authorization.

## Definition of MVP done

- A browser user, through the private tunnel, can open the Pipeline page and see every open deal scored, with model-vs-forecast disagreements flagged, in under 3 seconds when warm.
- For each of the six scripted deal scenarios, the Deal brief page returns a score with drivers and a brief whose every claim cites a passage from that deal or the shared playbook.
- Missing evidence is stated rather than invented; no citation ever points to another account.
- The model is trained by SageMaker on point-in-time snapshots, beats the Salesforce stage-probability baseline on the held-out quarter (AUC and Brier score), and is served only after manual approval in the Model Registry.
- The workflow is bounded (≤ 2 Claude calls, 1 SageMaker call, 3 searches, 60 s per brief), guarded by Bedrock Guardrails and a code-based reviewer, and never claims to have changed the CRM.
- The app labels all data as synthetic, scores deals not people, and offers draft CRM updates only.
- All infrastructure is created by `make bootstrap` / `make apply` and fully removed by `make destroy-all`, with no manual console steps beyond sign-in and model access.
- The running app uses an IAM task role with least privilege, has no inbound access, emits privacy-conscious logs and sits under a budget with alerts.
- Evaluation results and a 3–5 minute demo runbook are checked in.

## Scope guardrails

No live Salesforce connection or write-back, Amazon AppFlow, Salesforce Data Cloud, real login (Cognito/SSO), public load balancer, NAT gateway, OpenSearch Serverless, Bedrock Agents or Knowledge Bases, SageMaker real-time endpoints, Model Monitor, Clarify jobs, Kubernetes or real customer data in this MVP. Terraform is limited to one demo environment in one account; CI-driven applies are a later option.

## Implementation status

Build, test and close one story at a time. Done: 18 of 83 points.

| ID | Story | Points | Status | Delivered | Still needed |
|---|---|---|---|---|---|
| IAC-01 | Terraform foundation, state and make commands | 3 | ✅ Done | `infra/bootstrap` (S3 state bucket) + `infra/stack` (S3 state, native locking), pinned Terraform/provider + lock files, `Makefile`, [guide 00](guides/00-provision-with-terraform.md); live run clean | — |
| IAC-02 | Account guardrails: budget, tags and region | 2 | ✅ Done | $60/month budget on tag `app=dealpulse` with 4 alerts, cost tag activated by Terraform, budget in `make verify` | — |
| MVP-01 | AWS account, model access and guardrails | 1 | 🟡 Waiting on owner | Budget verified; Titan V2 authorized; Opus 5.5 found (inference profile only); [guide 01](guides/01-account-budget-model-access.md) | Owner submits Anthropic use-case form; then confirm access |
| MVP-02 | Bedrock access: Claude, Titan and a smoke test | 3 | ⬜ To do | — | All |
| IAC-03 | Network and IAM roles | 3 | ✅ Done | VPC (no NAT), app SG with 0 inbound rules, 5 scoped roles; `make verify` 29/29 IAM checks; operator can assume run, not training | — |
| IAC-04 | S3 data bucket and OpenSearch domain | 5 | ✅ Done | Data bucket; OpenSearch 3.7 on 1 × t3.small (IAM-only, encrypted); `deal_passages` index + hybrid pipeline; risk check passed (filtered hybrid search, 121 ms); 8/8 access checks; [guide 03](guides/03-opensearch-knowledge-base.md) | — |
| MVP-03 | Synthetic Salesforce data generator | 5 | ✅ Done | `make data`: 2,460 opps, 678 notes, 12,886 point-in-time training rows, 42 knowledge docs, 7 scenarios/traps; all volumes ±10%, all checks pass, reproducible; uploaded to S3 ([report](evidence/MVP-03-data-summary.md)) | — |
| IAC-05 | SageMaker registry, serverless endpoint and Bedrock guardrail | 5 | 🟡 Waiting on MVP-04 | Guardrail v1 live (5/5 checks: injection blocked, contact details masked, no judging employees); model registry; endpoint code + `make deploy-model` approval gate; IAM 32/32 | **Endpoint fails to start (read-only filesystem; see story)**; fix, deploy, rollback rehearsal |
| MVP-04 | Win-probability model | 8 | 🟡 Code ready | `features.py`, `ml/train.py` + `inference.py` (XGBoost 3.2 container), `make train`/`approve-model`, report; local dry run: AUC 0.888 vs baseline 0.703, 9/9 driver directions | SageMaker run; decision on the top-6 driver criterion |
| MVP-05 | Deal scoring and plain-language drivers | 3 | ⬜ To do | — | All |
| MVP-06 | Knowledge base ingestion | 5 | ⬜ To do | — | All |
| MVP-07 | Deal-scoped hybrid retrieval and citations | 5 | ⬜ To do | — | All |
| MVP-08 | LangGraph deal-brief workflow, guardrails and reviewer | 8 | ⬜ To do | — | All |
| IAC-06 | ECR, CodeBuild and private ECS service | 5 | ⬜ To do | — | All |
| MVP-09 | App container on ECS Fargate | 3 | ⬜ To do | — | All |
| MVP-10 | Streamlit pages and interaction flow | 8 | 🟡 App runs offline | Mockup ([artifact](https://claude.ai/artifact/HybQdgsSUP5qcRXXP2aZL9)) + **Streamlit app with all 5 pages** on saved data (`make run`), 14 UI tests, [guide 07](guides/07-web-app.md) | Live data from MVP-05/07/08; live UI smoke test |
| MVP-11 | Evaluation, safety and regression tests | 5 | ⬜ To do | — | All |
| IAC-07 | Safe, complete teardown | 3 | 🟡 Teardown verified | `make destroy` + `destroy-all` run by the owner; `make verify-destroyed ALL=1`: nothing left (only free SageMaker history records remain); lock check before confirmation | Rebuild round trip (`make bootstrap` → `apply` → `data` → `train`) |
| MVP-12 | Observability, release and demo runbook | 3 | ⬜ To do | — | All |
