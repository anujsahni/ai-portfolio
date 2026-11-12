# CL-15 — Proof-of-value scorecard and specialist view

**Phase:** 5 · Activate and close  
**Type:** UI and sales engineering  
**Priority:** P1 (second on the cut line: fall back to a static version)  
**Estimate:** 3–4 hours  
**Story points:** 3 (mostly content, read from the evaluation and sync data)  
**Target day:** Sun 15 Nov

## User story

As a sales engineering leader, I want to see the demo as a proof of value, with success criteria, evidence, time to value, cost and owners, so that I can judge whether this customer is ready to buy and which specialists the deal needs.

## Scope

- A **POV scorecard** page after Act 5, framed as Northstar's proof of value:
  - **Success criteria** agreed with the customer (from CL-01), each with pass or fail and a link to its evidence in the app. For example: "Agent answers the headline question correctly: pass (6/6 vs 1/6 baseline)"; "SAP deliveries replicated incrementally with deletes: pass"; "One definition of on-time delivery used by BI and AI: pass".
  - **Time to value:** how long each phase took to build, from the completion records.
  - **Cost estimate:** MAR per connector per month from the sync log, with the assumptions stated, and a note that real pricing comes from Fivetran's pricing page or the account team.
  - **Specialist map:** which specialty owns each workstream (database and application replication, SAP, lakehouse, transformation, activation, AI and context engineering), the risks each found, and the open items before production.
  - **Path to production:** the "at a customer" column from the architecture page as a short checklist (connectivity, security review, dbt platform, Managed Data Lake destination, Activations).
- Read live from the evaluation report and `fivetran_log` where possible; the rest from a checked-in YAML file.

**Out of scope:** real pricing; CRM integration of the POV itself.

## Acceptance criteria

- [ ] Every success criterion links to a place in the app that proves it.
- [ ] Scores and MAR figures match the evaluation report and the sync log (test).
- [ ] The specialist map covers all six specialties named in the README.
- [ ] Cost figures are labelled as estimates with their assumptions.
- [ ] Fallback: a static Markdown version exists in `docs/demo/pov-scorecard.md` if the interactive page is cut.

## Dependencies and deliverables

**Dependencies:** CL-11, CL-12.  
**Deliverables:** the scorecard page, `docs/demo/pov.yaml`, the static fallback.

## Completion evidence

A screenshot of the scorecard.
