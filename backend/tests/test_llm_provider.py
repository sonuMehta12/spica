"""
The model provider is a setting: spec/llm-provider.md.

Every caller speaks the Responses API's shape — `input` items in, a reply
with `output`, `output_text` and `usage` out. With `LLM_PROVIDER=anthropic`,
app/llm.py translates both ways; these tests hold that translation to the
Messages API, against a fake Anthropic client, so they spend no tokens.
"""

import json
from types import SimpleNamespace

import pytest

from app import llm


class FakeAnthropic:
    """Answers `messages.create` from a script and keeps every request."""

    def __init__(self, *script):
        self.script = list(script)
        self.calls: list[dict] = []
        self.messages = self

    async def create(self, **kw):
        self.calls.append(kw)
        return self.script.pop(0)


def block(**kw):
    """A content block as the SDK returns it: attributes, and `model_dump`."""
    b = SimpleNamespace(**kw)
    b.model_dump = lambda exclude_none=True: {k: v for k, v in kw.items() if v is not None}
    return b


def answer(*blocks, stop="end_turn", **usage):
    u = {"input_tokens": 100, "output_tokens": 20, "cache_read_input_tokens": 0,
         "cache_creation_input_tokens": 0, **usage}
    return SimpleNamespace(content=list(blocks), stop_reason=stop, usage=SimpleNamespace(**u))


@pytest.fixture
def anthropic(monkeypatch):
    def install(*script, effort="medium"):
        fake = FakeAnthropic(*script)
        cfg = SimpleNamespace(llm_provider="anthropic", llm_effort=effort,
                              llm_max_tokens=16000, llm_model="claude-haiku-5-5",
                              categorise_model="", categorise_effort="medium")
        monkeypatch.setattr("app.llm.settings", lambda: cfg)
        monkeypatch.setattr("app.llm.client", lambda: fake)
        monkeypatch.setattr("app.llm.model", lambda: "claude-haiku-5-5")
        return fake
    return install


TOOLS = [{"type": "function", "name": "log_spend", "description": "Log a payment.",
          "parameters": {"type": "object", "properties": {"amount": {"type": "number"}},
                         "required": ["amount"]}, "strict": False},
         {"type": "function", "name": "spend", "description": "Read spending.",
          "parameters": {"type": "object", "properties": {}}, "strict": False}]


async def test_the_defaults_are_anthropic_and_haiku_5_5(monkeypatch):
    from app.config import Settings
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    s = Settings(_env_file=None)
    assert (s.llm_provider, s.llm_model) == ("anthropic", "claude-haiku-5-5")


async def test_a_request_is_the_messages_api_shape(anthropic):
    fake = anthropic(answer(block(type="text", text="Logged.")))
    reply = await llm.respond(
        instructions="You are Spica.", tools=TOOLS,
        input=[{"role": "developer", "content": "Earlier: they track chai."},
               {"role": "assistant", "content": "Hi."},
               {"role": "user", "content": ""},
               {"role": "user", "content": "chai 20"}])
    kw = fake.calls[0]
    assert kw["model"] == "claude-haiku-5-5" and kw["max_tokens"] == 16000
    assert kw["output_config"] == {"effort": "medium"} and "thinking" not in kw
    # The instructions are the cached prefix; the rolling summary joins the system.
    assert kw["system"][0] == {"type": "text", "text": "You are Spica.",
                               "cache_control": {"type": "ephemeral"}}
    assert kw["system"][1]["text"] == "Earlier: they track chai."
    # A window that opens on the agent gets a turn in front; empty text is dropped.
    assert [m["role"] for m in kw["messages"]] == ["user", "assistant", "user"]
    assert kw["messages"][-1]["content"] == [{"type": "text", "text": "chai 20"}]
    # Tools only change key names; the last carries the cache mark.
    assert kw["tools"][0] == {"name": "log_spend", "description": "Log a payment.",
                              "input_schema": TOOLS[0]["parameters"]}
    assert kw["tools"][-1]["cache_control"] == {"type": "ephemeral"}
    assert reply.output_text == "Logged."


@pytest.mark.parametrize("effort, sent, thinking", [
    ("none", "low", {"type": "disabled"}), ("low", "low", None),
    ("medium", "medium", None), ("high", "high", None)])
async def test_effort_maps_and_none_turns_thinking_off(anthropic, effort, sent, thinking):
    fake = anthropic(answer(block(type="text", text="ok")))
    await llm.respond(instructions="x", input="hi", effort=effort)
    assert fake.calls[0]["output_config"] == {"effort": sent}
    assert fake.calls[0].get("thinking") == thinking


async def test_a_tool_loop_hands_thinking_and_calls_back_in_order(anthropic):
    """Two rounds, the way runner.rounds() drives them: the model thinks and
    calls a tool; the next request carries that thinking and that call back
    unchanged, then the tool's result, as the docs require."""
    thought = block(type="thinking", thinking="", signature="sig-1")
    fake = anthropic(
        answer(thought, block(type="tool_use", id="tu_1", name="log_spend", input={"amount": 20})),
        answer(block(type="text", text="Logged ₹20.")))
    items = [{"role": "user", "content": "chai 20"}]

    first = await llm.respond(instructions="x", input=items, tools=TOOLS)
    calls = [o for o in first.output if getattr(o, "type", None) == "function_call"]
    assert [(c.name, json.loads(c.arguments), c.call_id) for c in calls] == \
        [("log_spend", {"amount": 20}, "tu_1")]
    items.extend(first.output)
    items.append({"type": "function_call_output", "call_id": "tu_1",
                  "output": json.dumps({"ok": True})})

    second = await llm.respond(instructions="x", input=items, tools=TOOLS)
    msgs = fake.calls[1]["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant", "user"]
    assert msgs[1]["content"] == [
        {"type": "thinking", "thinking": "", "signature": "sig-1"},
        {"type": "tool_use", "id": "tu_1", "name": "log_spend", "input": {"amount": 20}}]
    assert msgs[2]["content"] == [{"type": "tool_result", "tool_use_id": "tu_1",
                                   "content": '{"ok": true}'}]
    assert second.output_text == "Logged ₹20."


async def test_usage_counts_cached_input_as_input(anthropic):
    anthropic(answer(block(type="text", text="ok"), input_tokens=30, output_tokens=7,
                     cache_read_input_tokens=900, cache_creation_input_tokens=50))
    reply = await llm.respond(instructions="x", input="hi")
    assert (reply.usage.input_tokens, reply.usage.output_tokens) == (980, 7)


async def test_a_refusal_is_prompt_refused(anthropic):
    anthropic(answer(stop="refusal"))
    with pytest.raises(llm.PromptRefused):
        await llm.respond(instructions="x", input="hi")


async def test_categorise_runs_on_anthropic_too(anthropic):
    fake = anthropic(answer(block(type="text", text='{"rows": []}')))
    text, used = await llm.categorise("skill", '{"rows": []}', effort="medium")
    assert text == '{"rows": []}' and used == "claude-haiku-5-5@medium"
    assert fake.calls[0]["messages"] == [{"role": "user",
                                          "content": [{"type": "text", "text": '{"rows": []}'}]}]
