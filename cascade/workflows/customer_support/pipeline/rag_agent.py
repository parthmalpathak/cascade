"""
RAG Agent — LangGraph node for retrieval-augmented generation.

Takes the classified query and intent, searches the FAISS knowledge base,
and returns grounded context for the response agent.
"""

from __future__ import annotations

import json
from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

from model_client import get_embeddings
from workflows.customer_support.pipeline.state import PipelineState

KB_PATH = Path(__file__).parent.parent / "data" / "knowledge_base"
DOCS_PATH = KB_PATH / "documents.json"

TOP_K = 4
DEFAULT_EMBEDDING_PROVIDER = "bedrock"
DEFAULT_EMBEDDING_MODEL_ID = "amazon.titan-embed-text-v1"

# Keyed by (embedding_provider, embedding_model_id) to support multiple providers
_vectorstore_cache: dict[tuple[str, str], FAISS] = {}


def _load_or_build_vectorstore(embedding_provider: str, embedding_model_id: str) -> FAISS:
    cache_key = (embedding_provider, embedding_model_id)
    if cache_key in _vectorstore_cache:
        return _vectorstore_cache[cache_key]

    embeddings = get_embeddings(embedding_provider, embedding_model_id)

    # Each provider+model gets its own index so embeddings don't collide
    safe_model = embedding_model_id.replace("/", "_").replace(".", "_")
    index_path = KB_PATH / f"faiss_index_{embedding_provider}_{safe_model}"

    if index_path.exists():
        vectorstore = FAISS.load_local(
            str(index_path),
            embeddings,
            allow_dangerous_deserialization=True,
        )
    else:
        with open(DOCS_PATH) as f:
            raw_docs = json.load(f)

        documents = [
            Document(
                page_content=d["content"],
                metadata={"id": d["id"], "category": d["category"], "title": d["title"]},
            )
            for d in raw_docs
        ]

        vectorstore = FAISS.from_documents(documents, embeddings)
        vectorstore.save_local(str(index_path))

    _vectorstore_cache[cache_key] = vectorstore
    return vectorstore


def retrieve_context(state: PipelineState) -> PipelineState:
    query = state["query"]
    intent = state.get("intent", "general")
    embedding_provider = state.get("embedding_provider", DEFAULT_EMBEDDING_PROVIDER)
    embedding_model_id = state.get("embedding_model_id", DEFAULT_EMBEDDING_MODEL_ID)

    vectorstore = _load_or_build_vectorstore(embedding_provider, embedding_model_id)

    results = vectorstore.similarity_search_with_score(
        query=f"[{intent}] {query}",
        k=TOP_K,
    )

    retrieved_docs = []
    retrieval_scores = []
    citations = []

    for doc, l2_distance in results:
        # FAISS returns L2 distances (lower = more similar). Convert to [0,1] similarity.
        similarity = round(1.0 / (1.0 + float(l2_distance)), 4)
        retrieved_docs.append({
            "content": doc.page_content,
            "title": doc.metadata.get("title", ""),
            "category": doc.metadata.get("category", ""),
            "doc_id": doc.metadata.get("id", ""),
            "score": similarity,
        })
        retrieval_scores.append(similarity)
        citations.append(doc.metadata.get("title", doc.metadata.get("id", "")))

    return {
        **state,
        "retrieved_docs": retrieved_docs,
        "retrieval_scores": retrieval_scores,
        "retrieval_query": f"[{intent}] {query}",
        "citations": citations,
    }
