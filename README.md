# CrossSignal · Culture Radio

**Discover music through the films, games, books, creators, places, and cultural references you already like.**

[**Try the live app**](https://crosssignal.onrender.com/) · [Project source](https://github.com/siamEEE/crosssignal) · [Qloo Agentic Hackathon 2026](https://qloo.devpost.com/)

CrossSignal starts from *culture*, rather than requiring you to name a favorite band. Select a few interests, optionally adjust genres and release eras, and tune your radio. The app uses the **Qloo Insights API** to discover associated artists, then checks the **Apple iTunes catalog** for actual songs and artwork. It presents the evidence behind a recommendation instead of treating cultural affinity as a guarantee that you will like something.

## What you can do

- **Build a cultural profile:** Search and confirm interests in films, TV/anime, games, books/manga, people, brands, places, and aesthetics.
- **Describe what you like:** Enter a short natural-language description; review and confirm the resolved cultural references before discovery.
- **Tune your music preferences:** Prefer, explore, or avoid genres; select multiple release eras; choose familiar, balanced, or adventurous discovery.
- **Listen and explore:** See artists connected to your interests, inspect the available evidence, play short catalog previews, and follow Apple Music links or artist-and-song searches on YouTube, YouTube Music, and Spotify.
- **Try another mix:** Keep your profile and look for additional Qloo-backed candidates while avoiding previously shown artists where possible.
- **Make a playlist:** Add tracks individually or in bulk; rename, reorder, remove, or clear your selection; copy a tracklist or export CSV.
- **Choose a mood:** Switch between **Daylight** and **After Hours** themes. Playlist, preferences, and theme are stored in your browser.

**Important distinctions:** Apple Music catalog links are track-specific; YouTube, YouTube Music, and Spotify links are **searches**, not verified matches or playlists created on those services. The in-app playlist is stored locally in the browser. Qloo affinities are associations, **not** predictions or probabilities of personal enjoyment.

## How it works

```text
User-selected cultural references
             |
      Qloo entity search
             |
    Confirmed entity / tag IDs
             |
  Qloo Insights artist candidates
             |
 Genre, era and discovery ranking
             |
     Apple iTunes catalog check
             |
  Real tracks + artwork + previews
             |
 Listen · Like / Dislike · Reroll · Save playlist
```

CrossSignal does not invent artists to fill a result page. Genre matches and limitations are shown where the available Qloo or music-catalog evidence is incomplete. The description interpreter currently uses deterministic parsing and user-confirmed Qloo entity resolution; the repository includes separate tool wrappers intended for possible agent integration, but **does not claim a deployed autonomous LLM agent**.

## Stack

| Layer | Technology |
| --- | --- |
| Frontend | React, TypeScript, Vite, Tailwind CSS, Motion |
| Backend | Python, FastAPI, Pydantic, httpx |
| Cultural discovery | Qloo Search + Insights |
| Track verification | Apple iTunes Search API |
| Deployment | Multistage Docker build on Render |
| Tests | pytest, Vitest, Ruff, TypeScript, frontend lint |

## Run locally

Prerequisites: **Python 3.12+**, [uv](https://docs.astral.sh/uv/), and **Node.js 24+**.

1. Clone this repository.
2. Create a local `.env` file in the repository root (never commit this file):

```dotenv
CROSSSIGNAL_PROVIDER=qloo
QLOO_API_KEY=your_qloo_api_key
QLOO_API_URL=https://hackathon.api.qloo.com
```

3. Install and build the frontend:

```bash
cd frontend
npm ci
npm run build
cd ..
```

4. Run FastAPI from the repository root:

```bash
uv sync --frozen
uv run --env-file .env uvicorn crosssignal.api:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`. The built React app and API are served on the same origin; `/api/health` reports backend status.

For frontend hot-reload development, run `npm run dev` inside `frontend/` while FastAPI is running.

### Checks

```bash
uv run pytest -q
uv run ruff check .
cd frontend
npm ci
npm run lint
npm run build
npx vitest run
```

## Availability and limitations

**The live demo relies on an event-issued Qloo API key.** Its access and quota are controlled by Qloo, and the key may be disabled after the hackathon/judging period. This repository cannot guarantee that live discovery will remain available indefinitely. If Qloo access ends, the source code, architecture, tests, and documented workflow remain available; live Qloo-powered artist discovery will need a valid replacement credential. The app reports missing upstream configuration instead of fabricating recommendations.

Render's free instance may also sleep when idle and require a short warm-up. Music previews and external catalog links depend on third-party availability. No music files are hosted in this repository.

## Evaluation and engineering notes

See [evaluation notes](docs/EVALUATION.md), [Qloo integration](docs/QLOO_INTEGRATION.md), and [development status](docs/STATUS.md). Synthetic fixtures and controlled tests are distinct from live Qloo outcomes; a successful catalog lookup alone does not prove recommendation quality.

## Submission and acknowledgments

Developed as a personal project for the **Qloo Agentic Hackathon 2026**. Qloo supplies cultural associations; Apple's iTunes catalog provides track metadata and short previews. CrossSignal is not affiliated with or endorsed by the linked music services.

