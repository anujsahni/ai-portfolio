"""WeekendWise web server (MVP-03 / MVP-07 / MVP-09).

Serves the approved screens and one planning endpoint. Everything that touches Google Cloud runs here, on the
server, as the Cloud Run runtime identity (or, locally, by impersonating it). The browser never sees credentials.

  GET  /, /plan, /itinerary, /sources, /architecture   the single-page app
  GET  /static/*                                       CSS, JS, favicon
  GET  /health, /healthz                               liveness (no cloud calls). Use /health from outside:
                                                       Cloud Run's front end reserves /healthz and answers 404
  GET  /readyz                                         readiness: settings load and Firestore answers a 1-document read
  GET  /api/config                                     cities, interests, sample trips, limits (from bundled seed data)
  POST /api/plan                                       runs the planner; streams progress as server-sent events

Abuse and cost controls (per instance): request body ≤ 8 KB, at most PLAN_MAX_CONCURRENT plans at once, at most
PLAN_RATE_PER_CLIENT plans per client per 10 minutes, at most PLAN_DAILY_LIMIT plans per day.
Run locally: make run   ·   Container: uvicorn --factory weekendwise.web.server:create_app
"""
from __future__ import annotations

import asyncio
import contextvars
import json
import logging
import os
import threading
import time
import uuid
from collections import defaultdict, deque
from dataclasses import replace
from datetime import date
from pathlib import Path

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response, StreamingResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from ..config import load_settings
from ..errors import WeekendWiseError
from ..observability import TimedRetriever, TimedVertex, error_category, event, request_id_var, setup_logging
from ..planner import MAX_TRIP_DAYS, WEATHER_WORDS

STATIC = Path(__file__).resolve().parent / "static"
SEED = Path(__file__).resolve().parents[2] / "data" / "seed"
APP_VERSION = os.environ.get("APP_VERSION", "dev")
MAX_BODY_BYTES = 8 * 1024
RATE_WINDOW_SECONDS = 600

CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
       "connect-src 'self'; font-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
SECURITY_HEADERS = {
    "Content-Security-Policy": CSP,
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Permissions-Policy": "geolocation=(), camera=(), microphone=()",
}


def _env_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.environ.get(name, default)))
    except ValueError:
        return default


class Limits:
    """In-memory, per-instance limits. Good enough for a demo with max 2 instances; not a security boundary."""

    def __init__(self, concurrent: int, per_client: int, daily: int, clock=time.monotonic, today=date.today):
        self.sem = threading.BoundedSemaphore(concurrent)
        self.per_client, self.daily = per_client, daily
        self.clock, self.today = clock, today
        self.hits: dict[str, deque] = defaultdict(deque)
        self.day, self.count = None, 0
        self.lock = threading.Lock()

    def admit(self, client: str) -> str | None:
        """Return None if allowed, else a reason code."""
        now = self.clock()
        with self.lock:
            if self.day != self.today():
                self.day, self.count = self.today(), 0
            if self.count >= self.daily:
                return "daily_limit"
            q = self.hits[client]
            while q and now - q[0] > RATE_WINDOW_SECONDS:
                q.popleft()
            if len(q) >= self.per_client:
                return "rate_limited"
            if not self.sem.acquire(blocking=False):
                return "busy"
            q.append(now)
            self.count += 1
        return None

    def release(self) -> None:
        self.sem.release()


class Runtime:
    """Lazily builds the planner so /healthz works before credentials are needed."""

    def __init__(self):
        self._lock = threading.RLock()
        self._planner = None
        self._db = None
        self.settings = None
        self._ready_cache: tuple[float, bool, str] | None = None

    def _settings(self):
        if self.settings is None:
            s = load_settings()
            impersonate = os.environ.get("WEEKENDWISE_RUN_AS")  # local only: e.g. "run" → weekendwise-run@…
            if impersonate and not s.impersonate_service_account:
                from ..gcp import service_account
                s = replace(s, impersonate_service_account=service_account(s.project_id, impersonate))
            self.settings = s
        return self.settings

    def db(self):
        with self._lock:
            if self._db is None:
                from ..gcp import firestore_client
                s = self._settings()
                self._db = firestore_client(s.project_id, s.firestore_database, impersonate=s.impersonate_service_account)
            return self._db

    def planner(self):
        with self._lock:
            if self._planner is None:
                from ..planner import Planner
                from ..retrieval import Retriever
                from ..vertex import VertexClient
                s = self._settings()
                vertex = TimedVertex(VertexClient(s))
                self._planner = Planner(s, TimedRetriever(Retriever(s, self.db(), vertex)), vertex)
            return self._planner

    def ready(self) -> tuple[bool, str]:
        now = time.monotonic()
        if self._ready_cache and now - self._ready_cache[0] < 30:
            return self._ready_cache[1], self._ready_cache[2]
        try:
            s = self._settings()
            docs = list(self.db().collection(s.firestore_collection).limit(1).get(timeout=s.firestore_timeout_seconds))
            ok, detail = (True, "ok") if docs else (False, "corpus_empty")
        except Exception as exc:  # report a category only, never the message (may contain project details)
            ok, detail = False, error_category(exc)
        self._ready_cache = (now, ok, detail)
        return ok, detail


def _load_seed(coll: str) -> list[dict]:
    return [{"id": p.stem, **json.loads(p.read_text(encoding="utf-8"))} for p in sorted((SEED / coll).glob("*.json"))]


def build_config(supported: tuple[str, ...]) -> dict:
    cities = []
    for c in _load_seed("cities"):
        if c["id"] not in supported or not c.get("supported"):
            continue
        cities.append({"id": c["id"], "name": c["name"], "state": c.get("state", ""), "tagline": c.get("tagline", ""),
                       "trending": bool(c.get("trending")), "weatherShort": c.get("weatherNotes", "").split(";")[0].strip().rstrip("."),
                       "seededConditionDates": c.get("seededConditionDates", [])})
    order = {"san-francisco": 0}
    cities.sort(key=lambda c: (order.get(c["id"], 1), c["name"]))
    interests = sorted(({"id": i["id"], "label": i["label"], "icon": i.get("icon", ""), "displayOrder": i.get("displayOrder", 99),
                         "selectedByDefault": bool(i.get("selectedByDefault"))} for i in _load_seed("interests") if i.get("active", True)),
                       key=lambda i: i["displayOrder"])
    categories = sorted(({"id": b["id"], "label": b["label"], "displayOrder": b.get("displayOrder", 99)} for b in _load_seed("budget_categories")),
                        key=lambda b: b["displayOrder"])
    short = {"SCENARIO-01": "SF art & coffee", "SCENARIO-02": "SF rainy Saturday", "SCENARIO-03": "SF tight budget",
             "SCENARIO-04": "Portland rain", "SCENARIO-05": "Santa Cruz coast", "SCENARIO-06": "Napa hot day"}
    samples = [{"id": s["id"], "title": s["title"], "short": short.get(s["id"][:11], s["title"]),
                "request": {k: s["request"][k] for k in ("cityId", "startDate", "endDate", "travelers", "budget", "interestIds", "constraints", "notes")}}
               for s in _load_seed("trip_scenarios") if s["request"].get("cityId") in supported]
    return {
        "version": APP_VERSION, "cities": cities, "interests": interests, "budgetCategories": categories, "samples": samples,
        "defaults": {"startDate": "2027-05-14", "endDate": "2027-05-16"},
        "limits": {"maxTripDays": MAX_TRIP_DAYS, "minBudget": 50, "maxBudget": 10000, "maxTravelers": 8},
        "weatherPattern": WEATHER_WORDS.pattern,
    }


def client_key(request: Request) -> str:
    # Cloud Run's front end appends the caller's address to X-Forwarded-For; locally use the socket peer.
    fwd = request.headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "unknown")


def _error(status: int, code: str, message: str, request_id: str, errors: list[str] | None = None) -> JSONResponse:
    body = {"status": "error", "code": code, "message": message, "requestId": request_id}
    if errors:
        body["errors"] = errors
    return JSONResponse(body, status_code=status)


LIMIT_MESSAGES = {
    "busy": (503, "The planner is busy with other trips. Please try again in a few seconds."),
    "rate_limited": (429, "You’ve made several plans in a short time. Please wait a few minutes and try again."),
    "daily_limit": (429, "This demo has reached its daily planning limit. Please try again tomorrow."),
}


def create_app(runtime: Runtime | None = None, limits: Limits | None = None) -> Starlette:
    setup_logging(os.environ.get("LOG_LEVEL", "INFO"))
    runtime = runtime or Runtime()
    limits = limits or Limits(_env_int("PLAN_MAX_CONCURRENT", 3), _env_int("PLAN_RATE_PER_CLIENT", 6), _env_int("PLAN_DAILY_LIMIT", 30))
    supported = tuple(c.strip() for c in os.environ.get("SUPPORTED_CITY_IDS", "san-francisco,portland,santa-cruz,napa-valley").split(",") if c.strip())
    app_config = build_config(supported)

    async def page(request: Request) -> Response:
        return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})

    async def healthz(request: Request) -> Response:
        return JSONResponse({"status": "ok", "version": APP_VERSION})

    async def readyz(request: Request) -> Response:
        ok, detail = await asyncio.to_thread(runtime.ready)
        return JSONResponse({"status": "ready" if ok else "not_ready", "detail": detail, "version": APP_VERSION},
                            status_code=200 if ok else 503)

    async def api_config(request: Request) -> Response:
        return JSONResponse(app_config, headers={"Cache-Control": "public, max-age=300"})

    async def api_plan(request: Request) -> Response:
        rid = request.headers.get("x-request-id", "")[:64] or uuid.uuid4().hex[:16]
        request_id_var.set(rid)
        raw = await request.body()
        if len(raw) > MAX_BODY_BYTES:
            return _error(413, "too_large", "That request is too large.", rid)
        try:
            body = json.loads(raw or b"{}")
            if not isinstance(body, dict):
                raise ValueError
        except ValueError:
            return _error(400, "bad_json", "The request wasn't valid JSON.", rid)

        denied = limits.admit(client_key(request))
        if denied:
            status, message = LIMIT_MESSAGES[denied]
            event("plan rejected", logging.WARNING, stage="admit", status=denied)
            return _error(status, denied, message, rid)

        try:
            planner = await asyncio.to_thread(runtime.planner)
        except Exception as exc:  # config, credentials, or client set-up problems
            limits.release()
            event("planner unavailable", logging.ERROR, stage="startup", errorCategory=error_category(exc))
            return _error(503, "unavailable", "The planner isn't available right now. Please try again shortly.", rid)

        queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_running_loop()
        summary = {"cityId": body.get("cityId"), "travelers": body.get("travelers")}

        def worker() -> None:
            start = time.monotonic()
            status, category = "error", None
            try:
                for kind, data in planner.plan_stream(body):
                    if kind == "step":
                        event("stage", stage=data.get("node"), status=data.get("status"))
                    else:
                        status = data.get("status", "error")
                        u = data.get("usage", {})
                        summary.update(modelCalls=u.get("modelCalls"), toolCalls=u.get("toolCalls"),
                                       retrievalQueries=u.get("retrievalQueries"), revisions=u.get("revisions"),
                                       citations=len(data.get("citations", [])), budgetStatus=(data.get("budget") or {}).get("status"),
                                       reviewOutcome=(data.get("review") or {}).get("outcome"))
                    loop.call_soon_threadsafe(queue.put_nowait, (kind, data))
            except WeekendWiseError as exc:
                category = error_category(exc)
                loop.call_soon_threadsafe(queue.put_nowait, ("error", {"message": exc.message, "hint": None, "requestId": rid}))
            except Exception as exc:  # never leak a stack trace to the browser
                category = error_category(exc)
                logging.getLogger("weekendwise").exception("planner crashed", extra={"fields": {"errorCategory": category}})
                loop.call_soon_threadsafe(queue.put_nowait, ("error", {"message": "Something went wrong while planning. Please try again.", "requestId": rid}))
            finally:
                limits.release()
                event("plan finished", logging.INFO if category is None else logging.ERROR, stage="respond", status=status,
                      errorCategory=category, latencyMs=int((time.monotonic() - start) * 1000), **summary)
                loop.call_soon_threadsafe(queue.put_nowait, None)

        ctx = contextvars.copy_context()
        loop.run_in_executor(None, ctx.run, worker)

        async def stream():
            yield f": request {rid}\n\n"
            while True:
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                if item is None:
                    break
                kind, data = item
                yield f"event: {kind}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

        return StreamingResponse(stream(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-store", "X-Request-ID": rid, "X-Accel-Buffering": "no"})

    async def not_found(request: Request, exc) -> Response:
        if request.url.path.startswith("/api/"):
            return _error(404, "not_found", "Not found.", "-")
        return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})  # unknown pages → app router

    routes = [
        Route("/", page), Route("/plan", page), Route("/itinerary", page), Route("/sources", page), Route("/architecture", page),
        Route("/health", healthz), Route("/healthz", healthz), Route("/readyz", readyz),
        Route("/api/config", api_config), Route("/api/plan", api_plan, methods=["POST"]),
        Route("/favicon.ico", lambda r: FileResponse(STATIC / "favicon.svg", media_type="image/svg+xml")),
        Mount("/static", app=StaticFiles(directory=STATIC), name="static"),
    ]
    app = Starlette(routes=routes, exception_handlers={404: not_found}, middleware=[Middleware(SecurityHeaders)])
    app.state.runtime, app.state.limits = runtime, limits
    return app


class SecurityHeaders:
    """Adds security headers to every HTTP response (pure ASGI, so streaming isn't buffered)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                present = {k.lower() for k, _ in headers}
                for k, v in SECURITY_HEADERS.items():
                    if k.lower().encode() not in present:
                        headers.append((k.lower().encode(), v.encode()))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)

