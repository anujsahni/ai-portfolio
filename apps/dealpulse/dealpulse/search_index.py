"""The OpenSearch index and hybrid search pipeline DealPulse searches (design §5).

One index, `deal_passages`, holds every passage: deal-scoped notes (with account and opportunity
IDs) and shared documents (playbook, policy, win/loss reviews, with neither). The search pipeline
blends keyword (BM25) and vector scores so exact names and meaning both count.
"""
from __future__ import annotations

import boto3
from opensearchpy import AWSV4SignerAuth, OpenSearch, RequestsHttpConnection

EMBEDDING_DIMENSION = 1024  # Titan Text Embeddings V2
KEYWORD_WEIGHT = 0.4
VECTOR_WEIGHT = 0.6

INDEX_BODY = {
    "settings": {
        "index": {
            "knn": True,
            "number_of_shards": 1,
            "number_of_replicas": 0,  # single-node domain: replicas would leave the index yellow
        }
    },
    "mappings": {
        "dynamic": "strict",
        "properties": {
            "passage_id": {"type": "keyword"},
            "text": {"type": "text", "analyzer": "english"},
            "title": {"type": "text", "analyzer": "english"},
            "doc_type": {"type": "keyword"},
            "account_id": {"type": "keyword"},
            "opportunity_id": {"type": "keyword"},
            "date": {"type": "date"},
            "author_role": {"type": "keyword"},
            "checksum": {"type": "keyword"},
            "active": {"type": "boolean"},
            "embedding": {
                "type": "knn_vector",
                "dimension": EMBEDDING_DIMENSION,
                "method": {
                    "name": "hnsw",
                    "engine": "lucene",  # efficient filtering, which deal-scoped search relies on
                    "space_type": "cosinesimil",
                    "parameters": {"m": 16, "ef_construction": 128},
                },
            },
        },
    },
}


def pipeline_body() -> dict:
    return {
        "description": "DealPulse hybrid search: min-max normalised BM25 and vector scores, weighted mean",
        "phase_results_processors": [{
            "normalization-processor": {
                "normalization": {"technique": "min_max"},
                "combination": {
                    "technique": "arithmetic_mean",
                    "parameters": {"weights": [KEYWORD_WEIGHT, VECTOR_WEIGHT]},
                },
            }
        }],
    }


def pipeline_name(index: str) -> str:
    return f"{index}-hybrid"


def hybrid_query(text: str, vector: list[float], *, filters: list[dict], size: int = 6) -> dict:
    """A hybrid query whose keyword and vector halves carry the same filter.

    The filter is required: DealPulse never searches without a scope (one deal, or shared docs).
    """
    if not filters:
        raise ValueError("hybrid_query requires at least one filter (deal or shared-document scope)")
    return {
        "size": size,
        "_source": {"excludes": ["embedding"]},
        "query": {
            "hybrid": {
                "queries": [
                    {"bool": {"must": [{"match": {"text": text}}], "filter": filters}},
                    {"knn": {"embedding": {"vector": vector, "k": max(size * 4, 20), "filter": {"bool": {"filter": filters}}}}},
                ]
            }
        },
    }


def client(session: boto3.Session, endpoint: str) -> OpenSearch:
    """An OpenSearch client whose requests are signed with the given session's IAM identity."""
    auth = AWSV4SignerAuth(session.get_credentials(), session.region_name, "es")
    return OpenSearch(
        hosts=[{"host": endpoint, "port": 443}],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        timeout=20,
        pool_maxsize=10,
    )
