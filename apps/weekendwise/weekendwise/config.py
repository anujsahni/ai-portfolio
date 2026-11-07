"""Server-side configuration for Vertex AI.

Values come from environment variables, falling back to a local `.env` file.
Model IDs live here only; other modules must not hard-code them.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .errors import ConfigError

THINKING_LEVELS = ("MINIMAL", "LOW", "MEDIUM", "HIGH")
FIRESTORE_MAX_VECTOR_DIMENSION = 2048


@dataclass(frozen=True)
class Settings:
    project_id: str
    generation_location: str
    embedding_location: str
    generation_model_id: str
    embedding_model_id: str
    embedding_dimension: int
    thinking_level: str = "LOW"
    max_prompt_chars: int = 24000
    max_output_tokens: int = 4096
    max_embedding_batch: int = 50
    request_timeout_seconds: float = 45.0
    model_retry_attempts: int = 1
    impersonate_service_account: str | None = None
    # Retrieval (MVP-05)
    supported_city_ids: tuple[str, ...] = ("san-francisco", "portland", "santa-cruz", "napa-valley")
    firestore_database: str = "(default)"
    firestore_collection: str = "guide_chunks"
    retrieval_top_k: int = 4
    retrieval_max_top_k: int = 5
    retrieval_max_distance: float = 0.34  # cosine; calibrated 2026-11-06: matches ≤0.306, off-topic ≥0.386
    firestore_timeout_seconds: float = 10.0
    source_stale_after_days: int = 365
    # Planner (MVP-06)
    planner_max_model_calls: int = 3       # draft + one revision + one JSON-repair attempt
    planner_max_retrieval_queries: int = 5
    planner_max_evidence: int = 10
    planner_deadline_seconds: float = 150.0


def read_dotenv(path: Path) -> dict[str, str]:
    """Minimal KEY=VALUE reader; ignores comments and blank lines."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.split(" #", 1)[0].strip().strip('"').strip("'")
    return values


def load_settings(env: Mapping[str, str] | None = None, dotenv_path: str | Path = ".env") -> Settings:
    """Build Settings, reporting every problem at once."""
    merged = {**read_dotenv(Path(dotenv_path)), **(os.environ if env is None else env)}
    problems: list[str] = []

    def get(name: str, default: str | None = None) -> str:
        value = (merged.get(name) or "").strip()
        if value:
            return value
        if default is None:
            problems.append(f"{name} is not set")
            return ""
        return default

    def get_int(name: str, default: int, low: int, high: int) -> int:
        raw = get(name, str(default))
        try:
            value = int(raw)
        except ValueError:
            problems.append(f"{name} must be a whole number (got {raw!r})")
            return default
        if not low <= value <= high:
            problems.append(f"{name} must be between {low} and {high} (got {value})")
        return value

    def get_required_int(name: str, low: int, high: int) -> int:
        if not (merged.get(name) or "").strip():
            problems.append(f"{name} is not set")
            return 0
        return get_int(name, 0, low, high)

    def get_float(name: str, default: float, low: float, high: float) -> float:
        raw = get(name, str(default))
        try:
            value = float(raw)
        except ValueError:
            problems.append(f"{name} must be a number (got {raw!r})")
            return default
        if not low <= value <= high:
            problems.append(f"{name} must be between {low} and {high} (got {value})")
        return value

    region = get("GCP_REGION", "us-central1")
    settings = Settings(
        project_id=get("GCP_PROJECT_ID"),
        generation_location=get("VERTEX_GENERATION_LOCATION", "global"),
        embedding_location=get("VERTEX_EMBEDDING_LOCATION", region),
        generation_model_id=get("VERTEX_GENERATION_MODEL_ID"),
        embedding_model_id=get("VERTEX_EMBEDDING_MODEL_ID"),
        embedding_dimension=get_required_int("VERTEX_EMBEDDING_DIMENSION", 1, FIRESTORE_MAX_VECTOR_DIMENSION),
        thinking_level=get("VERTEX_THINKING_LEVEL", "LOW").upper(),
        max_prompt_chars=get_int("MAX_PROMPT_CHARS", 24000, 500, 200000),
        max_output_tokens=get_int("MAX_OUTPUT_TOKENS", 4096, 16, 16384),
        max_embedding_batch=get_int("MAX_EMBEDDING_BATCH", 50, 1, 250),
        request_timeout_seconds=get_float("REQUEST_TIMEOUT_SECONDS", 45.0, 1.0, 300.0),
        model_retry_attempts=get_int("MODEL_RETRY_ATTEMPTS", 1, 0, 3),
        impersonate_service_account=(merged.get("VERTEX_IMPERSONATE_SERVICE_ACCOUNT") or "").strip() or None,
        supported_city_ids=tuple(c.strip() for c in get("SUPPORTED_CITY_IDS", "san-francisco,portland,santa-cruz,napa-valley").split(",") if c.strip()),
        firestore_database=get("FIRESTORE_DATABASE_ID", "(default)"),
        firestore_collection=get("FIRESTORE_COLLECTION", "guide_chunks"),
        retrieval_top_k=get_int("RETRIEVAL_TOP_K", 4, 1, 10),
        retrieval_max_top_k=get_int("RETRIEVAL_MAX_TOP_K", 5, 1, 10),
        retrieval_max_distance=get_float("RETRIEVAL_MAX_DISTANCE", 0.34, 0.0, 2.0),
        firestore_timeout_seconds=get_float("FIRESTORE_TIMEOUT_SECONDS", 10.0, 1.0, 60.0),
        source_stale_after_days=get_int("SOURCE_STALE_AFTER_DAYS", 365, 1, 3650),
        planner_max_model_calls=get_int("PLANNER_MAX_MODEL_CALLS", 3, 1, 5),
        planner_max_retrieval_queries=get_int("PLANNER_MAX_RETRIEVAL_QUERIES", 5, 1, 8),
        planner_max_evidence=get_int("PLANNER_MAX_EVIDENCE", 10, 2, 20),
        planner_deadline_seconds=get_float("PLANNER_DEADLINE_SECONDS", 150.0, 10.0, 600.0),
    )
    if settings.retrieval_top_k > settings.retrieval_max_top_k:
        problems.append("RETRIEVAL_TOP_K must not exceed RETRIEVAL_MAX_TOP_K")
    if settings.thinking_level not in THINKING_LEVELS:
        problems.append(f"VERTEX_THINKING_LEVEL must be one of {', '.join(THINKING_LEVELS)}")
    if problems:
        raise ConfigError(
            "WeekendWise configuration is incomplete: " + "; ".join(problems) + ".",
            hint="Set these in .env (copy .env.example) or as environment variables.",
        )
    return settings
