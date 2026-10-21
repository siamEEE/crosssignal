"""Pure metric functions. No I/O, no network, no randomness.

None means "not applicable / not measurable", which is reported as such
rather than coerced to 0 or 1.

Important limit: these metrics check structure, grounding *references*,
availability and diversity. None of them measures whether a
recommendation is a good musical fit; that needs human judgment
(see evaluation.human) or real behavioural data.
"""

import math
from collections import Counter
from collections.abc import Iterable, Sequence
from itertools import combinations

from crosssignal.evaluation.catalog_probe import ArtistAvailability, Availability
from crosssignal.evaluation.schemas import RecommendedArtist, interest_key


def ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def mean(values: Iterable[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    return sum(present) / len(present) if present else None


def duplicate_rate(names: Sequence[str]) -> float | None:
    """Share of list slots wasted on repeats of an earlier artist."""
    keys = [interest_key(n) for n in names]
    return ratio(len(keys) - len(set(keys)), len(keys))


def grounding(
    artists: Sequence[RecommendedArtist], profile_interests: Sequence[str]
) -> dict[str, float | int | None]:
    """Referential grounding: are cited reasons real inputs?

    grounded_rate: artists citing >=1 interest, all of which are inputs.
    uncited_rate: artists with no stated reason.
    invalid_citations: cited names that are not inputs (hallucinated).
    This checks that a reason points at the user's input, not that the
    reason is musically sensible.
    """
    inputs = {interest_key(n) for n in profile_interests}
    grounded = uncited = invalid = 0
    for artist in artists:
        cited = [interest_key(c) for c in artist.cited_interests]
        bad = [c for c in cited if c not in inputs]
        invalid += len(bad)
        if not cited:
            uncited += 1
        elif not bad:
            grounded += 1
    return {
        "grounded_rate": ratio(grounded, len(artists)),
        "uncited_rate": ratio(uncited, len(artists)),
        "invalid_citations": invalid,
    }


def interest_coverage(
    artists: Sequence[RecommendedArtist], profile_interests: Sequence[str]
) -> float | None:
    """Share of distinct input interests cited by at least one artist."""
    inputs = {interest_key(n) for n in profile_interests}
    cited = {interest_key(c) for a in artists for c in a.cited_interests}
    return ratio(len(inputs & cited), len(inputs))


def availability(
    results: Sequence[ArtistAvailability],
) -> dict[str, float | int | None]:
    """Track availability among artists the catalog actually answered for.

    Failed and unmeasured lookups are excluded from the rate and counted
    separately, so an outage is not mistaken for missing music.
    """
    counts = Counter(r.status for r in results)
    found = counts[Availability.FOUND]
    answered = found + counts[Availability.NOT_FOUND]
    return {
        "available_rate": ratio(found, answered),
        "catalog_found": found,
        "catalog_answered": answered,
        "catalog_errors": counts[Availability.ERROR],
        "catalog_unmeasured": counts[Availability.UNMEASURED],
    }


def normalized_entropy(labels: Sequence[str]) -> float | None:
    """Shannon entropy of labels scaled to [0, 1].

    Scaled by log(len(labels)), the maximum reachable for this many
    items: 1.0 = every item has a different label, 0.0 = all the same.
    """
    if not labels:
        return None
    counts = Counter(labels)
    if len(counts) == 1:
        return 0.0
    total = len(labels)
    entropy = -sum((c / total) * math.log(c / total) for c in counts.values())
    return entropy / math.log(total)


def genre_diversity(results: Sequence[ArtistAvailability]) -> dict[str, float | None]:
    """Diversity of catalog primary genres among found artists.

    Uses iTunes primaryGenreName, which is coarse ("Soundtrack",
    "Electronic"); treat it as a rough spread signal only.
    """
    genres = [
        r.genres[0] for r in results if r.status is Availability.FOUND and r.genres
    ]
    return {
        "genre_entropy": normalized_entropy(genres),
        "distinct_genre_ratio": ratio(len(set(genres)), len(genres)),
    }


def jaccard(a: Iterable[str], b: Iterable[str]) -> float | None:
    sa, sb = {interest_key(x) for x in a}, {interest_key(x) for x in b}
    return ratio(len(sa & sb), len(sa | sb))


def rank_biased_overlap(
    a: Sequence[str], b: Sequence[str], p: float = 0.9
) -> float | None:
    """Truncated rank-biased overlap, normalized so identical lists give 1.

    Webber, Moffat & Zobel (2010). Weighs agreement near the top of both
    lists more than agreement further down. Depth = the longer list.
    """
    if not 0 < p < 1:
        raise ValueError("p must be in (0, 1)")
    depth = max(len(a), len(b))
    if depth == 0:
        return None
    ka, kb = [interest_key(x) for x in a], [interest_key(x) for x in b]
    score = 0.0
    for d in range(1, depth + 1):
        agreement = len(set(ka[:d]) & set(kb[:d])) / d
        score += p ** (d - 1) * agreement
    return (1 - p) * score / (1 - p**depth)


def cross_profile_diversity(lists: Sequence[Sequence[str]]) -> dict[str, float | None]:
    """How much recommendations change between different profiles.

    distinct_artist_ratio: distinct artists / total slots across profiles.
    mean_pairwise_jaccard: average overlap between two profiles' lists;
    high values mean everyone gets roughly the same artists.
    """
    nonempty = [list(x) for x in lists if x]
    slots = sum(len(x) for x in nonempty)
    distinct = {interest_key(n) for x in nonempty for n in x}
    pairs = [jaccard(x, y) for x, y in combinations(nonempty, 2)]
    return {
        "distinct_artist_ratio": ratio(len(distinct), slots),
        "mean_pairwise_jaccard": mean(pairs),
    }


def percentile(values: Sequence[float], q: float) -> float | None:
    """Linear-interpolated percentile, q in [0, 100]."""
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * q / 100
    low, high = math.floor(position), math.ceil(position)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def wilson_interval(
    successes: int, trials: int, z: float = 1.96
) -> tuple[float, float] | None:
    """Wilson score interval for a proportion (default 95%)."""
    if trials == 0:
        return None
    phat = successes / trials
    denom = 1 + z**2 / trials
    centre = (phat + z**2 / (2 * trials)) / denom
    margin = z * math.sqrt(phat * (1 - phat) / trials + z**2 / (4 * trials**2)) / denom
    return (max(0.0, centre - margin), min(1.0, centre + margin))
