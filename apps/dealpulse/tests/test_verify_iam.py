"""Offline checks on the IAM verification plan (no AWS calls)."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("verify_iam", Path(__file__).parents[1] / "scripts" / "verify_iam.py")
verify_iam = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify_iam)

OUT = {
    "region": "us-east-1",
    "names": {"bucket": "dp-data-1", "domain": "dp", "index": "deal_passages", "endpoint": "dp-win-model", "ecr_repo": "dp"},
    "models": {
        "claude_inference_profile": "us.anthropic.claude-opus-5-5",
        "claude_model_id": "anthropic.claude-opus-5-5",
        "titan_model_id": "amazon.titan-embed-text-v2:0",
    },
}
CHECKS = verify_iam.build_checks(OUT, "111122223333")


def test_every_role_has_allow_and_deny_checks():
    for role in ("run", "ingest", "training", "build", "task_exec"):
        expectations = {expected for r, *_, expected in CHECKS if r == role}
        assert expectations == {True, False}, role


def test_story_denies_are_covered():
    denied = [(r, a, res) for r, _, a, res, ok in CHECKS if not ok]
    assert any(r == "run" and a == "es:ESHttpPut" for r, a, _ in denied)          # app can't write the index
    assert any(r == "run" and a == "s3:PutObject" for r, a, _ in denied)          # app can't write S3
    assert any(r == "ingest" and "inference-profile" in res for r, _, res in denied)  # ingest can't call Claude
    assert any(r == "training" and "crm-snapshot" in res for r, _, res in denied)     # training can't read the snapshot
    assert len(CHECKS) >= 10
