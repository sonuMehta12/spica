"""
The n2n_eval cases — one day, said in order, and everything that must come back.

The cases are one conversation on one account, in the order below: a morning
hello, a breakfast, a chai, a correction, a thanks, tasks, lunch, habits, and
the questions of an evening. Later turns act on what earlier ones wrote, the
way the app is really used (spec/done/chat-quality.md § The harness).
The account starts from the lived-in week of `fixture.py`; today is left to
the conversation. A case's `given` sentences are said just before it, ungraded.

A case expects, each optional:

- **tools** — what must run (`called`), what must not (`not_called`), that
  nothing may be written at all (`no_writes`), or no tool at all (`no_tools`);
- **cards** — `cards(...)` is the exact set the reply carries, and any other
  card is an *unneeded* card; `card(...)` checks one card's fields;
- **rows** — `row(...)` reads one value after the turn; `delta(...)` reads one
  before and after, so a count says what *this* turn changed, whatever the
  turns before it wrote;
- **the reply, mechanically** — `figure(...)` is a number computed from the
  rows that must appear in it; `reply_has`, `reply_lacks`, `no_markup`.

`must` and `must_not` are not checked by code: they are what Claude looks for
when it reads the reply against the tool results after a run. Keep a check to
what must be true whatever words the model chooses. `why` says where the case
came from: a real turn that went wrong (with its date), or the design. A gap
already written down gets `known=` with where it is written; its failures are
reported and never counted.

`ONBOARDING`, at the end, is not the day: the first run's answers, each case on
an account just signed in and said to `POST /onboarding/turn` with its
`question` — the block the onboarding agent is checked by
(spec/done/onboarding-goals.md § Definition of done).
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from sqlalchemy import text

#: The tools that only read. Everything else writes something. `next_question`
#: neither reads nor writes: it tells the first run's screen to move on.
READS = frozenset({"paisa_report", "diet_report", "suggest_dishes", "dishes_search",
                   "exercises", "work_report", "people", "places", "next_question"})


@dataclass
class Turn:
    """What the turn under test produced."""

    reply: str
    cards: list[dict]
    #: Every tool call: `tool`, `args`, `ok`, `error`, and `result`.
    tools: list[dict]
    session: Any
    user: str
    today: date
    #: What each check read before the turn, by the check's `key`.
    pre: dict = field(default_factory=dict)
    #: The first run's `next`: the agent called `next_question` and the screen
    #: moves on. None on a chat turn.
    next: bool | None = None


@dataclass
class Check:
    #: What it asserts, in words — shown in the review beside the verdict.
    says: str
    fn: Callable[[Turn], Awaitable[str | None]]
    #: Read before the turn, for a check about what the turn changed. Its
    #: result is in `Turn.pre[key]` when `fn` runs.
    prep: Callable[[Turn], Awaitable[Any]] | None = None
    key: str = ""

    async def __call__(self, t: Turn) -> str | None:
        return await self.fn(t)


@dataclass
class Case:
    id: str
    group: str
    say: str
    checks: list[Check] = field(default_factory=list)
    given: list[str] = field(default_factory=list)
    must: list[str] = field(default_factory=list)
    must_not: list[str] = field(default_factory=list)
    why: str = "design"
    known: str | None = None
    #: The clock this turn is said at, HH:MM. Cases without one are spaced
    #: evenly between the ones that have it, so the day keeps its order and the
    #: run never depends on the hour it happens to be started.
    at: str | None = None
    #: The first run's question this is an answer to — about, place, health,
    #: money, habits. Set, the case goes to `POST /onboarding/turn` on an
    #: account just signed in, never to the chat, and its `given` are earlier
    #: answers to the same question.
    question: str | None = None
    #: State made through the API before anything is said, by name in
    #: `fixture.SEEDS` — for a fact the case must not leave to a model's turn.
    seed: str | None = None


# ─── tools ───────────────────────────────────────────────────────────────────

def _ran(t: Turn) -> list[str]:
    return [x["tool"] for x in t.tools if x.get("ok")]


def called(*names: str) -> Check:
    async def fn(t: Turn) -> str | None:
        ran = _ran(t)
        if set(names) & set(ran):
            return None
        return f"expected {' or '.join(names)}; ran {ran or 'nothing'}"
    return Check(f"runs {' or '.join(names)}", fn)


def not_called(*names: str) -> Check:
    async def fn(t: Turn) -> str | None:
        hit = [n for n in names if n in _ran(t)]
        return f"must not run {', '.join(hit)}" if hit else None
    return Check(f"does not run {', '.join(names)}", fn)


def no_writes() -> Check:
    """Nothing written — not even an attempt. A question, a greeting or a thanks."""
    async def fn(t: Turn) -> str | None:
        hit = [f"{x['tool']}({_short(x.get('args'))})" for x in t.tools if x["tool"] not in READS]
        return f"wrote on a turn that asked for nothing: {', '.join(hit)}" if hit else None
    return Check("writes nothing", fn)


def no_tools() -> Check:
    async def fn(t: Turn) -> str | None:
        ran = [x["tool"] for x in t.tools]
        return f"ran {ran} on a turn that needs no data" if ran else None
    return Check("runs no tool", fn)


def _short(args: Any) -> str:
    s = ", ".join(f"{k}={v!r}" for k, v in (args or {}).items())
    return s if len(s) < 80 else s[:77] + "…"


# ─── cards ───────────────────────────────────────────────────────────────────

def _label(c: dict) -> str:
    s = c.get("kind", "?")
    if c.get("source"):
        s += "/" + c["source"]
    if c.get("kind") == "confirm" and c.get("state", "written") != "written":
        s += ":" + c["state"]
    return s


def _fits(spec: str, c: dict) -> bool:
    kind, _, rest = spec.partition("/")
    source, _, state = rest.partition(":")
    if c.get("kind") != kind:
        return False
    if source and c.get("source") != source:
        return False
    if state and c.get("state", "written") != state:
        return False
    if not state and kind == "confirm" and c.get("state", "written") != "written":
        return False
    return True


def cards(*specs: str) -> Check:
    """The exact set of cards: `confirm/paisa`, `confirm/paisa:deleted`,
    `table/diet`, `todos`, `suggest`. `cards()` is no card at all. A card the
    case did not list is an unneeded card."""
    async def fn(t: Turn) -> str | None:
        pool = [c for c in t.cards if c.get("kind") != "agent"]
        missing = []
        for spec in specs:
            hit = next((c for c in pool if _fits(spec, c)), None)
            if hit is None:
                missing.append(spec)
            else:
                pool.remove(hit)
        why = []
        if missing:
            why.append(f"missing {', '.join(missing)}")
        if pool:
            why.append(f"unneeded {', '.join(_label(c) for c in pool)}")
        return "; ".join(why) or None
    return Check(f"cards: {', '.join(specs) if specs else 'none'}", fn)


def no_card(kind: str, source: str | None = None) -> Check:
    async def fn(t: Turn) -> str | None:
        hit = [_label(c) for c in t.cards if c.get("kind") == kind
               and (source is None or c.get("source") == source)]
        return f"unneeded {', '.join(hit)}" if hit else None
    return Check(f"no {kind}{'/' + source if source else ''} card", fn)


def card(spec: str, lede: str | None = None, **fields: str) -> Check:
    """One card of this spec whose lede and fields match these regexes."""
    async def fn(t: Turn) -> str | None:
        pool = [c for c in t.cards if _fits(spec, c)]
        if not pool:
            return f"no {spec} card"
        for c in pool:
            if lede and not re.search(lede, c.get("lede", ""), re.I):
                continue
            vals = {f["key"]: f["value"] for f in c.get("fields", [])}
            if all(re.search(rx, str(vals.get(k, "")), re.I) for k, rx in fields.items()):
                return None
        c = pool[0]
        return (f"{spec} card does not match: lede {c.get('lede')!r}, fields "
                f"{ {f['key']: f['value'] for f in c.get('fields', [])} }")
    want = ", ".join([f"lede ~ {lede}"] if lede else [] + [f"{k} ~ {v}" for k, v in fields.items()])
    return Check(f"a {spec} card{' with ' + want if want else ''}", fn)


# ─── rows ────────────────────────────────────────────────────────────────────

def _params(t: Turn) -> dict:
    return {"u": t.user, "today": t.today, "yesterday": t.today - timedelta(days=1),
            "week_ago": t.today - timedelta(days=6),
            "tomorrow": t.today + timedelta(days=1), "day_after": t.today + timedelta(days=2)}


async def _value(t: Turn, sql: str) -> Any:
    got = (await t.session.execute(text(sql), _params(t))).first()
    return got[0] if got is not None and len(got) == 1 else got


def row(sql: str, expect: Callable[[Any], bool], says: str) -> Check:
    """One value read back after the turn. `:u` is the account, `:today`,
    `:yesterday`, `:tomorrow`, `:day_after` and `:week_ago` (six days back —
    "is hafte" is the seven days ending today) the days around the run."""
    async def fn(t: Turn) -> str | None:
        value = await _value(t, sql)
        return None if expect(value) else f"{says} (got {value!r})"
    return Check(says, fn)


_delta_n = 0


def delta(sql: str, change: float, says: str) -> Check:
    """A count read before the turn and after it: what this turn changed,
    whatever the conversation wrote before it."""
    global _delta_n
    _delta_n += 1
    key = f"delta-{_delta_n}"

    async def prep(t: Turn) -> Any:
        return await _value(t, sql)

    async def fn(t: Turn) -> str | None:
        before, after = float(t.pre.get(key) or 0), float(await _value(t, sql) or 0)
        if abs((after - before) - change) < 1e-6:
            return None
        return f"{says} (changed by {after - before:+g}, expected {change:+g})"
    return Check(says, fn, prep=prep, key=key)


# ─── the reply ───────────────────────────────────────────────────────────────

_MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august",
           "september", "october", "november", "december"]


def says_today() -> Check:
    """The reply names today: its day of the month, and the month by name or
    number."""
    async def fn(t: Turn) -> str | None:
        r = (t.reply or "").lower()
        day = re.search(rf"\b0?{t.today.day}\b", r)
        month = _MONTHS[t.today.month - 1]
        named = month in r or month[:3] in r or re.search(rf"\b0?{t.today.month}\b", r)
        return None if day and named else f"today, {t.today.isoformat()}, is not in the reply"
    return Check("names today's date", fn)


_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _numbers(s: str) -> set[float]:
    out = set()
    for m in _NUM.findall(s or ""):
        try:
            out.add(float(m.replace(",", "")))
        except ValueError:
            pass
    # "16k", "1.2k", "1 lakh" — the person's own ways of saying a figure
    for m in re.findall(r"(\d+(?:\.\d+)?)\s?k\b", s or "", re.I):
        out.add(float(m) * 1000)
    return out


def figure(sql: str, says: str, paise: bool = False) -> Check:
    """A number worked out from the seeded rows with SQL appears in the reply —
    in rupees when `paise`. The answer to a question about the person's own
    data is that number, and nothing else will do."""
    async def fn(t: Turn) -> str | None:
        value = await _value(t, sql)
        if value is None:
            return f"{says}: the check's own query found nothing"
        want = round(float(value) / 100, 2) if paise else round(float(value), 1)
        have = _numbers(t.reply)
        if any(abs(n - want) < 0.51 for n in have):
            return None
        shown = f"₹{want:,.0f}" if paise else f"{want:g}"
        return f"{says}: expected {shown} in the reply"
    return Check(says, fn)


def reply_has(pattern: str, says: str) -> Check:
    async def fn(t: Turn) -> str | None:
        return None if re.search(pattern, t.reply or "", re.I) else f"{says}: {t.reply[:120]!r}"
    return Check(says, fn)


def reply_lacks(pattern: str, says: str) -> Check:
    async def fn(t: Turn) -> str | None:
        m = re.search(pattern, t.reply or "", re.I)
        return f"{says}: found {m.group(0)!r}" if m else None
    return Check(says, fn)


def no_list() -> Check:
    """The card shows the list; the sentence does not type it out again."""
    async def fn(t: Turn) -> str | None:
        items = re.findall(r"(?m)^\s*(?:[-•*]|\d+[.)])\s+\S", t.reply or "")
        return f"the reply types out a list of {len(items)} the card already shows" \
            if len(items) >= 3 else None
    return Check("a summary, not the list again", fn)


def no_markup() -> Check:
    """No code block, no JSON, no hand-made widget: cards are the server's job."""
    async def fn(t: Turn) -> str | None:
        r = t.reply or ""
        if "```" in r or re.search(r"^\s*[\[{]", r) or re.search(r'"type"\s*:', r):
            return "the reply carries markup — a code block or JSON — instead of prose"
        return None
    return Check("prose, no code block or JSON", fn)


# ─── SQL the cases share ─────────────────────────────────────────────────────

def tx(where: str, col: str) -> str:
    return (f"SELECT {col} FROM transactions WHERE user_id = :u AND deleted_at IS NULL "
            f"AND {where} ORDER BY created_at DESC LIMIT 1")


def tx_count(where: str) -> str:
    return ("SELECT count(*) FROM transactions WHERE user_id = :u AND deleted_at IS NULL "
            f"AND {where}")


def meals(where: str) -> str:
    return f"SELECT count(*) FROM meal_logs WHERE user_id = :u AND deleted_at IS NULL AND {where}"


def habit_today(name: str) -> str:
    return ("SELECT coalesce(sum(coalesce(l.amount, 1)), 0) FROM habit_logs l JOIN habits h "
            "ON h.id = l.habit_id WHERE l.user_id = :u AND l.local_day = :today AND "
            f"h.name ILIKE '{name}%' AND l.deleted_at IS NULL")


def task(where: str, col: str) -> str:
    return (f"SELECT {col} FROM tasks WHERE user_id = :u AND deleted_at IS NULL AND {where} "
            "ORDER BY created_at LIMIT 1")


def task_count(where: str) -> str:
    return f"SELECT count(*) FROM tasks WHERE user_id = :u AND deleted_at IS NULL AND {where}"


SPENT_TODAY = ("SELECT sum(amount_paise) FROM transactions WHERE user_id = :u AND deleted_at "
               "IS NULL AND local_day = :today AND direction = 'debit' AND kind = 'expense'")
FOOD_WEEK = ("SELECT sum(amount_paise) FROM transactions WHERE user_id = :u AND deleted_at IS "
             "NULL AND category = 'Khana/Grocery' AND local_day >= :week_ago")
PROTEIN_LEFT = ("SELECT u.protein_g_target - coalesce(sum(m.protein_g), 0) FROM users u LEFT "
                "JOIN meal_logs m ON m.user_id = u.id AND m.local_day = :today AND "
                "m.deleted_at IS NULL WHERE u.id = :u GROUP BY u.protein_g_target")
OPEN_TASKS = ("SELECT count(*) FROM tasks WHERE user_id = :u AND deleted_at IS NULL AND "
              "archived_at IS NULL AND status <> 'done'")

UDHAAR_AMIT = (
    "SELECT (SELECT coalesce(sum(amount_paise), 0) FROM transactions WHERE user_id = :u AND "
    "deleted_at IS NULL AND kind = 'lent' AND counterparty_name ILIKE 'amit%') - (SELECT "
    "coalesce(sum(r.amount_paise), 0) FROM transactions r JOIN transactions l ON l.id = "
    "r.settles_id WHERE r.user_id = :u AND r.deleted_at IS NULL AND r.kind = 'repayment' AND "
    "l.counterparty_name ILIKE 'amit%')")
ALL_TX = "SELECT count(*) FROM transactions WHERE user_id = :u AND deleted_at IS NULL"
ALL_TASKS = "SELECT count(*) FROM tasks WHERE user_id = :u AND deleted_at IS NULL"
ALL_MEALS = "SELECT count(*) FROM meal_logs WHERE user_id = :u AND deleted_at IS NULL"
ALL_HABIT_LOGS = "SELECT count(*) FROM habit_logs WHERE user_id = :u AND deleted_at IS NULL"
MEMORIES = "SELECT count(*) FROM memories WHERE user_id = :u AND deleted_at IS NULL"
DONE_TASKS = ("SELECT count(*) FROM tasks WHERE user_id = :u AND deleted_at IS NULL "
              "AND status = 'done'")


def nothing_written() -> list[Check]:
    """A turn that asked for nothing leaves every ledger as it found it."""
    return [no_writes(), no_markup(),
            delta(ALL_TX, 0, "no payment written"), delta(ALL_MEALS, 0, "no meal written"),
            delta(ALL_TASKS, 0, "no task written"), delta(DONE_TASKS, 0, "no task ticked"),
            delta(ALL_HABIT_LOGS, 0, "no habit ticked"), delta(MEMORIES, 0, "no memory written")]


# ─── the day, in order ───────────────────────────────────────────────────────

CASES: list[Case] = [

    # ── Morning ─────────────────────────────────────────────────────────────
    Case("hi", "talk", "hi", [*nothing_written(), cards()], at="08:00",
         must=["greets back, briefly, with no numbers nobody asked for"],
         why="real · 09-30 — a greeting's task count was wrong"),
    Case("date", "talk", "aaj kya date hai?", [*nothing_written(), no_tools(), cards(),
                                              says_today()]),
    Case("meal", "food", "breakfast mein 3 boiled eggs khaye", [
        called("log_meal"), cards("confirm/diet"),
        delta(meals("local_day = :today AND meal_type ILIKE 'breakfast'"), 1, "one breakfast"),
    ]),
    Case("meal-followup", "food", "haan boiled hi the", [
        not_called("log_meal"), no_card("table"),
        delta(ALL_MEALS, 0, "still one breakfast, not two"),
    ], why="real · 10-01 — brought a paisa table"),
    Case("pay-log", "money", "chai 20", at="09:00", checks=[
        called("log_payment"), cards("confirm/paisa"),
        delta(tx_count("description ILIKE '%chai%' AND local_day = :today"), 1, "one chai"),
    ]),
    Case("pay-auto", "money", "auto 80", [
        called("log_payment"), cards("confirm/paisa"),
        row(tx("amount_paise = 8000 AND local_day = :today", "category"),
            lambda v: v == "Transport", "an auto is Transport, never food"),
    ], why="real · 10-01"),
    Case("thanks", "talk", "thanks", [*nothing_written(), cards()],
         must=["a short acknowledgement and nothing else"],
         why="real · 10-08 — logged the payment again"),
    Case("pay-fix", "money", "chai 25 ki thi", [
        called("correct_payment"), not_called("log_payment"), cards("confirm/paisa"),
        delta(tx_count("description ILIKE '%chai%'"), 0, "corrected, not a second chai"),
        row(tx("description ILIKE '%chai%' AND local_day = :today", "amount_paise"),
            lambda v: v == 2500, "the chai is ₹25"),
    ], why="real · 10-01"),
    Case("pay-recat", "money", "amazon wala Ghar category mein daal do", [
        called("correct_payment"), not_called("log_payment"), cards("confirm/paisa"),
        row(tx("description ILIKE '%amazon%' AND local_day = :today", "category"),
            lambda v: v == "Ghar", "today's Amazon is Ghar"),
        row(tx("description ILIKE '%amazon%' AND local_day < :today", "category"),
            lambda v: v == "Shopping", "last week's Amazon is untouched"),
    ], given=["amazon 1200"], why="real · 10-01 — the correction's lookup showed a table"),
    Case("pay-del", "money", "auto wala delete kar do", [
        called("delete_payment"), cards("confirm/paisa:deleted"),
        delta(tx_count("description ILIKE '%auto%'"), -1, "the auto is gone"),
        delta(tx_count("description ILIKE '%uber%'"), 0, "the Uber is not"),
    ], why="real · 10-01 — brought a table"),
    Case("habit-count", "body", "aaj 2 cigarette pi", [
        called("log_day"), cards("confirm/body"),
        delta(habit_today("cigarette"), 2, "two cigarettes today"),
        delta(ALL_TX, 0, "no payment with it"),
    ]),
    Case("pay-cig", "money", "spent 25 on cigarette", [
        called("log_payment"), called("log_day"), cards("confirm/paisa", "confirm/body"),
        row(tx("amount_paise = 2500 AND local_day = :today", "category"),
            lambda v: v not in ("Khana/Grocery", "Health/Diet"),
            "a cigarette is not food and not health"),
        delta(habit_today("cigarette"), 1, "one cigarette smoked, inferred from the price"),
    ], must=["says it counted one cigarette too"],
       why="real · 10-01, 10-09; one sentence, two facts — decided 2026-10-09"),
    Case("pay-no-amount", "money", "grocery pe bhi kharcha kiya aaj", [
        *nothing_written(), cards(),
    ], must=["asks how much it was"], must_not=["claims anything was logged"]),
    Case("spent-today", "money-read", "aaj kitna kharcha hua?", [
        *nothing_written(), cards(), figure(SPENT_TODAY, "today's spend", paise=True),
    ]),
    Case("pay-k", "money", "16k ki shopping ki — RO, pressure cooker aur kuch aur cheezein", [
        called("log_payment"), cards("confirm/paisa"),
        row(tx("amount_paise = 1600000", "category"), lambda v: v == "Shopping",
            "₹16,000 of shopping"),
    ], why="real · 10-08"),
    Case("biryani", "money", "Swiggy se biryani mangayi 350", [
        called("log_payment"), not_called("log_meal"), cards("confirm/paisa"),
        delta(ALL_MEALS, 0, "no meal until they say they ate it"),
    ], must=["asks whether they ate the biryani before logging a meal"],
       why="decided 2026-10-09 — food is asked about, not inferred"),
    Case("pay-yesterday", "money", "kal Uber 310 ka tha, wo bhi daal do", [
        called("log_payment"), cards("confirm/paisa"),
        row(tx("amount_paise = 31000", "local_day = :yesterday"), lambda v: v is True,
            "logged on yesterday, not today"),
    ]),
    Case("pay-fix-amount", "money", "90k sorry", [
        called("correct_payment"), not_called("log_payment"), cards("confirm/paisa"),
        delta(tx_count("category = 'Salary'"), 0, "corrected, not a second salary"),
        row(tx("category = 'Salary' AND local_day = :today", "amount_paise"),
            lambda v: v == 9000000, "the salary is ₹90,000"),
    ], given=["90 salary credit hui"], why="real · 10-01"),
    Case("lent", "money", "Priya ko 3000 udhaar diye", [
        called("log_payment"), cards("confirm/paisa"),
        row(tx("amount_paise = 300000", "kind"), lambda v: v == "lent", "a lending"),
    ], why="real · 10-01 — filed as income"),
    Case("repaid", "money", "Amit ne 1500 wapas kar diye", [
        called("log_payment"), cards("confirm/paisa"),
        delta(tx_count("kind = 'repayment' AND settles_id IS NOT NULL"), 1,
              "a repayment that settles Amit's lending"),
    ]),
    Case("borrowed", "money", "Rohit se 2000 udhaar liye", [
        called("log_payment"), cards("confirm/paisa"),
        row(tx("amount_paise = 200000", "kind"), lambda v: v == "borrowed", "a borrowing"),
    ]),
    Case("udhaar", "money-read", "Amit pe ab kitna baaki hai?", [
        *nothing_written(), cards(), figure(UDHAAR_AMIT, "what Amit still owes", paise=True),
    ]),
    Case("target", "money", "savings target 15000 kar do", [
        called("update_profile"), cards("confirm/profile"),
        row("SELECT savings_target_paise FROM users WHERE id = :u", lambda v: v == 1500000,
            "the target is ₹15,000"),
    ]),

    # ── Paisa: questions ────────────────────────────────────────────────────
    Case("food-week", "money-read", "is hafte khane pe kitna gaya?", at="11:30", checks=[
        *nothing_written(), called("paisa_report"), cards(),
        figure(FOOD_WEEK, "food over the last seven days", paise=True),
    ]),
    Case("spent-month", "money-read", "is mahine kitna kharcha hua?", [
        *nothing_written(), called("paisa_report"), cards(),
    ], must=["one total for the month, the figure the tool returned"]),
    Case("left", "money-read", "is mahine kitna bacha hai?", [
        *nothing_written(), called("paisa_report"), cards(),
    ], must=["what is left, as the tool returned it"],
       must_not=["adds or subtracts figures itself to get what is left"]),
    Case("payments-week", "money-read", "is hafte ki payments dikhao", [
        *nothing_written(), called("paisa_report"), cards("table/paisa"), no_list(),
    ], must_not=["reads every payment out in the sentence — the table shows them"],
       why="real · 10-08"),
    Case("last-three", "money-read", "last 3 payments dikhao", [
        *nothing_written(), called("paisa_report"), cards("table/paisa"),
    ]),
    Case("doubtful", "money-read", "aaj ke doubtful payments dekh lo", [
        no_markup(), called("categorise_now", "paisa_report"),
    ], must=["names the ₹300 UPI payment it is unsure of, or what it did with it"],
       why="real · 10-01 — said 0 pending and named one in the same reply"),
    Case("no-data", "money-read", "pichle saal diwali pe kitna kharcha hua tha?", [
        *nothing_written(), cards(),
    ], must=["says there is no data for then"], must_not=["gives a figure"]),

    # ── Kaam ────────────────────────────────────────────────────────────────
    Case("due-today", "work-read", "aaj kya due hai?", at="12:00", checks=[
        *nothing_written(), called("work_report"),
        reply_has(r"hallucination", "names the chat hallucinations task"),
    ]),
    Case("late", "work-read", "kaunse tasks late hain?", [
        *nothing_written(), called("work_report"), reply_has(r"grafana", "names Grafana"),
    ]),
    Case("task-add", "work", "create a task that tomorrow I have to work on db migration", [
        called("save_task"), cards("confirm/work"),
        delta(task_count("title ILIKE '%migration%'"), 1, "one migration task"),
        row(task("title ILIKE '%migration%'", "due = :tomorrow"), lambda v: v is True,
            "due tomorrow"),
    ], why="real · 10-08 — a lookup brought the To-do card along"),
    Case("task-dup", "work", "create a task that tomorrow I have to work on db migration", [
        cards("confirm/work"),
        delta(ALL_TASKS, 0, "still one migration task"),
    ], must_not=["claims it changed the task — it was already there"], why="real · 10-01"),
    Case("task-move", "work", "db migration wala task parso pe daal do", [
        called("save_task"), cards("confirm/work"),
        row(task("title ILIKE '%migration%'", "due = :day_after"), lambda v: v is True,
            "due the day after tomorrow"),
    ]),
    Case("theek", "talk", "theek hai", [*nothing_written(), cards()],
         why="real · 10-08 — marked a task done"),
    Case("task-done", "work", "grafana wala task ho gaya", [
        called("save_task"), cards("confirm/work"),
        row(task("title ILIKE 'grafana%'", "status"), lambda v: v == "done", "Grafana is done"),
        delta(DONE_TASKS, 1, "and nothing else was ticked"),
    ]),
    Case("project", "work", "Garden naam ka project bana do", [
        called("manage_project"), cards("confirm/work"),
    ]),
    Case("task-in", "work", "PersonaOS mein task add karo: onboarding copy likhna", [
        called("save_task"), cards("confirm/work"),
        row("SELECT p.name FROM tasks t JOIN projects p ON p.id = t.project_id WHERE "
            "t.user_id = :u AND t.title ILIKE '%onboarding%'", lambda v: v == "PersonaOS",
            "in PersonaOS"),
    ]),
    Case("todos", "work-read", "mere saare tasks dikhao", [
        *nothing_written(), called("work_report"), cards("todos"), no_list(),
    ], must_not=["reads every task out in the sentence — the card shows them",
                 "a count that does not match the tool's result"], why="real · 10-01"),
    Case("show-ui", "talk", "ui mein dikhao", [*nothing_written()],
         why="real · 10-01 — wrote a ```ui block"),
    Case("project-tasks", "work-read", "PersonaOS ke tasks dikhao", [
        *nothing_written(), called("work_report"), cards("todos"), no_list(),
    ], must_not=["names another project's task as PersonaOS's"]),
    Case("projects", "work-read", "mere projects kaun se hain?", [
        *nothing_written(), cards(),
        reply_has(r"personaos", "names PersonaOS"), reply_has(r"novacart", "names Novacart"),
    ], why="real · 10-01"),
    Case("done-today", "work-read", "aaj kya complete kiya?", [
        *nothing_written(), reply_has(r"grafana", "names Grafana"),
    ]),
    Case("acha", "talk", "acha", [*nothing_written(), no_tools(), cards()],
         why="real · 10-08 — read the task list"),

    # ── Lunch, and food questions ───────────────────────────────────────────
    Case("meal-gaps", "food", "lunch mein 2 roti, dal, achaar aur thoda salad", at="13:30", checks=[
        called("log_meal"), cards("confirm/diet"),
        delta(meals("local_day = :today AND meal_type ILIKE 'lunch'"), 1, "one lunch"),
    ]),
    Case("meal-fix", "food", "dal ek katori thi", [
        called("correct_meal"), not_called("log_meal"), cards("confirm/diet"),
        delta(ALL_MEALS, 0, "corrected, not a second lunch"),
    ], why="real · 10-01"),
    Case("meal-clarify", "food", "roti 40 gram atta ki thi, salad mein bas onion aur kheera", [
        not_called("log_meal"), delta(ALL_MEALS, 0, "still one lunch"),
    ], why="real · 10-01 — logged lunch again"),
    Case("meal-dispute", "food", "itna protein nahi hota chole bhature mein", [
        not_called("log_meal"), delta(ALL_MEALS, 0, "no meal added"),
    ], given=["shaam ko chole bhature khaye"], why="real · 10-09"),
    Case("meal-del", "food", "breakfast wala delete kar do", [
        called("delete_meal"), cards("confirm/diet:deleted"),
        delta(meals("local_day = :today AND meal_type ILIKE 'breakfast'"), -1,
              "today's breakfast is gone"),
    ], why="real · 10-01 — brought a diet table"),
    Case("meal-yesterday", "food", "kal raat dinner mein dal chawal khaya tha", [
        called("log_meal"), cards("confirm/diet"),
        delta(meals("local_day = :yesterday AND meal_type ILIKE 'dinner'"), 1,
              "yesterday's dinner"),
    ]),
    Case("pay-log-2", "money", "chai 20", [
        called("log_payment"), not_called("correct_payment"), cards("confirm/paisa"),
        delta(tx_count("description ILIKE '%chai%' AND local_day = :today"), 1,
              "a second chai, not a change to the morning's"),
    ], why="the 10-09 baseline: a second chai was taken for a correction"),
    Case("eaten-today", "food-read", "aaj kya kya khaya?", at="15:30", checks=[
        *nothing_written(), called("diet_report"), cards("table/diet"),
    ]),
    Case("protein-left", "food-read", "aaj kitna protein baaki hai?", [
        *nothing_written(), cards(), figure(PROTEIN_LEFT, "protein still to go today"),
    ]),
    Case("suggest", "food-read", "dinner mein kya khaun?", [
        *nothing_written(), called("suggest_dishes", "dishes_search"), no_card("table"),
    ], must=["dishes the tool returned, with their real protein"]),
    Case("suggest-again", "food-read", "ek aur option do", [
        *nothing_written(), no_card("table"),
    ], must=["any protein still to go matches the tools' figure this turn"],
       why="real · 10-01 — 122 g left, then 63 g, nothing logged between"),
    Case("pantry", "food-read", "pantry mein kya hai?", [
        *nothing_written(), called("diet_report"),
    ], must=["names atta, eggs and soya chunks"]),
    Case("stock", "food", "200g paneer laya", [
        called("pantry_move"), not_called("log_meal"), cards("confirm/pantry"),
    ], why="real · 10-01, and the 10-09 baseline: read as eaten"),
    Case("dish-save", "food", "masala oats ki recipe save kar lo", [
        called("keep_dish"), cards("confirm/diet"),
        row("SELECT coalesce(d.kcal, -1) FROM dishes d JOIN dish_saves s ON s.dish_id = d.id "
            "WHERE s.user_id = :u AND d.name ILIKE '%oats%' LIMIT 1", lambda v: v != 0,
            "unknown nutrition is left unknown, never written as 0"),
    ], why="real · 10-01 — saved with 0 kcal and 0 g"),

    # ── Habits, sleep, workouts ─────────────────────────────────────────────
    Case("habit-new", "body", "meditation track karna shuru karo", at="18:30", checks=[
        called("manage_habit"), cards("confirm/body"),
    ]),
    Case("habit-stop", "body", "meditation track karna band karo", [
        called("manage_habit"), cards("confirm/body:deleted"),
        delta(ALL_HABIT_LOGS, 0, "no habit ticked on the way"),
    ], why="real · 10-01 — stopping meditation logged two cigarettes"),
    Case("habit-start", "body", "yoga bhi track karo", [
        called("manage_habit"), cards("confirm/body"),
        row("SELECT count(*) FROM habits WHERE user_id = :u AND name ILIKE 'yoga%' AND "
            "deleted_at IS NULL", lambda v: v == 1, "yoga is tracked"),
    ], must_not=["asks whether to start it — they said to"],
       why="the 10-09 baseline: asked instead of starting it"),
    Case("habit-add-log", "body", "aaj yoga kiya, log kar do", [
        called("log_day"), cards("confirm/body"),
        delta(habit_today("yoga"), 1, "today's yoga is ticked"),
        delta(habit_today("cigarette"), 0, "and no cigarette with it"),
    ], why="real · 10-08 — ticked two habits"),
    Case("habit-tick", "body", "aaj workout kiya", [
        called("log_day"), cards("confirm/body"),
        delta(habit_today("workout"), 1, "today's workout is ticked"),
        delta(habit_today("cigarette"), 0, "and nothing else"),
    ]),
    Case("habits-which", "body", "kaun si habits track ho rahi hain?", [
        *nothing_written(), reply_has(r"cigarette", "names Cigarette"),
        reply_has(r"workout", "names Workout"),
    ], why="real · 10-08 — said none were tracked, and ticked one"),
    Case("day", "body", "6.5 ghante soya, weight 71.2", [
        called("log_day"),
        row("SELECT sleep_hours FROM days WHERE user_id = :u AND local_day = :today",
            lambda v: v is not None and abs(float(v) - 6.5) < 0.01, "6.5 hours of sleep"),
    ]),
    Case("sleep-fix", "body", "sorry 7 ghante soya tha", [
        called("log_day"),
        row("SELECT sleep_hours FROM days WHERE user_id = :u AND local_day = :today",
            lambda v: v is not None and abs(float(v) - 7) < 0.01, "7 hours now"),
        row("SELECT weight_kg FROM days WHERE user_id = :u AND local_day = :today",
            lambda v: v is not None and abs(float(v) - 71.2) < 0.01, "the weight kept"),
    ]),
    Case("weight-read", "body", "last time weight kitna tha?", [
        *nothing_written(), cards(), reply_has(r"\b71(\.[02])?\b", "says 71.2 or 71 kg"),
    ]),
    Case("workouts", "body", "legs ke liye kya karu? 20 minute hai", [
        *nothing_written(), called("exercises"), no_card("table"),
    ], must=["suggests goblet squats or walking lunges from the library"],
       why="real · 10-01 — said nothing in the library fit"),
    Case("exercise", "body", "aaj goblet squat kiya", [
        called("log_exercise"), cards("confirm/body"),
    ]),

    # ── People, places, memory ──────────────────────────────────────────────
    Case("cig-pack", "money", "cigarette ka packet liya, 350 ka", [
        called("log_payment"), cards("confirm/paisa"),
        delta(habit_today("cigarette"), 0, "a packet is not a cigarette smoked"),
    ], must=["asks how many they smoked today, or whether to count any"],
       why="decided 2026-10-09 — the unclear second fact is asked about"),
    Case("person", "people", "Mohan Lal mera dost hai", at="20:00", checks=[
        called("file_person"), cards("confirm/people"),
    ]),
    Case("people-read", "people", "Amit ke saath kya hisaab hai?", [
        *nothing_written(), called("people", "paisa_report"), cards(),
        figure(UDHAAR_AMIT, "what Amit still owes", paise=True),
    ]),
    Case("places-read", "people", "Blue Tokai pe kitna kharcha hua hai?", [
        *nothing_written(), called("places", "paisa_report"), cards(),
    ], must=["says nothing is recorded as spent at Blue Tokai"]),
    Case("memory", "people", "yaad rakhna: main Sunday ko gym nahi jaata", [
        called("remember"), cards("confirm/memory"),
    ]),
    Case("memory-read", "people", "mere baare mein kya yaad hai?", [
        *nothing_written(), cards(),
    ], must=["says what the memories hold"],
       must_not=["states anything about them the memories and data do not say"],
       why="real · 10-01 — fourteen money cards"),

    # ── Evening talk ────────────────────────────────────────────────────────
    Case("abilities", "talk", "tum kya kya kar sakte ho?", at="21:00", checks=[
        *nothing_written(), no_tools(), cards(),
    ], must=["says it logs and answers about money, food and work"],
       must_not=["reports today's numbers nobody asked for"], why="real · 10-08"),
    Case("trip", "talk", "is weekend ka trip plan suggest karo", [
        *nothing_written(), cards(),
    ], must_not=["presents a task or payment as part of a trip plan"], why="real · 10-08"),
    Case("overview", "talk", "mera sab detail do", [
        *nothing_written(), no_card("confirm"),
    ], why="real · 10-06 — thirteen cards"),
]

GROUPS = sorted({c.group for c in CASES})


# ─── the first run (spec/done/onboarding-goals.md) ────────────────────────────────

def me(col: str) -> str:
    return f"SELECT {col} FROM users WHERE id = :u"


def weighed(col: str) -> str:
    """The latest weigh-in's column — what everything that reads weight reads."""
    return (f"SELECT {col} FROM weigh_ins WHERE user_id = :u AND deleted_at IS NULL "
            "ORDER BY local_day DESC LIMIT 1")


#: Every fact the first run asks for, in one value: what a skip leaves alone.
PROFILE = ("SELECT row(display_name, gender, dob, height_cm, city, diet, savings_target_paise, "
           "weight_target_kg)::text FROM users WHERE id = :u")
#: 28 said this year is 1 January, 28 years back — worked out from the run's day.
AGED_28 = ("SELECT dob = make_date(extract(year FROM CAST(:today AS date))::int - 28, 1, 1) "
           "FROM users WHERE id = :u")
#: The target is the weight to reach: the latest weigh-in, less the five.
LOSE_5 = ("SELECT u.weight_target_kg = w.weight_kg - 5 FROM users u, LATERAL (SELECT "
          "weight_kg FROM weigh_ins WHERE user_id = u.id AND deleted_at IS NULL ORDER BY "
          "local_day DESC LIMIT 1) w WHERE u.id = :u")
WEIGH_INS = "SELECT count(*) FROM weigh_ins WHERE user_id = :u AND deleted_at IS NULL"
HABITS = "SELECT count(*) FROM habits WHERE user_id = :u AND deleted_at IS NULL"
MESSAGES = "SELECT count(*) FROM messages WHERE user_id = :u"


def habits(where: str) -> str:
    return f"SELECT count(*) FROM habits WHERE user_id = :u AND deleted_at IS NULL AND {where}"


def memories(where: str) -> str:
    return f"SELECT count(*) FROM memories WHERE user_id = :u AND deleted_at IS NULL AND {where}"


def moves_on() -> Check:
    """`next_question` ran: the screen asks the next question itself."""
    async def fn(t: Turn) -> str | None:
        return None if t.next else "the question stayed open (next is false)"
    return Check("moves on to the next question", fn)


def stays() -> Check:
    """The question stays open — a follow-up, or "Say that again?"."""
    async def fn(t: Turn) -> str | None:
        return None if t.next is False else "moved on with the question unfinished"
    return Check("keeps the question open", fn)


def asks_once() -> Check:
    """The one follow-up: a line, not a form."""
    async def fn(t: Turn) -> str | None:
        r = (t.reply or "").strip()
        if not r:
            return "asked for nothing"
        return f"more than one line: {r[:120]!r}" if "\n" in r else None
    return Check("asks for the rest, in one line", fn)


def weight_card(dotted: bool) -> Check:
    """The weigh-in's card carries the amber dot exactly when the weight was
    said as a guess."""
    async def fn(t: Turn) -> str | None:
        got = [bool(f.get("guessed")) for c in t.cards if _fits("confirm/body", c)
               for f in c.get("fields", []) if f.get("key") == "weight_kg"]
        if not got:
            return "no card shows the weight"
        return None if got[0] == dotted else \
            f"the weight's card is {'dotted' if got[0] else 'not dotted'}"
    return Check(f"the weight's card {'carries' if dotted else 'has no'} the estimate dot", fn)


_same_n = 0


def unchanged(sql: str, says: str) -> Check:
    """One value read before the turn and after it, and equal."""
    global _same_n
    _same_n += 1
    key = f"same-{_same_n}"

    async def prep(t: Turn) -> Any:
        return await _value(t, sql)

    async def fn(t: Turn) -> str | None:
        before, after = t.pre.get(key), await _value(t, sql)
        return None if before == after else f"{says} (was {before!r}, now {after!r})"
    return Check(says, fn, prep=prep, key=key)


def never_zero() -> Check:
    """No value of 0 sent to any tool, landed or refused: unknown is absent,
    never a zero (spec/done/onboarding-goals.md § Rules and edge cases)."""
    async def fn(t: Turn) -> str | None:
        hit = [f"{x['tool']}({_short(x.get('args'))})" for x in t.tools
               if any(isinstance(v, int | float) and not isinstance(v, bool) and v == 0
                      for v in (x.get("args") or {}).values())]
        return f"tried to write a zero: {', '.join(hit)}" if hit else None
    return Check("never tries a zero", fn)


def untouched() -> list[Check]:
    """What no answer writes: a payment, a meal, a task, a habit tick, a line in
    the chat thread — the thread stays a conversation the person starts — or a
    zero."""
    return [delta(ALL_TX, 0, "no payment written"), delta(ALL_MEALS, 0, "no meal written"),
            delta(ALL_TASKS, 0, "no task written"), delta(ALL_HABIT_LOGS, 0, "no habit ticked"),
            delta(MESSAGES, 0, "nothing in the chat thread"), never_zero()]


def kept_nothing() -> list[Check]:
    """A skip, or an answer to something else: nothing written, not even tried."""
    return [*untouched(), no_writes(), cards(), unchanged(PROFILE, "the profile as it was"),
            delta(WEIGH_INS, 0, "no weigh-in"), delta(MEMORIES, 0, "no memory written"),
            delta(HABITS, 0, "no habit started")]


def about(height: float, weight: float | None, estimated: bool = False,
          profile_cards: int = 4) -> list[Check]:
    """Question a, once answered — the name corrected from Google's, male, 28,
    the height, and the weight when one was said. `profile_cards` is how many
    of the four profile facts this turn said; the rest came in `given`."""
    checks = [
        *untouched(), called("update_profile"),
        row(me("display_name"), lambda v: v == "Sonu", "the name is Sonu"),
        row(me("gender"), lambda v: v == "male", "male"),
        row(AGED_28, lambda v: v is True, "28 is stored as 1 January, 28 years back"),
        row(me("height_cm"), lambda v: v is not None and abs(float(v) - height) < 0.05,
            f"{height:g} cm"),
    ]
    if weight is None:
        return [*checks, row(WEIGH_INS, lambda v: v == 0, "no weight, so no weigh-in"),
                cards(*["confirm/profile"] * profile_cards)]
    return [
        *checks, called("log_day"),
        row(weighed("weight_kg"), lambda v: v is not None and abs(float(v) - weight) < 0.05,
            f"a weigh-in of {weight:g} kg"),
        row(weighed("local_day = :today"), lambda v: v is True, "weighed today"),
        row(weighed("estimated"), lambda v: v is estimated,
            "marked approximate" if estimated else "a reading, not marked approximate"),
        weight_card(dotted=estimated),
        cards(*["confirm/profile"] * profile_cards, "confirm/body"),
    ]


ABOUT = "Sonu, male, 28"

ONBOARDING: list[Case] = [

    # ── a · name, gender, age, height, weight ───────────────────────────────
    Case("ob-about", "onboarding", f"{ABOUT}. Five nine, around 72 kilo", question="about",
         checks=[*about(175.3, 72, estimated=True), moves_on()],
         why="spec — the sample answer"),
    Case("ob-metric", "onboarding", f"{ABOUT}. 175 cm, 72 kg", question="about",
         checks=[*about(175, 72), moves_on()], why="spec — metric, and an exact weight"),
    Case("ob-hinglish", "onboarding", "Sonu, ladka hoon, 28 saal. Paanch nau, 72 ke aas paas",
         question="about", checks=[*about(175.3, 72, estimated=True), moves_on()],
         why="spec — Hinglish"),
    Case("ob-digits", "onboarding", "Sonu male 28 5 9 72 kilo", question="about",
         checks=[*about(175.3, 72), moves_on()],
         why="spec — spoken digits, as the recogniser writes them"),
    Case("ob-partial", "onboarding", ABOUT, question="about", checks=[
        *untouched(), called("update_profile"), not_called("log_day"),
        row(me("display_name"), lambda v: v == "Sonu", "the name is Sonu"),
        row(AGED_28, lambda v: v is True, "28 is stored as 1 January, 28 years back"),
        row(me("height_cm"), lambda v: v is None, "no height — unknown is not zero"),
        row(WEIGH_INS, lambda v: v == 0, "no weigh-in"),
        cards(*["confirm/profile"] * 3), stays(), asks_once(),
    ], must=["asks once, in one short line, for the height and the weight"],
       must_not=["asks again for the name, gender or age", "thanks or praises them"],
       why="spec — a partial answer, and the one follow-up"),
    Case("ob-followup", "onboarding", "five nine, 72 kilo", question="about", given=[ABOUT],
         checks=[*about(175.3, 72, profile_cards=1), moves_on()],
         why="spec — the follow-up's answer, read against what is already known"),
    Case("ob-once", "onboarding", "five nine", question="about", given=[ABOUT],
         checks=[*about(175.3, None, profile_cards=1), moves_on()],
         why="spec — never asks twice: the weight left out after the follow-up stays out"),
    Case("ob-skip", "onboarding", "skip", question="about",
         checks=[*kept_nothing(), moves_on()], why="spec — skipped by saying so"),
    Case("ob-unreadable", "onboarding", "sdfgh jkl", question="about", checks=[
        *kept_nothing(), stays(),
        reply_has(r"^\s*say that again\?\s*$", "replies exactly “Say that again?”"),
    ], why="spec — an answer it cannot read writes nothing and asks once more"),

    # ── b · where they live, what they eat ──────────────────────────────────
    Case("ob-place", "onboarding", "Delhi. Non-veg, but no beef.", question="place", checks=[
        *untouched(), called("update_profile"), called("remember"),
        row(me("city"), lambda v: (v or "").strip().lower() == "delhi", "lives in Delhi"),
        row(me("diet"), lambda v: v == "nonveg", "the diet is nonveg"),
        row(memories("kind = 'preference' AND text ILIKE '%beef%' AND source = 'user'"),
            lambda v: v == 1, "one preference memory about beef, in the person's own name"),
        cards("confirm/profile", "confirm/profile", "confirm/memory"), moves_on(),
    ], why="spec — the sample answer"),
    Case("ob-vegan", "onboarding", "Pune, vegan", question="place", checks=[
        *untouched(), called("update_profile"), called("remember"),
        row(me("city"), lambda v: (v or "").strip().lower() == "pune", "lives in Pune"),
        row(me("diet"), lambda v: v == "veg", "the diet is veg, the nearest of the four"),
        row(memories("kind = 'preference' AND source = 'user' AND text ~* '(vegan|dairy)'"),
            lambda v: v == 1, "one preference memory for what vegan adds"),
        cards("confirm/profile", "confirm/profile", "confirm/memory"), moves_on(),
    ], why="skill — a diet outside the four is the nearest, and what it adds remembered"),

    # ── c · the health goal ─────────────────────────────────────────────────
    Case("ob-goal-weighed", "onboarding", "lose 5 kilo", question="health", seed="weighed",
         checks=[
             *untouched(), called("update_profile"),
             row(LOSE_5, lambda v: v is True, "the target is the latest weigh-in less 5 kg"),
             delta(MEMORIES, 0, "the target is the goal — no sentence beside it"),
             cards("confirm/profile"), moves_on(),
         ], why="spec — a goal with a number, and a weight to count from"),
    Case("ob-goal-unweighed", "onboarding", "lose 5 kilo", question="health", checks=[
        *untouched(), called("remember"),
        row(me("weight_target_kg"), lambda v: v is None, "no target invented"),
        delta(memories("kind = 'project'"), 1, "the goal remembered, in their words"),
        cards("confirm/memory"), moves_on(),
    ], why="spec — a goal with a number, and no weight to count from"),

    # ── d · the monthly saving ──────────────────────────────────────────────
    Case("ob-money", "onboarding", "15k every month", question="money", checks=[
        *untouched(), called("update_profile"),
        row(me("savings_target_paise"), lambda v: v == 1500000, "the target is ₹15,000"),
        cards("confirm/profile"), moves_on(),
    ], why="spec — the sample answer"),
    Case("ob-nahi", "onboarding", "nahi batana", question="money",
         checks=[*kept_nothing(), moves_on()], why="spec — skipped by saying so"),
    Case("ob-offtopic", "onboarding", "aaj lunch mein biryani khayi", question="money",
         checks=[*kept_nothing(), moves_on()],
         why="spec — an answer about something else is a skip"),

    # ── e · habits ──────────────────────────────────────────────────────────
    Case("ob-habits", "onboarding", "gym every day, and fewer cigarettes", question="habits",
         checks=[
             *untouched(), called("manage_habit"),
             row(habits("name ILIKE '%gym%' AND direction = 'build'"), lambda v: v == 1,
                 "Gym, a habit to build"),
             row(habits("name ILIKE '%cigarette%' AND direction = 'break'"), lambda v: v == 1,
                 "Cigarettes, a habit to break"),
             row(habits("(name ~* '(every|daily|day)')"), lambda v: v == 0,
                 "no frequency in a habit's name"),
             delta(HABITS, 2, "two habits, no more"),
             cards("confirm/body", "confirm/body"), moves_on(),
         ], why="spec — the sample answer: two habits, build and break, no frequency"),
]
