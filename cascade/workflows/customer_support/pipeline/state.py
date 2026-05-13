from typing import Any, Optional
from typing_extensions import TypedDict


class PipelineState(TypedDict, total=False):
    # Input
    query: str
    task_id: str

    # Model config (set by runner, consumed by pipeline agents)
    provider: str            # anthropic | openai | bedrock
    model_id: str            # e.g. claude-sonnet-4-6 / gpt-4o / us.anthropic.claude-sonnet-4-6
    embedding_provider: str  # bedrock | openai
    embedding_model_id: str  # e.g. amazon.titan-embed-text-v1 / text-embedding-3-small

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
