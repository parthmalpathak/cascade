"""
Routing Agent — LangGraph node for intent classification.

Receives a raw customer query, classifies intent into one of five categories,
and returns a routing decision to pass downstream.
"""

from __future__ import annotations

import json

from model_client import invoke_llm
from workflows.customer_support.pipeline.state import PipelineState

SYSTEM_PROMPT = """You are a customer support routing agent. Your job is to classify the user's intent and route the query to the correct handler.

Classify the query into EXACTLY ONE of these intents:
- billing: questions about invoices, charges, payment methods, or account balances
- technical: product issues, bugs, error messages, or how-to questions
- policy: questions about terms of service, return policies, or company rules
- refund: explicit requests for money back or credit
- escalation: angry customers, legal threats, VIP customers, or unresolvable issues

Return a JSON object with exactly these fields:
{
  "intent": "<one of the five labels>",
  "confidence": <float 0.0–1.0>,
  "rationale": "<one sentence explaining the classification>",
  "ambiguous": <true|false>
}"""


def route_query(state: PipelineState) -> PipelineState:
    response_text = invoke_llm(
        provider=state.get("provider", "bedrock"),
        model_id=state.get("model_id", "us.anthropic.claude-sonnet-4-6"),
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": state["query"]}],
        max_tokens=512,
        temperature=0,
    )

    try:
        result = json.loads(response_text)
    except json.JSONDecodeError:
        result = {
            "intent": "escalation",
            "confidence": 0.0,
            "rationale": "Failed to parse routing response — defaulting to escalation.",
            "ambiguous": True,
        }

    return {
        **state,
        "intent": result["intent"],
        "routing_confidence": result["confidence"],
        "routing_rationale": result["rationale"],
        "routing_ambiguous": result.get("ambiguous", False),
    }
