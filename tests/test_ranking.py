import pytest
from fakes import TAG, song

from crosssignal.models import Evidence, Interest
from crosssignal.ranking import (
    Candidate,
    GenreFit,
    Preferences,
    Ranked,
    Support,
    diversify,
    era_fit,
    familiarity_term,
    genre_verdict,
    score,
    select_tracks,
    sort_key,
    tag_share,
)


def tags(*slugs):
    return [TAG + s for s in slugs]


def verdict(tag_slugs, catalog, **prefs):
    return genre_verdict(tags(*tag_slugs), catalog, Preferences(**prefs))


# --- genre compatibility ------------------------------------------------------


def test_confirmed_needs_qloo_tag_and_agreeing_catalog():
    v = verdict(["metalcore", "metal"], "Metal", preferred=("metal",))
    assert (v.fit, v.support, v.matched) == (
        GenreFit.PREFERRED,
        Support.BOTH,
        ("metal",),
    )
    assert not v.related_only
    # Adjacent families agree: a metal band filed under "Rock", but this is
    # flagged so it is never described as the catalog saying "Metal".
    related = verdict(["metal"], "Hard Rock", preferred=("metal",))
    assert related.support is Support.BOTH and related.related_only


def test_each_reported_genre_needs_its_own_catalog_support():
    v = verdict(["metal", "jazz"], "Metal", preferred=("metal", "jazz"))
    assert v.matched == ("metal",)


def test_coarse_catalog_does_not_establish_avoided_subgenre():
    assert verdict([], "Metal", avoided=("metalcore",)).fit is GenreFit.NEUTRAL


def test_qloo_only_when_catalog_genre_is_unknown_or_unmapped():
    assert verdict(["djent"], None, preferred=("djent",)).support is Support.QLOO
    assert (
        verdict(["djent"], "Video Game", preferred=("djent",)).support is Support.QLOO
    )


def test_a_stray_qloo_tag_contradicted_by_the_catalog_is_a_conflict():
    # Observed live: a pop star carried a black_metal tag.
    v = verdict(["pop", "black_metal", "hip_hop"], "Pop", preferred=("metal",))
    assert v.fit is GenreFit.CONFLICT


def test_catalog_only_support_names_the_broad_family_never_a_subgenre():
    v = verdict([], "Alternative", preferred=("shoegaze",))
    assert (v.fit, v.support, v.matched) == (
        GenreFit.PREFERRED,
        Support.CATALOG,
        ("rock",),
    )


def test_open_to_ranks_below_preferred_and_is_labelled():
    v = verdict(["alternative_rock"], "Alternative", preferred=("metal",),
                open_to=("alternative-rock",))  # fmt: skip
    assert (v.fit, v.support) == (GenreFit.OPEN, Support.BOTH)
    preferred = verdict(["metal"], "Metal", preferred=("metal",))
    assert preferred.tier < v.tier


def test_missing_evidence_is_unverified_not_a_match():
    assert verdict([], None, preferred=("jazz",)).fit is GenreFit.UNVERIFIED
    assert verdict([], "Video Game", preferred=("jazz",)).fit is GenreFit.UNVERIFIED


def test_evidence_for_other_genres_is_a_mismatch():
    assert (
        verdict(["country"], "Country", preferred=("metal",)).fit is GenreFit.MISMATCH
    )


def test_no_preferences_is_neutral():
    assert verdict(["pop"], "Pop").fit is GenreFit.NEUTRAL


def test_avoided_genre_needs_corroboration_too():
    assert verdict(["country"], "Country", avoided=("country",)).fit is GenreFit.AVOIDED
    assert verdict([], "Country", avoided=("country",)).fit is GenreFit.AVOIDED
    # A stray metal tag on a pop act does not get it excluded for avoiding metal.
    assert (
        verdict(["pop", "black_metal"], "Pop", avoided=("metal",)).fit
        is GenreFit.NEUTRAL
    )


def test_wanted_subgenre_beats_broad_avoidance_of_its_parent():
    v = verdict(["metalcore", "metal"], "Metal", preferred=("metalcore",),
                avoided=("metal",))  # fmt: skip
    assert v.fit is GenreFit.PREFERRED


def test_preferences_validate_vocabularies():
    with pytest.raises(ValueError):
        Preferences(preferred=("metal",), avoided=("metal",))
    with pytest.raises(ValueError):
        Preferences(era="1890s")
    with pytest.raises(ValueError):
        Preferences(discovery="chaotic")
    with pytest.raises(ValueError):
        Preferences(preferred=("yacht-rock",))


def test_tag_share():
    assert tag_share(tags("metal", "pop", "rap", "trap"), ["metal"]) == 0.25
    assert tag_share([], ["metal"]) == 0.0


# --- scoring and ordering ---------------------------------------------------


def evidence(signal, rank):
    return Evidence(Interest(signal, signal, "screen", ""), signal, signal, rank)


def candidate(name, *ranks, signal="s1", popularity=0.5, pool=20):
    ev = tuple(
        evidence(f"{signal}{i}" if i else signal, r) for i, r in enumerate(ranks)
    )
    return Candidate(name.lower(), name, ev, pool, popularity)


def test_relevance_follows_qloo_rank_and_rewards_several_interests():
    prefs = Preferences()
    assert score(candidate("A", 1), None, prefs) > score(candidate("B", 5), None, prefs)
    assert score(candidate("C", 5, 5), None, prefs) > score(
        candidate("D", 5), None, prefs
    )


def test_familiarity_follows_the_discovery_mode():
    assert familiarity_term(0.9, "familiar") == 0.9
    assert familiarity_term(0.9, "adventurous") == pytest.approx(0.1)
    assert familiarity_term(0.9, "balanced") == 0.5
    assert familiarity_term(None, "familiar") == 0.5


def test_era_fit_counts_dated_tracks():
    tracks = [song("A", "x", year="2012"), song("A", "y", year="1999"),
              song("A", "z", year=None)]  # fmt: skip
    fit = era_fit(tracks, "2010s")
    assert (fit.in_era, fit.dated, fit.share) == (1, 2, 0.5)
    assert era_fit(tracks, None) is None
    assert era_fit([song("A", "z", year=None)], "2010s").share is None


def test_tier_beats_score():
    prefs = Preferences(preferred=("metal",))
    strong = genre_verdict(tags("metal"), "Metal", prefs)
    weak = genre_verdict([], None, prefs)
    top_rank_unverified = Ranked(candidate("Zed", 1), weak, 0.99)
    low_rank_confirmed = Ranked(candidate("Amy", 20), strong, 0.10)
    ordered = sorted([top_rank_unverified, low_rank_confirmed], key=sort_key)
    assert [r.candidate.name for r in ordered] == ["Amy", "Zed"]


def test_diversify_represents_every_interest_first():
    neutral = genre_verdict([], None, Preferences())
    items = [Ranked(candidate(f"A{i}", i, signal="a"), neutral, 1 - i / 10)
             for i in range(1, 7)]  # fmt: skip
    items.append(Ranked(candidate("B1", 1, signal="b"), neutral, 0.0))
    chosen = diversify(items, 4, interest_count=2)
    assert "B1" in [r.candidate.name for r in chosen]
    assert len(diversify(items, 7, interest_count=2)) == 7


# --- track selection --------------------------------------------------------


def test_track_selection_skips_versions_and_shown_songs_and_prefers_era():
    tracks = [
        song("A", "Old Hit", year="1995"),
        song("A", "Old Hit (2015 Remaster)", year="2015"),
        song("A", "New One", year="2016"),
        song("A", "Shown Elsewhere", year="2017", url="https://music.example/shown"),
        song("A", "Another", year="2018"),
    ]
    picked = select_tracks(tracks, "2010s", {"https://music.example/shown"})
    titles = [t.title for t in picked]
    assert "Shown Elsewhere" not in titles
    assert "Old Hit (2015 Remaster)" not in titles  # a version of "Old Hit"
    assert titles[:2] == ["New One", "Another"]  # in-era first, catalog order kept


def test_track_selection_prefers_previews_and_distinct_albums():
    tracks = [
        song("A", "No Preview", preview=False, album="One"),
        song("A", "Same Album", album="Two"),
        song("A", "Same Album Again", album="Two"),
        song("A", "Third", album="Three"),
    ]
    titles = [t.title for t in select_tracks(tracks, None, set())]
    assert titles == ["Same Album", "Third", "No Preview"]
    assert len(select_tracks(tracks, None, set(), limit=4)) == 4


def test_multiple_eras_use_a_union_and_represent_each_range():
    tracks = [song("A", str(y), year=str(y)) for y in (2019, 2018, 2017, 2003, 1984)]
    prefs = Preferences(eras=("2010s", "1980s", "2000s", "2010s"))
    assert prefs.eras == ("1980s", "2000s", "2010s")
    fit = era_fit(tracks, prefs.eras)
    assert (fit.in_era, fit.dated) == (5, 5)
    selected = select_tracks(tracks, prefs.eras, set())
    assert {t.year for t in selected} == {"1984", "2003", "2019"}
    assert select_tracks(tracks, prefs.eras, set()) == selected


def test_overlapping_recent_and_decade_do_not_double_count():
    from crosssignal.ranking import THIS_YEAR

    tracks = [song("A", "Recent", year=str(THIS_YEAR)), song("A", "Old", year="1994")]
    fit = era_fit(tracks, ("2020s", "recent"))
    assert (fit.in_era, fit.dated, fit.share) == (1, 2, 0.5)
    selected = select_tracks(tracks, ("2020s", "recent"), set())
    assert len(selected) == 2
    assert selected[0].title == "Recent"


def test_absent_era_is_soft_and_unknown_eras_are_rejected():
    tracks = [song("A", "Song", year="1994")]
    assert era_fit(tracks, ()) is None
    assert select_tracks(tracks, ("1980s", "2000s"), set()) == tuple(tracks)
    with pytest.raises(ValueError):
        Preferences(eras=("1890s",))
