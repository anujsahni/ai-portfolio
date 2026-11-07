"""Offline tests for weekendwise.vertex using a fake google-genai client."""
from types import SimpleNamespace

import pytest

from weekendwise.config import Settings
from weekendwise.errors import (
    ConfigError,
    EmbeddingDimensionError,
    ModelAccessError,
    ModelRequestError,
    ModelResponseError,
    ModelServiceError,
    ModelTimeoutError,
    QuotaError,
)
from weekendwise.vertex import VertexClient, translate_error

SETTINGS = Settings(
    project_id="demo",
    generation_location="global",
    embedding_location="us-central1",
    generation_model_id="gen-model",
    embedding_model_id="embed-model",
    embedding_dimension=4,
    max_prompt_chars=100,
    max_output_tokens=50,
    max_embedding_batch=2,
)


class FakeModels:
    def __init__(self, dim=4, text="ok", error=None):
        self.dim, self.text, self.error = dim, text, error
        self.calls = []

    def generate_content(self, *, model, contents, config):
        self.calls.append(("generate", model, config))
        if self.error:
            raise self.error
        return SimpleNamespace(
            text=self.text,
            candidates=[SimpleNamespace(finish_reason="STOP")],
            usage_metadata=SimpleNamespace(prompt_token_count=3, candidates_token_count=1, thoughts_token_count=0),
        )

    def embed_content(self, *, model, contents, config):
        self.calls.append(("embed", model, config, len(contents)))
        if self.error:
            raise self.error
        return SimpleNamespace(embeddings=[SimpleNamespace(values=[0.1] * self.dim) for _ in contents])


def make(models=None):
    models = models or FakeModels()
    locations = []

    def factory(settings, location):
        locations.append(location)
        return SimpleNamespace(models=models)

    return VertexClient(SETTINGS, client_factory=factory), models, locations


class ApiError(Exception):
    def __init__(self, code):
        super().__init__(f"{code} error with secret-ish payload")
        self.code = code


def test_generate_uses_configured_model_location_and_limits():
    client, models, locations = make()
    result = client.generate_text("hi", max_output_tokens=500)
    _, model, config = models.calls[0]
    assert model == "gen-model" and locations == ["global"]
    assert config.max_output_tokens == 50  # capped at the configured limit
    assert config.thinking_config.thinking_level == "LOW"
    assert result.text == "ok" and result.model_id == "gen-model"


def test_prompt_size_limit_is_enforced_before_calling():
    client, models, _ = make()
    with pytest.raises(ModelRequestError, match="limit is 100"):
        client.generate_text("x" * 101)
    assert models.calls == []


def test_empty_reply_is_an_error():
    client, _, _ = make(FakeModels(text=""))
    with pytest.raises(ModelResponseError):
        client.generate_text("hi")


def test_documents_and_queries_use_same_model_and_dimension():
    client, models, locations = make()
    docs = client.embed_documents(["a", "b", "c"])  # batch size 2 -> two calls
    query = client.embed_query("q")
    embed_calls = [c for c in models.calls if c[0] == "embed"]
    assert [c[3] for c in embed_calls] == [2, 1, 1]
    assert {c[1] for c in embed_calls} == {"embed-model"}
    assert {c[2].output_dimensionality for c in embed_calls} == {4}
    assert [c[2].task_type for c in embed_calls] == ["RETRIEVAL_DOCUMENT", "RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"]
    assert len(docs) == 3 and len(query) == 4
    assert set(locations) == {"us-central1"}


def test_wrong_dimension_is_rejected():
    client, _, _ = make(FakeModels(dim=3))
    with pytest.raises(EmbeddingDimensionError, match="3 dimensions; configured dimension is 4"):
        client.embed_query("q")


@pytest.mark.parametrize(
    "code,error_type",
    [(403, ModelAccessError), (404, ModelAccessError), (429, QuotaError), (400, ModelRequestError), (503, ModelServiceError)],
)
def test_api_errors_are_translated(code, error_type):
    client, _, _ = make(FakeModels(error=ApiError(code)))
    with pytest.raises(error_type) as err:
        client.generate_text("hi")
    assert "secret-ish" not in str(err.value)  # raw payloads never leak
    assert err.value.hint


def test_timeout_and_sign_in_errors():
    Timeout = type("ReadTimeout", (Exception,), {})
    assert isinstance(translate_error(Timeout(), kind="generation", model="m", location="l", settings=SETTINGS), ModelTimeoutError)
    Refresh = type("RefreshError", (Exception,), {"__module__": "google.auth.exceptions"})
    err = translate_error(Refresh(), kind="embedding", model="m", location="l", settings=SETTINGS)
    assert isinstance(err, ConfigError) and "application-default login" in err.hint
