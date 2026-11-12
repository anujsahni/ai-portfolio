"""CL-07: the semantic layer validates, every metric is described for a business reader, and metrics equal the hidden truth."""
from __future__ import annotations

import json
import re
from functools import lru_cache

import pytest
import yaml

from contextloop import config, semantic

pytestmark = pytest.mark.skipif(not config.WAREHOUSE_PATH.exists(), reason="run `make build` first")
SPEC = yaml.safe_load((config.DBT_PROJECT_DIR / "models" / "semantic" / "semantic_models.yml").read_text())


@lru_cache(maxsize=1)
def truth():
    return json.loads((config.TRUTH_DIR / "truth.json").read_text())


def test_validate_configs_passes():
    proc = semantic._mf("validate-configs")
    assert proc.returncode == 0, proc.stdout[-2000:]


@pytest.mark.parametrize("metric", [m["name"] for m in SPEC["metrics"]])
def test_every_metric_has_a_short_plain_description(metric):
    m = next(x for x in SPEC["metrics"] if x["name"] == metric)
    text = " ".join(m.get("description", "").split())
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", text) if s]
    assert 1 <= len(sentences) <= 3, f"{metric}: {len(sentences)} sentences"
    assert m.get("label")


def test_saved_query_returns_exactly_the_at_risk_list():
    rows = semantic.query(saved_query="at_risk_strategic_accounts")
    flagged = {r["account"] for r in rows if r["account_risk_flag"] == "1"}
    assert flagged == {r["kunnr"] for r in truth()["at_risk"]}
    assert len(rows) == truth()["golden"]["G4"]


def test_on_time_rate_by_account_and_overall():
    by_account = {r["account"]: float(r["on_time_delivery_rate"])
                  for r in semantic.query(["on_time_delivery_rate"], ["account"]) if r["on_time_delivery_rate"]}
    for k, v in truth()["on_time_by_customer"].items():
        assert round(by_account[k], 4) == v["rate"], k
    overall = semantic.query(["on_time_delivery_rate"], where="{{ Dimension('account__is_strategic') }} = true")
    assert round(100 * float(overall[0]["on_time_delivery_rate"]), 1) == truth()["golden"]["G2"]


def test_net_revenue_overall_and_by_region_quarter():
    rows = semantic.query(["net_revenue"], ["billing_document__region", "billing_document__billing_quarter"])
    got = {f"{r['billing_document__region']}|{r['billing_document__billing_quarter']}": float(r["net_revenue"]) for r in rows}
    for k, v in truth()["net_revenue_usd"].items():
        assert abs(got[k] - v) < 0.01, k
    total = float(semantic.query(["net_revenue"])[0]["net_revenue"])
    assert abs(total - sum(truth()["net_revenue_usd"].values())) < 0.05


def test_tickets_and_renewals():
    t = truth()
    strategic = semantic.query(["open_shipping_tickets"], where="{{ Dimension('account__is_strategic') }} = true")
    assert int(float(strategic[0]["open_shipping_tickets"])) == t["golden"]["G6"]
    by_acct = {r["account"]: int(float(r["open_shipping_tickets"])) for r in semantic.query(["open_shipping_tickets"], ["account"])}
    for k, n in t["open_shipping_tickets"].items():
        assert by_acct.get(k, 0) == n, k
    due = {r["account"] for r in semantic.query(["renewals_due_120d"], ["account"]) if float(r["renewals_due_120d"] or 0) > 0}
    assert due == set(t["renewals_due_120d"])


def test_rate_by_tier_uses_the_tier_at_delivery_time():
    rows = semantic.query(["on_time_delivery_rate"], ["delivery__tier_at_delivery"])
    got = {r["delivery__tier_at_delivery"]: round(float(r["on_time_delivery_rate"]), 4) for r in rows}
    assert got == truth()["on_time_by_tier_at_delivery"]
    today = {r["account__tier"]: round(float(r["on_time_delivery_rate"]), 4)
             for r in semantic.query(["on_time_delivery_rate"], ["account__tier"])}
    assert today != got, "today's tier and the tier at delivery should give different answers (trap T5)"
