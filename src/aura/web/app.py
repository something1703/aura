"""A small FastAPI JSON API over the Phase 1 pipeline.

This is a thin transport layer, not a new engine: every endpoint calls the
same functions the CLI calls (`aura.requirements`, `aura.architecture`,
`aura.evaluation`, `aura.reporting`). Nothing here duplicates domain logic.

The UI lives in the separate Next.js app under `web/` (started with
`npm run dev`), which talks to this API — it is CORS-enabled for that
purpose. This process never serves HTML itself.
"""

from __future__ import annotations

import os
from importlib import resources
from typing import Any

import yaml
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError

from aura import __version__
from aura.architecture.generator import generate_candidates
from aura.domain.models import Workload
from aura.errors import AuraError
from aura.evaluation.engine import evaluate_all, select_recommendation
from aura.reporting.adr import generate_adrs
from aura.reporting.context import build_context
from aura.reporting.diagram import to_mermaid
from aura.reporting.markdown import render_report
from aura.requirements.normalizer import normalize

_DEFAULT_ALLOWED_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]
_extra_origins = os.environ.get("AURA_WEB_ORIGIN")

app = FastAPI(title="AURA API", version=__version__)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_DEFAULT_ALLOWED_ORIGINS + ([_extra_origins] if _extra_origins else []),
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    yaml_text: str


@app.get("/api/example")
def example() -> dict[str, str]:
    # Bundled as package data (not read from ../../config/ by relative path)
    # so this works the same whether run from source, `pip install`, or the
    # Docker image — none of which put the repo's config/ next to the
    # installed package. Kept in sync with config/flash-commerce.yaml by
    # hand; that file is still the one the CLI and docs point at.
    text = resources.files("aura.web.examples").joinpath("flash-commerce.yaml").read_text(encoding="utf-8")
    return {"yaml_text": text}


def _error_response(status_code: int, message: str, details: list[str] | None = None) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": message, "details": details or []})


@app.post("/api/analyze")
def analyze(request: AnalyzeRequest) -> JSONResponse:
    try:
        document = yaml.safe_load(request.yaml_text)
    except yaml.YAMLError as exc:
        return _error_response(400, f"invalid YAML: {exc}")

    if not isinstance(document, dict):
        return _error_response(400, "workload document must be a YAML mapping at the top level")

    try:
        workload = Workload.model_validate(document)
    except ValidationError as exc:
        details = [
            "{}: {}".format(".".join(str(p) for p in e["loc"]), e["msg"]) for e in exc.errors()
        ]
        return _error_response(422, f"workload failed validation ({len(details)} issue(s))", details)

    try:
        normalized = normalize(workload, raw_document=document)
        candidates = generate_candidates(normalized)
        scores = evaluate_all(candidates, normalized)
        ctx = build_context(workload, normalized, candidates, scores)
        report_markdown = render_report(ctx)
        adrs = generate_adrs(ctx)
    except AuraError as exc:
        return _error_response(400, str(exc))

    recommendation = select_recommendation(scores)

    payload: dict[str, Any] = {
        "workload": workload.model_dump(mode="json"),
        "normalized": normalized.model_dump(mode="json"),
        "candidates": [
            {**c.model_dump(mode="json"), "diagram": to_mermaid(c.topology)} for c in candidates
        ],
        "scores": [s.model_dump(mode="json") for s in scores],
        "recommendation_id": recommendation.candidate_id if recommendation else None,
        "report_markdown": report_markdown,
        "adrs": adrs,
    }
    return JSONResponse(content=payload)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}
