# Qloo integration

Status: **live and verified** against `https://hackathon.api.qloo.com`
(2026-10-21). Tests use mocked HTTP with synthetic fixtures whose field
names match the observed responses; no real Qloo response data is stored
in this repository.

## Architecture

```
app.py ──► factory.build_provider(config.load_settings())
              ├─ CuratedProvider            (default; demo data)
              └─ QlooProvider ── QlooClient ── GET /search, GET /v2/insights
                    │
                    ▼
     RecommendationSet(picks: ArtistPick..., unresolved: Interest...)
                    │
discovery.discover ─┴─► Discovery(results, unresolved, source, provider_error)
                    │
app.py renders only crosssignal.models types; never Qloo JSON.
```

| Module | Role |
|---|---|
| `models.py` | The contract: `ArtistPick` (+ optional `score`/`score_kind`/`external_id`/`evidence`), `Evidence`, `RecommendationSet`, `InvalidSelection`, `RecommendationError(kind)`, `Outcome` |
| `config.py` | Environment variables; `Secret` masks the key in every string form |
| `qloo.py` | HTTP client with bounded retry, defensive parsers, `QlooProvider` |
| `factory.py` | Picks the provider from configuration |
| `tools.py` | Function-calling tool declarations + dispatcher (agent groundwork) |
| `qloo_smoke.py` | Explicitly invoked two-call live shape check |

### Three kinds of "no results", kept separate

| Situation | Signal | UI |
|---|---|---|
| Invalid input (empty, > 5, unknown id) | `InvalidSelection` raised | Prevented by the picker; a raise means a bug |
| Provider failed | `Discovery.provider_error` = `auth`, `rate_limit`, `timeout`, `unavailable`, `malformed`, `bad_request`, `not_configured` | Error message by kind; Retry for rate limit/timeout/unavailable only. Never falls back to demo data |
| Provider had nothing | `Outcome.NO_RECOMMENDATIONS`, plus `unresolved` interests | Info message; names the interests the source couldn't use |
| Catalog had nothing / failed | `Outcome.EMPTY` / `FAILURE` / `PARTIAL` | As before |

### How QlooProvider recommends

1. **Resolve** each selected interest with `GET /search`, using its
   category's entity type (`Films` → `urn:entity:movie`, `Games` →
   `urn:entity:videogame`). Search is fuzzy, so only an **exact**
   normalized name match of the right type counts. If several exact
   matches exist (e.g. five films called "Drive"), the one with the
   highest `popularity` wins. Aesthetics have no entity type and are
   reported as unresolved rather than mapped to a guessed entity.
2. **Recommend** with one
   `GET /v2/insights?filter.type=urn:entity:artist&signal.interests.entities=<id>&feature.explainability=true`
   per resolved interest, so each artist is credited only to the
   interests whose query really returned it. Entities whose types do not
   include `urn:entity:artist` are dropped.
3. **Merge** round-robin up to 8 artists, deduplicating by Qloo entity id
   and normalized name. An artist returned for several interests is
   credited to all of them.
4. **Provenance**: each pick carries `Evidence` per interest: the Qloo
   entity it resolved to, the artist's rank in that answer, its
   `query.affinity`, and its explainability share for that signal.
5. **Scores**: the card shows rank and affinity ("Qloo's #2 artist for the
   film *Drive* · affinity 0.92") with a tooltip saying affinity is an
   association ranking, **not** a probability that the user will like the
   artist. Demo "vibe" text is not shown on Qloo cards.

`discover()` also drops a track already shown on an earlier card
(collaborations), unless that would leave a card empty.

**Why not one joint query?** Tried live with Interstellar + Hollow Knight:
Qloo returned broadly popular artists (explainability split ~50/50),
not ones specific to either title. Per-interest queries give clearer
provenance. Revisit if blended results are wanted.

Calls per discovery: up to 5 searches + 5 insights (the hackathon key's
limit was 10 requests/second). Successful results are cached
in-process; failures are not, so Retry re-requests them.

### Retries

Timeouts, connection errors, 429 and 502/503/504 are retried at most twice
(0.5 s, then 1.5 s; a numeric `Retry-After` is honoured up to 5 s).
401/403/400/404 are raised immediately.

## Observed API behaviour (2026-10-21)

| Item | Observed |
|---|---|
| Host | `https://hackathon.api.qloo.com` (now the default) |
| Auth | `X-Api-Key`; missing or wrong key → 401, `text/plain` body |
| `/search` response | `{results: [...]}` only; no `success`/`duration` |
| Search entity fields | `name`, `entity_id`, `types` (list), `properties`, `popularity`, `disambiguation`, `tags` |
| Search matching | Fuzzy; a nonsense query still returns 200 with unrelated titles |
| `/v2/insights` response | `{success, results: {entities}, query: {explainability}}` |
| Artist entity | `type: "urn:entity"`, `subtype: "urn:entity:artist"`, `query.affinity` (float 0–1), `query.measurements`, `popularity`, `properties`, `tags`, `external` |
| Explainability | Per artist `query.explainability["signal.interests.entities"] = [{entity_id, score}]`; top level `query.explainability["signal.interests.entities"].effect_on_top{3,5,10}_recs` / `effect_on_all_recs` = `[{entity_id, avg_score}]` |
| Unknown signal id | 400, "All of the provided signal.interests.entities were invalid" |
| Unknown path | 404 "Not Found" |
| Rate-limit headers | `x-second-ratelimit-{limit,remaining,reset}` (limit 10), `x-month-ratelimit-*` |

### Discrepancies with documentation

- The hackathon guide lists `urn:entity:video_game`; `/search` rejects it
  with 400. `urn:entity:videogame` works and is what entities carry.
- The API reference describes 404 as "No results"; live, an empty search
  is 200 with fuzzy matches, and 404 only came back for an unknown path.
  404 is now an error (`bad_request`), not silently an empty list.
- `/search` has no `success`/`duration` keys.
- Artist `type` is `urn:entity`; the artist URN is in `subtype`.
- With a single signal, the explainability `score` is an integer (1).

### Picker resolution (live)

| Interest | Resolves to |
|---|---|
| Blade Runner 2049, Interstellar, Drive (2011), Lost in Translation | movie |
| Cyberpunk 2077, Journey (2012), Hollow Knight | video game |
| Studio Ghibli | unresolved (a studio, not a movie) |
| 4 aesthetics | unresolved (no entity type) |

## Configuration

| Variable | Default | Notes |
|---|---|---|
| `CROSSSIGNAL_PROVIDER` | `curated` | `qloo` to use Qloo |
| `QLOO_API_KEY` | (none) | Required for `qloo`. Never printed or rendered |
| `QLOO_API_URL` | `https://hackathon.api.qloo.com` | Must be `https://` |
| `QLOO_TIMEOUT_SECONDS` | `10` | 0–60 |

Invalid configuration shows a warning in the app (with no values) and
falls back to clearly labelled demo data. The app does not read `.env`
itself; `uv run --env-file .env` passes it to the process.

## Running live

```powershell
# Shape check: 2 calls, prints field names/types and entity names, never the key
uv run --env-file .env python -m crosssignal.qloo_smoke
uv run --env-file .env python -m crosssignal.qloo_smoke --query "Hollow Knight" --type urn:entity:videogame

# The app against Qloo
$env:CROSSSIGNAL_PROVIDER = "qloo"
uv run --env-file .env streamlit run app.py
Remove-Item Env:CROSSSIGNAL_PROVIDER
```

## Live validation (2026-10-21, aggregates only)

Real `QlooProvider` + live iTunes through `discover()`:

| Runs | Result |
|---|---|
| 9 single-interest runs (every film and game, plus one aesthetic) | 7 returned 8 artists each; Studio Ghibli and Dark academia correctly returned no recommendations |
| 4-interest run (2 films, 1 game, 1 aesthetic) | 8 artists, round-robin across the 3 resolved interests; aesthetic listed as unresolved |
| 5-interest run (2 films, 2 games, 1 aesthetic) | 8 artists across the 4 resolved interests |
| Total | 72 artists recommended; 72/72 had exact-name iTunes tracks; 0 provider errors; 0 duplicate tracks across cards |
| Headless app (live, 4 interests) | Live banner, 8 Qloo-attributed cards, 24 Apple Music links, unresolved notice, key not rendered |
| Headless app (invalid key) | "rejected its API key" error, no cards, no Retry, no demo fallback |

Quality notes for human review: Journey's artists skew to punk/indie and
overlap Lost in Translation's; one single-interest list had a mainstream
pop outlier at rank 8. These are Qloo's answers, shown as returned.

## Function-calling groundwork

`tools.py` declares three tools (`list_interests`, `recommend_artists`,
`find_tracks`) using only the JSON-schema keywords Gemini documents.
`ToolBox.call(name, args)` validates arguments, calls the existing
provider and catalog functions, and returns JSON-ready dicts. Each result
names its `source`, and errors come back as `{"error": {...}}`.

Not built yet: the Gemini SDK dependency, an agent loop, and any
prompts. Those need approval for the `google-genai` dependency and a
Gemini API key.
