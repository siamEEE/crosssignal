
# CrossSignal Development Status



## V3.1 contrast and copy correction (2026-10-24)

- Fixed the release-blocking After Hours collection conflict: collection cards
  use semantic data-accent surfaces, with explicit heading, body, metadata,
  artwork and chip colors. Removed global accent-utility foreground overrides.
  Small signal badges and buttons now own their foreground/background pairs.
- Preserved Daylight layout and the midnight/teal/plum/violet After Hours
  palette. Audited controls, selected genres/eras, description confirmation,
  loading/errors, listening links, playlist, notifications and keyboard focus.
  Disabled controls remain readable; outlines have contrasting halos and no
  delayed color transition. Opaque navigation avoids text contrast changing
  as content scrolls beneath it. Artist headings have an opaque artwork label.
- Also corrected Daylight description-panel text, error contrast, and a mobile
  playlist name field that was squeezed by the export buttons. No discovery,
  era ranking, reset, reroll, playlist persistence or theme behavior changed.
- Replaced all five poetic Culture Notes blurbs with ordinary descriptions;
  simplified description guidance, the After Hours introduction and genre
  discovery copy. No Qloo evidence or compatibility claims were invented.
- Added development-only axe-core and a repeatable local synthetic fixture
  server/browser audit. At 375 and 1440 px in both themes, 50 state checks
  passed with no measured text/control contrast failures, axe WCAG A/AA
  violations or app exceptions. Checks include gradient-stop envelopes,
  composited translucent colors, placeholders, disabled/hover/selected states,
  focus, all five cards, loading/errors, preview player and reset notification.
- Measured minimum normal-text contrast: 4.75:1; relevant control boundary:
  3.31:1. After Hours collection headings: 9.35-10.79:1; descriptions at least
  8.15:1. Browser screenshots of both themes were inspected, including mobile
  collections, description, genre/era controls, recommendations and playlists.
  Local screenshots and the full report are ignored under `.review/v31/`.
- Python: 272 tests; frontend: 35 tests; Ruff, frontend lint, TypeScript,
  production build and Git whitespace checks pass. Existing Starlette warning
  and ~533 kB production JS bundle warning remain. axe is not in the app bundle.
- Remaining manual checks: physical-device displays/audio and screen readers;
  native Reset confirmation appearance is browser/OS-owned (its behavior and
  text were checked). Synthetic fixtures are only for local tests; no live
  Qloo/catalog calls or credentials were used. User authorized the exact V3.1
  commit message and push to origin/feat/render-deployment; Render unchanged.

## V3 product sprint (2026-10-23)

- Implemented on `feat/render-deployment`, preserving the accepted Daylight
  layout and existing Python/FastAPI/Render Docker boundary. No new packages,
  services, authentication or credentials were needed or accessed.
- Multi-era preferences now run through profile migration, toggles, description
  interpretation, API, Python scoring, track selection and explanations.
  Overlapping year ranges count once; selected eras receive track coverage
  where the limited catalog sample permits. Eras remain soft preferences.
  Legacy single-era requests remain supported; explicit `eras: []` clears them.
- Header Reset has native confirmation, aborts/invalidate pending discovery,
  clears taste/profile/results/history and search drafts, and stops playback.
  Playlist and theme remain intact.
- Try another mix requests subsequent real Qloo pages, preserving preferences
  and explicit dislikes. A bounded 160-artist session history is excluded
  upstream and checked locally by id/name. Likes do not erase history;
  More like this adds artist evidence as a distinct refinement. Page cap is
  20, with honest empty-page and session-limit guidance; no automatic retries
  across extra pages or extra provider calls to pad a short selection.
- My Playlist replaces the saved-rotation UI and migrates its tracks. Individual
  and bulk add, Apple track-id dedupe, remove, up/down reorder, rename, validated
  storage (300-song bound), readable copy and formula-safe CSV export. Artist
  feedback stays separate. Exact Apple links and labeled artist+track searches
  retained. No external playlist synchronization is claimed.
- Persistent Daylight / After Hours choice, system preference on first visit,
  and pre-paint initialization. After Hours uses indigo/petrol/plum surfaces,
  cyan record details, amber sleeve accents, distinct navigation/playlist
  treatments, quieter masthead copy and visible focus. Core datasets and
  ranking are independent of theme. Guidance and error/era copy audited.
- Validation: 272 Python tests and 32 frontend tests passed; Ruff, frontend
  lint, TypeScript, production build and diff checks passed. Local headless
  Edge checked both themes at 375/768/1440 px, storage migrations, simultaneous
  eras, playlist reorder/rename/remove/CSV, refresh and confirmed reset.
- Additional local-only synthetic browser fixtures exercised the actual API
  and built frontend: pages 1/2/3, unseen artists, retained dislikes and all
  three eras, individual/bulk playlist add, empty pools, and an intercepted
  in-flight response after Reset. All passed with no app exceptions. These
  fixtures live only in ignored `.review/`, never in the production app.
- Remaining verification: live Qloo/catalog quality and quota behavior, audible
  playback on real phones (especially iOS), screen-reader traversal, clipboard
  permissions and a Docker image build. Existing Starlette deprecation and
  ~532 kB JavaScript bundle warning remain. No secrets or generated artifacts
  are included in the release commit. User explicitly authorized commit/push
  to `origin/feat/render-deployment` for the existing Render auto-deploy.

## Editorial redesign implementation (2026-10-23)

- Completed the user-authorized React visual redesign: paper masthead with
  original CSS record artwork, a three-step journey, search-first culture
  browser, illustrated asymmetric collections, green description section,
  lilac music controls and artwork-led radio results. Small-phone navigation
  and masthead are condensed; reduced motion and keyboard focus remain.
- All eight backend cultural categories and 13 genre families retained,
  including expandable rock/metal and advanced subgenres. No fabricated
  Qloo results, new integrations, dependencies or backend changes.
- Every track offers explicitly labeled artist + track searches on YouTube,
  YouTube Music and Spotify. Exact Apple Music links and previews retained.
- Independent saved-song rotation persists locally (100-song cap), separate
  from the three liked artists steering Qloo remixes; malformed storage and
  unsafe restored Apple links are rejected. Favorites remain available on
  reload before tuning another station.
- Featured selections can be retried when the query/category is unchanged.
  Corrected empty-result advice: open-to genres still filter the search.
- Validation: 265 pytest tests passed; 16 frontend tests passed; Ruff,
  frontend lint, TypeScript and Vite production build passed. Headless Edge
  checked 375/768/1440 px: no page overflow or app exceptions, nine category
  buttons (including Everything), 13 genres, search before collections,
  expandable Metalcore. Local screenshots are in ignored `.review/`.
- Python validation uses a workspace UV_CACHE_DIR and a fresh workspace
  pytest basetemp because the default cache/temp paths were inaccessible.
- Remaining: live Qloo/catalog calls were not made and no credentials were
  read; local browser checks cover the honest unconfigured state. Results
  interactions are covered by logic tests, not a live-provider browser run.
  Real-device audio, screen-reader checks and Docker image build remain
  unverified. Existing Starlette deprecation and ~521 kB JS bundle warning.
- Docker deployment recipe unchanged; local validation artifacts excluded
  from Git and Docker context. No commit, push or deployment performed.

## Current phase
V3.1 contrast/copy correction validated on `feat/render-deployment` (2026-10-24).
Release is authorized for commit/push to the existing deployment branch.
Earlier sprint notes below are historical checkpoints.

### Redesign and correctness sprint implementation
- Visible tune action renamed **Tune My Radio**, with a contrasting lime button;
  section navigation is available on mobile and spells out the tuning steps.
- Music editorial treatment: dark masthead, oversized serif headline, vinyl
  motif, paper sections and tighter card corners.
- Artist search links for YouTube, YouTube Music and Spotify; existing direct
  Apple Music track links retained. No new API integration or dependency.
- Reproduced and fixed two genre errors: Metal catalog evidence incorrectly
  confirmed a simultaneous Jazz preference; broad Metal catalog evidence alone
  incorrectly established an avoided Metalcore subgenre. Added regression tests.
- Discovery request ordering, aborted-search suppression, description revision
  checks, previous-profile pagination, changed-profile notice and page cap.
- Defensive storage parsing and a 50-artist hidden-feedback bound.
- API body, concurrency and process-wide request budgets; same-origin browser
  enforcement and response headers. See `docs/PUBLIC_DEPLOYMENT.md` for limits.
- Final validation: 265 Python tests, 13 frontend tests, Ruff, frontend lint,
  TypeScript and production build passed; Git whitespace check passed.
  Existing warnings: Starlette/httpx deprecation and ~519 kB frontend bundle.
- Browser visual/device verification and live provider calls have not been run
  during this sprint. No credentials were accessed; no commit, push or deploy.

Culture Radio vertical slice on `feat/qloo-live` (2026-10-21).
Checkpoint commit `49cf591` (local, user-approved) holds UI V1,
evaluation and live Qloo work. Everything after it is uncommitted.
Streamlit (`app.py`) remains the working fallback/release path.

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

- Culture Radio Phase 1, FastAPI engine boundary (2026-10-21, uncommitted):
  - New stdlib-only engine modules: `genres.py` (hierarchical taxonomy, 89
    Qloo music-genre tag ids, all observed live), `culture.py` (8 human
    categories -> verified Qloo entity/tag types; search + exact/ambiguous
    resolution; featured collections as names only), `interpret.py`
    (id-free NL contract + deterministic interpreter), `ranking.py` (pure
    genre verdicts, era/familiarity, track selection), `engine.py`
    (validate -> Qloo -> pre-rank -> bounded catalog check -> rank)
  - `api.py` (FastAPI): health, categories, featured, genres, search,
    interpret, discover; in-memory TTL cache; Qloo errors -> 429/502/503/504
    with a uniform `{error: {kind, message}}` body; serves `frontend/dist`
  - New deps (project-local, in `pyproject.toml`/`uv.lock`): `fastapi`,
    `uvicorn`
  - Key live finding: Qloo genre tags are noisy (a pop star tagged
    `black_metal`), so a genre match is "confirmed" only when Qloo tags
    and the Apple Music genre agree; contradictions are excluded and counted
  - 260 pytest tests; Ruff clean
  - Follow-up: `related_only` flag so a genre match via a related family
    (Qloo "Electronic", Apple "Pop") is never described as agreement

- Culture Radio Phases 2-4, React frontend + live slice (2026-10-21,
  uncommitted; see `frontend/README.md`, `docs/AGENT_DECISIONS.md`):
  - `frontend/`: Vite + React 19 + TypeScript (strict) + Tailwind v4,
    shadcn/ui-pattern components on `radix-ui`, `motion`, `lucide-react`,
    `clsx`/`tailwind-merge`/`class-variance-authority`; `vitest` (dev).
    Project-local npm only (`frontend/package-lock.json`); 0 vulnerabilities
  - Ivory/coral/lime/violet/apricot/ink design tokens, Fraunces + Space
    Grotesk, category-coloured styling, reduced-motion support
  - Sections: Explore (featured collections + live search across 8
    categories, ambiguity/suggestion states), Describe (deterministic NL
    reader, per-phrase confirmation, "apply music" step), Sound
    (preferred/open/avoid genre cycle, advanced subgenres, era,
    familiar/balanced/adventurous), Radio (grounded artist cards, 30 s
    previews, like / not for me / more like this, remix, dig deeper),
    sticky profile tray, shared preview player
  - Honest states: live/not-configured/offline banners, 503/429/5xx
    errors with retry where useful, `insufficient`/`empty` results with
    exclusion counts; no demo data in this UI
  - Live headless-Edge run (CDP script in session scratchpad, no deps):
    featured exact add, ambiguous "Drive" pick, aesthetic tag, Electronic
    preference -> 8 artists, all genre-confirmed, previews play; like +
    hide + remix excluded both and credited the liked artist; dig deeper
    returned 8 new artists; describe flow; no console errors from the app;
    390 px mobile with no page overflow after two fixes (grid min-width,
    genre tile width); unconfigured server shows a clear disabled state
  - Streamlit fallback unchanged and still starts (health ok; 20 UI tests)
  - Frontend: `tsc -b` clean, oxlint clean, 11 vitest tests, build ok

- Product-quality sprint plan (2026-10-21): superseded by the Culture
  Radio brief (final product decisions); probe findings kept below.
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
- Independent Codex review of the Culture Radio slice
- Manual browser checklist (real device/keyboard/screen reader; see the
  implementation report): focus order from the top of the page, tooltip
  keyboard access, audio on iOS Safari, real 375 px phones
- Approval to delete unused Vite scaffold files (`frontend/src/App.css`,
  `frontend/src/assets/*`, `frontend/public/icons.svg`)
- iTunes Search API rate limiting (~20 calls/min) can produce
  "catalog couldn't check" exclusions on rapid repeated remixes
- Aesthetic tags: effect on results is unmeasured; consider a live A/B
  check before featuring them more prominently
- Gemini interpreter: contract and validation exist; SDK, key and prompts
  need approval
- Frontend bundle is 516 kB (165 kB gzip); code-splitting not done
- Human review of Qloo result quality (Journey skews punk/indie; an
  occasional mainstream outlier)
- Artist identity across catalogs is by exact name only; same-name
  artists in iTunes could be a different act
- Approval for `google-genai` dependency and Gemini key before agent work
- `eval/results/` is committed (decided at checkpoint `49cf591`)
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
Independent Codex review of the Culture Radio slice, then (with
approval) commit it on top of checkpoint `49cf591`.

## Current blockers
- None for the vertical slice. Release path: Culture Radio (FastAPI +
  React) if review passes; Streamlit remains the working fallback.
- Everything after `49cf591` is uncommitted pending review.
