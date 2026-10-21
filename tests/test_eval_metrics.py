import math

import pytest

from crosssignal.evaluation import metrics
from crosssignal.evaluation.catalog_probe import ArtistAvailability, Availability
from crosssignal.evaluation.schemas import RecommendedArtist


def artist(name: str, *cited: str) -> RecommendedArtist:
    return RecommendedArtist(name, 1, cited)


def avail(status: Availability, *genres: str) -> ArtistAvailability:
    return ArtistAvailability(
        "x", status, 3 if status is Availability.FOUND else 0, genres
    )


def test_duplicate_rate_uses_normalized_names():
    assert metrics.duplicate_rate(["M83", "m83 ", "Tycho", "Tycho"]) == 0.5
    assert metrics.duplicate_rate([]) is None


def test_grounding_separates_grounded_uncited_and_invalid():
    result = metrics.grounding(
        [
            artist("A", "Drive"),
            artist("B", "drive", "Made Up"),  # one invalid citation
            artist("C"),  # no reason given
            artist("D", "Blade Runner 2049"),
        ],
        ["Drive", "Blade Runner 2049"],
    )
    assert result == {
        "grounded_rate": 0.5,
        "uncited_rate": 0.25,
        "invalid_citations": 1,
    }


def test_grounding_of_empty_list_is_not_applicable():
    assert metrics.grounding([], ["Drive"])["grounded_rate"] is None


def test_interest_coverage_counts_distinct_inputs():
    artists = [artist("A", "Drive"), artist("B", "Drive")]
    assert metrics.interest_coverage(artists, ["Drive", "Journey"]) == 0.5
    assert metrics.interest_coverage(artists, []) is None


def test_availability_excludes_errors_and_unmeasured_from_rate():
    result = metrics.availability(
        [
            avail(Availability.FOUND),
            avail(Availability.NOT_FOUND),
            avail(Availability.ERROR),
            avail(Availability.UNMEASURED),
        ]
    )
    assert result == {
        "available_rate": 0.5,
        "catalog_found": 1,
        "catalog_answered": 2,
        "catalog_errors": 1,
        "catalog_unmeasured": 1,
    }


def test_availability_all_unmeasured_is_not_zero():
    assert (
        metrics.availability([avail(Availability.UNMEASURED)])["available_rate"] is None
    )


def test_normalized_entropy_bounds():
    assert metrics.normalized_entropy([]) is None
    assert metrics.normalized_entropy(["a"]) == 0.0
    assert metrics.normalized_entropy(["a", "a", "a"]) == 0.0
    assert metrics.normalized_entropy(["a", "b", "c"]) == pytest.approx(1.0)
    assert 0 < metrics.normalized_entropy(["a", "a", "b"]) < 1


def test_genre_diversity_uses_primary_genre_of_found_artists_only():
    result = metrics.genre_diversity(
        [
            avail(Availability.FOUND, "Electronic", "Pop"),
            avail(Availability.FOUND, "Electronic"),
            avail(Availability.NOT_FOUND),
        ]
    )
    assert result == {"genre_entropy": 0.0, "distinct_genre_ratio": 0.5}


def test_jaccard():
    assert metrics.jaccard(["A", "B"], ["b", "C"]) == pytest.approx(1 / 3)
    assert metrics.jaccard([], []) is None


def test_rbo_identical_disjoint_and_top_weighted():
    assert metrics.rank_biased_overlap(
        ["a", "b", "c"], ["a", "b", "c"]
    ) == pytest.approx(1)
    assert metrics.rank_biased_overlap(["a", "b"], ["c", "d"]) == 0
    top = metrics.rank_biased_overlap(["a", "b", "c", "d"], ["a", "x", "y", "z"])
    bottom = metrics.rank_biased_overlap(["a", "b", "c", "d"], ["x", "y", "z", "d"])
    assert top > bottom
    assert metrics.rank_biased_overlap([], []) is None
    with pytest.raises(ValueError):
        metrics.rank_biased_overlap(["a"], ["a"], p=1)


def test_cross_profile_diversity():
    result = metrics.cross_profile_diversity([["A", "B"], ["A", "C"], []])
    assert result["distinct_artist_ratio"] == 0.75
    assert result["mean_pairwise_jaccard"] == pytest.approx(1 / 3)


def test_percentile_interpolates():
    assert metrics.percentile([], 50) is None
    assert metrics.percentile([10.0], 95) == 10.0
    assert metrics.percentile([1.0, 2.0, 3.0, 4.0], 50) == 2.5


def test_wilson_interval_known_value():
    low, high = metrics.wilson_interval(5, 10)
    assert low == pytest.approx(0.2366, abs=1e-3)
    assert high == pytest.approx(0.7634, abs=1e-3)
    assert metrics.wilson_interval(0, 0) is None
    assert metrics.wilson_interval(10, 10)[1] == 1.0
    assert not math.isnan(metrics.wilson_interval(0, 3)[0])
