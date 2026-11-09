# 03 — OpenSearch and the knowledge base

How DealPulse stores and searches call notes, playbook sections and win/loss reviews. Terraform creates the domain (IAC-04); `make apply` then creates the index and search pipeline; `make seed` loads the passages (MVP-06, *coming*). Use the console only to look, never to change settings by hand.

## What was created

| Resource | Name | Notes |
|---|---|---|
| OpenSearch domain | `<prefix>` (e.g. `dealpulse-y34c`) | OpenSearch 3.7, one `t3.small.search` node, 10 GB gp3, encryption at rest, node-to-node encryption, HTTPS only (TLS 1.2+). ~$0.036/hour, billed until destroyed. Creation took about 19 minutes. |
| Error logs | `/aws/opensearch/<prefix>/errors` | CloudWatch, 14-day retention |
| Index | `deal_passages` | 1 shard, 0 replicas (single node, so health is green) |
| Search pipeline | `deal_passages-hybrid` | Blends keyword and vector scores (below) |
| Data bucket | `<prefix>-data-<account>` | Versioned, encrypted, public access blocked, HTTPS only. Prefixes: `crm-snapshot/`, `training/`, `knowledge/`, `models/`, `reports/`, `build-src/` |

## Who can do what

Access is by **IAM only**: every request must be signed by an allowed role. There are no usernames or passwords, and unsigned requests get `403`.

| Who | Can | Can't |
|---|---|---|
| App (`<prefix>-run`) | Search `deal_passages` | Write, delete or change anything |
| Ingest (`<prefix>-ingest`) | Read and write the index, create the pipeline | Call Claude, write to S3 |
| Operator (you) | Everything on the domain (setup, inspection) | — |

Inside one AWS account, a domain's access policy can grant permissions even when a role's own policy doesn't. So the domain policy repeats the app's "search only" limit instead of granting it the whole domain. `make verify` proves it with real requests:

```text
✓ unsigned request refused (HTTP 403)
✓ app role can search (HTTP 200)
✓ app role can't write a document (HTTP 403)
✓ app role can't delete the index (HTTP 403)
✓ ingest role can write (HTTP 200)
✓ index health green
✓ data bucket refuses plain HTTP (HTTP 403)
✓ data bucket blocks all public access
```

## The index

Each document is one **passage** of about 300–500 tokens. The field list lives in `dealpulse/search_index.py`; the index rejects any other field (`dynamic: strict`).

| Field | Type | Meaning |
|---|---|---|
| `passage_id` | keyword | Stable ID, cited in briefs |
| `text`, `title` | text (English analyzer) | The passage, for keyword search |
| `doc_type` | keyword | `call_note`, `email`, `meeting`, `playbook`, `policy`, `win_loss` |
| `account_id`, `opportunity_id` | keyword | Set for deal notes; empty for shared documents |
| `date`, `author_role` | date, keyword | When and by whom (role, not name) |
| `checksum`, `active` | keyword, boolean | Lets `make seed` skip unchanged passages and retire removed ones |
| `embedding` | knn_vector, 1,024 dims | Titan V2 vector; HNSW graph, Lucene engine, cosine similarity |

The **Lucene engine** was chosen because it filters *while* it searches the vector graph. DealPulse always filters to one deal, and filtering afterwards could return too few results.

## Hybrid search

A query runs twice: once as keyword search (good for names like "Northbeam" or "SOC 2"), once as vector search (good for meaning: "budget not approved" ≈ "no funding yet"). The pipeline `deal_passages-hybrid` rescales both score lists to 0–1 (min-max) and blends them **40% keyword / 60% vector**. Both halves carry the **same filter**, and the query builder refuses to run without one.

`make apply RISK_CHECK=1` (or `python scripts/setup_opensearch.py --risk-check`) proves this works on the domain. It embeds 4 notes from two deals, asks "Has the budget been approved by finance?" filtered to one deal, and checks that only that deal's notes come back, budget note first:

```text
hybrid query (filter OPP-A) → ['A1', 'A2'] in 121 ms
✓ results only from the filtered deal (B1 also mentions a budget and must not appear)
✓ the budget note ranks first
```

## Inspecting it

```bash
make verify                                              # access checks + index health
.venv/bin/python scripts/setup_opensearch.py             # shows index/pipeline: created / unchanged / DIFFERS
aws opensearch describe-domain --domain-name <prefix>    # domain settings
```

In the console: **Amazon OpenSearch Service → Domains → `<prefix>`** shows health, settings and the access policy. OpenSearch Dashboards isn't set up, because IAM-only access doesn't give a browser login.

If you change the index fields in code, `setup_opensearch.py` reports `DIFFERS` instead of changing a live index. Recreate it with `--recreate-index`, which deletes all passages, then run `make seed` again.

## Managed domain vs. OpenSearch Serverless

| | Managed domain (chosen) | Serverless vector collection |
|---|---|---|
| Sizing | You pick the node (`t3.small.search`) | AWS scales compute units (OCUs) automatically |
| Idle cost (us-east-1) | ~$27/month | ~$175/month (dev/test, ~1 OCU minimum at $0.24/OCU-hour); ~$350 with redundancy |
| Scales to zero | No | No (minimum OCUs bill around the clock) |
| Upgrades and patching | Yours (Terraform `engine_version`) | AWS's |
| Fits DealPulse (~1,000 passages, few users) | Yes, with room to spare | Yes, but pays for capacity it won't use |

Serverless is the scale-up path for heavy or spiky search. Switching means replacing `opensearch.tf` with a collection plus encryption, network and data-access policies; signing requests for service `aoss` instead of `es`; and first confirming that the hybrid pipeline and filtered Lucene vector search are supported there.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `make apply` sits on "Still creating…" for 15–30 min | Normal for a new domain; the last stage ("Dynamic update") is slowest | Wait; don't interrupt. Check with `aws opensearch describe-domain-change-progress --domain-name <prefix>` |
| `403` for a signed request | That role isn't allowed that action | Expected for the app writing; otherwise compare with the table above |
| Index health `yellow` | Replicas > 0 on a single node | The index sets 0 replicas; recreate if it was made by hand |
| `DIFFERS` from the setup script | Index fields changed in code | `--recreate-index`, then `make seed` |
