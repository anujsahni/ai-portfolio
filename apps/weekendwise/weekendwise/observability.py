"""Structured, privacy-safe logging for WeekendWise (MVP-09).

One JSON object per line on stdout. Cloud Run sends these to Cloud Logging, which reads `severity` and
`message` and keeps the other fields in jsonPayload, so you can filter on e.g. jsonPayload.requestId.

What is logged: request ID, workflow stage, model ID, latency, token counts, retrieval result counts,
tool counts, result status, and an error category.
What is never logged: user prompts or notes, guide text, model output, model reasoning, credentials.
"""
from __future__ import annotations

import contextvars
import json
import logging
import sys
import time
from datetime import datetime, timezone

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")
log = logging.getLogger("weekendwise")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "severity": record.levelname,
            "message": record.getMessage(),
            "time": datetime.fromtimestamp(record.created, timezone.utc).isoformat(timespec="milliseconds"),
            "requestId": request_id_var.get(),
        }
        entry.update(getattr(record, "fields", {}))
        return json.dumps(entry, ensure_ascii=False, default=str)


class StdoutHandler(logging.StreamHandler):
    """Always writes to the current sys.stdout (Cloud Run collects stdout)."""

    def emit(self, record: logging.LogRecord) -> None:
        self.stream = sys.stdout
        super().emit(record)


def setup_logging(level: str = "INFO") -> None:
    if any(isinstance(h.formatter, JsonFormatter) for h in log.handlers):
        return
    handler = StdoutHandler()
    handler.setFormatter(JsonFormatter())
    log.addHandler(handler)
    log.setLevel(level)
    log.propagate = False


def event(message: str, severity: int = logging.INFO, **fields) -> None:
    """Log one structured event. Only pass safe fields (no prompts, guide text, or secrets)."""
    log.log(severity, message, extra={"fields": fields})


def error_category(exc: BaseException) -> str:
    return type(exc).__name__


class TimedRetriever:
    """Wraps a Retriever and logs latency and result counts (never the query text)."""

    def __init__(self, inner):
        self.inner = inner

    def retrieve(self, query: str, city_id: str, top_k: int | None = None):
        start = time.monotonic()
        try:
            res = self.inner.retrieve(query, city_id, top_k=top_k)
        except Exception as exc:
            event("retrieval failed", logging.ERROR, stage="retrieve", component="firestore", cityId=city_id,
                  latencyMs=int((time.monotonic() - start) * 1000), errorCategory=error_category(exc))
            raise
        event("retrieval", stage="retrieve", component="firestore", cityId=city_id, status=res.status,
              resultCount=len(res.chunks), nearestDistance=res.nearest_distance,
              latencyMs=int((time.monotonic() - start) * 1000))
        return res


class TimedVertex:
    """Wraps a VertexClient and logs model ID, latency, and token usage (never prompts or output)."""

    def __init__(self, inner):
        self.inner = inner

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def generate_text(self, prompt: str, **kw):
        start = time.monotonic()
        try:
            r = self.inner.generate_text(prompt, **kw)
        except Exception as exc:
            event("model call failed", logging.ERROR, stage="draft", component="vertex-ai",
                  modelId=self.inner.settings.generation_model_id, latencyMs=int((time.monotonic() - start) * 1000),
                  errorCategory=error_category(exc))
            raise
        event("model call", stage="draft", component="vertex-ai", modelId=r.model_id, latencyMs=r.latency_ms,
              inputTokens=r.input_tokens, outputTokens=r.output_tokens, thoughtTokens=r.thought_tokens,
              finishReason=r.finish_reason)
        return r

    def embed_query(self, text: str):
        start = time.monotonic()
        try:
            v = self.inner.embed_query(text)
        except Exception as exc:
            event("embedding failed", logging.ERROR, stage="retrieve", component="vertex-ai",
                  modelId=self.inner.settings.embedding_model_id, latencyMs=int((time.monotonic() - start) * 1000),
                  errorCategory=error_category(exc))
            raise
        event("embedding", stage="retrieve", component="vertex-ai", modelId=self.inner.settings.embedding_model_id,
              latencyMs=int((time.monotonic() - start) * 1000))
        return v
