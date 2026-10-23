import pytest
from fakes import FakeQloo, tag, title

from crosssignal import culture
from crosssignal.culture import Kind, Match

MOVIE, TV, BOOK = "urn:entity:movie", "urn:entity:tv_show", "urn:entity:book"


def client():
    return FakeQloo(
        searches={
            "Drive": [title("d1", "Drive", MOVIE, 2011, 0.99),
                      title("d2", "Drive", MOVIE, 1997, 0.85),
                      title("x", "Drive Angry", MOVIE, 2011)],
            "Interstellar": [title("i1", "Interstellar", MOVIE, 2014),
                             title("i2", "Interstellar Wars", MOVIE)],
            "Dune": [title("b1", "Dune (Dune, #1)", BOOK, 1965),
                     title("b2", "Dune Messiah (Dune #2)", BOOK, 1969)],
            "Tokyo": [title("t1", "Tokyo", "urn:entity:locality")],
            "zzz": [title("z", "Unrelated", MOVIE)],
        },
        tags={"cottagecore": [tag("urn:tag:ambience:qloo:cottagecore", "Cottagecore"),
                              tag("urn:tag:audience:qloo:x", "Audience", "urn:tag:audience:qloo")]},
    )  # fmt: skip


def test_single_exact_name_resolves():
    r = culture.resolve(client(), "interstellar", "screen")
    assert r.match is Match.EXACT
    assert r.candidates[0].id == "i1"
    assert r.candidates[0].type_label == "Film" and r.candidates[0].year == 2014


def test_several_exact_names_need_the_user_and_are_ordered_by_popularity():
    r = culture.resolve(client(), "Drive", "screen")
    assert r.match is Match.AMBIGUOUS
    assert [c.id for c in r.candidates] == ["d1", "d2"]  # "Drive Angry" not offered


def test_series_markers_do_not_block_an_exact_book_match():
    r = culture.resolve(client(), "Dune", "books")
    assert r.match is Match.EXACT and r.candidates[0].id == "b1"


def test_fuzzy_results_are_suggestions_never_a_match():
    assert culture.resolve(client(), "zzz", None).match is Match.SUGGESTIONS
    assert culture.resolve(client(), "nothing at all", None).match is Match.NONE


def test_search_only_types_are_not_offered_as_signals():
    # Locality is search-only in Qloo (400 as a signal), so it is dropped.
    assert culture.search(client(), "Tokyo", None) == []


def test_category_restricts_entity_types_in_one_call():
    fake = client()
    culture.search(fake, "Drive", "screen")
    (_, (_, types), _) = fake.calls[-1]
    assert types == (MOVIE, TV)
    culture.search(fake, "Drive", None)
    assert len(fake.calls[-1][1][1]) > 5  # every entity category at once


def test_aesthetics_use_tags_of_allowed_types_only():
    found = culture.search(client(), "cottagecore", "aesthetics")
    assert [(c.name, c.kind) for c in found] == [("Cottagecore", Kind.TAG)]


def test_unknown_category_and_blank_query():
    with pytest.raises(ValueError):
        culture.search(client(), "x", "cars")
    assert culture.search(client(), "   ", None) == []


def test_featured_collections_hold_names_not_ids():
    for collection in culture.FEATURED:
        for item in collection.items:
            assert item.category in culture.CATEGORY_BY_ID
            assert not item.query.startswith("urn:")
