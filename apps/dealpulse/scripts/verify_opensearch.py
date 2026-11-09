#!/usr/bin/env python3
"""IAC-04: prove who can do what on the OpenSearch domain and the data bucket (part of make verify).

Checks with real requests (no data is changed except one probe document that is deleted again):
  - an unsigned request is refused;
  - the app role (run) can search but not write;
  - the ingest role can write;
  - the data bucket rejects plain HTTP and blocks public access.
"""
from __future__ import annotations

import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dealpulse import search_index  # noqa: E402
from dealpulse.awsenv import operator_session, role_session, stack_outputs  # noqa: E402


def status_of(call) -> int:
    try:
        call()
        return 200
    except Exception as exc:
        return getattr(exc, "status_code", None) or 0


def main() -> int:
    out = stack_outputs()
    info, bucket = out["opensearch"], out["data_bucket"]
    endpoint, index = info["endpoint"], info["index"]
    results: list[tuple[bool, str]] = []

    domain = operator_session().client("opensearch").describe_domain(DomainName=info["domain"])["DomainStatus"]
    print(f"  domain {info['domain']}: {domain['EngineVersion']}, {domain['ClusterConfig']['InstanceType']} × "
          f"{domain['ClusterConfig']['InstanceCount']}, encryption at rest {domain['EncryptionAtRestOptions']['Enabled']}, "
          f"HTTPS only {domain['DomainEndpointOptions']['EnforceHTTPS']}")

    unsigned = requests.get(f"https://{endpoint}/", timeout=15).status_code
    results.append((unsigned == 403, f"unsigned request refused (HTTP {unsigned})"))

    run = search_index.client(role_session("run", session_name="verify"), endpoint)
    code = status_of(lambda: run.search(index=index, body={"size": 1, "query": {"match_all": {}}}))
    results.append((code == 200, f"app role can search (HTTP {code})"))
    code = status_of(lambda: run.index(index=index, id="verify-probe", body={"passage_id": "verify-probe"}))
    results.append((code == 403, f"app role can't write a document (HTTP {code})"))
    code = status_of(lambda: run.indices.delete(index=index))
    results.append((code == 403, f"app role can't delete the index (HTTP {code})"))

    ingest = search_index.client(role_session("ingest", session_name="verify"), endpoint)
    code = status_of(lambda: ingest.index(index=index, id="verify-probe", body={"passage_id": "verify-probe", "active": False}, refresh=True))
    results.append((code == 200, f"ingest role can write (HTTP {code})"))
    status_of(lambda: ingest.delete(index=index, id="verify-probe", refresh=True))

    health = ingest.cluster.health(index=index)["status"]
    results.append((health == "green", f"index health {health}"))

    plain = requests.get(f"http://{bucket}.s3.amazonaws.com/crm-snapshot/", timeout=15).status_code
    results.append((plain == 403, f"data bucket refuses plain HTTP (HTTP {plain})"))
    pab = operator_session().client("s3").get_public_access_block(Bucket=bucket)["PublicAccessBlockConfiguration"]
    results.append((all(pab.values()), "data bucket blocks all public access"))

    for ok, text in results:
        print(f"{'✓' if ok else '✗'} {text}")
    passed = sum(ok for ok, _ in results)
    print(f"{passed}/{len(results)} OpenSearch and bucket checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
