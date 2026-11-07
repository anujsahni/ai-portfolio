#!/usr/bin/env bash
# IAC-06: list anything WeekendWise left behind. Read-only. Exits 1 if a stack resource still exists.
#
#   After `make destroy`      the project stays ACTIVE: checks Cloud Run, Artifact Registry, Firestore,
#                             service accounts and stack state are gone; lists what is kept on purpose.
#   After `make destroy-all`  the project is DELETE_REQUESTED (or gone) and bootstrap state is empty.
set -uo pipefail
cd "$(dirname "$0")/.."

project=$(sed -n 's/^project_id *= *"\(.*\)".*/\1/p' infra/bootstrap/terraform.tfvars 2>/dev/null)
[ -n "$project" ] || project=$(sed -n 's/.*"project_id": "\(.*\)".*/\1/p' infra/stack/bootstrap.auto.tfvars.json 2>/dev/null)
region=$(sed -n 's/^region *= *"\(.*\)".*/\1/p' infra/bootstrap/terraform.tfvars 2>/dev/null)
region=${region:-us-central1}
[ -n "$project" ] || { echo "✗ Can't tell which project to check (no infra/bootstrap/terraform.tfvars)."; exit 1; }

state=$(gcloud projects describe "$project" --format='value(lifecycleState)' 2>/dev/null)
echo "Project $project: ${state:-not found}"
left=0

if [ -z "$state" ] || [ "$state" = "DELETE_REQUESTED" ]; then
  boot=$(terraform -chdir=infra/bootstrap state list 2>/dev/null | grep -v "^data\.")
  if [ -n "$boot" ]; then echo "✗ Still in bootstrap Terraform state:"; echo "$boot" | sed 's/^/    /'; left=1
  else echo "✓ Bootstrap Terraform state is empty"; fi
  echo "✓ The project is shut down: nothing in it can bill. Google deletes it for good after about 30 days."
  echo "  Its ID can't be reused; a rebuild needs a new suffix (make configure)."
  exit $left
fi

echo "The project is active, so this checks a routine teardown (make destroy)."
check() {
  local name=$1; shift
  local out; out=$("$@" 2>/dev/null)
  if [ -n "$out" ]; then echo "✗ $name still exist:"; echo "$out" | sed 's/^/    /'; left=1; else echo "✓ No $name"; fi
}
check "Cloud Run services" gcloud run services list --project "$project" --region "$region" --format='value(metadata.name)'
check "Artifact Registry repositories" gcloud artifacts repositories list --project "$project" --location "$region" --format='value(name)'
check "Firestore databases" gcloud firestore databases list --project "$project" --format='value(name)'
check "WeekendWise service accounts" gcloud iam service-accounts list --project "$project" --filter='email~^weekendwise-' --format='value(email)'

if [ -f infra/stack/backend.hcl ]; then
  terraform -chdir=infra/stack init -input=false -reconfigure -backend-config=backend.hcl >/dev/null 2>&1
  stack=$(terraform -chdir=infra/stack state list 2>/dev/null | grep -v "^data\.")
  if [ -n "$stack" ]; then echo "✗ Still in stack Terraform state:"; echo "$stack" | sed 's/^/    /'; left=1
  else echo "✓ Stack Terraform state is empty"; fi
fi

echo "Kept on purpose (cost: about \$0 while idle):"
echo "  - project, billing link, and the \$20 budget alert"
gcloud storage buckets list --project "$project" --format='value(name)' 2>/dev/null | sed 's/^/  - bucket: /'
echo "  Remove everything with: make destroy-all"
exit $left
