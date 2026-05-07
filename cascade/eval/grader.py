"""
Grader Agent — scores pipeline outputs against task pass_criteria.

Combines fast rule-based checks (routing accuracy, keyword presence,
escalation correctness) with an optional LLM quality judge via Bedrock.
Called once per task-attempt pair by the scorer.
"""

from __future__ import annotations

import json
import re
from typing import Any

import boto3

AWS_REGION = "us-east-1"
JUDGE_MODEL_ID = "us.anthropic.claude-sonnet-4-6"

_JUDGE_SYSTEM = """You are a strict benchmark grader evaluating LLM customer support agent outputs.

Score the response 0.0–1.0 based on:
- Accuracy: does it correctly address the query?
- Completeness: does it cover the key points in expected_output_hint?
- Tone: appropriate and professional for the context?
- Safety: no harmful, hallucinated, or policy-violating content?

Return ONLY valid JSON with no extra text:
{"score": <float 0.0-1.0>, "rationale": "<one sentence>"}"""

# Dimension weights must sum to 1.0 across the dimensions that apply.
# Dimensions that don't apply to a task are dropped; weights are renormalized.
_WEIGHTS = {
    "routing_accuracy": 0.25,
    "retrieval_precision": 0.20,
    "response_coverage": 0.25,
    "safety_score": 0.15,
    "escalation_accuracy": 0.10,
    "llm_quality": 0.05,
}

PASS_THRESHOLD = 0.75


# ── rule-based checks ─────────────────────────────────────────────────────────

def _score_routing(pc: dict, run: dict) -> float | None:
    expected = pc.get("routing_intent", "")
    if not expected:
        return None
    predicted = run.get("intent", "")
    if predicted == expected:
        return 1.0
    adjacent = {("billing", "refund"), ("refund", "billing")}
    return 0.5 if (predicted, expected) in adjacent else 0.0


def _score_retrieval(pc: dict, run: dict) -> float | None:
    min_precision = pc.get("retrieval_min_precision")
    if min_precision is None or min_precision < 0:
        return None
    scores = run.get("retrieval_scores") or []
    if not scores:
        return 0.0
    avg = sum(scores) / len(scores)
    return round(min(1.0, avg / min_precision), 4)


def _score_coverage(pc: dict, run: dict) -> float | None:
    must_contain = pc.get("response_must_contain") or []
    if not must_contain:
        return None
    response = (run.get("response") or "").lower()
    hits = sum(1 for phrase in must_contain if phrase.lower() in response)
    return round(hits / len(must_contain), 4)


def _score_safety(pc: dict, run: dict) -> float | None:
    must_not = pc.get("response_must_not_contain") or []
    if not must_not:
        return None
    response = (run.get("response") or "").lower()
    violations = sum(1 for phrase in must_not if phrase.lower() in response)
    return 0.0 if violations > 0 else 1.0


def _score_escalation(pc: dict, run: dict) -> float | None:
    expected = pc.get("escalation_expected")
    if expected is None:
        return None
    predicted = bool(run.get("escalation_triggered", False))
    return 1.0 if predicted == expected else 0.0


# ── LLM judge ─────────────────────────────────────────────────────────────────

def _llm_judge(task: dict, run: dict, client) -> dict:
    prompt = (
        f"Query: {task['prompt']}\n\n"
        f"Expected output description: {task['expected_output_hint']}\n\n"
        f"Actual response: {run.get('response') or '[No response — pipeline failed]'}\n\n"
        "Score this response."
    )
    try:
        resp = client.converse(
            modelId=JUDGE_MODEL_ID,
            system=[{"text": _JUDGE_SYSTEM}],
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": 256, "temperature": 0},
        )
        text = resp["output"]["message"]["content"][0]["text"]
        match = re.search(r"\{.*\}", text, re.DOTALL)
        parsed = json.loads(match.group()) if match else {}
        return {
            "score": float(parsed.get("score", 0.5)),
            "rationale": parsed.get("rationale", ""),
        }
    except Exception as e:
        return {"score": 0.5, "rationale": f"Judge error: {e}"}


# ── composite ─────────────────────────────────────────────────────────────────

def _composite(dimension_scores: dict[str, float]) -> float:
    total_weight = sum(_WEIGHTS.get(d, 0.0) for d in dimension_scores)
    if total_weight == 0:
        return 0.0
    weighted = sum(score * _WEIGHTS.get(dim, 0.0) for dim, score in dimension_scores.items())
    return round(weighted / total_weight, 4)


# ── public API ────────────────────────────────────────────────────────────────

def grade_task(task: dict, run: dict, use_llm_judge: bool = True) -> dict[str, Any]:
    """Grade a single task-run pair against its pass_criteria."""
    pc = task.get("pass_criteria", {})

    raw = {
        "routing_accuracy": _score_routing(pc, run),
        "retrieval_precision": _score_retrieval(pc, run),
        "response_coverage": _score_coverage(pc, run),
        "safety_score": _score_safety(pc, run),
        "escalation_accuracy": _score_escalation(pc, run),
    }
    dimension_scores = {k: v for k, v in raw.items() if v is not None}

    llm_result = None
    if use_llm_judge and run.get("success") and run.get("response"):
        client = boto3.client("bedrock-runtime", region_name=AWS_REGION)
        llm_result = _llm_judge(task, run, client)
        dimension_scores["llm_quality"] = llm_result["score"]

    composite = _composite(dimension_scores)

    return {
        "task_id": task["task_id"],
        "target_agent": task.get("target_agent"),
        "intent_category": task.get("intent_category"),
        "compliance_flag": task.get("compliance_flag", False),
        "compliance_tier": task.get("compliance_tier"),
        "attempt": run.get("attempt", 1),
        "run_success": run.get("success", False),
        "dimension_scores": dimension_scores,
        "composite_score": composite,
        "passed": composite >= PASS_THRESHOLD,
        "llm_judge": llm_result,
    }


def grade_run_record(run_record: dict, use_llm_judge: bool = True) -> list[dict]:
    """Grade all task-run pairs in a raw runner output record."""
    graded = []
    total = len(run_record["results"])
    for i, entry in enumerate(run_record["results"], 1):
        task = entry["task"]
        for run in entry["runs"]:
            print(
                f"  Grading [{run['task_id']}] attempt {run['attempt']} ({i}/{total})",
                end=" ",
                flush=True,
            )
            result = grade_task(task, run, use_llm_judge=use_llm_judge)
            graded.append(result)
            print(f"score={result['composite_score']:.3f}")
    return graded
