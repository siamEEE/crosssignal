"""Natural-language description -> structured, *unconfirmed* interpretation.

The contract (`Interpretation`) is what an optional LLM such as Gemini
would produce: phrases to look up and music preferences drawn from fixed
vocabularies. It contains no ids. Every phrase is resolved through Qloo
search afterwards and the user confirms each match, so a model can
neither invent ids nor skip confirmation.

Safety rules for any interpreter (enforced by the schema, which has no
place for them): never infer or record a person's character, religion,
politics, health, ethnicity, sexuality or other identity traits; describe
cultural references only.

`interpret_deterministic` implements the contract without any model, so
the natural-language path works when Gemini is unavailable.
"""

import re
from dataclasses import dataclass, field

from crosssignal import genres
from crosssignal.catalog import normalize_name
from crosssignal.ranking import DISCOVERY_MODES, ERAS

MAX_PHRASES = 8
MAX_TEXT = 600


@dataclass(frozen=True)
class Mention:
    phrase: str
    category: str | None = None  # a culture.CATEGORIES id, if the source knows


@dataclass(frozen=True)
class MusicHints:
    preferred: tuple[str, ...] = ()  # genres.BY_ID ids
    avoided: tuple[str, ...] = ()
    era: str | None = None  # a ranking.ERAS key
    discovery: str | None = None  # a ranking.DISCOVERY_MODES value
    eras: tuple[str, ...] = ()


@dataclass(frozen=True)
class Interpretation:
    mentions: tuple[Mention, ...]
    music: MusicHints = field(default_factory=MusicHints)
    interpreter: str = "deterministic"  # or "gemini"


class InvalidInterpretation(ValueError):
    pass


def validate(interpretation: Interpretation) -> Interpretation:
    """Reject anything outside the fixed vocabularies (e.g. LLM output)."""
    from crosssignal.culture import CATEGORY_BY_ID

    if len(interpretation.mentions) > MAX_PHRASES:
        raise InvalidInterpretation(f"At most {MAX_PHRASES} mentions.")
    for mention in interpretation.mentions:
        if not mention.phrase.strip() or len(mention.phrase) > 120:
            raise InvalidInterpretation("Mentions must be 1-120 characters.")
        if mention.category is not None and mention.category not in CATEGORY_BY_ID:
            raise InvalidInterpretation(f"Unknown category: {mention.category}")
    music = interpretation.music
    try:
        genres.validate([*music.preferred, *music.avoided])
    except genres.UnknownGenre as exc:
        raise InvalidInterpretation(str(exc)) from exc
    if any(e not in ERAS for e in music.eras):
        raise InvalidInterpretation("Unknown release era")
    if music.era is not None and music.era not in ERAS:
        raise InvalidInterpretation(f"Unknown era: {music.era}")
    if music.discovery is not None and music.discovery not in DISCOVERY_MODES:
        raise InvalidInterpretation(f"Unknown discovery mode: {music.discovery}")
    return interpretation


# --- deterministic interpreter ---------------------------------------------

_SPLIT = re.compile(r"[,;\n•]+|\s+(?:and|plus|&|also|but)\s+|\.\s+", re.IGNORECASE)
_FILLER = re.compile(
    r"^(?:(?:and|also|but|plus|i|i'm|im|i am|we|my|me)\s+)*"
    r"(?:really\s+|totally\s+|absolutely\s+)?"
    r"(?:love|like|enjoy|adore|dig|am into|'m into|into|obsessed with|"
    r"(?:a |an )?(?:big |huge )?fan of|favou?rites? (?:are|is|include)|"
    r"listen to|play|playing|watch|watching|read|reading|"
    r"stuff like|things like|anything like|vibes? like|lots of)?\s*",
    re.IGNORECASE,
)
_NEGATION = re.compile(
    r"^(?:no|not|never|avoid|without|except|hate|dislike|don't like|do not like|"
    r"nothing|anything but|please no)\b\s*(?:like\s+|any\s+|more\s+)?",
    re.IGNORECASE,
)
_MUSIC_WORDS = re.compile(r"\b(?:music|songs?|bands?|artists?|vibes?|stuff)\b",
                          re.IGNORECASE)  # fmt: skip
_QUALIFIERS = {
    "mostly", "mainly", "some", "lots", "of", "a", "lot", "heavy", "especially",
    "plus", "also", "really", "too", "and", "the", "good", "great", "old", "new",
    "classic", "modern", "any", "kind", "sort", "more",
}  # fmt: skip
_TRAILING_FLUFF = re.compile(
    r"\s+(?:vibes?|aesthetics?|energy|feel|stuff|kind of things?)$", re.IGNORECASE
)
_LEADING_LIKE = re.compile(r"^\s*(?:like|such as|e g|eg|similar to)\s+", re.IGNORECASE)
_ERA_WORDS = {
    "pre-1980": r"\b(?:60s|70s|1960s|1970s|oldies|classic era)\b",
    "1980s": r"\b(?:80s|1980s|eighties)\b",
    "1990s": r"\b(?:90s|1990s|nineties)\b",
    "2000s": r"\b(?:2000s|00s|noughties|aughts)\b",
    "2010s": r"\b(?:2010s|10s)\b",
    "2020s": r"\b(?:2020s|20s)\b",
    "recent": r"\b(?:new music|recent|latest|newest|fresh releases?)\b",
}
_DISCOVERY_WORDS = {
    "adventurous": r"\b(?:hidden gems?|underground|obscure|lesser[- ]known|"
    r"deep cuts|niche|undiscovered|adventurous)\b",
    "familiar": r"\b(?:popular|well[- ]known|mainstream|big names|hits|familiar)\b",
}


def _genre_lookup() -> list[tuple[str, str]]:
    """(normalized label or alias, genre id), longest first."""
    pairs = []
    for genre in genres.GENRES:
        for name in {genre.label, genre.id.replace("-", " ")}:
            pairs.append((_norm(name), genre.id))
    return sorted(set(pairs), key=lambda p: -len(p[0]))


def _norm(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9&]+", " ", normalize_name(text)).split())


def _genres_in(phrase: str) -> tuple[list[str], str]:
    """Genre ids named in the phrase, and the phrase with them removed."""
    text = f" {_norm(phrase)} "
    found = []
    for name, gid in _genre_lookup():
        if f" {name} " in text:
            found.append(gid)
            text = text.replace(f" {name} ", " ")
    return found, " ".join(text.split())


def interpret_deterministic(text: str) -> Interpretation:
    """Rule-based reading of a description; every result still needs
    Qloo resolution and user confirmation."""
    text = text[:MAX_TEXT]
    preferred: list[str] = []
    avoided: list[str] = []
    eras = tuple(e for e, rx in _ERA_WORDS.items() if re.search(rx, text, re.IGNORECASE))
    era = eras[0] if len(eras) == 1 else None
    discovery = next(
        (d for d, rx in _DISCOVERY_WORDS.items() if re.search(rx, text, re.IGNORECASE)),
        None,
    )

    mentions: list[Mention] = []
    for raw in _SPLIT.split(text):
        phrase = raw.strip(" .!?\"'()")
        if not phrase:
            continue
        negated = bool(_NEGATION.match(phrase))
        phrase = _NEGATION.sub("", phrase)
        phrase = _FILLER.sub("", phrase).strip(" .!?\"'()")
        found, rest = _genres_in(phrase)
        if found:
            (avoided if negated else preferred).extend(found)
            # "metalcore" alone is a music preference, not a cultural
            # mention; "post-rock like Mogwai" leaves "Mogwai" to look up.
            phrase = _LEADING_LIKE.sub("", _MUSIC_WORDS.sub(" ", rest)).strip()
            if set(phrase.split()) <= _QUALIFIERS:
                phrase = ""
        if negated or len(phrase) < 2:
            continue
        if any(re.search(rx, phrase, re.IGNORECASE) for rx in _ERA_WORDS.values()):
            continue
        if any(
            re.search(rx, phrase, re.IGNORECASE) for rx in _DISCOVERY_WORDS.values()
        ):
            continue
        phrase = _TRAILING_FLUFF.sub("", phrase)
        if len(phrase) >= 2:
            mentions.append(Mention(phrase))

    first_seen: dict[str, Mention] = {}
    for mention in mentions:
        first_seen.setdefault(mention.phrase.casefold(), mention)
    music = MusicHints(
        tuple(dict.fromkeys(p for p in preferred if p not in avoided)),
        tuple(dict.fromkeys(avoided)),
        era,
        discovery,
        eras,
    )
    return Interpretation(tuple(first_seen.values())[:MAX_PHRASES], music)
