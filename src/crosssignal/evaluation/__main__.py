"""Command line entry point.

uv run python -m crosssignal.evaluation run --catalog snapshot
uv run python -m crosssignal.evaluation pairs --a curated --b random-baseline
uv run python -m crosssignal.evaluation preferences --judgments j.json
"""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from crosssignal.evaluation.catalog_probe import LiveProbe, NullProbe, SnapshotProbe
from crosssignal.evaluation.human import (
    PairKey,
    build_pairwise_tasks,
    score_preferences,
)
from crosssignal.evaluation.providers import (
    CuratedAdapter,
    RandomBaseline,
    ReplayProvider,
)
from crosssignal.evaluation.report import render_summary
from crosssignal.evaluation.runner import run_evaluation
from crosssignal.evaluation.schemas import load_profiles, parse_response

EVAL_DIR = Path("eval")
DEFAULT_PROFILES = EVAL_DIR / "profiles.json"
DEFAULT_SNAPSHOT = EVAL_DIR / "catalog_snapshot.json"
DEFAULT_OUT = EVAL_DIR / "results" / "latest"
BUILTIN = {"curated": CuratedAdapter, "random-baseline": RandomBaseline}


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2, ensure_ascii=False, sort_keys=False)
    path.write_text(text + "\n", encoding="utf-8")


def cmd_run(args: argparse.Namespace) -> None:
    profiles = load_profiles(args.profiles)
    providers = [BUILTIN[name]() for name in args.providers]
    providers += [ReplayProvider(path) for path in args.replay]

    if args.catalog == "live":
        probe = LiveProbe()
    elif args.catalog == "snapshot":
        probe = SnapshotProbe(args.snapshot)
    else:
        probe = NullProbe()

    document, responses = run_evaluation(profiles, providers, probe)
    write_json(args.out / "results.json", document)
    write_json(
        args.out / "responses.json",
        {name: [r.to_dict() for r in by_profile.values()]
         for name, by_profile in responses.items()},
    )  # fmt: skip
    (args.out / "summary.md").write_text(render_summary(document), encoding="utf-8")
    if args.record_snapshot:
        if not isinstance(probe, LiveProbe):
            raise SystemExit("--record-snapshot requires --catalog live")
        probe.save_snapshot(args.snapshot)
        print(f"Snapshot written to {args.snapshot}")
    print(f"Results written to {args.out}")


def cmd_pairs(args: argparse.Namespace) -> None:
    profiles = load_profiles(args.profiles)
    raw = json.loads((args.results / "responses.json").read_text(encoding="utf-8"))
    responses = {
        name: {r.profile_id: r for r in map(parse_response, items)}
        for name, items in raw.items()
    }
    for name in (args.a, args.b):
        if name not in responses:
            raise SystemExit(f"No responses for provider {name!r} in {args.results}")
    tasks, key = build_pairwise_tasks(profiles, responses, args.a, args.b, args.seed)
    write_json(args.out / "tasks.json", tasks)
    write_json(args.out / "key.json", [asdict(k) for k in key])
    print(f"{len(tasks)} blinded tasks in {args.out / 'tasks.json'}")
    print(f"Keep {args.out / 'key.json'} away from judges.")


def cmd_preferences(args: argparse.Namespace) -> None:
    key = [PairKey(**k) for k in json.loads(args.key.read_text(encoding="utf-8"))]
    judgments = json.loads(args.judgments.read_text(encoding="utf-8"))
    print(json.dumps(score_preferences(judgments, key), indent=2))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m crosssignal.evaluation")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="evaluate providers over the profile set")
    run.add_argument("--profiles", type=Path, default=DEFAULT_PROFILES)
    run.add_argument(
        "--providers", nargs="*", choices=sorted(BUILTIN), default=sorted(BUILTIN)
    )
    run.add_argument("--replay", type=Path, nargs="*", default=[],
                     help="recorded provider responses (LLM, Qloo) to include")  # fmt: skip
    run.add_argument(
        "--catalog", choices=["none", "snapshot", "live"], default="snapshot"
    )
    run.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    run.add_argument("--record-snapshot", action="store_true",
                     help="with --catalog live, save answers as the snapshot")  # fmt: skip
    run.add_argument("--out", type=Path, default=DEFAULT_OUT)
    run.set_defaults(func=cmd_run)

    pairs = sub.add_parser("pairs", help="build blinded pairwise judging tasks")
    pairs.add_argument("--profiles", type=Path, default=DEFAULT_PROFILES)
    pairs.add_argument("--results", type=Path, default=DEFAULT_OUT)
    pairs.add_argument("--a", required=True)
    pairs.add_argument("--b", required=True)
    pairs.add_argument("--seed", default="crosssignal")
    pairs.add_argument("--out", type=Path, default=EVAL_DIR / "results" / "pairs")
    pairs.set_defaults(func=cmd_pairs)

    prefs = sub.add_parser("preferences", help="score collected judgments")
    prefs.add_argument(
        "--key", type=Path, default=EVAL_DIR / "results" / "pairs" / "key.json"
    )
    prefs.add_argument("--judgments", type=Path, required=True)
    prefs.set_defaults(func=cmd_preferences)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
