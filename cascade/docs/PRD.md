# Cascade — Product Requirements Document

**Owner:** Parth Malpathak · parthmalpathak@gmail.com  
**Version:** 1.0 — April 2026  
**Status:** Draft

---

## 1. Executive Summary

### Problem Statement

Teams building multi-agent LLM pipelines have no systematic way to know whether a given model combination is production-ready — or which model performs best at each stage of their workflow. Evaluation today is ad hoc: a single end-to-end test that masks per-stage failure modes and gives no actionable signal about where to improve.

### Proposed Solution

Cascade is a local-first, agent-agnostic benchmarking framework. Describe your agents in manifest files, and Cascade auto-generates a tailored test suite, runs systematic model-combination experiments, and produces a per-stage leaderboard with a SHIP / CONDITIONAL / HOLD verdict. It works for any pipeline regardless of origin — LangGraph code, ChatGPT Custom GPTs, Microsoft Copilot agents, or any platform where agent instructions can be extracted to a manifest. The reference implementation is a 3-stage enterprise customer support pipeline (Routing → RAG → Response), built in LangGraph and shipped with the repo.

### Success Criteria

| Metric | Target | How Measured |
|--------|--------|-------------|
| Pipeline performance delta | ≥10% improvement in composite score between worst and best model combination found | Leaderboard run comparison |
| Leaderboard runs completed | ≥10 full benchmark runs across model combinations by end of V1 public release | `runs.jsonl` count |
| Onboarding time | A new user can plug in their own workflow and run a first benchmark in ≤30 minutes | Timed usability test |
| Task suite generation quality | ≥80% of Query Agent-generated tests pass human reviewer approval without edits | Review gate acceptance rate |
| Framework adoption | ≥3 external workflows successfully benchmarked by community users within 60 days of launch | GitHub issues / community reports |

---

## 2. User Experience & Functionality

### User Personas

| Persona | Role | Technical Level | Goal |
|---------|------|----------------|------|
| **The Deployer** | AI PM / ML engineer who owns a live multi-agent pipeline built in code (LangGraph, custom Python) | Comfortable with Python and LLM APIs; not a researcher | Wants to know: "Is my current model combination optimal? Where is my pipeline breaking?" |
| **The Migrator** | AI PM or ops lead who built a multi-agent workflow on a no-code platform (ChatGPT Custom GPTs, Microsoft Copilot Studio) and is locked into that platform's model choice | Can copy-paste agent instructions and export knowledge files; not writing pipeline code | Wants to evaluate: "Would this workflow perform better if I migrated to Claude or a different model combination?" |
| **The Learner** | Developer or PM new to multi-agent AI | Knows prompting; unfamiliar with eval frameworks | Wants to understand how model choice and hyperparameter tuning affect real pipeline outputs — uses the reference customer support pipeline as their sandbox |

---

### User Stories & Acceptance Criteria

#### Epic 1 — Plug In Your Workflow

**US-1.1** — As a Deployer or Migrator, I want to register my agent workflow by writing `agent_manifest.json` files so that Cascade understands my pipeline without requiring code changes.

*Acceptance Criteria:*
- [ ] A `agent_manifest.json` schema is documented with the following fields:
  - **Required:** `agent_id`, `role_description`, `input_schema`, `output_schema`
  - **Required for native execution:** `platform` (one of: `langgraph`, `chatgpt_custom_gpt`, `copilot_studio`, `custom`), `system_prompt` (full text — copied verbatim from the platform)
  - **Optional:** `knowledge_base_path` (directory of knowledge files — Cascade builds a FAISS index from these for native execution), `constraints`, `eval_focus`
  - **Code-based only:** `pipeline_entrypoint` (Python dotted path + function, e.g. `workflows.customer_support.pipeline.pipeline:run_pipeline`) — when set, Cascade delegates execution to this function instead of running natively; `system_prompt` in the manifest is then used only by the Query Agent for test generation context
- [ ] Cascade CLI validates the manifest on load and surfaces schema errors before any run starts
- [ ] A manifest with missing required fields produces a human-readable error, not a stack trace
- [ ] The reference customer support pipeline ships with pre-written manifests for all 3 agents as examples

**US-1.2** — As a Deployer, I want Cascade to understand how my agents are chained so that the Query Agent can generate coherent, workflow-aware tests.

*Acceptance Criteria:*
- [ ] A `workflow.yaml` file declares agent execution order and data flow between agents
- [ ] The Query Agent reads both the manifests and `workflow.yaml` before generating any tests
- [ ] Cascade correctly identifies the entry agent and terminal agent in any linear or branching workflow

---

#### Epic 2 — Test Suite Generation (Query Agent)

**US-2.1** — As a Deployer, I want the Query Agent to auto-generate a test suite tuned to my workflow so that I don't have to write 120 prompts by hand.

*Acceptance Criteria:*
- [ ] Query Agent generates a `task_suite.json` containing ≥30 test cases per agent (configurable)
- [ ] Each test case includes: `prompt`, `target_agent`, `intent_category`, `compliance_flag`, `expected_output_hint`
- [ ] Tests span at minimum 4 categories: happy path, edge case, adversarial/safety, ambiguous input
- [ ] Query Agent outputs a `task_suite_v{N}.json` with version increment on each regeneration — prior versions are preserved
- [ ] Generation completes in ≤3 minutes for a 3-agent workflow on Claude Sonnet

**US-2.2** — As a Deployer, I want to review and edit the generated test suite before any benchmark run starts so that I have full control over what gets tested.

*Acceptance Criteria:*
- [ ] After generation, Cascade prints: "Review `task_suite_v{N}.json` and press Enter to proceed, or `q` to abort"
- [ ] User can edit the JSON file freely before confirming — Cascade re-validates schema on confirm
- [ ] No benchmark run can start without explicit user confirmation of the task suite
- [ ] Cascade displays test count per agent and per category at the review prompt

---

#### Epic 3 — Benchmark Run Loop

**US-3.1** — As a Deployer, I want to run a benchmark against a specific model combination and see per-stage scores so that I can evaluate my current setup.

*Acceptance Criteria:*
- [ ] User specifies a model per agent in `run_config.yaml` before each run
- [ ] Eval runner fires all tasks through the full pipeline, capturing intermediate outputs at every agent node
- [ ] Each run produces a `scorecard_{run_id}.json` with: per-agent Pass@1, per-agent Pass@3, pipeline composite score, compliance tier pass rates, and overall verdict (SHIP / CONDITIONAL / HOLD)
- [ ] Run completes for 30 tasks across 3 agents in ≤10 minutes (non-auto-run mode)

**US-3.2** — As a Deployer, I want to iteratively swap models per agent and compare scores across runs so that I can converge on the optimal model combination.

*Acceptance Criteria:*
- [ ] After each run completes, Cascade prompts: "Change model for any agent? [y/n]" with current config displayed
- [ ] User can update any subset of agents' models without re-generating the task suite
- [ ] New run appends results to the leaderboard; prior run results are never overwritten
- [ ] Leaderboard displays all runs ranked by pipeline composite score

**US-3.3** — As a Deployer, I want an Auto-Run mode that tests all permutations of a selected model pool so that I don't have to manually iterate.

*Acceptance Criteria:*
- [ ] User defines a model pool per agent in `auto_run_config.yaml` (e.g., 3 models × 3 agents = 27 combinations)
- [ ] Before starting, Cascade displays: "X combinations × Y tests = Z API calls · Estimated cost: ~$N · Estimated time: ~T minutes. Confirm? [y/n]"
- [ ] Auto-run uses max-flow scheduling to distribute combinations across parallel workers (default: 3 workers, configurable)
- [ ] Checkpoint + resume: if auto-run is interrupted, restarting skips completed combinations (detected via `runs.jsonl`)
- [ ] Lite mode flag (`--lite`) runs 1 worker per combination and uses a reduced task suite (10 tasks per agent) for rapid spot-checking

---

#### Epic 4 — Grader Agent & Scoring

**US-4.1** — As a Deployer, I want the Grader Agent to automatically score each pipeline run so that I don't have to manually evaluate outputs.

*Acceptance Criteria:*
- [ ] Grader Agent scores every agent output on two pillars: Task Accuracy (Pass@1, Pass@3) and Safety Compliance (3-tier: baseline / values-block / intervention)
- [ ] Grader produces a numeric score (0.0–1.0) per test per agent, plus a compliance verdict per tier
- [ ] Pipeline composite score is computed as the product of per-stage scores (not average), surfacing the cascade compounding effect
- [ ] Grader outputs results to `results/{run_id}/grader_output.json` for dashboard ingestion

*Note: Rubric design (LLM-as-judge vs ground-truth matching) is an open V2 design decision — see Section 5.*

---

#### Epic 5 — Dashboard

**US-5.1** — As a Deployer, I want a local Streamlit dashboard that shows all my benchmark runs in a leaderboard so that I can compare model combinations at a glance.

*Acceptance Criteria:*
- [ ] Dashboard launches with `streamlit run dashboard/app.py` from the project root
- [ ] Leaderboard table shows: Model combination, per-agent scores, pipeline composite, compliance score, verdict
- [ ] Runs can be filtered by: workflow, date range, verdict (SHIP / CONDITIONAL / HOLD)
- [ ] Clicking a run shows the full scorecard: per-task pass/fail, compliance tier breakdown, per-agent drill-down
- [ ] Dashboard auto-refreshes when a new `grader_output.json` is written (polling interval: 5 seconds)
- [ ] "Export" button generates a self-contained HTML snapshot of the current leaderboard view for sharing

**US-5.2** — As a Learner, I want the dashboard to show me which stage of the pipeline is weakest for each model so that I understand where errors compound.

*Acceptance Criteria:*
- [ ] Dashboard includes a "Cascade Effect" view: bar chart showing per-stage score vs pipeline composite, illustrating error compounding
- [ ] View is available for any run, not just comparisons
- [ ] Weakest stage is highlighted in the leaderboard table

---

### Non-Goals (V1)

- **No cost/latency benchmarking** — model speed and API cost comparison are V2
- **No hosted / cloud deployment** — Cascade is local-only in V1; no shared leaderboard, no auth
- **No branching/parallel workflow support** — V1 supports linear agent chains only
- **No rubric designer UI** — grader rubric configuration is file-based only; no GUI
- **No model fine-tuning** — Cascade evaluates model inference only; no training loop
- **No mobile / responsive dashboard** — desktop browser only
- **No streaming eval results** — scores are written after a full run completes, not token-by-token
- **No replication of agent actions/plugins** — Cascade evaluates the LLM reasoning layer only; mid-conversation tool calls (ChatGPT plugin actions, Copilot Studio connectors, API integrations) are not executed in native mode; pipelines that rely heavily on external tool calls will produce lower-fidelity benchmark results

---

## 3. AI System Requirements

### Model & Tool Requirements

| Component | Model | Rationale |
|-----------|-------|-----------|
| **Query Agent** | Claude Sonnet (latest via Anthropic API) | Fixed — never swapped during benchmarking. Chosen for instruction-following quality in structured output generation. |
| **Grader Agent** | Claude Sonnet (latest via Anthropic API) | Fixed — must be consistent across all runs to avoid grader variance contaminating benchmark results. |
| **Pipeline Agents (reference impl.)** | Swappable: Claude 3.5 Sonnet, GPT-4o, Gemini 1.5 Pro, Llama 3 70B via AWS Bedrock | These are what Cascade benchmarks — the independent variable. |
| **Embeddings (RAG Agent)** | Amazon Titan Embed Text v1 via Bedrock | Fixed for the reference implementation; manifest-configurable for external workflows. |

### Pipeline Design

**Execution modes** — determined per-agent by the manifest:

- **Native mode (default):** Cascade constructs the agent from `system_prompt` + optional `knowledge_base_path` (FAISS-indexed on first run), then calls the model specified in `run_config.yaml` directly via Anthropic / OpenAI / Google AI API. This is how Migrators use Cascade — they copy their ChatGPT or Copilot agent instructions into the manifest, upload knowledge files, and Cascade runs the agent against different models without any code.
- **Entrypoint mode (code-based):** When `pipeline_entrypoint` is set in the manifest, Cascade dynamically imports and calls `run_pipeline(query: str, task_id: str) → dict` from the user's codebase. The manifest's `system_prompt` is used only by the Query Agent for test generation context; Cascade does not construct the agent itself. The reference customer support pipeline uses this mode.

**Platform limitation:** Native mode reconstructs the LLM reasoning layer only. Agent actions and mid-conversation tool calls (ChatGPT plugin actions, Copilot connectors) are not replicated. This is a known V1 constraint — see Non-Goals.

**Other constraints:**
- **Query Agent context budget**: Must fit full `workflow.yaml` + all `agent_manifest.json` files within a single Claude API call. Design constraint: total manifest + workflow YAML must not exceed 50k tokens.
- **Query Agent output format**: Structured JSON (`task_suite.json`) via tool use / structured output — no free-text parsing.
- **Grader Agent invocation**: Called once per agent output per task. Not called end-to-end — per-node scoring is the requirement.
- **Temperature**: Query Agent at 0.3 (creative enough for diverse tests, controlled enough for consistent structure). Grader Agent at 0 (deterministic scoring).

### Evaluation Strategy

| What Gets Evaluated | Method | Pass Target | Reviewer |
|--------------------|--------|-------------|----------|
| Task Accuracy — Pass@1 | Grader Agent score ≥ 0.7 on first attempt | ≥80% of tasks per agent | Automated |
| Task Accuracy — Pass@3 | Grader Agent score ≥ 0.7 on any of 3 attempts | ≥90% of tasks per agent | Automated |
| Safety Compliance — Baseline | No unsafe outputs on standard prompts | 100% | Automated |
| Safety Compliance — Values-block | Refuses or redirects adversarial prompts | ≥95% | Automated |
| Safety Compliance — Intervention | Escalates correctly on high-risk prompts | ≥90% | Automated |
| Query Agent test quality | % of generated tests approved without edits at human review gate | ≥80% | Human (Deployer) |

*Open question: Grader rubric design (LLM-as-judge vs ground-truth matching) — see Section 5, Open Questions.*

---

## 4. Technical Specifications

### Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│  SETUP PHASE (run once per workflow)                    │
│                                                         │
│  agent_manifest.json × N  ──┐                          │
│  workflow.yaml              ├──► Query Agent ──► task_suite_vN.json ──► Human Review Gate
│                             │   (Claude API, fixed)                         │
└─────────────────────────────┘                                               │
                                                                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  BENCHMARK RUN LOOP                                                         │
│                                                                             │
│  run_config.yaml (model per agent)                                          │
│       │                                                                     │
│       ▼                                                                     │
│  Eval Runner ──► Pipeline (Agent 1 → Agent 2 → ... → Agent N)              │
│       │              (intermediate outputs captured at every node)          │
│       ▼                                                                     │
│  Grader Agent ──► grader_output.json ──► runs.jsonl (checkpoint log)       │
│  (Claude API, fixed)                         │                              │
│                                              ▼                              │
│                                     Dashboard (Streamlit)                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Auto-Run Mode:**
```
auto_run_config.yaml (model pool per agent)
    │
    ▼
Permutation Generator ──► Cost/time estimate ──► User confirmation
    │
    ▼
Max-Flow Scheduler (N workers, configurable)
    │
    ├──► Worker 1: combination [A1-ModelX, A2-ModelY, A3-ModelZ]
    ├──► Worker 2: combination [A1-ModelX, A2-ModelY, A3-ModelW]
    └──► Worker N: ...
         (each worker appends to runs.jsonl on completion)
         (restart scans runs.jsonl to skip completed combinations)
```

### Integration Points

| Component | Integration | Details |
|-----------|------------|---------|
| Query Agent | Anthropic API | Claude Sonnet, tool use / structured output mode |
| Grader Agent | Anthropic API | Claude Sonnet, temperature 0 |
| Reference pipeline (entrypoint mode) | AWS Bedrock | Claude, GPT-4o (via Bedrock), Titan Embed |
| Native mode — model APIs | Anthropic API, OpenAI API, Google AI API | Swappable per-agent via `run_config.yaml` model ID |
| ChatGPT Custom GPTs | User provides: system prompt (copy-paste) + knowledge files (upload) | Cascade runs in native mode — no ChatGPT API access required |
| Microsoft Copilot Studio | User provides: agent instructions (copy-paste) + knowledge files (export) | Cascade runs in native mode — no Copilot API access required |
| Vector store (native mode) | FAISS (local) | Index built from `knowledge_base_path` on first run, cached locally |
| Dashboard | Streamlit (local) | Reads from `results/` directory, 5s polling |

### File Structure

```
cascade/
├── README.md
├── requirements.txt
├── .env.example
│
├── docs/
│   ├── PRD.md                     ← this document
│   ├── PRD.html                   ← rendered version
│   └── task_schema.md             ← task suite JSON schema reference
│
├── workflows/                     ← one subdirectory per pipeline
│   └── customer_support/          ← reference implementation (LangGraph, high-code)
│       ├── workflow.yaml          ← agent chain + pipeline_entrypoint declaration
│       ├── manifests/             ← one JSON per agent
│       │   ├── routing_agent.json
│       │   ├── rag_agent.json
│       │   └── response_agent.json
│       ├── pipeline/              ← LangGraph implementation (high_code only)
│       │   ├── routing_agent.py
│       │   ├── rag_agent.py
│       │   ├── response_agent.py
│       │   ├── pipeline.py
│       │   └── state.py
│       └── data/
│           └── knowledge_base/
│               └── documents.json
│
├── query_agent/
│   └── generator.py               ← reads workflow.yaml + manifests, generates task_suite_vN.json
│
├── tasks/                         ← approved task suites (versioned, human-reviewed)
│
├── eval/
│   ├── runner.py                  ← dynamically loads pipeline via workflow_entrypoint, fires tasks
│   ├── grader.py                  ← rule-based + LLM judge scoring per task
│   ├── scorer.py                  ← Pass@k logic, compliance tiers
│   ├── rubrics.py                 ← scoring rubric definitions
│   ├── scheduler.py               ← orchestrates multi-model benchmark runs
│   └── report.py                  ← generates scorecard JSON / markdown
│
├── results/                       ← raw run output (gitignored)
│
└── dashboard/
    └── app.py                     ← Streamlit leaderboard
```

### Security & Privacy

- **Local-only execution**: No data leaves the machine in V1. All run results, task suites, and model outputs are stored locally.
- **API key management**: Anthropic and AWS credentials via environment variables only — never hardcoded, never logged.
- **No PII in reference task suite**: The 120-prompt customer support task suite uses synthetic data only.
- **Compliance**: No GDPR / HIPAA / SOC 2 requirements in V1 (local tool, no user data storage). External workflow users are responsible for their own data classification.

### Performance Requirements

| Operation | Target | Notes |
|-----------|--------|-------|
| Task suite generation (Query Agent) | ≤3 min for 3-agent workflow, 30 tasks/agent | Single Claude API call per agent |
| Single benchmark run (manual mode) | ≤10 min for 30 tasks × 3 agents | Sequential execution |
| Auto-run (3 workers, 27 combinations) | ≤4 hours for full permutation sweep | Parallelized via max-flow scheduler |
| Dashboard load time | ≤3 seconds on first open | Local Streamlit, reads from `results/` |
| Dashboard refresh on new run | ≤10 seconds | 5s polling + render |

---

## 5. Risks

### Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Query Agent generates low-quality tests (too generic, misses agent intent) | Medium | High — bad tests make the whole benchmark meaningless | Human review gate is mandatory; track approval rate metric; iterate on Query Agent prompt if <80% pass rate |
| Grader Agent inconsistency across runs (same output, different score) | Medium | High — contaminates leaderboard comparisons | Grader temperature fixed at 0; pin model version; add grader regression tests |
| Permutation explosion causes runaway API costs | Medium | Medium — frustrating but recoverable | Cost estimate preview + mandatory confirmation before auto-run; Lite mode for spot-checking |
| AWS Bedrock rate limits throttle auto-run workers | Medium | Medium — slows benchmark, doesn't break it | Configurable worker count; exponential backoff in runner; checkpoint/resume means no lost work |
| agent_manifest.json schema too rigid — users can't describe their agents accurately | Low | High — blocks framework adoption | Ship schema with 3 real examples; accept `extra_fields` passthrough; gather feedback in V1.1 |
| LangGraph state passing breaks between agent nodes | Low | Medium — breaks reference impl. | Existing pipeline already working; add integration test that asserts state keys at each node |

---

### Open Questions

| # | Question | Owner | Blocking? | Target Resolution |
|---|----------|-------|-----------|------------------|
| OQ-1 | **Grader rubric design**: LLM-as-judge with no ground truth, or Query Agent also generates expected outputs + rubric per test? | Parth | No (V2) | V1.1 design session |
| OQ-2 | **Dashboard hosting V2**: Will the leaderboard ever be public/shareable? If yes, need auth + backend. | Parth | No | V2 scoping |
| OQ-3 | **Workflow.yaml schema**: What's the minimum representation needed for branching/conditional workflows? Linear is V1, but schema should not foreclose V2. | Parth | Soft — affects schema design | Before V1 code freeze |
| OQ-4 | **Query Agent model lock**: If Anthropic deprecates the pinned Claude Sonnet version, what's the re-validation process to ensure test quality doesn't regress? | Parth | No | Ongoing |
| OQ-5 | **Grader Agent as separate process vs inline**: Should the Grader run synchronously in the eval loop or as a post-processing step? Async is faster; sync gives live score feedback. | Parth | Yes — affects runner architecture | Before V1 build starts |

---

*Cascade V1.0 PRD — Parth Malpathak · April 2026*
