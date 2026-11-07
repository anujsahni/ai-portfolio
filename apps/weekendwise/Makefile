# WeekendWise infrastructure commands. See docs/mvp/guides/00-provision-with-terraform.md
#
# Two Terraform layers:
#   infra/bootstrap  project, billing link, APIs, $20 budget, state bucket   (local state)
#   infra/stack      resources inside the project                          (GCS state)

SHELL := /bin/bash
TF    ?= terraform

BOOT      := infra/bootstrap
STACK     := infra/stack
BOOT_VARS := $(BOOT)/terraform.tfvars
STACK_GEN := $(STACK)/bootstrap.auto.tfvars.json
BACKEND   := $(STACK)/backend.hcl
BOOT_LOG  := infra/.verify-bootstrap.log
STACK_LOG := infra/.verify-stack.log

.DEFAULT_GOAL := help
.PHONY: help tools configure check bootstrap bootstrap-plan plan apply verify \
        destroy destroy-all verify-destroyed build deploy release images proxy smoke-cloud ui-smoke evaluate logs seed venv test smoke-vertex mockups ask scenarios run \
        _need-billing _need-boot-vars _need-stack _stack-operator _need-venv _stack-destroy _stack-destroy-plan

PY        := .venv/bin/python
OPERATOR  := $(STACK)/operator.auto.tfvars.json
IMAGE_VARS := $(STACK)/image.auto.tfvars.json
LAST_BUILD := infra/.last-build
PROJECT    = $$(sed -n 's/.*"project_id": "\(.*\)".*/\1/p' $(STACK_GEN))
REGION     = $$(sed -n 's/.*"region": "\(.*\)".*/\1/p' $(STACK_GEN))
REPO       = $(REGION)-docker.pkg.dev/$(PROJECT)/weekendwise/app

help: ## Show available commands
	@grep -hE '^[a-z][a-z-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*## "}{printf "  make %-17s %s\n",$$1,$$2}'

tools: ## Check required tools are installed
	@command -v $(TF) >/dev/null || { echo "✗ terraform not found. Install: brew install hashicorp/tap/terraform"; exit 1; }
	@echo "✓ $$($(TF) version | head -1)"
	@if command -v gcloud >/dev/null; then echo "✓ $$(gcloud version 2>/dev/null | head -1)"; \
	 else echo "✗ gcloud not found (needed to sign in). Install: brew install --cask google-cloud-sdk"; exit 1; fi
	@if [ -n "$$GOOGLE_APPLICATION_CREDENTIALS" ] || [ -f "$$HOME/.config/gcloud/application_default_credentials.json" ]; then \
	   echo "✓ Application Default Credentials found"; \
	 else echo "✗ Not signed in for Terraform. Run: gcloud auth application-default login"; exit 1; fi

configure: ## Create infra/bootstrap/terraform.tfvars with a unique project ID
	@if [ -f $(BOOT_VARS) ]; then echo "✓ $(BOOT_VARS) already exists (not changed)"; exit 0; fi; \
	 suffix=$$(LC_ALL=C tr -dc 'a-z0-9' </dev/urandom | head -c 4); \
	 sed "s/^project_id *= *\"weekendwise-demo\"/project_id        = \"weekendwise-demo-$$suffix\"/" $(BOOT)/terraform.tfvars.example > $(BOOT_VARS); \
	 echo "✓ Created $(BOOT_VARS) with project_id weekendwise-demo-$$suffix"; \
	 echo "  Review it, then: export TF_VAR_billing_account_id=XXXXXX-XXXXXX-XXXXXX"

check: ## Format-check and validate all Terraform (no cloud access needed)
	$(TF) fmt -check -recursive infra
	$(TF) -chdir=$(BOOT) init -backend=false -input=false >/dev/null
	$(TF) -chdir=$(BOOT) validate
	$(TF) -chdir=$(STACK) init -backend=false -input=false >/dev/null
	$(TF) -chdir=$(STACK) validate

_need-boot-vars:
	@[ -f $(BOOT_VARS) ] || { echo "✗ $(BOOT_VARS) missing. Run: make configure"; exit 1; }

_need-billing:
	@[ -n "$$TF_VAR_billing_account_id" ] || { \
	   echo "✗ Set your billing account first (needed once per terminal):"; \
	   project=$$(sed -n 's/^project_id *= *"\(.*\)"/\1/p' $(BOOT_VARS) 2>/dev/null); \
	   linked=$$( [ -n "$$project" ] && command -v gcloud >/dev/null && \
	     gcloud billing projects describe "$$project" --format='value(billingAccountName)' 2>/dev/null | sed 's|^billingAccounts/||'); \
	   if [ -n "$$linked" ]; then echo "    export TF_VAR_billing_account_id=$$linked   # account already linked to $$project"; \
	   else echo "    export TF_VAR_billing_account_id=XXXXXX-XXXXXX-XXXXXX   (find it with: gcloud billing accounts list)"; fi; \
	   exit 1; }

bootstrap-plan: _need-boot-vars _need-billing ## Preview what bootstrap will create or change
	$(TF) -chdir=$(BOOT) init -input=false
	$(TF) -chdir=$(BOOT) plan -input=false

bootstrap: _need-boot-vars _need-billing ## Create/update project, billing link, APIs, $20 budget, state bucket
	@echo "⚠  This links a billing account. Charges are possible. The budget only ALERTS; it does not stop spending."
	$(TF) -chdir=$(BOOT) init -input=false
	$(TF) -chdir=$(BOOT) apply -input=false
	@project=$$($(TF) -chdir=$(BOOT) output -raw project_id); \
	 region=$$($(TF) -chdir=$(BOOT) output -raw region); \
	 bucket=$$($(TF) -chdir=$(BOOT) output -raw state_bucket); \
	 printf 'bucket = "%s"\nprefix = "stack"\n' "$$bucket" > $(BACKEND); \
	 printf '{\n  "project_id": "%s",\n  "region": "%s"\n}\n' "$$project" "$$region" > $(STACK_GEN); \
	 echo ""; echo "✓ Bootstrap complete"; \
	 echo "  project:      $$project"; echo "  region:       $$region"; echo "  state bucket: $$bucket"; \
	 echo "  wrote $(BACKEND) and $(STACK_GEN)"; \
	 echo "  Record project and region in your private .env (see .env.example)."

_need-stack:
	@[ -f $(BACKEND) ] && [ -f $(STACK_GEN) ] || { echo "✗ Stack isn't configured. Run: make bootstrap"; exit 1; }

# Who may impersonate the service accounts: your gcloud account, saved once (git-ignored).
_stack-operator:
	@if [ ! -f $(OPERATOR) ]; then \
	   account=$$(gcloud config get-value account 2>/dev/null); \
	   [ -n "$$account" ] || { echo "✗ No gcloud account. Run: gcloud auth login"; exit 1; }; \
	   printf '{\n  "operator_principals": ["user:%s"]\n}\n' "$$account" > $(OPERATOR); \
	   echo "✓ Operator set to user:$$account ($(OPERATOR))"; \
	 fi

plan: _need-stack _stack-operator ## Preview changes to the stack
	$(TF) -chdir=$(STACK) init -input=false -reconfigure -backend-config=backend.hcl >/dev/null
	$(TF) -chdir=$(STACK) plan -input=false

apply: _need-stack _stack-operator ## Create/update the stack (service accounts and IAM today)
	$(TF) -chdir=$(STACK) init -input=false -reconfigure -backend-config=backend.hcl >/dev/null
	$(TF) -chdir=$(STACK) apply -input=false

# ---------------------------------------------------------------- Python

_need-venv:
	@[ -x $(PY) ] && $(PY) -c "import google.genai, pytest" 2>/dev/null || { echo "✗ Python environment not ready. Run: make venv"; exit 1; }

venv: ## Create .venv and install pinned Python dependencies
	@[ -x $(PY) ] || python3 -m venv .venv
	$(PY) -m pip install -q --upgrade pip
	$(PY) -m pip install -q -r requirements-dev.txt
	@echo "✓ Python environment ready ($$($(PY) --version))"

test: _need-venv ## Run offline unit tests (no cloud calls)
	$(PY) -m pytest -q tests

smoke-vertex: _need-venv ## Call Gemini + embeddings once (< 1 cent). AS=run|ingest to test a service account
	@if [ -n "$(AS)" ]; then \
	   project=$$(sed -n 's/^GCP_PROJECT_ID=//p' .env 2>/dev/null); \
	   [ -n "$$project" ] || project=$$($(TF) -chdir=$(BOOT) output -raw project_id); \
	   $(PY) scripts/smoke_vertex.py --as weekendwise-$(AS)@$$project.iam.gserviceaccount.com; \
	 else $(PY) scripts/smoke_vertex.py; fi

evaluate: _need-venv ## Run the 30-case evaluation set live (MVP-08; ~20–40 cents). C="PLAN-001 PLAN-024" for some cases
	@$(PY) scripts/evaluate.py $(C)

scenarios: _need-venv ## Plan all 6 scripted trips with the real planner and compare to expectations (a few cents). S=<id> for one
	@$(PY) scripts/run_scenarios.py $(S)

ask: _need-venv ## Ask a grounded question as the app would: make ask Q="..." CITY=portland (JSON=1 for raw response)
	@[ -n "$(Q)" ] || { echo '✗ Usage: make ask Q="Where can we get coffee?" CITY=san-francisco'; exit 1; }
	@$(PY) scripts/ask.py --city "$(or $(CITY),san-francisco)" $(if $(JSON),--json) "$(Q)"

verify: _need-boot-vars _need-billing _need-stack ## Check for drift and show what exists
	@echo "── Bootstrap drift check (contacts Google; usually 10–60 seconds)…"; \
	 start=$$(date +%s); \
	 $(TF) -chdir=$(BOOT) plan -input=false -no-color -detailed-exitcode -lock=false >$(BOOT_LOG) 2>&1; rc=$$?; \
	 secs=$$(( $$(date +%s) - start )); \
	 if [ $$rc -eq 0 ]; then echo "✓ bootstrap: no changes ($${secs}s)"; \
	 elif [ $$rc -eq 2 ]; then echo "✗ bootstrap: drift found ($${secs}s). Details:"; grep -E '^  [#~+-]|Plan:' $(BOOT_LOG) | sed 's/^/    /'; echo "  Full plan: make bootstrap-plan (log: $(BOOT_LOG))"; exit 1; \
	 else echo "✗ bootstrap check failed ($${secs}s):"; tail -20 $(BOOT_LOG) | sed 's/^/    /'; exit $$rc; fi
	@echo "── Stack drift check (usually 5–30 seconds)…"; \
	 start=$$(date +%s); \
	 $(TF) -chdir=$(STACK) init -input=false -reconfigure -backend-config=backend.hcl >$(STACK_LOG) 2>&1 || { echo "✗ stack init failed:"; tail -20 $(STACK_LOG) | sed 's/^/    /'; exit 1; }; \
	 $(TF) -chdir=$(STACK) plan -input=false -no-color -detailed-exitcode -lock=false >$(STACK_LOG) 2>&1; rc=$$?; \
	 secs=$$(( $$(date +%s) - start )); \
	 if [ $$rc -eq 0 ]; then echo "✓ stack: no changes ($${secs}s)"; \
	 elif [ $$rc -eq 2 ]; then echo "✗ stack: drift found ($${secs}s). Details:"; grep -E '^  [#~+-]|Plan:|Changes to Outputs' $(STACK_LOG) | sed 's/^/    /'; echo "  Full plan: make plan (log: $(STACK_LOG))"; exit 1; \
	 else echo "✗ stack check failed ($${secs}s):"; tail -20 $(STACK_LOG) | sed 's/^/    /'; exit $$rc; fi
	@echo "── Bootstrap outputs"; $(TF) -chdir=$(BOOT) output
	@if command -v gcloud >/dev/null; then \
	   project=$$($(TF) -chdir=$(BOOT) output -raw project_id); \
	   echo "── Live checks (gcloud)"; \
	   echo "billing:"; gcloud billing projects describe $$project --format='value(billingEnabled)' | sed 's/^/  billingEnabled=/'; \
	   echo "budget (only this project):"; \
	   gcloud billing budgets list --billing-account="$$TF_VAR_billing_account_id" --billing-project=$$project \
	     --format='value(displayName,amount.specifiedAmount.units,amount.specifiedAmount.currencyCode,thresholdRules.len())' \
	     | awk -F'\t' '{printf "  %s: %s %s/month, %s alert rules\n",$$1,$$2,$$3,$$4}'; \
	   echo "enabled APIs:"; gcloud services list --enabled --project $$project --format='value(config.name)' | sort | sed 's/^/  /'; \
	   echo "service-account keys (should be none):"; \
	   for sa in $$(gcloud iam service-accounts list --project $$project --format='value(email)'); do \
	     gcloud iam service-accounts keys list --iam-account $$sa --managed-by=user --format='value(name)' | sed 's/^/  KEY FOUND: /'; done; \
	   echo "  (check done)"; \
	 fi
	@if [ -x $(PY) ] && [ -n "$$($(TF) -chdir=$(STACK) output -json service_accounts 2>/dev/null | grep weekendwise-run)" ]; then \
	   echo "── Service-account access (IAC-03; impersonates each account, reads/writes nothing)"; \
	   $(PY) scripts/verify_iam.py $$($(TF) -chdir=$(BOOT) output -raw project_id); \
	 fi
	@if [ -x $(PY) ] && $(TF) -chdir=$(STACK) state list 2>/dev/null | grep -q '^google_firestore_database.default$$'; then \
	   echo "── Firestore (IAC-04; reads only)"; \
	   $(PY) scripts/verify_firestore.py $$($(TF) -chdir=$(BOOT) output -raw project_id) $$($(TF) -chdir=$(BOOT) output -raw region) \
	     && { echo "── Retrieval test set (MVP-05; 29 cases as weekendwise-run, reads only)"; $(PY) scripts/check_retrieval.py; }; \
	 fi
	@if $(TF) -chdir=$(STACK) state list 2>/dev/null | grep -q '^google_cloud_run_v2_service.app$$'; then \
	   echo "── Cloud Run (IAC-05)"; \
	   $(TF) -chdir=$(STACK) output -json cloud_run | python3 -c "import json,sys; d=json.load(sys.stdin); [print(f'  {k}: {d[k]}') for k in ('image','service_account','min_instances','max_instances','public','deletion_protection','latest_ready_revision')]"; \
	   url=$$($(TF) -chdir=$(STACK) output -json cloud_run | python3 -c "import json,sys; print(json.load(sys.stdin)['url'])"); \
	   code=$$(curl -s -o /dev/null -m 30 -w '%{http_code}' $$url/health); \
	   echo "  request without a token: HTTP $$code ($$( [ $$code = 403 ] && echo 'private, as intended' || echo 'check allow_unauthenticated'))"; \
	   echo "  Deeper check (health, readiness, one live plan): make smoke-cloud"; \
	 fi

destroy: _need-stack _stack-operator ## Destroy the stack only (keeps project, billing, budget, state). Shows the plan, then asks for the project ID (or CONFIRM=<project-id>)
	@$(MAKE) --no-print-directory _stack-destroy-plan
	@project=$(PROJECT); \
	 if [ "$(CONFIRM)" != "$$project" ]; then read -r -p "Type the project ID ($$project) to destroy the stack: " ans; [ "$$ans" = "$$project" ] || { echo "✗ Cancelled"; exit 1; }; fi
	@$(MAKE) --no-print-directory _stack-destroy
	@echo "✓ Stack destroyed. Check with: make verify-destroyed   Rebuild with: make apply && make seed && make release"

STACK_UNPROTECT := -var=firestore_delete_protection=false -var=cloud_run_deletion_protection=false

# Show what a stack destroy would remove (read-only).
_stack-destroy-plan:
	@$(TF) -chdir=$(STACK) init -input=false -reconfigure -backend-config=backend.hcl >/dev/null
	@echo "── These stack resources would be destroyed:"
	@$(TF) -chdir=$(STACK) plan -destroy -input=false -no-color -lock=false $(STACK_UNPROTECT) 2>&1 \
	   | grep -E '^  # .* will be destroyed|^Plan:' | sed -e 's/^  # /  - /' -e 's/ will be destroyed//' || true

# Lift delete protection (only here), destroy everything in the stack, and forget the deployed image
# (its registry is gone, so the next make apply starts from the placeholder image).
_stack-destroy:
	$(TF) -chdir=$(STACK) init -input=false -reconfigure -backend-config=backend.hcl >/dev/null
	@targets=""; state=$$($(TF) -chdir=$(STACK) state list 2>/dev/null); \
	 echo "$$state" | grep -q '^google_firestore_database.default$$' && targets="$$targets -target=google_firestore_database.default"; \
	 echo "$$state" | grep -q '^google_cloud_run_v2_service.app$$' && targets="$$targets -target=google_cloud_run_v2_service.app"; \
	 if [ -n "$$targets" ]; then \
	   echo "── Lifting delete protection (Firestore, Cloud Run)"; \
	   $(TF) -chdir=$(STACK) apply -input=false -auto-approve $$targets $(STACK_UNPROTECT) || exit 1; \
	 fi
	$(TF) -chdir=$(STACK) destroy -input=false -auto-approve $(STACK_UNPROTECT)
	@rm -f $(IMAGE_VARS) $(LAST_BUILD)

destroy-all: _need-boot-vars _need-billing ## Destroy EVERYTHING incl. the project. Confirm with CONFIRM=<project-id>
	@project=$$($(TF) -chdir=$(BOOT) output -raw project_id 2>/dev/null); \
	 [ -n "$$project" ] || { echo "✗ No bootstrap state found; nothing to destroy."; exit 1; }; \
	 echo "⚠  This deletes the stack, budget, state bucket, and project $$project (restorable ~30 days in the console)."; \
	 if [ -f $(BACKEND) ] && [ -f $(STACK_GEN) ]; then $(MAKE) --no-print-directory _stack-destroy-plan; fi; \
	 echo "── Then the bootstrap: the budget, API enablement, state bucket, and the project itself."; \
	 if [ "$(CONFIRM)" != "$$project" ]; then read -r -p "Type the project ID ($$project) to destroy everything: " ans; [ "$$ans" = "$$project" ] || { echo "✗ Cancelled"; exit 1; }; fi
	@if [ -f $(BACKEND) ] && [ -f $(STACK_GEN) ]; then $(MAKE) --no-print-directory _stack-operator _stack-destroy; fi
	@echo "── Lifting deletion protection on the project and state bucket"
	$(TF) -chdir=$(BOOT) apply -input=false -auto-approve \
	  -target=google_project.this -target=google_storage_bucket.tf_state \
	  -var=project_deletion_policy=DELETE -var=state_bucket_force_destroy=true
	$(TF) -chdir=$(BOOT) destroy -input=false -auto-approve \
	  -var=project_deletion_policy=DELETE -var=state_bucket_force_destroy=true
	@rm -f $(BACKEND) $(STACK_GEN)
	@echo "✓ Everything destroyed. Run 'make verify-destroyed', and check Billing → Reports over the next few days."

verify-destroyed: ## List anything WeekendWise left behind; fails if something remains (after destroy or destroy-all)
	@bash scripts/verify_destroyed.sh

run: _need-venv ## Run the real app locally at http://localhost:8080 as weekendwise-run (PORT=8080). Each plan costs ~1 cent
	@echo "→ WeekendWise on http://localhost:$(or $(PORT),8080)  (Ctrl+C to stop; runs as weekendwise-run, live Vertex AI + Firestore)"
	@WEEKENDWISE_RUN_AS=run $(PY) -m uvicorn --factory weekendwise.web.server:create_app --host 127.0.0.1 --port $(or $(PORT),8080) --no-access-log

mockups: ## Serve the HTML mockup at http://localhost:8000/plan with clean page paths (PORT=8000)
	@python3 scripts/serve_mockups.py $(or $(PORT),8000)

build: _need-stack test ## Run tests, then build the app image with Cloud Build (as weekendwise-build) and push it to Artifact Registry
	@project=$(PROJECT); region=$(REGION); repo=$(REPO); \
	 gcloud artifacts repositories describe weekendwise --location $$region --project $$project >/dev/null 2>&1 \
	   || { echo "✗ Artifact Registry repository not found. Run: make apply"; exit 1; }; \
	 if git rev-parse --git-dir >/dev/null 2>&1 && git diff --quiet HEAD 2>/dev/null; then tag=$$(git rev-parse --short=12 HEAD); \
	 else tag=$$(date -u +%Y%m%d-%H%M%S); fi; \
	 echo "── Building $$repo:$$tag with Cloud Build (uploads only the files allowed by .gcloudignore; ~2–4 min)"; \
	 gcloud builds submit . --project $$project --region $$region --config cloudbuild.yaml \
	   --service-account projects/$$project/serviceAccounts/weekendwise-build@$$project.iam.gserviceaccount.com \
	   --substitutions _IMAGE=$$repo,_TAG=$$tag || exit 1; \
	 echo "$$repo:$$tag" > $(LAST_BUILD); \
	 echo "✓ Pushed $$repo:$$tag"; echo "  Next: make deploy   (rolls out this image)"

deploy: _need-stack _stack-operator ## Roll out an image with Terraform: make deploy (last build) or IMAGE=<tag> to roll back
	@image="$(IMAGE)"; [ -n "$$image" ] || image=$$(cat $(LAST_BUILD) 2>/dev/null); \
	 [ -n "$$image" ] || { echo "✗ No image. Run make build first, or pass IMAGE=<tag> (see make images)"; exit 1; }; \
	 case "$$image" in */*) ;; *) image="$(REPO):$$image";; esac; \
	 printf '{\n  "image": "%s"\n}\n' "$$image" > $(IMAGE_VARS); \
	 echo "── Deploying $$image (saved in $(IMAGE_VARS) so make apply keeps it)"
	$(TF) -chdir=$(STACK) init -input=false -reconfigure -backend-config=backend.hcl >/dev/null
	$(TF) -chdir=$(STACK) apply -input=false
	@echo "── Service"; $(TF) -chdir=$(STACK) output -json cloud_run | python3 -c "import json,sys; d=json.load(sys.stdin); [print(f'  {k}: {d[k]}') for k in ('url','image','latest_ready_revision','public','min_instances','max_instances')]"
	@echo "  Next: make smoke-cloud   (health, readiness, and one live plan as the runtime identity)"
	@echo "        make proxy         (open the private app in your browser at http://localhost:8082)"

release: build deploy ## build + deploy in one go

images: _need-stack ## List recent images (tags you can roll back to with make deploy IMAGE=<tag>)
	@gcloud artifacts docker images list $(REPO) --include-tags --sort-by=~CREATE_TIME --limit 10 \
	   --format='table(tags.list():label=TAG,createTime.date("%Y-%m-%d %H:%M"):label=CREATED)'; \
	 echo "Deployed now: $$(sed -n 's/.*"image": "\(.*\)".*/\1/p' $(IMAGE_VARS) 2>/dev/null)"

proxy: _need-stack ## Open the private Cloud Run app at http://localhost:8082 using your Google sign-in (PORT=8082)
	@echo "→ http://localhost:$(or $(PORT),8082)  (Ctrl+C to stop; requests are signed with your gcloud identity)"
	@gcloud run services proxy weekendwise --project $(PROJECT) --region $(REGION) --port $(or $(PORT),8082)

logs: _need-stack ## Recent Cloud Run app logs (last hour): RID=<request id> for one request, ERRORS=1 for errors only
	@filter='resource.type="cloud_run_revision" AND resource.labels.service_name="weekendwise" AND jsonPayload.message:*'; \
	 [ -z "$(RID)" ] || filter="$$filter AND jsonPayload.requestId=\"$(RID)\""; \
	 [ -z "$(ERRORS)" ] || filter="$$filter AND severity>=ERROR"; \
	 gcloud logging read "$$filter" --project $(PROJECT) --freshness 1h --limit $(or $(N),40) --order asc \
	   --format='table[no-heading](timestamp.date("%H:%M:%S"),severity,jsonPayload.requestId,jsonPayload.message,jsonPayload.stage,jsonPayload.component,jsonPayload.status,jsonPayload.latencyMs,jsonPayload.errorCategory)'

smoke-cloud: _need-venv _need-stack ## Check the deployed service: private by default, healthy, ready, one live plan (~1 cent). NO_PLAN=1 to skip the plan
	@$(PY) scripts/smoke_cloud_run.py $(if $(NO_PLAN),--no-plan)

ui-smoke: _need-venv ## Drive the web UI in headless Chrome (local app on :8080; CLOUD=1 for Cloud Run; OFFLINE=1 = free checks only)
	@$(PY) -c "import playwright" 2>/dev/null || $(PY) -m pip install -q playwright==1.64.1
	@if [ -n "$(CLOUD)" ]; then \
	   url=$$($(TF) -chdir=$(STACK) output -json cloud_run | python3 -c "import json,sys; print(json.load(sys.stdin)['url'])"); \
	   $(PY) scripts/ui_smoke.py --base-url $$url --bearer "$$(gcloud auth print-identity-token)" $(if $(OFFLINE),--offline) $(S); \
	 else $(PY) scripts/ui_smoke.py $(if $(OFFLINE),--offline) $(S); fi

seed: _need-venv _need-stack ## Load data/seed/ into Firestore with embeddings (DRY_RUN=1 to preview; FIXTURES=1 adds test fixtures)
	@python3 scripts/build_seed_data.py | tail -1
	@dim=$$($(TF) -chdir=$(STACK) output -json firestore 2>/dev/null | $(PY) -c "import json,sys; print(json.load(sys.stdin)['embedding_dimension'])" 2>/dev/null); \
	 [ -n "$$dim" ] || { echo "✗ Firestore isn't in the stack yet. Run: make apply"; exit 1; }; \
	 $(PY) scripts/seed_firestore.py --index-dimension $$dim $(if $(DRY_RUN),--dry-run) $(if $(FIXTURES),--include-fixtures)
