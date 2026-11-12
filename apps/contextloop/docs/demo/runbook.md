# ContextLoop demo runbook

For the presenter on the day. The step-by-step setup is in [getting-started.md](../getting-started.md); the words are in the [talk track](talk-track.md); likely questions are in the [Q&A sheet](qa.md).

## The night before (about 15 minutes)

1. `git pull` and confirm that `recordings/demo/` holds runs for both agents on G1 to G6, plus `governed/G1-t6off.json`.
2. Run `make images` on the network you will present from. It pulls the pinned images so the demo needs no downloads tomorrow.
3. Run `make clean && make demo && make lakehouse`. Expect the app at http://127.0.0.1:8501 in under five minutes.
4. Run `make test`: everything should pass. Run `make eval` and check that the replayed scores match the report in `reports/`.
5. Walk all five acts once in **Replay** mode, pressing every button. Then press **Reset the mock CRM** in Act 5.
6. For live mode, run `make ask AGENT=governed Q=G4`. It should answer 25 within a couple of minutes.
7. Close everything that might pop up or compete for memory: chat apps, notifications, backups, other Docker projects.

## Five minutes before

- [ ] `make ps`: every service is healthy, and Trino is too if you plan to show it.
- [ ] The app is open at 127.0.0.1:8501 on the home page, at 125% browser zoom for screen sharing.
- [ ] The sidebar shows **REPLAY**, unless you planned a live segment.
- [ ] The CRM is reset (Act 5 → **Reset the mock CRM**).
- [ ] Act 2's incremental sync hasn't been run yet. If it has, run `make clean && make demo` (about 1 minute) so the schema change shows live.
- [ ] A second tab has the architecture page (`contextloop/ui/architecture/index.html`) as a backup.
- [ ] The talk track is open on a second screen or printed.

## Resetting between runs

| What | How | Time |
|---|---|---|
| CRM writes and audit log | Act 5 → **Reset the mock CRM** | instant |
| Everything (data, sync history, Iceberg snapshots) | `make clean && make demo` | about 1 minute |
| Stale-Zendesk scenario after experimenting | `docker compose run --rm sync python -m contextloop.cli scenario t6-on` | seconds |

## If something fails

| Failure | What to do in front of the audience | Fix afterwards |
|---|---|---|
| Live agent is slow or errors | Switch the sidebar to **Replay**; say "this is the recorded, scored run of exactly this" | Check the key and network; `make logs` |
| `mcp-metrics`, `mcp-freshness` or `dbt-mcp` is down | Replay still works (it doesn't call them); carry on | `docker compose restart mcp-metrics` (or the service), then `make ps` |
| "Run incremental sync" or "Break it" hangs | Open **Go deeper** and talk through the code; move on | `docker compose restart app`, then `make sync` / `make build` |
| Trino panel errors | Show the DuckDB side and the snapshot history; say Trino is optional | `make lakehouse` |
| The app won't load | Use the architecture page in the second tab and the screenshots in `docs/images/guide/` | `docker compose restart app`, `make logs` |
| Laptop runs out of memory | Stop Trino: `docker compose stop trino` | Give Docker at least 8 GB |

## Rehearsal log

Record each timed rehearsal here (CL-16 needs two, each within 10% of the target length).

| Date | Version | Target | Actual | Cut or changed |
|---|---|---|---|---|
| | 10 minutes | 10:00 | | |
| | 20 minutes | 20:00 | | |
