# MVP-03 — Synthetic Salesforce data generator (`make data`)

**Type:** Data  
**Priority:** P0  
**Estimate:** 6–10 hours  
**Story points:** 5 (realistic relational data, notes that match hidden drivers, point-in-time rows and test traps)  

## User story

As the demo owner, I want believable, Salesforce-shaped data with a known hidden truth so that the model, retrieval and briefs can be built and checked without any real customer data.

## Scope

- `data/generator/` writes, from one seed, the objects and volumes in [design §3](../../design.md#3-synthetic-data) for the fictional vendor **Altura Analytics**: `Account`, `User` (6 reps, 2 managers in 2 teams), `Opportunity` (~2,400 closed over 8 quarters + ~60 open this quarter), `OpportunityHistory`, `Contact`, `OpportunityContactRole`, `Task`/`Event` with `Description`, `Case`.
- Use standard Salesforce field API names and the default stages and probabilities (Prospecting 10% … Negotiation/Review 75%), plus custom fields `Discount_Pct__c`, `Competitor__c`, `Product_Line__c`.
- **Hidden outcome rule:** a logistic function of a few drivers (recent activity, executive engagement, close-date pushes, discount depth, competitor present, open severe cases) plus noise decides each closed deal's outcome. The rule and its weights are saved to `data/generator/hidden_rule.json` for evaluation only; the app never reads it.
- **Notes that match the numbers:** about 700 call, email and meeting notes on open deals, written from templates with variation so they reflect each deal's drivers (no CFO meeting is described for a deal with no executive engagement).
- **Shared documents** in `data/playbooks/`: 8 playbook sections, 4 pricing and discount policy sections (20% needs VP approval, 30% needs CFO approval), about 30 win/loss reviews.
- **Point-in-time training rows:** for each closed deal, one row per week it was open, with features as of that week and the final outcome as label (~12,000 rows) in `training/`.
- **Test traps** (listed in `data/generator/traps.json`): the prompt-injection email, the look-alike accounts *Northbeam Logistics* / *Northbeam Logistics Group*, a deal asking for a 35% discount, a deal with almost no notes.
- `make data` writes everything locally to `data/out/` and uploads to S3 (`crm-snapshot/`, `training/`, `knowledge/`) as the operator. Re-running with the same seed produces identical files.

**Out of scope:** LLM-generated notes (templates keep it free and reproducible), real company or person names, multi-currency and Salesforce metadata such as page layouts.

## Acceptance criteria

- [x] `make data` produces all objects with the target volumes (±10%) and uploads them to the right S3 prefixes.
- [x] Same seed → byte-identical output (checksums compared in a test); a different seed → different data.
- [x] Referential integrity holds: every foreign key resolves; every open deal has an owner, an account and at least one contact role.
- [x] Historical win rate and stage mix look plausible (e.g. overall win rate 20–35%), and the report prints them.
- [x] Notes agree with drivers for a sampled check of 20 deals (automated rule checks).
- [x] Training rows contain only information known at the snapshot date (unit test: no row uses a stage, amount or activity dated after its snapshot).
- [x] All four traps exist and are listed in `traps.json`.
- [x] No real company, person, email domain or phone number is used (emails use `example.com`, phones use reserved 555 numbers).

## Dependencies and deliverables

**Dependencies:** IAC-04 (the bucket) for the upload step; generation itself runs offline.  
**Deliverables:** `data/generator/`, `data/playbooks/`, `make data`, unit tests, a data summary report in `docs/mvp/evidence/MVP-03-data-summary.md`.

## Completion evidence

The data summary report: counts per object, win rate by stage and segment, and the trap list.

## Completion record (2026-11-09) ✅ Done

Full report: [MVP-03 data summary](../evidence/MVP-03-data-summary.md).

- **`make data`** generates everything in under a second, checks it, writes the report and uploads to `s3://<prefix>-data-<account>/` (`crm-snapshot/` 11 files, `training/` 1, `knowledge/` 42; about 15.5 MB). `LOCAL=1` skips the upload; `SEED=n` picks another seed.
- **Volumes (seed 1), all within ±10% of design:** 400 accounts, 8 users, 1,593 contacts, 2,460 opportunities (2,400 closed + 60 open on 40 accounts), ~15,500 history rows, ~6,470 contact roles, 300 cases, 678 notes on open deals, 12,886 training rows. Plus ~36,000 tasks/events in total and ~1,900 field-history rows.
- **Outcomes look real:** win rate 31.2% (28–32% across 12 seeds). Executive engagement 41.7% vs 17.9% win rate; champion 36.7% vs 20.6%; competitor present 22.3% vs 34.4%. Lost deals spread across all stages.
- **Point-in-time history:** `OpportunityHistory` records stage, close-date and forecast-category changes; `OpportunityFieldHistory` records discount and competitor. Training rows snapshot each closed deal every 18 days while it was open.
- **Shared feature code** `dealpulse/features.py` (35 columns) is built here because training rows need it; MVP-04 reuses it. It reads only history dated on or before the snapshot. Excluded on purpose: owner, rep win rate, Probability, ForecastCategoryName, free text.
- **Knowledge:** 8 playbook and 4 pricing-policy sections, hand-written in `data/playbooks/`; 30 anonymised win/loss reviews generated from closed deals (no company names or IDs, so they're safe to cite for any deal).
- **Scenarios and traps** (`data/generator/scenarios.json` → `data/out/eval/traps.json`): S1 Commit with no executive, S2 healthy Best Case, S3 35% discount, S4 two notes only, S5 prompt-injection email, S6a/S6b look-alike Northbeam accounts with opposite budget stories.
- **Checks (all pass):** referential integrity; notes agree with each open deal's drivers (no executive meeting or approved budget described without executive engagement, no competitor named unless in the deal, discount figures match, slip notes ≤ slips); emails on `example.com`, phones in the reserved 555-01xx range; all traps present.
- **Tests:** 12 new offline tests (19 total, `make test`), including same-seed → identical files, the writer refusing to overwrite a folder it didn't create, and **no leakage**: features rebuilt from only the records that existed on each snapshot date are identical, and flipping a deal's final outcome doesn't change its features. A full-scale re-run was byte-identical (58 files).
- **Access in the real bucket:** the app role can read `crm-snapshot/` but gets 403 on `training/` and `knowledge/` (it searches knowledge through OpenSearch).

**Decisions and deviations:**
- Generator code lives in `dealpulse/datagen/` (importable and testable); its inputs (`hidden_rule.json`, `scenarios.json`) live in `data/generator/`. Generated output, including the hidden truth and resolved trap IDs, goes to `data/out/` (git-ignored, reproducible).
- Hidden-rule intercept set to −1.4 for a ~30% win rate; snapshots every 18 days (not weekly) to land near the ~12,000-row target.
- **Default seed is 1, not 7.** Notes on open deals vary with the seed (535–812 across seeds 1–12, average 677). Seed 1 sits near the average; the spread is printed in the report.
- Forecast-category changes are recorded in `OpportunityHistory`, as Salesforce does. This also keeps an open Commit deal's history consistent with its current category.
- Account names are built from invented syllables (e.g. "Kelvale Freight") to avoid real company names; scenario names are fixed and fictional. Any resemblance to a real organisation is coincidental.
- About 12% of open-deal notes repeat a wording already used on the same deal (long deals use up a topic's variants). Acceptable for synthetic data; retrieval should still work because the deal facts differ.
