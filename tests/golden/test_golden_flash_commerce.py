"""Golden-file test (docs/TESTING.md): the decision for flash-commerce.yaml
must be stable across runs. This intentionally captures the *decision*
(eligibility, ranking, recommendation) rather than every nested field, so it
stays meaningful without becoming a brittle pin on incidental formatting.
"""

from __future__ import annotations

import json
from pathlib import Path

from aura.architecture.generator import generate_candidates
from aura.domain.models import Workload
from aura.evaluation.engine import evaluate_all, select_recommendation
from aura.requirements.loader import load_workload_document
from aura.requirements.normalizer import normalize

GOLDEN_DIR = Path(__file__).parent
EXPECTED_PATH = GOLDEN_DIR / "flash_commerce.expected.json"


def _decision_summary() -> dict:
    repo_root = Path(__file__).resolve().parent.parent.parent
    document = load_workload_document(repo_root / "config" / "flash-commerce.yaml")
    workload = Workload.model_validate(document)
    normalized = normalize(workload, raw_document=document)
    candidates = generate_candidates(normalized)
    scores = evaluate_all(candidates, normalized)
    recommendation = select_recommendation(scores)

    return {
        "recommendation": recommendation.candidate_id if recommendation else None,
        "candidates": [
            {
                "candidate_id": s.candidate_id,
                "eligibility": s.eligibility.value,
                "weighted_score": s.weighted_score,
            }
            for s in scores
        ],
    }


def test_flash_commerce_decision_is_stable():
    actual = _decision_summary()
    expected = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))
    assert actual == expected


def test_flash_commerce_decision_is_deterministic_across_runs():
    assert _decision_summary() == _decision_summary()
