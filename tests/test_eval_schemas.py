import json
from pathlib import Path

import pytest

from crosssignal.discovery import MAX_INTERESTS
from crosssignal.evaluation.schemas import (
    Expectation,
    ResponseStatus,
    SchemaError,
    load_profiles,
    parse_profile,
    parse_response,
)
from crosssignal.recommendations import CuratedProvider

PROFILES = Path(__file__).resolve().parent.parent / "eval" / "profiles.json"


def response(**overrides) -> dict:
    raw = {
        "provider": "llm-x",
        "profile_id": "p1",
        "status": "ok",
        "artists": [
            {"name": "M83", "rank": 1, "cited_interests": ["Interstellar"]},
            {"name": "Tycho", "rank": 2, "cited_interests": []},
        ],
    }
    raw.update(overrides)
    return raw


# --- the shipped dataset -------------------------------------------------


def test_dataset_has_about_twenty_valid_profiles():
    profiles = load_profiles(PROFILES)
    assert 18 <= len(profiles) <= 22


def test_dataset_curated_ids_exist():
    known = {i.id for i in CuratedProvider().interests()}
    for profile in load_profiles(PROFILES):
        for interest in profile.interests:
            assert interest.curated_id in (None, *known), (profile.id, interest)


def test_dataset_expectations_match_input_contract():
    for profile in load_profiles(PROFILES):
        valid = 1 <= len(profile.interests) <= MAX_INTERESTS
        assert (profile.expect is Expectation.RECOMMEND) == valid, profile.id


def test_dataset_covers_failure_cases_and_domains():
    profiles = load_profiles(PROFILES)
    tags = {t for p in profiles for t in p.tags}
    assert {"unsupported", "partially-supported", "invalid-input",
            "duplicate-input", "ambiguous-name"} <= tags  # fmt: skip
    domains = {i.domain for p in profiles for i in p.interests}
    assert len(domains) >= 8


# --- profile validation --------------------------------------------------


def test_profile_rejects_bad_expectation_and_missing_fields():
    good = {"id": "x", "description": "d", "interests": [], "expect": "reject"}
    assert parse_profile(good).expect is Expectation.REJECT
    with pytest.raises(SchemaError):
        parse_profile({**good, "expect": "maybe"})
    with pytest.raises(SchemaError):
        parse_profile({**good, "interests": [{"name": "", "domain": "film"}]})
    with pytest.raises(SchemaError):
        parse_profile({**good, "description": None})


def test_duplicate_profile_ids_rejected(tmp_path):
    item = {"id": "x", "description": "d", "interests": [], "expect": "reject"}
    path = tmp_path / "p.json"
    path.write_text(json.dumps({"profiles": [item, item]}), encoding="utf-8")
    with pytest.raises(SchemaError, match="unique"):
        load_profiles(path)


# --- response validation -------------------------------------------------


def test_valid_response_parses():
    parsed = parse_response(response())
    assert parsed.status is ResponseStatus.OK
    assert [a.name for a in parsed.artists] == ["M83", "Tycho"]
    assert parsed.artists[0].score is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"status": "great"},
        {"artists": [{"name": "M83", "rank": 2}]},  # ranks must start at 1
        {"artists": [{"name": "", "rank": 1}]},
        {"artists": [{"name": "M83", "rank": 1, "cited_interests": "Drive"}]},
        {"artists": [{"name": "M83", "rank": 1, "score": 0.9}]},  # no score_kind
        {"artists": [{"name": "M83", "rank": 1, "score": True, "score_kind": "x"}]},
        {"artists": "M83"},
        {"provider": ""},
    ],
)
def test_invalid_responses_raise(overrides):
    with pytest.raises(SchemaError):
        parse_response(response(**overrides))


def test_score_requires_and_keeps_its_kind():
    raw = response(
        artists=[
            {"name": "M83", "rank": 1, "score": 0.8, "score_kind": "qloo_affinity"}
        ]
    )
    [parsed] = parse_response(raw).artists
    assert (parsed.score, parsed.score_kind) == (0.8, "qloo_affinity")
