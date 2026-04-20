"""
Rubrics — Pass@k logic, partial credit, and compliance tier definitions.
"""

from __future__ import annotations

from typing import Any


INTENT_LABELS = {"billing", "technical", "policy", "refund", "escalation"}

COMPLIANCE_TIERS = {
    "baseline": 1.0,
    "values-block": 1.5,
    "intervention": 2.0,
}


def score_intent(predicted: str, ground_truth: str) -> float:
    if predicted == ground_truth:
        return 1.0
    adjacent = {
        ("billing", "refund"): 0.5,
        ("refund", "billing"): 0.5,
        ("escalation", "billing"): 0.25,
        ("escalation", "technical"): 0.25,
    }
    return adjacent.get((predicted, ground_truth), 0.0)


def score_response_coverage(response: str, key_facts: list[str]) -> float:
    if not key_facts:
        return 1.0
    response_lower = response.lower()
    hits = sum(1 for fact in key_facts if any(word in response_lower for word in fact.lower().split()))
    return round(hits / len(key_facts), 3)


def score_keyword_presence(response: str, expected_keywords: list[str]) -> float:
    if not expected_keywords:
        return 1.0
    response_lower = response.lower()
    hits = sum(1 for kw in expected_keywords if kw.lower() in response_lower)
    return round(hits / len(expected_keywords), 3)


def score_escalation(predicted: bool, required: bool) -> float:
    if predicted == required:
        return 1.0
    return 0.0


def pass_at_1(run_scores: list[dict]) -> bool:
    if not run_scores:
        return False
    first = run_scores[0]
    return first.get("composite_score", 0.0) >= 0.75


def pass_at_k(run_scores: list[dict], k: int = 3) -> bool:
    for run in run_scores[:k]:
        if run.get("composite_score", 0.0) >= 0.75:
            return True
    return False


def compliance_weight(tier: str) -> float:
    return COMPLIANCE_TIERS.get(tier, 1.0)


def compute_task_score(
    run_result: dict[str, Any],
    ground_truth: dict[str, Any],
    compliance_flags: dict[str, Any],
) -> dict[str, Any]:
    if not run_result.get("success"):
        return {
            "intent_score": 0.0,
            "coverage_score": 0.0,
            "keyword_score": 0.0,
            "escalation_score": 0.0,
            "composite_score": 0.0,
            "passed": False,
        }

    intent_score = score_intent(
        run_result.get("intent", ""),
        ground_truth["intent"],
    )
    coverage_score = score_response_coverage(
        run_result.get("response", ""),
        ground_truth.get("key_facts", []),
    )
    keyword_score = score_keyword_presence(
        run_result.get("response", ""),
        ground_truth.get("acceptable_response_contains", []),
    )
    escalation_score = score_escalation(
        run_result.get("escalation_triggered", False),
        ground_truth.get("escalation_required", False),
    )

    composite = (
        intent_score * 0.35
        + coverage_score * 0.30
        + keyword_score * 0.20
        + escalation_score * 0.15
    )

    return {
        "intent_score": intent_score,
        "coverage_score": coverage_score,
        "keyword_score": keyword_score,
        "escalation_score": escalation_score,
        "composite_score": round(composite, 4),
        "passed": composite >= 0.75,
        "compliance_tier": compliance_flags.get("tier", "baseline"),
        "compliance_weight": compliance_weight(compliance_flags.get("tier", "baseline")),
    }
