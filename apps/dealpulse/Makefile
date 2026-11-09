# DealPulse commands. See docs/mvp/guides/00-provision-with-terraform.md
#
# Two Terraform layers:
#   infra/bootstrap  state bucket, budget                          (local state, git-ignored)
#   infra/stack      everything the app needs                      (S3 state with native locking)
#
# AWS sign-in: uses AWS_PROFILE (default: "default"). Override per command: make plan AWS_PROFILE=demo

SHELL := /bin/bash
TF    ?= terraform
AWS_PROFILE ?= default
# YES=1 skips Terraform's "yes" prompt (use only after reviewing a plan).
export AWS_PROFILE
PY    := .venv/bin/python

BOOT      := infra/bootstrap
STACK     := infra/stack
BOOT_VARS := $(BOOT)/terraform.tfvars
STACK_GEN := $(STACK)/bootstrap.auto.tfvars.json
BACKEND   := $(STACK)/backend.hcl
BOOT_LOG  := infra/.verify-bootstrap.log
STACK_LOG := infra/.verify-stack.log
PREFIX     = $$(sed -n 's/^name_prefix *= *"\(.*\)"/\1/p' $(BOOT_VARS) 2>/dev/null)

.DEFAULT_GOAL := help
.PHONY: help tools configure check bootstrap bootstrap-plan plan apply verify \
        data train approve-model deploy-model seed build deploy release images proxy pause resume \
        destroy destroy-all verify-destroyed \
        venv test architecture models mockups mockup-smoke run _stack-not-locked _stack-destroy-plan _stack-destroy _need-boot-vars _need-stack _need-signin _need-venv _not-yet

help: ## Show available commands
	@grep -hE '^[a-z][a-z-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*## "}{printf "  make %-17s %s\n",$$1,$$2}'

# ---------------------------------------------------------------- Setup

tools: ## Check Terraform, AWS CLI, Session Manager plugin, Python and AWS sign-in
	@command -v $(TF) >/dev/null || { echo "✗ terraform not found. Install 1.10+ from https://developer.hashicorp.com/terraform/install"; exit 1; }
	@v=$$($(TF) version -json | python3 -c "import json,sys; print(json.load(sys.stdin)['terraform_version'])"); \
	 python3 -c "import sys; v=tuple(map(int,'$$v'.split('.')[:2])); sys.exit(0 if v>=(1,10) else 1)" \
	   && echo "✓ terraform $$v" || { echo "✗ terraform $$v is too old; need 1.10+ (S3 state locking)"; exit 1; }
	@command -v aws >/dev/null && echo "✓ $$(aws --version 2>&1 | cut -d' ' -f1)" || { echo "✗ AWS CLI not found. Install: https://docs.aws.amazon.com/cli/"; exit 1; }
	@command -v session-manager-plugin >/dev/null && echo "✓ session-manager-plugin (for make proxy)" \
	   || { echo "✗ Session Manager plugin not found (needed for make proxy). Install: https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html"; exit 1; }
	@python3 -c "import sys; sys.exit(0 if sys.version_info>=(3,11) else 1)" && echo "✓ $$(python3 --version)" || { echo "✗ Python 3.11+ required"; exit 1; }
	@$(MAKE) --no-print-directory _need-signin
	@arn=$$(aws sts get-caller-identity --query Arn --output text); \
	 echo "✓ signed in (profile $(AWS_PROFILE)): $${arn##*:}"; \
	 case "$$arn" in *:user/*) echo "  note: this is an IAM user with long-lived access keys. It works; short-lived sign-in (aws sso login) is safer.";; esac; \
	 region=$$(aws configure get region); [ "$$region" = "us-east-1" ] || echo "  note: profile region is '$$region'; DealPulse uses the region in $(BOOT_VARS) (us-east-1)."

_need-signin:
	@aws sts get-caller-identity >/dev/null 2>&1 || { echo "✗ Not signed in to AWS (profile $(AWS_PROFILE)). Run: aws sso login --profile $(AWS_PROFILE), or set AWS_PROFILE=<profile>"; exit 1; }

configure: ## Create infra/bootstrap/terraform.tfvars with a unique name prefix (dealpulse-xxxx)
	@if [ -f $(BOOT_VARS) ]; then echo "✓ $(BOOT_VARS) already exists (not changed): name_prefix = $(PREFIX)"; exit 0; fi; \
	 suffix=$$(LC_ALL=C tr -dc 'a-z0-9' </dev/urandom | head -c 4); \
	 sed "s/dealpulse-xxxx/dealpulse-$$suffix/" $(BOOT)/terraform.tfvars.example > $(BOOT_VARS); \
	 echo "✓ Created $(BOOT_VARS) with name_prefix dealpulse-$$suffix. Review it, then: make bootstrap"

check: ## Format-check and validate all Terraform (no AWS access needed)
	$(TF) fmt -check -recursive infra
	$(TF) -chdir=$(BOOT) init -backend=false -input=false >/dev/null
	$(TF) -chdir=$(BOOT) validate
	$(TF) -chdir=$(STACK) init -backend=false -input=false >/dev/null
	$(TF) -chdir=$(STACK) validate

# ---------------------------------------------------------------- Python

_need-venv:
	@[ -x $(PY) ] && $(PY) -c "import boto3, pytest" 2>/dev/null || { echo "✗ Python environment not ready. Run: make venv"; exit 1; }

venv: ## Create .venv and install pinned Python dependencies
	@[ -x $(PY) ] || python3 -m venv .venv
	$(PY) -m pip install -q --upgrade pip
	$(PY) -m pip install -q -r requirements-dev.txt
	@echo "✓ Python environment ready ($$($(PY) --version))"

test: _need-venv ## Run offline unit tests (no AWS calls)
	$(PY) -m pytest -q tests

architecture: _need-venv ## Render the Architecture page to docs/images/architecture.png (needs Chrome)
	@$(PY) -c "import playwright" 2>/dev/null || $(PY) -m pip install -q playwright==1.64.1
	$(PY) scripts/render_architecture.py

run: _need-venv ## Run the web app at http://localhost:8501 (offline: saved data, no AWS). PORT=8501
	@$(PY) -c "import streamlit" 2>/dev/null || { echo "✗ Streamlit missing. Run: make venv"; exit 1; }
	@echo "→ http://localhost:$(or $(PORT),8501)/  (Ctrl+C to stop; data: $${DEALPULSE_DATA:-offline})"
	@DEALPULSE_DATA=$${DEALPULSE_DATA:-offline} $(PY) -m streamlit run dealpulse/ui/app.py --server.address 127.0.0.1 --server.port $(or $(PORT),8501)

mockups: ## Serve the clickable UI mockup at http://localhost:8000/#pipeline (PORT=8000; local only)
	@echo "→ http://localhost:$(or $(PORT),8000)/#pipeline  (Ctrl+C to stop; synthetic data, no AWS calls)"
	@python3 -m http.server $(or $(PORT),8000) --bind 127.0.0.1 --directory artifacts/dealpulse-mockups

mockup-smoke: _need-venv ## Drive the mockup in headless Chrome: pages, persona rules, citations, phone width
	@$(PY) -c "import playwright" 2>/dev/null || $(PY) -m pip install -q playwright==1.64.1
	@$(PY) scripts/mockup_smoke.py

# ---------------------------------------------------------------- Bootstrap

_need-boot-vars:
	@[ -f $(BOOT_VARS) ] || { echo "✗ $(BOOT_VARS) missing. Run: make configure"; exit 1; }

bootstrap-plan: _need-boot-vars _need-signin ## Preview what bootstrap will create or change
	$(TF) -chdir=$(BOOT) init -input=false
	$(TF) -chdir=$(BOOT) plan -input=false

bootstrap: _need-boot-vars _need-signin ## Create/update the state bucket (and budget, IAC-02); writes the stack's backend settings
	@echo "⚠  This creates AWS resources in account $$(aws sts get-caller-identity --query Account --output text). Budgets only ALERT; they don't stop spending."
	$(TF) -chdir=$(BOOT) init -input=false
	$(TF) -chdir=$(BOOT) apply -input=false $(if $(YES),-auto-approve)
	@prefix=$$($(TF) -chdir=$(BOOT) output -raw name_prefix); \
	 region=$$($(TF) -chdir=$(BOOT) output -raw region); \
	 bucket=$$($(TF) -chdir=$(BOOT) output -raw state_bucket); \
	 printf 'bucket       = "%s"\nkey          = "stack/terraform.tfstate"\nregion       = "%s"\nencrypt      = true\nuse_lockfile = true\n' "$$bucket" "$$region" > $(BACKEND); \
	 printf '{\n  "name_prefix": "%s",\n  "region": "%s"\n}\n' "$$prefix" "$$region" > $(STACK_GEN); \
	 echo ""; echo "✓ Bootstrap complete"; \
	 echo "  name prefix:  $$prefix"; echo "  region:       $$region"; echo "  state bucket: $$bucket"; \
	 echo "  wrote $(BACKEND) and $(STACK_GEN)"

# ---------------------------------------------------------------- Stack

_need-stack:
	@[ -f $(BACKEND) ] && [ -f $(STACK_GEN) ] || { echo "✗ Stack isn't configured. Run: make bootstrap"; exit 1; }

plan: _need-stack _need-signin ## Preview changes to the stack
	$(TF) -chdir=$(STACK) init -input=false -reconfigure -backend-config=backend.hcl >/dev/null
	$(TF) -chdir=$(STACK) plan -input=false

apply: _need-stack _need-signin ## Create/update the stack (then the OpenSearch index and search pipeline)
	@if $(TF) -chdir=$(STACK) state list 2>/dev/null | grep -q '^aws_opensearch_domain.main$$'; then :; \
	 elif grep -q 'aws_opensearch_domain' $(STACK)/*.tf; then \
	   echo "⚠  This run may create the OpenSearch domain: ~\$$0.036/hour (~\$$26/month), billed until destroyed, even when idle."; \
	   echo "   Creating it takes about 15–20 minutes."; fi
	$(TF) -chdir=$(STACK) init -input=false -reconfigure -backend-config=backend.hcl >/dev/null
	$(TF) -chdir=$(STACK) apply -input=false $(if $(YES),-auto-approve)
	@if $(TF) -chdir=$(STACK) state list 2>/dev/null | grep -q '^aws_opensearch_domain.main$$'; then \
	   [ -x $(PY) ] || { echo "✗ Run make venv, then make apply again to create the index"; exit 1; }; \
	   echo "── OpenSearch index and search pipeline (as the ingest role)"; \
	   $(PY) scripts/setup_opensearch.py $(if $(RISK_CHECK),--risk-check); \
	 fi

verify: _need-boot-vars _need-stack _need-signin ## Check bootstrap and stack for drift, and show what exists
	@echo "── Bootstrap drift check…"; start=$$(date +%s); \
	 $(TF) -chdir=$(BOOT) plan -input=false -no-color -detailed-exitcode -lock=false >$(BOOT_LOG) 2>&1; rc=$$?; \
	 secs=$$(( $$(date +%s) - start )); \
	 if [ $$rc -eq 0 ]; then echo "✓ bootstrap: no changes ($${secs}s)"; \
	 elif [ $$rc -eq 2 ]; then echo "✗ bootstrap: drift found ($${secs}s):"; grep -E '^  [#~+-]|Plan:' $(BOOT_LOG) | sed 's/^/    /'; exit 1; \
	 else echo "✗ bootstrap check failed:"; tail -20 $(BOOT_LOG) | sed 's/^/    /'; exit $$rc; fi
	@echo "── Stack drift check…"; start=$$(date +%s); \
	 $(TF) -chdir=$(STACK) init -input=false -reconfigure -backend-config=backend.hcl >$(STACK_LOG) 2>&1 || { echo "✗ stack init failed:"; tail -20 $(STACK_LOG) | sed 's/^/    /'; exit 1; }; \
	 $(TF) -chdir=$(STACK) plan -input=false -no-color -detailed-exitcode -lock=false >$(STACK_LOG) 2>&1; rc=$$?; \
	 secs=$$(( $$(date +%s) - start )); \
	 if [ $$rc -eq 0 ]; then echo "✓ stack: no changes ($${secs}s)"; \
	 elif [ $$rc -eq 2 ]; then echo "✗ stack: drift found ($${secs}s):"; grep -E '^  [#~+-]|Plan:' $(STACK_LOG) | sed 's/^/    /'; exit 1; \
	 else echo "✗ stack check failed:"; tail -20 $(STACK_LOG) | sed 's/^/    /'; exit $$rc; fi
	@echo "── State bucket"; bucket=$$($(TF) -chdir=$(BOOT) output -raw state_bucket); \
	 echo "  $$bucket"; \
	 echo "  versioning: $$(aws s3api get-bucket-versioning --bucket $$bucket --query Status --output text)"; \
	 echo "  public access blocked: $$(aws s3api get-public-access-block --bucket $$bucket --query 'PublicAccessBlockConfiguration.[BlockPublicAcls,BlockPublicPolicy,IgnorePublicAcls,RestrictPublicBuckets]' --output text | tr '\t' ' ')"; \
	 echo "  stack state: $$(aws s3 ls s3://$$bucket/stack/ | awk '{print $$4" ("$$3" bytes)"}' | tr '\n' ' ')"
	@echo "── Budget (alerts only; never stops spending)"; acct=$$(aws sts get-caller-identity --query Account --output text); \
	 name=$(PREFIX)-monthly; \
	 aws budgets describe-budget --account-id $$acct --budget-name $$name \
	   --query 'Budget.[BudgetName,BudgetLimit.Amount,CalculatedSpend.ActualSpend.Amount]' --output text \
	   | awk -F'\t' '{printf "  %s: $$%s/month, spent so far $$%.2f (tag app=dealpulse)\n",$$1,$$2,$$3}'; \
	 echo "  alerts: $$(aws budgets describe-notifications-for-budget --account-id $$acct --budget-name $$name --query 'length(Notifications)' --output text)"; \
	 echo "  cost tag 'app': $$(aws ce list-cost-allocation-tags --tag-keys app --query 'CostAllocationTags[0].Status' --output text)"
	@if [ -x $(PY) ] && $(TF) -chdir=$(STACK) state list 2>/dev/null | grep -q '^aws_iam_role.run$$'; then \
	   echo "── IAM roles and network (IAC-03; policy simulator, calls no services)"; \
	   $(PY) scripts/verify_iam.py; \
	 fi
	@if [ -x $(PY) ] && $(TF) -chdir=$(STACK) state list 2>/dev/null | grep -q '^aws_opensearch_domain.main$$'; then \
	   echo "── OpenSearch and data bucket (IAC-04; real requests, changes nothing)"; \
	   $(PY) scripts/verify_opensearch.py; \
	 fi
	@if [ -x $(PY) ] && $(TF) -chdir=$(STACK) state list 2>/dev/null | grep -q '^aws_bedrock_guardrail.main$$'; then \
	   echo "── Bedrock guardrail (IAC-05; 5 checks as the app role, fractions of a cent)"; \
	   $(PY) scripts/verify_guardrail.py; \
	   echo "── Model endpoint"; \
	   $(TF) -chdir=$(STACK) output -json model | $(PY) -c "import json,sys; m=json.load(sys.stdin); \
	     print('  registry:', m['package_group']); \
	     print('  endpoint:', m['endpoint'] or 'not deployed (make deploy-model MODEL=<approved package ARN>)')"; \
	 fi

# ---------------------------------------------------------------- Later stories

_not-yet:
	@echo "✗ 'make $(WHAT)' is not available yet (delivered by $(STORY); see docs/mvp/README.md)"; exit 1

data: _need-venv ## Generate synthetic Salesforce data into data/out, check it, upload to S3 (LOCAL=1 skips upload; SEED=n)
	@[ -n "$(LOCAL)" ] || $(MAKE) --no-print-directory _need-stack _need-signin
	@$(PY) scripts/generate_data.py $(if $(SEED),--seed $(SEED)) $(if $(LOCAL),,--upload)
train: _need-venv _need-stack _need-signin ## Train on SageMaker (~1 cent), write the evaluation report, register the model as PENDING
	@echo "⚠  Starts a SageMaker training job: one ml.m5.large for a few minutes (about a cent)."
	@$(PY) scripts/train_model.py train
approve-model: _need-venv _need-stack _need-signin ## Approve a registered model after reading its report: MODEL=<package-arn>
	@[ -n "$(MODEL)" ] || { echo "✗ Usage: make approve-model MODEL=<model package ARN>  (list them: make models)"; exit 1; }
	@$(PY) scripts/train_model.py approve --model "$(MODEL)" $(if $(YES),--yes)
MODEL_VARS := $(STACK)/model.auto.tfvars.json

deploy-model: _need-stack _need-signin ## Serve an APPROVED model on the serverless endpoint: MODEL=<package-arn> (also rolls back)
	@[ -n "$(MODEL)" ] || { echo "✗ Usage: make deploy-model MODEL=<model package ARN>  (list them: make models)"; exit 1; }
	@status=$$(aws sagemaker describe-model-package --model-package-name "$(MODEL)" --query ModelApprovalStatus --output text 2>/dev/null); \
	 [ -n "$$status" ] || { echo "✗ Model package not found: $(MODEL)"; exit 1; }; \
	 [ "$$status" = "Approved" ] || { echo "✗ $(MODEL) is $$status. Read its evaluation report, then: make approve-model MODEL=$(MODEL)"; exit 1; }; \
	 previous=$$(sed -n 's/.*"model_package_arn": "\(.*\)".*/\1/p' $(MODEL_VARS) 2>/dev/null); \
	 printf '{\n  "model_package_arn": "%s"\n}\n' "$(MODEL)" > $(MODEL_VARS); \
	 echo "── Deploying $(MODEL) (saved in $(MODEL_VARS))"; \
	 [ -z "$$previous" ] || echo "   previous: $$previous  (to roll back: make deploy-model MODEL=$$previous)"
	$(TF) -chdir=$(STACK) init -input=false -reconfigure -backend-config=backend.hcl >/dev/null
	$(TF) -chdir=$(STACK) apply -input=false $(if $(YES),-auto-approve)
	@echo "── Endpoint"; aws sagemaker describe-endpoint --endpoint-name $$($(TF) -chdir=$(STACK) output -json model | python3 -c "import json,sys; print(json.load(sys.stdin)['endpoint'])") \
	   --query '[EndpointName,EndpointStatus,EndpointConfigName]' --output text

models: _need-stack _need-signin ## List registered model versions and their approval status
	@group=$$($(TF) -chdir=$(STACK) output -json model | python3 -c "import json,sys; print(json.load(sys.stdin)['package_group'])"); \
	 aws sagemaker list-model-packages --model-package-group-name $$group --sort-by CreationTime --sort-order Descending \
	   --query 'ModelPackageSummaryList[].[ModelPackageVersion,ModelApprovalStatus,CreationTime,ModelPackageArn]' --output table; \
	 echo "Deployed now: $$(sed -n 's/.*"model_package_arn": "\(.*\)".*/\1/p' $(MODEL_VARS) 2>/dev/null || echo none)"
seed: ## Embed notes and playbooks and load them into OpenSearch (MVP-06)
	@$(MAKE) --no-print-directory _not-yet WHAT=$@ STORY=MVP-06
build: ## Run tests, then build the app image with CodeBuild (IAC-06)
	@$(MAKE) --no-print-directory _not-yet WHAT=$@ STORY=IAC-06
deploy: ## Roll out an image to ECS: IMAGE=<tag> (IAC-06)
	@$(MAKE) --no-print-directory _not-yet WHAT=$@ STORY=IAC-06
release: ## build + deploy (IAC-06)
	@$(MAKE) --no-print-directory _not-yet WHAT=$@ STORY=IAC-06
images: ## List recent image tags you can roll back to (IAC-06)
	@$(MAKE) --no-print-directory _not-yet WHAT=$@ STORY=IAC-06
proxy: ## Open the private app at http://localhost:8502 through an SSM tunnel (IAC-06)
	@$(MAKE) --no-print-directory _not-yet WHAT=$@ STORY=IAC-06
pause: ## Scale the app to 0 tasks (IAC-06)
	@$(MAKE) --no-print-directory _not-yet WHAT=$@ STORY=IAC-06
resume: ## Scale the app back to 1 task (IAC-06)
	@$(MAKE) --no-print-directory _not-yet WHAT=$@ STORY=IAC-06
# ---------------------------------------------------------------- Teardown (IAC-07)
# Protection (data bucket that refuses to delete while it holds files) is lifted ONLY here.
STACK_UNPROTECT := -var=data_bucket_force_destroy=true

destroy: _need-venv _need-stack _need-signin ## Destroy the stack (keeps state bucket + budget). Shows what goes, then asks for the prefix (or CONFIRM=<prefix>)
	@$(MAKE) --no-print-directory _stack-destroy-plan
	@prefix=$(PREFIX); \
	 if [ "$(CONFIRM)" != "$$prefix" ]; then read -r -p "Type the name prefix ($$prefix) to destroy the stack: " ans || ans=""; \
	   [ "$$ans" = "$$prefix" ] || { echo "✗ Cancelled. Nothing was changed."; exit 1; }; fi
	@$(MAKE) --no-print-directory _stack-destroy
	@echo "✓ Stack destroyed. Check: make verify-destroyed"
	@echo "  Rebuild: make apply RISK_CHECK=1 && make data && make train  (then approve/deploy a model)"

# Stop early, before any question, if another Terraform run holds the stack's state lock.
_stack-not-locked:
	@bucket=$$(sed -n 's/^bucket *= *"\(.*\)"/\1/p' $(BACKEND)); key=$$(sed -n 's/^key *= *"\(.*\)"/\1/p' $(BACKEND)); \
	 lock=$$(aws s3 cp "s3://$$bucket/$$key.tflock" - 2>/dev/null) || exit 0; \
	 echo "$$lock" | python3 -c "import json,sys; l=json.load(sys.stdin); \
print('✗ Another Terraform run is using the stack right now, so nothing was changed.'); \
print(f\"  {l.get('Operation','?').replace('OperationType','')} by {l.get('Who','?')}, started {l.get('Created','?')[:19]} UTC (lock {l.get('ID','?')})\"); \
print('  Wait for it to finish (a model deploy takes ~10 min, OpenSearch ~20), then run this again.'); \
print('  Only if that run crashed and nothing is running: terraform -chdir=infra/stack force-unlock ' + l.get('ID','<ID>'))"; \
	 exit 1

# What a stack destroy would remove (reads only).
_stack-destroy-plan: _stack-not-locked
	@$(TF) -chdir=$(STACK) init -input=false -reconfigure -backend-config=backend.hcl >/dev/null
	@echo "── Terraform would destroy:"
	@$(TF) -chdir=$(STACK) plan -destroy -input=false -no-color -lock=false $(STACK_UNPROTECT) 2>&1 \
	   | grep -E '^  # .* will be destroyed|^Plan:' | sed -e 's/^  # /  - /' -e 's/ will be destroyed//' || true
	@echo "── Also removed (made outside Terraform):"
	@$(PY) scripts/predestroy.py --dry-run | sed 's/^/  /'
	@echo "⚠  This deletes the synthetic data, the search index, model versions and the guardrail. It can't be undone."

_stack-destroy:
	$(TF) -chdir=$(STACK) init -input=false -reconfigure -backend-config=backend.hcl >/dev/null
	@if $(TF) -chdir=$(STACK) state list 2>/dev/null | grep -q '^aws_s3_bucket.data$$'; then \
	   echo "── Allowing the data bucket to be deleted with its files"; \
	   $(TF) -chdir=$(STACK) apply -input=false -auto-approve -target=aws_s3_bucket.data $(STACK_UNPROTECT) >/dev/null || exit 1; \
	 fi
	@echo "── Removing model versions and training logs"; $(PY) scripts/predestroy.py
	@echo "── Destroying the stack (the OpenSearch domain takes about 10–15 minutes)"
	$(TF) -chdir=$(STACK) destroy -input=false -auto-approve $(STACK_UNPROTECT)
	@rm -f $(MODEL_VARS) infra/.last-build

BOOT_UNPROTECT := -var=state_bucket_force_destroy=true

destroy-all: _need-venv _need-boot-vars _need-signin ## Destroy EVERYTHING: stack, then state bucket, budget and cost tag. Confirm with CONFIRM=<prefix>
	@prefix=$(PREFIX); \
	 echo "⚠  This removes all of DealPulse in account $$(aws sts get-caller-identity --query Account --output text): the stack, then the state bucket, the \$$60 budget and the 'app' cost tag."; \
	 if [ -f $(BACKEND) ] && [ -f $(STACK_GEN) ]; then $(MAKE) --no-print-directory _stack-destroy-plan; fi; \
	 echo "── Then the bootstrap:"; echo "  - state bucket, budget, cost allocation tag 'app' (back to Inactive)"; \
	 if [ "$(CONFIRM)" != "$$prefix" ]; then read -r -p "Type the name prefix ($$prefix) to destroy everything: " ans || ans=""; \
	   [ "$$ans" = "$$prefix" ] || { echo "✗ Cancelled. Nothing was changed."; exit 1; }; fi
	@if [ -f $(BACKEND) ] && [ -f $(STACK_GEN) ]; then $(MAKE) --no-print-directory _stack-destroy; fi
	@echo "── Allowing the state bucket to be deleted with its files"
	$(TF) -chdir=$(BOOT) init -input=false >/dev/null
	$(TF) -chdir=$(BOOT) apply -input=false -auto-approve -target=aws_s3_bucket.tf_state $(BOOT_UNPROTECT) >/dev/null
	$(TF) -chdir=$(BOOT) destroy -input=false -auto-approve $(BOOT_UNPROTECT)
	@rm -f $(BACKEND) $(STACK_GEN)
	@echo "✓ Everything destroyed. Check: make verify-destroyed ALL=1, and Billing → Bills over the next few days."
	@echo "  Your settings (infra/bootstrap/terraform.tfvars) are kept; make bootstrap starts again from scratch."

verify-destroyed: _need-venv _need-boot-vars _need-signin ## List anything DealPulse left behind (ALL=1 after destroy-all). Fails if something remains
	@$(PY) scripts/verify_destroyed.py $(if $(ALL),--all)
