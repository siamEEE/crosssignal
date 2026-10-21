"""Blinded pairwise preference collection and scoring.

People see two unlabeled recommendation lists for the same profile and
pick the one that better fits it (or "tie"). Left/right order is seeded
per task, and the provider key is written to a separate file so judges
never see provider names.

The result is a *preference rate among these judges and profiles*. It is
not an accuracy score: there is no ground-truth "correct" artist list
for a taste profile, and a small panel of judges is not the population.
"""

import hashlib
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from crosssignal.evaluation.metrics import wilson_interval
from crosssignal.evaluation.schemas import (
    Profile,
    RecommendationResponse,
    ResponseStatus,
    SchemaError,
)

QUESTION = (
    "Which list better matches the music this person would enjoy, given "
    "their interests? Judge fit and the stated reasons. Choose 'tie' if "
    "neither is clearly better."
)
CHOICES = ("left", "right", "tie")


@dataclass(frozen=True)
class PairKey:
    task_id: str
    profile_id: str
    left: str
    right: str


def _left_first(seed: str, task_id: str) -> bool:
    return hashlib.sha256(f"{seed}:{task_id}".encode()).digest()[0] % 2 == 0


def _present(response: RecommendationResponse) -> list[dict]:
    return [
        {"artist": a.name, "because": list(a.cited_interests)} for a in response.artists
    ]


def build_pairwise_tasks(
    profiles: Sequence[Profile],
    responses: Mapping[str, Mapping[str, RecommendationResponse]],
    provider_a: str,
    provider_b: str,
    seed: str = "crosssignal",
) -> tuple[list[dict], list[PairKey]]:
    """Tasks for profiles where both providers returned artists.

    `responses[provider][profile_id]`. Returns (tasks for judges, key).
    """
    tasks, key = [], []
    for profile in profiles:
        a = responses[provider_a].get(profile.id)
        b = responses[provider_b].get(profile.id)
        if not all(r and r.status is ResponseStatus.OK and r.artists for r in (a, b)):
            continue
        task_id = f"{profile.id}:{provider_a}-vs-{provider_b}"
        task_id = hashlib.sha256(f"{seed}:{task_id}".encode()).hexdigest()[:12]
        left, right = (a, b) if _left_first(seed, task_id) else (b, a)
        tasks.append(
            {
                "task_id": task_id,
                "profile": profile.description,
                "interests": [i.name for i in profile.interests],
                "question": QUESTION,
                "left": _present(left),
                "right": _present(right),
            }
        )
        key.append(PairKey(task_id, profile.id, left.provider, right.provider))
    return tasks, key


def score_preferences(
    judgments: Sequence[Mapping[str, str]], key: Sequence[PairKey]
) -> dict:
    """Aggregate judgments {task_id, judge_id, choice} per provider.

    Win rate excludes ties; ties are reported. The interval is a 95%
    Wilson interval over judgments, which treats judgments as
    independent, an optimistic assumption when one judge rates many tasks.
    """
    by_task = {k.task_id: k for k in key}
    wins: Counter[str] = Counter()
    ties = 0
    judges: set[str] = set()
    seen: set[tuple[str, str]] = set()
    for judgment in judgments:
        task_id, judge, choice = (
            judgment.get("task_id"),
            judgment.get("judge_id"),
            judgment.get("choice"),
        )
        if task_id not in by_task:
            raise SchemaError(f"unknown task_id: {task_id!r}")
        if choice not in CHOICES:
            raise SchemaError(f"choice must be one of {CHOICES}: {choice!r}")
        if not isinstance(judge, str) or not judge:
            raise SchemaError("judge_id is required")
        if (task_id, judge) in seen:
            raise SchemaError(f"duplicate judgment: {task_id} by {judge}")
        seen.add((task_id, judge))
        judges.add(judge)
        if choice == "tie":
            ties += 1
        else:
            pair = by_task[task_id]
            wins[pair.left if choice == "left" else pair.right] += 1

    providers = sorted({p for k in key for p in (k.left, k.right)})
    decided = sum(wins.values())
    return {
        "kind": "pairwise preference (not accuracy)",
        "judgments": len(seen),
        "judges": len(judges),
        "ties": ties,
        "providers": {
            name: {
                "wins": wins[name],
                "win_rate_excluding_ties": wins[name] / decided if decided else None,
                "wilson_95": wilson_interval(wins[name], decided),
            }
            for name in providers
        },
    }
