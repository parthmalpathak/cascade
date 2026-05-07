# Cascade

**Agent-agnostic benchmarking for multi-stage LLM pipelines.**

Cascade answers one question before you ship an agent pipeline: *is this production-ready?* It auto-generates a tailored test suite from your agent definitions, runs systematic model experiments, and produces a per-stage leaderboard with a SHIP / CONDITIONAL / HOLD verdict.

Works for any pipeline — LangGraph code, ChatGPT Custom GPTs, Microsoft Copilot agents, or anything where agent instructions can be written to a manifest file.

**Documentation:** [PRD](docs/PRD.md)

---

## How It Works

```
1. Describe your agents    →  workflow.yaml + manifests/
2. Generate test suite     →  python -m query_agent.generator --workflow <path>
3. Run benchmark           →  python -m eval.runner --workflow <path>
4. View leaderboard        →  streamlit run dashboard/app.py
```

The **Query Agent** reads your workflow and agent manifests, then uses Claude via AWS Bedrock to generate a domain-appropriate test suite. The **eval stack** fires every task through your pipeline, scores each stage individually and end-to-end, and writes a scorecard JSON. The **dashboard** renders a leaderboard across model combinations.

The key insight: **pipeline score ≠ average of stage scores.** Errors compound. A model scoring 89% at each stage produces ~72% end-to-end. Cascade surfaces where the drops happen.

---

## Reference Pipeline

The repo ships with a fully working 3-stage customer support pipeline as the reference implementation:

```
Raw Query → [Routing Agent] → [RAG Agent] → [Response Agent] → Final Answer
```

| Agent | Role | Scored On |
|---|---|---|
| Routing Agent | Classifies intent into 5 categories | Classification accuracy, edge-case handling |
| RAG Agent | Retrieves grounded context from FAISS knowledge base | Retrieval precision, hallucination rate |
| Response Agent | Synthesizes context into customer-facing response | Response quality, tone, escalation accuracy |

---

## Quickstart

### Prerequisites
- Python 3.11+
- AWS account with Bedrock access (Claude Sonnet + Titan Embeddings)
- AWS credentials configured via `aws configure`

### Install

```bash
git clone https://github.com/parthmalpathak/cascade.git
cd cascade
pip install -r requirements.txt
cp .env.example .env
```

### Run the reference pipeline

```bash
# 1. Generate test suite (requires Bedrock access)
python -m query_agent.generator --workflow workflows/customer_support/workflow.yaml

# 2. Run benchmark
python -m eval.runner --workflow workflows/customer_support/workflow.yaml

# 3. View results
streamlit run dashboard/app.py
```

---

## Adding Your Own Workflow

Cascade is designed for any pipeline. You only need two things:

**1. A `workflow.yaml`** describing your agents and their chain:

```yaml
name: my-pipeline
mode: high_code          # high_code (bring your own pipeline/) or no_code
pipeline_entrypoint: "workflows.my_pipeline.pipeline.pipeline:run_pipeline"

agents:
  - id: agent_one
    manifest: manifests/agent_one.json
    position: 1
  - id: agent_two
    manifest: manifests/agent_two.json
    position: 2

chain:
  entry: agent_one
  flow:
    - from: agent_one
      to: agent_two
      passes: [field_a, field_b]
  terminal: agent_two
```

**2. A manifest JSON per agent** describing its role and contract:

```json
{
  "agent_id": "agent_one",
  "platform": "langgraph",
  "role_description": "What this agent does and why it matters.",
  "system_prompt": "The full system prompt — copied verbatim from your platform.",
  "input_schema": { "query": "string" },
  "output_schema": { "result": "string" },
  "constraints": ["Must return valid JSON"],
  "eval_focus": ["Accuracy on edge cases"]
}
```

For **no-code workflows** (Custom GPTs, Copilot agents): set `mode: no_code` and drop knowledge files in `data/`. No pipeline code needed — the Generic Agent Executor builds and runs equivalent agents from your manifests automatically.

For **high-code workflows** (LangGraph, custom Python): set `mode: high_code`, add your `pipeline/` directory with a `run_pipeline(query, task_id) -> dict` entry point.

Place your workflow under `workflows/<your-workflow-name>/` following the same structure as `workflows/customer_support/`.

---

## Repository Structure

```
cascade/
├── README.md
├── requirements.txt
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
│       ├── manifests/          ← one JSON per agent
│       ├── pipeline/           ← LangGraph implementation
│       └── data/
│           └── knowledge_base/ ← FAISS source documents
│
├── query_agent/
│   └── generator.py            ← generates task suite from workflow + manifests
│
├── eval/
│   ├── runner.py               ← fires tasks through pipeline, captures outputs
│   ├── scorer.py               ← Pass@k scoring logic
│   ├── grader.py               ← rule-based + LLM judge scoring per task
│   ├── rubrics.py              ← partial credit and compliance tier logic
│   ├── report.py               ← generates scorecard JSON / markdown
│   └── scheduler.py            ← orchestrates multi-model benchmark runs
│
├── dashboard/
│   └── app.py                  ← Streamlit leaderboard
│
├── tasks/                      ← approved task suites (versioned, human-reviewed)
│
└── results/                    ← raw run output (gitignored)
```

---

## Evaluation Pillars

**Pillar 1 — Task Accuracy**
- Pass@1: did the agent complete the task correctly on the first attempt?
- Pass@3: did it succeed within 3 attempts?
- Partial credit scoring with confidence intervals
- Measured per-stage and as a pipeline composite

**Pillar 2 — Safety / Compliance**
- 3-tier compliance battery: baseline / values-block / intervention
- Adversarial and edge-case prompt battery per stage
- Pipeline-level compliance score
- Verdict: SHIP / CONDITIONAL / HOLD

---

## Author

Parth Malpathak
