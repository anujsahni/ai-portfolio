"""Grounded retrieval from Firestore (MVP-05).

One bounded nearest-neighbour query per request:
  guide_chunks WHERE cityId == <city> AND active == true, nearest on `embedding`, top-k (≤ max).
Results farther than the calibrated distance are dropped; if nothing is close enough the
result is INSUFFICIENT_EVIDENCE rather than a forced match. Server-side only; the browser
never talks to Firestore.
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Protocol

from .config import Settings
from .errors import WeekendWiseError

OK = "ok"
INSUFFICIENT_EVIDENCE = "insufficient_evidence"
UNSUPPORTED_CITY = "unsupported_city"
MAX_QUERY_CHARS = 1000


class RetrievalError(WeekendWiseError):
    """Firestore retrieval failed (index, permission, timeout, or database problem)."""


class Embedder(Protocol):
    def embed_query(self, text: str) -> list[float]: ...


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    source_id: str
    city_id: str
    title: str
    section: str
    content_type: str
    last_reviewed: str
    text: str
    distance: float


@dataclass
class RetrievalResult:
    status: str
    query: str
    city_id: str
    chunks: list[RetrievedChunk] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)  # stale/conflict warnings for the planner and UI
    reason: str = ""
    nearest_distance: float | None = None  # closest match even when rejected (for diagnostics)
    max_distance: float | None = None
    top_k: int = 0
    latency_ms: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


class Retriever:
    def __init__(self, settings: Settings, db, embedder: Embedder, *, today: date | None = None):
        self.s = settings
        self.db = db
        self.embedder = embedder
        self.today = today or date.today()

    def retrieve(self, query: str, city_id: str, top_k: int | None = None) -> RetrievalResult:
        s = self.s
        query = (query or "").strip()
        k = max(1, min(top_k or s.retrieval_top_k, s.retrieval_max_top_k))
        base = RetrievalResult(status=OK, query=query, city_id=city_id, max_distance=s.retrieval_max_distance, top_k=k)

        if city_id not in s.supported_city_ids:
            base.status, base.reason = UNSUPPORTED_CITY, (
                f"'{city_id}' isn't a supported city. Supported: {', '.join(s.supported_city_ids)}."
            )
            return base
        if not query:
            base.status, base.reason = INSUFFICIENT_EVIDENCE, "The question is empty."
            return base
        if len(query) > MAX_QUERY_CHARS:
            query = query[:MAX_QUERY_CHARS]
            base.query = query

        start = time.monotonic()
        vector = self.embedder.embed_query(query)
        hits = self._nearest(city_id, vector, k)
        base.latency_ms = int((time.monotonic() - start) * 1000)

        # Defence in depth: the query already filters, but never pass through wrong-city or inactive chunks.
        hits = [h for h in hits if h["cityId"] == city_id and h["active"] is True]
        if not hits:
            base.status, base.reason = INSUFFICIENT_EVIDENCE, "No guides are loaded for this city (run make seed)."
            return base

        base.nearest_distance = min(h["distance"] for h in hits)
        kept = [self._chunk(h) for h in hits if h["distance"] <= s.retrieval_max_distance]
        if not kept:
            base.status = INSUFFICIENT_EVIDENCE
            base.reason = (
                f"No guide passage is close enough to the question (closest distance {base.nearest_distance:.3f}; "
                f"limit {s.retrieval_max_distance:.3f})."
            )
            return base

        base.chunks = kept
        base.notes = self._source_notes(kept)
        return base

    # ------------------------------------------------------------------ Firestore

    def _nearest(self, city_id: str, vector: list[float], k: int) -> list[dict]:
        from google.cloud.firestore_v1.base_query import FieldFilter
        from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
        from google.cloud.firestore_v1.vector import Vector

        query = (
            self.db.collection(self.s.firestore_collection)
            .where(filter=FieldFilter("cityId", "==", city_id))
            .where(filter=FieldFilter("active", "==", True))
            .find_nearest(
                vector_field="embedding",
                query_vector=Vector(vector),
                limit=k,
                distance_measure=DistanceMeasure.COSINE,
                distance_result_field="distance",
            )
        )
        try:
            snaps = list(query.stream(timeout=self.s.firestore_timeout_seconds))
        except Exception as exc:  # translated; never re-raised raw
            raise translate_firestore_error(exc, self.s) from exc
        out = []
        for snap in snaps[:k]:
            d = snap.to_dict() or {}
            d["chunkId"] = d.get("chunkId") or snap.id
            out.append(d)
        return out

    @staticmethod
    def _chunk(h: dict) -> RetrievedChunk:
        return RetrievedChunk(
            chunk_id=h["chunkId"],
            source_id=h["sourceId"],
            city_id=h["cityId"],
            title=h.get("title", ""),
            section=h.get("section", ""),
            content_type=h.get("contentType", ""),
            last_reviewed=h.get("lastReviewed", ""),
            text=h.get("text", ""),
            distance=float(h["distance"]),
        )

    def _source_notes(self, chunks: list[RetrievedChunk]) -> list[str]:
        """Flag stale sources and known conflicts between retrieved sources."""
        notes: list[str] = []
        source_ids = sorted({c.source_id for c in chunks})
        sources = {}
        try:
            refs = [self.db.collection("guide_sources").document(sid) for sid in source_ids]
            sources = {snap.id: (snap.to_dict() or {}) for snap in self.db.get_all(refs) if snap.exists}
        except Exception:  # noqa: BLE001 - notes are best-effort; retrieval still succeeds
            sources = {}
        for sid in source_ids:
            reviewed = next((c.last_reviewed for c in chunks if c.source_id == sid), "")
            try:
                age = (self.today - date.fromisoformat(reviewed)).days
            except ValueError:
                age = None
            if age is not None and age > self.s.source_stale_after_days:
                notes.append(f"{sid} was last reviewed {reviewed} ({age} days ago); treat it as possibly out of date.")
            other = (sources.get(sid) or {}).get("conflictsWith")
            if other:
                newer = " Prefer the more recently reviewed source." if other in source_ids else ""
                notes.append(f"{sid} conflicts with {other}.{newer} Tell the traveler to confirm with official sources.")
        return notes


def translate_firestore_error(exc: Exception, settings: Settings) -> RetrievalError:
    name = type(exc).__name__
    where = f"Firestore {settings.firestore_database}/{settings.firestore_collection}"
    if name == "FailedPrecondition":
        return RetrievalError(
            f"{where}: the vector index is missing, still building, or doesn't match the query.",
            hint="Run make verify (Firestore section); create it with make apply (IAC-04).",
        )
    if name in ("PermissionDenied", "Unauthenticated"):
        return RetrievalError(f"{where}: permission denied.", hint="The runtime identity needs roles/datastore.viewer (IAC-03).")
    if name in ("DeadlineExceeded", "ServiceUnavailable") or "Timeout" in name:
        return RetrievalError(
            f"{where}: no response within {settings.firestore_timeout_seconds:g} seconds.",
            hint="Retry; if it persists, check Firestore status.",
        )
    if name == "NotFound":
        return RetrievalError(f"{where}: database not found.", hint="Run make apply (IAC-04).")
    return RetrievalError(f"{where}: unexpected error ({name}).", hint="See server logs.")
