#!/usr/bin/env python3
"""IAC-07: list anything DealPulse left behind (reads only). Exits 1 if something remains.

    python scripts/verify_destroyed.py          # after make destroy: the stack must be gone
    python scripts/verify_destroyed.py --all    # after make destroy-all: the state bucket and budget too

Checks each service directly by the name prefix (tag-based search can lag behind deletions), then
lists anything still carrying the tags app=dealpulse and name_prefix=<prefix> as a cross-check.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

sys.path.insert(0, str(Path(__file__).resolve().parent))
from predestroy import name_prefix, region  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="also expect the bootstrap (state bucket, budget) to be gone")
    args = parser.parse_args()
    prefix = name_prefix()
    s = boto3.Session(region_name=region())
    account = s.client("sts").get_caller_identity()["Account"]
    left: list[str] = []
    notes: list[str] = []

    def bucket(name: str) -> bool:
        try:
            s.client("s3").head_bucket(Bucket=name)
            return True
        except ClientError:
            return False

    # Stack
    try:
        d = s.client("opensearch").describe_domain(DomainName=prefix)["DomainStatus"]
        (notes if d.get("Deleted") else left).append(
            f"OpenSearch domain {prefix}" + (" (being deleted; billing has stopped)" if d.get("Deleted") else ""))
    except ClientError:
        pass
    if bucket(f"{prefix}-data-{account}"):
        left.append(f"S3 bucket {prefix}-data-{account}")
    sm = s.client("sagemaker")
    left += [f"SageMaker endpoint {e['EndpointName']}" for e in sm.list_endpoints(NameContains=prefix)["Endpoints"]]
    left += [f"SageMaker endpoint config {e['EndpointConfigName']}" for e in sm.list_endpoint_configs(NameContains=prefix)["EndpointConfigs"]]
    left += [f"SageMaker model {m['ModelName']}" for m in sm.list_models(NameContains=prefix)["Models"]]
    left += [f"Model registry {g['ModelPackageGroupName']}" for g in sm.list_model_package_groups(NameContains=prefix)["ModelPackageGroupSummaryList"]]
    left += [f"Bedrock guardrail {g['name']}" for g in s.client("bedrock").list_guardrails()["guardrails"] if g["name"].startswith(prefix)]
    iam = s.client("iam")
    for page in iam.get_paginator("list_roles").paginate():
        left += [f"IAM role {r['RoleName']}" for r in page["Roles"] if r["RoleName"].startswith(f"{prefix}-")]
    ec2 = s.client("ec2")
    left += [f"VPC {v['VpcId']}" for v in ec2.describe_vpcs(Filters=[{"Name": "tag:name_prefix", "Values": [prefix]}])["Vpcs"]]
    logs = s.client("logs")
    for lg_prefix in (f"/{prefix}/", f"/aws/opensearch/{prefix}", f"/aws/codebuild/{prefix}"):
        left += [f"Log group {g['logGroupName']}" for g in logs.describe_log_groups(logGroupNamePrefix=lg_prefix)["logGroups"]]
    try:
        streams = logs.describe_log_streams(logGroupName="/aws/sagemaker/TrainingJobs", logStreamNamePrefix=f"{prefix}-win-")["logStreams"]
        left += [f"Training log stream {st['logStreamName']}" for st in streams]
    except ClientError:
        pass
    left += [f"ECR repository {r['repositoryName']}" for r in s.client("ecr").describe_repositories()["repositories"]
             if r["repositoryName"].startswith(prefix)]
    left += [f"ECS cluster {c}" for c in s.client("ecs").list_clusters()["clusterArns"] if c.endswith(f"/{prefix}")]

    # Bootstrap (expected to remain after make destroy)
    boot = []
    if bucket(f"{prefix}-tfstate-{account}"):
        boot.append(f"S3 state bucket {prefix}-tfstate-{account}")
    try:
        s.client("budgets").describe_budget(AccountId=account, BudgetName=f"{prefix}-monthly")
        boot.append(f"Budget {prefix}-monthly")
    except ClientError:
        pass
    if args.all:
        left += boot
    else:
        notes += [f"{b} (kept on purpose by make destroy)" for b in boot]

    tagged = s.client("resourcegroupstaggingapi").get_resources(
        TagFilters=[{"Key": "app", "Values": ["dealpulse"]}, {"Key": "name_prefix", "Values": [prefix]}])["ResourceTagMappingList"]
    # SageMaker keeps free history records (training-job record, lineage contexts/actions, trial components)
    # after the resources are gone; the training-job record can't be deleted at all. Everything else in tag
    # search is usually a deleted resource the index hasn't caught up with yet.
    history_types = ("training-job/", "experiment-trial-component/", "context/", "action/", "artifact/")
    names = [t["ResourceARN"].split(":")[-1] for t in tagged]
    history = [n for n in names if n.startswith(history_types)]
    stale = [n for n in names if not n.startswith(history_types)]
    if history:
        notes.append(f"{len(history)} SageMaker history record(s) (training-job record, lineage entries): free metadata, kept by AWS")
    if stale:
        notes.append(f"{len(stale)} item(s) still in tag search, usually already deleted (the index lags): "
                     + ", ".join(stale[:5]) + ("…" if len(stale) > 5 else ""))

    for item in left:
        print(f"✗ still exists: {item}")
    for item in notes:
        print(f"· {item}")
    if left:
        print(f"✗ {len(left)} DealPulse resource(s) remain")
        return 1
    print(f"✓ nothing left from {'DealPulse' if args.all else 'the DealPulse stack'} ({prefix})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
