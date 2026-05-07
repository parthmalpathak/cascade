"""
Eval runner — fires each task through the pipeline and captures per-stage outputs.
"""

from __future__ import annotations

import importlib
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

CASCADE_ROOT = Path(__file__).parent.parent
TASKS_DIR = CASCADE_ROOT / "tasks"
RESULTS_DIR = CASCADE_ROOT / "results"
DEFAULT_WORKFLOW = CASCADE_ROOT / "workflows" / "customer_support" / "workflow.yaml"


def _load_workflow(workflow_path: Path) -> dict:
    with open(workflow_path) as f:
        return yaml.safe_load(f)


def _load_pipeline(workflow: dict):
    entrypoint = workflow.get("pipeline_entrypoint")
    if not entrypoint:
        raise NotImplementedError(
            "No pipeline_entrypoint in workflow.yaml. "
            "Generic Agent Executor for no_code workflows is not yet implemented."
        )
    module_path, func_name = entrypoint.rsplit(":", 1)
    module = importlib.import_module(module_path)
    return getattr(module, func_name)


def _latest_task_suite() -> Path:
    suites = sorted(TASKS_DIR.glob("task_suite_v*.json"))
    if not suites:
        raise FileNotFoundError(
            f"No task_suite_v*.json found in {TASKS_DIR}. "
            "Run: python -m query_agent.generator"
        )
    return suites[-1]


def load_tasks(path: Path | None = None) -> list[dict]:
    suite_path = path or _latest_task_suite()
    with open(suite_path) as f:
        data = json.load(f)
    return data if isinstance(data, list) else data["tasks"]


def run_single_task(
    task: dict,
    run_pipeline,
    attempt: int = 1,
) -> dict[str, Any]:
    task_id = task["task_id"]
    query = task["prompt"]

    start = time.time()
    try:
        state: dict = run_pipeline(query=query, task_id=task_id)
        elapsed = time.time() - start
        return {
            "task_id": task_id,
            "attempt": attempt,
            "success": True,
            "elapsed_seconds": round(elapsed, 3),
            "error": None,
            **{k: v for k, v in state.items() if k not in ("task_id",)},
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


def run_suite(
    pass_k: int = 1,
    model_tag: str = "default",
    task_suite_path: Path | None = None,
    workflow_path: Path = DEFAULT_WORKFLOW,
) -> dict[str, Any]:
    workflow = _load_workflow(workflow_path)
    run_pipeline = _load_pipeline(workflow)
    tasks = load_tasks(task_suite_path)

    print(f"Workflow: {workflow['name']}")
    print(f"Running {len(tasks)} tasks × {pass_k} attempts each...")

    results = []
    for task in tasks:
        task_results = []
        for attempt in range(1, pass_k + 1):
            print(f"  [{task['task_id']}] attempt {attempt}/{pass_k}", end=" ", flush=True)
            result = run_single_task(task, run_pipeline, attempt=attempt)
            task_results.append(result)
            print("OK" if result["success"] else f"ERROR: {result.get('error', '')}")
        results.append({"task": task, "runs": task_results})

    run_record = {
        "run_id": datetime.utcnow().strftime("%Y%m%dT%H%M%SZ"),
        "workflow": workflow["name"],
        "model_tag": model_tag,
        "pass_k": pass_k,
        "total_tasks": len(tasks),
        "results": results,
    }

    RESULTS_DIR.mkdir(exist_ok=True)
    out_path = RESULTS_DIR / f"{run_record['run_id']}_{model_tag}_raw.json"
    with open(out_path, "w") as f:
        json.dump(run_record, f, indent=2)

    print(f"\nRaw results saved to {out_path}")
    return run_record


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--pass-k", type=int, default=1)
    parser.add_argument("--model", type=str, default="claude-sonnet-4-6")
    parser.add_argument("--task-suite", type=str, default=None)
    parser.add_argument(
        "--workflow",
        type=str,
        default=str(DEFAULT_WORKFLOW),
        help="Path to workflow.yaml",
    )
    args = parser.parse_args()

    run_suite(
        pass_k=args.pass_k,
        model_tag=args.model,
        task_suite_path=Path(args.task_suite) if args.task_suite else None,
        workflow_path=Path(args.workflow),
    )
