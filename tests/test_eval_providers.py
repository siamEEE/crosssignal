import json

import pytest

from crosssignal.catalog import CatalogError
from crosssignal.evaluation.catalog_probe import (
    Availability,
    LiveProbe,
    NullProbe,
    SnapshotProbe,
)
from crosssignal.evaluation.providers import (
    CuratedAdapter,
    RandomBaseline,
    ReplayProvider,
)
from crosssignal.evaluation.schemas import (
    ProfileInterest,
    RecommendationRequest,
    ResponseStatus,
    SchemaError,
)
from crosssignal.models import Track


def request(
    *interests: tuple[str, str | None], pid: str = "p"
) -> RecommendationRequest:
    return RecommendationRequest(
        pid, tuple(ProfileInterest(name, "film", cid) for name, cid in interests)
    )


# --- curated adapter -----------------------------------------------------


def test_curated_cites_the_profiles_own_wording():
    response = CuratedAdapter().recommend(request(("drive (2011 film)", "drive")))
    assert response.status is ResponseStatus.OK
    assert [a.name for a in response.artists] == ["Kavinsky", "Cliff Martinez"]
    assert all(a.cited_interests == ("drive (2011 film)",) for a in response.artists)
    assert [a.rank for a in response.artists] == [1, 2]
    assert all(a.score is None for a in response.artists)  # never invented


def test_curated_reports_partial_and_unsupported_interests():
    adapter = CuratedAdapter()
    partial = adapter.recommend(request(("Drive", "drive"), ("Twin Peaks", None)))
    assert partial.status is ResponseStatus.OK
    assert partial.unsupported_interests == ("Twin Peaks",)

    none = adapter.recommend(request(("Twin Peaks", None), ("Bogus", "not-an-id")))
    assert none.status is ResponseStatus.UNSUPPORTED
    assert none.artists == ()


def test_curated_deduplicates_repeated_interest():
    response = CuratedAdapter().recommend(
        request(("Drive", "drive"), ("Drive", "drive"))
    )
    assert [a.name for a in response.artists] == ["Kavinsky", "Cliff Martinez"]


@pytest.mark.parametrize("count", [0, 6])
def test_live_adapters_reject_invalid_requests(count):
    req = request(*[(f"I{n}", "drive") for n in range(count)])
    for adapter in (CuratedAdapter(), RandomBaseline()):
        assert adapter.recommend(req).status is ResponseStatus.REJECTED


# --- random baseline -----------------------------------------------------


def test_random_baseline_is_deterministic_per_profile():
    baseline = RandomBaseline()
    one = baseline.recommend(request(("Drive", None), pid="a"))
    again = RandomBaseline().recommend(request(("Drive", None), pid="a"))
    other = baseline.recommend(request(("Drive", None), pid="b"))
    assert one == again
    assert [a.name for a in one.artists] != [a.name for a in other.artists]
    assert len(one.artists) == 8
    assert len({a.name for a in one.artists}) == 8


# --- replay --------------------------------------------------------------


def write(tmp_path, payload) -> object:
    path = tmp_path / "rec.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def recorded(pid: str, provider: str = "llm-x") -> dict:
    return {
        "provider": provider,
        "profile_id": pid,
        "status": "ok",
        "artists": [{"name": "M83", "rank": 1, "cited_interests": ["Drive"]}],
    }


def test_replay_serves_recordings_and_flags_gaps(tmp_path):
    path = write(tmp_path, {"provider": "llm-x", "responses": [recorded("a")]})
    replay = ReplayProvider(path)
    assert replay.name == "llm-x"
    assert replay.recommend(request(("Drive", None), pid="a")).artists[0].name == "M83"
    gap = replay.recommend(request(("Drive", None), pid="zzz"))
    assert gap.status is ResponseStatus.ERROR
    assert "no recorded response" in gap.error


def test_replay_rejects_mixed_or_malformed_recordings(tmp_path):
    mixed = {"provider": "llm-x", "responses": [recorded("a"), recorded("b", "other")]}
    with pytest.raises(SchemaError):
        ReplayProvider(write(tmp_path, mixed))
    with pytest.raises(SchemaError):
        ReplayProvider(write(tmp_path, {"responses": "nope"}))


# --- catalog probes ------------------------------------------------------


def track(artist: str, genre: str | None) -> Track:
    return Track("t", artist, None, None, "https://x", None, None, genre)


def test_live_probe_records_answers_but_not_failures(tmp_path):
    calls = []

    def search(artist):
        calls.append(artist)
        if artist == "Down":
            raise CatalogError("offline")
        if artist == "Ghost":
            return []
        return [
            track(artist, "Electronic"),
            track(artist, "Electronic"),
            track(artist, "Pop"),
        ]

    probe = LiveProbe(search)
    found = probe.probe("M83")
    assert (found.status, found.track_count, found.genres) == (
        Availability.FOUND, 3, ("Electronic", "Pop"),
    )  # fmt: skip
    assert probe.probe("m83").status is Availability.FOUND
    assert probe.probe("Ghost").status is Availability.NOT_FOUND
    assert probe.probe("Down").status is Availability.ERROR
    assert calls == ["M83", "Ghost", "Down"]  # cached by normalized name

    path = tmp_path / "snap.json"
    probe.save_snapshot(path)
    snapshot = SnapshotProbe(path)
    assert snapshot.probe("M83") == found
    assert snapshot.probe("Ghost").status is Availability.NOT_FOUND
    # A failure is not a fact about the catalog, so it was not recorded.
    assert snapshot.probe("Down").status is Availability.UNMEASURED


def test_null_probe_measures_nothing():
    assert NullProbe().probe("M83").status is Availability.UNMEASURED
