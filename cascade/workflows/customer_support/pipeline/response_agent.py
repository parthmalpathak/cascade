"""
Response Agent — LangGraph node for final answer synthesis.

Takes the routed intent and retrieved context, generates a customer-facing
response with appropriate tone, completeness, and escalation decision.
"""

from __future__ import annotations

import json

from model_client import invoke_llm
from workflows.customer_support.pipeline.state import PipelineState

SYSTEM_PROMPT = """You are a professional customer support agent. Using the provided context documents, generate a helpful, accurate, and appropriately-toned response to the customer query.

Rules:
1. Ground your answer ONLY in the provided context. Do not hallucinate.
2. If the context does not contain enough information, say so honestly.
3. Match tone to the situation: professional for billing/policy, empathetic for refunds, calm-but-urgent for escalations.
4. Be concise — aim for 2–4 sentences unless complexity requires more.
5. Set escalation_triggered to true if: the customer is hostile, the issue is unresolvable via policy, or legal action is mentioned.

Return a JSON object with exactly these fields:
{
  "response": "<customer-facing response text>",
  "tone": "<professional|empathetic|urgent|neutral>",
  "escalation_triggered": <true|false>,
  "completeness": <float 0.0–1.0>,
  "grounded": <true|false>
}"""


def _format_context(docs: list[dict]) -> str:
    if not docs:
        return "No relevant documents found."
    parts = []
    for i, doc in enumerate(docs, 1):
        parts.append(f"[{i}] {doc['title']}\n{doc['content']}")
    return "\n\n".join(parts)


def generate_response(state: PipelineState) -> PipelineState:
    context = _format_context(state.get("retrieved_docs", []))
    intent = state.get("intent", "general")

    user_message = (
        f"Intent: {intent}\n\n"
        f"Customer Query: {state['query']}\n\n"
        f"Context Documents:\n{context}\n\n"
        "Generate the response."
    )

    response_text = invoke_llm(
        provider=state.get("provider", "bedrock"),
        model_id=state.get("model_id", "us.anthropic.claude-sonnet-4-6"),
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
        max_tokens=1024,
        temperature=0.1,
    )

    try:
        result = json.loads(response_text)
    except json.JSONDecodeError:
        result = {
            "response": response_text,
            "tone": "neutral",
            "escalation_triggered": False,
            "completeness": 0.5,
            "grounded": False,
        }

    return {
        **state,
        "response": result["response"],
        "response_tone": result.get("tone", "neutral"),
        "escalation_triggered": result.get("escalation_triggered", False),
    }
