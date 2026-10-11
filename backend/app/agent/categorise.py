"""
The nightly second look at the payments the agent was unsure about.
spec/in-progress/categorise.md.

One function, `categorise()`, and two doors onto it: the `categorise_now` tool
and `scripts/categorise.py`. No route — the phone talks to the agent.

Four tiers, cheapest first. The dictionary and the rules cost nothing and
decide most rows; what is left goes to the model in **one** call, with the
skill file as its system prompt; what the model is not sure of is left for the
user as a `proposed` card. Everything examined gets a `predictions` row, so the
learning starts the first night whether or not anything was written.

What is learned is learned from rows every run and never stored — the house
rule. A payee's category is the mode of its past rows; a band is a gap in the
sorted amounts; a rule learned from a correction is the correction itself,
read back. Delete the row and the lesson goes with it, which is right.
"""

from __future__ import annotations

import json
import re
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import llm
from app.models.paisa import Counterparty, Prediction, Transaction
from app.routes import writes
from app.schemas.writes import TransactionPatch

IST = ZoneInfo("Asia/Kolkata")
SKILL_FILE = Path(__file__).with_name("skills") / "categorise.md"

#: Written without asking at or above this. spec/agent.md rule: below it, a
#: suggestion, never a silent write.
SILENT = 0.85
#: What the dictionary tier claims — history all one way, amount in band.
DICTIONARY = 0.95
#: A payee met for the first time is always asked about once, whatever the
#: model says. spec/paisa-categorise.md §5.6 output validation.
NEW_PAYEE_CAP = 0.84
#: One call a night; the backlog is small and the call is one either way.
BATCH_CAP = 40
#: Band learning. A gap wider than this share of the range starts a new band;
#: fewer rows than this and a category has no band at all.
BAND_GAP = 0.40
BAND_MIN_ROWS = 5
#: A payee needs this many rows before its history counts, and this share in
#: one category before the dictionary speaks for it.
PAYEE_MIN_ROWS = 3
DOMINANT = 0.80
#: Two payments this close share a context — a ride and the shop it stopped at.
SESSION_MINUTES = 15


# ─── reading one row ─────────────────────────────────────────────────────────

_NOISE = re.compile(r"[\d₹,.()\-–—/&+:;!?\"'*]+")


def payee_key(t: Transaction) -> str:
    """Who was paid, as a key. The payment system's name when there is one;
    otherwise the user's own words, normalised — *Rapido* eleven times is a
    payee for this purpose, and that is what lets the dictionary cover the
    rows that have no counterparty, which is three quarters of them."""
    if t.counterparty_name:
        return t.counterparty_name.strip().upper()
    words = _NOISE.sub(" ", t.description.lower()).split()
    return " ".join(words) or t.description.strip().lower()


def clock_known(at: datetime) -> bool:
    """False for the two timestamps that mean *time unknown*: the import's
    noon UTC (spec/done/paisa-import.md) and a bare noon IST, which is what a
    write without a stated clock gets. A real payment at exactly 12:00:00 is
    misread once in a very long while; a fake evening every day is worse."""
    u = at.astimezone(UTC)
    if (u.hour, u.minute, u.second) == (12, 0, 0):
        return False
    i = at.astimezone(IST)
    return (i.hour, i.minute, i.second) != (12, 0, 0)


def working_day(d: date) -> bool:
    return d.weekday() < 5


def _norm_desc(t: Transaction) -> str:
    return _NOISE.sub(" ", t.description.lower()).strip()


def description_is_raw_payee(t: Transaction) -> bool:
    """The notification shape: the description *is* the payee's name, perhaps
    with a courtesy prefix. The only case a description is ever rewritten."""
    if not t.counterparty_name:
        return False
    d = _norm_desc(t)
    p = _NOISE.sub(" ", t.counterparty_name.lower()).strip()
    return d == p or d.removeprefix("mr ").removeprefix("mrs ").strip() == p


# ─── what the ledger has taught ──────────────────────────────────────────────

@dataclass
class Payee:
    key: str
    n: int = 0
    by_category: Counter = field(default_factory=Counter)
    amounts: list[int] = field(default_factory=list)
    descriptions: Counter = field(default_factory=Counter)
    weekdays: int = 0
    last_seen: date | None = None
    label: str | None = None        # counterparties.display_name, the user's word
    is_peer: bool = False

    @property
    def top(self) -> tuple[str, float]:
        cat, n = self.by_category.most_common(1)[0]
        return cat, n / self.n

    @property
    def band(self) -> tuple[int, int] | None:
        return (min(self.amounts), max(self.amounts)) if self.n >= PAYEE_MIN_ROWS else None

    @property
    def median(self) -> int:
        return int(statistics.median(self.amounts))


@dataclass
class Learned:
    """Everything the tiers and the skill file read. Built from rows at run
    time; nothing here is stored."""

    categories: dict[str, list[str]]             # name → sample descriptions
    counts: Counter                              # name → rows
    payees: dict[str, Payee]
    bands: dict[str, list[tuple[int, int]]]      # name → [(lo, hi)] paise
    weekday_share: dict[str, float]              # name → share of rows on Mon–Fri
    routines: list[str]
    corrections: list[str]
    rows: int


def cluster(amounts: list[int], gap: float = BAND_GAP) -> list[tuple[int, int]]:
    """1-D bands: sort, and start a new band wherever consecutive amounts are
    further apart than `gap` of the whole range. Transport's 40–60 and 114–160
    fall out of this on the real rows; typing either number in would break the
    day the user moves city."""
    xs = sorted(amounts)
    if not xs:
        return []
    span = xs[-1] - xs[0]
    if span == 0:
        return [(xs[0], xs[0])]
    bands, lo, prev = [], xs[0], xs[0]
    for x in xs[1:]:
        if x - prev > gap * span:
            bands.append((lo, prev))
            lo = x
        prev = x
    bands.append((lo, prev))
    return bands


def _rupees(p: int) -> str:
    return f"₹{round(p / 100):,}"


def _hours_window(hours: list[int]) -> str:
    xs = sorted(hours)
    lo, hi = xs[len(xs) // 4], xs[(3 * len(xs)) // 4]
    return f"{lo:02d}:00–{hi + 1:02d}:00"


def learn_from(rows: list[Transaction], labels: dict[str, Counterparty],
               corrections: list[str]) -> Learned:
    """Pure: the learned state from labelled rows. `rows` are the ground truth
    — expenses at confidence 1.0 that are not *Other* — already cut to the
    dates the caller wants (the eval learns from the first half only)."""
    cats: dict[str, Counter] = defaultdict(Counter)
    by_cat_amounts: dict[str, list[int]] = defaultdict(list)
    by_cat_weekday: dict[str, list[bool]] = defaultdict(list)
    by_cat_hours: dict[str, list[int]] = defaultdict(list)
    payees: dict[str, Payee] = {}
    for t in rows:
        cats[t.category][t.description] += 1
        by_cat_amounts[t.category].append(t.amount_paise)
        by_cat_weekday[t.category].append(working_day(t.local_day))
        if clock_known(t.occurred_at):
            by_cat_hours[t.category].append(t.occurred_at.astimezone(IST).hour)
        key = payee_key(t)
        p = payees.setdefault(key, Payee(key))
        p.n += 1
        p.by_category[t.category] += 1
        p.amounts.append(t.amount_paise)
        p.descriptions[t.description] += 1
        p.weekdays += working_day(t.local_day)
        p.last_seen = max(p.last_seen or t.local_day, t.local_day)
        cp = labels.get(key)
        if cp is not None:
            p.label = cp.display_name
            p.is_peer = cp.is_peer
    routines = []
    for cat, hours in sorted(by_cat_hours.items()):
        if len(hours) >= PAYEE_MIN_ROWS:
            wd = sum(by_cat_weekday[cat]) / len(by_cat_weekday[cat])
            routines.append(f"{cat}: usually {_hours_window(hours)} "
                            f"({len(hours)} rows with a clock, {wd:.0%} on working days)")
    return Learned(
        categories={c: [d for d, _ in cats[c].most_common(3)] for c in cats},
        counts=Counter({c: sum(cats[c].values()) for c in cats}),
        payees=payees,
        bands={c: cluster(a) for c, a in by_cat_amounts.items() if len(a) >= BAND_MIN_ROWS},
        weekday_share={c: sum(w) / len(w) for c, w in by_cat_weekday.items()},
        routines=routines,
        corrections=corrections,
        rows=len(rows),
    )


async def learn(session: AsyncSession, user: str, before: date | None = None) -> Learned:
    """The learned state from this ledger. `before` cuts the rows to those
    strictly earlier than a date — the eval's train/test split."""
    clauses = [Transaction.user_id == user, Transaction.deleted_at.is_(None),
               Transaction.kind == "expense", Transaction.confidence >= 1.0,
               Transaction.category != "Other"]
    if before is not None:
        clauses.append(Transaction.local_day < before)
    rows = list((await session.scalars(
        select(Transaction).where(*clauses).order_by(Transaction.occurred_at))).all())
    cps = (await session.scalars(select(Counterparty).where(
        Counterparty.user_id == user, Counterparty.deleted_at.is_(None)))).all()
    labels = {c.raw_name.strip().upper(): c for c in cps}
    # A correction is a rule the user taught, read back as the fact it is.
    q = (select(Prediction, Transaction)
         .join(Transaction, Transaction.id == Prediction.transaction_id)
         .where(Prediction.user_id == user, Prediction.corrected_at.isnot(None),
                Prediction.actual_category.isnot(None),
                Prediction.actual_category != Prediction.pred_category,
                Transaction.deleted_at.is_(None))
         .order_by(Prediction.corrected_at.desc()).limit(40))
    if before is not None:
        q = q.where(Transaction.local_day < before)
    corrections = [
        f"{t.counterparty_name or t.description} at {_rupees(t.amount_paise)} on "
        f"{t.local_day:%a %d %b} was {p.actual_category}"
        + (f" · {p.actual_description}" if p.actual_description
           and p.actual_description != t.description else "")
        + f", not {p.pred_category}"
        for p, t in (await session.execute(q)).all()
    ]
    return learn_from(rows, labels, corrections)


# ─── the skill file ──────────────────────────────────────────────────────────

def skill_file(learned: Learned) -> str:
    """The static half from disk, the generated half from rows. One document,
    the sub-agent's system prompt. Served to the user one day so they can see
    what the agent believes about them — it is a report, so serving it is a
    read, not a design."""
    static = SKILL_FILE.read_text()
    out = [static.rstrip(), ""]
    out.append(f"{learned.rows} labelled payments. Amounts in rupees.")
    out.append("")
    out.append("## Categories in use")
    for cat, n in learned.counts.most_common():
        samples = " · ".join(f"“{d}”" for d in learned.categories[cat])
        out.append(f"- **{cat}** ({n}) — {samples}")
    out.append("")
    out.append("## Learned payees")
    known = sorted((p for p in learned.payees.values() if p.n >= PAYEE_MIN_ROWS),
                   key=lambda p: -p.n)
    if known:
        out.append("| payee | label | category | rows | amounts | working days | last seen |")
        out.append("|---|---|---|---|---|---|---|")
        for p in known:
            cat, share = p.top
            lo, hi = p.band or (p.median, p.median)
            label = p.label or p.descriptions.most_common(1)[0][0]
            catcell = cat if share >= DOMINANT else f"{cat} ({share:.0%})"
            out.append(f"| {p.key} | {label} | {catcell} | {p.n} | "
                       f"{_rupees(lo)}–{_rupees(hi)} | {p.weekdays / p.n:.0%} | "
                       f"{p.last_seen:%d %b} |")
    else:
        out.append("(no payee has three rows yet)")
    peers = sorted(p.key for p in learned.payees.values() if p.is_peer)
    if peers:
        out.append("")
        out.append("Paid this person back at least once, so a person, not a shop: "
                   + ", ".join(peers))
    out.append("")
    out.append("## Learned amount bands")
    if learned.bands:
        for cat, bands in sorted(learned.bands.items()):
            out.append(f"- {cat}: " + ", ".join(f"{_rupees(lo)}–{_rupees(hi)}" for lo, hi in bands))
    else:
        out.append("(no category has five rows yet)")
    out.append("")
    out.append("## Routines")
    out.extend(f"- {r}" for r in learned.routines) if learned.routines else out.append(
        "(no category has three rows with a real clock yet)")
    out.append("")
    out.append("## Rules learned from corrections")
    out.extend(f"- {c}" for c in learned.corrections) if learned.corrections else out.append(
        "(none yet)")
    out.append("")
    return "\n".join(out)


# ─── signals, snapshotted ────────────────────────────────────────────────────

def signals_for(t: Transaction, learned: Learned, prev: Transaction | None) -> dict:
    """What the tiers and the model see for one row. Stored on the prediction
    exactly as computed: `payee_seen_count` was 3 tonight and is 47 later, and
    recomputing it would make a training example that never existed."""
    key = payee_key(t)
    p = learned.payees.get(key)
    known = clock_known(t.occurred_at)
    at = t.occurred_at.astimezone(IST)
    band = p.band if p else None
    in_band = bool(band and band[0] <= t.amount_paise <= band[1])
    matches = [c for c, bands in learned.bands.items()
               if any(lo <= t.amount_paise <= hi for lo, hi in bands)]
    mins = None
    if prev is not None and known and clock_known(prev.occurred_at):
        mins = int((t.occurred_at - prev.occurred_at).total_seconds() // 60)
    return {
        "amount_paise": t.amount_paise, "method": t.method,
        "hour_of_day": at.hour if known else None,
        "day_of_week": t.local_day.weekday(), "is_working_day": working_day(t.local_day),
        "payee_key": key, "payee_seen_count": p.n if p else 0,
        "payee_band": {"lo": band[0], "hi": band[1], "median": p.median} if band else None,
        "amount_in_payee_band": in_band,
        "amount_band_match": matches,
        "has_bidirectional": bool(p and p.is_peer), "in_contacts": False,
        "mins_since_last_txn": mins,
        "last_txn_category": prev.category if prev is not None else None,
        "description_is_raw_payee": description_is_raw_payee(t),
        "motion_before": None, "location_cluster": None,
    }


# ─── the tiers ───────────────────────────────────────────────────────────────

@dataclass
class Guess:
    category: str
    confidence: float
    by: str                      # dictionary | rules | llm
    why: str
    description: str | None = None


def tier_dictionary(t: Transaction, s: dict, learned: Learned) -> Guess | None:
    p = learned.payees.get(s["payee_key"])
    if p is None or p.n < PAYEE_MIN_ROWS or not s["amount_in_payee_band"]:
        return None
    cat, share = p.top
    if share < DOMINANT:
        return None
    label = p.label or p.descriptions.most_common(1)[0][0]
    return Guess(cat, DICTIONARY, "dictionary",
                 f"known payee ({p.n}×, {share:.0%} {cat}), amount in band",
                 description=label if s["description_is_raw_payee"] else None)


def tier_rules(t: Transaction, s: dict, learned: Learned) -> Guess | None:
    """Starting weights — the eval tunes them; the spec records the shape.
    The weekday gate is learned too: a category whose rows are nearly all on
    working days is not this payment when today is not one."""
    score, cat, why = 0.0, None, []
    p = learned.payees.get(s["payee_key"])
    if p is not None and p.n >= PAYEE_MIN_ROWS:
        cat = p.top[0]
        if s["amount_in_payee_band"]:
            score += 0.50
            why.append("payee history, amount in band")
        else:
            score += 0.15
            why.append("payee history, amount outside its band")
    matches = s["amount_band_match"]
    if len(matches) == 1:
        score += 0.30
        cat = cat or matches[0]
        why.append(f"only {matches[0]} has a band here")
        if learned.weekday_share.get(matches[0], 0) >= 0.7 and not s["is_working_day"]:
            score -= 0.30
            why.append("but not a working day")
    if s["mins_since_last_txn"] is not None and s["mins_since_last_txn"] <= SESSION_MINUTES:
        score += 0.10
        why.append(f"{s['mins_since_last_txn']} min after the last payment")
    if s["payee_seen_count"] == 0:
        score -= 0.20
        why.append("payee never seen")
    if cat is None:
        return None
    return Guess(cat, round(max(0.0, min(1.0, score)), 2), "rules", "; ".join(why))


def _item(t: Transaction, s: dict) -> dict:
    """One row as the model sees it — compact, and only what the skill file
    teaches it to read."""
    return {
        "id": t.id, "amount": round(t.amount_paise / 100),
        "payee": t.counterparty_name, "seen": s["payee_seen_count"],
        "band": ([round(s["payee_band"]["lo"] / 100), round(s["payee_band"]["hi"] / 100)]
                 if s["payee_band"] else None),
        "hour": s["hour_of_day"], "weekday": t.local_day.strftime("%a"),
        "working_day": s["is_working_day"],
        "mins_since_last": s["mins_since_last_txn"], "last_category": s["last_txn_category"],
        "description": t.description, "description_is_payee": s["description_is_raw_payee"],
    }


def parse_and_validate(text: str, items: list[dict], learned: Learned) -> dict[str, Guess]:
    """What stands between the model and the ledger, in the spec's order:
    unparseable → nothing (every row falls to review); a category outside the
    live set → that row dropped; a sure answer about a never-seen payee →
    capped; a description for a row whose words are the user's → ignored."""
    try:
        raw = text.strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            raw = raw[raw.find("["):]
        data = json.loads(raw)
        assert isinstance(data, list)
    except (ValueError, AssertionError):
        return {}
    by_id = {i["id"]: i for i in items}
    out: dict[str, Guess] = {}
    for g in data:
        if not isinstance(g, dict) or g.get("id") not in by_id:
            continue
        cat = g.get("category")
        if cat not in learned.counts:
            continue
        try:
            conf = float(g.get("confidence", 0))
        except (TypeError, ValueError):
            conf = 0.0
        conf = max(0.0, min(1.0, conf))
        item = by_id[g["id"]]
        if item["seen"] == 0 and conf > NEW_PAYEE_CAP:
            conf = NEW_PAYEE_CAP
        desc = g.get("description") if item["description_is_payee"] else None
        out[g["id"]] = Guess(cat, round(conf, 2), "llm", str(g.get("why") or "")[:200],
                             description=(str(desc)[:60] if desc else None))
    return out


async def tier_model(items: list[dict], learned: Learned, *, model_id: str | None = None,
                     effort: str | None = None) -> tuple[dict[str, Guess], str]:
    """One call for the whole batch. Returns the guesses and `model@effort`
    they came from, for the prediction row. The overrides are the eval's."""
    if not items:
        return {}, ""
    system = skill_file(learned)
    payload = json.dumps(items, ensure_ascii=False)
    text, used = await llm.categorise(system, payload, model_id=model_id, effort=effort)
    return parse_and_validate(text, items, learned), used


# ─── the run ─────────────────────────────────────────────────────────────────

async def pending(session: AsyncSession, user: str, day: date | None = None,
                  cap: int = BATCH_CAP) -> list[Transaction]:
    """Which rows get the second look: expenses the agent guessed at and the
    user never confirmed, or filed as *Other* — and nobody has been asked
    about yet. Ground truth (1.0, not Other) is never re-examined."""
    asked = select(Prediction.transaction_id).where(
        Prediction.user_id == user, Prediction.corrected_at.is_(None))
    clauses = [Transaction.user_id == user, Transaction.deleted_at.is_(None),
               Transaction.kind == "expense",
               (Transaction.confidence < 1.0) | (Transaction.category == "Other"),
               Transaction.id.notin_(asked)]
    if day is not None:
        clauses.append(Transaction.local_day == day)
    return list((await session.scalars(
        select(Transaction).where(*clauses)
        .order_by(Transaction.local_day, Transaction.occurred_at).limit(cap))).all())


async def _previous(session: AsyncSession, user: str, t: Transaction) -> Transaction | None:
    return await session.scalar(
        select(Transaction).where(Transaction.user_id == user, Transaction.deleted_at.is_(None),
                                  Transaction.occurred_at < t.occurred_at)
        .order_by(Transaction.occurred_at.desc()).limit(1))


def decide(t: Transaction, s: dict, learned: Learned) -> Guess | None:
    """Tiers 0 and 1. None means the row goes to the model."""
    g = tier_dictionary(t, s, learned)
    if g is None:
        g = tier_rules(t, s, learned)
        if g is not None and g.confidence < SILENT:
            return None      # a weak rule is not an answer; let the model look
    return g


def may_write(t: Transaction, g: Guess) -> bool:
    """A silent write goes over a guess, never over a fact. *Other* at 1.0 is
    the user saying they did not know — a fact about the user — so it is
    proposed, not decided."""
    return t.confidence < 1.0 and g.confidence >= SILENT


def agrees(t: Transaction, g: Guess) -> bool:
    """The second look landed on the category the row already has.

    That is not a question. The first live run asked five of nineteen — *EMI →
    EMI?*, *Doctor → Health/Diet?* — and a queue that asks about rows it agrees
    with is a queue that stops being read. It is not a silent write either: two
    independent estimates agreeing is evidence, so the row's confidence moves
    up to the better of the two and the amber dot stays. Only the user's own
    word makes it 1.0."""
    return (t.confidence < 1.0 and g.category == t.category
            and t.category != "Other" and g.confidence > t.confidence)


async def categorise(session: AsyncSession, user: str, day: date | None = None, *,
                     dry: bool = False, use_model: bool = True) -> dict:
    """The batch. Returns the report the tool and the script both print:
    what was written, what is proposed, and how each tier did."""
    rows = await pending(session, user, day)
    learned = await learn(session, user)
    report: dict = {"examined": len(rows), "written": [], "agreed": [], "proposed": [],
                    "by_tier": {"dictionary": 0, "rules": 0, "llm": 0, "unsure": 0},
                    "labelled_rows": learned.rows}
    if not rows:
        return report

    sig: dict[str, dict] = {}
    guess: dict[str, Guess] = {}
    to_model: list[dict] = []
    for t in rows:
        s = signals_for(t, learned, await _previous(session, user, t))
        sig[t.id] = s
        g = decide(t, s, learned)
        if g is not None:
            guess[t.id] = g
        else:
            to_model.append(_item(t, s))
    used = ""
    if use_model and to_model:
        from_model, used = await tier_model(to_model, learned)
        guess.update(from_model)

    for t in rows:
        g = guess.get(t.id)
        if g is None:
            # The model dropped it or the batch did not parse: still recorded,
            # at zero, so the user is asked and the miss is counted.
            g = Guess(t.category, 0.0, "llm", "no usable prediction")
        report["by_tier"][g.by if g.confidence > 0 else "unsure"] += 1
        wrote = agreed = False
        patch: dict = {}
        if may_write(t, g):
            patch = {"category": g.category, "confidence": g.confidence}
            if g.description and sig[t.id]["description_is_raw_payee"]:
                patch["description"] = g.description
            wrote = True
        elif agrees(t, g):
            # The category is already right; only how sure the ledger is moves.
            patch = {"confidence": g.confidence}
            agreed = True
        if patch and not dry:
            # Through the same route the agent and the UI use. The prediction
            # goes in *after*, because the route closes any open prediction it
            # finds and the batch's own write must not read as a correction.
            await writes.patch_transaction(t.id, TransactionPatch(**patch), session, user)
        if not dry:
            session.add(Prediction(
                user_id=user, transaction_id=t.id, predicted_by=g.by,
                model=used if g.by == "llm" else None, signals=sig[t.id],
                pred_category=g.category, pred_description=g.description,
                confidence=g.confidence, reasoning=g.why,
            ))
        entry = {"transaction_id": t.id, "amount_paise": t.amount_paise,
                 "payee": t.counterparty_name or t.description, "local_day": t.local_day,
                 "was": t.category,
                 "guess": {"category": g.category, "description": g.description,
                           "confidence": g.confidence, "why": g.why, "by": g.by}}
        bucket = "written" if wrote else "agreed" if agreed else "proposed"
        report[bucket].append(entry)
    if not dry:
        await session.commit()
    return report


async def to_review(session: AsyncSession, user: str) -> list[dict]:
    """Open proposals — asked, not yet answered — for `paisa_report`. Not
    scoped to a date, like udhaar's `open`: an unanswered question from last
    month is still a question."""
    q = (select(Prediction, Transaction)
         .join(Transaction, Transaction.id == Prediction.transaction_id)
         .where(Prediction.user_id == user, Prediction.corrected_at.is_(None),
                Transaction.deleted_at.is_(None),
                (Transaction.confidence < 1.0) | (Transaction.category == "Other"))
         .order_by(Transaction.local_day.desc(), Prediction.created_at.desc()))
    seen: set[str] = set()
    out = []
    for p, t in (await session.execute(q)).all():
        if t.id in seen:
            continue
        seen.add(t.id)
        # The batch's own writes and agreements leave an open prediction — it
        # closes when the *user* answers. Neither is a question: one it decided,
        # the other it corroborated. Only a disagreement is asked about.
        if t.category == p.pred_category and t.category != "Other":
            continue
        out.append({"transaction_id": t.id, "amount_paise": t.amount_paise,
                    "payee": t.counterparty_name or t.description, "local_day": t.local_day,
                    "was": t.category,
                    "guess": {"category": p.pred_category,
                              "description": p.pred_description,
                              "confidence": p.confidence, "why": p.reasoning,
                              "by": p.predicted_by}})
    return out
