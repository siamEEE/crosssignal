"""Turn selected interests into catalog-backed artist results."""

from collections.abc import Callable, Sequence

from crosssignal.catalog import CatalogError
from crosssignal.models import (
    ArtistPick,
    ArtistResult,
    Discovery,
    InvalidSelection,
    LookupStatus,
    RecommendationError,
    Track,
)
from crosssignal.recommendations import RecommendationProvider

MAX_INTERESTS = 5
MAX_ARTISTS = 8

TrackLookup = Callable[[ArtistPick], Sequence[Track]]
ProgressCallback = Callable[[int, int, ArtistPick], None]


def discover(
    interest_ids: Sequence[str],
    provider: RecommendationProvider,
    lookup: TrackLookup,
    on_progress: ProgressCallback | None = None,
    max_artists: int = MAX_ARTISTS,
) -> Discovery:
    """Recommend artists, then look up each one in the catalog.

    Three kinds of trouble stay distinct:
    - invalid input raises InvalidSelection (a caller bug or bad request);
    - a failing provider returns a Discovery with `provider_error` set;
    - a provider with nothing to suggest returns a Discovery with no results.
    A failed catalog lookup only affects its own artist.
    `on_progress(done, total, pick)` fires after each lookup finishes.
    """
    if not interest_ids:
        raise InvalidSelection("Select at least one interest.")
    if len(interest_ids) > MAX_INTERESTS:
        raise InvalidSelection(f"Select at most {MAX_INTERESTS} interests.")

    ids = tuple(interest_ids)
    try:
        recommended = provider.recommend(interest_ids, max_artists)
    except RecommendationError as exc:
        return Discovery(ids, source=provider.source, provider_error=exc.kind)

    picks = recommended.picks
    results: list[ArtistResult] = []
    shown: set[str] = set()  # track URLs already on an earlier card
    for done, pick in enumerate(picks, start=1):
        try:
            tracks = tuple(lookup(pick))
        except CatalogError as exc:
            result = ArtistResult(pick, LookupStatus.ERROR, error=str(exc))
        else:
            status = LookupStatus.OK if tracks else LookupStatus.EMPTY
            # A collaboration can be found for two artists. Show it once,
            # unless that would leave this artist's card with no tracks.
            fresh = tuple(t for t in tracks if t.url not in shown)
            tracks = fresh or tracks
            shown.update(t.url for t in tracks)
            result = ArtistResult(pick, status, tracks)
        results.append(result)
        if on_progress is not None:
            on_progress(done, len(picks), pick)

    return Discovery(ids, tuple(results), recommended.unresolved, provider.source)
