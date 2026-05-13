"""
Cascade leaderboard — Streamlit dashboard.

Run: streamlit run dashboard/app.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

RESULTS_DIR = Path(__file__).parent.parent / "results"

_VERDICT_LABEL = {
    "SHIP": "✅ SHIP",
    "CONDITIONAL": "⚠️ CONDITIONAL",
    "HOLD": "🚫 HOLD",
}

st.set_page_config(page_title="Cascade Leaderboard", page_icon="🏆", layout="wide")


@st.cache_data(ttl=30)
def load_scorecards() -> list[dict]:
    cards = []
    for path in sorted(RESULTS_DIR.glob("*_scorecard.json"), reverse=True):
        try:
            with open(path) as f:
                cards.append(json.load(f))
        except Exception:
            pass
    return cards


def pct(v: float) -> str:
    return f"{v:.1%}"


# ── Header ────────────────────────────────────────────────────────────────────

st.title("🏆 Cascade — LLM Pipeline Benchmark Leaderboard")
st.caption("Agent-agnostic evaluation: routing accuracy · retrieval precision · response quality · compliance")

scorecards = load_scorecards()

if not scorecards:
    st.warning(
        "No scorecard results found in `results/`. "
        "Run `python -m eval.scheduler` to generate results."
    )
    st.stop()

# ── Leaderboard table ─────────────────────────────────────────────────────────

st.header("Leaderboard")

rows = []
for sc in scorecards:
    lb = sc.get("leaderboard_row", {})
    if not lb:
        continue
    rows.append({
        "Model": lb.get("model", "unknown"),
        "Routing": pct(lb.get("routing", 0.0)),
        "Retrieval": pct(lb.get("retrieval", 0.0)),
        "Response": pct(lb.get("response", 0.0)),
        "Pipeline": pct(lb.get("pipeline", 0.0)),
        "Compliance": pct(lb.get("compliance", 0.0)),
        "Verdict": _VERDICT_LABEL.get(lb.get("verdict", ""), lb.get("verdict", "")),
        "Run ID": sc.get("run_id", ""),
    })

st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

st.info(
    "**Pipeline score ≠ average of stage scores.** "
    "Errors compound: a model at 89% per stage produces ~72% end-to-end."
)

# ── Per-model drilldown ───────────────────────────────────────────────────────

st.divider()
st.header("Model Drilldown")

model_options = list(dict.fromkeys(sc["model"] for sc in scorecards))
selected = st.selectbox("Select model", options=model_options)
sc = next(s for s in scorecards if s["model"] == selected)
s = sc["summary"]

col1, col2, col3, col4 = st.columns(4)
col1.metric("Pipeline Composite", pct(s["pipeline_composite"]))
col2.metric("Compliance Score", pct(s["compliance_score"]))
col3.metric("Pass@1 Overall", pct(s["pass_at_1_overall"]))
col4.metric("Verdict", _VERDICT_LABEL.get(s["verdict"], s["verdict"]))

# Stage breakdown
st.subheader("Stage Breakdown")
stage_rows = [
    {
        "Stage": stage,
        "Mean Score": pct(data["mean_score"]),
        "Pass@1 Rate": pct(data["pass_at_1_rate"]),
        "Tasks": data["n_tasks"],
    }
    for stage, data in sorted(sc["stage_breakdown"].items())
]
st.dataframe(pd.DataFrame(stage_rows), use_container_width=True, hide_index=True)

# Intent breakdown
st.subheader("Intent Breakdown")
intent_rows = [
    {"Intent": intent, "Mean Score": pct(data["mean_score"]), "Tasks": data["n"]}
    for intent, data in sc["intent_breakdown"].items()
]
st.dataframe(pd.DataFrame(intent_rows), use_container_width=True, hide_index=True)

# Compliance breakdown
if sc.get("compliance_breakdown"):
    st.subheader("Compliance Tier Breakdown")
    comp_rows = [
        {"Tier": tier, "Mean Score": pct(data["mean_score"]), "Tasks": data["n"]}
        for tier, data in sc["compliance_breakdown"].items()
    ]
    st.dataframe(pd.DataFrame(comp_rows), use_container_width=True, hide_index=True)

st.caption(f"Run ID: `{sc['run_id']}` | Generated: {sc['generated_at']}")
