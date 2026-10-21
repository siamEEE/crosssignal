"""Run providers over the profile set and compute metrics.

Everything in the result except the `timing` section is a pure function
of (profiles, provider outputs, catalog answers), so a run against a
catalog snapshot is reproducible byte for byte.
"""

import time
from collections import Counter
from collections.abc import Callable, Sequence
from itertools import combinations

from crosssignal.evaluation import metrics
from crosssignal.evaluation.catalog_probe import ArtistAvailability, CatalogProbe
from crosssignal.evaluation.providers import EvalProvider
from crosssignal.evaluation.schemas import (
    MAX_ARTISTS,
    Expectation,
    Profile,
    RecommendationRequest,
    RecommendationResponse,
    ResponseStatus,
)

SCHEMA_VERSION = 1

# Questions these automated metrics cannot answer; stated in every report.
NOT_MEASURED = {
    "musical_fit": "Whether artists suit the profile. Needs human judgment "
    "(pairwise preference via `evaluation pairs`) - a preference, not accuracy.",
    "explanation_quality": "Whether the stated reason is convincing. Needs "
    "human judgment; grounded_rate only checks that reasons cite real inputs.",
    "qloo_affinity": "Qloo affinity scores and their calibration. Needs real "
    "Qloo responses; no scores are produced or estimated here.",
    "qloo_entity_resolution": "How often Qloo resolves free-text interests "
    "to entities. Needs Qloo search API access.",
    "novelty_vs_user_history": "Whether artists are new to the user. Needs "
    "listening history, which CrossSignal does not collect.",
}


class Outcome:
    ANSWERED = "answered"
    ABSTAINED = "abstained"  # unsupported: honest "I don't know"
    CORRECT_REJECTION = "correct_rejection"
    WRONG_REJECTION = "wrong_rejection"  # refused a valid request
    MISSED_REJECTION = "missed_rejection"  # answered an invalid request
    ERROR = "error"


def classify(expect: Expectation, response: RecommendationResponse) -> str:
    status = response.status
    if status is ResponseStatus.ERROR:
        return Outcome.ERROR
    if expect is Expectation.REJECT:
        rejected = status is ResponseStatus.REJECTED
        return Outcome.CORRECT_REJECTION if rejected else Outcome.MISSED_REJECTION
    if status is ResponseStatus.REJECTED:
        return Outcome.WRONG_REJECTION
    if status is ResponseStatus.UNSUPPORTED or not response.artists:
        return Outcome.ABSTAINED
    return Outcome.ANSWERED


def score_response(
    profile: Profile,
    response: RecommendationResponse,
    catalog: Sequence[ArtistAvailability],
    max_artists: int,
) -> dict:
    """Per-profile record. Quality metrics only for answered requests."""
    outcome = classify(profile.expect, response)
    names = [a.name for a in response.artists]
    record = {
        "profile_id": profile.id,
        "provider": response.provider,
        "tags": list(profile.tags),
        "status": str(response.status),
        "outcome": outcome,
        "error": response.error,
        "unsupported_interests": list(response.unsupported_interests),
        "artists": names,
    }
    if outcome != Outcome.ANSWERED:
        return record
    interests = [i.name for i in profile.interests]
    record.update(
        {
            "artist_count": len(names),
            "within_limit": len(names) <= max_artists,
            "duplicate_rate": metrics.duplicate_rate(names),
            **metrics.grounding(response.artists, interests),
            "interest_coverage": metrics.interest_coverage(response.artists, interests),
            **metrics.availability(catalog),
            **metrics.genre_diversity(catalog),
            "provider_scores_present": sum(
                a.score is not None for a in response.artists
            ),
        }
    )
    return record


def _aggregate(records: Sequence[dict]) -> dict:
    answered = [r for r in records if r["outcome"] == Outcome.ANSWERED]
    found = sum(r["catalog_found"] for r in answered)
    probed = sum(r["catalog_answered"] for r in answered)
    return {
        "answered": len(answered),
        "mean_grounded_rate": metrics.mean(r["grounded_rate"] for r in answered),
        "mean_uncited_rate": metrics.mean(r["uncited_rate"] for r in answered),
        "invalid_citations": sum(r["invalid_citations"] for r in answered),
        "mean_interest_coverage": metrics.mean(
            r["interest_coverage"] for r in answered
        ),
        "mean_duplicate_rate": metrics.mean(r["duplicate_rate"] for r in answered),
        "within_limit_rate": metrics.ratio(
            sum(r["within_limit"] for r in answered), len(answered)
        ),
        "pooled_available_rate": metrics.ratio(found, probed),
        "catalog_errors": sum(r["catalog_errors"] for r in answered),
        "catalog_unmeasured": sum(r["catalog_unmeasured"] for r in answered),
        "mean_genre_entropy": metrics.mean(r["genre_entropy"] for r in answered),
        "provider_scores_present": sum(r["provider_scores_present"] for r in answered),
        **metrics.cross_profile_diversity([r["artists"] for r in answered]),
    }


def summarize_provider(records: Sequence[dict], common: set[str]) -> dict:
    outcomes = Counter(r["outcome"] for r in records)
    return {
        "profiles": len(records),
        "outcomes": dict(sorted(outcomes.items())),
        "provider_error_rate": metrics.ratio(outcomes[Outcome.ERROR], len(records)),
        "all_answered": _aggregate(records),
        "common_subset": _aggregate([r for r in records if r["profile_id"] in common]),
    }


def overlap(records_a: Sequence[dict], records_b: Sequence[dict]) -> dict:
    b_by_profile = {r["profile_id"]: r for r in records_b}
    pairs = [
        (a["artists"], b_by_profile[a["profile_id"]]["artists"])
        for a in records_a
        if a["outcome"] == Outcome.ANSWERED
        and b_by_profile.get(a["profile_id"], {}).get("outcome") == Outcome.ANSWERED
    ]
    return {
        "profiles_compared": len(pairs),
        "mean_jaccard": metrics.mean(metrics.jaccard(x, y) for x, y in pairs),
        "mean_rbo_p0.9": metrics.mean(
            metrics.rank_biased_overlap(x, y) for x, y in pairs
        ),
    }


def run_evaluation(
    profiles: Sequence[Profile],
    providers: Sequence[EvalProvider],
    probe: CatalogProbe,
    *,
    max_artists: int = MAX_ARTISTS,
    clock: Callable[[], float] = time.perf_counter,
) -> tuple[dict, dict[str, dict[str, RecommendationResponse]]]:
    """Returns (results document, normalized responses by provider/profile)."""
    responses: dict[str, dict[str, RecommendationResponse]] = {}
    records: dict[str, list[dict]] = {}
    timing: dict[str, dict[str, list[float]]] = {}

    for provider in providers:
        responses[provider.name] = {}
        records[provider.name] = []
        times = timing.setdefault(provider.name, {"provider_ms": [], "catalog_ms": []})
        for profile in profiles:
            request = RecommendationRequest(profile.id, profile.interests, max_artists)
            start = clock()
            response = provider.recommend(request)
            times["provider_ms"].append((clock() - start) * 1000)
            responses[provider.name][profile.id] = response

            catalog = []
            for artist in response.artists:
                start = clock()
                catalog.append(probe.probe(artist.name))
                # Only live lookups have a meaningful latency.
                if probe.mode == "live":
                    times["catalog_ms"].append((clock() - start) * 1000)
            records[provider.name].append(
                score_response(profile, response, catalog, max_artists)
            )

    answered_by = [
        {r["profile_id"] for r in recs if r["outcome"] == Outcome.ANSWERED}
        for recs in records.values()
    ]
    common = set.intersection(*answered_by) if answered_by else set()
    names = [p.name for p in providers]

    document = {
        "schema_version": SCHEMA_VERSION,
        "config": {
            "providers": names,
            "catalog_mode": probe.mode,
            "max_artists": max_artists,
            "profiles": len(profiles),
            "common_subset_profiles": sorted(common),
        },
        "providers": {n: summarize_provider(records[n], common) for n in names},
        "overlap": {
            f"{a} vs {b}": overlap(records[a], records[b])
            for a, b in combinations(names, 2)
        },
        "records": [r for n in names for r in records[n]],
        "not_measured": NOT_MEASURED,
        "timing": {
            name: {
                "note": "wall-clock, environment-dependent; excluded from "
                "reproducibility guarantees",
                **{
                    f"{kind}_p{q}": metrics.percentile(values, q)
                    for kind, values in series.items()
                    for q in (50, 95)
                },
            }
            for name, series in timing.items()
        },
    }
    return document, responses
