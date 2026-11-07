"""Google credentials helpers. Never uses key files."""
from __future__ import annotations

from .errors import ConfigError

SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]


def credentials(project_id: str, impersonate: str | None = None):
    """Application Default Credentials, optionally impersonating a service account."""
    import google.auth
    from google.auth import exceptions, impersonated_credentials

    try:
        creds, _ = google.auth.default(scopes=SCOPES, quota_project_id=project_id)
    except exceptions.DefaultCredentialsError as exc:
        raise ConfigError("No Google credentials found.", hint="Run: gcloud auth application-default login") from exc
    if impersonate:
        creds = impersonated_credentials.Credentials(source_credentials=creds, target_principal=impersonate, target_scopes=SCOPES)
    return creds


def service_account(project_id: str, name: str) -> str:
    """Email of a WeekendWise service account, e.g. name='run' -> weekendwise-run@<project>.iam.gserviceaccount.com."""
    return f"weekendwise-{name}@{project_id}.iam.gserviceaccount.com"


def firestore_client(project_id: str, database: str = "(default)", impersonate: str | None = None):
    from google.cloud import firestore

    return firestore.Client(project=project_id, database=database, credentials=credentials(project_id, impersonate))
