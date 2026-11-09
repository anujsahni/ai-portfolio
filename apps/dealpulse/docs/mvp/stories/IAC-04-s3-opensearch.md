# IAC-04 — S3 data bucket and OpenSearch domain (Terraform)

**Type:** Infrastructure as code  
**Priority:** P0  
**Estimate:** 5–8 hours  
**Story points:** 5 (bucket layout, OpenSearch domain with IAM access policy, index and hybrid search pipeline, early risk check)  

## User story

As the demo owner, I want the data bucket and a small OpenSearch domain created by Terraform, with vector and hybrid search confirmed working, so that data loading and retrieval stories have somewhere safe to write and read.

## Scope

- **S3 data bucket** (`infra/stack/s3.tf`): versioning, SSE-S3, all public access blocked, TLS-only policy, `force_destroy` only through IAC-07's destroy path. Prefixes: `crm-snapshot/`, `training/`, `knowledge/`, `models/`, `reports/`. Lifecycle rule expires old noncurrent versions after 30 days.
- **OpenSearch Service domain** (`infra/stack/opensearch.tf`):
  - one `t3.small.search` data node, 10 GB gp3, latest OpenSearch 2.x engine version supported for this instance type (confirm at implementation);
  - HTTPS required, TLS 1.2+, node-to-node encryption; encryption at rest if the instance type supports it (record the result);
  - **public endpoint with an IAM-based domain access policy** that allows only `dealpulse-run` (`_search` on the index) and `dealpulse-ingest` (index read/write) and the operator role for setup; no anonymous access;
  - CloudWatch error logs.
- **Index and search pipeline**, created by an idempotent script (`scripts/setup_opensearch.py`, run by `make apply` after Terraform) because Terraform doesn't manage index mappings well:
  - index `deal_passages` with fields from [design §5](../../design.md#5-retrieval-opensearch--titan): `passage_id`, `text`, `doc_type`, `account_id`, `opportunity_id`, `date`, `author_role`, `checksum`, `embedding` (`knn_vector`, 1,024 dims, HNSW, cosine);
  - a search pipeline with a normalization processor that combines keyword and vector scores (weights in config).
- **Early risk check:** index three sample documents and run one hybrid query to prove `t3.small.search` supports vector + hybrid search. If it doesn't, stop and choose the smallest instance type that does before continuing.

**Out of scope:** OpenSearch Serverless, VPC-only domains, fine-grained access control with internal users, UltraWarm, snapshots to S3 and dashboards access.

## Acceptance criteria

- [x] `make apply` creates the bucket and domain; a second plan shows no changes. Domain creation time is documented (it can take 15+ minutes).
- [x] An unsigned request to the domain is refused; a signed request as `dealpulse-run` can `_search` but gets 403 on indexing; `dealpulse-ingest` can index.
- [x] `scripts/setup_opensearch.py` creates the index and pipeline, and running it again changes nothing.
- [x] The risk check returns hybrid results for a sample query, and the result is recorded in this story.
- [x] The bucket rejects public access and non-TLS requests.
- [x] Guide 03 (OpenSearch) explains the domain, the access policy, the index fields and how to inspect them.

## Dependencies and deliverables

**Dependencies:** IAC-03.  
**Deliverables:** `s3.tf`, `opensearch.tf`, `scripts/setup_opensearch.py`, outputs (bucket name, domain endpoint), guide 03 (first part).

## Completion evidence

Output of the access checks and the hybrid-query risk check, and the domain's engine version and instance type.

## Completion record (2026-11-09) ✅ Done

- **Applied by the owner** with `make apply RISK_CHECK=1`: 10 resources. A second `make plan` showed **No changes**.
- **Domain** `dealpulse-y34c`: OpenSearch **3.7** (newest offered, supports `t3.small.search`), 1 × `t3.small.search`, 10 GB gp3, **encryption at rest on** (supported on this instance type), node-to-node encryption, HTTPS only with TLS 1.2+ (`Policy-Min-TLS-1-2-PFS-2023-10`), error logs to CloudWatch (14 days). AWS price list: **$0.036/hour**. Creation took **about 19 minutes** (11:24 → 11:42); the last stage, "Dynamic update", was the slowest.
- **Access policy** repeats each role's limits (app: `_search` on `deal_passages` only; ingest and operator: the domain), because a same-account domain policy can grant on its own.
- **Index** `deal_passages` (strict mapping, 1 shard, 0 replicas, 1,024-dim `knn_vector`, HNSW + Lucene + cosine) and **search pipeline** `deal_passages-hybrid` (min-max normalisation, 0.4 keyword / 0.6 vector), created by `scripts/setup_opensearch.py` as the ingest role. Re-run: both `unchanged`.
- **Risk check passed:** 4 Titan-embedded notes from two deals; "Has the budget been approved by finance?" filtered to OPP-A returned `['A1', 'A2']` in 121 ms. The other deal's budget note never appeared, and the right note ranked first. `t3.small.search` is confirmed for vector + hybrid search; no instance change needed.
- **Access checks** (`scripts/verify_opensearch.py`, part of `make verify`): **8/8 pass**: unsigned 403; app can search (200) but can't write (403) or delete the index (403); ingest can write (200); index health green; data bucket refuses plain HTTP (403) and blocks public access.
- **Data bucket** `dealpulse-y34c-data-…`: versioning, SSE-S3, public access blocked, TLS-only policy, noncurrent versions expire after 30 days, `build-src/` uploads after 14 days.
- **Tests:** 5 offline tests on the index definition and query builder, including "the hybrid query refuses to run without a scope filter" (`make test`: 7 passed).
- [Guide 03](../guides/03-opensearch-knowledge-base.md): domain, access table, index fields, hybrid search, how to inspect, Managed vs. Serverless comparison, troubleshooting.

**Notes for later stories:**
- `dealpulse/search_index.py` holds the index body, pipeline and `hybrid_query()`; MVP-06 and MVP-07 should use it rather than redefine them.
- `dealpulse/awsenv.py` gives `role_session("run" | "ingest")` for running as the app's roles locally.
- Billing for the domain started at creation. `make destroy` (IAC-07) is the way to stop it.
