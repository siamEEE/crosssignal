"""Thin HTTP API over the CrossSignal engine, for the Culture Radio frontend.

    uv run --env-file .env uvicorn crosssignal.api:app --port 8000

Endpoints only translate JSON <-> engine types; all logic lives in the
engine modules. Qloo answers and catalog lookups are cached in memory
(private server-side caching is allowed by the hackathon terms). The API
key never leaves this process: it is not in any response or log line.
If `frontend/dist` exists it is served at `/`.
"""

import threading
import time
from collections import deque
from collections.abc import Callable, Hashable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import httpx
from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from crosssignal import culture, genres
from crosssignal.agent import AgentUnavailable, agent_configured, run_agent
from crosssignal.catalog import search_tracks
from crosssignal.config import ConfigError, load_settings
from crosssignal.culture import Kind
from crosssignal.engine import (
    MAX_ARTISTS,
    MAX_LIKED,
    MAX_SIGNALS,
    Engine,
    Feedback,
    InvalidRequest,
    Result,
    Signal,
)
from crosssignal.interpret import interpret_deterministic
from crosssignal.models import ProviderErrorKind, RecommendationError, Track
from crosssignal.qloo import QlooClient
from crosssignal.ranking import DISCOVERY_MODES, ERAS, Preferences, Ranked

FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
QLOO_MIN_INTERVAL = 0.12  # stay under the observed 10 requests/second
QLOO_TTL = 6 * 3600
CATALOG_TTL = 3600
CATALOG_SEARCH_LIMIT = 40


class TTLCache:
    """Tiny thread-safe cache. Exceptions are never cached."""

    def __init__(self, ttl: float, max_items: int = 2000) -> None:
        self._ttl, self._max = ttl, max_items
        self._items: dict[Hashable, tuple[float, object]] = {}
        self._lock = threading.Lock()

    def get_or_set(self, key: Hashable, produce: Callable[[], object]) -> object:
        now = time.monotonic()
        with self._lock:
            hit = self._items.get(key)
            if hit and now - hit[0] < self._ttl:
                return hit[1]
        value = produce()
        with self._lock:
            if len(self._items) >= self._max:
                self._items.pop(next(iter(self._items)))
            self._items[key] = (now, value)
        return value


class CachedQloo:
    """QlooClient with an in-memory cache, same method signatures."""

    def __init__(self, client: QlooClient, ttl: float = QLOO_TTL) -> None:
        self._client = client
        self._cache = TTLCache(ttl)

    def _key(self, name: str, args: tuple, kwargs: dict) -> Hashable:
        freeze = lambda v: tuple(v) if isinstance(v, list | tuple) else v
        return (name, tuple(map(freeze, args)),
                tuple(sorted((k, freeze(v)) for k, v in kwargs.items())))  # fmt: skip

    def search(self, *args, **kwargs):
        key = self._key("search", args, kwargs)
        return self._cache.get_or_set(key, lambda: self._client.search(*args, **kwargs))

    def tags(self, *args, **kwargs):
        key = self._key("tags", args, kwargs)
        return self._cache.get_or_set(key, lambda: self._client.tags(*args, **kwargs))

    def artist_insights(self, *args, **kwargs):
        key = self._key("insights", args, kwargs)
        return self._cache.get_or_set(
            key, lambda: self._client.artist_insights(*args, **kwargs)
        )


@dataclass
class Services:
    qloo: QlooClient | CachedQloo | None
    engine: Engine | None
    config_problem: str | None = None


def build_services() -> Services:
    try:
        settings = load_settings()
    except ConfigError as exc:
        return Services(None, None, str(exc))
    if not settings.qloo.configured:
        return Services(None, None, "QLOO_API_KEY is not set")
    qloo = CachedQloo(QlooClient(settings.qloo, min_interval=QLOO_MIN_INTERVAL))
    http = httpx.Client(timeout=15)
    catalog_cache = TTLCache(CATALOG_TTL)

    def lookup(artist: str) -> list[Track]:
        return catalog_cache.get_or_set(
            ("itunes", artist),
            lambda: search_tracks(artist, client=http, limit=CATALOG_SEARCH_LIMIT),
        )

    return Services(qloo, Engine(qloo, lookup))


# --- request / response schemas -----------------------------------------------


class SignalIn(BaseModel):
    id: str = Field(min_length=1, max_length=200)
    kind: Kind
    name: str = Field(min_length=1, max_length=200)
    category: str = Field(max_length=40)
    qloo_type: str = Field(max_length=80)

    def to_signal(self) -> Signal:
        return Signal(self.id, self.kind, self.name, self.category, self.qloo_type)


class PreferencesIn(BaseModel):
    preferred: list[str] = Field(default=[], max_length=100)
    open_to: list[str] = Field(default=[], max_length=100)
    avoided: list[str] = Field(default=[], max_length=100)
    era: str | None = Field(default=None, max_length=20)  # legacy single-era clients
    eras: list[str] | None = Field(default=None, max_length=len(ERAS))
    discovery: Literal["familiar", "balanced", "adventurous"] = "balanced"


class FeedbackIn(BaseModel):
    liked: list[SignalIn] = Field(default=[], max_length=MAX_LIKED)
    disliked: list[str] = Field(default=[], max_length=50)


class DiscoverIn(BaseModel):
    signals: list[SignalIn] = Field(max_length=MAX_SIGNALS)
    preferences: PreferencesIn = PreferencesIn()
    feedback: FeedbackIn = FeedbackIn()
    page: int = Field(default=1, ge=1, le=20)
    max_artists: int = Field(default=MAX_ARTISTS, ge=1, le=MAX_ARTISTS)
    exclude_artists: list[str] = Field(default=[], max_length=160)


class AgentTurnIn(BaseModel):
    role: Literal["user", "model"]
    content: str = Field(max_length=900)


class AgentIn(BaseModel):
    message: str = Field(min_length=1, max_length=600)
    signals: list[SignalIn] = Field(default=[], max_length=MAX_SIGNALS)
    preferences: PreferencesIn = PreferencesIn()
    feedback: FeedbackIn = FeedbackIn()
    history: list[AgentTurnIn] = Field(default=[], max_length=6)
    seen: list[str] = Field(default=[], max_length=160)
    page: int = Field(default=1, ge=1, le=20)


class InterpretIn(BaseModel):
    text: str = Field(min_length=1, max_length=600)


# --- serialisation -----------------------------------------------------------


def _candidate(c: culture.Candidate) -> dict:
    return {
        "id": c.id, "kind": c.kind, "name": c.name, "category": c.category,
        "qloo_type": c.qloo_type, "type_label": c.type_label, "year": c.year,
        "disambiguation": c.disambiguation, "image_url": c.image_url,
        "popularity": c.popularity,
    }  # fmt: skip


def _resolution(r: culture.Resolution) -> dict:
    return {
        "query": r.query,
        "category": r.category,
        "match": r.match,
        "candidates": [_candidate(c) for c in r.candidates],
    }


def _track(t: Track) -> dict:
    return {
        "title": t.title, "artist": t.artist, "album": t.album, "year": t.year,
        "url": t.url, "artwork_small": t.artwork_small,
        "artwork_large": t.artwork_large, "preview_url": t.preview_url,
        "genre": t.genre,
    }  # fmt: skip


def _artist(item: Ranked) -> dict:
    c, verdict = item.candidate, item.verdict
    return {
        "id": c.entity_id,
        "name": c.name,
        "image_url": c.image_url,
        "source": c.source,
        "popularity": c.popularity,
        "genre": {
            "fit": verdict.fit,
            "support": verdict.support,
            "related_only": verdict.related_only,
            "matched": [
                {"id": g, "label": genres.BY_ID[g].label} for g in verdict.matched
            ],
            "qloo_tags": [name for _, name in c.genre_tags],
            "catalog_genre": item.catalog_genre,
        },
        "era": (
            {"in_era": item.era.in_era, "dated": item.era.dated}
            if item.era is not None
            else None
        ),
        "evidence": [
            {
                "signal_id": e.signal_id,
                "signal_name": e.signal_name,
                "category": e.interest.category,
                "rank": e.rank,
                "affinity": e.affinity,
                "explained_share": e.explained_share,
            }
            for e in c.evidence
        ],
        "tracks": [_track(t) for t in item.tracks],
    }


def _signal(s: Signal) -> dict:
    return {"id": s.id, "kind": s.kind, "name": s.name, "category": s.category,
            "qloo_type": s.qloo_type}  # fmt: skip


def _result(result: Result) -> dict:
    tally = result.tally
    prefs = result.preferences
    return {
        "status": result.status,
        "page": result.page,
        "notices": result.notices,
        "signals": [_signal(s) for s in result.signals],
        "tag_signals": [_signal(s) for s in result.tag_signals],
        "preferences": {
            "preferred": list(prefs.preferred),
            "open_to": list(prefs.open_to),
            "avoided": list(prefs.avoided),
            "era": prefs.eras[0] if len(prefs.eras) == 1 else None,
            "eras": list(prefs.eras),
            "discovery": prefs.discovery,
        },
        "tally": {
            "qloo_candidates": tally.qloo_candidates,
            "avoided": tally.avoided,
            "mismatched": tally.mismatched,
            "conflicting": tally.conflicting,
            "no_catalog_match": tally.no_catalog_match,
            "catalog_errors": tally.catalog_errors,
            "lookups": tally.lookups,
            "fallback_used": tally.fallback_used,
            "excluded": tally.excluded_names,
        },
        "artists": [_artist(item) for item in result.picks],
    }


# --- app ---------------------------------------------------------------------

UPSTREAM_STATUS = {
    ProviderErrorKind.NOT_CONFIGURED: 503,
    ProviderErrorKind.RATE_LIMIT: 429,
    ProviderErrorKind.TIMEOUT: 504,
}
ERROR_MESSAGES = {
    ProviderErrorKind.AUTH: "Qloo rejected the server's API key.",
    ProviderErrorKind.RATE_LIMIT: "Qloo is rate limiting requests. Try again shortly.",
    ProviderErrorKind.TIMEOUT: "Qloo took too long to respond.",
    ProviderErrorKind.UNAVAILABLE: "Qloo couldn't be reached.",
    ProviderErrorKind.MALFORMED: "Qloo sent a response CrossSignal couldn't read.",
    ProviderErrorKind.BAD_REQUEST: "Qloo rejected the request.",
    ProviderErrorKind.NOT_CONFIGURED: "Live recommendations aren't configured on "
    "this server (no Qloo API key).",
}


def _error(status: int, kind: str, message: str) -> JSONResponse:
    return JSONResponse({"error": {"kind": kind, "message": message}}, status)


def create_app(services: Services | None = None) -> FastAPI:
    app = FastAPI(title="CrossSignal Culture Radio API", version="0.1.0")
    app.state.services = services
    capacity = threading.BoundedSemaphore(4)
    recent_requests: deque[float] = deque()

    @app.middleware("http")
    async def request_limits(request: Request, call_next):
        # Bound upstream work per process; reject bursts rather than queueing
        # unbounded paid-provider requests. No client IP or taste data stored.
        expensive = request.url.path in {
            "/api/search", "/api/interpret", "/api/discover", "/api/agent/chat"
        }
        acquired = False
        if expensive:
            origin = request.headers.get("origin")
            if origin and origin.rstrip("/") != str(request.base_url).rstrip("/"):
                return _error(403, "invalid_request", "Cross-origin requests are not allowed.")
            now = time.monotonic()
            while recent_requests and now - recent_requests[0] >= 60:
                recent_requests.popleft()
            if len(recent_requests) >= 60:
                return _error(429, "rate_limit", "The radio is busy. Try again shortly.")
            recent_requests.append(now)
            size = 0
            chunks = []
            async for chunk in request.stream():
                size += len(chunk)
                if size > 32_768:
                    return _error(413, "invalid_request", "Request is too large.")
                chunks.append(chunk)
            request._body = b"".join(chunks)
        if expensive:
            acquired = capacity.acquire(blocking=False)
            if not acquired:
                return _error(429, "rate_limit", "The radio is busy. Try again shortly.")
        try:
            response = await call_next(request)
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            return response
        finally:
            if acquired:
                capacity.release()

    def svc() -> Services:
        if app.state.services is None:
            app.state.services = build_services()
        return app.state.services

    def live() -> tuple[QlooClient | CachedQloo, Engine]:
        s = svc()
        if s.qloo is None or s.engine is None:
            raise RecommendationError(
                ProviderErrorKind.NOT_CONFIGURED, "not configured"
            )
        return s.qloo, s.engine

    @app.exception_handler(RecommendationError)
    async def upstream_error(request: Request, exc: RecommendationError):
        return _error(
            UPSTREAM_STATUS.get(exc.kind, 502), exc.kind, ERROR_MESSAGES[exc.kind]
        )

    @app.exception_handler(RequestValidationError)
    async def invalid_body(request: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        where = ".".join(str(p) for p in first.get("loc", ()) if p != "body")
        return _error(422, "invalid_request", f"{where}: {first.get('msg', 'invalid')}")

    @app.exception_handler(InvalidRequest)
    async def invalid_request(request: Request, exc: InvalidRequest):
        return _error(422, "invalid_request", str(exc))

    @app.exception_handler(ValueError)
    async def invalid_value(request: Request, exc: ValueError):
        return _error(422, "invalid_request", str(exc))

    @app.get("/api/health")
    def health() -> dict:
        s = svc()
        return {
            "status": "ok",
            "qloo_configured": s.qloo is not None,
            "config_problem": s.config_problem,
            "interpreter": "deterministic",
            "agent_configured": agent_configured(),
        }

    @app.get("/api/categories")
    def categories() -> list[dict]:
        return [{"id": c.id, "label": c.label, "hint": c.hint, "kind": c.kind}
                for c in culture.CATEGORIES]  # fmt: skip

    @app.get("/api/featured")
    def featured() -> list[dict]:
        return [
            {"id": c.id, "title": c.title, "blurb": c.blurb, "accent": c.accent,
             "items": [{"query": i.query, "category": i.category} for i in c.items]}
            for c in culture.FEATURED
        ]  # fmt: skip

    @app.get("/api/genres")
    def genre_options() -> dict:
        return {
            "genres": genres.tree(),
            "eras": list(ERAS),
            "discovery_modes": list(DISCOVERY_MODES),
            "limits": {"signals": MAX_SIGNALS, "liked": MAX_LIKED},
        }

    @app.get("/api/search")
    def search(
        q: str = Query(min_length=1, max_length=120),
        category: str | None = Query(default=None, max_length=40),
        take: int = Query(default=12, ge=1, le=30),
    ) -> dict:
        qloo, _ = live()
        return _resolution(culture.resolve(qloo, q, category, take))

    @app.post("/api/interpret")
    def interpret(body: InterpretIn) -> dict:
        qloo, _ = live()
        reading = interpret_deterministic(body.text)
        mentions = []
        for mention in reading.mentions:
            resolution = culture.resolve(qloo, mention.phrase, mention.category, 6)
            tags = culture.search(qloo, mention.phrase, "aesthetics", 4)
            mentions.append({
                "phrase": mention.phrase,
                "resolution": _resolution(resolution),
                "tag_candidates": [_candidate(t) for t in tags],
            })  # fmt: skip
        music = reading.music
        return {
            "interpreter": reading.interpreter,
            "mentions": mentions,
            "music": {
                "preferred": list(music.preferred),
                "avoided": list(music.avoided),
                "era": music.era,
                "eras": list(music.eras or ((music.era,) if music.era else ())),
                "discovery": music.discovery,
            },
        }

    @app.post("/api/discover")
    def discover(body: DiscoverIn) -> dict:
        _, engine = live()
        p = body.preferences
        prefs = Preferences(
            preferred=tuple(p.preferred), open_to=tuple(p.open_to),
            avoided=tuple(p.avoided), era=p.era if p.eras is None else None,
            discovery=p.discovery, eras=tuple(p.eras or ())
        )
        feedback = Feedback(
            tuple(s.to_signal() for s in body.feedback.liked),
            tuple(body.feedback.disliked),
        )
        result = engine.discover(
            [s.to_signal() for s in body.signals], prefs, feedback,
            body.page, body.max_artists, body.exclude_artists,
        )  # fmt: skip
        return _result(result)

    @app.post("/api/agent/chat")
    def agent_chat(body: AgentIn) -> dict:
        qloo, engine = live()
        p = body.preferences
        prefs = Preferences(
            preferred=tuple(p.preferred), open_to=tuple(p.open_to),
            avoided=tuple(p.avoided), era=p.era if p.eras is None else None,
            discovery=p.discovery, eras=tuple(p.eras or ())
        )
        feedback = Feedback(
            tuple(s.to_signal() for s in body.feedback.liked),
            tuple(body.feedback.disliked),
        )
        try:
            response = run_agent(
                qloo, engine, body.message,
                [s.to_signal() for s in body.signals], prefs, feedback,
                history=[turn.model_dump() for turn in body.history],
                seen=body.seen, default_page=body.page,
            )
        except AgentUnavailable as exc:
            return _error(503, "unavailable", str(exc))
        return {
            "reply": response["reply"],
            "trace": response["trace"],
            "signals": [_signal(s) for s in response["signals"]],
            "preferences": response["preferences"],
            "result": _result(response["result"]) if response["result"] is not None else None,
            "page": response["page"],
        }

    if FRONTEND_DIST.is_dir():
        app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
    return app


app = create_app()
