# IAC-05 — SageMaker registry, serverless endpoint and Bedrock guardrail (Terraform)

**Type:** Infrastructure as code  
**Priority:** P0  
**Estimate:** 4–7 hours  
**Story points:** 5 (model package group, an endpoint that waits for an approved model, and a versioned guardrail)  

## User story

As the demo owner, I want the model registry, the serverless model endpoint and the Bedrock guardrail defined in Terraform so that deploying a model or changing safety rules is a reviewed code change, not a console edit.

## Scope

- **SageMaker** (`infra/stack/sagemaker.tf`):
  - model package group `dealpulse-win-model`;
  - variable `model_package_arn` (empty by default). When it is empty, no model or endpoint is created. When set to an **approved** package ARN, Terraform creates `aws_sagemaker_model` (from the package), an endpoint configuration with **serverless** settings (2,048 MB memory, max concurrency 2) and the endpoint `dealpulse-win-model`;
  - `make deploy-model MODEL=<package-arn>` sets the variable and applies; rollback is re-applying the previous ARN.
- **Bedrock guardrail** (`infra/stack/bedrock.tf`): `aws_bedrock_guardrail` + `aws_bedrock_guardrail_version` with:
  - content filter **prompt attack** at high strength on input;
  - **sensitive information**: `EMAIL` and `PHONE` set to anonymize (mask);
  - **denied topic**: "Evaluating individual employees" (judging or ranking a person's performance), with 3–5 example phrases;
  - clear blocked-input and blocked-output messages.
  Guardrail ID and version are stack outputs read by the app.
- Update `dealpulse-run` to allow `sagemaker:InvokeEndpoint` on this endpoint and `bedrock:ApplyGuardrail` on this guardrail only.

**Out of scope:** real-time (instance-based) endpoints, autoscaling policies, Model Monitor, Clarify, and a guardrail attached inside the model call (MVP-08 calls ApplyGuardrail directly).

## Acceptance criteria

- [x] With `model_package_arn` empty, `make apply` creates the package group and guardrail and no endpoint; the plan is clean on re-run.
- [ ] Setting an approved ARN creates a serverless endpoint that reaches `InService`; setting a pending ARN is refused with a clear message (checked by the make target before applying).
- [ ] Changing the ARN back to the previous value rolls the endpoint back (rehearsed once).
- [x] An `ApplyGuardrail` call on a known prompt-attack sample is blocked, and an output containing an email and phone number comes back masked.
- [x] `dealpulse-run` can invoke this endpoint and apply this guardrail, and nothing else of either kind (checked in `make verify`).

## Dependencies and deliverables

**Dependencies:** IAC-03, IAC-04.  
**Deliverables:** `sagemaker.tf`, `bedrock.tf`, `make deploy-model`, IAM updates, guide 02 (Guardrails section), guide 04 (endpoint section).

## Completion evidence

Endpoint status after deploy and after rollback, and the two guardrail checks.

## Progress record (2026-11-09) 🟡 In progress: waiting on a trained model (MVP-04)

Done and verified:
- **Applied** (free to create): the guardrail (**version 1**), model registry `dealpulse-y34c-win-model`; the app role's `ApplyGuardrail` permission narrowed from `guardrail/*` to this guardrail. No model or endpoint is created while `model_package_arn` is empty. `make verify`: both layers **no changes**.
- **Guardrail** (`bedrock.tf`): prompt-attack filter (HIGH, input), `EMAIL` and `PHONE` anonymised, denied topic "Evaluating employees" with 4 examples, plain-language blocked messages.
- **`scripts/verify_guardrail.py`** (part of `make verify`, run as the app role): **5/5 pass**. The planted injection email is blocked; an ordinary deal question passes; "rank my account executives … who I should fire" is blocked; an output with an email and phone comes back as `… at {EMAIL} or call {PHONE} …`; ordinary brief text passes.
- **IAM checks** now 32/32: the app role can apply this guardrail but not another; ingest can't apply it.
- **Endpoint code** (`sagemaker.tf`): a serverless endpoint (2,048 MB, max concurrency 2) from the approved package; model and endpoint-config names carry a hash of the package ARN so a new version swaps in cleanly (`create_before_destroy`).
- **`make deploy-model MODEL=<arn>`** checks the package's approval status first, saves the ARN in `model.auto.tfvars.json` and prints the previous ARN as the rollback command. Tested refusals: no `MODEL` → usage message; unknown package → "Model package not found". **`make models`** lists versions and approval status.

Still needed (needs MVP-04's first registered model):
- Deploy an approved version and see the endpoint reach `InService`; confirm a *pending* version is refused.
- Rehearse one rollback to a previous approved version.

### Bug found 2026-11-09: the serverless endpoint fails to start

`make deploy-model` for version 1 created the model and endpoint configuration, but the endpoint ended **Failed** after ~10 minutes ("the model process exited"). Endpoint logs: the SageMaker XGBoost container tries to **pip-install our `inference.py` source directory** into `/opt/venv` at start-up, and Serverless Inference's filesystem is read-only, so it fails with `Permission denied` (`InstallModuleError`); the model server never starts and every `/ping` fails. Training wasn't affected (training jobs have a writable disk). Terraform doesn't record a failed endpoint, which also affected teardown (handled in IAC-07).

Fix options to test on rebuild: (1) build our own small inference image on top of the XGBoost container with `inference.py` baked in, pushed to the ECR repository IAC-06 creates; (2) make the container install the module somewhere writable (`/tmp`) or skip the install; (3) as a fallback, a real-time endpoint on the smallest instance (costs per hour, so least preferred). The fix must be checked with one real deploy and a scoring call as the app role.
