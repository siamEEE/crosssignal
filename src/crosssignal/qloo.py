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

Also verified live (2026-10-21, Culture Radio slice):
- /search accepts several comma-separated `types` in one call; results
  carry `properties.image.url`, `properties.release_year` /
  `publication_year` and `disambiguation`. Search-result tags use
  `tag_id`; insights tags use `id`.
- Artist insights carry `tags` of type `urn:tag:genre:music` and honour
  `filter.tags`, `filter.exclude.tags`, `filter.exclude.entities`,
  `filter.popularity.min/max` and `page` (page 2 is disjoint from page 1).
- An artist entity works as a signal ("more like this").
- `urn:entity:locality` is search-only; as a signal it returns 400.
- GET /v2/tags?filter.query=...&filter.tag.types=... ->
  {results: {tags: [{id, name, type, ...}]}}.

This module turns every failure into RecommendationError with a kind, so
the UI never sees HTTP or Qloo JSON details.
"""

import threading
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
MUSIC_GENRE_TAG = "urn:tag:genre:music"
INSIGHTS_MAX_TAKE = 50
TAGS_MAX_TAKE = 50
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
    year: int | None = None  # release or publication year, if given
    disambiguation: str | None = None
    image_url: str | None = None
    # (tag id, tag name) pairs of type urn:tag:genre:music.
    genre_tags: tuple[tuple[str, str], ...] = ()
    start_year: int | None = None  # artists: first active year, if given


@dataclass(frozen=True)
class QlooTag:
    tag_id: str
    name: str
    tag_type: str


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
    properties = item.get("properties")
    properties = properties if isinstance(properties, dict) else {}
    return QlooEntity(
        entity_id,
        name,
        tuple(dict.fromkeys(types)),
        _number(query.get("affinity")),
        _number(item.get("popularity")),
        _explained_by(query),
        year=_year(properties.get("release_year"))
        or _year(properties.get("publication_year")),
        disambiguation=_text(item.get("disambiguation")),
        image_url=_image_url(properties.get("image")),
        genre_tags=_genre_tags(item.get("tags")),
        start_year=_year(properties.get("start_year")),
    )


def _year(value: object) -> int | None:
    number = _number(value)
    return int(number) if number is not None and 1000 <= number <= 2100 else None


def _image_url(image: object) -> str | None:
    url = image.get("url") if isinstance(image, dict) else None
    return url if isinstance(url, str) and url.startswith("https://") else None


def _genre_tags(tags: object) -> tuple[tuple[str, str], ...]:
    """Music-genre tags; insights use `id`, search results use `tag_id`."""
    if not isinstance(tags, list):
        return ()
    pairs: dict[str, str] = {}
    for tag in tags:
        if not isinstance(tag, dict) or tag.get("type") != MUSIC_GENRE_TAG:
            continue
        tag_id = _text(tag.get("id")) or _text(tag.get("tag_id"))
        if tag_id is not None:
            pairs.setdefault(tag_id, _text(tag.get("name")) or tag_id)
    return tuple(pairs.items())


def parse_tags(payload: object) -> list[QlooTag]:
    results = payload.get("results") if isinstance(payload, dict) else None
    tags = results.get("tags") if isinstance(results, dict) else None
    if not isinstance(tags, list):
        raise _fail(ProviderErrorKind.MALFORMED, "tags response had no tags list")
    parsed = []
    for tag in tags:
        if not isinstance(tag, dict):
            continue
        tag_id, name, kind = (_text(tag.get(k)) for k in ("id", "name", "type"))
        if tag_id and name and kind and tag_id.startswith("urn:tag:"):
            parsed.append(QlooTag(tag_id, name, kind))
    return parsed


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
        min_interval: float = 0.0,
    ) -> None:
        """`min_interval` spaces requests out (seconds) to stay under the
        per-second rate limit when several callers share one client."""
        if not settings.configured:
            raise _fail(ProviderErrorKind.NOT_CONFIGURED, "QLOO_API_KEY is not set")
        self._settings = settings
        self._http = http or httpx.Client(timeout=settings.timeout)
        self._sleep = sleep
        self._min_interval = min_interval
        self._lock = threading.Lock()
        self._last_request = 0.0

    def _throttle(self) -> None:
        if self._min_interval <= 0:
            return
        with self._lock:
            wait = self._last_request + self._min_interval - time.monotonic()
            if wait > 0:
                self._sleep(wait)
            self._last_request = time.monotonic()

    def _get(self, path: str, params: dict[str, str | int | float]) -> object:
        headers = {
            "X-Api-Key": self._settings.api_key.reveal(),
            "Accept": "application/json",
        }
        url = f"{self._settings.base_url}{path}"
        for attempt in range(MAX_RETRIES + 1):
            last = attempt == MAX_RETRIES
            self._throttle()
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

    def tags(
        self, query: str, tag_types: Sequence[str] = (), take: int = 10
    ) -> list[QlooTag]:
        """GET /v2/tags: tags whose name matches `query` (partial match)."""
        params: dict[str, str | int | float] = {
            "filter.query": query,
            "take": min(take, TAGS_MAX_TAKE),
        }
        if tag_types:
            params["filter.tag.types"] = ",".join(tag_types)
        return parse_tags(self._get("/v2/tags", params))

    def artist_insights(
        self,
        entity_ids: Sequence[str],
        take: int,
        *,
        tag_signals: Sequence[str] = (),
        filter_tags: Sequence[str] = (),
        exclude_tags: Sequence[str] = (),
        exclude_entities: Sequence[str] = (),
        popularity_min: float | None = None,
        popularity_max: float | None = None,
        page: int | None = None,
    ) -> list[QlooEntity]:
        """Artists for the signal entities. Non-artist entities are dropped.

        Optional arguments map one-to-one onto parameters the docs list
        for `filter.type=urn:entity:artist`; empty ones are not sent.
        """
        if not entity_ids:
            raise ValueError("artist_insights needs at least one signal entity")
        params: dict[str, str | int | float] = {
            "filter.type": ARTIST_TYPE,
            SIGNAL_KEY: ",".join(entity_ids),
            "feature.explainability": "true",
            "take": min(take, INSIGHTS_MAX_TAKE),
        }
        optional: dict[str, str | float | int | None] = {
            "signal.interests.tags": ",".join(tag_signals) or None,
            "filter.tags": ",".join(filter_tags) or None,
            "filter.exclude.tags": ",".join(exclude_tags) or None,
            "filter.exclude.entities": ",".join(exclude_entities) or None,
            "filter.popularity.min": popularity_min,
            "filter.popularity.max": popularity_max,
            "page": page if page and page > 1 else None,
        }
        params.update({k: v for k, v in optional.items() if v is not None})
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
