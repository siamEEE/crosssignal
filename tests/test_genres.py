import pytest

from crosssignal import genres
from crosssignal.genres import TAG

REQUIRED = [
    "pop", "rnb-soul", "hip-hop", "electronic", "lo-fi", "jazz", "folk", "country",
    "latin", "reggae", "rock", "metal", "alternative-rock", "hard-rock", "shoegaze",
    "post-rock", "progressive-rock", "pop-punk", "alternative-metal", "metalcore",
    "progressive-metal", "djent", "nu-metal", "industrial-metal", "symphonic-metal",
]  # fmt: skip


def test_taxonomy_covers_the_requested_genres_and_is_well_formed():
    ids = [g.id for g in genres.GENRES]
    assert len(ids) == len(set(ids))
    assert set(REQUIRED) <= set(ids)
    for genre in genres.GENRES:
        assert genre.tags, genre.id
        assert all(t.startswith(TAG) and t != TAG for t in genre.tags)
        if genre.parent:
            assert genres.BY_ID[genre.parent].parent is None  # two levels only
            assert not genre.itunes  # catalog names live on broad genres
        else:
            assert genre.itunes and not genre.advanced


def test_extreme_subgenres_are_advanced_and_requested_ones_are_not():
    for gid in ("black-metal", "death-metal", "grindcore", "deathcore"):
        assert genres.BY_ID[gid].advanced
    for gid in ("metalcore", "djent", "shoegaze", "pop-punk", "symphonic-metal"):
        assert not genres.BY_ID[gid].advanced


def test_broad_genre_includes_subgenre_tags_but_not_vice_versa():
    metal = genres.tag_ids(["metal"])
    assert TAG + "metalcore" in metal and TAG + "black_metal" in metal
    assert genres.tag_ids(["metalcore"]) == {
        TAG + "metalcore",
        TAG + "melodic_metalcore",
    }


def test_matching_is_by_tag_id_only():
    tags = [TAG + "metalcore", TAG + "pop"]
    assert genres.matched_genres(tags, ["metal", "metalcore", "rock"]) == [
        "metal", "metalcore",
    ]  # fmt: skip
    # A similar-looking id is not a match: no fuzzy name matching.
    assert genres.matched_genres([TAG + "metalcore_metal"], ["metalcore"]) == []


def test_catalog_genres_map_to_broad_families_exactly():
    assert genres.catalog_families("Metal") == {"metal"}
    assert genres.catalog_families("alternative") == {"rock"}
    assert genres.catalog_families("Video Game") == set()
    assert genres.catalog_families(None) == set()
    assert genres.itunes_matches("Metal", ["metalcore", "pop"]) == ["metalcore"]


def test_adjacent_families_agree_and_unrelated_do_not():
    assert genres.families_agree("rock", "metal")
    assert genres.families_agree("metal", "metal")
    assert not genres.families_agree("metal", "pop")


def test_validate_and_tree():
    assert genres.validate(["rock", "rock", "metal"]) == ["rock", "metal"]
    with pytest.raises(genres.UnknownGenre):
        genres.validate(["metal", "yacht-rock"])
    tree = {g["id"]: g for g in genres.tree()}
    assert "metalcore" not in tree
    metal_subs = {s["id"]: s["advanced"] for s in tree["metal"]["subgenres"]}
    assert metal_subs["metalcore"] is False and metal_subs["grindcore"] is True
