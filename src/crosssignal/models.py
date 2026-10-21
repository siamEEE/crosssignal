"""Plain data types shared by retrieval and presentation.

These carry no Streamlit or HTTP dependencies, so any recommendation
source (curated demo data now, Qloo later) can produce them.
"""

from dataclasses import dataclass, field
from enum import StrEnum


@dataclass(frozen=True)
class Interest:
    id: str
    name: str
    category: str
    vibe: str


@dataclass(frozen=True)
class Evidence:
    """Why a source returned an artist for one interest, as the source said it.

    `signal_id` is the source entity the interest resolved to, `rank` the
    artist's 1-based position in the source's answer for that signal.
    `affinity` and `explained_share` are copied only when the source
    returned them; neither is a probability that the user likes the artist.
    """

    interest: Interest
    signal_id: str
    signal_name: str
    rank: int
    affinity: float | None = None
    explained_share: float | None = None


@dataclass(frozen=True)
class ArtistPick:
    """An artist suggested for one or more selected interests.

    `interests` are the selected interests that led to this artist: the
    explanation shown to the user. `score` is set only when the source
    really returns one, and `score_kind` then names it. `evidence` holds
    per-interest provenance when the source provides it.
    """

    artist: str
    interests: tuple[Interest, ...]
    source: str
    aliases: tuple[str, ...] = ()
    score: float | None = None
    score_kind: str | None = None
    external_id: str | None = None  # e.g. a Qloo entity id
    evidence: tuple[Evidence, ...] = ()


@dataclass(frozen=True)
class RecommendationSet:
    """A provider's answer: picks plus interests it could not use."""

    picks: tuple[ArtistPick, ...]
    unresolved: tuple[Interest, ...] = ()


class InvalidSelection(ValueError):
    """The user's selection breaks the input contract (empty, too many, unknown)."""


class ProviderErrorKind(StrEnum):
    AUTH = "auth"
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"
    MALFORMED = "malformed"
    NOT_CONFIGURED = "not_configured"
    BAD_REQUEST = "bad_request"


class RecommendationError(Exception):
    """A recommendation source failed. Not the user's fault."""

    def __init__(self, kind: ProviderErrorKind, message: str) -> None:
        super().__init__(message)
        self.kind = kind


@dataclass(frozen=True)
class Track:
    title: str
    artist: str
    album: str | None
    year: str | None
    url: str
    artwork_small: str | None
    artwork_large: str | None
    genre: str | None = None


class LookupStatus(StrEnum):
    OK = "ok"
    EMPTY = "empty"
    ERROR = "error"


@dataclass(frozen=True)
class ArtistResult:
    pick: ArtistPick
    status: LookupStatus
    tracks: tuple[Track, ...] = ()
    error: str | None = None


class Outcome(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    EMPTY = "empty"  # artists recommended, none found in the catalog
    FAILURE = "failure"  # every catalog lookup failed
    NO_RECOMMENDATIONS = "no_recommendations"  # provider answered with nothing
    PROVIDER_ERROR = "provider_error"  # the recommendation source failed


@dataclass(frozen=True)
class Discovery:
    interest_ids: tuple[str, ...]
    results: tuple[ArtistResult, ...] = field(default_factory=tuple)
    unresolved: tuple[Interest, ...] = ()
    source: str | None = None
    provider_error: ProviderErrorKind | None = None

    def count(self, status: LookupStatus) -> int:
        return sum(1 for result in self.results if result.status is status)

    @property
    def outcome(self) -> Outcome:
        if self.provider_error is not None:
            return Outcome.PROVIDER_ERROR
        if not self.results:
            return Outcome.NO_RECOMMENDATIONS
        found = self.count(LookupStatus.OK)
        errors = self.count(LookupStatus.ERROR)
        if self.results and found == len(self.results):
            return Outcome.SUCCESS
        if found:
            return Outcome.PARTIAL
        if errors:
            return Outcome.FAILURE
        return Outcome.EMPTY
