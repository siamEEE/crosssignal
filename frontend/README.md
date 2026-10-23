# CrossSignal · Culture Radio (frontend)

React 19 + TypeScript + Vite + Tailwind CSS v4, with shadcn/ui-style
components on Radix primitives, Motion for animation and Lucide icons.
It talks only to the FastAPI backend in `src/crosssignal/api.py`.

```powershell
# from the repository root: backend (serves the built app at :8000 too)
uv run --env-file .env uvicorn crosssignal.api:app --port 8000

# frontend dev server with hot reload (proxies /api to :8000)
cd frontend
npm install
npm run dev        # http://localhost:5173

npm run build      # type-check + production build into frontend/dist
npx vitest run     # unit tests (profile reducer, explanation text)
npm run lint       # oxlint
```

Layout:

| Path | Role |
|---|---|
| `src/lib/api.ts`, `types.ts` | Typed API client; errors become `ApiError(kind, message)` |
| `src/lib/profile.ts` | Profile reducer (interests, genres, era, discovery, feedback) + localStorage convenience |
| `src/lib/explain.ts` | Every user-facing explanation, derived only from API fields |
| `src/components/ui/` | Vendored shadcn/ui-pattern components (Button, Tooltip, Segmented) |
| `src/components/` | Header, Hero, Explore, Describe, Sound, Radio, Tray, Player |

Design tokens (palette, fonts, motion) live in `src/index.css`
(`@theme`). Motion respects `prefers-reduced-motion`.

Browser contrast regression checks (local synthetic fixtures, no credentials):

```powershell
# Repository root, after npm run build in frontend:
uv run python tests/contrast_server.py
# In a second terminal, launch an isolated Edge/Chromium profile with
# --remote-debugging-port=9336 and --user-data-dir pointing inside .review/.
node frontend/scripts/audit-contrast.mjs
```

The runner uses development-only axe-core plus computed sRGB contrast checks
for text, placeholders, translucent fills, gradient-stop combinations, control
boundaries and focus rings. It exercises both themes at 375/1440 px, including
selected, hover, disabled, results, playlist, loading, error and notification
states. Screenshots and a JSON report go to ignored `.review/v31/`. Any measured
contrast failure or axe violation makes the command fail. Gradient envelopes
are conservative; screenshot review remains necessary for overlapping content,
artwork and browser/OS-owned native confirmation dialogs.
