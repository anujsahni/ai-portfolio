# CL-01 — Demo narrative, golden question and talk track

**Phase:** 0 · Foundation  
**Type:** Story and design  
**Priority:** P0  
**Estimate:** 2–4 hours  
**Story points:** 3 (shapes every later story; must be agreed before data is generated)  
**Target day:** Wed 11 Nov

## User story

As the presenter, I want one agreed story, with a single headline question, a known right answer and a scripted path through five acts, so that every later story builds toward the same ten-minute demo.

## Scope

- `docs/demo/narrative.md`: the customer (**Northstar Industrial**, fictional), the four source systems, the persona asking (the COO) and the persona presenting (a Fivetran sales engineering specialist).
- The **headline question**: *"Which of our strategic accounts are at risk because of late shipments, and what should the account teams do this week?"*
- **Business definitions** written in plain English; CL-06 and CL-07 implement exactly these:
  - *Strategic account*: Salesforce `Account.Tier__c = 'Strategic'` **as of the end of the period** (history mode matters).
  - *On time*: the carrier's `delivered_at` is on or before the SAP requested delivery date (`VBAK.VDATU`); cancelled (soft-deleted) deliveries are excluded.
  - *On-time delivery rate (90 days)*: on-time deliveries divided by all non-cancelled deliveries shipped in the last 90 days, per account.
  - *Net revenue*: billed amount (`VBRK`/`VBRP`) minus credit memos, converted to USD at the monthly rate.
  - *At risk*: strategic, on-time rate below 85%, **and** either 2 or more open shipping-related tickets or a renewal opportunity closing in the next 120 days.
- **Six golden questions**, including the headline question, each with the kind of answer expected (a list, a number, a yes or no). The generator (CL-03) computes the expected values.
- **Talk track** for each act: what is on screen, the one sentence to say, the one thing the audience should remember, and the specialty it shows. Two lengths: 10 minutes and 20 minutes.
- **Discovery framing:** three questions a sales engineer would ask a real customer before this demo (sources, AI plans, current trust issues), so the demo is presented as a proof of value, not a feature tour.

**Out of scope:** slides; the Q&A sheet (CL-16).

## Acceptance criteria

- [x] `docs/demo/narrative.md` exists with the customer, personas, headline question and every definition above.
- [x] Every definition names the exact source fields it uses, so CL-03 and CL-06 can implement it without guessing.
- [x] Six golden questions are listed with answer types; at least three of them fail when a specific trap (T1–T6) is ignored, and the mapping is written down.
- [x] Talk track for all five acts plus the POV scorecard, in a 10-minute and a 20-minute version, with timings that add up.
- [x] Each act names the Fivetran or dbt capability shown and the specialty it represents.
- [x] The owner has read and agreed the narrative (recorded in the completion record).

## Dependencies and deliverables

**Dependencies:** none.  
**Deliverables:** `docs/demo/narrative.md`, `docs/demo/talk-track.md`.

## Completion evidence

Links to both documents and the owner's sign-off.
