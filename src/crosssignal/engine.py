"""Culture Radio pipeline: confirmed signals -> verified, ranked artists.

Stages are separate so each can be tested, and later steered by an agent
(see docs/AGENT_DECISIONS.md):

    1. validate     signals and preferences (no network)
    2. discover     Qloo artist insights per entity signal, with genre,
                    avoided-genre, popularity and feedback filters
    3. pre-rank     by Qloo evidence only, to decide what to verify first
    4. validate     catalog lookups (bounded, parallel) for real tracks
    5. rank         final deterministic ranking + track selection

Nothing is invented to fill a page: if too few artists survive, the
result says so (`Status.INSUFFICIENT` / `Status.EMPTY`) with counts.
"""

from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from enum import StrEnum

from crosssignal import genres
from crosssignal.catalog import CatalogError, normalize_name
from crosssignal.culture import CATEGORIES, Kind
from crosssignal.models import Evidence, Interest, Track
from crosssignal.qloo import ARTIST_TYPE, QlooClient, QlooEntity
from crosssignal.ranking import (
    EXCLUDED,
    POPULARITY_BOUNDS,
    Candidate,
    GenreFit,
    Preferences,
    Ranked,
    Tally,
    diversify,
    dominant_genre,
    era_fit,
    genre_verdict,
    score,
    select_tracks,
    sort_key,
    tag_share,
)

MAX_SIGNALS = 5
MAX_LIKED = 3
MAX_ARTISTS = 8
MIN_RESULTS = 3
POOL_TAKE = 20
MAX_LOOKUPS = 14
LOOKUP_WORKERS = 3

ENTITY_TYPES = {t for c in CATEGORIES if c.kind is Kind.ENTITY for t in c.types}
TAG_TYPES = {t for c in CATEGORIES if c.kind is Kind.TAG for t in c.types}

ArtistLookup = Callable[[str], Sequence[Track]]


class InvalidRequest(ValueError):
    """The request breaks the contract; a client bug, not an upstream failure."""


class Status(StrEnum):
    OK = "ok"
    INSUFFICIENT = "insufficient"  # some, but fewer than MIN_RESULTS
    EMPTY = "empty"


@dataclass(frozen=True)
class Signal:
    """A user-confirmed Qloo entity or tag."""

    id: str
    kind: Kind
    name: str
    category: str
    qloo_type: str

    def as_interest(self) -> Interest:
        return Interest(self.id, self.name, self.category, "")


@dataclass(frozen=True)
class Feedback:
    liked: tuple[Signal, ...] = ()  # artists; become extra signals
    disliked: tuple[str, ...] = ()  # artist entity ids; excluded


NO_FEEDBACK = Feedback()


@dataclass
class Result:
    status: Status
    picks: list[Ranked]
    tally: Tally
    signals: tuple[Signal, ...]
    tag_signals: tuple[Signal, ...]
    preferences: Preferences
    page: int
    notices: list[str] = field(default_factory=list)


def validate_signals(
    signals: Sequence[Signal], feedback: Feedback
) -> tuple[list[Signal], list[Signal]]:
    """Split into entity and tag signals; raise InvalidRequest if unusable."""
    if len(signals) > MAX_SIGNALS:
        raise InvalidRequest(f"Choose at most {MAX_SIGNALS} interests.")
    if len(feedback.liked) > MAX_LIKED:
        raise InvalidRequest(f"At most {MAX_LIKED} liked artists can steer a remix.")
    entities, tags = [], []
    for signal in dict.fromkeys(signals):
        if signal.kind is Kind.TAG:
            if signal.qloo_type not in TAG_TYPES or not signal.id.startswith(
                "urn:tag:"
            ):
                raise InvalidRequest(f"Unsupported tag signal: {signal.name}")
            tags.append(signal)
        elif signal.qloo_type in ENTITY_TYPES:
            entities.append(signal)
        else:
            raise InvalidRequest(f"Unsupported entity type: {signal.qloo_type}")
    for artist in feedback.liked:
        if artist.kind is not Kind.ENTITY or artist.qloo_type != ARTIST_TYPE:
            raise InvalidRequest("Liked items must be artists.")
    if not entities and not feedback.liked:
        raise InvalidRequest(
            "Add at least one title, person, brand or place. Aesthetic tags "
            "alone are too weak a signal for artist recommendations."
        )
    return entities, tags


class Engine:
    def __init__(
        self,
        client: QlooClient,
        lookup: ArtistLookup,
        workers: int = LOOKUP_WORKERS,
        max_lookups: int = MAX_LOOKUPS,
    ) -> None:
        self._client = client
        self._lookup = lookup
        self._workers = workers
        self._max_lookups = max_lookups

    # --- stage 2: Qloo -------------------------------------------------------

    def _query(
        self,
        signals: Sequence[Signal],
        tag_signals: Sequence[Signal],
        prefs: Preferences,
        excluded_ids: Sequence[str],
        page: int,
        with_genre_filter: bool,
    ) -> dict[str, list[QlooEntity]]:
        low, high = POPULARITY_BOUNDS[prefs.discovery]
        filter_tags = (
            sorted(genres.tag_ids(prefs.preferred + prefs.open_to))
            if with_genre_filter and prefs.wants_genres
            else []
        )
        return {
            signal.id: self._client.artist_insights(
                [signal.id],
                POOL_TAKE,
                tag_signals=[t.id for t in tag_signals],
                filter_tags=filter_tags,
                exclude_tags=sorted(genres.tag_ids(prefs.avoided)),
                exclude_entities=list(excluded_ids),
                popularity_min=low,
                popularity_max=high,
                page=page,
            )
            for signal in signals
        }

    @staticmethod
    def _merge(
        lists: dict[str, list[QlooEntity]],
        signals: Sequence[Signal],
        source: str,
        into: dict[str, Candidate],
        excluded_ids: set[str],
    ) -> None:
        """Merge per-signal lists into candidates, keeping per-signal evidence.

        Artists are keyed by entity id; a different id with the same
        normalized name is treated as the same artist.
        """
        names = {normalize_name(c.name): key for key, c in into.items()}
        for signal in signals:
            artists = lists.get(signal.id, [])
            for rank, artist in enumerate(artists, start=1):
                if artist.entity_id in excluded_ids:
                    continue
                key = artist.entity_id
                key = (
                    key if key in into else names.get(normalize_name(artist.name), key)
                )
                evidence = Evidence(
                    interest=signal.as_interest(),
                    signal_id=signal.id,
                    signal_name=signal.name,
                    rank=rank,
                    affinity=artist.affinity,
                    explained_share=dict(artist.explained_by).get(signal.id),
                )
                existing = into.get(key)
                if existing is None:
                    into[key] = Candidate(
                        entity_id=artist.entity_id,
                        name=artist.name,
                        evidence=(evidence,),
                        pool_size=max(len(artists), 1),
                        popularity=artist.popularity,
                        genre_tags=artist.genre_tags,
                        image_url=artist.image_url,
                        source=source,
                    )
                    names[normalize_name(artist.name)] = key
                elif all(e.signal_id != signal.id for e in existing.evidence):
                    into[key] = replace(
                        existing, evidence=(*existing.evidence, evidence)
                    )

    # --- stage 3-5 -------------------------------------------------------------

    @staticmethod
    def _pre_tier(candidate: Candidate, prefs: Preferences) -> int:
        verdict = genre_verdict((t for t, _ in candidate.genre_tags), None, prefs)
        return {
            GenreFit.PREFERRED: 0,
            GenreFit.OPEN: 1,
            GenreFit.NEUTRAL: 1,
            GenreFit.UNVERIFIED: 2,
            GenreFit.MISMATCH: 3,  # the catalog genre may still support it
            GenreFit.AVOIDED: 9,
        }[verdict.fit]

    def _lookup_safely(self, name: str) -> tuple[list[Track] | None, bool]:
        try:
            return list(self._lookup(name)), False
        except CatalogError:
            return None, True

    def discover(
        self,
        signals: Sequence[Signal],
        prefs: Preferences,
        feedback: Feedback = NO_FEEDBACK,
        page: int = 1,
        max_artists: int = MAX_ARTISTS,
    ) -> Result:
        entities, tag_signals = validate_signals(signals, feedback)
        if not 1 <= page <= 20:
            raise InvalidRequest("page must be between 1 and 20")
        sources = [*entities, *feedback.liked]
        excluded_ids = {*feedback.disliked, *(a.id for a in feedback.liked)}
        tally = Tally()
        notices: list[str] = []

        candidates: dict[str, Candidate] = {}
        lists = self._query(
            sources, tag_signals, prefs, sorted(excluded_ids), page, True
        )
        self._merge(lists, sources, "filtered", candidates, excluded_ids)

        def usable() -> int:
            return sum(self._pre_tier(c, prefs) < 3 for c in candidates.values())

        # Genre filters can starve the pool; one unfiltered pass lets local
        # evidence (incl. catalog genre) decide instead of returning nothing.
        if prefs.wants_genres and usable() < max_artists:
            lists = self._query(
                sources, tag_signals, prefs, sorted(excluded_ids), page, False
            )
            self._merge(lists, sources, "unfiltered", candidates, excluded_ids)
            tally.fallback_used = True
            notices.append("genre_fallback")
        tally.qloo_candidates = len(candidates)
        if tag_signals:
            notices.append("tag_signals_unmeasured")

        queue = []
        for candidate in candidates.values():
            tier = self._pre_tier(candidate, prefs)
            if tier == 9:
                tally.avoided += 1
                tally.exclude("avoided", candidate.name)
                continue
            # Artists whose Qloo tags sit mostly in the wanted genres are
            # checked first; a lone stray tag is weak evidence.
            share = tag_share(
                (t for t, _ in candidate.genre_tags), prefs.preferred + prefs.open_to
            )
            queue.append(
                (
                    tier,
                    -share,
                    -score(candidate, None, prefs),
                    candidate.name,
                    candidate,
                )
            )
        queue.sort(key=lambda entry: entry[:4])

        accepted: list[Ranked] = []
        position = 0
        with ThreadPoolExecutor(max_workers=self._workers) as pool:
            while (
                position < len(queue)
                and len(accepted) < max_artists
                and tally.lookups < self._max_lookups
            ):
                room = min(self._workers, self._max_lookups - tally.lookups)
                batch = [entry[-1] for entry in queue[position : position + room]]
                position += len(batch)
                tally.lookups += len(batch)
                for candidate, (tracks, failed) in zip(
                    batch,
                    pool.map(lambda c: self._lookup_safely(c.name), batch),
                    strict=True,
                ):
                    if failed:
                        tally.catalog_errors += 1
                        tally.exclude("catalog_error", candidate.name)
                        continue
                    if not tracks:
                        tally.no_catalog_match += 1
                        tally.exclude("no_catalog_match", candidate.name)
                        continue
                    catalog_genre = dominant_genre(tracks)
                    verdict = genre_verdict(
                        (t for t, _ in candidate.genre_tags), catalog_genre, prefs
                    )
                    if verdict.fit in EXCLUDED:
                        if verdict.fit is GenreFit.AVOIDED:
                            tally.avoided += 1
                        elif verdict.fit is GenreFit.CONFLICT:
                            tally.conflicting += 1
                        else:
                            tally.mismatched += 1
                        tally.exclude(verdict.fit.value, candidate.name)
                        continue
                    era = era_fit(tracks, prefs.era)
                    accepted.append(
                        Ranked(
                            candidate,
                            verdict,
                            score(candidate, era, prefs),
                            tuple(tracks),
                            catalog_genre,
                            era,
                        )
                    )

        accepted.sort(key=sort_key)
        chosen = diversify(accepted, max_artists, len(sources))
        shown: set[str] = set()
        picks = []
        for item in chosen:
            tracks = select_tracks(item.tracks, prefs.era, shown)
            if not tracks:  # every song already shown on another card
                continue
            shown.update(t.url for t in tracks)
            picks.append(replace(item, tracks=tracks))

        if not picks:
            status = Status.EMPTY
        elif len(picks) < MIN_RESULTS:
            status = Status.INSUFFICIENT
        else:
            status = Status.OK
        return Result(status, picks, tally, tuple(sources), tuple(tag_signals),
                      prefs, page, notices)  # fmt: skip
