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
