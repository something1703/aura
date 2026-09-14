# AURA web UI

A Next.js front end for AURA: a static "how it works" walkthrough plus a live demo that
posts a workload YAML to the AURA API and renders the real result (candidate comparison,
topology diagrams, scoring breakdown, failure analysis, cost analysis, ADRs, full report).

`src/lib/api.ts` calls this app's own origin (`/api/*`); it never talks to the AURA API
directly. `src/app/api/[...path]/route.ts` is the one bit of server-side logic that does —
a Route Handler that forwards each request to the real FastAPI JSON API in
`../src/aura/web/app.py`, which runs the same engines as the `aura` CLI.

## Run it

```bash
# terminal 1, from the repo root
pip install -e .
aura serve                 # http://127.0.0.1:8000

# terminal 2, from this directory
npm install
npm run dev                # http://localhost:3000
```

`AURA_API_URL` (default `http://127.0.0.1:8000`) points the proxy Route Handler at the
API — read from the environment at request time, not baked in at build time, so it's set
with plain `AURA_API_URL=... npm run dev` / `docker run -e AURA_API_URL=...`, never as a
`NEXT_PUBLIC_*` build arg. Because the browser never leaves this app's own origin, the
API's `AURA_WEB_ORIGIN` CORS setting doesn't come into play in normal use.

## Structure

- `src/app/page.tsx` — hero + "How it works" (static) + `<AnalyzeDemo />`
- `src/components/AnalyzeDemo.tsx` — the interactive demo: textarea, results tables
- `src/components/MermaidDiagram.tsx` — renders a topology graph to SVG
- `src/components/ReportMarkdown.tsx` — renders the generated Markdown report/ADRs
- `src/lib/api.ts` — typed client for the AURA API
