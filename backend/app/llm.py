"""
The only module that imports an LLM SDK.

Not architecture for its own sake: spec/api.md still has an open question about
where the model runs, and that answer would change `/categorise` and `/chat`
completely. Threading vendor calls through twenty files makes that a rewrite;
keeping them here makes it one file.

Provider and model are configuration — `LLM_PROVIDER` and `LLM_MODEL` in
`.env`. OpenAI `gpt-6-luna` today (2026-10-01; `gpt-5.6-luna` before); Anthropic behind the
same three functions when wanted. Nothing else in the codebase knows which.

`respond()` is the one call shape; `categorise()` and the runner's two calls
sit on it. Nothing else in the codebase reaches past this file.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.config import settings

PROVIDERS = ("openai", "anthropic")


@lru_cache
def client() -> Any:
    """The vendor SDK client, built once from config. Imported lazily so a
    machine without a key can still run everything that is not the agent."""
    cfg = settings()
    if cfg.llm_provider == "openai":
        from openai import AsyncOpenAI
        return AsyncOpenAI(api_key=cfg.openai_api_key or None, timeout=cfg.llm_timeout_seconds)
    if cfg.llm_provider == "anthropic":
        try:
            from anthropic import AsyncAnthropic
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("LLM_PROVIDER=anthropic needs `uv add anthropic`") from e
        return AsyncAnthropic(api_key=cfg.anthropic_api_key or None,
                              timeout=cfg.llm_timeout_seconds)
    raise RuntimeError(f"LLM_PROVIDER must be one of {PROVIDERS}, got {cfg.llm_provider!r}")


class PromptRefused(Exception):
    """The provider would not take this prompt at all."""


def model() -> str:
    return settings().llm_model


async def respond(*, instructions: str, input: list | str, tools: list[dict] | None = None,
                  model_id: str | None = None, effort: str | None = None,
                  cache_key: str | None = None) -> Any:
    """One model call, the Responses API, no streaming — every caller in the
    codebase goes through here (decided 2026-09-15; `/v1/chat/completions`
    before that). Why the move: this model only allows thinking together with
    function tools on this endpoint, and the reply still lands whole.

    `store=False`: the user's ledger is not kept on the provider's side. The
    price of statelessness is that a tool loop has to hand the model's own
    reasoning items back with the tool outputs, which is what
    `reasoning.encrypted_content` is for — the caller appends `resp.output`
    to the next `input`, as the docs show, and nothing else is needed.

    `cache_key` is the provider's routing hint for its prompt cache; the
    layout that makes the cache hit is the caller's job (`instructions` and
    `tools` stable, the volatile part last in `input`)."""
    how = effort or settings().llm_effort
    kw: dict[str, Any] = {
        "model": model_id or model(), "instructions": instructions, "input": input,
        "reasoning": {"effort": how}, "store": False,
    }
    if how != "none":
        kw["include"] = ["reasoning.encrypted_content"]
    if tools:
        kw["tools"] = tools
    if cache_key:
        kw["prompt_cache_key"] = cache_key
    try:
        return await client().responses.create(**kw)
    except Exception as e:
        # The provider refusing the prompt itself — "last 3 payments dikhao"
        # was flagged as a policy risk once (2026-10-10), a false positive. It
        # is not our error and not the person's; the caller says so plainly
        # rather than letting it surface as a failed request.
        if getattr(e, "code", None) == "invalid_prompt" or "invalid_prompt" in str(e):
            raise PromptRefused(str(e)) from e
        raise


async def categorise(system: str, payload: str, *, model_id: str | None = None,
                     effort: str | None = None) -> tuple[str, str]:
    """Tier 2 of spec/in-progress/categorise.md — the batch, one call. The
    system prompt is the skill file; the payload is the day's uncertain rows
    as JSON; the answer is JSON the caller validates before anything is
    written. Returns the text and `model@effort`, stamped on the prediction
    row so accuracy can be compared per model later. `CATEGORISE_MODEL` /
    `CATEGORISE_EFFORT` move this call without touching the conversation;
    the explicit arguments are for the eval, which compares them."""
    cfg = settings()
    used = model_id or cfg.categorise_model or model()
    how = effort or cfg.categorise_effort or cfg.llm_effort
    resp = await respond(instructions=system, input=payload, model_id=used, effort=how,
                         cache_key="cortex-categorise")
    return (resp.output_text or ""), f"{used}@{how}"


async def chat(*args, **kwargs):
    """The agent. Returns typed cards, not just prose — spec/in-progress/agent.md. Phase A."""
    raise NotImplementedError("agent phase A")


async def embed(*args, **kwargs):
    """Vectors for the dish ladder's fourth rung. Stored beside the rows via pgvector."""
    raise NotImplementedError("agent phase B")
