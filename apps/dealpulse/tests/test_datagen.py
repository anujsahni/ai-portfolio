"""MVP-03: the synthetic CRM is reproducible, consistent and leak-free (no AWS calls)."""
import json
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from dealpulse import features as F
from dealpulse.datagen import checks, output
from dealpulse.datagen.generator import Generator

ROOT = Path(__file__).resolve().parents[1]
RULE = json.loads((ROOT / "data/generator/hidden_rule.json").read_text())
SCENARIOS = json.loads((ROOT / "data/generator/scenarios.json").read_text())["scenarios"]


@pytest.fixture(scope="module")
def ds():
    return Generator(1, RULE, SCENARIOS).generate()


def test_same_seed_gives_identical_files(tmp_path):
    for name in ("a", "b"):
        output.write(Generator(3, RULE, SCENARIOS, scale=0.15).generate(), tmp_path / name, seed=3, rule=RULE)
    assert (tmp_path / "a/manifest.json").read_text() == (tmp_path / "b/manifest.json").read_text()
    output.write(Generator(4, RULE, SCENARIOS, scale=0.15).generate(), tmp_path / "c", seed=4, rule=RULE)
    assert (tmp_path / "a/manifest.json").read_text() != (tmp_path / "c/manifest.json").read_text()


def test_writer_refuses_to_replace_an_unrelated_folder(tmp_path):
    (tmp_path / "keep.txt").write_text("not generator output")
    with pytest.raises(SystemExit):
        output.write(Generator(3, RULE, SCENARIOS, scale=0.15).generate(), tmp_path, seed=3, rule=RULE)
    assert (tmp_path / "keep.txt").exists()


def test_referential_integrity(ds):
    assert checks.referential_integrity(ds.objects) == []


def test_notes_agree_with_drivers(ds):
    assert checks.notes_agree_with_drivers(ds.objects, ds.truth) == []


def test_contacts_are_fictional(ds):
    assert checks.contact_details_are_fictional(ds.objects) == []


def test_win_rate_is_plausible(ds):
    closed = [t for t in ds.truth if t["closed"]]
    assert 0.20 <= sum(t["won"] for t in closed) / len(closed) <= 0.35


def test_drivers_move_win_rates_the_right_way(ds):
    closed = [t for t in ds.truth if t["closed"]]
    rate = lambda group: sum(t["won"] for t in group) / len(group)
    assert rate([t for t in closed if t["exec_engaged"]]) > rate([t for t in closed if not t["exec_engaged"]]) + 0.1
    assert rate([t for t in closed if t["competitor"]]) < rate([t for t in closed if not t["competitor"]])


def test_all_traps_present(ds):
    traps = ds.traps
    assert traps["injection"]["ActivityId"] and traps["discount_35"] and traps["thin_notes"]
    assert traps["lookalike"]["approved"]["AccountId"] != traps["lookalike"]["not_approved"]["AccountId"]
    notes = {r["Id"]: r["Description"] for k in ("Task", "Event") for r in ds.objects[k] if r.get("Description")}
    assert "Closed Won" in notes[traps["injection"]["ActivityId"]]
    thin = sum(1 for k in ("Task", "Event") for r in ds.objects[k] if r["WhatId"] == traps["thin_notes"] and r.get("Description"))
    assert thin <= 2
    opp = next(o for o in ds.objects["Opportunity"] if o["Id"] == traps["discount_35"])
    assert opp["Discount_Pct__c"] == 35


def test_lookalike_notes_tell_opposite_budget_stories(ds):
    lk = ds.traps["lookalike"]
    def text(opp_id):
        return " ".join(r["Description"] for k in ("Task", "Event") for r in ds.objects[k]
                        if r["WhatId"] == opp_id and r.get("Description"))
    assert "budget is approved" in text(lk["approved"]["OpportunityId"]) or "signed off" in text(lk["approved"]["OpportunityId"])
    assert "budget is approved" not in text(lk["not_approved"]["OpportunityId"])


def _filtered_index(objects, as_of: date):
    """The CRM as it existed on `as_of`: drop every dated record after it."""
    iso = as_of.isoformat()
    keep = {}
    for name, rows in objects.items():
        date_field = {"OpportunityHistory": "CreatedDate", "OpportunityFieldHistory": "CreatedDate",
                      "OpportunityContactRole": "CreatedDate", "Task": "ActivityDate", "Event": "ActivityDate",
                      "Case": "CreatedDate"}.get(name)
        keep[name] = [r for r in rows if date_field is None or r[date_field] <= iso]
    return F.build_index(keep)


def test_training_features_use_only_past_records(ds):
    index = F.build_index(ds.objects)
    closed = [d for d in index.values() if d.opportunity["IsClosed"]][:60]
    checked = 0
    for deal in closed:
        for as_of in F.snapshot_dates(deal)[::2]:
            past = _filtered_index(ds.objects, as_of)[deal.opportunity["Id"]]
            # Case close dates are in the future relative to as_of; features must treat them as still open.
            assert F.features_as_of(deal, as_of) == F.features_as_of(past, as_of), (deal.opportunity["Id"], as_of)
            checked += 1
    assert checked > 50


def test_features_ignore_the_final_outcome(ds):
    index = F.build_index(ds.objects)
    deal = next(d for d in index.values() if d.opportunity["IsClosed"] and d.opportunity["IsWon"])
    as_of = F.snapshot_dates(deal)[0]
    flipped = replace(deal, opportunity={**deal.opportunity, "IsWon": False, "StageName": "Closed Lost",
                                         "Probability": 0, "ForecastCategoryName": "Omitted"})
    assert F.features_as_of(deal, as_of) == F.features_as_of(flipped, as_of)


def test_feature_columns_are_stable():
    assert len(F.FEATURE_COLUMNS) == len(set(F.FEATURE_COLUMNS))
    for banned in ("owner", "rep", "probability", "forecast"):
        assert not any(banned in c for c in F.FEATURE_COLUMNS)
