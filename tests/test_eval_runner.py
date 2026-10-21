import itertools
import json
from pathlib import Path

import pytest

from crosssignal.evaluation.__main__ import main
from crosssignal.evaluation.catalog_probe import (
    ArtistAvailability,
    Availability,
    NullProbe,
)
from crosssignal.evaluation.providers import CuratedAdapter, RandomBaseline
from crosssignal.evaluation.report import render_summary
from crosssignal.evaluation.runner import NOT_MEASURED, Outcome, run_evaluation
from crosssignal.evaluation.schemas import (
    RecommendationResponse,
    ResponseStatus,
    load_profiles,
)

PROFILES = load_profiles(
    Path(__file__).resolve().parent.parent / "eval" / "profiles.json"
)


class FakeProbe:
    """Every artist found with genre by first letter; 'Kevin Shields' missing."""

    mode = "fake"

    def probe(self, artist: str) -> ArtistAvailability:
        if artist == "Kevin Shields":
            return ArtistAvailability(artist, Availability.NOT_FOUND)
        if artist == "Tycho":
            return ArtistAvailability(artist, Availability.ERROR)
        return ArtistAvailability(artist, Availability.FOUND, 3, (artist[0],))


class Broken:
    name = "broken"

    def recommend(self, request):
        return RecommendationResponse(
            self.name, request.profile_id, ResponseStatus.ERROR, error="quota"
        )


def ticking_clock():
    counter = itertools.count()
    return lambda: next(counter) / 1000  # 1 ms per call


def evaluate(providers=None, probe=None):
    document, _ = run_evaluation(
        PROFILES,
        providers or [CuratedAdapter(), RandomBaseline()],
        probe or FakeProbe(),
        clock=ticking_clock(),
    )
    return document


def records(document, provider):
    return {
        r["profile_id"]: r for r in document["records"] if r["provider"] == provider
    }


def test_outcomes_classify_failure_cases():
    curated = records(evaluate(), "curated")
    assert curated["empty"]["outcome"] == Outcome.CORRECT_REJECTION
    assert curated["over-limit"]["outcome"] == Outcome.CORRECT_REJECTION
    assert curated["prestige-tv"]["outcome"] == Outcome.ABSTAINED
    assert curated["gothic-reader"]["outcome"] == Outcome.ANSWERED
    assert curated["gothic-reader"]["unsupported_interests"] == [
        "The Secret History", "Wuthering Heights",
    ]  # fmt: skip


def test_curated_is_grounded_and_covers_supported_inputs():
    curated = records(evaluate(), "curated")
    neon = curated["neon-noir"]
    assert neon["grounded_rate"] == 1.0
    assert neon["invalid_citations"] == 0
    assert neon["interest_coverage"] == 1.0
    assert neon["within_limit"] and neon["duplicate_rate"] == 0
    # Partially supported: unsupported books lower coverage, honestly.
    assert curated["gothic-reader"]["interest_coverage"] == 1 / 3


def test_availability_counts_not_found_and_errors_separately():
    curated = records(evaluate(), "curated")
    lost = curated["five-worlds"]  # includes The Jesus and Mary Chain, not Shields
    assert lost["catalog_errors"] == 0
    rainy = curated["neon-noir"]  # includes Tycho -> fake error
    assert rainy["catalog_errors"] == 1
    assert rainy["available_rate"] == 1.0  # errors excluded from the rate


def test_random_baseline_games_grounding_and_coverage():
    providers = evaluate()["providers"]
    random_summary = providers["random-baseline"]["all_answered"]
    # Citing real inputs at random scores perfectly on referential metrics.
    # This is why they are necessary checks, never evidence of quality.
    assert random_summary["mean_grounded_rate"] == 1.0
    assert random_summary["mean_interest_coverage"] >= 0.9
    # Coverage-sensitive signals still separate it: it answers interests
    # the curated provider honestly abstains on.
    curated = providers["curated"]["outcomes"]
    assert providers["random-baseline"]["outcomes"]["answered"] > curated["answered"]


def test_errors_are_counted_and_excluded_from_quality():
    document = evaluate([CuratedAdapter(), Broken()])
    broken = document["providers"]["broken"]
    assert broken["provider_error_rate"] == 1.0
    assert broken["all_answered"]["answered"] == 0
    assert broken["all_answered"]["mean_grounded_rate"] is None
    assert document["config"]["common_subset_profiles"] == []
    assert document["overlap"]["curated vs broken"]["profiles_compared"] == 0


def test_common_subset_and_overlap():
    document = evaluate()
    common = document["config"]["common_subset_profiles"]
    assert "neon-noir" in common and "prestige-tv" not in common
    pair = document["overlap"]["curated vs random-baseline"]
    assert pair["profiles_compared"] == len(common)
    assert 0 <= pair["mean_jaccard"] < 1


def test_results_are_deterministic_apart_from_timing():
    first, second = evaluate(), evaluate()
    first.pop("timing"), second.pop("timing")
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_timing_uses_injected_clock():
    timing = evaluate([CuratedAdapter()])["timing"]["curated"]
    assert timing["provider_ms_p50"] == pytest.approx(1.0)
    assert timing["catalog_ms_p50"] is None  # not a live catalog


def test_report_states_limits_and_unmeasured_items():
    text = render_summary(evaluate())
    assert "No metric here measures recommendation accuracy" in text
    for name in NOT_MEASURED:
        assert name in text
    assert "prestige-tv" in text  # failure cases are listed
    assert "| curated |" in text


def test_null_probe_reports_availability_as_not_applicable():
    document = evaluate([CuratedAdapter()], NullProbe())
    summary = document["providers"]["curated"]["all_answered"]
    assert summary["pooled_available_rate"] is None
    assert summary["catalog_unmeasured"] > 0


def test_cli_run_and_pairs_write_outputs(tmp_path):
    out = tmp_path / "out"
    main(["run", "--catalog", "none", "--out", str(out)])
    assert {p.name for p in out.iterdir()} == {
        "results.json",
        "responses.json",
        "summary.md",
    }

    pairs = tmp_path / "pairs"
    main(["pairs", "--results", str(out), "--a", "curated", "--b", "random-baseline",
          "--out", str(pairs)])  # fmt: skip
    tasks = json.loads((pairs / "tasks.json").read_text(encoding="utf-8"))
    key = json.loads((pairs / "key.json").read_text(encoding="utf-8"))
    assert tasks and len(tasks) == len(key)
    assert "curated" not in json.dumps(tasks)
