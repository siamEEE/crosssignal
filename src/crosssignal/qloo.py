"""Qloo Insights API client and recommendation provider.

Verified live against https://hackathon.api.qloo.com (2026-10-21):
- Auth: `X-Api-Key` header. Missing or wrong key -> 401 (text/plain body).
- GET /search?query=...&types=urn:entity:movie&take=N -> {results: [...]}.
  No `success`/`duration` keys. Search is fuzzy: it returns 200 with
  loosely related titles even for nonsense queries, so only exact
  normalized-name matches are trusted. Several exact matches can exist
  ("Drive" -> 5 films); the most `popular` one is used.
  Game type is `urn:entity:videogame` (`urn:entity:video_game` -> 400).
- GET /v2/insights?filter.type=urn:entity:artist
      &signal.interests.entities=<ids>&feature.explainability=true&take=N
  -> {success, results: {entities: [...]}, query: {explainability: ...}}.
  Artist entities have type `urn:entity`, subtype `urn:entity:artist`,
  `query.affinity` (float 0-1) and, with explainability,
  `query.explainability["signal.interests.entities"] = [{entity_id, score}]`.
  Unknown signal ids -> 400.
- 404 means an unknown path ("Not Found"), never "no results".
- Rate limit headers: x-second-ratelimit-limit (10 at the time of
  writing) and x-month-ratelimit-*. 429 is retried with bounded backoff.

This module turns every failure into RecommendationError with a kind, so
the UI never sees HTTP or Qloo JSON details.
"""

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import httpx

from crosssignal.catalog import normalize_name
from crosssignal.config import QlooSettings
from crosssignal.models import (
    ArtistPick,
    Evidence,
    Interest,
    InvalidSelection,
    ProviderErrorKind,
    RecommendationError,
    RecommendationSet,
)

QLOO_SOURCE = "qloo"
ARTIST_TYPE = "urn:entity:artist"
INSIGHTS_MAX_TAKE = 50
SIGNAL_KEY = "signal.interests.entities"

# How each picker category is searched in Qloo. Categories without a Qloo
# entity type (aesthetics such as "Dark academia") are reported as
# unresolved rather than forced onto a guessed entity.
CATEGORY_TYPES = {
    "Films": "urn:entity:movie",
    "Games": "urn:entity:videogame",
}

# Transient failures worth retrying, with a short bounded backoff.
MAX_RETRIES = 2
BACKOFF_SECONDS = (0.5, 1.5)
MAX_RETRY_AFTER = 5.0
RETRY_STATUSES = {429, 502, 503, 504}


@dataclass(frozen=True)
class QlooEntity:
    entity_id: str
    name: str
    types: tuple[str, ...] = ()
    affinity: float | None = None
    popularity: float | None = None
    # (signal entity id, share of influence) from feature.explainability.
    explained_by: tuple[tuple[str, float], ...] = ()


def _fail(kind: ProviderErrorKind, message: str) -> RecommendationError:
    return RecommendationError(kind, f"Qloo: {message}")


def _status_error(status: int) -> RecommendationError:
    if status in (401, 403):
        return _fail(ProviderErrorKind.AUTH, f"authentication rejected ({status})")
    if status == 429:
        return _fail(ProviderErrorKind.RATE_LIMIT, "rate limit exceeded (429)")
    if status in (400, 404, 422):
        return _fail(ProviderErrorKind.BAD_REQUEST, f"request rejected ({status})")
    return _fail(ProviderErrorKind.UNAVAILABLE, f"service error ({status})")


def _text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _explained_by(query: dict) -> tuple[tuple[str, float], ...]:
    explainability = query.get("explainability")
    if not isinstance(explainability, dict):
        return ()
    items = explainability.get(SIGNAL_KEY)
    if not isinstance(items, list):
        return ()
    pairs = []
    for item in items:
        if isinstance(item, dict):
            signal, share = _text(item.get("entity_id")), _number(item.get("score"))
            if signal is not None and share is not None:
                pairs.append((signal, share))
    return tuple(pairs)


def parse_entity(item: object) -> QlooEntity | None:
    """One entity, or None if it lacks a usable id and name."""
    if not isinstance(item, dict):
        return None
    entity_id, name = _text(item.get("entity_id")), _text(item.get("name"))
    if entity_id is None or name is None:
        return None

    types: list[str] = []
    raw_types = item.get("types")
    if isinstance(raw_types, list):
        types += [t for t in raw_types if isinstance(t, str)]
    types += [t for t in (item.get("type"), item.get("subtype")) if isinstance(t, str)]

    query = item.get("query")
    query = query if isinstance(query, dict) else {}
    return QlooEntity(
        entity_id,
        name,
        tuple(dict.fromkeys(types)),
        _number(query.get("affinity")),
        _number(item.get("popularity")),
        _explained_by(query),
    )


def parse_search(payload: object) -> list[QlooEntity]:
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        raise _fail(ProviderErrorKind.MALFORMED, "search response had no results list")
    return [e for e in map(parse_entity, payload["results"]) if e is not None]


def parse_insights(payload: object) -> list[QlooEntity]:
    if not isinstance(payload, dict):
        raise _fail(ProviderErrorKind.MALFORMED, "insights response was not an object")
    if payload.get("success") is False:
        raise _fail(ProviderErrorKind.MALFORMED, "insights response reported failure")
    results = payload.get("results")
    entities = results.get("entities") if isinstance(results, dict) else None
    if not isinstance(entities, list):
        raise _fail(ProviderErrorKind.MALFORMED, "insights response had no entities")
    return [e for e in map(parse_entity, entities) if e is not None]


def _retry_delay(response: httpx.Response | None, attempt: int) -> float:
    """Seconds to wait before retry `attempt` (0-based)."""
    delay = BACKOFF_SECONDS[min(attempt, len(BACKOFF_SECONDS) - 1)]
    if response is not None:
        retry_after = _number_from_header(response.headers.get("Retry-After"))
        if retry_after is not None:
            delay = max(delay, retry_after)
    return min(delay, MAX_RETRY_AFTER)


def _number_from_header(value: str | None) -> float | None:
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


class QlooClient:
    """Thin HTTP client, one method per endpoint.

    Retries timeouts, connection failures, 429 and 502-504 up to
    MAX_RETRIES times with a short backoff; every other failure is raised
    immediately. No caching here; QlooProvider caches successful answers.
    """

    def __init__(
        self,
        settings: QlooSettings,
        http: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not settings.configured:
            raise _fail(ProviderErrorKind.NOT_CONFIGURED, "QLOO_API_KEY is not set")
        self._settings = settings
        self._http = http or httpx.Client(timeout=settings.timeout)
        self._sleep = sleep

    def _get(self, path: str, params: dict[str, str | int]) -> object:
        headers = {
            "X-Api-Key": self._settings.api_key.reveal(),
            "Accept": "application/json",
        }
        url = f"{self._settings.base_url}{path}"
        for attempt in range(MAX_RETRIES + 1):
            last = attempt == MAX_RETRIES
            try:
                response = self._http.get(url, params=params, headers=headers)
            except httpx.TimeoutException as exc:
                if last:
                    raise _fail(ProviderErrorKind.TIMEOUT, "request timed out") from exc
                self._sleep(_retry_delay(None, attempt))
                continue
            except httpx.HTTPError as exc:
                if last:
                    raise _fail(
                        ProviderErrorKind.UNAVAILABLE, "could not reach the API"
                    ) from exc
                self._sleep(_retry_delay(None, attempt))
                continue

            if response.status_code in RETRY_STATUSES and not last:
                self._sleep(_retry_delay(response, attempt))
                continue
            if not response.is_success:
                raise _status_error(response.status_code)
            try:
                return response.json()
            except ValueError as exc:
                raise _fail(
                    ProviderErrorKind.MALFORMED, "response was not JSON"
                ) from exc
        raise AssertionError("unreachable")  # pragma: no cover

    def search(
        self, query: str, types: Sequence[str], take: int = 5
    ) -> list[QlooEntity]:
        params = {"query": query, "types": ",".join(types), "take": take}
        return parse_search(self._get("/search", params))

    def artist_insights(self, entity_ids: Sequence[str], take: int) -> list[QlooEntity]:
        """Artists for the signal entities. Non-artist entities are dropped."""
        if not entity_ids:
            raise ValueError("artist_insights needs at least one signal entity")
        params = {
            "filter.type": ARTIST_TYPE,
            SIGNAL_KEY: ",".join(entity_ids),
            "feature.explainability": "true",
            "take": min(take, INSIGHTS_MAX_TAKE),
        }
        entities = parse_insights(self._get("/v2/insights", params))
        return [e for e in entities if ARTIST_TYPE in e.types]


class QlooProvider:
    """RecommendationProvider backed by Qloo.

    Each selected interest is resolved to a Qloo entity by exact
    (normalized) name within its category's entity type, then queried
    alone for artists, so every artist is credited only to the interests
    whose Qloo query actually returned it. (A single joint query was
    tried live: it returned broadly popular artists rather than ones
    specific to each title, and splits credit by explainability shares
    instead of by query.) Results are merged round-robin like the curated
    provider and deduplicated by Qloo entity id and normalized name.
    Successful lookups are cached for the life of the provider; failures
    are not.
    """

    source = QLOO_SOURCE

    def __init__(
        self,
        client: QlooClient,
        interests: Sequence[Interest],
        search_take: int = 10,
    ) -> None:
        self._client = client
        self._interests = {i.id: i for i in interests}
        self._search_take = search_take
        self._resolved: dict[str, QlooEntity | None] = {}
        self._artists: dict[tuple[str, int], list[QlooEntity]] = {}

    def interests(self) -> list[Interest]:
        return list(self._interests.values())

    def resolve(self, interest: Interest) -> QlooEntity | None:
        """The Qloo entity for an interest, or None if there is no exact match.

        Among several exact matches of the right type, the most popular
        wins; ties keep Qloo's search order.
        """
        if interest.id in self._resolved:
            return self._resolved[interest.id]
        entity_type = CATEGORY_TYPES.get(interest.category)
        match = None
        if entity_type is not None:
            wanted = normalize_name(interest.name)
            exact = [
                entity
                for entity in self._client.search(
                    interest.name, [entity_type], self._search_take
                )
                if entity_type in entity.types and normalize_name(entity.name) == wanted
            ]
            if exact:
                match = max(exact, key=lambda e: e.popularity or 0.0)
        self._resolved[interest.id] = match
        return match

    def _artists_for(self, entity: QlooEntity, take: int) -> list[QlooEntity]:
        key = (entity.entity_id, take)
        if key not in self._artists:
            self._artists[key] = self._client.artist_insights([entity.entity_id], take)
        return self._artists[key]

    def recommend(
        self, interest_ids: Sequence[str], max_artists: int
    ) -> RecommendationSet:
        unknown = [i for i in interest_ids if i not in self._interests]
        if unknown:
            raise InvalidSelection(f"Unknown interest ids: {unknown}")
        selected = [self._interests[i] for i in dict.fromkeys(interest_ids)]

        entities = {i.id: self.resolve(i) for i in selected}
        unresolved = tuple(i for i in selected if entities[i.id] is None)
        resolved = [i for i in selected if entities[i.id] is not None]
        lists = {i.id: self._artists_for(entities[i.id], max_artists) for i in resolved}

        # One key per artist: the first-seen entity id, and names map to it
        # too, so two entities with the same normalized name merge.
        keys: dict[str, str] = {}

        def key_for(artist: QlooEntity) -> str:
            name = normalize_name(artist.name)
            key = keys.get(artist.entity_id) or keys.get(name) or artist.entity_id
            keys.setdefault(artist.entity_id, key)
            keys.setdefault(name, key)
            return key

        # Round-robin: every resolved interest contributes before any
        # contributes a second artist.
        order: list[str] = []
        first_seen: dict[str, QlooEntity] = {}
        evidence: dict[str, list[Evidence]] = {}
        depth = max((len(v) for v in lists.values()), default=0)
        for level in range(depth):
            for interest in resolved:
                artists = lists[interest.id]
                if level >= len(artists):
                    continue
                artist = artists[level]
                key = key_for(artist)
                if key not in first_seen:
                    first_seen[key] = artist
                    order.append(key)
                signal = entities[interest.id]
                credited = evidence.setdefault(key, [])
                if all(e.interest != interest for e in credited):
                    credited.append(
                        Evidence(
                            interest=interest,
                            signal_id=signal.entity_id,
                            signal_name=signal.name,
                            rank=level + 1,
                            affinity=artist.affinity,
                            explained_share=dict(artist.explained_by).get(
                                signal.entity_id
                            ),
                        )
                    )

        picks = []
        for key in order[:max_artists]:
            artist = first_seen[key]
            proof = tuple(
                sorted(evidence[key], key=lambda e: selected.index(e.interest))
            )
            # An affinity belongs to one (interest, artist) query. Show it
            # only when exactly one interest produced the artist.
            single = len(proof) == 1 and proof[0].affinity is not None
            picks.append(
                ArtistPick(
                    artist=artist.name,
                    interests=tuple(e.interest for e in proof),
                    source=self.source,
                    score=proof[0].affinity if single else None,
                    score_kind="qloo_affinity" if single else None,
                    external_id=artist.entity_id,
                    evidence=proof,
                )
            )
        return RecommendationSet(tuple(picks), unresolved)
