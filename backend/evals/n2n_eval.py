"""
n2n_eval — the day, end to end, against the real model.

    cd backend
    uv run python -m evals.n2n_eval                        # the whole day, three times
    uv run python -m evals.n2n_eval --repeat 1             # once, for a quick look
    uv run python -m evals.n2n_eval --only money,talk      # some groups, in order
    uv run python -m evals.n2n_eval --only onboarding,plan-veg   # blocks and single cases
    uv run python -m evals.n2n_eval --upto pay-fix         # the day up to a case
    uv run python -m evals.n2n_eval --model gpt-6-sol      # the same day, another model
    uv run python -m evals.n2n_eval --effort low           # the same day, thinking more

Not part of `pytest`, on purpose: it calls the model named in .env (or
`--model`) and spends real tokens. The tests in tests/ mock the model and
assert the server; this asserts the loop a person meets — the sentence, the
tool, the card, the row. spec/done/chat-quality.md § The harness.

**One conversation, a day in order.** Each run is one account seeded with the
lived-in week of `fixture.py`; the cases are said to it one after another, at
the clock each case gives, so later turns act on what earlier ones wrote. A
case's `given` sentences are said just before it, ungraded. `--repeat` runs the
day that many times, side by side, each on its own account. A case passes when
it passes in every run.

**Two blocks beside the day.** `plan` is Home's read, not a sentence: today's
plan from the lived-in account at two clocks, and from a veg account.
`onboarding` is the first run (spec/done/onboarding-goals.md): each case on its own
account just signed in — no lived-in week — and said to `POST /onboarding/turn`
with its question, `--repeat` times like the day. A full run says all three;
`--only` picks groups, blocks or single cases from any of them.

**What is checked** is the case's own checks (`cases.py`). Nothing here reads a
reply for meaning: Claude does that from the report, which keeps every reply
and every tool call **with its result** — captured here, in the eval, and
nowhere else.

A case marked `known` is a gap already written down: reported, never counted.
The exit status is 1 when anything else fails. Each run writes
`reports/n2n-<time>.json`; `evals.to_artifact` turns one into the review
page's data.
"""

from __future__ import annotations

import argparse
import asyncio
import contextvars
import json
import os
import re
import sys
import time
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

BACKEND = Path(__file__).resolve().parents[1]
#: N2N_DB names another database, so two runs — two efforts — can go side by side.
EVAL_DB = os.environ.get("N2N_DB", "cortex_eval")
ADMIN_URL = "postgresql://cortex:cortex@localhost:5434/cortex"
EVAL_URL = f"postgresql+asyncpg://cortex:cortex@localhost:5434/{EVAL_DB}"
IST = ZoneInfo("Asia/Kolkata")

# Before any app import: `settings()` is cached on first use, and the app
# must never see the dev database's URL (tests/conftest.py, the same rule).
os.environ["DATABASE_URL"] = EVAL_URL
os.environ["DAILY_TURN_LIMIT"] = "1000000"
os.chdir(BACKEND)  # alembic.ini and its script_location are relative to here
sys.path.insert(0, str(BACKEND))

from evals.cases import CASES, GROUPS, ONBOARDING, Case, Turn  # noqa: E402

# ─── what a turn did, captured ───────────────────────────────────────────────

@dataclass
class Capture:
    calls: list[dict] = field(default_factory=list)
    instructions: str | None = None
    model_input: Any = None
    #: The turn's model calls, for a route that does not report them itself —
    #: the first run's answer.
    tokens_in: int = 0
    tokens_out: int = 0


CAP: contextvars.ContextVar[Capture | None] = contextvars.ContextVar("n2n_capture", default=None)


def spy() -> None:
    """Record every tool call with its result, and what the agent was sent.
    The runner calls `T.run` and `respond` through module attributes, so
    wrapping them here reaches every call without touching the app."""
    import app.agent.runner as R
    import app.agent.tools as T

    run, respond = T.run, R.respond

    async def run_spy(session, user, name, args, **kw):
        result = await run(session, user, name, args, **kw)
        cap = CAP.get()
        if cap is not None:
            # The same dict the runner enriches after this returns, so the
            # judge sees what the model saw.
            cap.calls.append({"tool": name, "args": dict(args or {}), "result": result})
        return result

    async def respond_spy(**kw):
        cap = CAP.get()
        if cap is not None and cap.instructions is None and kw.get("tools"):
            cap.instructions, cap.model_input = kw.get("instructions"), kw.get("input")
        resp = await respond(**kw)
        if cap is not None and getattr(resp, "usage", None) is not None:
            cap.tokens_in += resp.usage.input_tokens
            cap.tokens_out += resp.usage.output_tokens
        return resp

    T.run = run_spy
    R.respond = respond_spy


# ─── the database ────────────────────────────────────────────────────────────

async def fresh_database() -> None:
    import asyncpg
    from alembic.config import Config

    from alembic import command

    admin = await asyncpg.connect(ADMIN_URL)
    await admin.execute(f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                        f"WHERE datname = '{EVAL_DB}' AND pid <> pg_backend_pid()")
    await admin.execute(f"DROP DATABASE IF EXISTS {EVAL_DB}")
    await admin.execute(f"CREATE DATABASE {EVAL_DB}")
    await admin.close()
    conn = await asyncpg.connect(EVAL_URL.replace("+asyncpg", ""))
    for ext in ("vector", "pg_trgm"):
        await conn.execute(f"CREATE EXTENSION IF NOT EXISTS {ext}")
    await conn.close()
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", EVAL_URL)
    await asyncio.to_thread(command.upgrade, cfg, "head")


# ─── the day ─────────────────────────────────────────────────────────────────

def clocks(cases: list[Case]) -> list[str]:
    """Each case's HH:MM. Anchored cases keep theirs; the rest are spaced
    evenly between anchors, and five minutes apart after the last."""
    def mins(hhmm: str) -> int:
        h, m = hhmm.split(":")
        return int(h) * 60 + int(m)
    marks = [(i, mins(c.at)) for i, c in enumerate(cases) if c.at]
    if not marks or marks[0][0] != 0:
        marks.insert(0, (0, marks[0][1] - 5 * marks[0][0] if marks else 8 * 60))
    out = []
    for i in range(len(cases)):
        before = max((m for m in marks if m[0] <= i), key=lambda m: m[0])
        after = min((m for m in marks if m[0] > i), key=lambda m: m[0], default=None)
        if after is None:
            t = before[1] + 5 * (i - before[0])
        else:
            span = after[0] - before[0]
            t = before[1] + (after[1] - before[1]) * (i - before[0]) // span
        t = min(t, 23 * 60 + 50)
        out.append(f"{t // 60:02d}:{t % 60:02d}")
    return out


def _card_label(c: dict) -> str:
    s = c.get("kind", "?") + ("/" + c["source"] if c.get("source") else "")
    if c.get("kind") == "confirm" and c.get("state", "written") != "written":
        s += ":" + c["state"]
    return s + (f" — {c['lede']}" if c.get("lede") else "")


def _broken(rep: int, why: str) -> dict:
    return {"rep": rep, "passed": False, "failures": [why], "reply": "", "cards": [],
            "tools": [], "earlier": [], "tokens_in": 0, "tokens_out": 0, "at": None}


async def run_day(cases: list[Case], rep: int, env: dict) -> dict[str, dict]:
    """One account, the cases said in order. Returns each case's result."""
    from httpx import AsyncClient

    from evals.fixture import lived_in_week, make_account

    today, Session = env["today"], env["Session"]
    token = f"n2n-{uuid.uuid4().hex}"
    async with Session() as s:
        user = await make_account(s, token)
        await s.commit()
    results: dict[str, dict] = {}
    async with AsyncClient(transport=env["transport"], base_url="http://eval",
                           headers={"Authorization": f"Bearer {token}"}, timeout=300) as client:
        try:
            await lived_in_week(client, today)
        except Exception as e:  # noqa: BLE001 — a broken fixture is the harness's failure, said
            return {c.id: _broken(rep, f"harness: fixture failed — {e}") for c in cases}

        async def say(text: str, at: str) -> dict:
            r = await client.post("/chat", json={"message": text, "local_day": today.isoformat(),
                                                 "local_time": f"{at}:00"})
            body = r.json() if r.status_code == 200 else {"reply": r.text, "cards": []}
            body["_status"] = r.status_code
            return body

        for case, at in zip(cases, env["clocks"], strict=True):
            t0 = time.monotonic()
            out: dict[str, Any] = {"rep": rep, "at": at, "earlier": [], "failures": []}
            try:
                for g in case.given:
                    b = await say(g, at)
                    out["earlier"].append({"said": g, "reply": b.get("reply") or ""})
                pre = await _prep(case, user, env)
                cap = Capture()
                CAP.set(cap)
                body = await say(case.say, at)
                CAP.set(None)
            except Exception as e:  # noqa: BLE001 — one broken turn must not end the day
                results[case.id] = _broken(rep, f"harness: {type(e).__name__}: {str(e)[:300]}")
                continue
            results[case.id] = await _grade(case, body, cap, pre, user, env, out, t0)
    return results


async def _prep(case: Case, user: str, env: dict) -> dict:
    """What the case's checks read before the turn, by each check's key."""
    async with env["Session"]() as s:
        pre = Turn(reply="", cards=[], tools=[], session=s, user=user, today=env["today"])
        for check in case.checks:
            if check.prep is not None:
                pre.pre[check.key] = await check.prep(pre)
    return pre.pre


async def _grade(case: Case, body: dict, cap: Capture, pre: dict, user: str, env: dict,
                 out: dict, t0: float) -> dict:
    """What the turn came back with, kept for the report, and the case's checks
    run on it."""
    from evals.judge_aid import context_of

    out["reply"] = body.get("reply") or ""
    # The turn's context block as the agent got it — what Claude reads a
    # reply's figures against, beside the tool results.
    out["context"] = context_of(cap.model_input)
    out["tokens_in"] = body.get("tokens_in", cap.tokens_in)
    out["tokens_out"] = body.get("tokens_out", cap.tokens_out)
    raw_cards = [c for c in (body.get("cards") or []) if c.get("kind") != "agent"]
    out["cards"] = [_card_label(c) for c in raw_cards]
    tools = [{"tool": c["tool"], "args": c["args"],
              "ok": not (c["result"] or {}).get("error"),
              "error": (c["result"] or {}).get("error"), "result": c["result"]}
             for c in cap.calls]
    out["tools"] = tools
    if case.question:
        out["next"] = body.get("next")
    if body["_status"] != 200:
        out["failures"].append(f"HTTP {body['_status']}: {out['reply'][:200]}")
    async with env["Session"]() as s:
        turn = Turn(reply=out["reply"], cards=raw_cards, tools=tools, session=s,
                    user=user, today=env["today"], pre=pre, next=body.get("next"))
        for check in case.checks:
            try:
                why = await check(turn)
            except Exception as e:  # noqa: BLE001 — a check that cannot run is a failure, said
                why = f"check “{check.says}” raised {type(e).__name__}: {e}"
            if why:
                out["failures"].append(why)
    out["passed"] = not out["failures"]
    out["seconds"] = round(time.monotonic() - t0, 1)
    return out


# ─── the first run: answers on an account just signed in ─────────────────────

async def first_run(cases: list[Case], rep: int, env: dict) -> dict[str, dict]:
    """The first run's answers, each case on its own account just signed in —
    no lived-in week, nothing but the name Google gave — said to `POST
    /onboarding/turn`, never to the chat. An answer is read against what is
    already known, so a case starts from its own `seed` and `given` and from
    nothing another case wrote."""
    from httpx import AsyncClient

    from evals.fixture import SEEDS, new_account

    today, Session = env["today"], env["Session"]
    results: dict[str, dict] = {}
    for case in cases:
        token = f"n2n-{uuid.uuid4().hex}"
        async with Session() as s:
            user = await new_account(s, token)
            await s.commit()
        t0 = time.monotonic()
        out: dict[str, Any] = {"rep": rep, "at": None, "earlier": [], "failures": []}
        async with AsyncClient(transport=env["transport"], base_url="http://eval",
                               headers={"Authorization": f"Bearer {token}"},
                               timeout=300) as client:
            try:
                if case.seed:
                    await SEEDS[case.seed](client, today)
                for g in case.given:
                    b = await _answer(client, case.question, g, today)
                    out["earlier"].append({
                        "said": g, "reply": b.get("reply") or "", "next": b.get("next"),
                        "cards": [_card_label(c) for c in b.get("cards") or []]})
                pre = await _prep(case, user, env)
                cap = Capture()
                CAP.set(cap)
                body = await _answer(client, case.question, case.say, today)
                CAP.set(None)
            except Exception as e:  # noqa: BLE001 — one broken case must not end the block
                results[case.id] = _broken(rep, f"harness: {type(e).__name__}: {str(e)[:300]}")
                continue
        results[case.id] = await _grade(case, body, cap, pre, user, env, out, t0)
    return results


async def _answer(client, question: str, text: str, today) -> dict:
    """One answer to one of screen 3's questions, as the screen sends it."""
    r = await client.post("/onboarding/turn", json={"question": question, "text": text,
                                                    "local_day": today.isoformat()})
    body = r.json() if r.status_code == 200 else {"reply": r.text, "cards": []}
    body["_status"] = r.status_code
    return body


# ─── Home's plan: a read, not a sentence ─────────────────────────────────────

#: Not a sentence to the agent: Home's own read. spec/in-progress/today-plan.md.
PLAN = "plan"
#: The spec's band: protein within 10 g of the target, calories within 10%.
PROTEIN_BAND, KCAL_BAND = 10, 0.10
#: The skill file's ceiling on one meal, and on a snack. Past them a plan has
#: stopped being food someone eats.
MEAL_KCAL, MEAL_PROTEIN, SNACK_KCAL = 800, 50, 350


#: The plan block's cases, by id: two clocks on the lived-in account, and the
#: veg account's morning.
PLAN_IDS = ("plan-morning", "plan-evening", "plan-veg")
#: What a veg plan never holds — meat, fish or egg — by the words a dish's name
#: says them in: the eval's reading of the model's plan, for the one check a
#: word can make. Claude reads the rest.
NOT_VEG = re.compile(r"\b(eggs?|anda|ande|omelet(te)?|chicken|mutton|lamb|goat|fish|"
                     r"machh?li|prawns?|shrimps?|beef|pork|meat|gosht)\b", re.I)


def _plan_result(cid: str, clock: str, p: dict, fails: list[str], t0: float,
                 why: str = "spec/in-progress/today-plan.md",
                 must_not: list[str] | None = None) -> dict:
    print(f" {'✓' if not fails else '✗'} {cid:<15}       GET /plan/today at {clock}",
          flush=True)
    for reason in fails:
        print(f"       · {reason}", flush=True)
    return {"id": cid, "group": PLAN, "say": f"GET /plan/today {clock}", "given": [],
            "why": why, "known": None, "expect": [], "must": [], "must_not": must_not or [],
            "passes": int(not fails), "runs": [{
                "rep": 0, "passed": not fails, "failures": fails, "reply": "",
                "cards": [], "tools": [], "judge": None, "earlier": [],
                "plan": p, "seconds": round(time.monotonic() - t0, 1)}]}


async def plan_cases(env: dict, ids: list[str]) -> list[dict]:
    """The plan block's cases among `ids`."""
    out = await lived_in_plans(env, [i for i in ids if i in ("plan-morning", "plan-evening")])
    if "plan-veg" in ids:
        out.append(await veg_plan(env))
    return out


async def lived_in_plans(env: dict, ids: list[str]) -> list[dict]:
    """Today's plan from the real model, at breakfast and before dinner, on a
    lived-in account: one meal for each slot still ahead, landing on the
    targets when there is room to, and a workout."""
    from httpx import AsyncClient

    from evals.fixture import lived_in_week, make_account

    if not ids:
        return []
    token = f"n2n-{uuid.uuid4().hex}"
    async with env["Session"]() as s:
        await make_account(s, token)
        await s.commit()
    out = []
    async with AsyncClient(transport=env["transport"], base_url="http://eval",
                           headers={"Authorization": f"Bearer {token}"}, timeout=240) as client:
        await lived_in_week(client, env["today"])
        for cid, clock in (("plan-morning", "08:00"), ("plan-evening", "18:30")):
            if cid not in ids:
                continue
            t0 = time.monotonic()
            r = await client.get("/plan/today", params={"local_day": env["today"].isoformat(),
                                                       "local_time": clock})
            p = r.json() if r.status_code == 200 else {}
            fails = []
            if r.status_code != 200 or not p.get("available"):
                fails.append(f"no plan: HTTP {r.status_code} {str(p or r.text)[:160]}")
            else:
                slots = [m["slot"] for m in p["meals"]]
                if slots != p["slots_ahead"]:
                    fails.append(f"planned {slots}, but {p['slots_ahead']} are ahead")
                for m in p["meals"]:
                    cap = SNACK_KCAL if m["slot"] == "Snack" else MEAL_KCAL
                    if m["kcal"] > cap * 1.1 or m["protein_g"] > MEAL_PROTEIN * 1.1:
                        fails.append(f"{m['slot']} is {m['kcal']} kcal, "
                                     f"{m['protein_g']:g} g — not one meal")
                t, got, planned = p["targets"], p["logged"], p["planned"]
                # The targets are owed only when the slots left can reach them.
                room_k = sum(SNACK_KCAL if s == "Snack" else MEAL_KCAL for s in p["slots_ahead"])
                room_p = MEAL_PROTEIN * len(p["slots_ahead"])
                if t["protein_g"] and 0 < t["protein_g"] - got["protein_g"] <= room_p:
                    lands = got["protein_g"] + planned["protein_g"]
                    if abs(lands - t["protein_g"]) > PROTEIN_BAND:
                        fails.append(f"protein lands at {lands:g} g against {t['protein_g']:g}")
                if t["kcal"] and 0 < t["kcal"] - got["kcal"] <= room_k:
                    lands = got["kcal"] + planned["kcal"]
                    if abs(lands - t["kcal"]) > KCAL_BAND * t["kcal"]:
                        fails.append(f"calories land at {lands} against {t['kcal']}")
                w = p.get("workout")
                if not w:
                    fails.append("no workout")
                elif w["kind"] != "rest" and not w["minutes"]:
                    fails.append(f"a {w['kind']} with no minutes")
            out.append(_plan_result(cid, clock, p, fails, t0))
    return out


async def veg_plan(env: dict) -> dict:
    """Home's plan for a veg account at breakfast, every slot ahead: no meat, no
    fish, no egg in any meal — though eggs are in the kitchen and the library's
    Egg bhurji is cookable. The diet is a limit, never a preference
    (spec/done/onboarding-goals.md § What reads the answers)."""
    from httpx import AsyncClient

    from evals.fixture import DISHES, make_account, veg_kitchen

    not_veg = {d[0] for d in DISHES if NOT_VEG.search(d[1])}
    token = f"n2n-{uuid.uuid4().hex}"
    async with env["Session"]() as s:
        await make_account(s, token)
        await s.commit()
    async with AsyncClient(transport=env["transport"], base_url="http://eval",
                           headers={"Authorization": f"Bearer {token}"}, timeout=240) as client:
        await veg_kitchen(client, env["today"])
        t0 = time.monotonic()
        r = await client.get("/plan/today", params={"local_day": env["today"].isoformat(),
                                                   "local_time": "08:00"})
    p = r.json() if r.status_code == 200 else {}
    fails = []
    if r.status_code != 200 or not p.get("available"):
        fails.append(f"no plan: HTTP {r.status_code} {str(p or r.text)[:160]}")
    elif not p["meals"]:
        fails.append(f"no meals, with {p['slots_ahead']} ahead")
    else:
        fails += [f"{m['slot']} is {m['name']} — not veg" for m in p["meals"]
                  if m.get("dish_id") in not_veg or NOT_VEG.search(m["name"])]
    return _plan_result("plan-veg", "08:00", p, fails, t0,
                        why="spec/done/onboarding-goals.md — the diet is a limit",
                        must_not=["a meal with meat, fish or egg in it, or cooked with them"])


# ─── a run ───────────────────────────────────────────────────────────────────

#: The first run's block, by the group its cases share.
FIRST = "onboarding"


def pick(only: list[str] | None, upto: str | None) -> tuple[list[Case], list[str], list[Case]]:
    """What this run says: the day's cases, the plan's, the first run's.
    `--only` names day groups, the `plan` and `onboarding` blocks, or single
    cases from any of them; `--upto` is the day alone, up to a case."""
    day, plan, first = list(CASES), list(PLAN_IDS), list(ONBOARDING)
    names = {c.id for c in day} | set(plan) | {c.id for c in first}
    if upto:
        ids = [c.id for c in day]
        if upto not in ids:
            raise SystemExit(f"no case {upto!r}; cases: {', '.join(ids)}")
        day, plan, first = day[: ids.index(upto) + 1], [], []
    if only:
        unknown = set(only) - set(GROUPS) - {PLAN, FIRST} - names
        if unknown:
            raise SystemExit(f"no group or case {', '.join(sorted(unknown))}; groups: "
                             f"{', '.join(GROUPS)}, {PLAN}, {FIRST}")
        day = [c for c in day if c.group in only or c.id in only]
        plan = [i for i in plan if PLAN in only or i in only]
        first = [c for c in first if c.group in only or c.id in only]
    return day, plan, first


def _block(group: str) -> str:
    return group if group in (PLAN, FIRST) else "day"


def _case_result(case: Case, rs: list[dict], at: str | None) -> dict:
    _print_case(case, rs)
    return {
        "id": case.id, "group": case.group, "say": case.say, "given": case.given,
        "at": at, "question": case.question, "why": case.why, "known": case.known,
        "expect": [c.says for c in case.checks], "must": case.must,
        "must_not": case.must_not, "passes": sum(bool(r.get("passed")) for r in rs),
        "runs": rs,
    }


async def run(cases: list[Case], plan_ids: list[str], first: list[Case], repeat: int) -> int:
    from httpx import ASGITransport
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    print(f"n2n_eval: building {EVAL_DB} …", flush=True)
    await fresh_database()

    import app.db as db
    from app.config import settings
    from app.llm import model
    from app.main import app
    from evals.fixture import seed_library

    # The day and the first run go side by side, each `repeat` wide.
    engine = create_async_engine(EVAL_URL, pool_size=repeat * 6 + 2, max_overflow=10)
    db.engine = engine
    db.SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        await seed_library(s)
        await s.commit()
    spy()

    today = datetime.now(IST).date()
    env = {"today": today, "Session": Session, "transport": ASGITransport(app=app),
           "clocks": clocks(cases)}
    agent_model, effort = model(), settings().llm_effort
    print(f"n2n_eval: {len(cases)} cases, the day said {repeat}× · {len(plan_ids)} plan · "
          f"{len(first)} first-run cases, {repeat}× · on {agent_model} (effort {effort}), "
          f"today {today}\n", flush=True)

    started = time.monotonic()
    days, firsts = await asyncio.gather(
        asyncio.gather(*(run_day(cases, r, env) for r in range(repeat) if cases)),
        asyncio.gather(*(first_run(first, r, env) for r in range(repeat) if first)))
    plan = await plan_cases(env, plan_ids)
    await engine.dispose()

    first_fail = [next((c.id for c in cases if not d.get(c.id, {}).get("passed")), None)
                  for d in days]
    results = []
    for block, block_cases, clocks_ in ((days, cases, env["clocks"]),
                                        (firsts, first, [None] * len(first))):
        for case, at in zip(block_cases, clocks_, strict=True):
            rs = [d.get(case.id) or _broken(i, "harness: no result") for i, d in enumerate(block)]
            results.append(_case_result(case, rs, at))
    results += plan

    passed = sum(1 for r in results if r["passes"] == len(r["runs"]))
    known_n = sum(1 for r in results if r["passes"] < len(r["runs"]) and r.get("known"))
    failed = len(results) - passed - known_n
    tokens = Counter()
    for r in results:
        for x in r["runs"]:
            tokens["tokens_in"] += x.get("tokens_in") or 0
            tokens["tokens_out"] += x.get("tokens_out") or 0

    took = time.monotonic() - started
    runs_total = sum(len(r["runs"]) for r in results)
    runs_ok = sum(1 for r in results for x in r["runs"] if x.get("passed"))
    print(f"\n{passed} passed · {failed} failed · {known_n} known gaps — of {len(results)} "
          f"cases, {repeat} run{'s' if repeat > 1 else ''} each · {took:.0f}s")
    print(f"cases passing every run: {100 * passed / max(1, len(results)):.1f}% · "
          f"turns passing: {runs_ok}/{runs_total} = {100 * runs_ok / max(1, runs_total):.1f}%")
    blocks = {}
    for b in ("day", PLAN, FIRST):
        rows = [r for r in results if _block(r["group"]) == b]
        if rows:
            blocks[b] = {"cases": len(rows),
                         "passed": sum(1 for r in rows if r["passes"] == len(r["runs"])),
                         "turns": sum(len(r["runs"]) for r in rows),
                         "turns_passed": sum(1 for r in rows for x in r["runs"]
                                             if x.get("passed"))}
    if len(blocks) > 1:
        # The day's own score stays readable beside the blocks run with it.
        for b, n in blocks.items():
            print(f"  {b}: {n['passed']}/{n['cases']} cases · "
                  f"{n['turns_passed']}/{n['turns']} turns")
    if cases:
        print(f"first failure in each day: {first_fail}")
    print(f"agent {tokens['tokens_in']:,} in, {tokens['tokens_out']:,} out")
    by_group = {}
    for g in sorted({r["group"] for r in results}):
        rows = [r for r in results if r["group"] == g]
        by_group[g] = {"cases": len(rows),
                       "passed": sum(1 for r in rows if r["passes"] == len(r["runs"]))}
    reports = BACKEND / "evals" / "reports"
    reports.mkdir(exist_ok=True)
    stamp = datetime.now(IST).strftime("%Y%m%d-%H%M%S")
    path = reports / f"n2n-{stamp}.json"
    path.write_text(json.dumps({
        "id": stamp, "model": agent_model, "effort": effort, "judge": None,
        "today": today.isoformat(), "repeat": repeat, "cases_n": len(results),
        "passed": passed, "failed": failed, "known": known_n, "turns_passed": runs_ok,
        "turns": runs_total, "seconds": round(took), "by_group": by_group, "blocks": blocks,
        "first_failure": first_fail, **tokens, "cases": results},
        indent=1, ensure_ascii=False, default=str))
    print(f"report: {path.relative_to(BACKEND)}")
    return 1 if failed else 0


def _print_case(case: Case, rs: list[dict]) -> None:
    ok = sum(bool(r.get("passed")) for r in rs)
    mark = "✓" if ok == len(rs) else ("~" if case.known else "✗")
    tally = f"{ok}/{len(rs)}" if len(rs) > 1 else ""
    said = f"[{case.question}] {case.say}" if case.question else case.say
    print(f" {mark} {case.id:<15}{tally:>5}  {said}", flush=True)
    seen = Counter(why for r in rs for why in r["failures"])
    for why, n in seen.most_common():
        print(f"       · {why}{f'  (×{n})' if n > 1 else ''}", flush=True)
    if ok < len(rs) and case.known:
        print(f"       (known gap: {case.known})", flush=True)


def main() -> None:
    p = argparse.ArgumentParser(prog="n2n_eval", description=__doc__.split("\n\n")[0].strip())
    p.add_argument("--only", help=f"comma-separated day groups ({', '.join(GROUPS)}), the "
                                  f"{PLAN} and {FIRST} blocks, or single case ids")
    p.add_argument("--upto", help="the day up to and including this case")
    p.add_argument("--repeat", type=int, default=3, help="days run side by side (default 3)")
    p.add_argument("--model", help="the agent's model for this run, instead of .env's")
    p.add_argument("--effort", help="the agent's reasoning effort for this run")
    a = p.parse_args()
    # Before the app reads its settings, which are cached on first use.
    if a.model:
        os.environ["LLM_MODEL"] = a.model
    if a.effort:
        os.environ["LLM_EFFORT"] = a.effort
    only = [g.strip() for g in a.only.split(",")] if a.only else None
    day, plan, first = pick(only, a.upto)
    sys.exit(asyncio.run(run(day, plan, first, max(1, a.repeat))))


if __name__ == "__main__":
    main()
