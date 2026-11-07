# IAC-06 — Safe, complete teardown with Terraform

**Type:** Infrastructure as code + cost control  
**Priority:** P0  
**Estimate:** 3–5 hours  
**Story points:** 3 (ordered destroy, protection flags, confirmation, and leftover check)  

## User story

As the demo owner, I want one command to remove everything WeekendWise created, with a safety check and a leftover report, so that I can stop all costs after a demo without hunting through the console.

## Scope

- **`make destroy`** (routine): destroys `infra/stack` only (Cloud Run, Artifact Registry, Firestore database and index, service accounts, IAM). Keeps the project, billing link, budget, and state bucket so the environment can be rebuilt quickly.
- **`make destroy-all`** (final): runs `make destroy`, then destroys `infra/bootstrap`: the state bucket (after its state is no longer needed), budget, APIs, and the project itself, which shuts it down and schedules it for deletion.
- Both targets:
  - require typing the project ID to confirm (no `-auto-approve` unless `CONFIRM=<project-id>` is passed),
  - show the destroy plan before asking,
  - turn off delete protection flags (Firestore, Cloud Run, project `deletion_policy`) only through variables in the destroy path, never by default.
- **`make verify-destroyed`**: lists anything left in the project (Cloud Run services, repositories, Firestore databases, service accounts, budget) and exits non-zero if something remains.
- Document what can't be undone: deleted Firestore data, deleted images, and the roughly 30-day hold on project IDs and the `(default)` database name.

**Out of scope:** scheduled automatic teardown (a possible later story), deleting billing accounts, and backups before destroy.

## Acceptance criteria

- [ ] `make destroy` followed by `make apply` (and `make seed`) rebuilds a working stack with no manual steps.
- [ ] `make destroy-all` leaves no billable WeekendWise resources; `make verify-destroyed` passes, and the project shows as pending deletion.
- [ ] Destroy refuses to run without the typed or passed project ID confirmation.
- [x] Protection flags are on by default and only lifted inside the destroy targets.
- [x] The how-to covers routine teardown, full teardown, re-creation after full teardown (a new project ID suffix), and the cost check afterward.

## Dependencies and deliverables

**Dependencies:** IAC-02, IAC-03, IAC-04, IAC-05.  
**Deliverables:** `destroy`, `destroy-all`, and `verify-destroyed` targets, a teardown script, and how-to sections.

## Completion evidence

Logs from one full cycle: `make bootstrap` → `make apply` → `make destroy` → `make apply` → `make destroy-all` → `make verify-destroyed`, plus a Billing report check a few days later.

## Progress record — 🟡 Routine teardown verified, waiting for rebuild and full teardown (updated 2026-11-06)

Done:
- `make destroy` lists the stack resources it will remove (a read-only destroy plan), then asks for the project ID (or `CONFIRM=`). It lifts Firestore **and** Cloud Run delete protection only inside the destroy path, destroys the stack, and forgets the deployed image so the next `make apply` starts cleanly.
- `make destroy-all` shows the same list plus the bootstrap scope before asking.
- `make verify-destroyed` (`scripts/verify_destroyed.sh`, read-only) works in both cases:
  - Project still active (routine teardown): checks there are no Cloud Run services, registries, Firestore databases, WeekendWise service accounts, or stack state, and lists what is kept on purpose.
  - Project pending deletion: checks the bootstrap state is empty.
  - Exits non-zero if anything remains. Tested against the live stack: it correctly listed everything as still present and failed.
- How-to 00 covers routine and full teardown, the rebuild (`make apply && make seed && make release && make smoke-cloud`), what can't be undone, and the cost check.

Rehearsal so far (2026-11-06, UTC):
- ✅ `make apply` (22:34) → `make release` (22:42–23:10) on `weekendwise-demo-jytx`, with Cloud Run and Firestore deletion protection on.
- ✅ `make destroy` (23:11): removed Cloud Run (4 revisions), the Artifact Registry repository, the Firestore database and vector index, and the 3 service accounts. Protection was lifted only inside the destroy path.
- ✅ `make verify-destroyed`: no Cloud Run services, registries, Firestore databases, WeekendWise service accounts, or stack state. Kept on purpose: project, billing link, $20 budget, the state bucket, and Cloud Build's source bucket.

Still needed (owner), continuing the same cycle: `make apply && make seed && make release` → `make smoke-cloud` (proves the rebuild needs no manual steps) → `make destroy-all CONFIRM=<project-id>` → `make verify-destroyed`, then a billing check a few days later.
