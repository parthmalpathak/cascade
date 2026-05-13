"""
Model Client — provider-agnostic LLM and embeddings interface.

Supported providers:
  - anthropic  : Anthropic API (claude-* models)
  - openai     : OpenAI API (gpt-* models)
  - bedrock    : AWS Bedrock (cross-region inference profiles)

Usage:
  from model_client import invoke_llm, get_embeddings

  text = invoke_llm(
      provider="anthropic",
      model_id="claude-sonnet-4-6",
      system="You are helpful.",
      messages=[{"role": "user", "content": "Hello"}],
  )

  embeddings = get_embeddings(provider="bedrock", model_id="amazon.titan-embed-text-v1")
"""

from __future__ import annotations

import os
from typing import Any


def invoke_llm(
    provider: str,
    model_id: str,
    messages: list[dict[str, str]],
    system: str = "",
    max_tokens: int = 1024,
    temperature: float = 0.0,
) -> str:
    """
    Invoke an LLM and return the response text.

    messages format: [{"role": "user" | "assistant", "content": "<text>"}]
    """
    if provider == "anthropic":
        return _invoke_anthropic(model_id, messages, system, max_tokens, temperature)
    elif provider == "openai":
        return _invoke_openai(model_id, messages, system, max_tokens, temperature)
    elif provider == "bedrock":
        return _invoke_bedrock(model_id, messages, system, max_tokens, temperature)
    else:
        raise ValueError(f"Unknown provider: {provider!r}. Choose from: anthropic, openai, bedrock")


def get_embeddings(provider: str, model_id: str):
    """
    Return a LangChain-compatible embeddings object for the given provider and model.
    The returned object can be passed directly to FAISS.from_documents().
    """
    if provider == "bedrock":
        import boto3
        from langchain_aws import BedrockEmbeddings
        client = boto3.client(
            "bedrock-runtime",
            region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
        )
        return BedrockEmbeddings(client=client, model_id=model_id)
    elif provider == "openai":
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(
            model=model_id,
            api_key=os.environ["OPENAI_API_KEY"],
        )
    else:
        raise ValueError(f"Embeddings not supported for provider: {provider!r}")


# ── provider implementations ──────────────────────────────────────────────────

def _invoke_anthropic(
    model_id: str,
    messages: list[dict],
    system: str,
    max_tokens: int,
    temperature: float,
) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    kwargs: dict[str, Any] = {
        "model": model_id,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if system:
        kwargs["system"] = system
    response = client.messages.create(**kwargs)
    return response.content[0].text


def _invoke_openai(
    model_id: str,
    messages: list[dict],
    system: str,
    max_tokens: int,
    temperature: float,
) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    full_messages = []
    if system:
        full_messages.append({"role": "system", "content": system})
    full_messages.extend(messages)
    response = client.chat.completions.create(
        model=model_id,
        messages=full_messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return response.choices[0].message.content


def _invoke_bedrock(
    model_id: str,
    messages: list[dict],
    system: str,
    max_tokens: int,
    temperature: float,
) -> str:
    import boto3
    client = boto3.client(
        "bedrock-runtime",
        region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
    )
    bedrock_messages = [
        {"role": m["role"], "content": [{"text": m["content"]}]}
        for m in messages
    ]
    kwargs: dict[str, Any] = {
        "modelId": model_id,
        "messages": bedrock_messages,
        "inferenceConfig": {"maxTokens": max_tokens, "temperature": temperature},
    }
    if system:
        kwargs["system"] = [{"text": system}]
    response = client.converse(**kwargs)
    return response["output"]["message"]["content"][0]["text"]
