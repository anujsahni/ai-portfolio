# 00 — Provision and destroy with Terraform

Terraform is the only supported way to create, change or remove DealPulse's AWS resources. This guide grows story by story; sections for later stories are marked *(coming in …)*.

> ⚠️ **Costs.** Most of what bootstrap creates is free, but later stories create billed resources (OpenSearch bills by the hour, even when idle). An AWS budget **sends alerts; it does not stop spending.** Remove everything with `make destroy-all` when you're done (IAC-07).

## How it's organised

| Layer | Folder | State | Creates |
|---|---|---|---|
| Bootstrap | `infra/bootstrap/` | Local file, git-ignored | Terraform state bucket; $60 budget (IAC-02) |
| Stack | `infra/stack/` | S3 bucket from bootstrap, with native locking | Network, IAM, S3, OpenSearch, SageMaker, guardrail, ECR, CodeBuild, ECS (IAC-03 to IAC-06) |

Every resource carries the tags `app=dealpulse`, `env=demo`, `managed_by=terraform` and `name_prefix=<your prefix>`, so you can find all of them in the console (Resource Groups → Tag Editor) and the teardown check can spot leftovers.

## What you need

- **Terraform 1.10 or newer** (for S3 state locking). If Homebrew only offers 1.5.7, download the official binary from <https://developer.hashicorp.com/terraform/install> and put it on your `PATH` (for example `~/.local/bin`).
- **AWS CLI v2** and the **Session Manager plugin** (used later by `make proxy`).
- **Python 3.11+**.
- An AWS sign-in with permission to create the resources. `make` uses the AWS profile in `AWS_PROFILE` (default: `default`). Short-lived sign-in (`aws sso login`) is preferred; an IAM user with access keys also works.

## First-time setup

```bash
make tools          # checks Terraform 1.10+, AWS CLI, plugin, Python and who you're signed in as
make configure      # creates infra/bootstrap/terraform.tfvars with a unique prefix, e.g. dealpulse-y34c
make bootstrap-plan # preview (read-only)
make bootstrap      # creates the state bucket; writes infra/stack/backend.hcl and bootstrap.auto.tfvars.json
make apply          # creates/updates the stack
make verify         # drift check for both layers + state bucket checks
```

Expected `make verify` output on a fresh setup:

```text
── Bootstrap drift check…
✓ bootstrap: no changes (6s)
── Stack drift check…
✓ stack: no changes (5s)
── State bucket
  dealpulse-xxxx-tfstate-<account-id>
  versioning: Enabled
  public access blocked: True True True True
  stack state: terraform.tfstate (1402 bytes)
── Budget (alerts only; never stops spending)
  dealpulse-xxxx-monthly: $60.0/month, spent so far $0.00 (tag app=dealpulse)
  alerts: 4
  cost tag 'app': Active
```

`make bootstrap` and `make apply` show the plan and ask for `yes`. After reviewing a plan you can skip the prompt with `YES=1`.

To use a different profile for one command: `make plan AWS_PROFILE=demo`.

## Files Terraform writes (all git-ignored)

| File | Written by | Contains |
|---|---|---|
| `infra/bootstrap/terraform.tfvars` | `make configure` | name prefix, region |
| `infra/bootstrap/terraform.tfstate` | `make bootstrap` | bootstrap state (keep it; it's how bootstrap is changed or destroyed later) |
| `infra/stack/backend.hcl` | `make bootstrap` | state bucket, key, region, locking |
| `infra/stack/bootstrap.auto.tfvars.json` | `make bootstrap` | name prefix, region for the stack |

## Checks without AWS access

```bash
make check          # terraform fmt -check + validate for both layers
```

## Troubleshooting

| Message | Fix |
|---|---|
| `terraform … is too old; need 1.10+` | Install a newer Terraform (see above). |
| `Not signed in to AWS (profile …)` | `aws sso login --profile <name>` or set `AWS_PROFILE`. |
| `Stack isn't configured. Run: make bootstrap` | Run `make bootstrap` once; it writes the stack's backend settings. |
| `Error acquiring the state lock` | Another Terraform run is in progress. Wait for it; if a run crashed, remove the stale lock with `terraform -chdir=infra/stack force-unlock <ID>`. |

## Budget and alerts

`make bootstrap` creates the budget `<prefix>-monthly`: **$60/month** with email alerts at 50%, 80% and 100% of actual spend and at 100% of forecasted spend. Alert addresses come from `alert_emails` in `infra/bootstrap/terraform.tfvars` (git-ignored). AWS emails them directly; no confirmation step is needed.

- **It only counts DealPulse.** The budget filters on the tag `app=dealpulse`, so other workloads in the same account don't trigger it. Terraform activates `app` as a *cost allocation tag* for this. AWS can take **up to 24 hours** to start applying a newly activated tag, and it counts spend only from then on, so the budget shows $0 at first.
- **It only alerts.** Nothing is stopped or deleted when a threshold is crossed. Use `make pause` (IAC-06) and `make destroy` / `make destroy-all` (IAC-07) to stop costs.
- **Check it:** `make verify` prints the budget, spend so far, the number of alerts and the tag status. In the console: Billing and Cost Management → Budgets.
- **Change it:** edit `budget_amount_usd` or `alert_emails` in `infra/bootstrap/terraform.tfvars`, then `make bootstrap`.
- **Untagged costs aren't counted.** A few charges can't carry tags (for example some data transfer). Expect the budget to read slightly below the true total; Cost Explorer filtered by the tag shows the same view.

## Teardown

Two levels. Both show exactly what will go, then ask you to type the name prefix (e.g. `dealpulse-y34c`). Pass `CONFIRM=<prefix>` to skip the question. Nothing changes if you cancel.

| Command | Removes | Keeps | Time |
|---|---|---|---|
| `make destroy` | The whole stack: OpenSearch domain and index, data bucket and its files, model registry and versions, endpoint, guardrail, IAM roles, network, log groups | State bucket, $60 budget, cost tag | ~15 min (OpenSearch is slowest) |
| `make destroy-all` | All of the above, then the state bucket, the budget and the `app` cost allocation tag (set back to Inactive) | Your settings file `infra/bootstrap/terraform.tfvars` | ~15–20 min |

```bash
make destroy                 # or: make destroy-all
make verify-destroyed        # after destroy;      ALL=1 after destroy-all
```

**What happens, in order**
1. Shows Terraform's destroy list plus what was made outside Terraform: model versions from `make train`, DealPulse's training log streams, and any endpoint whose creation failed (Terraform doesn't track those).
2. Asks for the prefix.
3. Lets the data bucket be deleted with its files. This protection is lifted only inside these commands.
4. Removes the items made outside Terraform. Only DealPulse's own log streams are deleted, never SageMaker's shared log group.
5. Runs `terraform destroy`, and for `destroy-all` then destroys the bootstrap the same way.

**If another Terraform run is in progress** (for example a `make deploy-model` in another terminal or session), `make destroy` stops before asking anything and says who holds the lock and since when. Let that run finish, then try again. Use `terraform -chdir=infra/stack force-unlock <ID>` only if the other run crashed and nothing is running.

**What can't be undone:** the synthetic data in S3, the search index, registered model versions and their approval history, and the guardrail. All of them can be recreated: `make apply RISK_CHECK=1`, `make data`, `make train`, then approve and deploy a model. SageMaker keeps the training-job records themselves (free, read-only metadata).

**Checking it's all gone:** `make verify-destroyed` looks up each service directly by name and fails if anything remains. It also lists anything still carrying the DealPulse tags; that tag search can lag a deletion by a while, so treat it as a cross-check. A deleted OpenSearch domain may show as "being deleted" for a few minutes; billing stops when deletion starts. Check **Billing → Bills** a few days later.

**Rebuilding after `destroy-all`:** `make bootstrap` creates a new state bucket with the same prefix; then continue with `make apply`.
