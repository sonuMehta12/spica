"""
One turn of the conversation. spec/agent.md.

    load the thread  →  assemble the prompt  →  call the model  →
    run the tools it asked for  →  call again  →  reply in cards  →  append

No streaming: the reply lands whole. That is a deliberate simplification while
the card shapes are still moving — a stream of half-built cards is harder to
change than a single response. The Responses API since 2026-09-15, through
`llm.respond()`; the thread itself is stored in our own rows, so the wire
shape lives in this file and nowhere else.

**What the model sees is not what the user sees.** The user has the whole
thread; the model gets `WINDOW` turns plus a rolling summary of what fell out
before them. Tool traffic is never replayed: an old tool result is a stale
number, and replaying it is how a model comes to quote last week's spend as
today's. Every turn re-reads the ledger.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date

from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import cards as C
from app.agent import prompt as P
from app.agent import tools as T
from app.config import settings
from app.diet_summary import diet_summary
from app.llm import PromptRefused, model, respond
from app.models.chat import Conversation, Message

log = logging.getLogger(__name__)

#: Messages the model is given, and when the thread is compacted. `WINDOW` is
#: the floor a fold returns to; `FOLD_AT` is the ceiling the un-summarised tail
#: may reach first. Folding in batches rather than every turn keeps the message
#: list append-only in between — which is what a prompt cache rewards — and
#: runs the summariser's own model call once per batch instead of once a turn.
#: `CHAT_WINDOW` and `CHAT_FOLD_AT` in `.env`. spec/done/prompt-layout.md.
WINDOW = settings().chat_window
#: Never below WINDOW + 2, or a fold would have nothing to fold.
FOLD_AT = max(settings().chat_fold_at, WINDOW + 2)
#: A turn is one user message and one reply, so the loop must allow a few
#: rounds of tool use — and must not allow a model to loop forever.
MAX_ROUNDS = 6


@dataclass
class Turn:
    text: str
    cards: list[dict] = field(default_factory=list)
    trace: list[dict] = field(default_factory=list)
    tokens_in: int = 0
    tokens_out: int = 0


class ModelFailed(Exception):
    """The model call itself failed — a timeout, the provider down, a prompt
    it refused that the caller had no line for — as distinct from a tool's
    own fault. The first run's turn answers it with a status the screen can
    offer a retry on (spec/done/onboarding-goals.md § A turn)."""


#: What the person reads when the provider refuses the prompt itself.
REFUSED = "I couldn't take that one in — could you say it another way?"


async def _thread(session: AsyncSession, user: str) -> Conversation:
    """The one thread. There is no 'new chat' and there will not be one."""
    row = await session.scalar(select(Conversation).where(
        Conversation.user_id == user, Conversation.deleted_at.is_(None)))
    if row is None:
        row = Conversation(user_id=user)
        session.add(row)
        await session.flush()
    return row


async def history(session: AsyncSession, user: str, limit: int = 200,
                  before: int | None = None,
                  include_cleared: bool = False) -> tuple[list[Message], bool]:
    """One page of what the *user* scrolls, newest last, with whether more sits
    behind it.

    `before` is a `seq`, not an offset: `seq` is already the sort key and
    already per-conversation, so a soft delete or a new arrival cannot shift
    the ground under someone mid-scroll the way `?page=3` would.
    """
    convo = await _thread(session, user)
    where = [Message.conversation_id == convo.id, Message.deleted_at.is_(None)]
    if not include_cleared:
        where.append(Message.seq > convo.cleared_through_seq)
    if before is not None:
        where.append(Message.seq < before)
    rows = list((await session.scalars(
        select(Message).where(*where).order_by(Message.seq.desc()).limit(limit + 1)
    )).all())
    # One extra was asked for purely to answer "is there more?" without a
    # second count query.
    more = len(rows) > limit
    return list(reversed(rows[:limit])), more


async def _window(session: AsyncSession, convo: Conversation) -> list[Message]:
    """Everything not yet folded into the summary.

    Not "the newest WINDOW" — that left a hole. Folding happens in batches, so
    the un-summarised tail grows to FOLD_AT between folds; taking only the
    newest WINDOW of it meant the middle of the conversation was in neither the
    summary nor the window, and the model simply could not see it. Taking all
    of it is also what makes the list append-only between folds, which is the
    whole point of batching. `FOLD_AT` is a safety cap, not the usual bound.
    """
    return list(reversed(list((await session.scalars(
        select(Message).where(Message.conversation_id == convo.id,
                              Message.deleted_at.is_(None),
                              Message.seq > convo.summary_through_seq)
        .order_by(Message.seq.desc()).limit(FOLD_AT)
    )).all())))


async def _fold(session: AsyncSession, convo: Conversation) -> tuple[int, int]:
    """Fold everything past the window into the summary.

    Prose about the *conversation* — what was asked, what was decided, what the
    user is in the middle of. Never numbers: the ledger is re-read every turn,
    so a figure carried forward here could only ever be stale.

    **It reissues; it does not rewrite.** The summary is the only trace left of
    every message behind the pointer, and each fold re-encodes it, so an
    instruction that lets the model drop what is already there compounds: the
    live thread reached 65 rewrites into 120 words and every one of those words
    was about the last three turns.

    Two things had to be said, and both were found by measuring. *"Reissue it
    in full"* carries the old note where *"merge"* and *"do not drop"* did not.
    And the summariser has to be told it is **not in the conversation**: handed
    a transcript that ends on a question it would otherwise answer the question
    in the agent's own second-person voice, markdown and stale numbers
    included, throwing the note away entirely. spec/done/prompt-layout.md.
    """
    total = await session.scalar(select(func.count()).select_from(Message).where(
        Message.conversation_id == convo.id, Message.deleted_at.is_(None),
        Message.seq > convo.summary_through_seq))
    if (total or 0) < FOLD_AT:
        return 0, 0
    overflow = list((await session.scalars(
        select(Message).where(Message.conversation_id == convo.id,
                              Message.deleted_at.is_(None),
                              Message.seq > convo.summary_through_seq)
        .order_by(Message.seq).limit(total - WINDOW)
    )).all())
    if not overflow:
        return 0, 0
    return await _summarise(session, convo, overflow)


async def _summarise(session: AsyncSession, convo: Conversation,
                     overflow: list[Message]) -> tuple[int, int]:
    """Merge a slice of turns into the running summary and move the pointer
    past them. Called on a fold, and by a clear, which folds everything."""
    transcript = "\n".join(f"{m.role}: {m.text}" for m in overflow if m.text)
    words = settings().chat_summary_words
    resp = await respond(
        cache_key="cortex-summary",
        instructions=(
             "You maintain the running memory of a conversation between a person and "
             "their ledger agent. You are NOT part of that conversation.\n"
             "Never answer anything in the transcript, never address the person, never "
             "continue the agent's last reply. Write ABOUT them, in the third person, "
             "as a note to yourself. If the transcript ends on a question, the note "
             "records that they asked it — it does not answer it.\n"
             "Your previous note is the only record left of everything it covers. "
             "Reissue it in full, changed only where the new turns add to it or make "
             "part of it finished. Dropping something still open loses it for good.\n"
             "Keep: what they asked for, what was decided, what they are in the middle "
             "of, what they want next.\n"
             "Drop: every number, amount and date — those are re-read from the database "
             "and would go stale here. Drop small talk and anything closed.\n"
             f"Under {words} words. Plain prose, oldest concerns first. No preamble, "
             "no headings, no markdown."),
        input=[{"role": "user", "content":
                f"Your note so far:\n{convo.summary or '(none yet — this is the first)'}"
                f"\n\n<transcript>\n{transcript}\n</transcript>"}],
    )
    convo.summary = (resp.output_text or convo.summary or "").strip()
    convo.summary_through_seq = overflow[-1].seq
    return resp.usage.input_tokens, resp.usage.output_tokens


async def clear(session: AsyncSession, user: str, keep: int = 1) -> Conversation:
    """Clear the screen without forgetting.

    Everything above the last `keep` messages is folded into the summary and
    hidden from the client's default read. Nothing is deleted: the thread is
    still one thread, which is the promise `_thread` makes, and *Show* brings
    the hidden turns back.

    Clearing **compacts** rather than merely hiding, because a clean screen
    beside an agent that still quotes what you just cleared reads as broken.
    The gist survives in the summary; the words do not.
    spec/done/chat-history.md.
    """
    convo = await _thread(session, user)
    rows = list((await session.scalars(
        select(Message).where(Message.conversation_id == convo.id,
                              Message.deleted_at.is_(None))
        .order_by(Message.seq)
    )).all())
    if len(rows) <= keep:
        return convo
    above = rows[:-keep] if keep else rows
    # Only what is not already in the summary needs summarising.
    fresh = [m for m in above if m.seq > convo.summary_through_seq]
    if fresh:
        try:
            await _summarise(session, convo, fresh)
        except Exception:  # noqa: BLE001 — hiding must work even if the model does not
            log.exception("clear: compaction failed; hiding without folding")
    convo.cleared_through_seq = above[-1].seq
    await session.commit()
    return convo


def _input(convo: Conversation, window: list[Message], said: str, now: str) -> list[dict]:
    """The `input` list, ordered by how often each part changes, most stable
    first, because a provider's cache matches a prefix and stops at the first
    difference. The system prompt and the tool schemas ride separately as
    `instructions` and `tools` and sit in front of all of this.

    1. the rolling summary — changes once every FOLD_AT turns
    2. the window — append-only between folds
    3. this turn: what is true right now, then what they said

    `now` is attached here and never stored. Replayed three turns later it
    would be a stale number, which is the same reason tool results are not
    replayed either.
    """
    items: list[dict] = []
    if convo.summary:
        items.append({"role": "developer",
                      "content": f"Earlier in this conversation:\n{convo.summary}"})
    for m in window:
        items.append({"role": "user" if m.role == "user" else "assistant",
                      "content": m.text or ""})
    items.append({"role": "user", "content": f"{now}{_written(window)}\n\n{said}"})
    return items


def _written(window: list[Message]) -> str:
    """The rows the conversation's recent turns wrote, by id, newest first —
    on the context block, beside today's numbers.

    Tool results are not replayed, so the next turn saw what was *said* and
    not *which row* it was said about: "dal ek katori thi" went out as
    `meal_id: PLACEHOLDER`, and "90k sorry" and "chai 25 ki thi" logged a
    second payment rather than correct the one just made (2026-10-09). The ids
    are already on each turn's cards.

    Not under the replies themselves: put there, the model copied the line
    into its own answers and wrote claims in its shape for rows it never
    wrote (2026-10-10). Ids only, with each card's one-line label — never a
    figure that could go stale.
    """
    rows = [c for m in reversed(window) if m.role != "user"
            for c in (m.cards or []) if c.get("kind") == "confirm" and c.get("row_id")]
    if not rows:
        return ""
    said = "; ".join(f"{c.get('source')} {c['row_id']}"
                     + (" (deleted)" if c.get("state") == "deleted" else "")
                     + (f" — {c['lede']}" if c.get("lede") else "") for c in rows[:15])
    return f"\n[rows written in this conversation, newest first — for corrections: {said}]"


#: The model echoing a context line into its reply.
_ECHO = re.compile(r"\s*\[(?:wrote|rows written)[^\]]*\]")


async def _enrich(session: AsyncSession, user: str, name: str, args: dict,
                  result: dict) -> None:
    """One number a card needs that its own tool does not return: after a meal
    is written or corrected, what is left today; after a pantry move, what is
    on the shelf now. Fetched here so the card can lead with it, which is the
    rule the old confirm copy broke."""
    if result.get("error"):
        return
    if name in ("log_meal", "correct_meal"):
        raw = args.get("local_day") or (result.get("meal") or {}).get("local_day")
        if raw:
            day = raw if isinstance(raw, date) else date.fromisoformat(str(raw))
            today = await diet_summary(session, user, day, day, {"today"})
            result["_protein_left"] = today.get("today", {}).get("protein_left_g")
    elif name == "pantry_move" and result.get("food_id"):
        result["_stock_after"] = await session.scalar(text(
            "SELECT COALESCE(SUM(quantity), 0)::int FROM pantry_moves "
            "WHERE user_id = :u AND food_id = :f AND deleted_at IS NULL"),
            {"u": user, "f": result["food_id"]})


def _said_by(cards: list[dict]) -> str:
    """The one line the thread keeps for a tap, so the model's window and the
    user's scrollback both know what happened."""
    for c in cards:
        if c.get("kind") == "confirm":
            what = next((f["value"] for f in c.get("fields", [])
                         if f["key"] in ("dish", "description", "name", "food")), "")
            return f"{what} · {c['lede']}" if what else c["lede"]
        if c.get("kind") == "table":
            return c["heading"]
    return "Done"


async def act(session: AsyncSession, user: str, name: str, args: dict,
              record: bool = False) -> Turn:
    """A tool run from a tap, not from the model — the same tool, the same
    cards, minus the model and the seconds it takes. With `record` the turn is
    appended like any other; without it the cards are returned and the thread
    is left alone, because a tap's confirmation is a receipt, not something
    said — the ledger holds the fact and the model re-reads the ledger every
    turn. spec/done/chat-cards.md."""
    if name not in T.BY_NAME:
        raise HTTPException(status_code=404, detail=f"no tool called {name!r}")
    convo = await _thread(session, user)
    result = await T.run(session, user, name, args)
    if result.get("error"):
        raise HTTPException(status_code=int(result.get("status") or 422),
                            detail=str(result["error"]))
    await _enrich(session, user, name, args, result)
    cards = [c.model_dump() for c in C.from_tool(name, args, result)]
    turn = Turn(text=_said_by(cards), cards=cards,
                trace=[{"tool": name, "args": args, "ok": True, "tap": True}])
    if record:
        seq = (await session.scalar(select(func.coalesce(func.max(Message.seq), 0)).where(
            Message.conversation_id == convo.id))) or 0
        session.add(Message(conversation_id=convo.id, user_id=user, seq=seq + 1,
                            role="agent", text=turn.text, cards=turn.cards,
                            tool_trace=turn.trace, tokens_in=0, tokens_out=0, model="tap"))
        await session.flush()
    await session.commit()
    return turn


def final_text(resp) -> str:
    """The reply the person reads — the model's final answer, said once.

    `output_text` joins every text part of every message item, so a turn that
    came back with a commentary message beside its final one, or the same part
    twice, reached the thread as one sentence written twice with no space
    between (2026-09-27). Final-answer messages only when the model marks them,
    each distinct part once, and a text that is exactly one half repeated is
    that half.
    """
    msgs = [o for o in (getattr(resp, "output", None) or [])
            if getattr(o, "type", None) == "message"]
    if not msgs:
        return (getattr(resp, "output_text", "") or "").strip()
    finals = [o for o in msgs if getattr(o, "phase", None) == "final_answer"] or msgs
    parts: list[str] = []
    for o in finals:
        for c in getattr(o, "content", None) or []:
            t = (getattr(c, "text", "") or "").strip()
            if t and t not in parts:
                parts.append(t)
    text = "\n\n".join(parts)
    half = len(text) // 2
    if half and len(text) % 2 == 0 and text[:half] == text[half:]:
        text = text[:half]
    return text.strip()


async def rounds(session: AsyncSession, user: str, items: list, *, system: str,
                 tools: list[dict], cache_key: str, said: str,
                 local_time: str | None = None,
                 refused: str | None = REFUSED) -> tuple[Turn, list[dict]]:
    """The tool loop: call the model, run what it asked for, hand back what
    came of it, until it answers in prose. Returns the turn, and what
    suggest_dishes / dishes_search / exercises returned — the closed set a
    reply's dish names are matched against once the prose is known.

    The chat's turn and the first run's agent (onboarding.py) both run on it,
    each with its own prompt and its own `tools` — what the model is offered
    is all it can run. A failed model call raises `ModelFailed`; a refusal
    becomes the `refused` line instead, unless that is None.
    """
    registry = {t["name"]: t for t in tools}
    offered = T.schemas(tools)
    turn = Turn(text="")
    seen: set[str] = set()
    candidates: list[dict] = []
    for _ in range(MAX_ROUNDS):
        try:
            resp = await respond(instructions=system, input=items, tools=offered,
                                 cache_key=cache_key)
        except PromptRefused as e:
            if refused is None:
                raise ModelFailed(str(e)) from e
            turn.text = refused
            break
        except Exception as e:
            raise ModelFailed(str(e)) from e
        turn.tokens_in += resp.usage.input_tokens
        turn.tokens_out += resp.usage.output_tokens
        calls = [o for o in resp.output if getattr(o, "type", None) == "function_call"]
        if not calls:
            turn.text = _ECHO.sub("", final_text(resp)).strip()
            break

        # Everything the model produced goes back in front of the tool
        # outputs — the function calls, and the reasoning items the docs say
        # must travel with them. Statelessly (`store=False`) that reasoning is
        # the encrypted item `respond()` asked for.
        items.extend(resp.output)
        for call in calls:
            name = call.name
            try:
                args = json.loads(call.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            # The same write twice in one turn is a model repeating itself, not
            # the user asking twice. Ids are minted server-side, so nothing
            # else would catch it.
            key = f"{name}:{call.arguments}"
            if key in seen and name.startswith(("log_", "keep_", "save_", "delete_",
                                                "remember")):
                result = {"error": "already done in this turn"}
            else:
                seen.add(key)
                # A write with no stated time takes the clock off this turn,
                # not midday. Before this, everything the agent logged landed
                # at 12:00 whatever hour it actually was.
                result = await T.run(session, user, name, args, default_time=local_time,
                                     said=said, registry=registry)
                await _enrich(session, user, name, args, result)
            turn.trace.append({"tool": name, "args": args,
                               "ok": not result.get("error"),
                               "error": result.get("error")})
            if name in ("suggest_dishes", "dishes_search", "exercises") and not result.get("error"):
                got = (result.get("candidates") or result.get("dishes")
                       or result.get("exercises") or [])
                if name == "exercises":
                    got = [{**e, "_type": "exercise"} for e in got]
                candidates.extend(got)
            turn.cards.extend(c.model_dump() for c in C.from_tool(name, args, result))
            items.append({"type": "function_call_output", "call_id": call.call_id,
                          "output": json.dumps(T.for_model(name, result, args),
                                               default=str)[:12000]})
    else:
        turn.text = turn.text or "That took too many steps — ask me again, more narrowly."
    return turn, candidates


async def reply(session: AsyncSession, user: str, said: str, today: date,
                local_time: str | None = None) -> Turn:
    """A turn. Tools run against the same session, so a write and the read that
    follows it in the same breath see each other."""
    convo = await _thread(session, user)
    system = await P.build(session, user)
    now = await P.now_block(session, user, today, local_time)
    window = await _window(session, convo)
    items = _input(convo, window, said, now)

    turn, candidates = await rounds(session, user, items, system=system, tools=T.TOOLS,
                                    cache_key=f"cortex-{user}", said=said,
                                    local_time=local_time)

    # The model's prose leads; the typed cards follow it. The dishes it named
    # become a card only now, because only now is there prose to read.
    turn.cards.extend(c.model_dump() for c in C.suggest_from_text(turn.text, candidates))
    # Reads the model made only to check something do not become cards.
    turn.cards = C.curate(turn.cards, [t["tool"] for t in turn.trace])
    turn.cards = ([C.AgentCard(text=turn.text).model_dump()] if turn.text else []) + turn.cards

    seq = (await session.scalar(select(func.coalesce(func.max(Message.seq), 0)).where(
        Message.conversation_id == convo.id))) or 0
    session.add(Message(conversation_id=convo.id, user_id=user, seq=seq + 1,
                        role="user", text=said))
    session.add(Message(conversation_id=convo.id, user_id=user, seq=seq + 2,
                        role="agent", text=turn.text, cards=turn.cards,
                        tool_trace=turn.trace, tokens_in=turn.tokens_in,
                        tokens_out=turn.tokens_out, model=model()))
    await session.flush()
    # The turn lands first, on its own. Compaction used to run before this
    # commit, so a summariser that timed out took the whole turn with it —
    # while any tool that had already written stayed written, because the
    # routes commit for themselves. The user then retried and paid twice.
    await session.commit()

    try:
        folded_in, folded_out = await _fold(session, convo)
        await session.commit()
        # The summariser's own call is part of what this turn cost. Leaving it
        # out understated every long thread's usage.
        turn.tokens_in += folded_in
        turn.tokens_out += folded_out
    except Exception:  # noqa: BLE001 — a failed fold is not the user's problem
        await session.rollback()
        log.exception("compaction failed; the thread stays uncompacted until next turn")
    return turn
