import pytest
from fakes import TAG, FakeCatalog, FakeQloo, artist, song

from crosssignal.culture import Kind
from crosssignal.engine import (
    MAX_SIGNALS,
    Engine,
    Feedback,
    InvalidRequest,
    Signal,
    Status,
)
from crosssignal.models import ProviderErrorKind, RecommendationError
from crosssignal.ranking import GenreFit, Preferences, Support

FILM = Signal("m1", Kind.ENTITY, "Neon Film", "screen", "urn:entity:movie")
GAME = Signal("g1", Kind.ENTITY, "Chrome Game", "games", "urn:entity:videogame")
MOOD = Signal("urn:tag:ambience:qloo:rainy", Kind.TAG, "Rainy", "aesthetics",
              "urn:tag:ambience:qloo")  # fmt: skip


def metal_band(i):
    return artist(f"a{i}", f"Band {i}", "metal", "metalcore")


def tracks_for(*names, genre="Metal", year="2015"):
    return {n: [song(n, f"{n} song {k}", genre=genre, year=year) for k in range(4)]
            for n in names}  # fmt: skip


def engine(qloo, catalog, **kw):
    return Engine(qloo, catalog, workers=2, **kw)


# --- validation ---------------------------------------------------------------


def test_tag_only_profiles_are_rejected_with_a_reason():
    with pytest.raises(InvalidRequest, match="at least one title"):
        engine(FakeQloo(), FakeCatalog()).discover([MOOD], Preferences())


def test_signal_limits_and_types_are_enforced():
    e = engine(FakeQloo(), FakeCatalog())
    many = [Signal(f"m{i}", Kind.ENTITY, f"F{i}", "screen", "urn:entity:movie")
            for i in range(MAX_SIGNALS + 1)]  # fmt: skip
    with pytest.raises(InvalidRequest):
        e.discover(many, Preferences())
    locality = Signal("l1", Kind.ENTITY, "Tokyo", "places", "urn:entity:locality")
    with pytest.raises(InvalidRequest):
        e.discover([locality], Preferences())
    with pytest.raises(InvalidRequest):
        e.discover([FILM], Preferences(), Feedback(liked=(GAME,)))  # not an artist
    with pytest.raises(InvalidRequest):
        e.discover([FILM], Preferences(), page=0)


# --- Qloo request shape ---------------------------------------------------------


def test_preferences_and_feedback_become_documented_qloo_filters():
    qloo = FakeQloo(insights={"m1": [metal_band(1)]})
    liked = Signal("liked1", Kind.ENTITY, "Liked", "liked", "urn:entity:artist")
    engine(qloo, FakeCatalog(tracks_for("Band 1"))).discover(
        [FILM, MOOD],
        Preferences(
            preferred=("metalcore",), avoided=("country",), discovery="adventurous"
        ),
        Feedback(liked=(liked,), disliked=("bad1",)),
        page=2,
    )
    calls = qloo.insight_calls()
    assert [c[1] for c in calls[:2]] == [("m1",), ("liked1",)]  # one query per signal
    kw = calls[0][2]
    assert set(kw["filter_tags"]) == {TAG + "metalcore", TAG + "melodic_metalcore"}
    assert TAG + "country" in kw["exclude_tags"]
    assert set(kw["exclude_entities"]) == {"bad1", "liked1"}
    assert kw["tag_signals"] == [MOOD.id]
    assert (kw["popularity_min"], kw["popularity_max"]) == (None, 0.85)
    assert kw["page"] == 2


def test_no_genre_filter_without_genre_preferences():
    qloo = FakeQloo(insights={"m1": [metal_band(1)]})
    engine(qloo, FakeCatalog(tracks_for("Band 1"))).discover([FILM], Preferences())
    assert qloo.insight_calls()[0][2]["filter_tags"] == []
    assert len(qloo.insight_calls()) == 1


# --- verification and ranking -------------------------------------------------


def test_confirmed_artists_rank_first_and_conflicts_are_excluded_and_counted():
    pop_star = artist("p1", "Pop Star", "pop", "black_metal", popularity=0.99)
    unknown = artist("u1", "Mystery Act")  # no genre tags
    qloo = FakeQloo(insights={"m1": [pop_star, unknown, metal_band(1), metal_band(2),
                                     metal_band(3)]})  # fmt: skip
    catalog = FakeCatalog({**tracks_for("Band 1", "Band 2", "Band 3"),
                           **tracks_for("Pop Star", genre="Pop"),
                           **tracks_for("Mystery Act", genre="Video Game")})  # fmt: skip
    result = engine(qloo, catalog).discover([FILM], Preferences(preferred=("metal",)))

    names = [r.candidate.name for r in result.picks]
    assert names[:3] == ["Band 1", "Band 2", "Band 3"]
    assert names[-1] == "Mystery Act"  # unverified sorts last, still shown
    assert result.picks[-1].verdict.fit is GenreFit.UNVERIFIED
    assert all(r.verdict.support is Support.BOTH for r in result.picks[:3])
    assert "Pop Star" not in names
    assert result.tally.conflicting == 1
    assert result.tally.excluded_names["conflict"] == ["Pop Star"]


def test_too_few_compatible_artists_is_reported_not_padded():
    qloo = FakeQloo(insights={"m1": [artist("c1", "Country Act", "country"),
                                     metal_band(1)]})  # fmt: skip
    catalog = FakeCatalog({**tracks_for("Band 1"),
                           **tracks_for("Country Act", genre="Country")})  # fmt: skip
    result = engine(qloo, catalog).discover([FILM], Preferences(preferred=("metal",)))
    assert result.status is Status.INSUFFICIENT
    assert [r.candidate.name for r in result.picks] == ["Band 1"]
    assert result.tally.mismatched == 1


def test_empty_when_nothing_survives():
    qloo = FakeQloo(insights={"m1": [metal_band(1)]})
    result = engine(qloo, FakeCatalog()).discover([FILM], Preferences())
    assert result.status is Status.EMPTY
    assert result.tally.no_catalog_match == 1


def test_genre_filter_starvation_triggers_one_unfiltered_pass():
    qloo = FakeQloo(
        genre_filtered={"m1": [metal_band(1)]},
        insights={"m1": [metal_band(1), artist("q1", "Untagged Act"),
                         artist("r9", "Rock Act", "rock")]},
    )  # fmt: skip
    catalog = FakeCatalog({**tracks_for("Band 1", "Untagged Act"),
                           **tracks_for("Rock Act", genre="Rock")})  # fmt: skip
    result = engine(qloo, catalog).discover([FILM], Preferences(preferred=("metal",)))
    assert result.tally.fallback_used and "genre_fallback" in result.notices
    assert len(qloo.insight_calls()) == 2
    sources = {r.candidate.name: r.candidate.source for r in result.picks}
    assert sources == {"Band 1": "filtered", "Untagged Act": "unfiltered"}
    # No Qloo genre tag, but the catalog files it under Metal: kept, labelled
    # as catalog-only support and ranked below the confirmed band.
    assert result.picks[-1].verdict.support is Support.CATALOG
    # Rock-tagged and filed under Rock: evidence for another genre.
    assert result.tally.excluded_names["mismatch"] == ["Rock Act"]


def test_catalog_failures_and_lookup_budget():
    bands = [metal_band(i) for i in range(10)]
    catalog = FakeCatalog(tracks_for(*[f"Band {i}" for i in range(10)]),
                          failing={"Band 0"})  # fmt: skip
    result = engine(FakeQloo(insights={"m1": bands}), catalog, max_lookups=5).discover(
        [FILM], Preferences(), max_artists=8
    )
    assert result.tally.lookups == 5 and len(catalog.lookups) == 5
    assert result.tally.catalog_errors == 1
    assert len(result.picks) == 4


def test_artists_from_several_signals_merge_with_evidence_from_each():
    shared = metal_band(1)
    renamed = artist("other-id", "band 1", "metal")  # same act, another id
    qloo = FakeQloo(insights={"m1": [shared, metal_band(2)], "g1": [renamed]})
    catalog = FakeCatalog(tracks_for("Band 1", "Band 2", "band 1"))
    result = engine(qloo, catalog).discover([FILM, GAME], Preferences())
    first = result.picks[0]
    assert first.candidate.name == "Band 1"
    assert [(e.signal_name, e.rank) for e in first.candidate.evidence] == [
        ("Neon Film", 1), ("Chrome Game", 1),
    ]  # fmt: skip
    assert len(result.picks) == 2


def test_disliked_and_liked_artists_never_appear_in_results():
    liked = Signal("a1", Kind.ENTITY, "Band 1", "liked", "urn:entity:artist")
    qloo = FakeQloo(insights={"m1": [metal_band(1), metal_band(2), metal_band(3)],
                              "a1": [metal_band(4)]})  # fmt: skip
    catalog = FakeCatalog(tracks_for(*[f"Band {i}" for i in range(1, 5)]))
    result = engine(qloo, catalog).discover(
        [FILM], Preferences(), Feedback(liked=(liked,), disliked=("a2",))
    )
    names = [r.candidate.name for r in result.picks]
    assert "Band 1" not in names and "Band 2" not in names
    assert {"Band 3", "Band 4"} <= set(names)
    band4 = next(r for r in result.picks if r.candidate.name == "Band 4")
    assert band4.candidate.evidence[0].signal_name == "Band 1"  # "because you liked"


def test_a_song_shown_on_one_card_is_not_repeated_on_another():
    duet = song("Band 1 & Band 2", "Duet", url="https://music.example/duet")
    catalog = FakeCatalog({
        "Band 1": [duet, song("Band 1", "Solo A")],
        "Band 2": [duet, song("Band 2", "Solo B")],
    })  # fmt: skip
    qloo = FakeQloo(insights={"m1": [metal_band(1), metal_band(2)]})
    result = engine(qloo, catalog).discover([FILM], Preferences())
    urls = [t.url for r in result.picks for t in r.tracks]
    assert urls.count("https://music.example/duet") == 1


def test_era_preference_reorders_and_reports_evidence():
    # A realistic pool: Qloo returned 10 artists, two are in the catalog.
    qloo = FakeQloo(insights={"m1": [metal_band(i) for i in range(1, 11)]})
    catalog = FakeCatalog({**tracks_for("Band 1", year="1994"),
                           **tracks_for("Band 2", year="2016")})  # fmt: skip
    result = engine(qloo, catalog).discover([FILM], Preferences(era="2010s"))
    assert [r.candidate.name for r in result.picks] == ["Band 2", "Band 1"]
    assert (result.picks[0].era.in_era, result.picks[0].era.dated) == (4, 4)


def test_upstream_errors_propagate_for_the_api_to_report():
    qloo = FakeQloo(error=RecommendationError(ProviderErrorKind.RATE_LIMIT, "429"))
    with pytest.raises(RecommendationError):
        engine(qloo, FakeCatalog()).discover([FILM], Preferences())


def test_tag_signals_add_a_notice_because_their_effect_is_unmeasured():
    qloo = FakeQloo(insights={"m1": [metal_band(1)]})
    result = engine(qloo, FakeCatalog(tracks_for("Band 1"))).discover(
        [FILM, MOOD], Preferences()
    )
    assert "tag_signals_unmeasured" in result.notices
    assert result.tag_signals == (MOOD,)
