"""Deterministic, explainable ranking of Qloo-recommended artists.

Pure functions only: no HTTP. Ranking is lexicographic so its behaviour
can be stated in one sentence: genre compatibility tier first, then a
weighted relevance score, then name. The score combines Qloo's own rank
for the user's interests with optional era and familiarity fit. It is a
product heuristic for ordering, never shown as a probability.

Genre evidence comes from two independent sources: the artist's Qloo
music-genre tag ids and its dominant iTunes genre. Live data showed Qloo
tags alone are noisy (a pop star tagged black metal), so a match is only
*confirmed* when both sources agree:

    fit         support   meaning
    PREFERRED   both      Qloo tag + agreeing catalog genre   (tier 0)
    OPEN        both                                          (tier 1)
    NEUTRAL     -         no genre preferences given          (tier 1)
    PREFERRED   qloo      Qloo tag; catalog genre unknown     (tier 2)
    OPEN        qloo                                          (tier 3)
    PREFERRED   catalog   catalog family only, no Qloo tag    (tier 4)
    OPEN        catalog                                       (tier 5)
    UNVERIFIED  -         no genre evidence at all            (tier 6)
    CONFLICT    -         Qloo tag, but catalog says an unrelated family (excluded)
    MISMATCH    -         evidence fits nothing chosen        (excluded)
    AVOIDED     -         corroborated avoided genre          (excluded)
"""

import datetime
import math
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from crosssignal import genres
from crosssignal.catalog import base_title
from crosssignal.models import Evidence, Track

THIS_YEAR = datetime.date.today().year
ERAS: dict[str, tuple[int, int]] = {
    "pre-1980": (0, 1979),
    "1980s": (1980, 1989),
    "1990s": (1990, 1999),
    "2000s": (2000, 2009),
    "2010s": (2010, 2019),
    "2020s": (2020, 2029),
    "recent": (THIS_YEAR - 4, THIS_YEAR),
}
DISCOVERY_MODES = ("familiar", "balanced", "adventurous")

# Qloo `filter.popularity.*` bounds (popularity percentile, 0-1) per mode.
# Values chosen from live observation: most well-known artists returned
# for films sat at 0.9+; a 0.8 cap still returned relevant artists.
POPULARITY_BOUNDS: dict[str, tuple[float | None, float | None]] = {
    "familiar": (0.9, None),
    "balanced": (None, None),
    "adventurous": (None, 0.85),
}

WEIGHT_RELEVANCE = 0.6
WEIGHT_ERA = 0.2
WEIGHT_FAMILIARITY = 0.2
BONUS_PER_EXTRA_INTEREST = 0.1


class GenreFit(StrEnum):
    PREFERRED = "preferred"
    OPEN = "open"
    NEUTRAL = "neutral"
    UNVERIFIED = "unverified"
    CONFLICT = "conflict"
    MISMATCH = "mismatch"
    AVOIDED = "avoided"


class Support(StrEnum):
    BOTH = "both"  # Qloo tag and catalog genre agree: confirmed
    QLOO = "qloo"  # Qloo tag only; no usable catalog genre
    CATALOG = "catalog"  # catalog genre family only; no Qloo tag


EXCLUDED = {GenreFit.CONFLICT, GenreFit.MISMATCH, GenreFit.AVOIDED}
_TIERS = {
    (GenreFit.PREFERRED, Support.BOTH): 0,
    (GenreFit.OPEN, Support.BOTH): 1,
    (GenreFit.NEUTRAL, None): 1,
    (GenreFit.PREFERRED, Support.QLOO): 2,
    (GenreFit.OPEN, Support.QLOO): 3,
    (GenreFit.PREFERRED, Support.CATALOG): 4,
    (GenreFit.OPEN, Support.CATALOG): 5,
    (GenreFit.UNVERIFIED, None): 6,
}


@dataclass(frozen=True)
class Preferences:
    preferred: tuple[str, ...] = ()
    open_to: tuple[str, ...] = ()
    avoided: tuple[str, ...] = ()
    era: str | None = None
    discovery: str = "balanced"
    eras: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        genres.validate([*self.preferred, *self.open_to, *self.avoided])
        overlap = set(self.avoided) & set(self.preferred + self.open_to)
        if overlap:
            raise ValueError(f"Genres both wanted and avoided: {sorted(overlap)}")
        chosen = (*self.eras, *((self.era,) if self.era is not None else ()))
        if any(era not in ERAS for era in chosen):
            raise ValueError("Unknown release era")
        # Canonical order keeps scoring and track selection independent of click order.
        object.__setattr__(self, "eras", tuple(era for era in ERAS if era in chosen))
        if self.discovery not in DISCOVERY_MODES:
            raise ValueError(f"Unknown discovery mode: {self.discovery}")

    @property
    def wants_genres(self) -> bool:
        return bool(self.preferred or self.open_to)


@dataclass(frozen=True)
class GenreVerdict:
    fit: GenreFit
    matched: tuple[str, ...] = ()  # genre ids the evidence supports
    support: Support | None = None
    # BOTH via a related family (Qloo: electronic, catalog: Pop) rather
    # than the same one; the UI must not call that full agreement.
    related_only: bool = False

    @property
    def tier(self) -> int:
        return _TIERS[(self.fit, self.support)]


def _support(gids: list[str], families: set[str]) -> Support | None:
    """How the catalog relates to Qloo-matched genres; None = contradicts."""
    if not families:
        return Support.QLOO
    if any(
        genres.families_agree(genres.broad(g).id, f) for g in gids for f in families
    ):
        return Support.BOTH
    return None


def _avoided(tags: set[str], families: set[str], catalog_genre, prefs) -> list[str]:
    wanted = genres.matched_genres(tags, prefs.preferred + prefs.open_to)
    hits = [
        a
        for a in genres.matched_genres(tags, prefs.avoided)
        # Avoiding broad "Metal" while preferring "Metalcore": the wanted
        # subgenre beats the broad avoidance of its parent.
        if not any(genres.BY_ID[w].parent == a for w in wanted)
        and _support([a], families) is not None
    ]
    if not wanted:  # a Qloo-confirmed wanted genre outranks a coarse catalog label
        hits += genres.itunes_matches(
            catalog_genre, [g for g in prefs.avoided if genres.BY_ID[g].parent is None]
        )
    return list(dict.fromkeys(hits))


def genre_verdict(
    tag_ids: Iterable[str], catalog_genre: str | None, prefs: Preferences
) -> GenreVerdict:
    """Classify an artist's genre evidence against the preferences.

    `tag_ids` are the artist's Qloo urn:tag:genre:music ids;
    `catalog_genre` is its dominant iTunes primaryGenreName, if known
    (None before the catalog has been checked).
    """
    tags = set(tag_ids)
    families = genres.catalog_families(catalog_genre)
    if avoided := _avoided(tags, families, catalog_genre, prefs):
        return GenreVerdict(GenreFit.AVOIDED, tuple(avoided))
    if not prefs.wants_genres:
        return GenreVerdict(GenreFit.NEUTRAL)

    conflict = False
    for fit, wanted in ((GenreFit.PREFERRED, prefs.preferred),
                        (GenreFit.OPEN, prefs.open_to)):  # fmt: skip
        if hit := genres.matched_genres(tags, wanted):
            supported = [g for g in hit if _support([g], families) is not None]
            support = _support(supported, families) if supported else None
            if support is not None:
                related = support is Support.BOTH and any(
                    genres.broad(g).id not in families for g in supported
                )
                return GenreVerdict(fit, tuple(supported), support, related)
            conflict = True
    for fit, wanted in ((GenreFit.PREFERRED, prefs.preferred),
                        (GenreFit.OPEN, prefs.open_to)):  # fmt: skip
        # The catalog is coarse: it can support a family, never a subgenre.
        if broad := [g for g in dict.fromkeys(genres.broad(w).id for w in wanted)
                     if g in families]:  # fmt: skip
            return GenreVerdict(fit, tuple(broad), Support.CATALOG)
    if conflict:
        return GenreVerdict(GenreFit.CONFLICT)
    if not tags and not families:
        return GenreVerdict(GenreFit.UNVERIFIED)
    return GenreVerdict(GenreFit.MISMATCH)


def tag_share(tag_ids: Iterable[str], genre_ids: Iterable[str]) -> float:
    """Share of an artist's Qloo genre tags that fall in the chosen genres."""
    tags = set(tag_ids)
    return len(tags & genres.tag_ids(genre_ids)) / len(tags) if tags else 0.0


@dataclass(frozen=True)
class EraFit:
    in_era: int
    dated: int  # tracks with a known year

    @property
    def share(self) -> float | None:
        return self.in_era / self.dated if self.dated else None


def selected_eras(eras: str | Sequence[str] | None) -> tuple[str, ...]:
    if isinstance(eras, str):
        return (eras,)
    return tuple(eras or ())


def year_matches(year: int, eras: Sequence[str]) -> bool:
    return any(ERAS[era][0] <= year <= ERAS[era][1] for era in eras)


def era_fit(tracks: Sequence[Track], era: str | Sequence[str] | None) -> EraFit | None:
    eras = selected_eras(era)
    if not eras:
        return None
    years = [int(t.year) for t in tracks if t.year and t.year.isdigit()]
    # Count the union, so a recent release also in the 2020s is counted once.
    return EraFit(sum(year_matches(year, eras) for year in years), len(years))


def familiarity_term(popularity: float | None, mode: str) -> float:
    """0-1 fit of Qloo's popularity percentile to the discovery mode.

    Neutral (0.5) when the mode is balanced or popularity is unknown.
    """
    if popularity is None or mode == "balanced":
        return 0.5
    return popularity if mode == "familiar" else 1.0 - popularity


@dataclass(frozen=True)
class Candidate:
    """An artist Qloo returned, with everything the ranker may use."""

    entity_id: str
    name: str
    evidence: tuple[Evidence, ...]  # one per interest that produced it
    pool_size: int  # how many artists each Qloo query returned (for rank scaling)
    popularity: float | None = None
    genre_tags: tuple[tuple[str, str], ...] = ()
    image_url: str | None = None
    source: str = "filtered"  # "filtered", "unfiltered" or "more_like"


@dataclass(frozen=True)
class Ranked:
    candidate: Candidate
    verdict: GenreVerdict
    score: float
    tracks: tuple[Track, ...] = ()
    catalog_genre: str | None = None
    era: EraFit | None = None


def relevance(candidate: Candidate) -> float:
    """1.0 for Qloo's #1 artist of an interest, falling linearly with rank."""
    best = min(e.rank for e in candidate.evidence)
    pool = max(candidate.pool_size, 1)
    extra = BONUS_PER_EXTRA_INTEREST * (len(candidate.evidence) - 1)
    return max(0.0, 1.0 - (best - 1) / pool) + extra


def score(candidate: Candidate, era: EraFit | None, prefs: Preferences) -> float:
    era_term = 0.5
    if era is not None and era.share is not None:
        era_term = era.share
    return round(
        WEIGHT_RELEVANCE * relevance(candidate)
        + WEIGHT_ERA * era_term
        + WEIGHT_FAMILIARITY * familiarity_term(candidate.popularity, prefs.discovery),
        6,
    )


def sort_key(item: Ranked) -> tuple:
    return (item.verdict.tier, -item.score, item.candidate.name.casefold())


def dominant_genre(tracks: Sequence[Track]) -> str | None:
    counts = Counter(t.genre for t in tracks if t.genre)
    if not counts:
        return None
    top = max(counts.values())
    return min(g for g, n in counts.items() if n == top)


def select_tracks(
    tracks: Sequence[Track], era: str | Sequence[str] | None,
    shown_urls: set[str], limit: int = 3
) -> tuple[Track, ...]:
    """Pick songs to show instead of the first catalog hits.

    Skips songs already shown on another card and repeated versions of a
    song, then prefers: in-era releases, playable previews and distinct
    albums, keeping catalog order (sole credits first) within ties.
    """
    eras = selected_eras(era)
    seen_titles: set[str] = set()
    pool = []
    for position, track in enumerate(tracks):
        key = base_title(track.title)
        if track.url in shown_urls or key in seen_titles:
            continue
        seen_titles.add(key)
        in_era = bool(
            track.year and track.year.isdigit()
            and (not eras or year_matches(int(track.year), eras))
        )
        pool.append((not in_era, track.preview_url is None, position, track))
    pool.sort(key=lambda entry: entry[:3])

    picked: list[Track] = []
    albums: set[str] = set()
    # Represent selected eras before filling remaining slots. A track can cover
    # overlapping ranges, but is never selected twice. Missing sample years do
    # not exclude the artist or imply anything about its complete discography.
    covered: set[str] = set()
    for selected in eras if len(eras) > 1 else ():
        if selected in covered or len(picked) == limit:
            continue
        for *_, track in pool:
            if track in picked or not track.year or not track.year.isdigit():
                continue
            year = int(track.year)
            if year_matches(year, (selected,)):
                picked.append(track)
                if track.album:
                    albums.add(track.album)
                covered.update(e for e in eras if year_matches(year, (e,)))
                break
    for distinct_only in (True, False):
        for *_, track in pool:
            if len(picked) == limit:
                break
            if track in picked or (distinct_only and track.album in albums):
                continue
            picked.append(track)
            if track.album:
                albums.add(track.album)
    order = {id(t): i for i, (*_, t) in enumerate(pool)}
    return tuple(sorted(picked, key=lambda t: order[id(t)]))


def diversify(items: Sequence[Ranked], limit: int, interest_count: int) -> list[Ranked]:
    """Take `limit` items in rank order, capping how many any one interest
    contributes on the first pass so every interest is represented."""
    cap = math.ceil(limit / max(interest_count, 1)) + 1
    used: Counter[str] = Counter()
    chosen: list[Ranked] = []
    for item in items:
        owner = min(item.candidate.evidence, key=lambda e: e.rank).signal_id
        if used[owner] < cap:
            chosen.append(item)
            used[owner] += 1
        if len(chosen) == limit:
            return chosen
    for item in items:
        if item not in chosen:
            chosen.append(item)
        if len(chosen) == limit:
            break
    return chosen


@dataclass
class Tally:
    """Why candidates did not make it, for an honest summary."""

    qloo_candidates: int = 0
    avoided: int = 0
    mismatched: int = 0
    conflicting: int = 0  # Qloo tag vs catalog genre disagree
    no_catalog_match: int = 0
    catalog_errors: int = 0
    disliked: int = 0
    lookups: int = 0
    fallback_used: bool = False
    excluded_names: dict[str, list[str]] = field(default_factory=dict)

    def exclude(self, reason: str, name: str) -> None:
        self.excluded_names.setdefault(reason, []).append(name)
