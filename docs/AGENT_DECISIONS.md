# Agent decision points (Culture Radio)

CrossSignal has **no agent framework and no LLM call**. Every step below
runs deterministically today. This document lists the points where an
optional Gemini agent could later take over, what it would be allowed
to decide, and the fallback that keeps working without it.

## Pipeline

```
text ──► interpret.py ──► mentions + music hints (no ids)
                              │
picker / search ──► culture.resolve ──► candidates ──► USER CONFIRMS ──► Signal
                                                                          │
genres / era / discovery / feedback ─────────────────────────► Preferences, Feedback
                                                                          │
engine.Engine.discover:
  1 validate      validate_signals, Preferences.__post_init__
  2 discover      Qloo /v2/insights per entity signal (+ tag signals, filters)
  3 pre-rank      Qloo-only evidence, decides lookup order
  4 validate      Apple catalog lookups (≤14, 3 in parallel)
  5 rank          ranking.genre_verdict / score / diversify / select_tracks
                                                                          │
api.py ──► JSON ──► React (presentation only)
```

## Decision points

| # | Decision | Deterministic default (today) | What an agent may do | Hard limits (enforced in code) |
|---|---|---|---|---|
| D1 | Split free text into mentions and music hints | `interpret.interpret_deterministic`: list splitting, filler stripping, genre/era/discovery keyword tables | Produce an `Interpretation` (phrases + category hints + vocab-only music hints) | `interpret.validate`: ≤8 mentions, 1-120 chars, known categories, known genre/era/discovery ids. No ids, no free-form fields |
| D2 | Which Qloo candidate a phrase means | `culture.resolve`: exactly one exact normalized name ⇒ `exact`; several ⇒ `ambiguous` (popularity order); none ⇒ `suggestions` | Re-order candidates or pre-select a likely one | The user still confirms every addition. Only ids returned by Qloo search can become signals |
| D3 | Map an aesthetic phrase to tags | `/v2/tags` search restricted to ambience, style, media-genre and subgenre tag types | Choose among returned tags | Tag-only profiles are rejected (`engine.validate_signals`); audience/identity tag types are never offered |
| D4 | Natural-language taste ⇒ genre preferences | Keyword match against `genres.GENRES` labels | Suggest preferred/avoided genre ids | Ids must exist in `genres.BY_ID`; applied only when the user taps "Apply" |
| D5 | Relaxation when too few artists survive | One unfiltered Qloo pass when the genre filter starves the pool (`genre_fallback`); otherwise return `insufficient`/`empty` with counts | Propose a relaxation (open-to instead of preferred, any era, balanced, next page) to the user | Never fills the page with unverified or excluded artists; the user runs the relaxed query |
| D6 | Wording of explanations | `frontend/src/lib/explain.ts` templates over API fields | Rephrase for tone | May only use returned fields (rank, affinity, tags, catalog genre, era counts); must not call affinity a probability; no inferences about the person |
| D7 | Remix strategy | 👍 adds the artist as an extra Qloo signal; 👎 adds `filter.exclude.entities`; "Dig deeper" requests the next Qloo `page` | Choose which feedback to apply | Same API contract; ≤3 liked artists, ≤5 interests |

## Interpretation contract

`crosssignal.interpret.Interpretation` (dataclasses, JSON-serialisable):

```json
{
  "mentions": [{"phrase": "Outer Wilds", "category": "games"}],
  "music": {
    "preferred": ["post-rock"],
    "avoided": ["country"],
    "era": "2010s",
    "discovery": "adventurous"
  },
  "interpreter": "gemini"
}
```

- `category` is optional and must be a `culture.CATEGORIES` id.
- Genre ids come from `GET /api/genres`; eras and discovery modes too.
- The output is validated, then every phrase goes through the same Qloo
  search and user confirmation as typed text.

## Safety rules for any interpreter

- Describe cultural references only. Never infer or store a person's
  character, religion, politics, health (including mental health),
  ethnicity, sexuality or other identity traits. The schema has no field
  for them, and the frontend has no place to show them.
- Never output Qloo ids, scores or artists; those come only from Qloo.
- Never claim a recommendation is personalised beyond what was confirmed.

## Not built yet

The Gemini SDK dependency, API key, prompts and an agent loop. These
need explicit approval (paid API, new integration) per AGENTS.md.
