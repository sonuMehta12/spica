"""
What the agent replies with: typed objects, not a paragraph.

A suggestion can only be kept if it is an object, and a number stays true only
if the card points at the row rather than copying it — the app's live-ids rule.
`spec/chat-cards.md` is the card-by-card contract; `spec/agent.md` § cards is
why there are cards at all.

The model writes prose; the **runner** builds the cards from the tools that
actually ran. That way a `confirm` card cannot describe a write that did not
happen, which is exactly the failure a model asked to emit its own JSON would
produce.

Every string a card carries is UI copy and therefore English. The agent's
prose stays in whatever the user is speaking; the model handles that.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel

Source = Literal["paisa", "diet", "body", "pantry", "people", "places", "memory", "profile",
                 "work", "commitment"]


class AgentCard(BaseModel):
    kind: Literal["agent"] = "agent"
    text: str


class TableCard(BaseModel):
    """Ledger rows, held by **id** so a deletion updates every card. The heading
    leads with the number the rows add up to."""

    kind: Literal["table"] = "table"
    source: Literal["paisa", "diet"]
    heading: str
    ids: list[str]


class Field(BaseModel):
    key: str
    label: str
    value: str
    #: True when the agent worked it out rather than being told, or when the
    #: person gave it as a guess (an approximate weight) — the card draws an
    #: amber dot before it. A guess they gave leaves when an exact value
    #: replaces it, not when it is confirmed.
    guessed: bool = False


class ConfirmCard(BaseModel):
    """A write that happened, with the guessed parts marked so one tap fixes
    them. `lede` leads with what is LEFT, never with what was consumed."""

    kind: Literal["confirm"] = "confirm"
    source: Source
    row_id: str | None
    #: `deleted` renders the lede struck through with no tray — the row is
    #: history, and a card that quietly vanished would leave the user unsure
    #: whether anything happened.
    state: Literal["written", "proposed", "deleted"] = "written"
    lede: str
    fields: list[Field]
    #: Lines the ladder could not resolve. Shown, never guessed at.
    unresolved: list[str] = []
    #: Lines that matched a food but carry no weight — "2 roti" is not two
    #: grams of atta, and forty would be a number the user never said. Their
    #: macros are missing from the total, so the card says so.
    needs_quantity: list[str] = []


class SuggestItem(BaseModel):
    """One thing to eat or do. The display fields are reference values on the
    dish or exercise — carrying them is allowed; a claim about the user is not."""

    type: Literal["dish", "exercise"]
    ref: str
    name: str
    why: str
    saved: bool = False
    meal_type: str | None = None
    minutes: int | None = None
    protein_g: float | None = None
    kcal: int | None = None
    image_url: str | None = None
    missing: list[str] = []
    #: Exercise only.
    exercise_kind: str | None = None
    muscle_group: str | None = None
    tried: int | None = None


class SuggestCard(BaseModel):
    kind: Literal["suggest"] = "suggest"
    items: list[SuggestItem]


class AskCard(BaseModel):
    """One question, and only when the answer changes a number."""

    kind: Literal["ask"] = "ask"
    question: str
    options: list[str] = []
    #: The write the question is holding up, so the card can show which row.
    pending_row_id: str | None = None


class TodosCard(BaseModel):
    """The task list, live. It carries no rows at all — the app draws the
    tasks it already holds, so ticking one anywhere ticks it here too. Sent
    when the agent reads tasks; before, "mere saare tasks dikhao" came back as
    a paragraph of bullets (2026-10-01)."""

    kind: Literal["todos"] = "todos"
    scope: Literal["all"] = "all"
    #: One project's tasks when the question named one; null for all of them.
    project: str | None = None


class CommitmentsCard(BaseModel):
    """What is owed this month, live. It carries no rows: the app draws the
    month's commitments it reads from `GET /commitments`, so an edit or a
    delete anywhere updates every card that showed them, and nothing here is a
    sentence about what is owed. Sent when the agent reads `commitments`."""

    kind: Literal["commitments"] = "commitments"


Card = AgentCard | TableCard | ConfirmCard | SuggestCard | AskCard | TodosCard | CommitmentsCard


def rupees(paise: Any) -> str:
    return f"₹{round((paise or 0) / 100):,}"


def _n(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def _guessed(row: dict) -> bool:
    """A row below full confidence was worked out, not told."""
    conf = row.get("confidence")
    return conf is not None and float(conf) < 1


# ─── builders ────────────────────────────────────────────────────────────────

def _payment(row: dict) -> ConfirmCard:
    return ConfirmCard(
        source="paisa", row_id=row.get("id"),
        lede=f"{rupees(row.get('amount_paise'))} · {row.get('description', '')}",
        fields=[
            Field(key="amount_paise", label="Amount", value=rupees(row.get("amount_paise"))),
            Field(key="category", label="Category", value=str(row.get("category", "")),
                  guessed=_guessed(row)),
            Field(key="description", label="What", value=str(row.get("description", ""))),
            Field(key="local_day", label="Day", value=str(row.get("local_day", ""))),
        ],
    )


def _ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _commitment(result: dict) -> ConfirmCard:
    """A commitment made, changed, skipped or deleted — a write, so a card. The
    lede says what changed; what is owed is always the live figure on the
    page, never a sentence here."""
    name = str(result.get("name") or "Commitment")
    if result.get("deleted"):
        n = result.get("payments_now_ordinary_spending") or 0
        fields = [Field(key="name", label="Commitment", value=name)]
        if n:
            fields.append(Field(key="payments", label="Payments",
                                value=f"{_n(n, 'payment', 'payments')} now count as spending"))
        return ConfirmCard(source="commitment", row_id=result.get("commitment_id"),
                           state="deleted", lede=f"{name} · deleted", fields=fields)
    amount = rupees(result.get("amount_paise"))
    action = result.get("action")
    tail = {"skipped": "not this month", "unskipped": "back on",
            "linked": "payment counted"}.get(action, "every month" if result.get("repeats")
                                             else "this month only")
    fields = [
        Field(key="name", label="Commitment", value=name),
        Field(key="amount_paise", label="Amount", value=amount),
        Field(key="category", label="Category", value=str(result.get("category", "")),
              guessed=action == "made" and not result.get("category_stated")),
    ]
    if result.get("due_day"):
        fields.append(Field(key="due_day", label="Due", value=f"the {_ordinal(result['due_day'])}"))
    fields.append(Field(key="repeats", label="Repeats",
                        value="every month" if result.get("repeats") else "this month only"))
    return ConfirmCard(source="commitment", row_id=result.get("commitment_id"),
                       lede=f"{name} · {amount} · {tail}", fields=fields)


def _meal(result: dict) -> ConfirmCard:
    meal = result.get("meal", {})
    left = result.get("_protein_left")
    # Nothing in the plate had nutrition on file, so the stored zero means
    # "nobody knows", not "no calories". Unknown is not zero.
    known = result.get("nutrition_known", True)
    # The one thing the estimator had to decide that the user did not say.
    # Shown so a wrong portion costs a tap, not a silently wrong day's total.
    assumption = (result.get("assumption") or "").strip()
    protein = meal.get("protein_g", 0)
    if left is not None and known:
        lede = f"{left:g} g protein left"
    elif not known:
        lede = "Logged · macros unknown"
    else:
        lede = f"{float(protein):g} g protein logged"
    # Macros are always derived from the library; the dot marks the ones the
    # ladder was not sure of, which is what `confidence` records.
    guessed = _guessed(meal)
    return ConfirmCard(
        source="diet", row_id=meal.get("id"), lede=lede,
        fields=[
            Field(key="dish", label="What", value=str(meal.get("dish", ""))),
            Field(key="meal_type", label="When", value=str(meal.get("meal_type", ""))),
            Field(key="kcal", label="Calories",
                  value=str(meal.get("kcal", 0)) if known else "—", guessed=guessed),
            Field(key="protein_g", label="Protein",
                  value=f"{float(protein):g} g" if known else "—", guessed=guessed),
            # Carbs and fat when the plate's foods know them. Absent, not zero,
            # when they do not — the honesty rule again.
            *[Field(key=k, label=label, value=f"{float(meal[k]):g} g", guessed=guessed)
              for k, label in (("carbs_g", "Carbs"), ("fat_g", "Fat"))
              if known and meal.get(k) is not None],
            *([Field(key="assumption", label="Assumed", value=assumption, guessed=True)]
              if assumption else []),
        ],
        unresolved=result.get("unresolved", []),
        needs_quantity=result.get("needs_quantity", []),
    )


def _hours(h: float) -> str:
    whole, frac = divmod(float(h), 1)
    return f"{int(whole)} h {int(round(frac * 60))} m" if frac else f"{int(whole)} h"


def _day(result: dict) -> list[Card]:
    """The day's sleep and habit ticks on one card, and the weight on its own.

    A weight is a weigh-in — the row Profile, diet_report and the first run's
    summary read — so its card holds that row's id: Undo deletes the reading,
    and a reading deleted anywhere reaches the card. On the day's card it
    pointed at `days`, where neither could find it."""
    day = result.get("day") or {}
    weigh_in = result.get("weigh_in")
    habits = [h for h in result.get("habits") or [] if h.get("logged")]
    parts: list[str] = []
    fields: list[Field] = []
    if day.get("sleep_hours") is not None:
        parts.append(f"{_hours(day['sleep_hours'])} sleep")
        fields.append(Field(key="sleep_hours", label="Sleep", value=_hours(day["sleep_hours"])))
    for h in habits:
        fields.append(Field(key=f"habit:{h['habit']}", label=h["habit"],
                            value="Ticked"))
    if habits and not parts:
        parts.append(_n(len(habits), "habit ticked", "habits ticked"))
    elif habits:
        parts.append(_n(len(habits), "habit", "habits"))
    cards: list[Card] = []
    if fields:
        cards.append(ConfirmCard(source="body", row_id=day.get("id"), lede=" · ".join(parts),
                                 fields=fields))
    if weigh_in:
        kg = f"{float(weigh_in['weight_kg']):g} kg"
        # Said as a guess ("around 72"): the dot, until an exact reading
        # replaces it.
        cards.append(ConfirmCard(source="body", row_id=weigh_in.get("id"), lede=kg, fields=[
            Field(key="weight_kg", label="Weight", value=kg,
                  guessed=bool(weigh_in.get("estimated")))]))
    return cards


def _habit(result: dict) -> ConfirmCard:
    """Starting, renaming or retiring a habit is a write, so it earns a card
    like any other. Retiring keeps the logs, so the card says the tracking
    stopped, not that the history went."""
    if result.get("deleted"):
        return ConfirmCard(
            source="body", row_id=result.get("habit_id"), state="deleted",
            lede=f"{result.get('name') or 'Habit'} · no longer tracked",
            fields=[Field(key="name", label="Habit", value=str(result.get("name") or ""))],
        )
    way = "build" if result.get("direction") == "build" else "break"
    fields = [Field(key="name", label="Habit", value=str(result.get("name", ""))),
              Field(key="direction", label="Aim", value=way)]
    if result.get("unit"):
        fields.append(Field(key="unit", label="Counts", value=str(result["unit"])))
    # A name already tracked was that habit, left as it was: no write
    # happened, and "tracking build" would claim one — as save_task's twin
    # says "already on the list".
    state = "already tracked" if result.get("already_tracked") else f"tracking {way}"
    return ConfirmCard(
        source="body", row_id=result.get("habit_id"),
        lede=f"{result.get('name', '')} · {state}", fields=fields)


def _project(result: dict) -> ConfirmCard:
    """A project made, changed or retired. Deleting keeps the tasks — they move
    to the default — so the card says where they went."""
    name = str(result.get("name") or "Project")
    if result.get("deleted"):
        n = result.get("tasks_moved_to_default") or 0
        return ConfirmCard(
            source="work", row_id=result.get("project_id"), state="deleted",
            lede=f"{name} · deleted",
            fields=[Field(key="tasks", label="Tasks", value=f"{n} moved to the default project")])
    fields = [Field(key="name", label="Project", value=name)]
    if result.get("description"):
        fields.append(Field(key="description", label="About", value=str(result["description"])))
    if result.get("aliases"):
        fields.append(Field(key="aliases", label="Also", value=", ".join(result["aliases"])))
    verb = ("created" if result.get("created") else
            "archived" if result.get("archived") else "updated")
    return ConfirmCard(source="work", row_id=result.get("project_id"),
                       lede=f"{name} · {verb}", fields=fields)


def _task(result: dict, lede: str) -> ConfirmCard:
    """A task added or changed. A project the model chose carries the dot."""
    fields = [Field(key="project", label="Project", value=str(result.get("project") or ""),
                    guessed=bool(result.get("guessed")))]
    if result.get("due"):
        fields.append(Field(key="due", label="Due", value=str(result["due"])))
    if result.get("priority"):
        fields.append(Field(key="priority", label="Priority", value=f"P{result['priority']}"))
    if result.get("move_in"):
        m = result["move_in"]
        fields.append(Field(key="move_in", label="Next",
                            value=f"move {m.get('ref') or 'it'} forward in "
                                  f"{str(m.get('source') or 'the tracker').title()}"))
    return ConfirmCard(source="work", row_id=result.get("task_id"), lede=lede, fields=fields)


_MOVE = {"purchase": "bought", "opening": "stock take", "consumption": "used",
         "waste": "waste", "correction": "correction"}


def _pantry(result: dict) -> ConfirmCard:
    food, unit = result.get("food", ""), result.get("unit", "")
    qty, kind = result.get("quantity", 0), result.get("kind", "")
    after = result.get("_stock_after")
    lede = (f"{after} {unit} {food} left" if after is not None
            else f"{qty} {unit} {food} {_MOVE.get(kind, kind)}")
    return ConfirmCard(
        source="pantry", row_id=result.get("id"), lede=lede,
        fields=[
            Field(key="food", label="Food", value=str(food)),
            Field(key="quantity", label="Moved", value=f"{qty} {unit}"),
            Field(key="kind", label="Kind", value=_MOVE.get(kind, str(kind))),
        ],
    )


_DIETS = {"veg": "Veg", "nonveg": "Non-veg", "eggetarian": "Eggetarian", "any": "Anything"}

_PROFILE = {
    "protein_g_target": ("Protein target", lambda v: f"{v:g} g"),
    "kcal_target": ("Calorie target", lambda v: f"{int(v)} kcal"),
    "savings_target_paise": ("Savings target", rupees),
    "sleep_target_min": ("Sleep target", lambda v: _hours(v / 60)),
    "step_target": ("Step target", lambda v: f"{int(v):,} steps"),
    "weight_target_kg": ("Weight target", lambda v: f"{float(v):g} kg"),
    "display_name": ("Name", str),
    "gender": ("Gender", lambda v: str(v).capitalize()),
    # Stored at the column's precision (175.3), shown whole.
    "height_cm": ("Height", lambda v: f"{round(float(v))} cm"),
    "city": ("City", str),
    "diet": ("Diet", lambda v: _DIETS.get(v, str(v))),
}


def _profile(result: dict) -> list[Card]:
    if not result:
        return []
    key, value = next(iter(result.items()))
    if key == "dob":
        # A date of birth is shown as an age, never as the date — an age said
        # as "28" is stored as 1 January, and only its year means anything.
        # Keyed `age`, not `dob`: builds that know `dob` draw the live row as
        # a date, and would show the invented 1 January as a birthday.
        age = result.get("age")
        shown = f"{age} years" if age is not None else "—"
        return [ConfirmCard(source="profile", row_id=None, lede=f"Age → {shown}",
                            fields=[Field(key="age", label="Age", value=shown)])]
    label, fmt = _PROFILE.get(key, (key.replace("_", " ").capitalize(), str))
    try:
        shown = fmt(value) if value is not None else "—"
    except (TypeError, ValueError):
        shown = str(value)
    return [ConfirmCard(source="profile", row_id=None, lede=f"{label} → {shown}",
                        fields=[Field(key=key, label=label, value=shown)])]


def _of(shown: int, total: int, one: str, many: str) -> str:
    """`30 of 94 payments` when the rows are a page of the range; `94 payments`
    when they are all of it. The heading must describe the rows under it."""
    return f"{shown} of {_n(total, one, many)}" if total > shown else _n(shown, one, many)


def _table_paisa(args: dict, result: dict) -> list[Card]:
    rows = result.get("rows") or []
    if not rows:
        return []
    # What the rows under the heading add up to — not the range's total, which
    # the agent's own sentence carries and which a 30-row page would misstate.
    # Out and in are counted apart: a salary is not a payment, and summing it
    # with the spending gave a heading that matched nothing on the card.
    out = sum(r.get("amount_paise", 0) for r in rows if r.get("direction") == "debit")
    into = sum(r.get("amount_paise", 0) for r in rows if r.get("direction") == "credit")
    days = result.get("days_in_range")
    if days is None:
        to = date.fromisoformat(args["to"])
        frm = date.fromisoformat(args["from"]) if args.get("from") else to.replace(day=1)
        days = (to - frm).days + 1
    total = result.get("total_matching", len(rows))
    money = f"{rupees(out)} out" + (f", {rupees(into)} in" if into else "")
    what = "row" if into else "payment"
    return [TableCard(source="paisa",
                      heading=f"{money} · {_of(len(rows), total, what, what + 's')}"
                              f" · {_n(days, 'day', 'days')}",
                      ids=[r["id"] for r in rows])]


def _proposed(item: dict) -> ConfirmCard:
    """A guess the batch would not write: state `proposed`, the category
    dotted, the reason beside it. Confirm on the tray or a *haan* in chat
    sends the guess back through correct_payment, which closes the prediction."""
    g = item.get("guess") or {}
    conf = float(g.get("confidence") or 0)
    fields = [Field(key="category", label="Category", value=str(g.get("category", "")),
                    guessed=True)]
    if g.get("description"):
        fields.append(Field(key="description", label="What", value=str(g["description"]),
                            guessed=True))
    fields.append(Field(key="why", label="Why", value=str(g.get("why") or "—")))
    fields.append(Field(key="local_day", label="Day", value=str(item.get("local_day", ""))))
    sure = f" · {conf:.0%} sure" if conf else ""
    return ConfirmCard(
        source="paisa", row_id=item.get("transaction_id"), state="proposed",
        lede=f"{rupees(item.get('amount_paise'))} · {item.get('payee', '')}{sure}",
        fields=fields,
    )


def _categorised(result: dict) -> list[Card]:
    """What the batch did: one table of the rows it wrote, held by id, and a
    proposed card for each it would not decide."""
    out: list[Card] = []
    written = result.get("written") or []
    if written:
        paise = sum(w.get("amount_paise", 0) for w in written)
        out.append(TableCard(source="paisa",
                             heading=f"{rupees(paise)} · "
                                     f"{_n(len(written), 'payment', 'payments')} categorised",
                             ids=[w["transaction_id"] for w in written]))
    # Everything open when the tool provided it, this run's proposals otherwise
    # — a question answered last week is not asked again, and one still open
    # from last night is.
    out.extend(_proposed(p) for p in (result.get("to_review")
                                      or result.get("proposed") or []))
    return out


def _table_diet(result: dict) -> list[Card]:
    rows = result.get("rows") or []
    if not rows:
        return []
    protein = sum(float(r.get("protein_g") or 0) for r in rows)
    total = result.get("total_matching", len(rows))
    return [TableCard(source="diet",
                      heading=f"{protein:g} g protein · {_of(len(rows), total, 'meal', 'meals')}",
                      ids=[r["id"] for r in rows])]


def from_tool(name: str, args: dict, result: dict) -> list[Card]:
    """The cards a completed tool call earns. Every write gets one; a read gets
    a table only when it asked for rows — its numbers belong in the agent's
    own sentence. Suggestions are matched from the prose afterwards, see
    `suggest_from_text`."""
    if result.get("error"):
        return []

    if name == "paisa_report":
        # Rows become a table only when the agent says they were asked to be
        # seen; read to find a number, they are its business (2026-10-10).
        cards: list[Card] = _table_paisa(args, result) if args.get("show") else []
        if "commitments" in (args.get("fields") or []) and result.get("commitments"):
            cards.append(CommitmentsCard())
        return cards + [_proposed(p) for p in result.get("to_review") or []]
    if name == "manage_commitment":
        return [_commitment(result)]
    if name == "categorise_now":
        return _categorised(result)
    if name == "diet_report":
        return _table_diet(result) if args.get("show") else []

    if name in ("log_payment", "correct_payment"):
        return [_payment(result)]
    if name in ("log_meal", "correct_meal"):
        return [_meal(result)]
    if name == "delete_payment":
        card = _payment(result)
        card.state = "deleted"
        return [card]
    if name == "delete_meal":
        return [ConfirmCard(
            source="diet", row_id=result.get("id"), state="deleted",
            lede=f"{result.get('dish', '')} · deleted",
            fields=[
                Field(key="dish", label="What", value=str(result.get("dish", ""))),
                Field(key="meal_type", label="When", value=str(result.get("meal_type", ""))),
                Field(key="local_day", label="Day", value=str(result.get("local_day", ""))),
            ],
        )]
    if name == "log_day":
        return _day(result)
    if name == "manage_habit":
        return [_habit(result)]
    if name == "manage_project":
        return [_project(result)]
    if name == "save_task" and result.get("already"):
        return [_task(result, f"{result.get('title', '')} · already on the list")]
    if name == "save_task" and result.get("added"):
        return [_task(result, f"{result.get('title', '')} · added")]
    if name == "save_task":
        state = ("done" if result.get("status") == "done" else
                 f"moved to {result['moved_to']}" if result.get("moved_to") else
                 "archived" if result.get("archived") else "updated")
        return [_task(result, f"{result.get('title', '')} · {state}")]
    if name == "pantry_move":
        return [_pantry(result)]
    if name == "keep_dish":
        return [ConfirmCard(source="diet", row_id=result.get("dish_id"),
                            lede=f"Saved · {result.get('name', '')}",
                            fields=[Field(key="name", label="Dish",
                                          value=str(result.get("name", "")))])]
    if name == "log_exercise":
        return [ConfirmCard(
            source="body", row_id=result.get("exercise_id"),
            lede=f"{result.get('name', '')} · {result.get('tried', 0)}×",
            fields=[Field(key="name", label="Exercise", value=str(result.get("name", "")))],
        )]
    if name == "file_person":
        who = result.get("relation") or result.get("kind") or "person"
        fields = [Field(key="relation", label="Relation", value=str(result.get("relation") or "—")),
                  Field(key="kind", label="Kind", value=str(result.get("kind") or "—"))]
        if args.get("note"):
            fields.append(Field(key="note", label="Note", value=str(args["note"])))
        return [ConfirmCard(source="people", row_id=result.get("counterparty_id"),
                            lede=f"{result.get('name', '')} · {who}", fields=fields)]
    if name == "save_place":
        fields = [Field(key="kind", label="Kind", value=str(result.get("kind") or "—"))]
        if result.get("payments") is not None:
            fields.append(Field(key="payments", label="Payments",
                                value=_n(int(result["payments"]), "payment", "payments")))
        if result.get("spent_paise"):
            fields.append(Field(key="spent", label="Spent", value=rupees(result["spent_paise"])))
        return [ConfirmCard(source="places", row_id=result.get("place_id"),
                            lede=f"{result.get('name', '')} · {result.get('kind') or 'place'}",
                            fields=fields)]
    if name == "remember":
        return [ConfirmCard(source="memory", row_id=result.get("id"), lede="Remembered",
                            fields=[Field(key="text", label=str(result.get("kind") or "Note"),
                                          value=str(result.get("text", "")))])]
    if name == "update_profile":
        return _profile(result)
    if (name == "work_report" and args.get("show")
            and args.get("status", "open") in ("open", "all")):
        # A finished-tasks question ("aaj kya complete kiya") is answered in the
        # sentence; the live list is for what is still owed.
        return [TodosCard(project=args.get("project") or None)]

    return []


#: Tools whose answer is a suggestion. In a turn that asks for one, a table is
#: never the answer — "what can I eat today" drew the day's diet table under a
#: reply that suggested nothing from it (2026-10-01).
SUGGESTING = frozenset({"suggest_dishes", "dishes_search", "exercises"})


def curate(cards: list[dict], tools: list[str]) -> list[dict]:
    """Drop the cards a turn produced only because the model read something to
    find its way. Every read that asks for rows becomes a card, and the model
    reads before most writes — so "yes it was boiled eggs" came back with a
    paisa table nobody asked about (2026-10-01), and every correction, delete
    and new task came back with a table or the To-do list under it
    (2026-10-09).

    The rule (spec/done/chat-quality.md § What a right reply is): **one
    card for each thing that changed, or for the list that was asked for —
    never for what the agent read on the way.** A turn that wrote shows only
    what it wrote. A suggestion turn shows no table. A turn that only read
    keeps what it read: the table is what was asked for.
    """
    # One task list per turn, however many times the model read tasks — and
    # one table of each kind, the last one read: "last 3 payments" read twice
    # showed two tables (2026-10-10).
    out, listed = [], False
    last_table = {c.get("source"): i for i, c in enumerate(cards) if c.get("kind") == "table"}
    for i, c in enumerate(cards):
        if c.get("kind") == "todos":
            if listed:
                continue
            listed = True
        if c.get("kind") == "table" and last_table.get(c.get("source")) != i:
            continue
        out.append(c)
    wrote = any(c.get("kind") == "confirm" and c.get("state") in ("written", "deleted", None)
                for c in out)
    # A question waiting on them is a card when they asked to review — the
    # categoriser ran. Read in passing, on "mera sab detail do", it was
    # thirteen of them (2026-10-06).
    if "categorise_now" not in tools:
        out = [c for c in out if c.get("state") != "proposed"]
    if wrote:
        return [c for c in out if c.get("kind") == "confirm"]
    if SUGGESTING & set(tools):
        return [c for c in out if c.get("kind") != "table"]
    return out


# ─── suggestions, matched from the prose ─────────────────────────────────────

def _why(c: dict) -> str:
    bits: list[str] = []
    if c.get("missing"):
        bits.append("missing " + ", ".join(c["missing"][:3]))
    elif c.get("cookable_now"):
        bits.append("cookable now")
    if c.get("tried"):
        bits.append(f"had {c['tried']}×")
    ago = c.get("last_had_days_ago")
    if ago is not None:
        bits.append("today" if ago == 0 else f"{_n(int(ago), 'day', 'days')} ago")
    return " · ".join(bits)


def _why_exercise(c: dict) -> str:
    bits = [b for b in (c.get("kind"), c.get("muscle_group"), c.get("equipment")) if b]
    bits.append(f"done {c['tried']}×" if c.get("tried") else "not tried yet")
    return " · ".join(bits)


def _item(c: dict) -> SuggestItem:
    if c.get("_type") == "exercise":
        return SuggestItem(
            type="exercise", ref=c["id"], name=c.get("name", ""), why=_why_exercise(c),
            minutes=c.get("typical_minutes"), image_url=c.get("image_url"),
            exercise_kind=c.get("kind"), muscle_group=c.get("muscle_group"),
            tried=c.get("tried"),
        )
    return SuggestItem(
        type="dish", ref=c.get("dish_id") or c["id"], name=c.get("name", ""),
        why=_why(c), saved=bool(c.get("saved")),
        meal_type=c.get("meal_type"), minutes=c.get("minutes"),
        protein_g=float(c["protein_g"]) if c.get("protein_g") is not None else None,
        kcal=c.get("kcal"), image_url=c.get("image_url"),
        missing=list(c.get("missing") or []),
    )


def suggest_from_text(text: str, candidates: list[dict]) -> list[Card]:
    """The model picks in prose; this finds which of the turn's own candidates
    it named — dishes from `suggest_dishes` / `dishes_search`, exercises from
    `exercises`. Whole-word, case-insensitive, by name or alias; first two in
    order of appearance. The set is closed and small, so this is a lookup,
    not a parse — and it cannot produce a thing the tool did not return."""
    if not text or not candidates:
        return []
    low = text.lower()
    hits: list[tuple[int, dict]] = []
    seen: set[str] = set()
    for c in candidates:
        ref = c.get("dish_id") or c.get("id")
        if not ref or ref in seen:
            continue
        best: int | None = None
        for term in [c.get("name") or "", *(c.get("aliases") or [])]:
            term = term.strip().lower()
            if len(term) < 3:
                continue
            m = re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", low)
            if m and (best is None or m.start() < best):
                best = m.start()
        if best is not None:
            seen.add(ref)
            hits.append((best, c))
    hits.sort(key=lambda h: h[0])
    items = [_item(c) for _, c in hits[:2]]
    return [SuggestCard(items=items)] if items else []
