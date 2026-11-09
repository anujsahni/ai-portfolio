#!/usr/bin/env python3
"""MVP-04: train the win-probability model on SageMaker, report on it, register it, approve it.

    python scripts/train_model.py train              # make train
    python scripts/train_model.py approve MODEL=...  # make approve-model MODEL=<arn>

`train` packages ml/ as script-mode code, runs a SageMaker Training job (managed XGBoost 3.2
container, one ml.m5.large for a few minutes: about a cent), downloads evaluation.json, writes
docs/mvp/evidence/MVP-04-model-evaluation.md and reports/model/<job>.json (also uploaded to
s3://<bucket>/reports/model/ for the app's Model page), and registers a model package as
PendingManualApproval. Nothing is served until a person approves it and runs make deploy-model.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import tarfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dealpulse import model_report  # noqa: E402
from dealpulse.awsenv import operator_session, stack_outputs  # noqa: E402

XGBOOST_IMAGE = "683313688378.dkr.ecr.{region}.amazonaws.com/sagemaker-xgboost:3.2-0"
INSTANCE = "ml.m5.large"
HOURLY_USD = 0.115  # ml.m5.large training, us-east-1 (check current pricing)
HYPERPARAMETERS = {"max_depth": 4, "eta": 0.05, "num_round": 800, "early_stopping_rounds": 50,
                   "subsample": 0.8, "colsample_bytree": 0.8, "min_child_weight": 5, "seed": 7}
# Serverless endpoints run the container as a non-root user. On startup the XGBoost container
# pip-installs inference.py, and /opt/venv isn't writable, so install into /tmp and import from
# there instead. /tmp must exist when Python starts, which is why it's not /opt/ml/code.
# Keep in sync with aws_sagemaker_model.win_model in infra (which also sets these).
SERVERLESS_ENV = {"PIP_TARGET": "/tmp", "PYTHONPATH": "/tmp"}


def source_tarball() -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name in ("train.py", "inference.py", "metrics.py"):
            tar.add(ROOT / "ml" / name, arcname=name)
    return buf.getvalue()


def train(args: argparse.Namespace) -> int:
    out = stack_outputs()
    region, bucket = out["region"], out["data_bucket"]
    session = operator_session()
    s3, sm = session.client("s3"), session.client("sagemaker")
    job = f"{out['name_prefix']}-win-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}"
    image = XGBOOST_IMAGE.format(region=region)

    code_key = f"models/code/{job}/sourcedir.tar.gz"
    s3.put_object(Bucket=bucket, Key=code_key, Body=source_tarball())
    code_uri = f"s3://{bucket}/{code_key}"
    hp = {k: json.dumps(v) for k, v in HYPERPARAMETERS.items()}
    hp.update({"sagemaker_program": json.dumps("train.py"), "sagemaker_submit_directory": json.dumps(code_uri),
               "sagemaker_region": json.dumps(region)})

    print(f"── Starting training job {job} ({INSTANCE}, {image.split('/')[-1]})")
    sm.create_training_job(
        TrainingJobName=job, RoleArn=out["roles"]["training"], HyperParameters=hp,
        AlgorithmSpecification={"TrainingImage": image, "TrainingInputMode": "File"},
        InputDataConfig=[{"ChannelName": "train", "ContentType": "text/csv", "DataSource": {"S3DataSource": {
            "S3DataType": "S3Prefix", "S3Uri": f"s3://{bucket}/training/", "S3DataDistributionType": "FullyReplicated"}}}],
        OutputDataConfig={"S3OutputPath": f"s3://{bucket}/models/output/"},
        ResourceConfig={"InstanceType": INSTANCE, "InstanceCount": 1, "VolumeSizeInGB": 10},
        StoppingCondition={"MaxRuntimeInSeconds": 1800},
        Tags=[{"Key": "app", "Value": "dealpulse"}, {"Key": "name_prefix", "Value": out["name_prefix"]}],
    )
    last = None
    while True:
        desc = sm.describe_training_job(TrainingJobName=job)
        status = (desc["TrainingJobStatus"], desc.get("SecondaryStatus"))
        if status != last:
            print(f"   {datetime.now():%H:%M:%S} {status[0]} · {status[1]}")
            last = status
        if desc["TrainingJobStatus"] in ("Completed", "Failed", "Stopped"):
            break
        time.sleep(20)
    if desc["TrainingJobStatus"] != "Completed":
        print(f"✗ Training {desc['TrainingJobStatus']}: {desc.get('FailureReason', 'see CloudWatch logs /aws/sagemaker/TrainingJobs')}")
        return 1
    billable = desc.get("BillableTimeInSeconds", 0)
    cost_note = f"Billable training time {billable} s on {INSTANCE} (≈ ${billable / 3600 * HOURLY_USD:.3f})."
    print(f"✓ {cost_note}")

    model_uri = desc["ModelArtifacts"]["S3ModelArtifacts"]
    m_bucket, m_key = model_uri.removeprefix("s3://").split("/", 1)
    with tarfile.open(fileobj=io.BytesIO(s3.get_object(Bucket=m_bucket, Key=m_key)["Body"].read())) as tar:
        evaluation = json.load(tar.extractfile("evaluation.json"))

    eval_key = f"reports/model/{job}.json"
    s3.put_object(Bucket=bucket, Key=eval_key, Body=json.dumps(evaluation, indent=2).encode(), ContentType="application/json")
    group = out["model"]["package_group"]
    m, b = evaluation["model"], evaluation["baseline_stage_probability"]
    package = sm.create_model_package(
        ModelPackageGroupName=group,
        ModelPackageDescription=f"XGBoost win-probability model from {job}. Held-out AUC {m['auc']:.3f} (baseline {b['auc']:.3f}).",
        ModelApprovalStatus="PendingManualApproval",
        InferenceSpecification={
            "Containers": [{"Image": image, "ModelDataUrl": model_uri, "Environment": {
                "SAGEMAKER_PROGRAM": "inference.py", "SAGEMAKER_SUBMIT_DIRECTORY": code_uri, "SAGEMAKER_REGION": region,
                **SERVERLESS_ENV}}],
            "SupportedContentTypes": ["application/json"], "SupportedResponseMIMETypes": ["application/json"],
        },
        ModelMetrics={"ModelQuality": {"Statistics": {"ContentType": "application/json", "S3Uri": f"s3://{bucket}/{eval_key}"}}},
        CustomerMetadataProperties={
            "training_job": job, "auc": f"{m['auc']:.4f}", "brier": f"{m['brier']:.4f}",
            "baseline_auc": f"{b['auc']:.4f}", "baseline_brier": f"{b['brier']:.4f}",
            "test_quarter": evaluation["quarters"]["test"][0],
        },
    )
    arn = package["ModelPackageArn"]

    reports = ROOT / "reports" / "model"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / f"{job}.json").write_text(json.dumps({"job": job, "package": arn, **evaluation}, indent=2))
    evidence = ROOT / "docs/mvp/evidence/MVP-04-model-evaluation.md"
    evidence.write_text(model_report.markdown(evaluation, job=job, package_arn=arn, cost_note=cost_note))
    print(f"✓ registered {arn} (PendingManualApproval)")
    print(f"✓ report: {evidence.relative_to(ROOT)}  ·  s3://{bucket}/{eval_key}")
    for name, (ok, detail) in model_report.checks(evaluation).items():
        print(f"  {'✓' if ok else '✗'} {name.replace('_', ' ')}: {detail}")
    print(f"\nNext: read the report, then  make approve-model MODEL={arn}")
    return 0


def approve(args: argparse.Namespace) -> int:
    sm = operator_session().client("sagemaker")
    pkg = sm.describe_model_package(ModelPackageName=args.model)
    meta = pkg.get("CustomerMetadataProperties", {})
    print(f"Model package {args.model}")
    print(f"  status now: {pkg['ModelApprovalStatus']}  ·  trained by {meta.get('training_job')}")
    print(f"  held-out {meta.get('test_quarter')}: AUC {meta.get('auc')} (baseline {meta.get('baseline_auc')}), "
          f"Brier {meta.get('brier')} (baseline {meta.get('baseline_brier')})")
    if pkg["ModelApprovalStatus"] == "Approved":
        print("✓ already approved")
        return 0
    if not args.yes and input("Approve this version for deployment? Type 'approve': ").strip() != "approve":
        print("✗ Not approved")
        return 1
    sm.update_model_package(ModelPackageArn=args.model, ModelApprovalStatus="Approved",
                            ApprovalDescription=f"Approved via make approve-model at {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC")
    print(f"✓ Approved. Deploy with: make deploy-model MODEL={args.model}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("train")
    a = sub.add_parser("approve")
    a.add_argument("--model", required=True)
    a.add_argument("--yes", action="store_true", help="skip the typed confirmation")
    args = parser.parse_args()
    return train(args) if args.command == "train" else approve(args)


if __name__ == "__main__":
    sys.exit(main())
