#!/usr/bin/env python3
"""IAC-07: remove what DealPulse created outside Terraform, so `terraform destroy` can finish.

Run only by `make destroy` / `make destroy-all`, after the typed confirmation:
  - model versions in the <prefix>-win-model registry (made by make train; the group can't be deleted while it holds any)
  - DealPulse's training log streams in SageMaker's account-wide log group (the group itself is left alone)
  - CodeBuild log groups named /aws/codebuild/<prefix>* (IAC-06)
Everything here is irreversible. With --dry-run it only lists what it would remove.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

ROOT = Path(__file__).resolve().parents[1]


def name_prefix() -> str:
    text = (ROOT / "infra/bootstrap/terraform.tfvars").read_text()
    return re.search(r'^name_prefix\s*=\s*"([^"]+)"', text, re.M).group(1)


def region() -> str:
    text = (ROOT / "infra/bootstrap/terraform.tfvars").read_text()
    match = re.search(r'^region\s*=\s*"([^"]+)"', text, re.M)
    return match.group(1) if match else "us-east-1"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    prefix = name_prefix()
    session = boto3.Session(region_name=region())
    sm, logs = session.client("sagemaker"), session.client("logs")
    act = "would remove" if args.dry_run else "removed"
    count = 0

    # An endpoint whose creation failed exists in AWS but not in Terraform state, and would block
    # deleting its endpoint configuration. Remove it first (only when Terraform doesn't manage it).
    import subprocess
    state = subprocess.run(["terraform", f"-chdir={ROOT / 'infra/stack'}", "state", "list"],
                           capture_output=True, text=True).stdout.split()
    endpoint = f"{prefix}-win-model"
    if "aws_sagemaker_endpoint.win_model[0]" not in state:
        try:
            status = sm.describe_endpoint(EndpointName=endpoint)["EndpointStatus"]
            if not args.dry_run:
                sm.delete_endpoint(EndpointName=endpoint)
                sm.get_waiter("endpoint_deleted").wait(EndpointName=endpoint, WaiterConfig={"Delay": 10, "MaxAttempts": 60})
            print(f"  {act} endpoint {endpoint} ({status}; not tracked by Terraform)")
            count += 1
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "ValidationException":  # not found
                raise

    group = f"{prefix}-win-model"
    try:
        packages = sm.get_paginator("list_model_packages").paginate(ModelPackageGroupName=group)
        for page in packages:
            for pkg in page["ModelPackageSummaryList"]:
                if not args.dry_run:
                    sm.delete_model_package(ModelPackageName=pkg["ModelPackageArn"])
                print(f"  {act} model version {pkg['ModelPackageVersion']} ({pkg['ModelApprovalStatus']})")
                count += 1
    except ClientError as exc:
        if exc.response["Error"]["Code"] not in ("ValidationException", "ResourceNotFound"):
            raise

    try:
        streams = logs.get_paginator("describe_log_streams").paginate(
            logGroupName="/aws/sagemaker/TrainingJobs", logStreamNamePrefix=f"{prefix}-win-")
        for page in streams:
            for stream in page["logStreams"]:
                if not args.dry_run:
                    logs.delete_log_stream(logGroupName="/aws/sagemaker/TrainingJobs", logStreamName=stream["logStreamName"])
                print(f"  {act} training log stream {stream['logStreamName']}")
                count += 1
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ResourceNotFoundException":
            raise

    for page in logs.get_paginator("describe_log_groups").paginate(logGroupNamePrefix=f"/aws/codebuild/{prefix}"):
        for lg in page["logGroups"]:
            if not args.dry_run:
                logs.delete_log_group(logGroupName=lg["logGroupName"])
            print(f"  {act} log group {lg['logGroupName']}")
            count += 1

    print(f"✓ {count} item(s) outside Terraform {act if count else 'to remove: none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
