"""
pytest unit tests for the grader module.

Run from the cascade/ root:
    pytest tests/test_scorer.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the cascade root is on the path so eval.grader imports cleanly
sys.path.insert(0, str(Path(__file__).parent.parent))

from eval.grader import (
    _composite,
    _score_coverage,
    _score_escalation,
    _score_routing,
    _score_safety,
    grade_task,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _minimal_task(**overrides) -> dict:
    task = {
        "task_id": "t001",
        "target_agent": "routing_agent",
        "intent_category": "billing",
        "compliance_flag": False,
        "compliance_tier": None,
        "prompt": "What is my current invoice amount?",
        "expected_output_hint": "Provide the billing amount and payment due date.",
        "pass_criteria": {
            "routing_intent": "billing",
            "retrieval_min_precision": -1.0,
            "response_must_contain": [],
            "response_must_not_contain": [],
            "escalation_expected": False,
        },
    }
    task.update(overrides)
    return task


def _minimal_run(**overrides) -> dict:
    run = {
        "task_id": "t001",
        "attempt": 1,
        "success": True,
        "elapsed_seconds": 0.5,
        "error": None,
        "intent": "billing",
        "retrieval_scores": [],
        "response": "Your current invoice is $120.00, due on 15 June.",
        "escalation_triggered": False,
    }
    run.update(overrides)
    return run


# ── grade_task ────────────────────────────────────────────────────────────────

class TestGradeTask:
    def test_composite_in_range(self):
        result = grade_task(_minimal_task(), _minimal_run(), use_llm_judge=False)
        score = result["composite_score"]
        assert 0.0 <= score <= 1.0, f"composite_score out of range: {score}"

    def test_returns_required_keys(self):
        result = grade_task(_minimal_task(), _minimal_run(), use_llm_judge=False)
        for key in ("task_id", "composite_score", "passed", "dimension_scores", "attempt"):
            assert key in result, f"Missing key: {key}"

    def test_passed_flag_matches_threshold(self):
        from eval.rubrics import PASS_THRESHOLD
        result = grade_task(_minimal_task(), _minimal_run(), use_llm_judge=False)
        assert result["passed"] == (result["composite_score"] >= PASS_THRESHOLD)


# ── _composite ────────────────────────────────────────────────────────────────

class TestComposite:
    def test_single_dimension_full_score(self):
        # Only routing_accuracy (weight 0.25). Renormalized to weight 1.0 → score should equal input.
        score = _composite({"routing_accuracy": 1.0})
        assert score == 1.0

    def test_known_two_dimension_average(self):
        # routing_accuracy (0.25) = 1.0, retrieval_precision (0.20) = 0.0
        # weighted = 1.0*0.25 + 0.0*0.20 = 0.25; total_weight = 0.45
        expected = round(0.25 / 0.45, 4)
        score = _composite({"routing_accuracy": 1.0, "retrieval_precision": 0.0})
        assert score == expected

    def test_empty_returns_zero(self):
        assert _composite({}) == 0.0

    def test_all_dimensions_perfect(self):
        all_dims = {
            "routing_accuracy": 1.0,
            "retrieval_precision": 1.0,
            "response_coverage": 1.0,
            "safety_score": 1.0,
            "escalation_accuracy": 1.0,
            "llm_quality": 1.0,
        }
        assert _composite(all_dims) == 1.0


# ── _score_routing ────────────────────────────────────────────────────────────

class TestScoreRouting:
    def test_exact_match(self):
        pc = {"routing_intent": "billing"}
        run = {"intent": "billing"}
        assert _score_routing(pc, run) == 1.0

    def test_adjacent_billing_refund(self):
        pc = {"routing_intent": "refund"}
        run = {"intent": "billing"}
        assert _score_routing(pc, run) == 0.5

    def test_adjacent_refund_billing(self):
        pc = {"routing_intent": "billing"}
        run = {"intent": "refund"}
        assert _score_routing(pc, run) == 0.5

    def test_wrong_intent(self):
        pc = {"routing_intent": "billing"}
        run = {"intent": "technical"}
        assert _score_routing(pc, run) == 0.0

    def test_missing_expected_returns_none(self):
        pc = {}
        run = {"intent": "billing"}
        assert _score_routing(pc, run) is None

    def test_empty_routing_intent_returns_none(self):
        pc = {"routing_intent": ""}
        run = {"intent": "billing"}
        assert _score_routing(pc, run) is None


# ── _score_coverage ───────────────────────────────────────────────────────────

class TestScoreCoverage:
    def test_all_phrases_present(self):
        pc = {"response_must_contain": ["invoice", "payment"]}
        run = {"response": "Your invoice total and payment method are shown below."}
        assert _score_coverage(pc, run) == 1.0

    def test_half_phrases_present(self):
        pc = {"response_must_contain": ["invoice", "refund"]}
        run = {"response": "Please check your invoice."}
        assert _score_coverage(pc, run) == 0.5

    def test_no_phrases_match(self):
        pc = {"response_must_contain": ["credit card", "statement"]}
        run = {"response": "Thank you for contacting us."}
        assert _score_coverage(pc, run) == 0.0

    def test_empty_criteria_returns_none(self):
        pc = {"response_must_contain": []}
        run = {"response": "Hello"}
        assert _score_coverage(pc, run) is None

    def test_missing_criteria_returns_none(self):
        pc = {}
        run = {"response": "Hello"}
        assert _score_coverage(pc, run) is None


# ── _score_safety ─────────────────────────────────────────────────────────────

class TestScoreSafety:
    def test_no_violations(self):
        pc = {"response_must_not_contain": ["free money", "ignore policy"]}
        run = {"response": "We follow standard billing procedures."}
        assert _score_safety(pc, run) == 1.0

    def test_one_violation(self):
        pc = {"response_must_not_contain": ["free money"]}
        run = {"response": "We can give you free money as a credit."}
        assert _score_safety(pc, run) == 0.0

    def test_empty_must_not_returns_none(self):
        pc = {"response_must_not_contain": []}
        run = {"response": "Hello"}
        assert _score_safety(pc, run) is None


# ── _score_escalation ─────────────────────────────────────────────────────────

class TestScoreEscalation:
    def test_correct_escalation(self):
        pc = {"escalation_expected": True}
        run = {"escalation_triggered": True}
        assert _score_escalation(pc, run) == 1.0

    def test_correct_no_escalation(self):
        pc = {"escalation_expected": False}
        run = {"escalation_triggered": False}
        assert _score_escalation(pc, run) == 1.0

    def test_wrong_escalation(self):
        pc = {"escalation_expected": True}
        run = {"escalation_triggered": False}
        assert _score_escalation(pc, run) == 0.0

    def test_missing_criteria_returns_none(self):
        pc = {}
        run = {"escalation_triggered": True}
        assert _score_escalation(pc, run) is None
