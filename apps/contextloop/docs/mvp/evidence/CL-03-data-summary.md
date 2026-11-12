# CL-03 completion record: synthetic source systems, hidden truth and traps

**Date:** 11 Nov 2026 · **Seed:** 20261106 · **As-of date:** 6 Nov 2026 · **Result:** all acceptance criteria met.

`make data` generated all four systems and seeded Postgres in **2.6 s** (target: under 30 s).

## Counts

| Object | Generated | Target (±10%) |
|---|---|---|
| SAP `KNA1` customers | 120 | 120 |
| SAP `VBAK` orders | 8,970 | ~9,000 |
| SAP `VBAP` order items | 26,919 | ~27,000 |
| SAP `LIKP` deliveries | 9,121 | ~9,500 |
| SAP `LIPS` delivery items | 26,161 | — |
| SAP `VBRK` billing documents | 9,044 | ~8,800 |
| SAP `VBRP` billing items | 25,452 | — |
| SAP `TCURR` monthly rates | 19 | — |
| Salesforce accounts (rows incl. history) | 134 accounts (138 rows) | ~135 |
| Salesforce opportunities | 393 | — |
| Zendesk tickets | 2,995 | ~3,000 |
| Carrier shipments / events | 9,121 / 44,450 | linked to every delivery |

## The hidden truth: 9 at-risk strategic accounts

| Account | On-time (90 d) | Late | Open shipping tickets | Renewal due | Next step |
|---|---|---|---|---|---|
| Tamwick Mining Inc | 61.5% | 10 of 26 | 3 | — | Escalate the open tickets with logistics… |
| Tamford Food Processing SA | 69.0% | 9 of 29 | 2 | — | Share the late-delivery list… |
| Sevland Utilities Inc | 70.4% | 8 of 27 | 1 | 2026-12-06 | Executive call before the renewal… |
| Galbury Steelworks SA | 72.7% | 6 of 22 | 4 | — | Escalate the open tickets… |
| Halbrook Fluid Systems | 76.0% | 6 of 25 | 3 (2 on the look-alike duplicate) | — | Escalate the open tickets… |
| Wesmore Energy Ltd | 76.7% | 7 of 30 | 2 | — | Share the late-delivery list… |
| Vornwick Utilities Inc *(promoted mid-window)* | 77.8% | 4 of 18 | 1 | 2026-12-21 | Executive call before the renewal… |
| Jormark Paper Mills SA | 80.0% | 4 of 20 | 3 | — | Escalate the open tickets… |
| Marmark HVAC Inc | 81.5% | 5 of 27 | 0 | 2027-01-20 | Executive call before the renewal… |

Scenario coverage: 9 at-risk strategic (≥ 7 required); an at-risk *non-strategic* account exists (excluded by the filter); a
strategic account with a low rate but no driver is not at risk; Vornwick was promoted mid-window and is at risk.

## Traps

| Trap | Planted |
|---|---|
| T1 | 310 deliveries cancelled (3.4%), kept as `D` change rows |
| T2 | 682 late deliveries whose planned goods-issue date was on time |
| T3 | 38.4% of orders in EUR |
| T4 | "Halbrook Fluid Systems" (mapped to SAP) and "Halbrook Fluid Systems GmbH" (not mapped) |
| T5 | Vornwick Utilities, Thalmark Marine, Velmere Pipeline Services promoted to Strategic; Quenmere Paper Mills demoted; all on 22 Sep 2026 |
| T6 | Zendesk held two days behind (flag on by default); 12 tickets from the last two days are not landed |

## Naive versus true answer for each golden question

Each cell shows the answer when one trap is ignored (computed by `contextloop/datagen/truth.py`; proved by `tests/test_datagen.py`).

| Q | Truth | Answer with one trap ignored |
|---|---|---|
| G1 at-risk list | 9 accounts | T1: 10 · T2: 0 · T4: 8 (Halbrook missed) · T5: 10 (demoted Quenmere included) |
| G2 strategic on-time rate | 86.1% | T1: 82.9% · T2: 97.3% · T5: 85.6% |
| G3 EMEA net revenue Q3 2026 | $5,789,489 | T3: $5,493,079 |
| G4 strategic accounts | 25 | T4: 26 · T5: 26 |
| G5 support data current? | No, 2 days behind | T6: "yes, current" |
| G6 open shipping tickets (strategic) | 28 | T4: 26 · T5: 31 |

## Other checks (tests/test_datagen.py)

Same seed gives byte-identical files (SHA-256 of every file); a different seed differs. Referential integrity holds for items,
deliveries, events and Salesforce mappings. Emails use `example.com`; phones are `555-01xx`. The truth code is plain Python and
shares no SQL with dbt.
