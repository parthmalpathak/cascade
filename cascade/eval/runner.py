"""
Eval runner — fires each task through the pipeline and captures per-stage outputs.
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from pipeline.pipeline import run_pipeline
from pipeline.state import PipelineState

TASK_SUITE_PATH = Path(__file__).parent.parent / "tasks" / "task_suite.json"
RESULTS_DIR = Path(__file__).parent.parent / "results"


def load_tasks() -> list[dict]:
    with open(TASK_SUITE_PATH) as f:
        suite = json.load(f)
    return suite["tasks"]


def run_single_task(task: dict, attempt: int = 1) -> dict[str, Any]:
    task_id = task["id"]
    query = task["query"]

    start = time.time()
    try:
        state: PipelineState = run_pipeline(query=query, task_id=task_id)
        elapsed = time.time() - start
        return {
            "task_id": task_id,
            "attempt": attempt,
            "success": True,
            "elapsed_seconds": round(elapsed, 3),
            "intent": state.get("intent"),
            "routing_confidence": state.get("routing_confidence"),
            "routing_ambiguous": state.get("routing_ambiguous"),
            "num_docs_retrieved": len(state.get("retrieved_docs", [])),
            "retrieval_scores": state.get("retrieval_scores", []),
            "response": state.get("response"),
            "response_tone": state.get("response_tone"),
            "escalation_triggered": state.get("escalation_triggered"),
            "citations": state.get("citations", []),
            "error": None,
        }
    except Exception as e:
        elapsed = time.time() - start
        return {
            "task_id": task_id,
            "attempt": attempt,
            "success": False,
            "elapsed_seconds": round(elapsed, 3),
            "error": str(e),
        }


def run_suite(pass_k: int = 1, model_tag: str = "default") -> dict[str, Any]:
    tasks = load_tasks()
    results = []

    print(f"Running {len(tasks)} tasks × {pass_k} attempts each...")

    for task in tasks:
        task_results = []
        for attempt in range(1, pass_k + 1):
            print(f"  [{task['id']}] attempt {attempt}/{pass_k}", end=" ")
            result = run_single_task(task, attempt=attempt)
            task_results.append(result)
            print("OK" if result["success"] else f"ERROR: {result.get('error', '')}")
        results.append({
            "task": task,
            "runs": task_results,
        })

    run_record = {
        "run_id": datetime.utcnow().strftime("%Y%m%dT%H%M%SZ"),
        "model_tag": model_tag,
        "pass_k": pass_k,
        "total_tasks": len(tasks),
        "results": results,
    }

    RESULTS_DIR.mkdir(exist_ok=True)
    out_path = RESULTS_DIR / f"{run_record['run_id']}_{model_tag}.json"
    with open(out_path, "w") as f:
        json.dump(run_record, f, indent=2)

    print(f"\nResults saved to {out_path}")
    return run_record


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--pass-k", type=int, default=1)
    parser.add_argument("--model", type=str, default="claude-3-5-sonnet")
    args = parser.parse_args()

    run_suite(pass_k=args.pass_k, model_tag=args.model)
