"""Offline checks on the index definition and hybrid query builder (no AWS calls)."""
import pytest

from dealpulse import search_index


def test_index_fields_match_design():
    props = search_index.INDEX_BODY["mappings"]["properties"]
    for field in ("passage_id", "text", "doc_type", "account_id", "opportunity_id", "date",
                  "author_role", "checksum", "embedding"):
        assert field in props
    vector = props["embedding"]
    assert vector["dimension"] == 1024
    assert vector["method"]["space_type"] == "cosinesimil"
    assert search_index.INDEX_BODY["mappings"]["dynamic"] == "strict"


def test_single_node_has_no_replicas():
    assert search_index.INDEX_BODY["settings"]["index"]["number_of_replicas"] == 0


def test_pipeline_weights_sum_to_one():
    combo = search_index.pipeline_body()["phase_results_processors"][0]["normalization-processor"]["combination"]
    assert sum(combo["parameters"]["weights"]) == pytest.approx(1.0)


def test_hybrid_query_applies_filter_to_both_halves():
    filters = [{"term": {"opportunity_id": "OPP-1"}}]
    q = search_index.hybrid_query("budget", [0.0] * 1024, filters=filters)
    keyword, vector = q["query"]["hybrid"]["queries"]
    assert keyword["bool"]["filter"] == filters
    assert vector["knn"]["embedding"]["filter"]["bool"]["filter"] == filters
    assert q["_source"]["excludes"] == ["embedding"]


def test_hybrid_query_refuses_to_search_without_scope():
    with pytest.raises(ValueError):
        search_index.hybrid_query("budget", [0.0] * 1024, filters=[])
