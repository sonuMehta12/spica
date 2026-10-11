# The model provider — a setting, Anthropic by default

> Status: **settled 2026-10-11 — built; the eval on Haiku is owed.**
> Surface: backend (`app/llm.py`, `app/config.py`), the deploy settings.
> Replaces the OpenAI-only decision recorded in `app/config.py` (Luna, chosen
> 2026-09-12 and 2026-10-01 on cost).

## The problem

The agent ran on OpenAI's `gpt-6-luna`, through a key that should not have
been used for the deployed app. Spica moves to Anthropic, and the move should
never again be a code change: the next one — back, or to a newer model — is a
setting.

## What it does

Three settings choose the model, and nothing else in the codebase knows them:

| Setting | Default | Other value |
|---|---|---|
| `LLM_PROVIDER` | `anthropic` | `openai` |
| `LLM_MODEL` | `claude-haiku-5-5` | `gpt-6-luna` |
| the provider's key | `ANTHROPIC_API_KEY` | `OPENAI_API_KEY` |

**Claude Haiku 5.5** is the cheap, fast, tool-calling tier — the job Luna
did: from $0.10 per million input tokens and $0.50 per million output, a 1M
context, adaptive thinking, and the effort parameter, whose default (medium)
is the level the chat eval settled on.

Every caller keeps speaking one shape — the Responses API's `input` items in,
a reply with `output`, `output_text` and `usage` out. `app/llm.py` passes it
straight to OpenAI, and translates it both ways for Anthropic's Messages API:

- **The request.** The instructions are the first system block, marked for
  the prompt cache; the rolling summary (a `developer` item) joins the system
  after them, since Anthropic's messages hold only `user` and `assistant`.
  Tools keep their schema and change key names, and the last one carries the
  cache mark, so the stable prefix — tools, then system — is cached together.
  Tool outputs become `tool_result` blocks. Turns of one role merge; empty text
  is dropped; a window that opens on the agent gets a placeholder turn first.
- **Effort.** `output_config.effort`, mapped from the names the code uses;
  `none` — OpenAI's "no reasoning" — is `low` with thinking disabled, which
  Haiku 5.5 allows at `high` and below.
- **The reply.** Text, tool calls and thinking come back as the items the
  runner already reads, in the order Claude wrote them. A thinking block is
  kept whole — signature included — because in a tool loop it must go back
  unchanged in front of the calls it led to. Cached input counts as input in
  the turn's token count. A refusal is `PromptRefused`, as on OpenAI.
- `max_tokens` is `LLM_MAX_TOKENS`, 16,000: thinking counts against it, and
  a reply here is a line or two.

## Rules and edge cases

- **Run the end-to-end eval on Haiku before trusting it**
  (`uv run python -m evals.n2n_eval`). Every number the prompts were tuned to
  — 96% of cases, the effort sweep — was measured on Luna.
- **No sampling settings, no assistant prefill.** Haiku 5.5 refuses
  non-default temperature and a final assistant turn; the code sends neither.
- **The tests run on the OpenAI path** with the scripted model, and the
  Anthropic translation has its own (`tests/test_llm_provider.py`), so neither
  spends tokens.

## Decided against

| Option | Why not |
|---|---|
| A provider library over both (LiteLLM and the like) | A dependency to save one file of translation, and another layer between a tool loop and the docs it must follow |
| Moving every caller to the Messages API | The callers' shape works for both; translating at the one seam keeps the switch a setting |
| Sonnet 5.5 | Twenty times Haiku's price for a job Haiku's tier was chosen for; one setting away if the eval says otherwise |
