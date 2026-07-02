"""LLM provider abstraction with tiered model routing (fable mode).

``chat_json`` is the single entry point. Every call site declares a *tier*:

- ``scaffold`` — mechanical/volume work: per-conversation summaries, epoch
  profiles, extraction. Cheap-and-fast model when fable mode is on.
- ``hard`` — judgment work: report synthesis, trajectories, meta-analysis,
  the adversarial critique. Strongest model when fable mode is on.

With fable mode off, both tiers resolve to ``settings.llm_model`` and the
behaviour matches v1.1. Fable mode is enabled by ``FABLE_MODE=true`` or
per-request (report endpoints accept ``fable: true``), carried here via the
``fable`` argument.

Providers: openai, anthropic, grok/xai, ollama, and ``claude_cli`` — the
local ``claude`` binary in print mode (subscription OAuth, no API key on
disk). ``claude_cli`` is the local-first default on the Mac Mini.
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Literal

from app.config import settings
from app.utils.logger import get_logger

log = get_logger(__name__)

Tier = Literal["scaffold", "hard"]

# Cap concurrent in-flight LLM calls (subprocess or HTTP) so batch phases
# (per-conversation summaries, epoch profiles) don't stampede the provider.
_semaphore: asyncio.Semaphore | None = None


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(max(1, settings.llm_max_concurrency))
    return _semaphore


class LLMUnavailable(RuntimeError):
    """Raised when no usable LLM backend is configured."""


def _provider() -> str:
    # Accept both "grok" and "xai" for the xAI provider (v1.1 shipped with
    # the env example saying "xai" and the code saying "grok").
    return "grok" if settings.llm_provider == "xai" else settings.llm_provider


def llm_available() -> bool:
    provider = _provider()
    if provider == "openai":
        return bool(settings.openai_api_key)
    if provider == "anthropic":
        return bool(settings.anthropic_api_key)
    if provider == "grok":
        return bool(settings.xai_api_key)
    if provider == "ollama":
        return bool(settings.ollama_base_url)
    if provider == "claude_cli":
        return True  # binary + OAuth are checked at call time
    return False


def resolve_model(tier: Tier, fable: bool | None = None) -> str:
    """Which model a call at this tier should use."""
    fable_on = settings.fable_mode if fable is None else fable
    if not fable_on:
        return settings.llm_model
    return settings.scaffold_model if tier == "scaffold" else settings.hard_model


def _extract_json(text: str) -> dict[str, Any]:
    """Parse a JSON object out of model text, tolerating fences and prose."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text.strip())
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise
        parsed = json.loads(text[start : end + 1])
    if not isinstance(parsed, dict):
        raise json.JSONDecodeError("top-level JSON is not an object", text, 0)
    return parsed


async def chat_json(
    *,
    system: str,
    user: str,
    schema_hint: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 2048,
    tier: Tier = "hard",
    fable: bool | None = None,
) -> dict[str, Any]:
    """Single-shot JSON-mode completion with the configured provider."""
    if not llm_available():
        raise LLMUnavailable(
            "No LLM configured. Set LLM_PROVIDER + API key, use the claude_cli "
            "provider, or run with the `local-llm` compose profile."
        )

    composite_user = user if not schema_hint else f"{user}\n\nReturn ONLY JSON matching: {schema_hint}"
    model = resolve_model(tier, fable)
    provider = _provider()

    log.info(
        "llm.call",
        extra={"provider": provider, "model": model, "tier": tier, "user_chars": len(composite_user)},
    )

    async with _get_semaphore():
        if provider == "openai":
            return await _openai_json(system, composite_user, temperature, max_tokens, model)
        if provider == "anthropic":
            return await _anthropic_json(system, composite_user, temperature, max_tokens, model)
        if provider == "grok":
            return await _grok_json(system, composite_user, temperature, max_tokens, model)
        if provider == "ollama":
            return await _ollama_json(system, composite_user, temperature, max_tokens, model)
        if provider == "claude_cli":
            return await _claude_cli_json(system, composite_user, model)
    raise LLMUnavailable(f"Unsupported provider: {provider}")


async def _openai_json(
    system: str, user: str, temperature: float, max_tokens: int, model: str
) -> dict[str, Any]:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    resp = await client.chat.completions.create(
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    return _extract_json(resp.choices[0].message.content or "{}")


async def _grok_json(
    system: str, user: str, temperature: float, max_tokens: int, model: str
) -> dict[str, Any]:
    """xAI Grok via OpenAI-compatible endpoint at https://api.x.ai/v1."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(
        api_key=settings.xai_api_key,
        base_url=settings.xai_base_url,
    )
    resp = await client.chat.completions.create(
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    return _extract_json(resp.choices[0].message.content or "{}")


async def _anthropic_json(
    system: str, user: str, temperature: float, max_tokens: int, model: str
) -> dict[str, Any]:
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    resp = await client.messages.create(
        model=model,
        system=system + "\n\nRespond with valid JSON only.",
        max_tokens=max_tokens,
        temperature=temperature,
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    return _extract_json(text)


async def _ollama_json(
    system: str, user: str, temperature: float, max_tokens: int, model: str
) -> dict[str, Any]:
    import httpx

    async with httpx.AsyncClient(base_url=settings.ollama_base_url, timeout=300) as http:
        resp = await http.post(
            "/api/chat",
            json={
                "model": model,
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
    return _extract_json(body["message"]["content"])


async def _claude_cli_json(system: str, user: str, model: str) -> dict[str, Any]:
    """Local `claude -p` in print mode. Prompt goes over stdin (avoids argv limits)."""
    prompt = f"{system}\n\nRespond with valid JSON only — no prose, no fences.\n\n{user}"
    proc = await asyncio.create_subprocess_exec(
        settings.claude_cli_bin,
        "-p",
        "--model",
        model,
        "--output-format",
        "json",
        "--max-turns",
        "1",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(prompt.encode()), timeout=600)
    except asyncio.TimeoutError:
        proc.kill()
        raise LLMUnavailable(f"claude_cli timed out (model={model})")
    if proc.returncode != 0:
        raise LLMUnavailable(
            f"claude_cli exited {proc.returncode}: {stderr.decode(errors='replace')[:400]}"
        )
    envelope = json.loads(stdout.decode())
    if envelope.get("is_error"):
        raise LLMUnavailable(f"claude_cli error: {str(envelope.get('result'))[:400]}")
    result_text = envelope.get("result") or "{}"
    log.info(
        "llm.claude_cli_done",
        extra={
            "model": model,
            "duration_ms": envelope.get("duration_ms"),
            "cost_usd": envelope.get("total_cost_usd"),
        },
    )
    return _extract_json(result_text)
