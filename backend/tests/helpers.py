"""Small builders so a test reads as what it is checking, not plumbing."""

import json
from datetime import date
from types import SimpleNamespace

_seq = 0


def ulid() -> str:
    """A unique 26-char id per call — client-supplied, as every write expects."""
    global _seq
    _seq += 1
    return f"01TEST{_seq:020d}"


def iso(d: date) -> str:
    return d.isoformat()


async def make_transaction(client, **over):
    body = {
        "id": ulid(),
        "occurred_at": "2026-08-20T12:00:00+05:30",
        "local_day": "2026-08-20",
        "amount_paise": 10000,
        "direction": "debit",
        "kind": "expense",
        "category": "Other",
        "description": "Test spend",
        "source": "manual",
    }
    body.update(over)
    return await client.post("/transactions", json=body)


async def make_meal(client, **over):
    body = {
        "id": ulid(),
        "occurred_at": "2026-08-20T13:00:00+05:30",
        "local_day": "2026-08-20",
        "meal_type": "Lunch",
        "dish": "Test meal",
        "kcal": 400,
        "protein_g": "20",
        "source": "manual",
    }
    body.update(over)
    return await client.post("/meals", json=body)


# ─── a fake model ────────────────────────────────────────────────────────────

def _msg(content=None, calls=None):
    """One scripted model turn: prose, or the tool calls it wants run."""
    return SimpleNamespace(
        content=content,
        tool_calls=[SimpleNamespace(
            id=f"call_{i}", type="function",
            function=SimpleNamespace(name=n, arguments=json.dumps(a)))
            for i, (n, a) in enumerate(calls or [])] or None)


class FakeLLM:
    """Replays a script of turns through a fake `responses.create`. Records
    what it was sent, so a test can assert on the prompt as well as on the
    reply. A scripted step is still `_msg(content, calls)`; it is rendered
    here into the Responses shape — a `message` item and `function_call`
    items — so the tests read as what they check, not as wire format."""

    def __init__(self, script):
        self.script = list(script)
        self.sent = []
        self.responses = SimpleNamespace(create=self._create)

    async def _create(self, **kw):
        self.sent.append(kw)
        # The rolling summary is a model call too. It must not eat the next
        # scripted reply — otherwise a test's outcome depends on how long the
        # thread already is, which is to say on which tests ran before it.
        # Detected by the absence of tools rather than by the prompt's opening
        # words: the wording is tuned, the shape is not.
        if "tools" not in kw:
            step = _msg("(summary)")
        else:
            step = self.script.pop(0) if self.script else _msg("done")
        output = []
        if step.content is not None:
            output.append(SimpleNamespace(
                type="message", role="assistant",
                content=[SimpleNamespace(type="output_text", text=step.content)]))
        for c in step.tool_calls or []:
            output.append(SimpleNamespace(
                type="function_call", id=f"fc_{c.id}", call_id=c.id,
                name=c.function.name, arguments=c.function.arguments))
        return SimpleNamespace(
            output=output, output_text=step.content or "",
            usage=SimpleNamespace(input_tokens=100, output_tokens=10))


async def the_user(session) -> str:
    """The seeded user's id, for tests that call a tool or a script directly
    rather than through a route. The request path proves identity with a token;
    this is the door a test walks around."""
    from sqlalchemy import select

    from app.models.users import User

    return await session.scalar(select(User.id).order_by(User.created_at).limit(1))


async def make_commitment_row(db_session, user, *, month, name, category, amount,
                              repeats=True, due_day=None, source="stated",
                              skipped=False, rolled_from=None, carried_from=None):
    """A commitment written straight to the table, for a month the API will not
    make one in (it makes this month's only) — a past month's for the summary
    tests, or a line rolled from an earlier one."""
    from datetime import UTC, datetime

    from app.models.commitments import Commitment
    row = Commitment(
        id=ulid(), user_id=user, name=name, category=category, amount_paise=amount,
        amount_source=source, local_month=month, due_day=due_day, repeats=repeats,
        skipped_at=datetime.now(UTC) if skipped else None,
        rolled_from_id=rolled_from, carried_from_id=carried_from)
    db_session.add(row)
    await db_session.commit()
    return row
