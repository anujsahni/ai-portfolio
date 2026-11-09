#!/usr/bin/env python3
"""IAC-03: prove each DealPulse role can do its job and nothing more.

Uses the IAM policy simulator (iam:SimulatePrincipalPolicy), which evaluates the roles' policies
without calling any service, so it's free and safe, and works before later stories create the
resources. Also checks that the app security group has no inbound rules and that no IAM users
belong to DealPulse.

Usage: python scripts/verify_iam.py   (reads names and ARNs from `terraform output` in infra/stack)
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parents[1]


def stack_outputs() -> dict:
    raw = subprocess.run(
        ["terraform", f"-chdir={ROOT / 'infra' / 'stack'}", "output", "-json"],
        check=True, capture_output=True, text=True,
    ).stdout
    return {k: v["value"] for k, v in json.loads(raw).items()}


def build_checks(out: dict, account: str) -> list[tuple[str, str, str, str, bool]]:
    """(role, description, action, resource, expected_allowed)"""
    region, n, m = out["region"], out["names"], out["models"]
    bucket = f"arn:aws:s3:::{n['bucket']}"
    domain = f"arn:aws:es:{region}:{account}:domain/{n['domain']}"
    index = f"{domain}/{n['index']}"
    endpoint = f"arn:aws:sagemaker:{region}:{account}:endpoint/{n['endpoint']}"
    profile = f"arn:aws:bedrock:{region}:{account}:inference-profile/{m['claude_inference_profile']}"
    claude = f"arn:aws:bedrock:us-east-2::foundation-model/{m['claude_model_id']}"  # a region the US profile routes to
    titan = f"arn:aws:bedrock:{region}::foundation-model/{m['titan_model_id']}"
    sonnet = f"arn:aws:bedrock:{region}::foundation-model/anthropic.claude-sonnet-5-5"
    repo = f"arn:aws:ecr:{region}:{account}:repository/{n['ecr_repo']}"
    return [
        # run: the app
        ("run", "call Claude through the inference profile", "bedrock:InvokeModel", profile, True),
        ("run", "call Claude in a routed region", "bedrock:InvokeModel", claude, True),
        ("run", "embed with Titan", "bedrock:InvokeModel", titan, True),
        ("run", "call any other model", "bedrock:InvokeModel", sonnet, False),
        ("run", "score deals on the endpoint", "sagemaker:InvokeEndpoint", endpoint, True),
        ("run", "search the index", "es:ESHttpPost", f"{index}/_search", True),
        ("run", "write a document to the index", "es:ESHttpPut", f"{index}/_doc/x", False),
        ("run", "bulk-write the index", "es:ESHttpPost", f"{domain}/_bulk", False),
        ("run", "read the CRM snapshot", "s3:GetObject", f"{bucket}/crm-snapshot/deals.json", True),
        ("run", "change the CRM snapshot", "s3:PutObject", f"{bucket}/crm-snapshot/deals.json", False),
        ("run", "read training data", "s3:GetObject", f"{bucket}/training/rows.csv", False),
        # ingest: make seed
        ("ingest", "embed with Titan", "bedrock:InvokeModel", titan, True),
        ("ingest", "call Claude", "bedrock:InvokeModel", profile, False),
        ("ingest", "write the index", "es:ESHttpPut", f"{index}/_doc/x", True),
        ("ingest", "read knowledge documents", "s3:GetObject", f"{bucket}/knowledge/playbook.md", True),
        ("ingest", "write to the bucket", "s3:PutObject", f"{bucket}/knowledge/playbook.md", False),
        ("ingest", "score deals", "sagemaker:InvokeEndpoint", endpoint, False),
        # training: SageMaker
        ("training", "read training data", "s3:GetObject", f"{bucket}/training/rows.csv", True),
        ("training", "write model files", "s3:PutObject", f"{bucket}/models/model.tar.gz", True),
        ("training", "read the CRM snapshot", "s3:GetObject", f"{bucket}/crm-snapshot/deals.json", False),
        ("training", "call Claude", "bedrock:InvokeModel", profile, False),
        # build: CodeBuild
        ("build", "push the app image", "ecr:PutImage", repo, True),
        ("build", "read the CRM snapshot", "s3:GetObject", f"{bucket}/crm-snapshot/deals.json", False),
        ("build", "call Claude", "bedrock:InvokeModel", profile, False),
        # task_exec: ECS agent
        ("task_exec", "pull the app image", "ecr:BatchGetImage", repo, True),
        ("task_exec", "push an image", "ecr:PutImage", repo, False),
        ("task_exec", "call Claude", "bedrock:InvokeModel", profile, False),
    ] + ([
        ("run", "apply the DealPulse guardrail", "bedrock:ApplyGuardrail", out["guardrail"]["arn"], True),
        ("run", "apply any other guardrail", "bedrock:ApplyGuardrail",
         f"arn:aws:bedrock:{region}:{account}:guardrail/someotherguardrail", False),
        ("ingest", "apply the guardrail", "bedrock:ApplyGuardrail", out["guardrail"]["arn"], False),
    ] if "guardrail" in out else [])


def main() -> int:
    out = stack_outputs()
    session = boto3.Session(region_name=out["region"])
    account = session.client("sts").get_caller_identity()["Account"]
    iam = session.client("iam")

    failures = 0
    print(f"{'role':<10} {'expect':<6} {'got':<6}  check")
    for role, desc, action, resource, expected in build_checks(out, account):
        result = iam.simulate_principal_policy(
            PolicySourceArn=out["roles"][role], ActionNames=[action], ResourceArns=[resource],
        )["EvaluationResults"][0]["EvalDecision"]
        allowed = result == "allowed"
        ok = allowed == expected
        failures += not ok
        mark = "✓" if ok else "✗"
        print(f"{mark} {role:<8} {'allow' if expected else 'deny':<6} {'allow' if allowed else 'deny':<6}  {desc}  ({action})")

    ec2 = session.client("ec2")
    sg = ec2.describe_security_groups(GroupIds=[out["network"]["app_sg_id"]])["SecurityGroups"][0]
    inbound = len(sg["IpPermissions"])
    print(f"{'✓' if inbound == 0 else '✗'} app security group inbound rules: {inbound} (expect 0)")
    failures += inbound != 0

    users = [u["UserName"] for u in iam.list_users()["Users"] if u["UserName"].startswith(out["name_prefix"])]
    print(f"{'✓' if not users else '✗'} DealPulse IAM users: {len(users)} (expect 0)")
    failures += bool(users)

    total = len(build_checks(out, account)) + 2
    print(f"\n{total - failures}/{total} checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
