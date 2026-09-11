"""Shared data assembly for the Markdown report and ADR renderers.

Keeping this separate from ``markdown.py``/``adr.py`` means both renderers
work from exactly the same recommendation/rejection view of the evaluation
results — there is only one place that decides "what was selected and why."
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel

from aura.architecture.generator import Candidate
from aura.domain.models import Workload
from aura.evaluation.engine import CandidateScore, select_recommendation
from aura.requirements.normalizer import NormalizedRequirements


class ReportContext(BaseModel):
    generated_at: str
    workload: Workload
    normalized: NormalizedRequirements
    candidates: list[Candidate]
    scores: list[CandidateScore]
    recommendation: CandidateScore | None
    recommended_candidate: Candidate | None
    rejected: list[CandidateScore]

    def candidate_by_id(self, candidate_id: str) -> Candidate:
        return next(c for c in self.candidates if c.id == candidate_id)

    def score_by_id(self, candidate_id: str) -> CandidateScore:
        return next(s for s in self.scores if s.candidate_id == candidate_id)


def build_context(
    workload: Workload,
    normalized: NormalizedRequirements,
    candidates: list[Candidate],
    scores: list[CandidateScore],
    *,
    generated_at: str | None = None,
) -> ReportContext:
    recommendation = select_recommendation(scores)
    recommended_candidate = (
        next(c for c in candidates if c.id == recommendation.candidate_id) if recommendation else None
    )
    rejected = [
        s for s in scores if not recommendation or s.candidate_id != recommendation.candidate_id
    ]

    return ReportContext(
        generated_at=generated_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        workload=workload,
        normalized=normalized,
        candidates=candidates,
        scores=scores,
        recommendation=recommendation,
        recommended_candidate=recommended_candidate,
        rejected=rejected,
    )
