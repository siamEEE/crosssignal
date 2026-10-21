"""Normalized input/output schemas for recommendation evaluation.

Every provider under evaluation (curated demo data, a baseline, recorded
LLM output, future Qloo output) is adapted to RecommendationResponse, so
metrics never depend on a provider's native format.

Scores are optional on purpose. Only a provider that genuinely returns a
score (e.g. a Qloo affinity) may fill `score`, and `score_kind` must say
what it is. Adapters must never invent one.
"""

import json
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path

from crosssignal.catalog import normalize_name

MAX_ARTISTS = 8


class Expectation(StrEnum):
    RECOMMEND = "recommend"  # a valid request; the provider should answer
    REJECT = "reject"  # an invalid request; the provider should refuse it


class ResponseStatus(StrEnum):
    OK = "ok"
    REJECTED = "rejected"  # provider refused an invalid request
    UNSUPPORTED = "unsupported"  # provider knows none of the interests
    ERROR = "error"  # provider failed (network, quota, bug)


@dataclass(frozen=True)
class ProfileInterest:
    name: str
    domain: str  # e.g. film, game, aesthetic, book, tv, place, food
    curated_id: str | None = None  # the CuratedProvider id, if one exists


@dataclass(frozen=True)
class Profile:
    id: str
    description: str
    interests: tuple[ProfileInterest, ...]
    expect: Expectation
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class RecommendationRequest:
    profile_id: str
    interests: tuple[ProfileInterest, ...]
    max_artists: int = MAX_ARTISTS


@dataclass(frozen=True)
class RecommendedArtist:
    name: str
    rank: int  # 1-based
    cited_interests: tuple[str, ...]  # input interest names given as reasons
    score: float | None = None
    score_kind: str | None = None  # required whenever score is set


@dataclass(frozen=True)
class RecommendationResponse:
    provider: str
    profile_id: str
    status: ResponseStatus
    artists: tuple[RecommendedArtist, ...] = ()
    unsupported_interests: tuple[str, ...] = ()
    error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class SchemaError(ValueError):
    """Input data does not match the documented evaluation schema."""


# --- validation ----------------------------------------------------------


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SchemaError(message)


def _text(value: object, what: str) -> str:
    _require(isinstance(value, str) and bool(value.strip()), f"{what} must be text")
    return value.strip()


def parse_profile(raw: object) -> Profile:
    _require(isinstance(raw, dict), "profile must be an object")
    pid = _text(raw.get("id"), "profile id")
    interests_raw = raw.get("interests")
    _require(isinstance(interests_raw, list), f"{pid}: interests must be a list")
    interests = []
    for item in interests_raw:
        _require(isinstance(item, dict), f"{pid}: interest must be an object")
        curated = item.get("curated_id")
        _require(curated is None or isinstance(curated, str), f"{pid}: bad curated_id")
        interests.append(
            ProfileInterest(
                _text(item.get("name"), f"{pid}: interest name"),
                _text(item.get("domain"), f"{pid}: interest domain"),
                curated,
            )
        )
    try:
        expect = Expectation(raw.get("expect"))
    except ValueError as exc:
        raise SchemaError(f"{pid}: expect must be recommend or reject") from exc
    tags = raw.get("tags", [])
    _require(
        isinstance(tags, list) and all(isinstance(t, str) for t in tags),
        f"{pid}: tags must be a list of strings",
    )
    return Profile(
        pid,
        _text(raw.get("description"), f"{pid}: description"),
        tuple(interests),
        expect,
        tuple(tags),
    )


def load_profiles(path: Path) -> list[Profile]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(raw, dict), "profile file must be an object")
    _require(isinstance(raw.get("profiles"), list), "profile file needs a list")
    profiles = [parse_profile(item) for item in raw["profiles"]]
    ids = [p.id for p in profiles]
    _require(len(ids) == len(set(ids)), "profile ids must be unique")
    return profiles


def parse_response(raw: object) -> RecommendationResponse:
    """Validate a recorded response (e.g. captured LLM or Qloo output)."""
    _require(isinstance(raw, dict), "response must be an object")
    provider = _text(raw.get("provider"), "provider")
    pid = _text(raw.get("profile_id"), "profile_id")
    try:
        status = ResponseStatus(raw.get("status"))
    except ValueError as exc:
        raise SchemaError(f"{provider}/{pid}: unknown status") from exc

    artists_raw = raw.get("artists", [])
    _require(isinstance(artists_raw, list), f"{provider}/{pid}: artists not a list")
    artists = []
    for expected_rank, item in enumerate(artists_raw, start=1):
        _require(isinstance(item, dict), f"{provider}/{pid}: artist not an object")
        rank = item.get("rank")
        _require(rank == expected_rank, f"{provider}/{pid}: ranks must be 1..n")
        cited = item.get("cited_interests", [])
        _require(
            isinstance(cited, list) and all(isinstance(c, str) for c in cited),
            f"{provider}/{pid}: cited_interests must be strings",
        )
        score, kind = item.get("score"), item.get("score_kind")
        if score is not None:
            _require(
                isinstance(score, int | float) and not isinstance(score, bool),
                f"{provider}/{pid}: score must be a number",
            )
            _text(kind, f"{provider}/{pid}: score_kind (required with a score)")
        artists.append(
            RecommendedArtist(
                _text(item.get("name"), f"{provider}/{pid}: artist name"),
                rank,
                tuple(cited),
                float(score) if score is not None else None,
                kind if score is not None else None,
            )
        )
    unsupported = raw.get("unsupported_interests", [])
    _require(isinstance(unsupported, list), f"{provider}/{pid}: bad unsupported list")
    error = raw.get("error")
    _require(error is None or isinstance(error, str), f"{provider}/{pid}: bad error")
    return RecommendationResponse(
        provider, pid, status, tuple(artists), tuple(unsupported), error
    )


def interest_key(name: str) -> str:
    return normalize_name(name)
