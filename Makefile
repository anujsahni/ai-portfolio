.DEFAULT_GOAL := help
.PHONY: help weekendwise weekendwise-test weekendwise-mockups weekendwise-run \
	weekendwise-scenarios weekendwise-evaluate weekendwise-seed weekendwise-help \
	test mockups run scenarios evaluate seed \
	dealpulse dealpulse-help dealpulse-test dealpulse-verify dealpulse-architecture

APP := apps/weekendwise
DP  := apps/dealpulse

help: ## Show portfolio-level shortcuts
	@printf '%s\n' 'AI Portfolio shortcuts:' \
	  '  make weekendwise-test       Run WeekendWise offline tests' \
	  '  make weekendwise-mockups    Serve the local WeekendWise UI preview' \
	  '  make weekendwise-run        Run the WeekendWise backend locally' \
	  '  make weekendwise-scenarios  Run WeekendWise scripted scenarios' \
	  '  make weekendwise-evaluate   Run the WeekendWise evaluation set' \
	  '  make weekendwise-seed       Seed WeekendWise Firestore data (uses Google Cloud)' \
	  '  make weekendwise-help       Show all WeekendWise commands' \
	  '  make test / scenarios / mockups   Compatibility shortcuts for WeekendWise' \
	  '' \
	  '  make dealpulse-test         Run DealPulse offline tests' \
	  '  make dealpulse-verify       Check DealPulse AWS resources for drift and permissions (reads only)' \
	  '  make dealpulse-architecture Render the DealPulse architecture diagram for its README' \
	  '  make dealpulse-help         Show all DealPulse commands'

weekendwise: weekendwise-help ## Show commands for the WeekendWise app

weekendwise-help: ## Show all WeekendWise commands
	$(MAKE) -C $(APP) help

weekendwise-test: ## Run WeekendWise offline tests
	$(MAKE) -C $(APP) test

weekendwise-mockups: ## Serve WeekendWise UI mockups locally
	$(MAKE) -C $(APP) mockups

weekendwise-run: ## Run WeekendWise locally (requires app configuration)
	$(MAKE) -C $(APP) run

weekendwise-scenarios: ## Run WeekendWise live scripted scenarios
	$(MAKE) -C $(APP) scenarios

weekendwise-evaluate: ## Run WeekendWise live evaluation set
	$(MAKE) -C $(APP) evaluate

weekendwise-seed: ## Seed WeekendWise Firestore data
	$(MAKE) -C $(APP) seed

# Compatibility shortcuts for the original single-app repository commands.
test: weekendwise-test ## Run the default app's offline tests

mockups: weekendwise-mockups ## Serve the default app's local UI preview

run: weekendwise-run ## Run the default app locally

scenarios: weekendwise-scenarios ## Run the default app's live scenarios

evaluate: weekendwise-evaluate ## Run the default app's live evaluation

seed: weekendwise-seed ## Seed the default app's Firestore data

# ---------------------------------------------------------------- DealPulse (AWS)

dealpulse: dealpulse-help ## Show commands for the DealPulse app

dealpulse-help: ## Show all DealPulse commands
	$(MAKE) -C $(DP) help

dealpulse-test: ## Run DealPulse offline tests
	$(MAKE) -C $(DP) test

dealpulse-verify: ## Check DealPulse AWS resources for drift and permissions (reads only)
	$(MAKE) -C $(DP) verify

dealpulse-architecture: ## Render the DealPulse architecture diagram to its README image
	$(MAKE) -C $(DP) architecture
