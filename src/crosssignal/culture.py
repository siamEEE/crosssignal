"""Cultural interests: categories, Qloo search and resolution.

Human categories map onto Qloo entity types or tag types verified live
(2026-10-21). Anime and web series resolve as TV/movie entities, manga
and comics as books. Aesthetics resolve only to existing Qloo tags. An
id is only ever taken from a Qloo search result; nothing here builds one.
"""

import re
from dataclasses import dataclass
from enum import StrEnum

from crosssignal.catalog import normalize_name
from crosssignal.qloo import QlooClient, QlooEntity, QlooTag


class Kind(StrEnum):
    ENTITY = "entity"  # sent as signal.interests.entities
    TAG = "tag"  # sent as signal.interests.tags


@dataclass(frozen=True)
class Category:
    id: str
    label: str
    hint: str  # what belongs here, shown in the UI
    kind: Kind
    types: tuple[str, ...]  # Qloo entity types, or tag types for TAG


# fmt: off
CATEGORIES: tuple[Category, ...] = (
    Category("screen", "Film, TV & anime", "Films, series, anime, web series",
             Kind.ENTITY, ("urn:entity:movie", "urn:entity:tv_show")),
    Category("games", "Video games", "Console, PC and indie games",
             Kind.ENTITY, ("urn:entity:videogame",)),
    Category("books", "Books, manga & comics", "Novels, manga, comics",
             Kind.ENTITY, ("urn:entity:book",)),
    Category("people", "People & creators", "Directors, authors, creators",
             Kind.ENTITY, ("urn:entity:person",)),
    Category("podcasts", "Podcasts", "Shows you listen to",
             Kind.ENTITY, ("urn:entity:podcast",)),
    Category("brands", "Fashion, brands & scenes", "Labels, brands, streetwear",
             Kind.ENTITY, ("urn:entity:brand",)),
    Category("places", "Places & travel", "Cities, destinations, venues",
             Kind.ENTITY, ("urn:entity:destination", "urn:entity:place")),
    # Tag types that held aesthetics in live /v2/tags results. Audience and
    # identity-like tag types are deliberately not offered.
    Category("aesthetics", "Aesthetics & moods", "Dark academia, cottagecore, cyberpunk",
             Kind.TAG, ("urn:tag:ambience:qloo", "urn:tag:style:qloo",
                        "urn:tag:genre:media", "urn:tag:subgenre:qloo")),
)
# fmt: on

CATEGORY_BY_ID = {c.id: c for c in CATEGORIES}
TYPE_LABELS = {
    "urn:entity:movie": "Film",
    "urn:entity:tv_show": "TV",
    "urn:entity:videogame": "Game",
    "urn:entity:book": "Book",
    "urn:entity:person": "Person",
    "urn:entity:podcast": "Podcast",
    "urn:entity:brand": "Brand",
    "urn:entity:destination": "Destination",
    "urn:entity:place": "Place",
    "urn:tag:ambience:qloo": "Ambience",
    "urn:tag:style:qloo": "Style",
    "urn:tag:genre:media": "Media genre",
    "urn:tag:subgenre:qloo": "Subgenre",
}


@dataclass(frozen=True)
class Candidate:
    """A Qloo entity or tag the user can confirm as an interest."""

    id: str
    kind: Kind
    name: str
    category: str  # a CATEGORIES id
    qloo_type: str
    type_label: str
    year: int | None = None
    disambiguation: str | None = None
    image_url: str | None = None
    popularity: float | None = None


class Match(StrEnum):
    EXACT = "exact"  # exactly one candidate has the query's name
    AMBIGUOUS = "ambiguous"  # several share the name; the user must pick
    SUGGESTIONS = "suggestions"  # no exact name match; related results only
    NONE = "none"


@dataclass(frozen=True)
class Resolution:
    query: str
    category: str | None
    match: Match
    candidates: tuple[Candidate, ...]


# "Dune (Dune, #1)" -> "Dune"; series markers only, not real subtitles.
_SERIES = re.compile(r"\s*\([^()]*#\s*\d+[^()]*\)\s*$")


def comparable(name: str) -> str:
    return normalize_name(_SERIES.sub("", name))


def _category_for(entity_types: tuple[str, ...]) -> Category | None:
    for category in CATEGORIES:
        if category.kind is Kind.ENTITY and set(category.types) & set(entity_types):
            return category
    return None


def entity_candidate(entity: QlooEntity) -> Candidate | None:
    category = _category_for(entity.types)
    if category is None:
        return None
    qloo_type = next(t for t in entity.types if t in category.types)
    return Candidate(
        id=entity.entity_id,
        kind=Kind.ENTITY,
        name=entity.name,
        category=category.id,
        qloo_type=qloo_type,
        type_label=TYPE_LABELS.get(qloo_type, "Entity"),
        year=entity.year,
        disambiguation=entity.disambiguation,
        image_url=entity.image_url,
        popularity=entity.popularity,
    )


def tag_candidate(tag: QlooTag) -> Candidate:
    return Candidate(
        id=tag.tag_id,
        kind=Kind.TAG,
        name=tag.name,
        category="aesthetics",
        qloo_type=tag.tag_type,
        type_label=TYPE_LABELS.get(tag.tag_type, "Tag"),
    )


def search(
    client: QlooClient, query: str, category_id: str | None, take: int = 12
) -> list[Candidate]:
    """Qloo candidates for free text, in Qloo's order.

    With no category, every entity category is searched in one call.
    Aesthetics are searched only when asked for, since tags need a
    different endpoint and are a different kind of signal.
    """
    query = query.strip()
    if not query:
        return []
    if category_id is not None and category_id not in CATEGORY_BY_ID:
        raise ValueError(f"Unknown category: {category_id}")
    category = CATEGORY_BY_ID.get(category_id) if category_id else None

    if category is not None and category.kind is Kind.TAG:
        tags = client.tags(query, category.types, take)
        return list(dict.fromkeys(tag_candidate(t) for t in tags))

    types = (
        category.types
        if category
        else tuple(t for c in CATEGORIES if c.kind is Kind.ENTITY for t in c.types)
    )
    found = (entity_candidate(e) for e in client.search(query, types, take))
    unique: dict[str, Candidate] = {}
    for candidate in found:
        if candidate is not None:
            unique.setdefault(candidate.id, candidate)
    return list(unique.values())


def resolve(
    client: QlooClient, query: str, category_id: str | None, take: int = 8
) -> Resolution:
    """Search, then classify how certain the match is.

    Only a single exact (normalized) name match counts as resolved;
    several exact matches ("Drive", "Twin Peaks") need the user to choose.
    """
    candidates = search(client, query, category_id, take)
    wanted = comparable(query)
    exact = [c for c in candidates if comparable(c.name) == wanted]
    if len(exact) == 1:
        match, ordered = Match.EXACT, exact + [c for c in candidates if c not in exact]
    elif len(exact) > 1:
        ordered = sorted(exact, key=lambda c: -(c.popularity or 0.0))
        match = Match.AMBIGUOUS
    elif candidates:
        match, ordered = Match.SUGGESTIONS, candidates
    else:
        match, ordered = Match.NONE, []
    return Resolution(query, category_id, match, tuple(ordered))


@dataclass(frozen=True)
class FeaturedItem:
    query: str
    category: str


@dataclass(frozen=True)
class Collection:
    id: str
    title: str
    blurb: str
    accent: str  # a design token name used by the frontend
    items: tuple[FeaturedItem, ...]


def _items(*pairs: tuple[str, str]) -> tuple[FeaturedItem, ...]:
    return tuple(FeaturedItem(q, c) for q, c in pairs)


# Inspiration only: names, not ids. Each item is resolved live through
# Qloo search when chosen, exactly like typed text.
FEATURED: tuple[Collection, ...] = (
    Collection("neon", "Neon after dark", "Rain-slick cities and chrome.", "violet",
               _items(("Blade Runner 2049", "screen"), ("Drive", "screen"),
                      ("Cyberpunk 2077", "games"), ("Cyberpunk", "aesthetics"))),
    Collection("cosmic", "Cosmic & cinematic", "Big skies, slow reveals.", "lime",
               _items(("Interstellar", "screen"), ("Arrival", "screen"),
                      ("Outer Wilds", "games"), ("Dune", "books"))),
    Collection("cozy", "Cozy worlds", "Warm light and small rituals.", "apricot",
               _items(("Spirited Away", "screen"), ("Stardew Valley", "games"),
                      ("Cottagecore", "aesthetics"), ("Hayao Miyazaki", "people"))),
    Collection("anime", "Anime & manga", "Epic arcs, inked pages.", "coral",
               _items(("Attack on Titan", "screen"), ("Cowboy Bebop", "screen"),
                      ("Berserk", "books"), ("Chainsaw Man", "books"))),
    Collection("scenes", "Scenes & places", "Streetwear, cities, rooms.", "ink",
               _items(("Supreme", "brands"), ("Paris", "places"),
                      ("Tokyo", "places"), ("Dark Academia", "aesthetics"))),
)  # fmt: skip
