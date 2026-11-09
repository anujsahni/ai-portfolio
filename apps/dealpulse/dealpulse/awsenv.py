"""AWS sessions and stack settings shared by scripts and the app.

Operators work as themselves (their AWS profile) and assume the app's roles when a step must run
with that role's permissions, e.g. `make seed` as the ingest role. No access keys are stored.
"""
from __future__ import annotations

import functools
import json
import subprocess
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parents[1]
STACK_DIR = ROOT / "infra" / "stack"


@functools.lru_cache(maxsize=1)
def stack_outputs() -> dict:
    """Terraform outputs of infra/stack (names, ARNs, endpoints). Requires `make apply` to have run."""
    raw = subprocess.run(
        ["terraform", f"-chdir={STACK_DIR}", "output", "-json"],
        check=True, capture_output=True, text=True,
    ).stdout
    return {key: value["value"] for key, value in json.loads(raw).items()}


def operator_session(region: str | None = None) -> boto3.Session:
    return boto3.Session(region_name=region or stack_outputs()["region"])


def role_session(role: str, *, session_name: str = "dealpulse-operator") -> boto3.Session:
    """A session as one of the stack's roles (run, ingest), assumed from the operator's identity."""
    outputs = stack_outputs()
    arn = outputs["roles"][role]
    creds = operator_session().client("sts").assume_role(
        RoleArn=arn, RoleSessionName=session_name, DurationSeconds=3600,
    )["Credentials"]
    return boto3.Session(
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"],
        region_name=outputs["region"],
    )
