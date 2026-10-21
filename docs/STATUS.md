
# CrossSignal Development Status

## Current phase
Live Qloo integration on branch `feat/qloo-live`: verified end to end
against the hackathon API (2026-10-21). UI V1, quality sprint, evaluation
framework and Qloo work are all still uncommitted.

## Completed
- Devpost account created
- Qloo API key requested
- Python project initialized with uv
- Streamlit server started successfully
- Claude Code and Codex installed and signed in
- Initial Git commit (`3cce20b`)
- Live iTunes track search confirmed for all 23 curated artists (2026-10-18)
- UI V1 implementation (2026-10-18):
  - Retrieval split from presentation: `models`, `catalog`,
    `recommendations`, `discovery`, `text` modules under `src/crosssignal/`
  - `app.py` is UI only; `RecommendationProvider` protocol ready for Qloo
  - Codex audit fixes: validated iTunes JSON/shape/field types; normalized
    exact artist matching (no substring matches); results persist in
    session state; real per-artist progress with success / partial /
    failure / empty outcomes
  - 12 curated interests (6 added) across Films, Games, Aesthetics; max 5
  - Dark theme via `.streamlit/config.toml`, minimal CSS
  - 49 pytest tests (incl. headless AppTest UI tests); Ruff clean
- UI V1 quality sprint (2026-10-20, uncommitted):
  - Fix: bracketed feature credits ("Kavinsky (feat. X)") were rejected
    by artist matching; brackets are now credit separators
  - Track meta compares artist names with the same normalization as matching
  - Progress bar is always cleared, even if discovery raises
  - Accessibility: hero title is a real `<h1>`; track artwork has alt text
  - Results caption states artist count and interests; multi-interest
    credits read "A, B and C" (`text.join_names`)
  - New regression tests: five-interest run (artist cap, shared-artist
    credit), artwork + Markdown-injection rendering, all-empty outcome,
    retry after selection change, cached re-discovery, reset while stale
  - 59 pytest tests; Ruff clean; live five-interest iTunes run succeeded

- Recommendation evaluation framework (2026-10-20, uncommitted; see
  `docs/EVALUATION.md`):
  - `crosssignal.evaluation` package (stdlib only): normalized schemas,
    curated / seeded random-baseline / replay adapters, catalog probe
    (live, snapshot, none), pure metrics, runner, Markdown report, CLI
  - Blinded pairwise human-preference tasks and scoring (Wilson interval),
    labelled as preference, not accuracy
  - `eval/profiles.json`: 20 synthetic profiles over 12 domains, including
    unsupported, partial, ambiguous, duplicate and invalid inputs
  - `eval/catalog_snapshot.json`: real iTunes answers for the 23 curated
    artists, recorded 2026-10-20, for deterministic offline runs
  - `Track.genre` added from iTunes `primaryGenreName` (optional)
  - Finding: random baseline scores ~100% on grounding and coverage, so
    those are sanity checks only; musical fit needs human judgment
  - No LLM or Qloo responses exist yet; none were fabricated
  - 116 pytest tests; Ruff clean

- Qloo integration readiness (2026-10-20, uncommitted; see
  `docs/QLOO_INTEGRATION.md`):
  - Normalized contract in `models.py`: `RecommendationSet` (picks +
    unresolved interests), optional real `score`/`score_kind`/`external_id`
    on `ArtistPick`, `InvalidSelection`, `RecommendationError(kind)`
  - `discover()` separates invalid input (raises), provider failure
    (`Outcome.PROVIDER_ERROR`) and empty answers (`NO_RECOMMENDATIONS`)
  - `qloo.py`: client for documented `/search` and `/v2/insights`;
    typed errors (auth, rate limit, timeout, unavailable, malformed, bad
    request); documented 404 = no results; strict exact-name resolution;
    per-interest attribution; affinity used only if present
  - `config.py` env configuration with masked `Secret`; `factory.py`
  - UI shows source labels, provider errors by kind, retry where useful,
    and unresolved interests; depends only on `crosssignal.models`
  - `tools.py`: function-calling declarations + dispatcher over existing
    functions (no LLM SDK, no agent loop)
  - `qloo_smoke.py`: two-call live shape check that never prints the key
  - 169 pytest tests; Ruff clean
  - Unverified until live: affinity field location, search `types` field,
    which picker names resolve, auth status codes, hackathon host
    (all since verified; see below)

- Live Qloo integration (2026-10-21, uncommitted; see
  `docs/QLOO_INTEGRATION.md`):
  - Key loaded via `uv run --env-file .env`; never printed or rendered
  - Default host is now `https://hackathon.api.qloo.com`
  - `qloo_smoke` rewritten: Interstellar -> /search -> artist insights
    with `feature.explainability=true`; prints field names/types only
  - Verified fields: `query.affinity`, per-artist and aggregate
    `query.explainability`, artist URN in `subtype`, search `types` list
  - Doc discrepancies: `urn:entity:video_game` rejected (use
    `videogame`); 404 = unknown path, not "no results" (now an error);
    `/search` has no `success`/`duration`
  - Client: bounded retry (2) for timeout/network/429/502-504, honours
    `Retry-After` up to 5 s; non-artist entities dropped
  - Provider: most-popular exact match among same-name titles ("Drive");
    dedupe by entity id and name; per-interest `Evidence` (resolved
    entity, rank, affinity, explainability share)
  - UI: Qloo cards show "Qloo's #N artist for the film X · affinity"
    with a not-a-probability tooltip; demo vibes hidden on Qloo cards
  - `discover()` drops a track already shown on an earlier card
  - Live: 11 runs, 72/72 Qloo artists matched iTunes tracks, 0 provider
    errors; 7 of 8 film/game picks resolve (Studio Ghibli does not),
    aesthetics unresolved; headless live-app and invalid-key checks pass
  - 185 pytest tests; Ruff clean

- Product-quality sprint (2026-10-21): **planned only, not implemented;
  awaiting approval.** No source changes were made for it.
  - Read-only live probe (~15 calls) findings:
    - Artist entities carry `urn:tag:genre:music` tags and properties
      `primary_genres`, `secondary_genres`, `start_year`, `obscurity_scale`
    - Artist insights honour `filter.tags` with a music-genre tag
      (genre-consistent results) and `filter.popularity.max`
    - Release-year filters are documented for movies/TV only, not artists
    - `/v2/tags?filter.query=` resolves aesthetics ("dark academia" ->
      ambience tags) and subgenres (metalcore, shoegaze, post-rock)
    - An ambience tag alone as `signal.interests.tags` gave incoherent
      artists; not usable as a standalone signal without further testing
    - `/search` works for `urn:entity:book`, `tv_show`, `person`; names
      are ambiguous ("Dune (Dune, #1)", two "Twin Peaks"), so user
      confirmation is needed; Studio Ghibli does not resolve as a brand
  - Proposed design: separate resolution / Qloo discovery / catalog
    validation / ranking / presentation stages; searchable confirmed
    interests; optional genre, era and familiarity profile; deterministic
    ranking with genre tiers (confirmed / no evidence / mismatch);
    explicit "insufficient compatible artists" outcome; session feedback;
    documented agent decision points. No new dependencies.

## Pending
- Approve the product-quality sprint plan and answer its five open
  decisions: aesthetic tags as modifier-only vs. deferred; hide vs. show
  genre mismatches; session-only feedback; featured collection contents;
  approval scope (all steps, or stop after step 2 or 5)
- Manual browser check of live Qloo mode (cards, tooltip, mobile width)
- Decide how aesthetics and Studio Ghibli should work in live mode
  (e.g. `/v2/tags` + `signal.interests.tags`, or a brand entity); needs
  a design decision
- Human review of Qloo result quality (Journey skews punk/indie; an
  occasional mainstream outlier)
- Artist identity across catalogs is by exact name only; same-name
  artists in iTunes could be a different act
- Approval for `google-genai` dependency and Gemini key before agent work
- Decide whether `eval/results/` is committed or git-ignored
- Human pairwise judgments (none collected yet)
- LLM-only recordings (needs approval for a paid LLM API)
- Manual browser verification of UI V1 (desktop and mobile widths):
  hero heading styling, card artwork sizing, track rows at ~375px,
  keyboard focus order, offline behaviour (lookups are sequential with a
  15 s timeout, so a fully offline run can take a while before erroring)
- Codex review of UI V1 changes
- Verify agent permissions
- Evaluation adapter for `QlooProvider`, then the Qloo steps in
  `docs/EVALUATION.md`

## Rules
- No fabricated API responses
- No unnecessary frameworks
- No paid APIs without approval
- No large changes without review

## Next milestone
Human review of the live Qloo integration, then commit the accumulated
uncommitted work (UI V1, evaluation, Qloo) in reviewable commits, then
start the approved product-quality sprint at step 1 (stage separation).

## Current blockers
- Product-quality sprint: approval and design decisions pending.
- Nothing has been committed since `3cce20b`; a large uncommitted
  working tree raises review and loss risk.
