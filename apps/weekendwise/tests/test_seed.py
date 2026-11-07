"""Offline tests for the idempotent seed planner (weekendwise.seed)."""
from pathlib import Path

import pytest

from weekendwise import seed

MODEL, DIM = "embed-model", 3


def chunk(cid, text="hello", title="T"):
    return {"chunkId": cid, "title": title, "text": text, "cityId": "x", "active": True, "embedding": None}


def stored(coll, data, vector=(0.1, 0.2, 0.3), model=MODEL, dim=DIM):
    """What Firestore would hold after a previous seed run."""
    return seed.build_document(coll, data, vector=list(vector) if coll == seed.CHUNKS else None, model=model, dimension=dim)


def test_first_run_creates_and_embeds_everything():
    desired = {seed.CHUNKS: {"a": chunk("a"), "b": chunk("b")}, "cities": {"sf": {"name": "SF"}}}
    plan = seed.plan_sync(desired, {}, MODEL, DIM)
    assert plan.collections[seed.CHUNKS].create == ["a", "b"]
    assert plan.collections["cities"].create == ["sf"]
    assert plan.to_embed == ["a", "b"] and plan.reuse_embedding == []
    assert plan.has_changes


def test_second_run_is_a_no_op():
    desired = {seed.CHUNKS: {"a": chunk("a")}, "cities": {"sf": {"name": "SF"}}}
    existing = {seed.CHUNKS: {"a": stored(seed.CHUNKS, chunk("a"))}, "cities": {"sf": stored("cities", {"name": "SF"})}}
    plan = seed.plan_sync(desired, existing, MODEL, DIM)
    assert not plan.has_changes
    assert plan.to_embed == [] and plan.collections[seed.CHUNKS].unchanged == ["a"]


def test_text_change_re_embeds_only_that_chunk():
    existing = {seed.CHUNKS: {"a": stored(seed.CHUNKS, chunk("a")), "b": stored(seed.CHUNKS, chunk("b"))}}
    desired = {seed.CHUNKS: {"a": chunk("a", text="changed"), "b": chunk("b")}}
    plan = seed.plan_sync(desired, existing, MODEL, DIM)
    assert plan.to_embed == ["a"]
    assert plan.collections[seed.CHUNKS].update == ["a"] and plan.collections[seed.CHUNKS].unchanged == ["b"]


def test_metadata_change_reuses_vector():
    old = chunk("a")
    existing = {seed.CHUNKS: {"a": stored(seed.CHUNKS, old)}}
    desired = {seed.CHUNKS: {"a": {**old, "active": False}}}
    plan = seed.plan_sync(desired, existing, MODEL, DIM)
    assert plan.to_embed == [] and plan.reuse_embedding == ["a"]


def test_model_or_dimension_change_re_embeds():
    existing = {seed.CHUNKS: {"a": stored(seed.CHUNKS, chunk("a"))}}
    desired = {seed.CHUNKS: {"a": chunk("a")}}
    assert seed.plan_sync(desired, existing, "new-model", DIM).to_embed == ["a"]
    assert seed.plan_sync(desired, existing, MODEL, 4).to_embed == ["a"]


def test_deletes_only_documents_this_seeder_wrote():
    existing = {"cities": {"gone": stored("cities", {"name": "Old"}), "manual": {"name": "Added by hand"}}}
    plan = seed.plan_sync({"cities": {}}, existing, MODEL, DIM)
    assert plan.collections["cities"].delete == ["gone"]


def test_build_document_rejects_wrong_vector_size():
    with pytest.raises(ValueError, match="3-dimension"):
        seed.build_document(seed.CHUNKS, chunk("a"), vector=[0.1, 0.2], model=MODEL, dimension=DIM)


def test_real_seed_folder_loads_and_plans():
    root = Path(__file__).resolve().parents[1] / "data" / "seed"
    desired = seed.load_seed(root, seed.RUNTIME_COLLECTIONS)
    plan = seed.plan_sync(desired, {}, MODEL, 768)
    assert len(plan.to_embed) == len(desired[seed.CHUNKS]) > 0
    assert set(seed.FIXTURE_COLLECTIONS).isdisjoint(desired)  # fixtures not loaded by default
