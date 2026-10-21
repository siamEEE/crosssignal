"""Render a results document as a human-readable Markdown summary."""

from collections.abc import Mapping

CAVEATS = """\
## How to read this

- **No metric here measures recommendation accuracy.** Curated demo data
  and the random baseline are references, not ground truth.
- `grounded` checks that every stated reason cites a real input interest.
  The random baseline scores ~100% on it and on coverage, which is the
  point: referential grounding is necessary, not sufficient. Fit needs
  human judgment.
- `available` is measured only over artists the catalog answered for;
  catalog errors and unmeasured artists are counted separately.
- Genre entropy uses iTunes `primaryGenreName`, which is coarse.
- Timing is wall-clock and environment-dependent.
"""


def fmt(value: object) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.0%}"


def _table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "---|" * len(headers),
        *("| " + " | ".join(row) + " |" for row in rows),
    ]
    return "\n".join(lines)


def _outcomes_table(providers: Mapping[str, dict]) -> str:
    keys = ["answered", "abstained", "correct_rejection", "missed_rejection",
            "wrong_rejection", "error"]  # fmt: skip
    rows = [
        [name, str(p["profiles"]), *(str(p["outcomes"].get(k, 0)) for k in keys)]
        for name, p in providers.items()
    ]
    return _table(["provider", "profiles", *keys], rows)


def _quality_table(providers: Mapping[str, dict], subset: str) -> str:
    rows = []
    for name, p in providers.items():
        a = p[subset]
        rows.append(
            [
                name,
                str(a["answered"]),
                pct(a["mean_grounded_rate"]),
                pct(a["mean_uncited_rate"]),
                str(a["invalid_citations"]),
                pct(a["mean_interest_coverage"]),
                pct(a["mean_duplicate_rate"]),
                pct(a["within_limit_rate"]),
                pct(a["pooled_available_rate"]),
                f"{a['catalog_errors']}/{a['catalog_unmeasured']}",
                fmt(a["mean_genre_entropy"]),
                pct(a["distinct_artist_ratio"]),
                fmt(a["mean_pairwise_jaccard"]),
            ]
        )
    headers = ["provider", "n", "grounded", "uncited", "bad cites", "coverage",
               "dupes", "≤ limit", "available", "cat err/unmeasured",
               "genre H", "distinct artists", "cross-profile J"]  # fmt: skip
    return _table(headers, rows)


def _failures(records: list[dict]) -> str:
    rows = []
    for r in records:
        problems = []
        if r["outcome"] != "answered":
            problems.append(r["outcome"])
            if r["error"]:
                problems.append(r["error"])
        else:
            if r["invalid_citations"]:
                problems.append(f"{r['invalid_citations']} invalid citations")
            if not r["within_limit"]:
                problems.append("over artist limit")
            if r["duplicate_rate"]:
                problems.append("duplicate artists")
            if r["catalog_answered"] > r["catalog_found"]:
                missing = r["catalog_answered"] - r["catalog_found"]
                problems.append(f"{missing} artist(s) not in catalog")
            if r["catalog_errors"]:
                problems.append(f"{r['catalog_errors']} catalog error(s)")
        if r["unsupported_interests"]:
            problems.append("unsupported: " + ", ".join(r["unsupported_interests"]))
        if problems:
            rows.append([r["provider"], r["profile_id"], "; ".join(problems)])
    if not rows:
        return "None."
    return _table(["provider", "profile", "issue"], rows)


def render_summary(document: dict) -> str:
    config = document["config"]
    providers = document["providers"]
    parts = [
        "# CrossSignal recommendation evaluation",
        (
            f"Providers: {', '.join(config['providers'])} · profiles: "
            f"{config['profiles']} · max artists: {config['max_artists']} · "
            f"catalog: `{config['catalog_mode']}`"
        ),
        CAVEATS,
        "## Request handling",
        _outcomes_table(providers),
        "## Quality signals (all answered profiles)",
        _quality_table(providers, "all_answered"),
        "## Quality signals (profiles every provider answered)",
        (
            f"{len(config['common_subset_profiles'])} profiles. Use this table "
            "for side-by-side comparison; it removes coverage differences."
        ),
        _quality_table(providers, "common_subset"),
        "## Overlap between providers",
    ]
    if document["overlap"]:
        parts.append(
            _table(
                ["pair", "profiles", "mean Jaccard", "mean RBO (p=0.9)"],
                [
                    [
                        pair,
                        str(o["profiles_compared"]),
                        fmt(o["mean_jaccard"]),
                        fmt(o["mean_rbo_p0.9"]),
                    ]
                    for pair, o in document["overlap"].items()
                ],
            )
        )
    else:
        parts.append("Only one provider; no overlap to report.")
    parts += [
        "## Failure cases and issues",
        _failures(document["records"]),
        "## Not measured by this run",
        "\n".join(f"- **{k}**: {v}" for k, v in document["not_measured"].items()),
        "## Timing (environment-dependent)",
        _table(
            [
                "provider",
                "provider p50 ms",
                "provider p95 ms",
                "catalog p50 ms",
                "catalog p95 ms",
            ],
            [
                [
                    name,
                    fmt(t["provider_ms_p50"]),
                    fmt(t["provider_ms_p95"]),
                    fmt(t["catalog_ms_p50"]),
                    fmt(t["catalog_ms_p95"]),
                ]
                for name, t in document["timing"].items()
            ],
        ),
    ]
    return "\n\n".join(parts) + "\n"
