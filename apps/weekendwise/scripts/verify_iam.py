#!/usr/bin/env python3
"""IAC-03 check: each WeekendWise service account has exactly the access it should.

Impersonates each account and asks Google which permissions it holds on the project
(projects.testIamPermissions). Also confirms no user-managed keys exist.
No resources are read or written.

Usage: python scripts/verify_iam.py PROJECT_ID
"""
from __future__ import annotations

import sys
import time

import google.auth
from google.auth import impersonated_credentials
from google.auth.transport.requests import AuthorizedSession

SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]

# permission -> expected (True = must have, False = must NOT have), per account
EXPECTED = {
    "weekendwise-run": {
        "aiplatform.endpoints.predict": True,   # call Gemini / embeddings
        "datastore.entities.get": True,         # read Firestore
        "datastore.entities.list": True,
        "datastore.entities.create": False,     # must not write
        "datastore.entities.update": False,
        "datastore.entities.delete": False,
        "logging.logEntries.create": True,
        "artifactregistry.repositories.uploadArtifacts": False,
    },
    "weekendwise-ingest": {
        "aiplatform.endpoints.predict": True,
        "datastore.entities.get": True,
        "datastore.entities.create": True,      # writes the corpus
        "datastore.entities.update": True,
        "artifactregistry.repositories.uploadArtifacts": False,
    },
    "weekendwise-build": {
        "artifactregistry.repositories.uploadArtifacts": True,
        "logging.logEntries.create": True,
        "storage.objects.get": True,
        "aiplatform.endpoints.predict": False,
        "datastore.entities.get": False,
    },
}


def granted(session: AuthorizedSession, project: str, permissions: list[str]) -> set[str]:
    url = f"https://cloudresourcemanager.googleapis.com/v1/projects/{project}:testIamPermissions"
    r = session.post(url, json={"permissions": permissions}, timeout=30)
    r.raise_for_status()
    return set(r.json().get("permissions", []))


def main(project: str) -> int:
    source, _ = google.auth.default(scopes=SCOPES, quota_project_id=project)
    admin = AuthorizedSession(source)
    failures = 0
    for account, expected in EXPECTED.items():
        email = f"{account}@{project}.iam.gserviceaccount.com"
        creds = impersonated_credentials.Credentials(source_credentials=source, target_principal=email, target_scopes=SCOPES)
        session = AuthorizedSession(creds)
        result = None
        for attempt in range(6):  # new IAM grants can take a minute or two to apply
            try:
                result = granted(session, project, list(expected))
                break
            except Exception as exc:  # noqa: BLE001
                if attempt == 5:
                    print(f"✗ {account}: could not impersonate ({type(exc).__name__}). "
                          "New grants can take a few minutes; rerun make verify.")
                    failures += 1
                else:
                    time.sleep(15)
        if result is None:
            continue
        bad = [p for p, want in expected.items() if (p in result) != want]
        keys = admin.get(f"https://iam.googleapis.com/v1/projects/{project}/serviceAccounts/{email}/keys?keyTypes=USER_MANAGED", timeout=30)
        key_count = len(keys.json().get("keys", [])) if keys.ok else -1
        can = sorted(p for p in expected if p in result)
        cannot = sorted(p for p in expected if p not in result)
        status = "✓" if not bad and key_count == 0 else "✗"
        print(f"{status} {account}")
        print(f"    can:    {', '.join(can) or '-'}")
        print(f"    cannot: {', '.join(cannot) or '-'}")
        print(f"    user-managed keys: {key_count if key_count >= 0 else 'unknown'}")
        if bad:
            failures += 1
            for p in bad:
                print(f"    ✗ expected {'to have' if expected[p] else 'NOT to have'} {p}")
        if key_count != 0:
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
