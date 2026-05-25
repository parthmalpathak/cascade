# Cascade — Reference Implementation

This directory contains all runnable code for Cascade: the Query Agent, eval stack, reference pipeline, and dashboard.

**Project overview and PRD:** [docs/PRD.md](docs/PRD.md)

---

## Prerequisites

- Python 3.11+
- `ANTHROPIC_API_KEY` — required for the Query Agent (task suite generation) and the LLM grader judge
- AWS credentials (`aws configure`) — required only if benchmarking with the **Bedrock provider**
- `OPENAI_API_KEY` — required only if benchmarking with the **OpenAI provider**

```bash
cp .env.example .env
# Fill in whichever keys apply to your run
```

---

## Quickstart

```bash
# Install dependencies
pip install -e .

# 1. Generate test suite (requires ANTHROPIC_API_KEY)
python -m query_agent.generator --workflow workflows/customer_support/workflow.yaml

# 2. Run benchmark — Anthropic API
python -m eval.runner \
  --workflow workflows/customer_support/workflow.yaml \
  --provider anthropic \
  --model claude-sonnet-4-6

# 2. Run benchmark — Bedrock (requires AWS credentials)
python -m eval.runner \
  --workflow workflows/customer_support/workflow.yaml \
  --provider bedrock \
  --model us.anthropic.claude-sonnet-4-6

# 3. Score and generate report
python -m eval.scorer
python -m eval.report

# 4. View leaderboard
streamlit run dashboard/app.py
```

To run all model combinations automatically:

```bash
python -m eval.scheduler --yes
```

---

## Repository Structure

```
cascade/
├── model_client.py             ← provider-agnostic LLM + embeddings (Anthropic / OpenAI / Bedrock)
├── requirements.txt
├── pyproject.toml
├── .env.example
│
├── docs/
│   ├── PRD.md                  ← product requirements doc
│   ├── PRD.html                ← rendered version
│   └── task_schema.md          ← task suite JSON schema reference
│
├── workflows/                  ← one subdirectory per pipeline
│   └── customer_support/       ← reference implementation
│       ├── workflow.yaml       ← agent chain definition
│       ├── manifests/          ← one JSON manifest per agent
│       ├── pipeline/           ← LangGraph implementation
│       │   ├── routing_agent.py
│       │   ├── rag_agent.py
│       │   ├── response_agent.py
│       │   ├── pipeline.py
│       │   └── state.py
│       └── data/
│           └── knowledge_base/ ← FAISS source documents
│
├── query_agent/
│   └── generator.py            ← generates task suite from workflow + manifests (Anthropic API)
│
├── eval/
│   ├── runner.py               ← fires tasks through pipeline, captures per-stage outputs
│   ├── grader.py               ← rule-based + LLM judge scoring per task
│   ├── scorer.py               ← Pass@k, pipeline composite, compliance scoring
│   ├── rubrics.py              ← single source of truth: PASS_THRESHOLD, DIMENSION_WEIGHTS, COMPLIANCE_WEIGHTS
│   ├── report.py               ← generates scorecard JSON + markdown
│   └── scheduler.py            ← orchestrates multi-model benchmark runs (parallel, checkpointed)
│
├── dashboard/
│   └── app.py                  ← Streamlit leaderboard
│
├── tasks/                      ← approved task suites (versioned, human-reviewed JSON)
├── results/                    ← run outputs and scorecards (gitignored)
└── tests/
    └── test_scorer.py          ← pytest unit tests (34 tests)
```

---

## Providers

Cascade supports three providers for pipeline inference:

| Provider | Flag | Models | Embeddings |
|---|---|---|---|
| Anthropic API | `--provider anthropic` | `claude-sonnet-4-6`, etc. | Not supported (use Bedrock or OpenAI) |
| AWS Bedrock | `--provider bedrock` | `us.anthropic.claude-sonnet-4-6`, etc. | `amazon.titan-embed-text-v1` |
| OpenAI | `--provider openai` | `gpt-4o`, `gpt-4-turbo`, etc. | `text-embedding-3-small` |

The **Query Agent** (task suite generator) and **LLM grader judge** always use the Anthropic API directly — `ANTHROPIC_API_KEY` is required regardless of which provider you benchmark against.

---

## Adding Your Own Workflow

Cascade is pipeline-agnostic. To benchmark your own workflow:

1. Create `workflows/<your-workflow>/workflow.yaml` — declare your agent chain
2. Create `workflows/<your-workflow>/manifests/<agent>.json` per agent — describe role, prompts, I/O schema
3. For **high-code pipelines** (LangGraph, custom Python): add a `pipeline/` directory with a `run_pipeline(query, task_id, model_config) -> dict` entrypoint and set `mode: high_code` in `workflow.yaml`
4. Run `python -m query_agent.generator --workflow workflows/<your-workflow>/workflow.yaml`
5. Review and approve the generated task suite
6. Run `python -m eval.runner --workflow workflows/<your-workflow>/workflow.yaml`

See `workflows/customer_support/` as the reference.

---

## Running Tests

```bash
pytest tests/ -v
```

All 34 tests should pass. Tests cover: routing scoring, retrieval scoring (including edge cases), coverage scoring, safety scoring, escalation scoring, composite calculation, and pass@k logic.

---

## Author

Parth Malpathak — [parthmalpathak@gmail.com](mailto:parthmalpathak@gmail.com)
