# Cascade

**An open-source framework for benchmarking multi-agent LLM pipelines — and finding the best model for every stage.**

> *The layer between "we built an agent" and "we shipped an agent."*

---

## The Problem

Teams building multi-agent pipelines test end-to-end and call it done. But models don't fail uniformly — they fail at different stages for different reasons. GPT-4o might route perfectly and retrieve poorly. Claude might retrieve faithfully and over-refuse in response. An end-to-end pass rate hides all of this.

**Cascade surfaces it.**

---

## What Cascade Does

1. **Reads your pipeline** — you describe each agent in a manifest file. Cascade learns the role, input/output contract, and intent of every node in your workflow.
2. **Generates a test suite** — a Query Agent (Claude API, fixed) reads your manifests and auto-generates tailored bench tests: happy path, edge cases, adversarial prompts, compliance checks.
3. **You review** — the test suite is a JSON file. You read it, edit it, approve it. No run starts without your sign-off.
4. **Cascade benchmarks** — the eval runner fires every test through your pipeline with a given model combination, captures intermediate outputs at every agent node, and scores each stage independently.
5. **Swap models, re-run** — change the model for any agent and re-run. Scores accumulate into a leaderboard.
6. **Auto-run** — give Cascade a pool of models per agent and it runs all permutations automatically, with a cost estimate before it starts.

---

## The Key Insight: Errors Compound

A model with 89% accuracy at each of 3 stages produces ~72% end-to-end. The cascade effect is real and measurable. No existing benchmark shows this per-stage breakdown for multi-agent pipelines.

| Model | Routing | Retrieval | Response | Pipeline ★ | Compliance | Verdict |
|-------|---------|-----------|----------|------------|------------|---------|
| Claude 3.5 Sonnet | 94% | 88% | 91% | **82%** | 89% | SHIP |
| GPT-4o | 96% | 79% | 88% | **74%** | 81% | CONDITIONAL |
| Gemini 1.5 Pro | 89% | 85% | 83% | **72%** | 76% | CONDITIONAL |
| Llama 3 70B | 81% | 74% | 79% | **58%** | 61% | HOLD |

*Pipeline score = product of stage scores, not average. This is intentional.*

---

## Architecture

```
SETUP (run once)
  agent_manifest.json × N  ─┐
  workflow.yaml              ├──► Query Agent ──► task_suite_vN.json ──► Human Review
                             │   (Claude API, fixed)

BENCHMARK LOOP
  run_config.yaml (model per agent)
       │
       ▼
  Eval Runner ──► Pipeline (Agent 1 → Agent 2 → ... → Agent N)
                       (intermediate outputs captured at every node)
       │
       ▼
  Grader Agent ──► results/{run_id}/ ──► Dashboard (Streamlit, local)
  (Claude API, fixed)
```

---

## Reference Implementation

The `cascade/` directory contains a fully-functional 3-stage enterprise customer support pipeline:

```
Raw Query → [Routing Agent] → [RAG Agent] → [Response Agent] → Final Answer
```

- **Routing Agent** — classifies intent (billing, technical, policy, refund, escalation)
- **RAG Agent** — searches a FAISS knowledge base, returns grounded context
- **Response Agent** — synthesizes a customer-facing answer, manages tone and escalation

This pipeline is the proof-of-concept. Use it as a working example, or replace it with your own workflow.

---

## Bring Your Own Pipeline

Cascade is agent-agnostic. To benchmark your own multi-agent workflow:

1. Write an `agent_manifest.json` for each agent (see `cascade/manifests/` for examples)
2. Write a `workflow.yaml` declaring the agent chain and data flow
3. Run the Query Agent to generate your test suite
4. Configure `run_config.yaml` with your model choices
5. Run `cascade eval`

---

## Repo Structure

```
cascade/
├── manifests/           ← agent_manifest.json per agent (the plug-in contract)
├── workflow.yaml        ← declares agent chain and data flow
├── pipeline/            ← reference implementation (LangGraph + AWS Bedrock)
├── query_agent/         ← generates task_suite.json from manifests
├── tasks/               ← versioned test suites + schema spec
├── eval/                ← runner, grader, scorer, scheduler
├── results/             ← run outputs and leaderboard data (gitignored)
├── dashboard/           ← Streamlit leaderboard (local)
└── tests/               ← pytest unit tests
```

---

## V1 Scope

- Task Accuracy: Pass@1, Pass@3
- Safety Compliance: 3-tier battery (baseline / values-block / intervention)
- Manual run loop + auto-run with permutation scheduling
- Local Streamlit dashboard

Cost/latency benchmarking and rubric designer are V2.

---

## Stack

| Layer | Technology |
|-------|-----------|
| Agent orchestration | LangGraph |
| Model access | AWS Bedrock + OpenAI / Anthropic APIs |
| Query Agent + Grader | Anthropic API (Claude Sonnet, fixed) |
| Vector store | FAISS |
| Dashboard | Streamlit |

---

## Owner

[Parth Malpathak](mailto:parthmalpathak@gmail.com)

[Read the full PRD →](cascade/docs/PRD.md)
