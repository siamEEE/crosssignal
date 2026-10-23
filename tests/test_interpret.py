import pytest

from crosssignal.interpret import (
    MAX_PHRASES,
    Interpretation,
    InvalidInterpretation,
    Mention,
    MusicHints,
    interpret_deterministic,
    validate,
)


def phrases(text):
    return [m.phrase for m in interpret_deterministic(text).mentions]


def test_splits_lists_and_strips_filler():
    assert phrases("I love Interstellar, Hollow Knight and dark academia") == [
        "Interstellar", "Hollow Knight", "dark academia",
    ]  # fmt: skip
    assert phrases("Big fan of Twin Peaks; also into Berserk") == [
        "Twin Peaks",
        "Berserk",
    ]


def test_genres_become_preferences_not_cultural_mentions():
    reading = interpret_deterministic("Mostly metalcore and shoegaze, no country")
    assert reading.mentions == ()
    assert reading.music.preferred == ("metalcore", "shoegaze")
    assert reading.music.avoided == ("country",)


def test_genre_with_an_example_keeps_the_example_to_look_up():
    reading = interpret_deterministic("post-rock like Mogwai")
    assert reading.music.preferred == ("post-rock",)
    assert [m.phrase.casefold() for m in reading.mentions] == ["mogwai"]


def test_era_and_discovery_words():
    reading = interpret_deterministic("hidden gems from the 90s, Arrival")
    assert reading.music.era == "1990s"
    assert reading.music.discovery == "adventurous"
    assert [m.phrase for m in reading.mentions] == ["Arrival"]
    assert interpret_deterministic("popular stuff").music.discovery == "familiar"


def test_negated_cultural_phrases_are_dropped_and_duplicates_merged():
    assert phrases("Dune, dune, not Twilight") == ["Dune"]


def test_phrase_count_is_bounded():
    text = ", ".join(f"Title {i}" for i in range(20))
    assert len(phrases(text)) == MAX_PHRASES


def test_no_personal_trait_fields_exist_in_the_contract():
    fields = set(Interpretation.__dataclass_fields__) | set(
        MusicHints.__dataclass_fields__
    )
    assert fields == {"mentions", "music", "interpreter", "preferred", "avoided",
                      "era", "discovery"}  # fmt: skip


def test_validate_rejects_out_of_vocabulary_output():
    ok = Interpretation((Mention("Dune", "books"),), MusicHints(("metal",)), "gemini")
    assert validate(ok) is ok
    for bad in (
        Interpretation((Mention("Dune", "cars"),)),
        Interpretation((), MusicHints(("yacht-rock",))),
        Interpretation((), MusicHints(era="1890s")),
        Interpretation((), MusicHints(discovery="random")),
        Interpretation(tuple(Mention(f"m{i}") for i in range(MAX_PHRASES + 1))),
    ):
        with pytest.raises(InvalidInterpretation):
            validate(bad)
