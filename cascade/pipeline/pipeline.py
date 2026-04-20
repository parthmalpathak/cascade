"""
Full pipeline — wires routing, RAG, and response agents into a LangGraph graph.

Flow: route_query → retrieve_context → generate_response → END
State is passed between nodes via PipelineState TypedDict.
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from pipeline.rag_agent import retrieve_context
from pipeline.response_agent import generate_response
from pipeline.routing_agent import route_query
from pipeline.state import PipelineState


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


def run_pipeline(query: str, task_id: str = "") -> PipelineState:
    pipeline = build_pipeline()
    initial_state: PipelineState = {"query": query, "task_id": task_id}
    return pipeline.invoke(initial_state)


if __name__ == "__main__":
    import json

    result = run_pipeline("My invoice shows a charge I don't recognize. Can you help?")
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
