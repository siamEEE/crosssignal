# CrossSignal recommendation evaluation

Providers: curated, random-baseline · profiles: 20 · max artists: 8 · catalog: `snapshot`

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


## Request handling

| provider | profiles | answered | abstained | correct_rejection | missed_rejection | wrong_rejection | error |
|---|---|---|---|---|---|---|---|
| curated | 20 | 15 | 3 | 2 | 0 | 0 | 0 |
| random-baseline | 20 | 18 | 0 | 2 | 0 | 0 | 0 |

## Quality signals (all answered profiles)

| provider | n | grounded | uncited | bad cites | coverage | dupes | ≤ limit | available | cat err/unmeasured | genre H | distinct artists | cross-profile J |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| curated | 15 | 100% | 0% | 0 | 80% | 0% | 100% | 100% | 0/0 | 0.74 | 43% | 0.07 |
| random-baseline | 18 | 100% | 0% | 0 | 100% | 0% | 100% | 100% | 0/0 | 0.65 | 16% | 0.22 |

## Quality signals (profiles every provider answered)

15 profiles. Use this table for side-by-side comparison; it removes coverage differences.

| provider | n | grounded | uncited | bad cites | coverage | dupes | ≤ limit | available | cat err/unmeasured | genre H | distinct artists | cross-profile J |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| curated | 15 | 100% | 0% | 0 | 80% | 0% | 100% | 100% | 0/0 | 0.74 | 43% | 0.07 |
| random-baseline | 15 | 100% | 0% | 0 | 100% | 0% | 100% | 100% | 0/0 | 0.64 | 19% | 0.21 |

## Overlap between providers

| pair | profiles | mean Jaccard | mean RBO (p=0.9) |
|---|---|---|---|
| curated vs random-baseline | 15 | 0.13 | 0.09 |

## Failure cases and issues

| provider | profile | issue |
|---|---|---|
| curated | gothic-reader | unsupported: The Secret History, Wuthering Heights |
| curated | food-and-travel | abstained; unsupported: Neapolitan pizza, Kyoto temples, Specialty pour-over coffee |
| curated | global-screens | unsupported: Bollywood musicals, K-dramas |
| curated | prestige-tv | abstained; unsupported: Twin Peaks, Severance |
| curated | pit-lane-style | abstained; unsupported: Formula 1, Streetwear |
| curated | empty | correct_rejection; no interests |
| curated | over-limit | correct_rejection; more than 5 interests |
| curated | concrete-and-colour | unsupported: Brutalist architecture, Mark Rothko paintings |
| curated | trail-and-meadow | unsupported: Long-distance hiking |
| curated | cafe-amelie | unsupported: Amélie |
| random-baseline | empty | correct_rejection; no interests |
| random-baseline | over-limit | correct_rejection; more than 5 interests |

## Not measured by this run

- **musical_fit**: Whether artists suit the profile. Needs human judgment (pairwise preference via `evaluation pairs`) - a preference, not accuracy.
- **explanation_quality**: Whether the stated reason is convincing. Needs human judgment; grounded_rate only checks that reasons cite real inputs.
- **qloo_affinity**: Qloo affinity scores and their calibration. Needs real Qloo responses; no scores are produced or estimated here.
- **qloo_entity_resolution**: How often Qloo resolves free-text interests to entities. Needs Qloo search API access.
- **novelty_vs_user_history**: Whether artists are new to the user. Needs listening history, which CrossSignal does not collect.

## Timing (environment-dependent)

| provider | provider p50 ms | provider p95 ms | catalog p50 ms | catalog p95 ms |
|---|---|---|---|---|
| curated | 0.01 | 0.03 | n/a | n/a |
| random-baseline | 0.02 | 0.03 | n/a | n/a |
