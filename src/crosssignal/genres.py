"""Music genre taxonomy for preferences, mapped to verified Qloo tag ids.

Every tag id below was observed live on 2026-10-21, either returned by
GET /v2/tags?filter.tag.types=urn:tag:genre:music (exact name match) or
present in the `tags` of real artist entities from /v2/insights (e.g.
`country`, `soul`, `trap`, `rock` and `rhythm_blues`, whose /v2/tags
display names are noisy). No id is constructed from a label. Re-check
with:

    uv run --env-file .env python -m crosssignal.genres --verify

Genre compatibility compares an artist's Qloo music-genre tag *ids* with
the ids of the chosen genres (a broad genre includes its subgenres), and
separately an iTunes `primaryGenreName` with `itunes` names. Names are
never fuzzy-matched.
"""

import argparse
from collections.abc import Iterable
from dataclasses import dataclass

TAG = "urn:tag:genre:music:"


@dataclass(frozen=True)
class Genre:
    id: str
    label: str
    tags: tuple[str, ...]  # verified Qloo tag ids, full URNs
    parent: str | None = None  # None for a broad genre
    advanced: bool = False  # extreme or specialised: hidden by default
    itunes: tuple[str, ...] = ()  # iTunes primaryGenreName values (broad only)


def _g(gid, label, slugs, parent=None, advanced=False, itunes=()):
    return Genre(gid, label, tuple(TAG + s for s in slugs), parent, advanced, itunes)


# fmt: off
GENRES: tuple[Genre, ...] = (
    _g("pop", "Pop", ["pop"], itunes=("Pop", "K-Pop", "J-Pop", "Indie Pop", "Dance Pop")),
    _g("indie-pop", "Indie pop", ["indie_pop"], "pop"),
    _g("synth-pop", "Synth-pop", ["synth_pop"], "pop"),
    _g("dream-pop", "Dream pop", ["dream_pop"], "pop"),
    _g("k-pop", "K-pop", ["k_pop"], "pop"),
    _g("hyperpop", "Hyperpop", ["hyperpop"], "pop", advanced=True),

    _g("rnb-soul", "R&B & soul", ["rhythm_blues", "rhythm_and_blues", "r_b_soul",
       "soul"], itunes=("R&B/Soul", "Soul", "Contemporary R&B", "Neo-Soul")),
    _g("contemporary-rnb", "Contemporary R&B", ["contemporary_r_b"], "rnb-soul"),
    _g("alternative-rnb", "Alternative R&B", ["alternative_rnb", "alternative_r_b"],
       "rnb-soul"),
    _g("neo-soul", "Neo soul", ["neo_soul"], "rnb-soul"),

    _g("hip-hop", "Hip-hop", ["hip_hop", "rap"],
       itunes=("Hip-Hop/Rap", "Hip-Hop", "Rap", "Alternative Rap")),
    _g("trap", "Trap", ["trap", "trap_rap"], "hip-hop"),
    _g("alternative-hip-hop", "Alternative hip-hop", ["alternative_hip_hop"], "hip-hop"),
    _g("boom-bap", "Boom bap", ["boom_bap"], "hip-hop"),

    _g("electronic", "Electronic", ["electronic", "electronica"],
       itunes=("Electronic", "Dance", "House", "Techno", "Ambient", "Electronica",
               "Downtempo", "Drum & Bass", "Trance", "Dubstep")),
    _g("house", "House", ["house"], "electronic"),
    _g("techno", "Techno", ["techno"], "electronic"),
    _g("ambient", "Ambient", ["ambient"], "electronic"),
    _g("synthwave", "Synthwave", ["synthwave"], "electronic"),
    _g("drum-and-bass", "Drum & bass", ["drum_bass"], "electronic"),
    _g("downtempo", "Downtempo", ["downtempo"], "electronic"),
    _g("trip-hop", "Trip-hop", ["trip_hop"], "electronic"),

    _g("lo-fi", "Lo-fi", ["lo_fi"], itunes=("Lo-Fi",)),
    _g("lo-fi-hip-hop", "Lo-fi hip-hop", ["lo_fi_hip_hop"], "lo-fi"),
    _g("chillhop", "Chillhop", ["chillhop"], "lo-fi"),

    _g("jazz", "Jazz", ["jazz"], itunes=("Jazz", "Vocal Jazz", "Contemporary Jazz",
                                         "Smooth Jazz", "Bebop", "Fusion")),
    _g("jazz-fusion", "Jazz fusion", ["jazz_fusion"], "jazz"),
    _g("nu-jazz", "Nu jazz", ["nu_jazz"], "jazz"),

    _g("folk", "Folk", ["folk"], itunes=("Folk", "Singer/Songwriter", "Contemporary Folk")),
    _g("indie-folk", "Indie folk", ["indie_folk"], "folk"),
    _g("americana", "Americana", ["americana"], "folk"),

    _g("country", "Country", ["country", "contemporary_country"],
       itunes=("Country", "Contemporary Country", "Americana", "Honky Tonk")),
    _g("alt-country", "Alt-country", ["alt_country"], "country"),

    _g("latin", "Latin", ["latin"], itunes=("Latin", "Urbano latino", "Pop Latino",
                                            "Latin Urban", "Música Mexicana")),
    _g("reggaeton", "Reggaeton", ["reggaeton"], "latin"),
    _g("latin-pop", "Latin pop", ["latin_pop"], "latin"),
    _g("bossa-nova", "Bossa nova", ["bossa_nova"], "latin"),

    _g("reggae", "Reggae", ["reggae"], itunes=("Reggae", "Dancehall", "Dub")),
    _g("dub", "Dub", ["dub"], "reggae"),
    _g("dancehall", "Dancehall", ["dancehall"], "reggae"),

    _g("classical-score", "Classical & score", ["classical", "soundtrack"],
       itunes=("Classical", "Soundtrack", "Original Score", "Modern Era",
               "Classical Crossover", "Neo-Classical")),
    _g("neoclassical", "Neoclassical", ["neoclassical"], "classical-score"),
    _g("contemporary-classical", "Contemporary classical", ["contemporary_classical"],
       "classical-score"),
    _g("film-score", "Film score", ["film_score"], "classical-score"),

    _g("rock", "Rock", ["rock"], itunes=("Rock", "Alternative", "Hard Rock",
                                         "Indie Rock", "Punk", "Prog-Rock/Art Rock")),
    _g("alternative-rock", "Alternative rock", ["alternative_rock"], "rock"),
    _g("indie-rock", "Indie rock", ["indie_rock"], "rock"),
    _g("hard-rock", "Modern hard rock", ["hard_rock"], "rock"),
    _g("shoegaze", "Shoegaze", ["shoegaze"], "rock"),
    _g("post-rock", "Post-rock", ["post_rock"], "rock"),
    _g("progressive-rock", "Progressive rock", ["progressive_rock"], "rock"),
    _g("pop-punk", "Pop punk", ["pop_punk"], "rock"),
    _g("punk", "Punk", ["punk", "punk_rock"], "rock"),
    _g("grunge", "Grunge", ["grunge"], "rock"),
    _g("emo", "Emo", ["emo"], "rock"),
    _g("post-punk", "Post-punk", ["post_punk"], "rock"),
    _g("psychedelic-rock", "Psychedelic rock", ["psychedelic_rock"], "rock"),
    _g("math-rock", "Math rock", ["math_rock"], "rock", advanced=True),
    _g("noise-rock", "Noise rock", ["noise_rock"], "rock", advanced=True),
    _g("stoner-rock", "Stoner rock", ["stoner_rock"], "rock", advanced=True),

    _g("metal", "Metal", ["metal", "heavy_metal"], itunes=("Metal", "Heavy Metal")),
    _g("alternative-metal", "Alternative metal", ["alternative_metal"], "metal"),
    _g("metalcore", "Metalcore", ["metalcore", "melodic_metalcore"], "metal"),
    _g("progressive-metal", "Progressive metal", ["progressive_metal"], "metal"),
    _g("djent", "Djent", ["djent"], "metal"),
    _g("nu-metal", "Nu metal", ["nu_metal"], "metal"),
    _g("industrial-metal", "Industrial metal", ["industrial_metal"], "metal"),
    _g("symphonic-metal", "Symphonic metal", ["symphonic_metal"], "metal"),
    _g("power-metal", "Power metal", ["power_metal"], "metal", advanced=True),
    _g("gothic-metal", "Gothic metal", ["gothic_metal"], "metal", advanced=True),
    _g("folk-metal", "Folk metal", ["folk_metal"], "metal", advanced=True),
    _g("thrash-metal", "Thrash metal", ["thrash_metal"], "metal", advanced=True),
    _g("doom-metal", "Doom metal", ["doom_metal"], "metal", advanced=True),
    _g("sludge-metal", "Sludge metal", ["sludge_metal"], "metal", advanced=True),
    _g("post-metal", "Post-metal", ["post_metal"], "metal", advanced=True),
    _g("death-metal", "Death metal", ["death_metal"], "metal", advanced=True),
    _g("deathcore", "Deathcore", ["deathcore"], "metal", advanced=True),
    _g("black-metal", "Black metal", ["black_metal"], "metal", advanced=True),
    _g("mathcore", "Mathcore", ["mathcore"], "metal", advanced=True),
    _g("grindcore", "Grindcore", ["grindcore"], "metal", advanced=True),
)
# fmt: on

BY_ID: dict[str, Genre] = {g.id: g for g in GENRES}


class UnknownGenre(ValueError):
    pass


def validate(ids: Iterable[str]) -> list[str]:
    """The ids, de-duplicated in order; raises UnknownGenre for any unknown."""
    ids = list(dict.fromkeys(ids))
    unknown = [i for i in ids if i not in BY_ID]
    if unknown:
        raise UnknownGenre(f"Unknown genre ids: {unknown}")
    return ids


def children(genre_id: str) -> list[Genre]:
    return [g for g in GENRES if g.parent == genre_id]


def broad(genre_id: str) -> Genre:
    genre = BY_ID[genre_id]
    return BY_ID[genre.parent] if genre.parent else genre


def tag_ids(genre_ids: Iterable[str]) -> set[str]:
    """Qloo tag ids for the genres; a broad genre includes its subgenres."""
    ids: set[str] = set()
    for gid in genre_ids:
        ids.update(BY_ID[gid].tags)
        if BY_ID[gid].parent is None:
            for child in children(gid):
                ids.update(child.tags)
    return ids


def matched_genres(
    artist_tag_ids: Iterable[str], genre_ids: Iterable[str]
) -> list[str]:
    """Which of `genre_ids` the artist's Qloo genre tags confirm."""
    tags = set(artist_tag_ids)
    return [gid for gid in genre_ids if tags & tag_ids([gid])]


def itunes_matches(itunes_genre: str | None, genre_ids: Iterable[str]) -> list[str]:
    """Genres whose broad family lists this iTunes genre name exactly.

    iTunes genres are coarse ("Metal", "Alternative"), so this can only
    support a broad family, never confirm a specific subgenre.
    """
    families = catalog_families(itunes_genre)
    return [gid for gid in genre_ids if broad(gid).id in families]


def catalog_families(itunes_genre: str | None) -> set[str]:
    """Broad genre ids whose `itunes` names include this genre exactly.

    Empty for unknown or unmapped catalog genres (e.g. "Video Game").
    """
    if not itunes_genre:
        return set()
    name = itunes_genre.strip().casefold()
    return {
        g.id
        for g in GENRES
        if g.parent is None and name in (n.casefold() for n in g.itunes)
    }


# Broad families close enough that evidence for one does not contradict
# the other (a prog-metal band filed under "Rock" in iTunes).
ADJACENT = {
    frozenset(pair)
    for pair in (
        ("rock", "metal"),
        ("electronic", "lo-fi"),
        ("hip-hop", "lo-fi"),
        ("pop", "rnb-soul"),
        ("pop", "electronic"),
        ("folk", "country"),
        ("jazz", "rnb-soul"),
        ("electronic", "classical-score"),
    )
}


def families_agree(a: str, b: str) -> bool:
    return a == b or frozenset((a, b)) in ADJACENT


def tree() -> list[dict]:
    """JSON-ready hierarchy for the API."""
    return [
        {
            "id": g.id,
            "label": g.label,
            "subgenres": [
                {"id": c.id, "label": c.label, "advanced": c.advanced}
                for c in children(g.id)
            ],
        }
        for g in GENRES
        if g.parent is None
    ]


def _verify() -> int:  # pragma: no cover - live check
    """Confirm every tag id is still served by /v2/tags. Prints ids only."""
    from crosssignal.config import load_settings
    from crosssignal.qloo import MUSIC_GENRE_TAG, QlooClient

    client = QlooClient(load_settings().qloo, min_interval=0.15)
    missing = 0
    for genre in GENRES:
        for tag in genre.tags:
            slug = tag.removeprefix(TAG)
            found = client.tags(slug.replace("_", " "), [MUSIC_GENRE_TAG], take=50)
            ok = any(t.tag_id == tag for t in found)
            missing += not ok
            print(f"{'ok ' if ok else '?? '} {genre.id:24} {tag}")
    print(f"\n{missing} tag id(s) not returned by /v2/tags search "
          "(some appear only on artist entities; see module docstring).")  # fmt: skip
    return 0


if __name__ == "__main__":  # pragma: no cover
    parser = argparse.ArgumentParser(prog="python -m crosssignal.genres")
    parser.add_argument("--verify", action="store_true", help="check ids live")
    if parser.parse_args().verify:
        raise SystemExit(_verify())
    parser.print_help()
