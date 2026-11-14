"""OpenAI SDK clients for the LLM and embeddings.

Ollama serves an OpenAI-compatible API under `/v1`, so the official `openai` SDK works with a
custom `base_url` – switching to another provider is only a change in `.env`.
"""

from __future__ import annotations

from typing import Any

from openai import OpenAI

from acts.config import Settings


def llm_client(settings: Settings) -> OpenAI:
    """Client for chat completions.

    `max_retries=0`: with local Ollama retries only delay the error we want to see.
    """
    return OpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key, max_retries=0)


def embed_client(settings: Settings) -> OpenAI:
    """Client for embeddings (same server as the LLM)."""
    return OpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key, max_retries=1)


def chat_kwargs(settings: Settings) -> dict[str, Any]:
    """Parameters shared by every chat completion call.

    `reasoning_effort="none"` disables qwen3.5 thinking (Ollama maps it to `think=false`);
    without it the model writes hundreds of reasoning tokens before answering.
    """
    kwargs: dict[str, Any] = {
        "model": settings.llm_model,
        "temperature": settings.llm_temperature,
    }

    if settings.llm_reasoning_effort:
        kwargs["reasoning_effort"] = settings.llm_reasoning_effort

    return kwargs


def chat(messages: list[dict[str, str]], settings: Settings) -> str:
    """Single chat completion; returns the answer text."""
    response = llm_client(settings).chat.completions.create(
        **chat_kwargs(settings), messages=messages
    )

    return response.choices[0].message.content or ""
