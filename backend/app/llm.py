"""
The only module that imports an LLM SDK.

Not architecture for its own sake: spec/api.md still has an open question about
where the model runs, and that answer would change `/categorise` and `/chat`
completely. Threading vendor calls through twenty files makes that a rewrite;
keeping them here makes it one file.

Provider and model are configuration — `LLM_PROVIDER`, `LLM_MODEL` and the
provider's key, nothing else. Anthropic `claude-haiku-5-5` since 2026-10-11;
OpenAI `gpt-6-luna` before, still one setting away. Nothing else in the
codebase knows which.

`respond()` is the one call shape; `categorise()` and the runner's two calls
sit on it. Nothing else in the codebase reaches past this file. The shape the
callers speak is the Responses API's — `input` items in, a reply with
`output`, `output_text` and `usage` out — so OpenAI is a straight pass, and
Anthropic is translated both ways here: `_to_anthropic` for the request,
`Reply` for the answer.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
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
    """One model call, no streaming — every caller in the codebase goes
    through here. The provider is `LLM_PROVIDER`; the answer has the same
    shape either way (see the module note).

    `cache_key` is a hint for a provider's prompt cache; the layout that makes
    the cache hit is the caller's job (`instructions` and `tools` stable, the
    volatile part last in `input`)."""
    if settings().llm_provider == "anthropic":
        return await _respond_anthropic(instructions=instructions, input=input, tools=tools,
                                        model_id=model_id, effort=effort)
    return await _respond_openai(instructions=instructions, input=input, tools=tools,
                                 model_id=model_id, effort=effort, cache_key=cache_key)


async def _respond_openai(*, instructions: str, input: list | str, tools: list[dict] | None,
                          model_id: str | None, effort: str | None,
                          cache_key: str | None) -> Any:
    """The Responses API (decided 2026-09-15; `/v1/chat/completions` before
    that): Luna only allows thinking together with function tools there.

    `store=False`: the user's ledger is not kept on the provider's side. The
    price of statelessness is that a tool loop has to hand the model's own
    reasoning items back with the tool outputs, which is what
    `reasoning.encrypted_content` is for — the caller appends `resp.output`
    to the next `input`, as the docs show, and nothing else is needed."""
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


# ─── Anthropic ───────────────────────────────────────────────────────────────

# The callers' effort names, in Anthropic's terms. "none" is OpenAI's "no
# reasoning": here it is thinking off, at the lowest effort — thinking can be
# turned off at `high` and below on Haiku 5.5, never at `xhigh` or `max`.
_EFFORT = {"none": "low", "minimal": "low", "low": "low", "medium": "medium",
           "high": "high", "xhigh": "xhigh", "max": "max"}


@dataclass
class OutputText:
    text: str
    type: str = "output_text"


@dataclass
class OutputMessage:
    content: list[OutputText]
    type: str = "message"
    phase: str | None = None


@dataclass
class FunctionCall:
    """A tool call, in the shape the runner reads: `arguments` is JSON text."""
    name: str
    arguments: str
    call_id: str
    type: str = "function_call"


@dataclass
class Reasoning:
    """Claude's thinking block, kept whole — signature and all. In a tool loop
    it must go back unchanged in front of the tool calls it led to."""
    block: dict
    type: str = "reasoning"


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class Reply:
    """Anthropic's answer, in the shape every caller already reads."""
    output: list = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)

    @property
    def output_text(self) -> str:
        return "\n\n".join(t.text for o in self.output if isinstance(o, OutputMessage)
                           for t in o.content if t.text).strip()


def _tool(t: dict) -> dict:
    """A Responses-API function tool as an Anthropic tool: only the names differ."""
    return {"name": t["name"], "description": t.get("description", ""),
            "input_schema": t.get("parameters") or {"type": "object", "properties": {}}}


def _to_anthropic(instructions: str, input: list | str) -> tuple[list[dict], list[dict]]:
    """The system blocks and the messages for one call.

    The instructions are the first system block, marked for the prompt cache:
    they and the tools are the stable prefix. A `developer` item — the rolling
    summary — joins the system after them, because Anthropic's messages hold
    only `user` and `assistant`. The model's own items from an earlier round
    (thinking, text, tool calls) become one assistant message, in order; tool
    outputs become `tool_result` blocks; neighbouring turns of one role merge,
    since the API wants them alternating. Empty text is dropped — the API
    refuses an empty block."""
    system: list[dict] = [{"type": "text", "text": instructions,
                           "cache_control": {"type": "ephemeral"}}]
    messages: list[dict] = []

    def put(role: str, blocks: list[dict]) -> None:
        if not blocks:
            return
        if messages and messages[-1]["role"] == role:
            messages[-1]["content"].extend(blocks)
        else:
            messages.append({"role": role, "content": list(blocks)})

    items = [{"role": "user", "content": input}] if isinstance(input, str) else input
    for it in items:
        if isinstance(it, Reasoning):
            put("assistant", [it.block])
        elif isinstance(it, FunctionCall):
            try:
                args = json.loads(it.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            put("assistant", [{"type": "tool_use", "id": it.call_id, "name": it.name,
                               "input": args}])
        elif isinstance(it, OutputMessage):
            put("assistant", [{"type": "text", "text": t.text} for t in it.content if t.text])
        elif isinstance(it, dict) and it.get("type") == "function_call_output":
            put("user", [{"type": "tool_result", "tool_use_id": it["call_id"],
                          "content": str(it.get("output", ""))}])
        elif isinstance(it, dict) and it.get("role") in ("developer", "system"):
            if it.get("content"):
                system.append({"type": "text", "text": str(it["content"])})
        elif isinstance(it, dict) and it.get("role") in ("user", "assistant"):
            text = it.get("content")
            if isinstance(text, str) and text.strip():
                put(it["role"], [{"type": "text", "text": text}])
    # A conversation has to open with the person; a window that starts on
    # the agent's line gets a placeholder turn in front of it.
    if messages and messages[0]["role"] != "user":
        messages.insert(0, {"role": "user", "content": [{"type": "text", "text": "(earlier)"}]})
    return system, messages


def _from_anthropic(resp: Any) -> Reply:
    """Content blocks → the callers' items, in the order Claude wrote them."""
    out: list = []
    for b in getattr(resp, "content", None) or []:
        kind = getattr(b, "type", None)
        if kind == "text":
            if b.text:
                out.append(OutputMessage([OutputText(b.text)]))
        elif kind == "tool_use":
            out.append(FunctionCall(name=b.name, arguments=json.dumps(b.input or {}),
                                    call_id=b.id))
        elif kind in ("thinking", "redacted_thinking"):
            out.append(Reasoning(b.model_dump(exclude_none=True)))
    u = getattr(resp, "usage", None)
    # Cached input is still input: the count is what this turn read.
    read = sum(getattr(u, k, 0) or 0 for k in
               ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
    return Reply(out, Usage(read, getattr(u, "output_tokens", 0) or 0))


async def _respond_anthropic(*, instructions: str, input: list | str,
                             tools: list[dict] | None, model_id: str | None,
                             effort: str | None) -> Reply:
    """The Messages API. Effort is `output_config.effort`; "none" also turns
    thinking off. Thinking counts against `max_tokens`, hence the headroom."""
    cfg = settings()
    how = effort or cfg.llm_effort
    system, messages = _to_anthropic(instructions, input)
    kw: dict[str, Any] = {
        "model": model_id or model(), "max_tokens": cfg.llm_max_tokens,
        "system": system, "messages": messages,
        "output_config": {"effort": _EFFORT.get(how, "medium")},
    }
    if how == "none":
        kw["thinking"] = {"type": "disabled"}
    if tools:
        offered = [_tool(t) for t in tools]
        # The last tool carries the cache mark: tools sit in front of the
        # system prompt, so the whole stable prefix is cached at once.
        offered[-1] = {**offered[-1], "cache_control": {"type": "ephemeral"}}
        kw["tools"] = offered
    resp = await client().messages.create(**kw)
    if getattr(resp, "stop_reason", None) == "refusal":
        raise PromptRefused("the provider refused this prompt")
    return _from_anthropic(resp)


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
