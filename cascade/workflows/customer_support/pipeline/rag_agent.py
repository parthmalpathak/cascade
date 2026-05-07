"""
RAG Agent — LangGraph node for retrieval-augmented generation.

Takes the classified query and intent, searches the FAISS knowledge base,
and returns grounded context for the response agent.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import boto3
import faiss
import numpy as np
from langchain_aws import BedrockEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

from workflows.customer_support.pipeline.state import PipelineState

KB_PATH = Path(__file__).parent.parent / "data" / "knowledge_base"
FAISS_INDEX_PATH = KB_PATH / "faiss_index"
DOCS_PATH = KB_PATH / "documents.json"

TOP_K = 4
_vectorstore: FAISS | None = None


def _get_embeddings() -> BedrockEmbeddings:
    client = boto3.client("bedrock-runtime", region_name="us-east-1")
    return BedrockEmbeddings(
        client=client,
        model_id="amazon.titan-embed-text-v1",
    )


def _load_or_build_vectorstore() -> FAISS:
    global _vectorstore
    if _vectorstore is not None:
        return _vectorstore

    embeddings = _get_embeddings()

    if FAISS_INDEX_PATH.exists():
        _vectorstore = FAISS.load_local(
            str(FAISS_INDEX_PATH),
            embeddings,
            allow_dangerous_deserialization=True,
        )
        return _vectorstore

    with open(DOCS_PATH) as f:
        raw_docs = json.load(f)

    documents = [
        Document(
            page_content=d["content"],
            metadata={"id": d["id"], "category": d["category"], "title": d["title"]},
        )
        for d in raw_docs
    ]

    _vectorstore = FAISS.from_documents(documents, embeddings)
    _vectorstore.save_local(str(FAISS_INDEX_PATH))
    return _vectorstore


def retrieve_context(state: PipelineState) -> PipelineState:
    query = state["query"]
    intent = state.get("intent", "general")

    vectorstore = _load_or_build_vectorstore()

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
