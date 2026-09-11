# AURA web UI

A Next.js front end for AURA: a static "how it works" walkthrough plus a live demo that
posts a workload YAML to the AURA API and renders the real result (candidate comparison,
topology diagrams, scoring breakdown, failure analysis, cost analysis, ADRs, full report).

This app has no server-side logic of its own — every `src/lib/api.ts` call hits the FastAPI
JSON API in `../src/aura/web/app.py`, which runs the same engines as the `aura` CLI.

## Run it

```bash
# terminal 1, from the repo root
pip install -e .
aura serve                 # http://127.0.0.1:8000

# terminal 2, from this directory
npm install
npm run dev                # http://localhost:3000
```

`NEXT_PUBLIC_AURA_API_URL` (default `http://127.0.0.1:8000`) points this app at the API.
The API's `AURA_WEB_ORIGIN` env var allow-lists an extra CORS origin if you run the UI on a
non-default host/port.

## Structure

- `src/app/page.tsx` — hero + "How it works" (static) + `<AnalyzeDemo />`
- `src/components/AnalyzeDemo.tsx` — the interactive demo: textarea, results tables
- `src/components/MermaidDiagram.tsx` — renders a topology graph to SVG
- `src/components/ReportMarkdown.tsx` — renders the generated Markdown report/ADRs
- `src/lib/api.ts` — typed client for the AURA API
