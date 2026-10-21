import pytest

from crosssignal.models import InvalidSelection
from crosssignal.recommendations import DEMO_SOURCE, CuratedProvider

CATALOG = [
    ("a", "Alpha", "Films", "vibe a", ("A1", "A2")),
    ("b", "Beta", "Games", "vibe b", ("B1", "Shared")),
    ("c", "Gamma", "Aesthetics", "vibe c", ("Shared", "C2")),
]


def test_default_catalog_is_well_formed():
    provider = CuratedProvider()
    interests = provider.interests()
    assert len(interests) == 12
    assert len({i.id for i in interests}) == len(interests)
    assert {i.category for i in interests} == {"Films", "Games", "Aesthetics"}


def test_round_robin_represents_every_interest_first():
    provider = CuratedProvider(CATALOG)
    picks = provider.recommend(["a", "b"], max_artists=2).picks
    assert [p.artist for p in picks] == ["A1", "B1"]


def test_shared_artist_is_deduplicated_and_credits_all_interests():
    provider = CuratedProvider(CATALOG)
    picks = provider.recommend(["b", "c"], max_artists=10).picks
    assert [p.artist for p in picks] == ["B1", "Shared", "C2"]
    shared = picks[1]
    assert [i.name for i in shared.interests] == ["Beta", "Gamma"]


def test_every_pick_is_labelled_demo_curated():
    picks = CuratedProvider().recommend(["drive", "journey"], max_artists=8).picks
    assert picks
    assert all(p.source == DEMO_SOURCE for p in picks)


def test_max_artists_is_respected():
    provider = CuratedProvider()
    ids = [i.id for i in provider.interests()][:5]
    assert len(provider.recommend(ids, max_artists=8).picks) == 8


def test_unknown_interest_raises():
    with pytest.raises(InvalidSelection):
        CuratedProvider(CATALOG).recommend(["nope"], max_artists=3)
