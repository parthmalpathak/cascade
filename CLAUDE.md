# AgentBench — Project Brief for Claude Code

## What This Is

An open-source LLM agent evaluation framework. The goal is to answer one question before shipping any enterprise agent pipeline: **is this production-ready?**

No existing tool does this end-to-end for multi-stage agent pipelines with PM-readable output. AgentBench is that tool.

---

## The Core Idea

We are building and benchmarking a **3-stage enterprise customer support pipeline** — three LangGraph agents chained together:

```
Raw Query → [Routing Agent] → [RAG Agent] → [Response Agent] → Final Answer
```

AgentBench wraps around this pipeline, fires a task suite of 120 prompts through it, scores every stage individually AND end-to-end, and produces a scorecard + public leaderboard comparing GPT-4o, Claude, Gemini, and open-source models.

The key insight: **models don't fail uniformly — they fail at different stages.** GPT-4o might route perfectly but hallucinate in retrieval. Claude might retrieve faithfully but over-refuse in response. The leaderboard surfaces this. Nothing public does this today.

---

## The Three Agents

### Agent 1 — Routing Agent
- **What it does:** Receives a raw customer query. Classifies intent (billing, technical, policy, refund, escalation). Routes to the correct downstream handler.
- **Why it matters:** First decision gate. Mis-routing at this stage corrupts everything downstream.
- **Scored on:** Classification accuracy, edge-case mis-route rate, ambiguous query handling.

### Agent 2 — RAG Agent
- **What it does:** Takes the classified, routed query. Searches a knowledge base (policy docs, FAQs, product info). Returns grounded context.
- **Why it matters:** This is where hallucination either gets prevented or introduced. Retrieval quality determines response faithfulness.
- **Scored on:** Retrieval precision, faithfulness to source, hallucination rate.

### Agent 3 — Response Agent
- **What it does:** Synthesizes retrieved context into a final customer-facing response. Manages tone, completeness, escalation decision, safe output.
- **Why it matters:** The most visible layer — but its quality is entirely dependent on stages 1 and 2.
- **Scored on:** Response quality, tone appropriateness, escalation accuracy, safety compliance.

---

## V1 Scope — Two Evaluation Pillars Only

**Pillar 1 — Task Accuracy**
- Pass@1: did the agent complete the task correctly on the first try?
- Pass@3: did it succeed in 3 attempts?
- Partial credit scoring with confidence intervals
- Measured per-stage AND as a pipeline composite

**Pillar 2 — Values / Safety Compliance**
- 3-tier compliance battery (baseline / values-block / intervention)
- Adversarial and edge-case prompt battery per stage
- Cumulative pipeline compliance score
- Verdicts: SHIP / CONDITIONAL / HOLD

**Not in V1:** cost/latency comparison, failure mode taxonomy. Those are V2.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Agent orchestration | LangGraph |
| Model access | AWS Bedrock (Claude, Titan; also swap in OpenAI / Gemini via API) |
| Vector store | FAISS |
| Eval runner | Python |
| Scoring engine | Python (custom rubric logic) |
| Task suite storage | JSON |
| Dashboard / leaderboard | Streamlit |
| Version control | GitHub (open source from day 1) |

---

## File Structure to Build Towards

```
agentbench/
├── CLAUDE.md                  ← this file
├── README.md                  ← public-facing, goes on GitHub
├── PRD.md                     ← product requirements doc, also public
│
├── pipeline/
│   ├── routing_agent.py       ← LangGraph node: intent classification
│   ├── rag_agent.py           ← LangGraph node: retrieval
│   ├── response_agent.py      ← LangGraph node: generation
│   └── pipeline.py            ← wires all 3 nodes into the full graph
│
├── eval/
│   ├── runner.py              ← fires task suite through pipeline, captures per-stage outputs
│   ├── scorer.py              ← Task Accuracy + Compliance scoring logic
│   ├── rubrics.py             ← Pass@k logic, partial credit, compliance tiers
│   └── report.py             ← generates scorecard JSON / markdown
│
├── tasks/
│   ├── task_suite.json        ← 120 prompts with ground truth + compliance flags
│   └── schema.md              ← task format spec
│
├── dashboard/
│   └── app.py                 ← Streamlit leaderboard
│
└── tests/
    └── test_scorer.py         ← pytest unit tests for scoring logic
```

---

## What to Build First

Start here, in order:

1. **`pipeline/routing_agent.py`** — the simplest node. Build the intent classifier. Test it manually with 10 prompts before moving on.
2. **`pipeline/rag_agent.py`** — build the retrieval node. Use a small set of mock documents first (10–20 FAQ entries as a JSON knowledge base). FAISS index over them.
3. **`pipeline/response_agent.py`** — the generation node. Takes context from RAG, generates response.
4. **`pipeline/pipeline.py`** — wire all 3 together as a LangGraph graph with state passing between nodes.
5. **`tasks/task_suite.json`** — once the pipeline runs end-to-end, write 30 task prompts manually (billing, technical, policy, edge cases). Add ground truth + compliance flag per task. Scale to 120 after scoring logic is proven.
6. **`eval/runner.py`** — fires each task through the pipeline, captures outputs at each node.
7. **`eval/scorer.py`** — implement Pass@1 first. Get numbers. Then add Pass@3 and compliance tiers.
8. **`dashboard/app.py`** — Streamlit leaderboard. Build this last, after you have real numbers.

---

## The Leaderboard Story (What We're Building Towards)

The public output looks like this:

| Model | Routing | Retrieval | Response | Pipeline | Compliance | Verdict |
|-------|---------|-----------|----------|----------|------------|---------|
| Claude 3.5 Sonnet | 94% | 88% | 91% | 82% | 89% | SHIP |
| GPT-4o | 96% | 79% | 88% | 74% | 81% | CONDITIONAL |
| Gemini 1.5 Pro | 89% | 85% | 83% | 72% | 76% | CONDITIONAL |
| Llama 3 70B | 81% | 74% | 79% | 58% | 61% | HOLD |

The finding that drives inbound: **pipeline score ≠ average of stage scores.** Errors compound. A model with 89% at each stage produces ~72% end-to-end. No existing benchmark shows this.

---

## What This Project Proves

- End-to-end PM process: public PRD → discovery → build → ship → iterate
- Hands-on foundational model work: LangGraph + Bedrock, written by hand
- Evaluation thinking: the core skill of AI PMs at FAANG companies
- Public, verifiable artifact: any hiring manager can look at the GitHub and the leaderboard

---

## Owner

Parth Malpathak — parthmalpathak@gmail.com  
Background: 3+ years building and governing enterprise AI agents at Cummins Inc. (20+ agents, 3,000+ users, AI compliance framework 48.5% → 91.7%). This project generalizes that experience into an open, reproducible framework.
