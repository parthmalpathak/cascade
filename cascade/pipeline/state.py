from typing import Any, Optional
from typing_extensions import TypedDict


class PipelineState(TypedDict, total=False):
    # Input
    query: str
    task_id: str

    # Routing stage outputs
    intent: str
    routing_confidence: float
    routing_rationale: str
    routing_ambiguous: bool

    # RAG stage outputs
    retrieved_docs: list[dict[str, Any]]
    retrieval_scores: list[float]
    retrieval_query: str

    # Response stage outputs
    response: str
    response_tone: str
    escalation_triggered: bool
    citations: list[str]

    # Eval metadata (populated by runner)
    stage_outputs: dict[str, Any]
    error: Optional[str]
