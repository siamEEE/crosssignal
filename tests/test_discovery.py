import pytest

from crosssignal.catalog import CatalogError
from crosssignal.discovery import MAX_INTERESTS, discover
from crosssignal.models import (
    Interest,
    InvalidSelection,
    LookupStatus,
    Outcome,
    ProviderErrorKind,
    RecommendationError,
    RecommendationSet,
    Track,
)
from crosssignal.recommendations import CuratedProvider

CATALOG = [
    ("a", "Alpha", "Films", "vibe", ("Found", "Missing")),
    ("b", "Beta", "Games", "vibe", ("Broken", "Found Too")),
]


def track(artist: str) -> Track:
    return Track("Song", artist, None, None, "https://example.com", None, None)


def fake_lookup(pick):
    if pick.artist == "Broken":
        raise CatalogError("offline")
    if pick.artist == "Missing":
        return []
    return [track(pick.artist)]


def test_partial_results_keep_successful_artists():
    result = discover(["a", "b"], CuratedProvider(CATALOG), fake_lookup)
    statuses = {r.pick.artist: r.status for r in result.results}
    assert statuses == {
        "Found": LookupStatus.OK,
        "Broken": LookupStatus.ERROR,
        "Missing": LookupStatus.EMPTY,
        "Found Too": LookupStatus.OK,
    }
    assert result.outcome is Outcome.PARTIAL
    assert result.interest_ids == ("a", "b")


def test_full_success():
    result = discover(["a"], CuratedProvider(CATALOG), lambda p: [track(p.artist)])
    assert result.outcome is Outcome.SUCCESS


def test_total_failure():
    def offline(pick):
        raise CatalogError("offline")

    result = discover(["a", "b"], CuratedProvider(CATALOG), offline)
    assert result.outcome is Outcome.FAILURE
    assert result.count(LookupStatus.ERROR) == 4


def test_all_empty():
    result = discover(["a"], CuratedProvider(CATALOG), lambda p: [])
    assert result.outcome is Outcome.EMPTY


def test_progress_reports_after_each_lookup_completes():
    finished = []
    events = []

    def lookup(pick):
        finished.append(pick.artist)
        return [track(pick.artist)]

    def on_progress(done, total, pick):
        # The lookup for this pick must already have completed.
        assert finished[-1] == pick.artist
        events.append((done, total))

    discover(["a", "b"], CuratedProvider(CATALOG), lookup, on_progress)
    assert events == [(1, 4), (2, 4), (3, 4), (4, 4)]


def test_selection_limits_are_enforced():
    provider = CuratedProvider()
    with pytest.raises(InvalidSelection):
        discover([], provider, fake_lookup)
    ids = [i.id for i in provider.interests()][: MAX_INTERESTS + 1]
    with pytest.raises(InvalidSelection):
        discover(ids, provider, fake_lookup)
    with pytest.raises(InvalidSelection):
        discover(["not-an-interest"], provider, fake_lookup)


def test_unexpected_errors_are_not_swallowed():
    def buggy(pick):
        raise KeyError("programming error")

    with pytest.raises(KeyError):
        discover(["a"], CuratedProvider(CATALOG), buggy)


class StubProvider:
    source = "stub"

    def __init__(self, answer=None, error=None):
        self.answer, self.error = answer, error

    def interests(self):
        return []

    def recommend(self, interest_ids, max_artists):
        if self.error:
            raise self.error
        return self.answer


def test_provider_failure_is_reported_not_raised_and_skips_catalog():
    looked_up = []
    error = RecommendationError(ProviderErrorKind.AUTH, "Qloo: 401")
    result = discover(["a"], StubProvider(error=error), looked_up.append)
    assert result.outcome is Outcome.PROVIDER_ERROR
    assert result.provider_error is ProviderErrorKind.AUTH
    assert result.source == "stub"
    assert looked_up == []


def test_empty_recommendations_are_distinct_from_catalog_misses():
    unresolved = (Interest("x", "X", "Aesthetics", "v"),)
    result = discover(
        ["x"], StubProvider(RecommendationSet((), unresolved)), fake_lookup
    )
    assert result.outcome is Outcome.NO_RECOMMENDATIONS
    assert result.unresolved == unresolved
    assert (
        discover(["a"], CuratedProvider(CATALOG), lambda p: []).outcome is Outcome.EMPTY
    )


def test_a_track_shown_for_one_artist_is_not_repeated_for_the_next():
    duet = Track("Duet", "Found & Found Too", None, None, "https://x/duet", None, None)
    solo = Track("Solo", "Found Too", None, None, "https://x/solo", None, None)
    tracks = {"Found": [duet], "Found Too": [duet, solo]}

    result = discover(
        ["a", "b"], CuratedProvider(CATALOG), lambda p: tracks.get(p.artist, [])
    )
    by_artist = {r.pick.artist: r.tracks for r in result.results}
    assert by_artist["Found"] == (duet,)
    assert by_artist["Found Too"] == (solo,)


def test_a_card_keeps_its_tracks_when_all_were_already_shown():
    duet = Track("Duet", "Found & Found Too", None, None, "https://x/duet", None, None)
    result = discover(["a", "b"], CuratedProvider(CATALOG), lambda p: [duet])
    assert all(r.tracks == (duet,) for r in result.results)
