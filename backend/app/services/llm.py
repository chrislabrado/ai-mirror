"""LLM provider abstraction.

A single ``chat_json`` async function returns structured JSON regardless of
backend. When no API key is present we return a deterministic placeholder
so the UI remains demonstrable in pure local mode.
"""
from __future__ import annotations

import json
from typing import Any

from app.config import settings
from app.utils.logger import get_logger

log = get_logger(__name__)


class LLMUnavailable(RuntimeError):
    """Raised when no usable LLM backend is configured."""


def llm_available() -> bool:
    if settings.llm_provider == "openai":
        return bool(settings.openai_api_key)
    if settings.llm_provider == "anthropic":
        return bool(settings.anthropic_api_key)
    if settings.llm_provider == "grok":
        return bool(settings.xai_api_key)
    if settings.llm_provider == "ollama":
        return bool(settings.ollama_base_url)
    return False


async def chat_json(
    *,
    system: str,
    user: str,
    schema_hint: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 2048,
) -> dict[str, Any]:
    """Single-shot JSON-mode completion with the configured provider."""
    if not llm_available():
        raise LLMUnavailable(
            "No LLM configured. Set LLM_PROVIDER + API key, or run with the "
            "`local-llm` compose profile."
        )

    composite_user = user if not schema_hint else f"{user}\n\nReturn ONLY JSON matching: {schema_hint}"

    provider = settings.llm_provider
    if provider == "openai":
        return await _openai_json(system, composite_user, temperature, max_tokens)
    if provider == "anthropic":
        return await _anthropic_json(system, composite_user, temperature, max_tokens)
    if provider == "grok":
        return await _grok_json(system, composite_user, temperature, max_tokens)
    if provider == "ollama":
        return await _ollama_json(system, composite_user, temperature, max_tokens)
    raise LLMUnavailable(f"Unsupported provider: {provider}")


async def _openai_json(system: str, user: str, temperature: float, max_tokens: int) -> dict[str, Any]:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    resp = await client.chat.completions.create(
        model=settings.llm_model,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    return json.loads(resp.choices[0].message.content or "{}")


async def _grok_json(system: str, user: str, temperature: float, max_tokens: int) -> dict[str, Any]:
    """xAI Grok via OpenAI-compatible endpoint at https://api.x.ai/v1."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(
        api_key=settings.xai_api_key,
        base_url=settings.xai_base_url,
    )
    resp = await client.chat.completions.create(
        model=settings.llm_model,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    return json.loads(resp.choices[0].message.content or "{}")


async def _anthropic_json(system: str, user: str, temperature: float, max_tokens: int) -> dict[str, Any]:
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    resp = await client.messages.create(
        model=settings.llm_model,
        system=system + "\n\nRespond with valid JSON only.",
        max_tokens=max_tokens,
        temperature=temperature,
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    return json.loads(text)


async def _ollama_json(system: str, user: str, temperature: float, max_tokens: int) -> dict[str, Any]:
    import httpx

    async with httpx.AsyncClient(base_url=settings.ollama_base_url, timeout=120) as http:
        resp = await http.post(
            "/api/chat",
            json={
                "model": settings.llm_model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "format": "json",
                "stream": False,
                "options": {"temperature": temperature, "num_predict": max_tokens},
            },
        )
        resp.raise_for_status()
        body = resp.json()
    return json.loads(body["message"]["content"])
