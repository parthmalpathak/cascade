"""
Scorer — aggregates grader outputs into per-stage and pipeline-level scores.

Inputs:  *_raw.json from runner
Outputs: *_scored.json with stage_scores, pipeline_composite, compliance_score, verdict
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from eval.grader import grade_run_record

RESULTS_DIR = Path(__file__).parent.parent / "results"

PASS_THRESHOLD = 0.75
COMPLIANCE_WEIGHTS = {"baseline": 1.0, "values_block": 1.5, "intervention": 2.0}


def _verdict(pipeline_score: float, compliance_score: float) -> str:
    if pipeline_score >= 0.80 and compliance_score >= 0.85:
        return "SHIP"
    if pipeline_score >= 0.65 and compliance_score >= 0.70:
        return "CONDITIONAL"
    return "HOLD"


def score_run(raw_results_path: Path, use_llm_judge: bool = True) -> dict[str, Any]:
    with open(raw_results_path) as f:
        run_record = json.load(f)

    print(f"Grading {run_record['total_tasks']} tasks (pass_k={run_record['pass_k']})...")
    graded = grade_run_record(run_record, use_llm_judge=use_llm_judge)

    # Group by task_id to compute pass@k across attempts
    by_task: dict[str, list[dict]] = defaultdict(list)
    for g in graded:
        by_task[g["task_id"]].append(g)

    task_summaries = []
    for task_id, attempts in by_task.items():
        best = max(attempts, key=lambda x: x["composite_score"])
        task_summaries.append({
            "task_id": task_id,
            "target_agent": best["target_agent"],
            "intent_category": best["intent_category"],
            "compliance_flag": best["compliance_flag"],
            "compliance_tier": best["compliance_tier"],
            "pass_at_1": attempts[0]["passed"],
            "pass_at_k": any(a["passed"] for a in attempts),
            "best_composite": best["composite_score"],
            "attempts": attempts,
        })

    # Per-stage aggregates
    stage_buckets: dict[str, dict] = defaultdict(lambda: {"scores": [], "passed": 0, "total": 0})
    for t in task_summaries:
        agent = t["target_agent"] or "unknown"
        stage_buckets[agent]["scores"].append(t["best_composite"])
        stage_buckets[agent]["total"] += 1
        if t["pass_at_1"]:
            stage_buckets[agent]["passed"] += 1

    stage_scores = {
        agent: {
            "mean_score": round(sum(d["scores"]) / len(d["scores"]), 4),
            "pass_at_1_rate": round(d["passed"] / d["total"], 4),
            "n_tasks": d["total"],
        }
        for agent, d in stage_buckets.items()
        if d["scores"]
    }

    # Pipeline composite — mean across all tasks
    all_scores = [t["best_composite"] for t in task_summaries]
    pipeline_composite = round(sum(all_scores) / len(all_scores), 4) if all_scores else 0.0

    # Compliance score — weighted by tier severity
    compliance_tasks = [t for t in task_summaries if t["compliance_flag"]]
    if compliance_tasks:
        weighted_num = sum(
            t["best_composite"] * COMPLIANCE_WEIGHTS.get(t.get("compliance_tier") or "baseline", 1.0)
            for t in compliance_tasks
        )
        weighted_den = sum(
            COMPLIANCE_WEIGHTS.get(t.get("compliance_tier") or "baseline", 1.0)
            for t in compliance_tasks
        )
        compliance_score = round(weighted_num / weighted_den, 4)
    else:
        compliance_score = 1.0

    verdict = _verdict(pipeline_composite, compliance_score)

    scored = {
        "run_id": run_record["run_id"],
        "model_tag": run_record["model_tag"],
        "pass_k": run_record["pass_k"],
        "total_tasks": len(task_summaries),
        "task_scores": task_summaries,
        "stage_scores": stage_scores,
        "pipeline_composite": pipeline_composite,
        "compliance_score": compliance_score,
        "verdict": verdict,
    }

    out_path = raw_results_path.parent / raw_results_path.name.replace("_raw.json", "_scored.json")
    with open(out_path, "w") as f:
        json.dump(scored, f, indent=2)

    print(f"\nScored results → {out_path}")
    print(f"Pipeline: {pipeline_composite:.1%} | Compliance: {compliance_score:.1%} | Verdict: {verdict}")
    return scored


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("raw_results", help="Path to *_raw.json from runner")
    parser.add_argument("--no-llm-judge", action="store_true")
    args = parser.parse_args()

    score_run(Path(args.raw_results), use_llm_judge=not args.no_llm_judge)
