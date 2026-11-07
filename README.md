# GCP AI Portfolio

An independent portfolio repository for Google Cloud and AI application demos. This is not an official Google project.

## Apps

| App | Description | Status |
|---|---|---|
| [WeekendWise](apps/weekendwise/README.md) | Grounded AI weekend trip planner using LangGraph, Gemini and embeddings on Vertex AI, Firestore vector search, and Cloud Run. | Implemented demo; cloud resources are configured/deployed per app instructions. |

Each app is self-contained: application code, data, tests, scripts, documentation, infrastructure, build configuration, dependencies, and local environment live inside its directory. Shared root files are limited to portfolio navigation, repository-wide ignore rules, and optional command shortcuts.

## Local development

Open an app’s README for setup details. Optional root-level shortcuts delegate into the app directory:

- `make help` — list portfolio shortcuts
- `make weekendwise-test` — run that app’s offline tests
- `make weekendwise-mockups` — serve its static UI preview on loopback

For app-specific commands, run Make from that app’s directory, e.g. `make test` from `apps/weekendwise/`.
