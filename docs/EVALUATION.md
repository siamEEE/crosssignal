# Recommendation evaluation

How CrossSignal checks its interest-to-artist recommendations, what those
checks can and cannot show, and how the framework grows once Qloo access
arrives.

```bash
uv run python -m crosssignal.evaluation run                  # offline, snapshot catalog
uv run python -m crosssignal.evaluation run --catalog live   # query iTunes
uv run python -m crosssignal.evaluation run --catalog live --record-snapshot
uv run python -m crosssignal.evaluation run --replay eval/recordings/llm.json
uv run python -m crosssignal.evaluation pairs --a curated --b random-baseline
uv run python -m crosssignal.evaluation preferences --judgments judgments.json
```

Outputs go to `eval/results/latest/`: `results.json` (machine-readable),
`responses.json` (every normalized provider response) and `summary.md`.

## What this framework is not

There is no ground-truth "correct" artist list for a taste profile, so
**nothing here measures recommendation accuracy**. The curated provider is
hand-written demo data. The random baseline is a floor. Agreement with
either proves nothing about quality. Every report says so, and lists the
questions it cannot answer (`NOT_MEASURED` in `runner.py`).

## Design

```
eval/profiles.json ──► RecommendationRequest ──► EvalProvider ──► RecommendationResponse
                                                  │  curated          (normalized schema)
                                                  │  random-baseline         │
                                                  │  replay (LLM/Qloo)       ▼
                                                                       CatalogProbe
                                                                  (live | snapshot | none)
                                                                             │
                                               metrics.py (pure) ◄───────────┘
                                                     │
                                       results.json + summary.md
```

| Module | Responsibility |
|---|---|
| `evaluation/schemas.py` | Profile, request and response types; strict validation of recorded data |
| `evaluation/providers.py` | `EvalProvider` protocol; curated, random-baseline and replay adapters |
| `evaluation/catalog_probe.py` | Track availability via live iTunes, a recorded snapshot, or not at all |
| `evaluation/metrics.py` | Pure metric functions, no I/O |
| `evaluation/runner.py` | Runs providers over profiles; classifies outcomes; aggregates |
| `evaluation/report.py` | Markdown summary |
| `evaluation/human.py` | Blinded pairwise tasks and preference scoring |

No new dependencies: standard library only, plus the existing catalog code.

### Normalized response schema

```json
{
  "provider": "llm-gpt-x-2026-10",
  "profile_id": "neon-noir",
  "status": "ok | rejected | unsupported | error",
  "artists": [
    {"name": "Massive Attack", "rank": 1,
     "cited_interests": ["Blade Runner 2049"],
     "score": null, "score_kind": null}
  ],
  "unsupported_interests": [],
  "error": null
}
```

- `rank` must run 1..n. `cited_interests` are the input interest names
  the provider gives as its reason for the artist.
- `score` is optional and may be set **only** when the provider truly
  returns one, and `score_kind` must then name it (e.g. `qloo_affinity`).
  Adapters never invent scores. Scores are carried through but not
  compared across providers, because scores from different systems are on
  different scales.
- A recording file wraps responses:
  `{"provider": ..., "source_note": ..., "responses": [...]}`. A profile
  with no recording becomes an `error`, so gaps are visible.

## Dataset

`eval/profiles.json` has 20 synthetic profiles (not real users) using
interests from 12 domains: film, game, aesthetic, book, tv, food, place,
sport, fashion, architecture, art, activity. They are tagged so results
can be read by case:

| Tag | Purpose |
|---|---|
| `fully-supported` | Every interest exists in the curated demo set |
| `partially-supported` | Some interests unknown to curated data (books, art, ...) |
| `unsupported` | No interest known to curated data; honest abstention expected |
| `invalid-input` | Empty or over the 5-interest limit; must be rejected |
| `duplicate-input` | Same interest twice |
| `ambiguous-name` | "Journey" the game, not the band; tests need human review |
| `paraphrased-names` | User wording differs from catalog names |
| `non-western`, `unicode`, `similar-interests`, `shared-artist`, `max-interests` | Coverage of harder or edge cases |

`curated_id` links an interest to the demo provider. It says nothing about
which artists are right.

## Metrics

### Automated (computed every run)

| Metric | Definition | What it does **not** show |
|---|---|---|
| Outcome classes | answered / abstained / correct_rejection / wrong_rejection / missed_rejection / error, against the profile's `expect` | Quality of answered lists |
| `provider_error_rate` | errors / profiles | Cause of the error |
| `grounded_rate` | artists whose reasons all cite real inputs (and at least one) | Whether the reason is sensible. The random baseline scores ~100% |
| `uncited_rate`, `invalid_citations` | artists with no reason; cited names that are not inputs (hallucinated) | |
| `interest_coverage` | share of input interests cited by at least one artist | Whether those artists suit the interest |
| `duplicate_rate`, `within_limit` | wasted repeated slots; list length ≤ 8 | |
| `available_rate` | artists with ≥1 exact-credit iTunes track / artists the catalog answered for | Popularity or streaming availability elsewhere |
| `catalog_errors`, `catalog_unmeasured` | lookups that failed / were not probed; **excluded** from the rate so outages do not look like missing music | |
| `genre_entropy` | normalized Shannon entropy of iTunes `primaryGenreName` across found artists | Fine-grained style diversity (genres are coarse) |
| `distinct_artist_ratio`, `mean_pairwise_jaccard` | across profiles: distinct artists / slots; average overlap between two profiles' lists | Whether variety is *appropriate* |
| Provider overlap | per profile, Jaccard and normalized truncated rank-biased overlap (p = 0.9) between two providers | Which provider is better; overlap is only agreement |
| Latency p50/p95 | provider call wall-clock; catalog latency only in live mode | Production latency (environment-dependent) |

### Fair comparison rules

1. Same profiles, same `max_artists` (8), same catalog snapshot.
2. The same input contract (1–5 interests) is applied to every live
   adapter. Recorded providers are scored on what they actually did.
3. Abstaining on unknown interests is a separate outcome, not a failure.
   A provider that answers everything is not rewarded for it: the
   **common-subset** table restricts quality metrics to profiles every
   provider answered.
4. Coverage and grounding are reported per profile, so a provider that
   answers more profiles does not hide weak answers in an average.

### Requires human judgment

`musical_fit` and `explanation_quality` cannot be automated honestly.
`evaluation pairs` turns two providers' saved responses into blinded
side-by-side tasks: left/right order is seeded per task, provider names
are kept in a separate `key.json`, and each task asks which list better
suits the person, with "tie" allowed. `evaluation preferences` reports
wins, ties, the win rate excluding ties, and a 95% Wilson interval.

This is a **preference rate among these judges on these profiles**, not
accuracy. The interval treats judgments as independent, which is
optimistic when one judge rates many tasks. With a handful of judges,
report the raw counts and treat the interval as rough. Suggested minimum:
3 judges × all common-subset profiles per provider pair.

### Requires real Qloo responses

- Qloo affinity scores and their calibration (score vs. human preference)
- Entity-resolution rate: how often Qloo maps free-text interests to entities
- Qloo latency and quota/error behaviour under real load

None of these are estimated or simulated here.

## Comparing an LLM-only provider

No paid LLM API is called by this repository (that needs approval). To
evaluate one, generate responses outside the runner, save them in the
recording format above, and pass `--replay path.json`. To keep it fair:

- Give the model only each profile's interest names, `max_artists = 8`,
  and the 1–5 interest rule; ask it to cite which input interests justify
  each artist, and to return `unsupported` rather than guess.
- Record model id, date, prompt and temperature in `source_note`.
- Expect LLMs to produce artists outside the snapshot; those show as
  `unmeasured` until a live run with `--record-snapshot` adds them.

## Expanding once Qloo credentials arrive

1. Implement `QlooProvider` (app protocol) and a `QlooAdapter`
   (`EvalProvider`) that maps Qloo entities to `RecommendedArtist`,
   cites the input entities Qloo was queried with, and copies the real
   affinity value into `score` with `score_kind = "qloo_affinity"`.
2. Record Qloo responses once to a replay file, so later runs are
   deterministic and do not spend quota.
3. Add `qloo_entity_resolution` as an automated metric (resolved
   interests / input interests), using the real search responses.
4. Run `--catalog live --record-snapshot` to probe Qloo's artists in
   iTunes and extend the snapshot.
5. Run pairwise human preference: Qloo vs curated, Qloo vs LLM-only.
6. Only then analyse affinity calibration against human preferences.

## Assumptions

- iTunes availability (US storefront, exact-credit match, top 3 songs)
  stands in for "a user could listen to this". It is not a popularity
  measure.
- `eval/catalog_snapshot.json` was recorded from the live iTunes API on
  2026-10-20 for the 23 curated artists (all found). Catalog contents
  change, so re-record before drawing new conclusions.
- Catalog failures during recording are not written to the snapshot;
  only real answers are.
- The random baseline samples from the curated artist pool so availability
  is comparable; it is a sanity floor, not a competitor.
