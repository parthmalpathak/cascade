"""
Scheduler — orchestrates benchmark runs across multiple model configurations.

Reads a config YAML (or uses defaults), shows a cost/time estimate,
then runs runner → scorer → report for each model. Parallel workers.
Checkpoints to results/runs.jsonl so interrupted runs can be resumed.

Usage:
  python -m eval.scheduler                         # uses defaults
  python -m eval.scheduler --config auto_run.yaml  # custom config
  python -m eval.scheduler --yes                   # skip confirmation
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RESULTS_DIR = Path(__file__).parent.parent / "results"
CHECKPOINT_PATH = RESULTS_DIR / "runs.jsonl"

# Rough estimate: ~8s per task on Bedrock + ~3s LLM grading per task
_SECONDS_PER_TASK = 11

DEFAULT_CONFIG = {
    "models": [
        {"tag": "claude-sonnet-4-6", "model_id": "us.anthropic.claude-sonnet-4-6"},
    ],
    "pass_k": 1,
    "max_workers": 2,
    "use_llm_judge": True,
}


def _load_config(config_path: Path | None) -> dict:
    if config_path is None:
        return DEFAULT_CONFIG
    import yaml
    with open(config_path) as f:
        return yaml.safe_load(f)


def _completed_runs() -> set[tuple[str, str]]:
    """Return (model_tag, suite_version) pairs already in the checkpoint log."""
    if not CHECKPOINT_PATH.exists():
        return set()
    done = set()
    for line in CHECKPOINT_PATH.read_text().splitlines():
        if line.strip():
            entry = json.loads(line)
            done.add((entry["model_tag"], entry.get("suite_version", "")))
    return done


def _checkpoint(model_tag: str, run_id: str, verdict: str, suite_version: str) -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    with open(CHECKPOINT_PATH, "a") as f:
        f.write(
            json.dumps({
                "model_tag": model_tag,
                "run_id": run_id,
                "verdict": verdict,
                "suite_version": suite_version,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }) + "\n"
        )


def _run_one(
    model_config: dict,
    pass_k: int,
    task_suite_path: Path,
    use_llm_judge: bool,
) -> dict[str, Any]:
    # Deferred imports keep the main thread startup fast
    from eval.runner import run_suite
    from eval.scorer import score_run
    from eval.report import generate_report

    model_tag = model_config["tag"]
    print(f"\n[{model_tag}] Starting run...")

    raw_record = run_suite(
        pass_k=pass_k,
        model_tag=model_tag,
        task_suite_path=task_suite_path,
    )

    raw_path = RESULTS_DIR / f"{raw_record['run_id']}_{model_tag}_raw.json"
    scored = score_run(raw_path, use_llm_judge=use_llm_judge)

    scored_path = RESULTS_DIR / f"{raw_record['run_id']}_{model_tag}_scored.json"
    generate_report(scored_path)

    return {
        "model_tag": model_tag,
        "run_id": raw_record["run_id"],
        "verdict": scored["verdict"],
        "pipeline_composite": scored["pipeline_composite"],
        "compliance_score": scored["compliance_score"],
    }


def run_schedule(
    config_path: Path | None = None,
    task_suite_path: Path | None = None,
    skip_confirmation: bool = False,
) -> None:
    from eval.runner import load_tasks, _latest_task_suite

    config = _load_config(config_path)
    suite_path = task_suite_path or _latest_task_suite()
    suite_version = suite_path.stem  # e.g. "task_suite_v2"
    tasks = load_tasks(suite_path)

    models: list[dict] = config["models"]
    pass_k: int = config["pass_k"]
    max_workers: int = config["max_workers"]
    use_llm_judge: bool = config.get("use_llm_judge", True)

    done = _completed_runs()
    pending = [m for m in models if (m["tag"], suite_version) not in done]

    if not pending:
        print("All model combinations already completed. Check results/runs.jsonl.")
        return

    n_tasks = len(tasks)
    est_seconds = (n_tasks * pass_k * _SECONDS_PER_TASK * len(pending)) // max(max_workers, 1)
    est_minutes = max(1, est_seconds // 60)

    sep = "=" * 60
    print(f"\n{sep}")
    print("CASCADE AUTO-RUN SCHEDULE")
    print(sep)
    print(f"Task suite : {suite_path.name} ({n_tasks} tasks)")
    print(f"Models     : {[m['tag'] for m in pending]}")
    print(f"Pass@k     : {pass_k}  |  Workers: {max_workers}")
    print(f"LLM judge  : {'on' if use_llm_judge else 'off'}")
    print(f"Est. time  : ~{est_minutes} min")
    print(sep)

    if not skip_confirmation:
        confirm = input("\nProceed? [y/N] ").strip().lower()
        if confirm != "y":
            print("Aborted.")
            return

    RESULTS_DIR.mkdir(exist_ok=True)
    completed = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_run_one, model, pass_k, suite_path, use_llm_judge): model["tag"]
            for model in pending
        }
        for future in as_completed(futures):
            model_tag = futures[future]
            try:
                result = future.result()
                completed.append(result)
                _checkpoint(model_tag, result["run_id"], result["verdict"], suite_version)
                print(
                    f"\n[{model_tag}] Done — verdict: {result['verdict']} "
                    f"| pipeline: {result['pipeline_composite']:.1%} "
                    f"| compliance: {result['compliance_score']:.1%}"
                )
            except Exception as e:
                print(f"\n[{model_tag}] FAILED: {e}")

    print(f"\n{sep}")
    print("SCHEDULE COMPLETE")
    for r in completed:
        print(f"  {r['model_tag']}: {r['verdict']} ({r['pipeline_composite']:.1%})")
    print(sep)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, default=None, help="Path to auto_run_config.yaml")
    parser.add_argument("--task-suite", type=str, default=None, help="Path to task_suite_vN.json")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()

    run_schedule(
        config_path=Path(args.config) if args.config else None,
        task_suite_path=Path(args.task_suite) if args.task_suite else None,
        skip_confirmation=args.yes,
    )
