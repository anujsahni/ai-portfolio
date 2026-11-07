# How-to 00 — Provision and destroy WeekendWise with Terraform

**Related stories:** [IAC-01](../stories/IAC-01-terraform-foundation-state.md) · [IAC-02](../stories/IAC-02-project-billing-apis-budget.md) · [IAC-03](../stories/IAC-03-service-identities-iam.md) · [IAC-04](../stories/IAC-04-firestore-database-vector-index.md) · [IAC-05](../stories/IAC-05-artifact-registry-cloud-run.md) · [IAC-06](../stories/IAC-06-teardown-destroy.md)
**Time:** about 15 minutes the first time
**Run from:** the repository root, in a terminal on macOS or in Cloud Shell

> ⚠️ **Cost:** this links your billing account. The **$20/month budget only sends alert emails; it does not stop spending.** Run `make destroy-all` when you no longer need the project.

> **What's here:** Steps 1–10 build the project, identities, Firestore, and the searchable guides. Step 11 runs the app on your computer; Steps 12–14 put it on Cloud Run and show how to roll back. Teardown is at the end.

Terraform is the **only** way to create, change, or delete WeekendWise infrastructure. Console guides [01](01-project-and-billing.md)–[04](04-firestore-vector-search.md) are for looking things up, not for making changes.

---

## Quick reference

Already set up and just need the commands? Every new terminal:

```bash
cd ~/Documents/customers/google
export TF_VAR_billing_account_id=XXXXXX-XXXXXX-XXXXXX
make verify
```

| Command | What it does |
|---|---|
| `make help` | List all commands |
| `make tools` | Check Terraform, gcloud, and sign-in |
| `make configure` | Create your settings file with a unique project ID (first time only) |
| `make bootstrap-plan` | Preview project/billing/APIs/budget changes (changes nothing) |
| `make bootstrap` | Create or update the project, billing link, APIs, $20 budget, and state bucket |
| `make plan` / `make apply` | Preview / apply changes to the stack (resources inside the project) |
| `make verify` | Check for drift and show what exists, including service-account access |
| `make venv` / `make test` | Set up Python / run offline unit tests |
| `make seed` | Load the guide data into Firestore with embeddings (`DRY_RUN=1` to preview) |
| `make ask Q="…" CITY=…` | Ask a grounded question the way the app will (search, Gemini, verified citations) |
| `make scenarios` | Plan all 6 scripted trips with the real planner and compare to expectations (a few cents) |
| `make smoke-vertex` | One tiny Gemini + embedding call (add `AS=run` to test as the Cloud Run identity) |
| `make run` | Run the real app on your computer at http://localhost:8080 (live Gemini + Firestore, about 1 cent per plan) |
| `make ui-smoke` | Drive the app in headless Chrome: free checks plus the 6 sample trips (`OFFLINE=1` = free checks only) |
| `make evaluate` | Run the 30-case evaluation set and write the report (about 20–40 cents) |
| `make release` | `make build` (tests, then Cloud Build image) + `make deploy` (Terraform rolls it out to Cloud Run) |
| `make images` | List recent image tags you can roll back to |
| `make deploy IMAGE=<tag>` | Roll out a specific image (rollback) |
| `make smoke-cloud` | Check the deployed service: private, healthy, ready, and one live plan |
| `make proxy` | Open the private Cloud Run app in your browser at http://localhost:8082 |
| `make destroy` | Delete the stack only (keeps the project); shows the list first |
| `make destroy-all` | Delete **everything**, including the project |
| `make verify-destroyed` | List anything left behind; fails if something remains |

---

## First-time setup

### Step 1 — Install the tools (once per computer)

```bash
brew install hashicorp/tap/terraform
brew install --cask google-cloud-sdk
```

Close and reopen the terminal, then check:

```bash
terraform version   # 1.5 or newer
gcloud version
```

Cloud Shell already has both.

### Step 2 — Sign in to Google (once per computer)

```bash
gcloud auth login
gcloud auth application-default login
```

Each command opens a browser. Sign in with the Google account that has access to your billing account and click **Allow**.

- The first command lets `gcloud` act as you.
- The second lets Terraform act as you.
- No key files are created or needed.

### Step 3 — Check everything is ready

```bash
make tools
```

Expected:

```
✓ Terraform v1.x.x
✓ Google Cloud SDK xxx.x.x
✓ Application Default Credentials found
```

If you see a ✗, follow the message it prints.

### Step 4 — Create your settings file (once)

```bash
make configure
```

Expected:

```
✓ Created infra/bootstrap/terraform.tfvars with project_id weekendwise-demo-abcd
```

Open `infra/bootstrap/terraform.tfvars` if you want to check or change anything:

| Setting | Default | Notes |
|---|---|---|
| `project_id` | `weekendwise-demo-` + 4 random characters | Must be globally unique; can't change after creation |
| `region` | `us-central1` | Used for everything |
| `budget_amount_usd` | `20` | **20 is the maximum.** A higher value is rejected. |
| `alert_emails` | `[]` | Optional extra people to email. Billing admins are always emailed. |

This file is git-ignored. Running `make configure` again won't overwrite it.

### Step 5 — Tell Terraform your billing account (every new terminal)

```bash
gcloud billing accounts list
```

Copy the `ACCOUNT_ID` (looks like `0X0X0X-0X0X0X-0X0X0X`), then:

```bash
export TF_VAR_billing_account_id=0X0X0X-0X0X0X-0X0X0X
```

This lives only in the current terminal and is never saved to a file. **Repeat it whenever you open a new terminal**, or `make bootstrap`, `make verify`, and `make destroy-all` will stop and remind you.

### Step 6 — Preview (optional, changes nothing)

```bash
make bootstrap-plan
```

The last line should be:

```
Plan: 14 to add, 0 to change, 0 to destroy.
```

### Step 7 — Create the project, billing link, APIs, and budget

```bash
make bootstrap
```

Terraform shows the plan and asks:

```
Do you want to perform these actions?
  Enter a value:
```

Type **`yes`** and press Enter. It takes about 1–3 minutes. Expected ending:

```
Apply complete! Resources: 14 added, 0 changed, 0 destroyed.
...
✓ Bootstrap complete
  project:      weekendwise-demo-abcd
  region:       us-central1
  state bucket: weekendwise-demo-abcd-tfstate
  wrote infra/stack/backend.hcl and infra/stack/bootstrap.auto.tfvars.json
```

What was created:

| Item | Details |
|---|---|
| Project | `weekendwise-demo-abcd`, linked to your billing account |
| 11 APIs | App: Vertex AI, Firestore, Cloud Run, Cloud Build, Artifact Registry, Logging. Terraform: Resource Manager, Service Usage, IAM, Billing Budgets, Storage. |
| Budget | `weekendwise-monthly-20usd`: $20/month, this project only, emails at 50%, 80%, and 100% of actual spend and 100% of forecast; free credits excluded |
| State bucket | `weekendwise-demo-abcd-tfstate`: where Terraform keeps track of the stack |

Copy the project ID and region into your private `.env` (start from `cp .env.example .env`).

If it stops with "API … has not been used" or "not enabled", wait 1–2 minutes and run `make bootstrap` again. Newly enabled APIs take a moment to switch on.

### Step 8 — Create the service accounts (stack)

```bash
make apply
```

The first time, it saves your gcloud account as the **operator** (the person allowed to act as the service accounts):

```
✓ Operator set to user:you@example.com (infra/stack/operator.auto.tfvars.json)
```

Then it shows the plan, ending with `Plan: 18 to add, 0 to change, 0 to destroy.` on a fresh project. (If you already applied IAC-03 earlier, you'll see `2 to add`: the Firestore database and index.) Type **`yes`**. The vector index takes a few minutes to build. Expected:

```
Apply complete! Resources: 18 added, 0 changed, 0 destroyed.

Outputs:
service_accounts = {
  "build"  = "weekendwise-build@weekendwise-demo-abcd.iam.gserviceaccount.com"
  "ingest" = "weekendwise-ingest@weekendwise-demo-abcd.iam.gserviceaccount.com"
  "run"    = "weekendwise-run@weekendwise-demo-abcd.iam.gserviceaccount.com"
}
```

What gets created:

| Item | Details |
|---|---|
| Firestore `(default)` database | Native mode, `us-central1`, **delete protection on** (only the destroy commands lift it). Uses Firestore's free daily quota. |
| Vector index on `guide_chunks` | `cityId` + `active` + `embedding` (768 dimensions), so retrieval can filter by city and active status before finding the nearest passages |

And 16 identity items (all free):

| Service account | Used by | Roles |
|---|---|---|
| `weekendwise-run` | Cloud Run app | Vertex AI user, Firestore **read-only**, log writer |
| `weekendwise-ingest` | `make seed` | Vertex AI user, Firestore read/write |
| `weekendwise-build` | Cloud Build | Artifact Registry writer, log writer, storage object viewer |
| You (operator) | `make` commands | Can impersonate all three, and act as `run` and `build` when deploying |

No key files are created. Later stories add Firestore, Artifact Registry, and Cloud Run to this same stack.

### Step 9 — Load the guide data

Needs the Python environment once (`make venv`). Preview first, then load:

```bash
make seed DRY_RUN=1    # shows what would change; writes nothing
make seed              # embeds and writes (well under one cent)
```

Expected on the first run:

```
identity:   weekendwise-ingest@weekendwise-demo-abcd.iam.gserviceaccount.com
embeddings: gemini-embedding-001 @ us-central1, 768 dimensions

collection             new  update   same  delete
app_config               1       0      0       0
cities                   4       0      0       0
interests                6       0      0       0
budget_categories        4       0      0       0
local_conditions        14       0      0       0
guide_sources           47       0      0       0
guide_chunks            95       0      0       0
corpus_manifests         4       0      0       0

chunks to embed: 95   stored vectors reused: 0
✓ embedded 95 chunks in 3.8s
✓ wrote 175 documents, deleted 0; summary saved to ingestion_runs/latest
```

How it behaves:

- **Safe to rerun.** A second run prints `✓ Firestore already matches data/seed/. Nothing to do.`
- **Only changes are sent.** After you edit a guide in `data/guides/`, `make seed` rebuilds the seed JSON, re-embeds only the changed paragraphs, and removes chunks you deleted.
- **It writes as `weekendwise-ingest`.** The app's own account can only read.
- **Size check first.** It refuses to run if `VERTEX_EMBEDDING_DIMENSION` in `.env` doesn't match the Firestore index.
- **Test fixtures are left out by default.** Add `FIXTURES=1` to also load the trip scenarios, sample itineraries, and evaluation cases.

### Step 10 — Verify

```bash
make verify
```

Expected (abridged):

```
── Bootstrap drift check (contacts Google; usually 10–60 seconds)…
✓ bootstrap: no changes (10s)
── Stack drift check (usually 5–30 seconds)…
✓ stack: no changes (4s)
── Bootstrap outputs
budget = { amount = "20 USD per month", name = "weekendwise-monthly-20usd", ... }
project_id = "weekendwise-demo-abcd"
region = "us-central1"
state_bucket = "weekendwise-demo-abcd-tfstate"
── Live checks (gcloud)
billing:
  billingEnabled=True
budget (only this project):
  weekendwise-monthly-20usd: 20 USD/month, 4 alert rules
enabled APIs:
  aiplatform.googleapis.com
  ...
service-account keys (should be none):
  (check done)
── Service-account access (IAC-03; impersonates each account, reads/writes nothing)
✓ weekendwise-run
    can:    aiplatform.endpoints.predict, datastore.entities.get, datastore.entities.list, logging.logEntries.create
    cannot: artifactregistry.repositories.uploadArtifacts, datastore.entities.create, datastore.entities.delete, datastore.entities.update
    user-managed keys: 0
✓ weekendwise-ingest
    ...
✓ weekendwise-build
    ...
── Firestore (IAC-04; reads only)
✓ database (default): Native mode, us-central1
✓ location matches region (us-central1)
✓ delete protection: on
✓ vector index on guide_chunks (cityId + active + embedding), dimension 768: READY
✓ matches VERTEX_EMBEDDING_DIMENSION in .env (768)
✓ weekendwise-run can read guide_chunks: 95 documents
── Retrieval test set (MVP-05; 29 cases as weekendwise-run, reads only)
✓ R-SF-01    SF-ATTRACTION-SFMOMA (0.284), SF-ATTRACTION-SFMOMA (0.285), SF-ATTRACTION-DEYOUNG (0.312)
...
✓ N-SF-01    insufficient_evidence (closest 0.386)
...
✓ U-01       unsupported_city

29 of 29 retrieval cases passed (cut-off 0.340, top-k 4).
```

The retrieval test set ([data/retrieval_cases.json](../../../data/retrieval_cases.json)) has 18 questions that must find a specific guide (every city), 10 off-topic questions that must come back as "insufficient evidence", and an unsupported city. It also checks that the retired cable-car guide and other cities' guides never appear. Lower numbers mean closer matches.

If the index line says `still CREATING`, wait a few minutes and rerun.

The last section needs the Python environment (`make venv`). It proves the Cloud Run identity can **read but not write** Firestore. Right after `make apply`, new permissions can take 1–2 minutes to apply; the check retries for about 90 seconds, so rerun it if it still fails.

**About the API list:** you'll see a few more than 11, such as `containerregistry`, `firebaserules`, `iamcredentials`, `pubsub`, `storage-api`, `storage-component`, and `telemetry`. Google turns these on automatically as dependencies of the APIs we enabled. That's expected and they cost nothing unless used.

Optionally, in the console: **☰ → Billing → Budgets & alerts** shows `weekendwise-monthly-20usd`.

✅ **Done.** The project, service accounts, Firestore, and the searchable guide data are all in place.

### Step 11 — Try the app on your computer

```bash
make run
```

Open **http://localhost:8080**. This is the real app: the same screens as the mockup, but every plan comes from the planner (Firestore search + Gemini) running on your computer as `weekendwise-run`. Pick a city, or click a **Try a sample** chip, then **Make my weekend**. A plan takes about 15–40 seconds and costs about 1 cent. Press Ctrl+C in the terminal to stop.

To test it automatically in Chrome (desktop and phone sizes, all six sample trips, about 6 cents), run this in a second terminal while `make run` is going:

```bash
make ui-smoke
```

Expected ending: `31 of 31 checks passed`. Screenshots go to `reports/ui/`.

> If you get "You've made several plans in a short time", that's the demo's abuse limit (6 plans per person per 10 minutes). Wait a few minutes, or restart `make run`.

### Step 12 — Put it on Cloud Run

Three commands. The first creates the registry and the Cloud Run service (with Google's placeholder image), the second builds and rolls out the app:

```bash
make apply          # Plan: 3 to add (registry, Cloud Run service, your invoker access). Type yes.
make release        # runs the tests, builds with Cloud Build (~3 min), then Terraform deploys it. Type yes.
make smoke-cloud    # checks it end to end (~1 cent)
```

`make release` uploads only the Dockerfile, the app code, and `data/seed/` (see `.gcloudignore`). Your `.env` and Terraform files never leave your computer, and no key is put in the image: Cloud Run uses the `weekendwise-run` identity.

Expected ending of `make smoke-cloud`:

```
✓ min instances is 0 (scale to zero)
✓ max instances is bounded  (2)
✓ runs as the dedicated runtime identity  (weekendwise-run)
✓ app image deployed (not the placeholder)  (tag 20261106-…)
✓ private: a request without a token is rejected  (HTTP 403)
✓ /health answers as you  (HTTP 200, … incl. any cold start, version 20261106-…)
✓ reported version matches the deployed tag
✓ /readyz: Firestore readable as weekendwise-run
✓ live plan through Cloud Run (Vertex AI + Firestore as weekendwise-run)  (…s, 5 steps, 1 model call(s), …)

9 of 9 checks passed.
```

### Step 13 — Open the Cloud Run app in your browser

The service is **private**: only you can call it. Open it through a local proxy that signs each request with your Google sign-in:

```bash
make proxy
```

Then open **http://localhost:8082** and plan a trip. Ctrl+C stops the proxy. To run the automated browser checks against Cloud Run instead of your computer: `make ui-smoke CLOUD=1`.

**Making it public (only for a live demo).** Anyone with the URL could then trigger model calls that cost money. The app limits each person to 6 plans per 10 minutes and each instance to 30 plans a day, with at most 2 instances, but that is a speed bump, not a guarantee. To turn it on, create `infra/stack/terraform.tfvars` (git-ignored) with:

```hcl
allow_unauthenticated = true
```

then `make apply`. Turn it off after the demo by deleting that line and running `make apply` again. Keep using sample data only.

### Step 14 — Roll back

Every build gets its own tag. To go back to an earlier one:

```bash
make images                         # newest first, and which one is deployed
make deploy IMAGE=20261106-201500   # the tag you want; Terraform shows the change, type yes
make smoke-cloud
```

The deployed image is remembered in `infra/stack/image.auto.tfvars.json`, so a later `make apply` keeps it. The registry keeps the 10 most recent images.

---

## Making changes later

1. Edit `infra/bootstrap/terraform.tfvars` (or the `.tf` files).
2. `make bootstrap-plan` and read the changes.
3. `make bootstrap` and type `yes`.
4. `make verify` should show no changes.

Never change these resources in the console. If you do, `make verify` reports drift, and `make bootstrap` puts it back.

---

## Tearing down

### Delete everything (project included)

```bash
export TF_VAR_billing_account_id=0X0X0X-0X0X0X-0X0X0X   # if this is a new terminal
make destroy-all CONFIRM=weekendwise-demo-abcd
make verify-destroyed
```

It first lists the stack resources that will go. Without `CONFIRM=…`, it asks you to type the project ID. It then:

1. deletes the stack (Cloud Run, the image registry and all images, Firestore and its data, service accounts),
2. lifts the deletion protection on the project and state bucket,
3. deletes the budget, state bucket, and project.

Expected ending:

```
✓ Everything destroyed. Run 'make verify-destroyed', and check Billing → Reports over the next few days.
```

and from `make verify-destroyed`:

```
Project weekendwise-demo-abcd: DELETE_REQUESTED
✓ Bootstrap Terraform state is empty
✓ The project is shut down: nothing in it can bill. Google deletes it for good after about 30 days.
```

The project can be restored from the console for about 30 days, after which Google deletes it permanently. Check **Billing → Reports** over the next few days; charges already incurred can still appear.

### Delete only the stack (keep the project)

```bash
make destroy CONFIRM=weekendwise-demo-abcd
```

It shows the list of what will be deleted and asks for the project ID. It then lifts delete protection on Firestore and Cloud Run (only here; it's on by default), and deletes the Cloud Run service, the image registry (**all images**), the Firestore database (**all its data**), the vector index, and the service accounts. The project, billing, budget, and state bucket stay.

Check it worked:

```bash
make verify-destroyed
```

```
Project weekendwise-demo-abcd: ACTIVE
The project is active, so this checks a routine teardown (make destroy).
✓ No Cloud Run services
✓ No Artifact Registry repositories
✓ No Firestore databases
✓ No WeekendWise service accounts
✓ Stack Terraform state is empty
Kept on purpose (cost: about $0 while idle):
  - project, billing link, and the $20 budget alert
  - bucket: weekendwise-demo-abcd-tfstate
```

Rebuild everything with no manual steps:

```bash
make apply && make seed && make release && make smoke-cloud
```

If `make apply` can't recreate `(default)` straight after a delete, wait a few minutes and retry.

**What can't be undone:** deleted Firestore data and deleted images are gone (rebuild them with `make seed` and `make release`). The `(default)` database name and a deleted project's ID are held by Google for a while (minutes for the database, about 30 days for the project ID).

### Start again after `destroy-all`

A deleted project ID can't be reused for about 30 days, so get a new one:

```bash
rm infra/bootstrap/terraform.tfvars
make configure
make bootstrap
make apply
make verify
```

---

## Troubleshooting

| What you see | Why | Fix |
|---|---|---|
| `✗ gcloud not found` | Tools not installed | Step 1 |
| `could not find default credentials` / `✗ Not signed in` | Terraform sign-in missing | `gcloud auth application-default login` |
| `✗ Set your billing account first` | New terminal | Step 5 (`export TF_VAR_billing_account_id=…`) |
| `budget_amount_usd must be between 1 and 20` | Budget above the $20 cap | Set `budget_amount_usd = 20` or lower |
| `billing account … permission denied` | Your account can't use that billing account | Ask the billing admin for **Billing Account User** |
| `API … has not been used in project` | API still switching on | Wait 1–2 minutes and rerun |
| `Project ID already exists` / `already in use` | IDs are global and held ~30 days after deletion | `rm infra/bootstrap/terraform.tfvars && make configure` |
| `gcloud billing budgets list` says *requires a quota project* | The Budgets API needs a project to bill the request to | Add `--billing-project=<your project id>` (`make verify` already does this) |
| `make verify` seems stuck after "drift check…" | Terraform is checking every resource with Google; it prints nothing until done | Wait up to about a minute. If it's longer than 2 minutes, press Ctrl+C, run `gcloud auth application-default login` again (sign-in may have expired), and retry. Details are in `infra/.verify-bootstrap.log`. |
| `✗ bootstrap: drift found` | Something differs from the code | Run `make bootstrap-plan` to see what. If it's a console change, `make bootstrap` puts it back. |
| `Error acquiring the state lock` | An earlier run was interrupted | Make sure nothing else is running, then `terraform -chdir=infra/stack force-unlock <lock-id>` |
| `✗ Stack isn't configured` | Bootstrap hasn't run on this computer | `make bootstrap` (it rewrites the stack config files) |
| `✗ Artifact Registry repository not found` on `make build` | The registry is created by the stack | `make apply` first |
| `make build` fails with *does not have permission to act as service account* | Your account isn't an operator of `weekendwise-build` yet | `make apply` (adds you), wait a minute, retry |
| Cloud Run revision fails to start | The container crashed or couldn't read its settings | **Cloud Run → weekendwise → Logs**, or see the [runbook](../runbook.md#something-is-wrong); roll back with `make deploy IMAGE=<previous tag>` |
| `make smoke-cloud` says `HTTP 403` with a token | Invoker access not applied yet | Wait 1–2 minutes after `make apply` and retry |
| The app says "You've made several plans in a short time" | Per-person abuse limit (6 plans per 10 minutes) | Wait a few minutes; locally, restarting `make run` also resets it |
| `make destroy` stops at *deletion_protection* | Protection wasn't lifted (interrupted run) | Run `make destroy` again; it lifts protection first |

## Safety rules

- Never commit `terraform.tfvars`, `*.tfstate`, `backend.hcl`, `.env`, or anything containing the billing account ID. `.gitignore` covers these.
- No service-account key files, ever.
- Read the plan before typing `yes`.
- The budget is an alert, not a cap. Teardown is what stops costs.
- Keep `infra/bootstrap/terraform.tfstate` safe. It's how Terraform knows what to delete. If you lose it, delete the project manually in **IAM & Admin → Settings → Shut down**.
