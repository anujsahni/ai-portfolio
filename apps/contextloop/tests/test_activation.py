"""CL-14: the reverse ETL sync writes only the governed list, diff-based and idempotent, with an audit trail; Slack is optional."""
from __future__ import annotations

import json
import os

import httpx
import pytest

from contextloop import config

pytestmark = pytest.mark.skipif(os.environ.get("PGHOST") != "postgres", reason="runs inside the Compose network")


@pytest.fixture()
def client():
    from contextloop.activation import sync

    c = httpx.Client(timeout=30)
    c.post(f"{sync.CRM_URL}/reset")
    yield c
    c.post(f"{sync.CRM_URL}/reset")
    c.close()


def test_dry_run_then_sync_is_idempotent_and_audited(client):
    from contextloop.activation import sync

    truth = json.loads((config.TRUTH_DIR / "truth.json").read_text())
    p = sync.plan(client)
    assert p.counts == {"update": len(truth["at_risk"]), "clear": 0, "unchanged": 0}
    assert {c.account_id for c in p.changes} == {r["sf_account_id"] for r in truth["at_risk"]}
    result = sync.apply(client, p)
    assert result["written"] == len(truth["at_risk"])
    assert sync.plan(client).counts == {"update": 0, "clear": 0, "unchanged": len(truth["at_risk"])}
    audit = client.get(f"{sync.CRM_URL}/audit").json()
    assert len(audit) == len(truth["at_risk"]) and all(a["source_model"] == "marts.account_risk" and a["at"] for a in audit)


def test_only_the_governed_mart_decides_which_accounts_are_written(client):
    from contextloop.activation import sync

    naive_like = {"at_risk_accounts": [{"account_name": "Quenmere Paper Mills GmbH", "next_step": "Call them"}]}
    accounts = {c.account_name for c in sync.plan(client, naive_like).changes}
    assert "Quenmere Paper Mills GmbH" not in accounts
    assert accounts == {r["account_name"] for r in sync.governed_rows()}


def test_ai_drafted_next_steps_are_labelled(client):
    from contextloop.activation import sync

    row = sync.governed_rows()[0]
    p = sync.plan(client, {"at_risk_accounts": [{"account_name": row["account_name"], "next_step": "Drafted step"}]})
    ch = next(c for c in p.changes if c.account_name == row["account_name"])
    assert ch.after["Next_Step__c"] == "Drafted step" and ch.after["Next_Step_Source__c"] == "AI-drafted"
    assert all(c.after["Next_Step_Source__c"] == "Playbook rule (dbt)" for c in p.changes if c is not ch)


def test_slack_without_a_webhook_makes_no_network_call(monkeypatch):
    from contextloop.activation import sync

    monkeypatch.setenv("SLACK_WEBHOOK_URL", "")
    monkeypatch.setattr(httpx, "post", lambda *a, **k: pytest.fail("network call made"))
    assert sync.post_slack(sync.slack_message())["posted"] is False


def test_slack_with_a_webhook_posts_one_message(monkeypatch):
    from contextloop.activation import sync

    calls = []
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/T000/B000/XXXX")
    monkeypatch.setattr(httpx, "post", lambda url, json, timeout: calls.append(json) or httpx.Response(200))
    assert sync.post_slack(sync.slack_message())["posted"] is True
    assert len(calls) == 1 and "at risk" in calls[0]["text"]
