# IAC-07 — Safe, complete teardown with Terraform

**Type:** Infrastructure as code + cost control  
**Priority:** P0  
**Estimate:** 3–5 hours  
**Story points:** 3 (ordered destroy, protection flags, confirmation and leftover check)  

## User story

As the demo owner, I want one command to remove everything DealPulse created, with a safety check and a leftover report, so that I can stop all costs after a demo, especially the hourly OpenSearch charge, without hunting through the console.

## Scope

- **`make destroy`** (routine): destroys `infra/stack`: ECS service and cluster, CodeBuild, ECR (images included), SageMaker endpoint, endpoint config, model and package group (registered versions included), guardrail, OpenSearch domain, data bucket, roles and network. Keeps the state bucket and budget so the environment can be rebuilt quickly.
- **`make destroy-all`** (final): runs `make destroy`, then destroys `infra/bootstrap` (budget, then the state bucket after its state is no longer needed).
- Both targets:
  - require typing the name prefix to confirm (no `-auto-approve` unless `CONFIRM=<prefix>` is passed);
  - show the destroy plan before asking;
  - lift protection (`prevent_destroy`-style guards, bucket `force_destroy`, ECR `force_delete`) only through variables in the destroy path, never by default.
- Also remove what Terraform doesn't own: SageMaker training jobs' output under `models/` (bucket goes with the stack), CodeBuild source zips, CloudWatch log groups created by SageMaker and CodeBuild.
- **`make verify-destroyed`**: lists anything still tagged `app = dealpulse` (Resource Groups Tagging API) plus a direct check for OpenSearch domains, SageMaker endpoints, ECS services, ECR repositories and DealPulse log groups; exits non-zero if something remains.
- Complete guide 00 with routine teardown, full teardown, rebuilding afterwards and checking cost a few days later. Document what can't be undone: deleted data, images and model versions.

**Out of scope:** scheduled automatic teardown, backups before destroy and account closure.

## Acceptance criteria

- [ ] `make destroy` followed by `make apply`, `make data`, `make train`, `make approve-model`, `make deploy-model` and `make seed` rebuilds a working stack with no manual steps.
- [x] `make destroy-all` leaves no billable DealPulse resources; `make verify-destroyed` passes.
- [x] Destroy refuses to run without the typed or passed confirmation.
- [x] Protection is on by default and only lifted inside the destroy targets.
- [x] Guide 00 covers routine teardown, full teardown, rebuild and the follow-up cost check.

## Dependencies and deliverables

**Dependencies:** IAC-02, IAC-03, IAC-04, IAC-05, IAC-06.  
**Deliverables:** destroy targets, `scripts/verify_destroyed.sh`, guide 00 (teardown section).

## Completion evidence

Output of `make destroy-all` and `make verify-destroyed`, and a billing check a few days later.

## Progress record (2026-11-09) 🟡 Built and tested without deleting; waiting on the owner's teardown run

- **`make destroy`**: shows Terraform's destroy list (35 resources today) and the items made outside Terraform, asks for the prefix, lifts the data bucket's delete protection, runs `scripts/predestroy.py`, then `terraform destroy`. **`make destroy-all`**: the same, then the state bucket, budget and cost tag. **`make verify-destroyed`** (`ALL=1` after destroy-all): checks every service directly by name and fails if anything remains; tag search is shown as a cross-check.
- **Tested safely:** `make destroy` with no confirmation listed everything and stopped with "Cancelled. Nothing was changed." `make verify-destroyed` against the live stack correctly reported 15 remaining resources (and the kept state bucket and budget). `predestroy.py --dry-run` found 3 items Terraform doesn't track.
- **Found while testing:** model version 1 had been deployed, but the endpoint **failed** (see IAC-05), so it exists in AWS but not in Terraform state. A plain `terraform destroy` would fail on the endpoint configuration and leave the endpoint behind. `predestroy.py` now deletes any DealPulse endpoint Terraform doesn't manage, and waits until it's gone.
- [Guide 00](../guides/00-provision-with-terraform.md) has the *Teardown* section: both levels, the order of operations, what can't be undone, verification and rebuild.

- **First real run stopped safely (2026-11-09 20:57 UTC):** `make destroy` hit "Error acquiring the state lock" because another session was running `make deploy-model` at the same time. The lock did its job: nothing was changed. Fix: a `_stack-not-locked` check now runs **before** the plan and the confirmation, reads the lock in S3 and explains in plain words who holds it, since when, and that `force-unlock` is only for a crashed run. Tested against the live lock.

- **Owner's teardown run (2026-11-09):** `make destroy` removed the stack, then `make destroy-all` removed the bootstrap (9 resources: state bucket and its settings, budget, cost tag). `make verify-destroyed ALL=1`: **✓ nothing left from DealPulse**. The `app` cost allocation tag is back to Inactive.
- **What tag search still lists, and why that's fine:** 7 SageMaker history records (the training-job record, which AWS doesn't allow deleting; lineage contexts and actions for the registry and endpoint attempts; a trial component), all free metadata; and 2 already-deleted security-group items the tag index hadn't caught up with (`describe-security-groups` confirms the group doesn't exist). `verify_destroyed.py` now labels these two kinds separately instead of calling everything "lag".

Still needed: the owner runs `make destroy` (or `make destroy-all`) and `make verify-destroyed`; later, rebuild from scratch to prove the round trip.
