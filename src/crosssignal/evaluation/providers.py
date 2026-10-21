"""Adapters that put every recommendation source behind one interface.

- CuratedAdapter: the app's hand-curated demo provider.
- RandomBaseline: seeded random artists from the same pool. A floor, not
  a competitor; it shows what the metrics report for meaningless output.
- ReplayProvider: replays recorded responses (an LLM run, or real Qloo
  output once credentials exist) from a JSON file. Nothing is generated.
"""

import hashlib
import json
import random
from pathlib import Path
from typing import Protocol

from crosssignal.discovery import MAX_INTERESTS
from crosssignal.evaluation.schemas import (
    RecommendationRequest,
    RecommendationResponse,
    RecommendedArtist,
    ResponseStatus,
    SchemaError,
    parse_response,
)
from crosssignal.recommendations import CuratedProvider


class EvalProvider(Protocol):
    name: str

    def recommend(self, request: RecommendationRequest) -> RecommendationResponse:
        """Answer one request. Expected failures become a status, not a raise."""
        ...


def request_problem(request: RecommendationRequest) -> str | None:
    """The app's input contract, applied identically to live adapters."""
    if not request.interests:
        return "no interests"
    if len(request.interests) > MAX_INTERESTS:
        return f"more than {MAX_INTERESTS} interests"
    return None


class CuratedAdapter:
    name = "curated"

    def __init__(self, provider: CuratedProvider | None = None) -> None:
        self._provider = provider or CuratedProvider()
        self._known = {i.id for i in self._provider.interests()}

    def recommend(self, request: RecommendationRequest) -> RecommendationResponse:
        problem = request_problem(request)
        if problem:
            return RecommendationResponse(
                self.name, request.profile_id, ResponseStatus.REJECTED, error=problem
            )

        # Cite the profile's own wording for each curated interest.
        names_by_id: dict[str, str] = {}
        unsupported: list[str] = []
        for interest in request.interests:
            if interest.curated_id in self._known:
                names_by_id.setdefault(interest.curated_id, interest.name)
            else:
                unsupported.append(interest.name)
        if not names_by_id:
            return RecommendationResponse(
                self.name,
                request.profile_id,
                ResponseStatus.UNSUPPORTED,
                unsupported_interests=tuple(unsupported),
            )

        picks = self._provider.recommend(list(names_by_id), request.max_artists).picks
        artists = tuple(
            RecommendedArtist(
                name=pick.artist,
                rank=rank,
                cited_interests=tuple(names_by_id[i.id] for i in pick.interests),
            )
            for rank, pick in enumerate(picks, start=1)
        )
        return RecommendationResponse(
            self.name,
            request.profile_id,
            ResponseStatus.OK,
            artists,
            tuple(unsupported),
        )


def _stable_seed(*parts: str) -> int:
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


class RandomBaseline:
    """Random artists citing a random input interest. Deterministic per profile."""

    name = "random-baseline"

    def __init__(
        self, pool: list[str] | None = None, seed: str = "crosssignal"
    ) -> None:
        if pool is None:
            provider = CuratedProvider()
            pool = sorted(
                {p.artist for i in provider.interests()
                 for p in provider.recommend([i.id], max_artists=100).picks}
            )  # fmt: skip
        self._pool = sorted(set(pool))
        self._seed = seed

    def recommend(self, request: RecommendationRequest) -> RecommendationResponse:
        problem = request_problem(request)
        if problem:
            return RecommendationResponse(
                self.name, request.profile_id, ResponseStatus.REJECTED, error=problem
            )
        rng = random.Random(_stable_seed(self._seed, request.profile_id))
        chosen = rng.sample(self._pool, min(request.max_artists, len(self._pool)))
        names = [i.name for i in request.interests]
        artists = tuple(
            RecommendedArtist(name, rank, (rng.choice(names),))
            for rank, name in enumerate(chosen, start=1)
        )
        return RecommendationResponse(
            self.name, request.profile_id, ResponseStatus.OK, artists
        )


class ReplayProvider:
    """Serve recorded responses from a file.

    File format: {"provider": str, "source_note": str, "responses": [...]},
    each response matching schemas.parse_response. A profile with no
    recording is reported as an ERROR so gaps are visible, never filled.
    """

    def __init__(self, path: Path) -> None:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or not isinstance(raw.get("responses"), list):
            raise SchemaError(f"{path}: expected an object with a responses list")
        self.name = raw.get("provider") or path.stem
        self.source_note = raw.get("source_note", "")
        self._responses = {}
        for item in raw["responses"]:
            response = parse_response(item)
            if response.provider != self.name:
                raise SchemaError(f"{path}: mixed providers in one recording")
            self._responses[response.profile_id] = response

    def recommend(self, request: RecommendationRequest) -> RecommendationResponse:
        recorded = self._responses.get(request.profile_id)
        if recorded is None:
            return RecommendationResponse(
                self.name,
                request.profile_id,
                ResponseStatus.ERROR,
                error="missing: no recorded response",
            )
        return recorded
