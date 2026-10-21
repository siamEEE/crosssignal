import json

import pytest

from crosssignal.evaluation.human import build_pairwise_tasks, score_preferences
from crosssignal.evaluation.schemas import (
    Expectation,
    Profile,
    ProfileInterest,
    RecommendationResponse,
    RecommendedArtist,
    ResponseStatus,
    SchemaError,
)


def profile(pid: str) -> Profile:
    return Profile(pid, f"desc {pid}", (ProfileInterest("Drive", "film"),),
                   Expectation.RECOMMEND)  # fmt: skip


def ok(provider: str, pid: str, *artists: str) -> RecommendationResponse:
    return RecommendationResponse(
        provider,
        pid,
        ResponseStatus.OK,
        tuple(RecommendedArtist(a, n, ("Drive",)) for n, a in enumerate(artists, 1)),
    )


PROFILES = [profile(f"p{n}") for n in range(6)]
RESPONSES = {
    "alpha": {p.id: ok("alpha", p.id, "A1", "A2") for p in PROFILES},
    "beta": {
        **{p.id: ok("beta", p.id, "B1") for p in PROFILES[:-1]},
        "p5": RecommendationResponse("beta", "p5", ResponseStatus.UNSUPPORTED),
    },
}


def test_tasks_are_blinded_deterministic_and_skip_unanswered():
    tasks, key = build_pairwise_tasks(PROFILES, RESPONSES, "alpha", "beta")
    again, _ = build_pairwise_tasks(PROFILES, RESPONSES, "alpha", "beta")
    assert tasks == again
    assert len(tasks) == 5  # p5 has no beta answer
    text = json.dumps(tasks)
    assert "alpha" not in text and "beta" not in text
    # Order is randomised, so both sides appear on the left at least once.
    assert {k.left for k in key} == {"alpha", "beta"}


def test_preferences_count_wins_ties_and_judges():
    _, key = build_pairwise_tasks(PROFILES, RESPONSES, "alpha", "beta")
    judgments = []
    for k in key:
        side = "left" if k.left == "alpha" else "right"
        judgments.append({"task_id": k.task_id, "judge_id": "j1", "choice": side})
    judgments.append({"task_id": key[0].task_id, "judge_id": "j2", "choice": "tie"})

    result = score_preferences(judgments, key)
    assert result["kind"] == "pairwise preference (not accuracy)"
    assert (result["judgments"], result["judges"], result["ties"]) == (6, 2, 1)
    alpha = result["providers"]["alpha"]
    assert alpha["wins"] == 5
    assert alpha["win_rate_excluding_ties"] == 1.0
    assert alpha["wilson_95"][1] == 1.0 and alpha["wilson_95"][0] < 1.0
    assert result["providers"]["beta"]["wins"] == 0


def test_no_judgments_gives_no_rate():
    _, key = build_pairwise_tasks(PROFILES, RESPONSES, "alpha", "beta")
    result = score_preferences([], key)
    assert result["providers"]["alpha"]["win_rate_excluding_ties"] is None


@pytest.mark.parametrize(
    "judgment",
    [
        {"task_id": "nope", "judge_id": "j", "choice": "left"},
        {"task_id": "KEY", "judge_id": "j", "choice": "both"},
        {"task_id": "KEY", "judge_id": "", "choice": "left"},
    ],
)
def test_invalid_judgments_raise(judgment):
    _, key = build_pairwise_tasks(PROFILES, RESPONSES, "alpha", "beta")
    if judgment["task_id"] == "KEY":
        judgment = {**judgment, "task_id": key[0].task_id}
    with pytest.raises(SchemaError):
        score_preferences([judgment], key)


def test_duplicate_judgment_raises():
    _, key = build_pairwise_tasks(PROFILES, RESPONSES, "alpha", "beta")
    j = {"task_id": key[0].task_id, "judge_id": "j", "choice": "left"}
    with pytest.raises(SchemaError, match="duplicate"):
        score_preferences([j, j], key)
