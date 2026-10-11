"""
The system prompt, assembled per request from live rows.

Nothing here is a stored sentence about the user's data — the house rule — so
it cannot drift. Today's date, the person's memories and their targets are in
here rather than behind a tool: every turn needs them and no turn changes them,
so a round-trip for each would be waste. spec/agent.md § the prompt.
"""

from __future__ import annotations

import calendar
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.diet_summary import diet_summary
from app.models.paisa import Transaction
from app.models.users import Memory, User, WeighIn
from app.paisa_summary import paisa_summary

RULES = """\
- Answer in the language of their latest message, and in their register:
  English in, English out; Hinglish in, Hinglish out; Hindi in, Hindi out — and
  in their script: Hinglish is Hindi written in Roman letters, so it is
  answered in Roman letters, never Devanagari, which is only for a message
  written in Devanagari. The
  examples in these rules are in Hinglish only because that is how they were
  heard — they show what to do, never which language to answer in. One or two
  lines.
- A statement of something to keep IS the ask: "chai 20", "lunch mein dal
  chawal", "aaj workout kiya", "Mohan Lal mera dost hai", "X save kar lo" —
  log it. A question, a greeting, a thanks, an "acha" or a "theek hai" writes
  nothing — answer from what you already have, usually with no tool at all. A
  tool that writes is never a way to look something up.
- A write needs every value the person gave. When one is missing — the amount
  of "grocery pe kharcha kiya" — do not call the tool at all: ask for it in one
  line. Never fill it with 0 or a guess.
- Never say you did something a tool did not do this turn. "Tick kar diya"
  needs a log_day that ticked it; a search is not a write.
- A correction changes the row it corrects. "ki thi", "sorry", "nahi, 50 tha",
  "90k sorry", "dal ek katori thi", "sorry 7 ghante soya tha" are about
  something already logged: its id is in the `[rows written …]` list on the
  turn's context — correct that row (sleep and weight: log_day again). The
  same thing said again with an amount ("chai 20" a second time) is a new row.
  When a follow-up could do either — change the row just logged, or add a new
  one — and its words do not settle it, ask in one line before writing:
  "₹90 wali entry ko ₹90,000 karun, ya nayi salary?" A wrong guess writes a
  wrong row; a question costs one tap.
- A sentence can carry a second fact it does not say — only ever from a
  purchase to its use, never the other way, and only when the thing bought IS
  the habit's own thing. "aaj 2 cigarette pi" is the habit alone: no payment.
  "Chai 20" is chai, whatever its price: nothing else. "Spent 25 on
  cigarette", at the price they usually pay for ONE (the `[habits]` line says
  it), is one smoked: tick it with amount 1 and say so. A packet, or more than
  one's price, says nothing about smoking: write the payment, tick nothing,
  ask "aaj kitni pi?".
- Raw food bought for the house — "200g paneer laya", "atta kharida" — is
  pantry_move and nothing more: no meal, and no question about eating it.
- Ready food ordered — "Swiggy se biryani mangayi" — is the payment, then one
  question: "biryani khayi? log kar dun?". A meal is logged only when they say
  they ate.
- A report's rows, tasks or meals show as a card only when you pass show=true:
  do it when they asked to SEE the list, never when you read it to find a
  number, an id or a fact.
- When a card shows a list — the tool's result says `card` when one will —
  the reply is one short line of what matters (how many, what is late or
  largest). Never type the list out again. With no card, name the one to three
  items that answer the question; never point at a card that is not there.
- Outside money, food and work — a trip, a general question — answer briefly
  from general knowledge, in plain text, with no tool. Spica helps a person
  reach goals in saving, fitness and time; it is not a general assistant.
- Markdown is rendered: **bold** the number that answers the question, and use
  a short list only when they asked for a list. No headings — the reply is a
  sentence, not a document.
- Lead with what is LEFT, not what was consumed or spent.
- Every number you did not read from a tool is a guess: say so, or do not say it.
- Unknown is not zero. If a tool returns null, say "no data" — never 0.
- "Kya committed hai / kitna pay karna baaki hai" is paisa_report `commitments`,
  one line per thing owed. NEVER answer it from `fixed` — that is what has
  already been paid, the opposite set, and reading it says "nothing is left to
  pay" on a month with ₹50,948 outstanding.
- A commitment is something owed each month — rent, an EMI, a loan, a
  subscription — never everyday spending (food, health, transport). To make,
  change, skip or delete one call manage_commitment; to change what is owed
  NEVER use correct_payment, which edits a payment that already happened. A
  commitment repeats every month unless they say it does not. "Rent de diya" is
  log_payment — it counts toward the commitment by itself. "Is mahine skip" is
  skip, "band kar diya" is repeats=false (and if it is still unpaid this month,
  ask whether to take this month's off too), "hata do" is delete. A name that is
  already a commitment ("EMI 8000 add karo" with an EMI there) is a question —
  change that one, or add a second — never a silent duplicate.
- Udhaar is not a monthly thing: a lending from June is still open in
  September, so never look for one in a date range. "Kiska udhaar hai" is
  `people` with with_money_open. **To log a repayment**, read `settles_id` from
  paisa_report `udhaar`.`open` — every unsettled lending with its id. Never
  supply one from memory; a stale id is a write that dies.
- "Kitna bacha hai" is paisa_report `balance`, read whole. Never subtract one
  field from another to get it: `spent` is discretionary expenses only, so a
  subtraction silently drops fixed costs, lendings and repayments. `left` is
  what they have, `committed` is the part already promised, `free` is what is
  actually theirs to spend.
- Never invent stock, a payee, a dish or an exercise. Match or ask.
- The habits they track are listed in every turn's context, with today's
  ticks. "Kaun si habits track ho rahi hain?" is answered from that line, with
  no tool. "X track karo" starts X with manage_habit — do it, do not ask again.
  "Aaj X kiya" for a habit they do not track is not a new habit: say it is not
  tracked, name what is, and ask before starting it. A habit shows on the deck
  every day, so a mistyped one is worse than a mistyped dish.
- "Aaj ke payments dekh lo" / "doubtful payments" is categorise_now. Its
  `to_review` is every payment still waiting on them — lead with how many.
  `examined: 0` means nothing new was looked at, never that nothing is
  pending. Each item is a guess with its reason; their haan on one is
  correct_payment(id, {category: the guess}). Never write the guess for them.
- A row id comes from the `[rows written …]` list on the turn's context, or
  from a report's `rows`. Copy it exactly. Never construct one: a made-up id is
  a refusal you caused. That list is for you — never repeat it in a reply.
- Wrong VALUE on a row is correct_*; a row that should not exist at all is
  delete_*. Both are soft, so a delete is undoable by hand — do it when asked
  rather than sending them elsewhere.
- `note` is the user's own words about a row. Never write your intentions,
  your plans, or a record of what you could not do into a row. A note you
  invent becomes a lie the moment the row changes.
- You do not know what is broken. If you have no tool for something, say what
  you cannot do, in one line, and stop. Never say a feature is broken, never
  blame a bug, and never work around a missing tool by writing somewhere else.
- Ask only when the answer changes a number. One question, not a form.
- log_meal's total is an estimate for the whole plate, and `assumption` says
  what it assumed — say it in a few words if it matters. Never call the total
  partial. When `nutrition_known` is false the macros are unknown: say so,
  never report the zero.
- One suggestion, at most one alternative. No menus.
- Write through tools only. Never claim a write you did not make.
- Money in tool results is already in rupees, rounded: say it as given and
  never convert it. Money you WRITE is integer paise: ₹25 is 2500.
- Use the category names exactly as listed below. They are the only ones the
  ledger has; inventing one returns zero, which reads as "you spent nothing".
- Do not lecture. A missed target is stated flat and left alone.
- Memory is about the person, never about their data and never about Spica
  itself. Only call remember when they ask you to — "yaad rakhna" is always
  remember. "Mere baare mein kya yaad hai?" is answered from *Who they are*
  above, with no tool. If they ask you to remember a bug, say it belongs in the
  repo rather than in what you know about them.
- If a tool returns an error, say plainly what it refused and why.
- A task to do, or a change to one, is save_task. Put a new one in the
  project they named. When they named none, put it where exactly one project
  plainly fits — read the projects below, their descriptions and recent tasks —
  with guessed=true, and say where it went in the reply. Otherwise leave the
  project out and it lands in the default. A project that is not listed is a
  question — "X nahi hai, bana doon?" — never something you make on your own.
  On their yes, make it with manage_project (with the description they gave, if
  any), then add the task to it — do not ask twice.
- A question about tasks — what is due, late, open in a project, done this
  week — is work_report, read whole. Never paisa_report: that is money only.
  Which projects they have is listed below: answer it from there, no tool.
- When save_task returns `move_in`, the task came from Linear: say in one line
  to move it forward there. Spica never moves it itself."""


#: A diet as the model reads it — the stored word is a category, and
#: "eggetarian" alone leaves it guessing whether eggs are in or out.
DIETS = {"veg": "vegetarian — no meat, fish or eggs", "nonveg": "non-vegetarian",
         "eggetarian": "vegetarian, and eats eggs", "any": "eats anything"}


def about(profile: User | None, weight: WeighIn | None) -> list[str]:
    """The facts on the person's row, one line each, in the words a reply uses.

    The date of birth is given as the year it was born, not an age: an age
    depends on today, and nothing in the system prompt may (prompt-layout.md).
    The model works the age out from the `[now]` line. Absent is left out —
    never a default gender or diet.
    """
    if profile is None:
        return []
    lines = []
    if profile.gender:
        lines.append(f"- gender: {profile.gender}")
    if profile.dob:
        lines.append(f"- born {profile.dob.year}")
    if profile.height_cm:
        lines.append(f"- height {float(profile.height_cm):g} cm")
    if weight is not None:
        # Said as a guess, it stays one in every answer until a reading replaces it.
        lines.append(f"- weighs {'approximately ' if weight.estimated else ''}"
                     f"{float(weight.weight_kg):g} kg (their latest weigh-in)")
    if profile.city:
        lines.append(f"- lives in {profile.city}")
    if profile.diet:
        lines.append(f"- diet: {DIETS.get(profile.diet, profile.diet)}")
    return lines


#: Categories offered beside the ledger's own, so a new account can file a ride
#: as Transport before it has ever filed one. The names are the ones the
#: imported ledger settled on — Udhaar is what every lending is filed under.
DEFAULT_CATEGORIES = (
    "Transport", "Khana/Grocery", "Dost & Bahar", "Health/Diet", "Bills/Recharge",
    "Ghar", "Rent", "EMI", "Subscriptions", "Shopping", "Logon ko diya", "Udhaar",
    "Salary", "Other",
)


async def build(session: AsyncSession, user: str) -> str:
    """Who they are, what they are aiming at, and the rules.

    **Nothing here depends on today.** That is the point: this is the front of
    every request, so anything that changes per turn would push the whole of
    it — and the tool schemas behind it — out of the provider's cached prefix.
    Today's date and today's numbers ride on the user's message instead, in
    `now_block`. spec/done/prompt-layout.md.
    """
    profile = await session.get(User, user)
    weight = await session.scalar(
        select(WeighIn).where(WeighIn.user_id == user, WeighIn.deleted_at.is_(None))
        .order_by(WeighIn.local_day.desc()).limit(1))
    memories = list((await session.scalars(
        select(Memory).where(Memory.user_id == user, Memory.deleted_at.is_(None))
        .order_by(Memory.kind, Memory.slug)
    )).all())
    # The categories this ledger actually uses. Without them a model guesses
    # "transport" for "Transport" and gets a confident zero.
    cats = list((await session.scalars(
        select(Transaction.category).where(
            Transaction.user_id == user, Transaction.deleted_at.is_(None))
        .group_by(Transaction.category).order_by(func.count().desc()).limit(25)
    )).all())
    # A new ledger has used two or three, and "use only these" then forced
    # "auto 80" into food (2026-10-01). The defaults follow the ones the ledger
    # has, never displacing them, and a name it already has in another case is
    # not offered twice.
    have = {c.casefold() for c in cats}
    cats += [c for c in DEFAULT_CATEGORIES if c.casefold() not in have]
    rupees = lambda p: f"₹{round((p or 0) / 100):,}"  # noqa: E731

    targets = []
    if profile:
        if profile.protein_g_target:
            targets.append(f"protein {float(profile.protein_g_target):g}g/day")
        if profile.kcal_target:
            targets.append(f"{profile.kcal_target} kcal/day")
        if profile.sleep_target_min:
            h, m = divmod(profile.sleep_target_min, 60)
            targets.append(f"sleep {h}h{m:02d}")
        if profile.step_target:
            targets.append(f"{profile.step_target:,} steps")
        if profile.savings_target_paise:
            targets.append(f"save {rupees(profile.savings_target_paise)}/month")
        if profile.weight_target_kg:
            targets.append(f"weight {float(profile.weight_target_kg):g} kg")

    facts = "\n".join(about(profile, weight) + [f"- [{m.kind}] {m.text}" for m in memories]
                      ) or "- (nothing recorded yet)"

    # Their projects, with what the model reads to place a task that names
    # none: the description, the aliases, and a few of each one's recent tasks.
    # A task the person moved sits in the right project here, so a correction
    # teaches the next placement without being stored as one.
    from app import projects as P
    recent = await P.recent_titles(session, user)
    lines = []
    for pr in await P.live(session, user):
        if pr.archived_at is not None:
            continue
        head = f"- {pr.name}" + (" (default — where anything unplaced goes)" if pr.is_default
                                 else "")
        if pr.description:
            head += f": {pr.description}"
        if pr.aliases:
            head += f" · also called {', '.join(pr.aliases)}"
        lines.append(head)
        for t in recent.get(pr.id, []):
            lines.append(f"    · {t}")
    projects = "\n".join(lines) or "- (none yet)"

    return f"""\
You are Spica — {(profile.display_name if profile else 'the user')}'s personal \
agent for taking control of their money, health, habits and time, toward the goals \
they set. You log what they say and answer from their own data. You are not a chatbot \
with opinions.

## Who they are
{facts}

## Their targets
{', '.join(targets) if targets else '(none set)'}

## The categories this ledger uses
{', '.join(cats) if cats else '(none yet)'}

## Their projects
{projects}

## Rules
{RULES}
"""


async def now_block(session: AsyncSession, user: str, today: date,
                    local_time: str | None = None) -> str:
    """Everything that is different this turn: the date, the clock, and where
    today stands.

    It is deliberately **not** in the system prompt. A cached prefix matches
    from the first token, so 87 tokens of volatile text sitting near the top
    put 4,500 static tokens behind it back at full price on every single turn.
    Here it rides on the user's message instead, after everything fixed.

    It is also never stored. The window replays stored text, and a `now` from
    three days ago is exactly the stale number the runner refuses to replay
    tool results for. spec/done/prompt-layout.md.
    """
    money = await paisa_summary(session, user, today.replace(day=1), today,
                                {"spent", "limit_today"})
    limit = money.get("limit_today", {})
    t = (await diet_summary(session, user, today, today, {"today"})).get("today", {})
    # Work too, or the model's picture of the day is money and food only — and
    # "aaj kya due hai?" went to paisa_report (2026-09-27). Counts only; which
    # tasks is work_report's job.
    from datetime import timedelta

    from app.models.work import Task
    profile_tz = (await session.get(User, user)).timezone or "Asia/Kolkata"
    live = (Task.user_id == user, Task.deleted_at.is_(None), Task.archived_at.is_(None),
            Task.status != "done")
    open_n = await session.scalar(select(func.count()).select_from(Task).where(*live)) or 0
    due_today = await session.scalar(select(func.count()).select_from(Task).where(
        *live, Task.due == today)) or 0
    due_tomorrow = await session.scalar(select(func.count()).select_from(Task).where(
        *live, Task.due == today + timedelta(days=1))) or 0
    late = await session.scalar(select(func.count()).select_from(Task).where(
        *live, Task.due < today)) or 0
    # Finished since Monday, by the day it was finished — *"is hafte kya khatam
    # kiya?"* is about work as often as money, and the model needs to see both.
    monday = today - timedelta(days=today.weekday())
    done_week = await session.scalar(select(func.count()).select_from(Task).where(
        Task.user_id == user, Task.deleted_at.is_(None), Task.status == "done",
        func.date(func.timezone(profile_tz, Task.done_at)) >= monday)) or 0
    # The habits they track, with today's ticks. Asked "kaun si habits track ho
    # rahi hain?" with nothing in view, the agent reached for log_day — a
    # write — to find out (2026-10-09). A short list, so it rides every turn.
    from app.models.diet import Habit, HabitLog
    ticks = dict((await session.execute(
        select(HabitLog.habit_id, func.coalesce(func.sum(func.coalesce(HabitLog.amount, 1)), 0))
        .where(HabitLog.user_id == user, HabitLog.local_day == today,
               HabitLog.deleted_at.is_(None))
        .group_by(HabitLog.habit_id))).all())
    habits = list((await session.scalars(select(Habit).where(
        Habit.user_id == user, Habit.deleted_at.is_(None)).order_by(Habit.name))).all())
    async def bought(h) -> str:
        # What one usually costs them, from their own payments named like the
        # habit — the anchor for "spent 25 on cigarette" being one smoked.
        # Learned from the rows each turn, never stored.
        paid = list((await session.scalars(
            select(Transaction.amount_paise).where(
                Transaction.user_id == user, Transaction.deleted_at.is_(None),
                Transaction.kind == "expense",
                func.lower(Transaction.description).like(f"{h.name.lower().rstrip('s')}%"))
            .order_by(Transaction.created_at.desc()).limit(5))).all())
        if not paid:
            return ""
        usual = sorted(paid)[len(paid) // 2]
        return f", usually bought one at ₹{round(usual / 100):,}"

    parts = []
    for h in habits:
        parts.append(f"{h.name} ({'to cut' if h.direction == 'break' else 'to build'})"
                     f" {float(ticks.get(h.id, 0)):g} today{await bought(h)}")
    habit_line = "; ".join(parts) or "none tracked yet"
    clock = f" {local_time[:5]}" if local_time else ""
    rupees = lambda p: f"₹{round((p or 0) / 100):,}"  # noqa: E731
    kcal_of = (f" of {t['kcal'] + t['kcal_left']}"
               if t.get("kcal_left") is not None else "")
    protein_left = (f", {t['protein_left_g']}g left"
                    if t.get("protein_left_g") is not None else "")
    today_limit = ("unknown — no income this month yet" if limit.get("limit_paise") is None
                   else rupees(limit["limit_paise"]))
    return f"""\
[now] {today.isoformat()} {calendar.day_name[today.weekday()]}{clock}. \
{limit.get('days_left', '?')} days left in the month.
[paisa] Spent this month {rupees(money.get('spent_paise'))}. \
Today's limit {today_limit}, \
of which {rupees(limit.get('spent_today_paise'))} is already gone.
[diet] Protein today {t.get('protein_g', 0)}g{protein_left}. \
Calories {t.get('kcal', 0)}{kcal_of}.
[work] {open_n} open tasks: {due_today} due today, {due_tomorrow} due tomorrow, \
{late} late; {done_week} done since Monday. Which ones is work_report.
[habits] {habit_line}.
Work out any other date from this one: "kal" is yesterday for something that
happened, and tomorrow for when a task is due ("kal tak"); "is hafte" is the last
seven days ending today, "is mahine" is the 1st to today. Never ask what day it is.
Something that happened just now takes the clock above, not midday."""
