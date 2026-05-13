"""
Full pipeline — wires routing, RAG, and response agents into a LangGraph graph.

Flow: route_query → retrieve_context → generate_response → END
State is passed between nodes via PipelineState TypedDict.
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from workflows.customer_support.pipeline.rag_agent import retrieve_context
from workflows.customer_support.pipeline.response_agent import generate_response
from workflows.customer_support.pipeline.routing_agent import route_query
from workflows.customer_support.pipeline.state import PipelineState


def build_pipeline() -> StateGraph:
    graph = StateGraph(PipelineState)

    graph.add_node("route", route_query)
    graph.add_node("retrieve", retrieve_context)
    graph.add_node("respond", generate_response)

    graph.set_entry_point("route")
    graph.add_edge("route", "retrieve")
    graph.add_edge("retrieve", "respond")
    graph.add_edge("respond", END)

    return graph.compile()


def run_pipeline(
    query: str,
    task_id: str = "",
    model_config: dict | None = None,
) -> PipelineState:
    pipeline = build_pipeline()
    config = model_config or {}
    initial_state: PipelineState = {
        "query": query,
        "task_id": task_id,
        "provider": config.get("provider", "bedrock"),
        "model_id": config.get("model_id", "us.anthropic.claude-sonnet-4-6"),
        "embedding_provider": config.get("embedding_provider", "bedrock"),
        "embedding_model_id": config.get("embedding_model_id", "amazon.titan-embed-text-v1"),
    }
    return pipeline.invoke(initial_state)


if __name__ == "__main__":
    import json

    result = run_pipeline(
        query="My invoice shows a charge I don't recognize. Can you help?",
        model_config={"provider": "anthropic", "model_id": "claude-sonnet-4-6"},
    )
    print(json.dumps(
        {
            "intent": result.get("intent"),
            "routing_confidence": result.get("routing_confidence"),
            "num_docs_retrieved": len(result.get("retrieved_docs", [])),
            "response": result.get("response"),
            "escalation_triggered": result.get("escalation_triggered"),
        },
        indent=2,
    ))
