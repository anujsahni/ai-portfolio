# ContextLoop: every target is a thin wrapper over docker compose. Run `make help`.
SHELL := /bin/bash
COMPOSE := docker compose
RUN := $(COMPOSE) run --rm
BATCH ?= 1
TRAP ?= T1

.DEFAULT_GOAL := help
.PHONY: help images up down clean ps logs data sync build break lakehouse eval record ask export demo test sdk-debug pitch-video media-infra publish-pitch

help: ## Show available commands
	@grep -hE '^[a-z][a-z-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*## "}{printf "  make %-11s %s\n",$$1,$$2}'

images: ## Build the contextloop image and pull the pinned public images
	$(COMPOSE) build
	$(COMPOSE) --profile lakehouse pull --ignore-buildable

up: ## Start the long-running services and wait until they are healthy
	$(COMPOSE) up -d --wait

down: ## Stop everything (volumes are kept)
	$(COMPOSE) --profile lakehouse --profile jobs down

clean: ## Stop everything and delete the volumes and generated data
	$(COMPOSE) --profile lakehouse --profile jobs down -v
	rm -rf data/out connectors/*/files

ps: ## Show service status
	$(COMPOSE) --profile lakehouse ps

logs: ## Follow service logs
	$(COMPOSE) logs -f --tail=100

data: ## Generate the synthetic sources and seed Postgres (BATCH=2 adds the schema-change batch)
	$(RUN) datagen python -m contextloop.cli datagen --batch $(BATCH)

sync: ## Run both Connector SDK connectors and the SaaS landings, and write the sync log
	$(RUN) sync

build: ## Run dbt build, validate the semantic layer and publish the Iceberg marts
	$(RUN) build

break: ## Re-introduce a trap (TRAP=T1 or T4) so a named dbt test fails; `make build` restores it
	$(RUN) build python -m contextloop.cli build --break $(TRAP)

lakehouse: ## Start Trino and compare the same Iceberg query in DuckDB and Trino
	$(COMPOSE) --profile lakehouse up -d --wait trino
	$(RUN) build python -m contextloop.cli lakehouse

eval: ## Score both agents (live when CONTEXTLOOP_MODE=live and a key is set; otherwise re-scores the recordings)
	$(RUN) eval
	@$(MAKE) --no-print-directory export

record: ## Run both agents live (3 runs each) and save recordings and the report into the repo (needs ANTHROPIC_API_KEY)
	$(RUN) eval python -m contextloop.cli record
	@$(MAKE) --no-print-directory export

ask: ## Ask one golden question live and watch the tool calls, e.g. make ask AGENT=governed Q=G1
	$(RUN) eval python -m contextloop.cli ask $(AGENT) $(Q)

export: ## Copy recordings/ and reports/ from the data volume into the repository
	$(RUN) -T --no-deps eval python -m contextloop.cli export | tar -xf - -C .
	@echo "Copied recordings/ and reports/ into the repository."

demo: up data sync build ## The one command before a presentation: up, data, sync, build, then open the app
	@echo "ContextLoop is ready: http://127.0.0.1:8501"
	@command -v open >/dev/null && open http://127.0.0.1:8501 || true

test: ## Run the test suite inside the image (needs `make up` for the stack tests)
	$(RUN) test

sdk-debug: ## Run the SAP connector with Fivetran's own local tester (`fivetran debug`)
	$(RUN) sync python -m contextloop.cli sdk-debug

pitch-video: ## Render the narrated pitch video for the Architecture page (on the Mac host: say, ffmpeg; Playwright goes in .venv)
	@test -x .venv/bin/python || (python3 -m venv .venv && .venv/bin/pip install -q playwright)
	@.venv/bin/python -c "import playwright" 2>/dev/null || .venv/bin/pip install -q playwright
	.venv/bin/python scripts/render_pitch_video.py $(ARGS)

media-infra: ## Create the S3 bucket and CloudFront distribution that host the pitch video (once; Terraform, needs AWS sign-in)
	terraform -chdir=infra/media init -input=false
	terraform -chdir=infra/media apply

publish-pitch: ## Upload the rendered pitch video and its public watch page to S3/CloudFront, and link it on the Architecture page
	python3 scripts/publish_pitch.py
