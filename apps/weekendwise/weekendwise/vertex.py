"""Server-side Vertex AI client: Gemini generation and text embeddings.

- Model IDs, locations, and limits come from `Settings` (never hard-coded here).
- Documents and queries are embedded with the same model and dimension.
- Every call is bounded: prompt size, output tokens, timeout, and retries.
- Errors are translated into `weekendwise.errors` types with safe messages.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Sequence

from .config import Settings
from .errors import (
    ConfigError,
    EmbeddingDimensionError,
    ModelAccessError,
    ModelRequestError,
    ModelResponseError,
    ModelServiceError,
    ModelTimeoutError,
    QuotaError,
    WeekendWiseError,
)

RETRYABLE_STATUS = [429, 500, 502, 503, 504]


@dataclass(frozen=True)
class GenerationResult:
    text: str
    model_id: str
    finish_reason: str | None
    input_tokens: int | None
    output_tokens: int | None
    thought_tokens: int | None
    latency_ms: int


def _default_client_factory(settings: Settings, location: str):
    """Create a google-genai client bound to Vertex AI in one location."""
    import google.auth
    from google.auth import exceptions as auth_exceptions
    from google.auth import impersonated_credentials
    from google.genai import Client, types

    scopes = ["https://www.googleapis.com/auth/cloud-platform"]
    try:
        credentials, _ = google.auth.default(scopes=scopes, quota_project_id=settings.project_id)
    except auth_exceptions.DefaultCredentialsError as exc:
        raise ConfigError(
            "No Google credentials found.",
            hint="Run: gcloud auth application-default login",
        ) from exc
    if settings.impersonate_service_account:
        credentials = impersonated_credentials.Credentials(
            source_credentials=credentials,
            target_principal=settings.impersonate_service_account,
            target_scopes=scopes,
        )
    http_options = types.HttpOptions(
        timeout=int(settings.request_timeout_seconds * 1000),
        retry_options=types.HttpRetryOptions(
            attempts=1 + settings.model_retry_attempts,
            http_status_codes=RETRYABLE_STATUS,
        ),
    )
    return Client(
        vertexai=True,
        project=settings.project_id,
        location=location,
        credentials=credentials,
        http_options=http_options,
    )


class VertexClient:
    def __init__(self, settings: Settings, client_factory: Callable[[Settings, str], object] | None = None):
        self.settings = settings
        self._factory = client_factory or _default_client_factory
        self._clients: dict[str, object] = {}

    # ------------------------------------------------------------- generation

    def generate_text(
        self,
        prompt: str,
        *,
        system_instruction: str | None = None,
        max_output_tokens: int | None = None,
        temperature: float = 0.4,
        response_json_schema: dict | None = None,
    ) -> GenerationResult:
        s = self.settings
        size = len(prompt) + len(system_instruction or "")
        if size > s.max_prompt_chars:
            raise ModelRequestError(
                f"Prompt is {size} characters; the limit is {s.max_prompt_chars}.",
                hint="Retrieve fewer or shorter passages, or raise MAX_PROMPT_CHARS deliberately.",
            )
        out_tokens = min(max_output_tokens or s.max_output_tokens, s.max_output_tokens)

        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            max_output_tokens=out_tokens,
            temperature=temperature,
            thinking_config=types.ThinkingConfig(thinking_level=s.thinking_level),
            response_mime_type="application/json" if response_json_schema else None,
            response_json_schema=response_json_schema,
        )
        start = time.monotonic()
        response = self._call(
            "generation",
            s.generation_location,
            lambda client: client.models.generate_content(model=s.generation_model_id, contents=prompt, config=config),
        )
        latency_ms = int((time.monotonic() - start) * 1000)

        candidates = getattr(response, "candidates", None) or []
        raw_finish = getattr(candidates[0], "finish_reason", None) if candidates else None
        finish = str(getattr(raw_finish, "value", raw_finish)) if raw_finish else None
        text = (getattr(response, "text", None) or "").strip()
        if not text:
            raise ModelResponseError(
                f"The model returned no text (finish reason: {finish or 'unknown'}).",
                hint="If the reason is MAX_TOKENS, raise the output limit; if SAFETY, rephrase the request.",
            )
        usage = getattr(response, "usage_metadata", None)
        return GenerationResult(
            text=text,
            model_id=s.generation_model_id,
            finish_reason=finish,
            input_tokens=getattr(usage, "prompt_token_count", None),
            output_tokens=getattr(usage, "candidates_token_count", None),
            thought_tokens=getattr(usage, "thoughts_token_count", None),
            latency_ms=latency_ms,
        )

    # ------------------------------------------------------------- embeddings

    def embed_documents(self, texts: Sequence[str], titles: Sequence[str] | None = None) -> list[list[float]]:
        """Embed corpus chunks (task type RETRIEVAL_DOCUMENT)."""
        if titles is not None and len(titles) != len(texts):
            raise ValueError("titles must match texts one-to-one")
        vectors: list[list[float]] = []
        batch = self.settings.max_embedding_batch
        for i in range(0, len(texts), batch):
            vectors.extend(self._embed(list(texts[i : i + batch]), "RETRIEVAL_DOCUMENT"))
        return vectors

    def embed_query(self, text: str) -> list[float]:
        """Embed a traveler query (task type RETRIEVAL_QUERY), same model and dimension as documents."""
        return self._embed([text], "RETRIEVAL_QUERY")[0]

    def _embed(self, texts: list[str], task_type: str) -> list[list[float]]:
        if not texts:
            return []
        s = self.settings
        from google.genai import types

        config = types.EmbedContentConfig(task_type=task_type, output_dimensionality=s.embedding_dimension)
        response = self._call(
            "embedding",
            s.embedding_location,
            lambda client: client.models.embed_content(model=s.embedding_model_id, contents=texts, config=config),
        )
        embeddings = getattr(response, "embeddings", None) or []
        if len(embeddings) != len(texts):
            raise ModelResponseError(f"Asked for {len(texts)} embeddings but received {len(embeddings)}.")
        vectors = [list(e.values or []) for e in embeddings]
        for v in vectors:
            if len(v) != s.embedding_dimension:
                raise EmbeddingDimensionError(
                    f"Embedding has {len(v)} dimensions; configured dimension is {s.embedding_dimension}.",
                    hint="VERTEX_EMBEDDING_DIMENSION must match the model output and the Firestore vector index.",
                )
        return vectors

    # ------------------------------------------------------------- plumbing

    def _client(self, location: str):
        if location not in self._clients:
            self._clients[location] = self._factory(self.settings, location)
        return self._clients[location]

    def _call(self, kind: str, location: str, fn):
        model = self.settings.generation_model_id if kind == "generation" else self.settings.embedding_model_id
        try:
            return fn(self._client(location))
        except WeekendWiseError:
            raise
        except Exception as exc:  # translated below; never re-raised raw
            raise translate_error(exc, kind=kind, model=model, location=location, settings=self.settings) from exc


def translate_error(exc: Exception, *, kind: str, model: str, location: str, settings: Settings) -> WeekendWiseError:
    """Map SDK/auth/network exceptions to safe, actionable errors."""
    name = type(exc).__name__
    module = type(exc).__module__
    where = f"{kind} model {model} in {location}"
    who = settings.impersonate_service_account or "your signed-in account"

    if name in ("RefreshError", "TransportError") and "google.auth" in module:
        return ConfigError(
            f"Google sign-in failed or expired while calling the {where}.",
            hint="Run: gcloud auth application-default login",
        )
    if "Timeout" in name or ("httpx" in module and "timed out" in str(exc).lower()):
        return ModelTimeoutError(
            f"The {where} did not respond within {settings.request_timeout_seconds:g} seconds.",
            hint="Retry, shorten the prompt, or raise REQUEST_TIMEOUT_SECONDS.",
        )
    code = getattr(exc, "code", None)
    if isinstance(code, int):
        if code in (401, 403):
            return ModelAccessError(
                f"Permission denied for the {where} (as {who}).",
                hint="Grant roles/aiplatform.user to that identity, and check the Vertex AI API is enabled.",
            )
        if code == 404:
            return ModelAccessError(
                f"The {where} was not found or this project can't use it.",
                hint="Check the model ID and location (Gemini models may need location 'global').",
            )
        if code == 429:
            return QuotaError(
                f"Quota or rate limit reached for the {where}.",
                hint="Wait and retry, reduce request volume, or request more quota in IAM & Admin → Quotas.",
            )
        if code == 400:
            return ModelRequestError(
                f"The {where} rejected the request as invalid.",
                hint="Check prompt size and generation settings.",
            )
        if code >= 500:
            return ModelServiceError(f"Google returned a temporary error ({code}) for the {where}.", hint="Retry shortly.")
    return WeekendWiseError(f"Unexpected error calling the {where} ({name}).", hint="See server logs for details.")
