"""
Report generator — converts scored results into a human-readable scorecard.

Inputs:  *_scored.json from scorer
Outputs: *_scorecard.json, *_scorecard.md
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RESULTS_DIR = Path(__file__).parent.parent / "results"

_VERDICT_BADGE = {"SHIP": "✅ SHIP", "CONDITIONAL": "⚠️ CONDITIONAL", "HOLD": "🚫 HOLD"}


def _pct(v: float) -> str:
    return f"{v:.1%}"


def _overall_pass_at_1(task_scores: list[dict]) -> float:
    if not task_scores:
        return 0.0
    return round(sum(1 for t in task_scores if t["pass_at_1"]) / len(task_scores), 4)


def _intent_breakdown(task_scores: list[dict]) -> dict:
    by_intent: dict[str, list] = defaultdict(list)
    for t in task_scores:
        by_intent[t["intent_category"]].append(t["best_composite"])
    return {
        intent: {"mean_score": round(sum(s) / len(s), 4), "n": len(s)}
        for intent, s in sorted(by_intent.items())
    }


def _compliance_breakdown(task_scores: list[dict]) -> dict:
    compliance_tasks = [t for t in task_scores if t["compliance_flag"]]
    if not compliance_tasks:
        return {}
    by_tier: dict[str, list] = defaultdict(list)
    for t in compliance_tasks:
        by_tier[t.get("compliance_tier") or "baseline"].append(t["best_composite"])
    return {
        tier: {"mean_score": round(sum(s) / len(s), 4), "n": len(s)}
        for tier, s in sorted(by_tier.items())
    }


def _render_markdown(sc: dict) -> str:
    s = sc["summary"]
    verdict = s["verdict"]
    badge = _VERDICT_BADGE.get(verdict, verdict)

    lines = [
        f"# Cascade Scorecard — {sc['model']}",
        f"**Run ID:** `{sc['run_id']}` | **Generated:** {sc['generated_at']}",
        "",
        f"## Verdict: {badge}",
        "",
        "| Metric | Score |",
        "|--------|-------|",
        f"| Pipeline Composite | {_pct(s['pipeline_composite'])} |",
        f"| Compliance Score | {_pct(s['compliance_score'])} |",
        f"| Pass@1 Overall | {_pct(s['pass_at_1_overall'])} |",
        f"| Total Tasks | {s['total_tasks']} |",
        "",
        "## Stage Breakdown",
        "",
        "| Stage | Mean Score | Pass@1 Rate | Tasks |",
        "|-------|-----------|-------------|-------|",
    ]
    for stage, data in sorted(sc["stage_breakdown"].items()):
        lines.append(
            f"| {stage} | {_pct(data['mean_score'])} | {_pct(data['pass_at_1_rate'])} | {data['n_tasks']} |"
        )

    lines += [
        "",
        "## Intent Breakdown",
        "",
        "| Intent | Mean Score | Tasks |",
        "|--------|-----------|-------|",
    ]
    for intent, data in sc["intent_breakdown"].items():
        lines.append(f"| {intent} | {_pct(data['mean_score'])} | {data['n']} |")

    if sc.get("compliance_breakdown"):
        lines += [
            "",
            "## Compliance Tier Breakdown",
            "",
            "| Tier | Mean Score | Tasks |",
            "|------|-----------|-------|",
        ]
        for tier, data in sc["compliance_breakdown"].items():
            lines.append(f"| {tier} | {_pct(data['mean_score'])} | {data['n']} |")

    return "\n".join(lines) + "\n"


def generate_report(scored_path: Path) -> dict[str, Any]:
    with open(scored_path) as f:
        scored = json.load(f)

    task_scores = scored["task_scores"]
    scorecard = {
        "run_id": scored["run_id"],
        "model": scored["model_tag"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "pipeline_composite": scored["pipeline_composite"],
            "compliance_score": scored["compliance_score"],
            "verdict": scored["verdict"],
            "total_tasks": scored["total_tasks"],
            "pass_at_1_overall": _overall_pass_at_1(task_scores),
        },
        "stage_breakdown": scored["stage_scores"],
        "intent_breakdown": _intent_breakdown(task_scores),
        "compliance_breakdown": _compliance_breakdown(task_scores),
        "leaderboard_row": {
            "model": scored["model_tag"],
            "routing": scored["stage_scores"].get("routing_agent", {}).get("mean_score", 0.0),
            "retrieval": scored["stage_scores"].get("rag_agent", {}).get("mean_score", 0.0),
            "response": scored["stage_scores"].get("response_agent", {}).get("mean_score", 0.0),
            "pipeline": scored["pipeline_composite"],
            "compliance": scored["compliance_score"],
            "verdict": scored["verdict"],
        },
    }

    stem = scored_path.name.replace("_scored.json", "")
    json_path = scored_path.parent / f"{stem}_scorecard.json"
    md_path = scored_path.parent / f"{stem}_scorecard.md"

    with open(json_path, "w") as f:
        json.dump(scorecard, f, indent=2)
    md_path.write_text(_render_markdown(scorecard))

    print(f"Scorecard JSON → {json_path}")
    print(f"Scorecard MD   → {md_path}")
    return scorecard


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("scored_results", help="Path to *_scored.json from scorer")
    args = parser.parse_args()

    generate_report(Path(args.scored_results))
