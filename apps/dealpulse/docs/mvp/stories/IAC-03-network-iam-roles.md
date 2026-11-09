# IAC-03 — Network and IAM roles (Terraform)

**Type:** Infrastructure as code + security  
**Priority:** P0  
**Estimate:** 4–6 hours  
**Story points:** 3 (small VPC, five roles with scoped policies and a verification script)  

## User story

As the demo owner, I want a small network and separate least-privilege roles for running, loading data, training and building so that each part of DealPulse can do only its own job and nothing is reachable from the internet.

## Scope

- **Network** (`infra/stack/network.tf`): a dedicated VPC with two public subnets in two Availability Zones, an internet gateway and route table. **No NAT gateway.** One security group for the app task with **no inbound rules** and outbound HTTPS only.
- **IAM roles** (`infra/stack/iam.tf`), each with an inline or managed policy scoped to named resources:

  | Role | Used by | Can |
  |---|---|---|
  | `dealpulse-run` | ECS task (the app) | invoke the named SageMaker endpoint; invoke the Claude and Titan model IDs; apply the named guardrail; `es:ESHttpGet`/`ESHttpPost` on the index's `_search` path only; read `s3://…/crm-snapshot/*`; write its log group; SSM messages for ECS Exec |
  | `dealpulse-ingest` | `make seed` (assumed by the operator) | invoke Titan; read/write the OpenSearch index; read `s3://…/knowledge/*` |
  | `dealpulse-training` | SageMaker Training jobs | read `s3://…/training/*`, write `s3://…/models/*`; write training logs |
  | `dealpulse-build` | CodeBuild | push to the ECR repository; read the source upload; write build logs |
  | `dealpulse-task-exec` | ECS agent | pull from ECR; create the log stream |

- Operators run ingest and model steps by **assuming** `dealpulse-ingest` (or passing `dealpulse-training` to SageMaker). There are no IAM users and no access keys.
- `scripts/verify_iam.py` (`make verify` part): uses the IAM policy simulator to prove key allows and denies, e.g. run **can** search but **cannot** write the index or S3; ingest **cannot** invoke Claude.

**Out of scope:** private subnets with VPC endpoints (the production path), permission boundaries, AWS Organizations SCPs and IAM Identity Center setup.

## Acceptance criteria

- [x] `make apply` creates the VPC, subnets, security group and five roles; a second plan shows no changes.
- [x] The app security group has zero inbound rules.
- [x] Every policy names specific resources (endpoint, model IDs, guardrail, index, bucket prefixes) except where AWS requires `*`, and each such exception is commented.
- [x] `make verify` shows the expected allow/deny results for at least 10 checks, including: run cannot write OpenSearch or S3; ingest cannot invoke Claude; training cannot read the CRM snapshot folder.
- [x] No IAM users or access keys are created.

## Dependencies and deliverables

**Dependencies:** IAC-02.  
**Deliverables:** `network.tf`, `iam.tf`, outputs (role ARNs, subnet and security group IDs), `scripts/verify_iam.py`.

## Completion evidence

`make verify` output with the allow/deny table.

## Completion record (2026-11-09) ✅ Done

- **Network** (`network.tf`): VPC `10.40.0.0/16`, two public subnets in two AZs, internet gateway and route table, **no NAT gateway**. The VPC's default security group is emptied. The app security group `dealpulse-y34c-app` has **0 inbound rules** and one outbound rule (TCP 443).
- **Roles** (`iam.tf`), each with one inline policy: `dealpulse-y34c-run`, `-ingest`, `-training`, `-build`, `-task-exec`. Trust: run = ECS tasks + the operator; ingest = the operator only; training = SageMaker; build = CodeBuild; task-exec = ECS tasks. Service trusts are pinned to this account (`aws:SourceAccount`).
- Resources from later stories are referenced by fixed names (`locals.names` in `main.tf`: bucket `<prefix>-data-<account>`, domain `<prefix>`, index `deal_passages`, endpoint `<prefix>-win-model`, ECR repo `<prefix>`, log group `/<prefix>/app`), so every permission is already scoped.
- **Wildcards, each commented in code:** `ssmmessages:*Channel` (ECS Exec has no resource scoping), `ecr:GetAuthorizationToken` (account-level), `cloudwatch:PutMetricData` (limited by namespace condition), SageMaker's AWS-owned image pull, and `bedrock:ApplyGuardrail` on `guardrail/*` in this account until IAC-05 creates the guardrail and narrows it.
- **Claude permissions** cover the US inference profile **and** the model in every region the profile routes to, because MVP-01 found that Opus 5.5 only accepts calls through an inference profile.
- `make apply`: 20 resources added; a second plan showed **No changes**.
- `scripts/verify_iam.py` (part of `make verify`): **29/29 checks pass**: 27 allow/deny checks across all five roles via the IAM policy simulator, plus 0 inbound rules and 0 DealPulse IAM users. Includes the story's required denies: run can't write OpenSearch or S3; ingest can't call Claude; training can't read the CRM snapshot.
- Real assume-role check: the operator **can** assume `-run`; assuming `-training` is **denied**.
- `make venv` and `make test` added (pinned `boto3`, `pytest`); 2 offline tests guard the verification plan itself.

**Deviation:** role names carry the unique prefix (`dealpulse-y34c-run`, not `dealpulse-run`) so two deployments can share an account. Stories and docs keep the short names when describing roles.
