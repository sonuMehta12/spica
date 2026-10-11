"""spec/in-progress/categorise.md — the nightly batch and the skill file.

The model is faked. What is ours: reading a row honestly (the sentinel clock),
learning bands and payees from rows, the free tiers firing only when they
should, what stands between the model and the ledger, what a tier may and
may not write, and the prediction trail a correction closes. Whether the
model picks the right category is `scripts/categorise_eval.py`'s question.
"""

import json
from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest

from tests.helpers import make_transaction

pytestmark = pytest.mark.asyncio(loop_scope="session")

# Pinned to May 2026 so no other test's rows are in the way, and every
# labelled row here is ground truth: confidence 1.0, not Other.
#
# Every test takes `client`, the pure ones included: importing `app.agent.
# categorise` imports `app.db`, which caches `settings()` — so the import must
# come after the database fixture has pointed DATABASE_URL at cortex_test, or
# alembic quietly migrates the dev database and the seed hits an empty one.
DAYS = [f"2026-05-{d:02d}" for d in range(1, 29)]


def D(i: int) -> date:
    return date.fromisoformat(DAYS[i])


async def tx(client, day, amount, category, description, **over):
    body = {"local_day": day, "occurred_at": f"{day}T12:00:00+05:30", "amount_paise": amount,
            "category": category, "description": description}
    body.update(over)
    r = await make_transaction(client, **body)
    assert r.status_code == 201, r.text
    return r.json()


class FakeCategoriser:
    """The seam, scripted: whatever text the test wants the model to return."""

    def __init__(self, text):
        self.text, self.sent = text, []
        self.responses = SimpleNamespace(create=self._create)

    async def _create(self, **kw):
        self.sent.append(kw)
        return SimpleNamespace(output=[], output_text=self.text,
                               usage=SimpleNamespace(input_tokens=1, output_tokens=1))


@pytest.fixture
def model(monkeypatch):
    def install(text):
        fake = FakeCategoriser(text)
        monkeypatch.setattr("app.llm.client", lambda: fake)
        return fake
    return install


async def rows_by_id(client, *ids):
    r = await client.get("/transactions", params={"ids": ",".join(ids)})
    assert r.status_code == 200, r.text
    return {x["id"]: x for x in r.json()}


async def _user(db_session):
    from tests.helpers import the_user
    return await the_user(db_session)


# ─── reading one row ─────────────────────────────────────────────────────────

async def test_the_sentinel_clock_is_not_a_time(client):
    """Noon UTC is the import's *time unknown*; bare noon IST is a write with
    no stated clock. Neither is evening."""
    from app.agent.categorise import clock_known
    assert clock_known(datetime(2026, 8, 20, 12, 0, 0, tzinfo=UTC)) is False
    assert clock_known(datetime.fromisoformat("2026-08-20T12:00:00+05:30")) is False
    assert clock_known(datetime.fromisoformat("2026-08-20T19:42:00+05:30")) is True


async def test_bands_come_from_gaps_in_the_amounts(client):
    """The research's nine Transport amounts split at the 61–113 gap. A flat
    list is one band; nothing is hardcoded."""
    from app.agent.categorise import cluster
    research = [40, 40, 60, 114, 114, 130, 130, 140, 160]
    assert cluster([x * 100 for x in research]) == [(4000, 6000), (11400, 16000)]
    assert cluster([13000, 13000, 13000]) == [(13000, 13000)]
    assert cluster([]) == []


async def test_a_payee_is_the_payment_systems_name_or_the_users_words(client):
    from app.agent.categorise import description_is_raw_payee, payee_key
    raw = SimpleNamespace(counterparty_name="MOHAN LAL", description="Mr MOHAN LAL")
    words = SimpleNamespace(counterparty_name=None, description="Rapido (shaam) ₹135")
    assert payee_key(raw) == "MOHAN LAL" and description_is_raw_payee(raw)
    assert payee_key(words) == "rapido shaam" and not description_is_raw_payee(words)


# ─── learning, and the tiers ─────────────────────────────────────────────────

async def _seed_labelled(client):
    """Five Rapido rides in a band, one paan-shop payee three times, and a
    category with too few rows to have a band."""
    for i, amt in enumerate((13000, 13000, 14000, 12000, 15000)):
        await tx(client, DAYS[i], amt, "Test Transport", "Rapido")
    for i, amt in enumerate((4400, 6000, 8300)):
        await tx(client, DAYS[5 + i], amt, "Test Treat", "Cat-Paan",
                 counterparty_name="CAT PAAN WALA")
    await tx(client, DAYS[9], 20000, "Test Rare", "Once")


async def test_the_dictionary_speaks_only_for_a_payee_it_knows_in_band(client, db_session):
    """Known payee, amount in its band → 0.95. Same payee, amount far outside
    → not the dictionary's call (the ₹700 gym fees at the paan shop)."""
    from app.agent import categorise as C
    await _seed_labelled(client)
    user = await _user(db_session)
    learned = await C.learn(db_session, user)
    assert learned.payees["CAT PAAN WALA"].n == 3
    assert "Test Rare" not in learned.bands, "one row is not a band"
    assert learned.bands["Test Transport"] == [(12000, 15000)]

    in_band = SimpleNamespace(counterparty_name="CAT PAAN WALA", description="CAT PAAN WALA",
                              amount_paise=6000, method=None,
                              occurred_at=datetime(2026, 5, 20, 12, 0, tzinfo=UTC),
                              local_day=D(20), category="Other")
    s = C.signals_for(in_band, learned, None)
    assert s["hour_of_day"] is None and s["payee_seen_count"] == 3 and s["amount_in_payee_band"]
    g = C.tier_dictionary(in_band, s, learned)
    assert g and g.category == "Test Treat" and g.confidence == C.DICTIONARY
    assert g.description == "Cat-Paan", "the notification shape gets the learned label"

    out_of_band = SimpleNamespace(**{**in_band.__dict__, "amount_paise": 70000})
    s2 = C.signals_for(out_of_band, learned, None)
    assert C.tier_dictionary(out_of_band, s2, learned) is None
    assert C.decide(out_of_band, s2, learned) is None, "a weak rule defers to the model"


async def test_the_users_own_words_are_a_payee_too(client, db_session):
    """*Rapido* five times has no counterparty and is still known — that is
    what makes the dictionary cover the rows without a payee."""
    from app.agent import categorise as C
    user = await _user(db_session)
    learned = await C.learn(db_session, user)
    ride = SimpleNamespace(counterparty_name=None, description="Rapido", amount_paise=13500,
                           method=None, occurred_at=datetime(2026, 5, 21, 12, 0, tzinfo=UTC),
                           local_day=D(21), category="Other")
    s = C.signals_for(ride, learned, None)
    g = C.tier_dictionary(ride, s, learned)
    assert g and g.category == "Test Transport" and g.description is None


# ─── what stands between the model and the ledger ────────────────────────────

def _learned_with(*cats):
    from collections import Counter

    from app.agent.categorise import Learned
    return Learned(categories={c: [] for c in cats}, counts=Counter({c: 5 for c in cats}),
                   payees={}, bands={}, weekday_share={}, routines=[], corrections=[], rows=5)


async def test_validation_in_the_specs_order(client):
    from app.agent.categorise import NEW_PAYEE_CAP, parse_and_validate
    learned = _learned_with("Khana/Grocery", "Transport")
    items = [{"id": "a", "seen": 0, "description_is_payee": True},
             {"id": "b", "seen": 4, "description_is_payee": False}]
    # unparseable → nothing, so every row falls to review
    assert parse_and_validate("sorry, here you go:", items, learned) == {}
    good = json.dumps([
        {"id": "a", "category": "Transport", "confidence": 0.97, "why": "x", "description": "auto"},
        {"id": "b", "category": "Vibes", "confidence": 0.9, "why": "x"},
        {"id": "zzz", "category": "Transport", "confidence": 0.9, "why": "not asked"},
    ])
    out = parse_and_validate(good, items, learned)
    assert set(out) == {"a"}, "an unknown category and an unknown id are dropped"
    assert out["a"].confidence == NEW_PAYEE_CAP, "a never-seen payee is capped"
    assert out["a"].description == "auto"
    fenced = "```json\n" + json.dumps([{"id": "b", "category": "Transport", "confidence": 0.9,
                                        "description": "rewritten", "why": "x"}]) + "\n```"
    out = parse_and_validate(fenced, items, learned)
    assert out["b"].confidence == 0.9 and out["b"].description is None, \
        "a description for a row in the user's own words is ignored"


# ─── the run: what it writes, and what it never does ─────────────────────────

async def test_a_sure_guess_writes_and_an_unsure_one_proposes(client, db_session, model):
    """Two agent guesses at 0.7. The model is sure about one (a known payee,
    so no cap) and not the other. The first is written with the model's
    confidence, the second is proposed; both get a prediction with the
    signals as seen."""
    from sqlalchemy import select

    from app.agent import categorise as C
    from app.models.paisa import Prediction
    user = await _user(db_session)
    sure = await tx(client, DAYS[15], 5000, "Other", "Cat-Paan", confidence=0.7,
                    counterparty_name="CAT PAAN WALA")
    unsure = await tx(client, DAYS[16], 51200, "Other", "T-shirt", confidence=0.7)
    fake = model(json.dumps([
        {"id": sure["id"], "category": "Test Treat", "confidence": 0.9, "why": "known"},
        {"id": unsure["id"], "category": "Test Rare", "confidence": 0.6, "why": "guess"},
    ]))
    # The dictionary takes the in-band known payee before the model sees it,
    # so the model is asked about the T-shirt only.
    report = await C.categorise(db_session, user, D(16))
    assert report["examined"] == 1 and report["proposed"][0]["transaction_id"] == unsure["id"]
    report = await C.categorise(db_session, user, D(16))
    assert report["examined"] == 0, "asked once: an open prediction is not re-examined"

    report = await C.categorise(db_session, user, D(15))
    [w] = report["written"]
    assert w["transaction_id"] == sure["id"] and w["guess"]["by"] == "dictionary"
    assert fake.sent == [] or len(fake.sent) == 1

    rows = await rows_by_id(client, sure["id"], unsure["id"])
    assert rows[sure["id"]]["category"] == "Test Treat"
    assert rows[sure["id"]]["confidence"] == C.DICTIONARY
    assert rows[sure["id"]]["description"] == "Cat-Paan", "the raw payee name became the label"
    assert rows[unsure["id"]]["category"] == "Other", "below 0.85 nothing is written"
    assert rows[unsure["id"]]["description"] == "T-shirt"

    preds = (await db_session.scalars(select(Prediction).where(
        Prediction.transaction_id.in_([sure["id"], unsure["id"]])))).all()
    assert len(preds) == 2
    by = {p.transaction_id: p for p in preds}
    assert by[sure["id"]].predicted_by == "dictionary"
    assert by[sure["id"]].signals["payee_seen_count"] == 3
    assert by[unsure["id"]].predicted_by == "llm" and by[unsure["id"]].confidence == 0.6
    assert by[unsure["id"]].signals["hour_of_day"] is None


async def test_ground_truth_is_never_re_examined_and_other_at_one_is_only_proposed(
        client, db_session, model):
    from app.agent import categorise as C
    user = await _user(db_session)
    fact = await tx(client, DAYS[17], 9900, "Test Treat", "Cat-Paan",
                    counterparty_name="CAT PAAN WALA")
    other = await tx(client, DAYS[17], 30000, "Other", "Kharcha - kya tha?")
    model(json.dumps([{"id": other["id"], "category": "Test Rare", "confidence": 0.99,
                       "why": "sure"}]))
    report = await C.categorise(db_session, user, D(17))
    ids = {e["transaction_id"] for e in report["written"] + report["proposed"]}
    assert fact["id"] not in ids, "a row the user categorised at 1.0 is ground truth"
    assert report["written"] == [] and report["proposed"][0]["transaction_id"] == other["id"]
    assert (await rows_by_id(client, other["id"]))[other["id"]]["category"] == "Other", \
        "Other at 1.0 is a fact about the user: proposed, never decided"


async def test_a_correction_closes_the_prediction_and_becomes_a_rule(client, db_session, model):
    """The user answers a proposal through the same PATCH the agent uses. The
    prediction records actual_*, and the next skill file carries the rule."""
    from sqlalchemy import select

    from app.agent import categorise as C
    from app.models.paisa import Prediction
    user = await _user(db_session)
    row = await tx(client, DAYS[18], 15000, "Other", "Sunday fruit", confidence=0.7)
    model(json.dumps([{"id": row["id"], "category": "Test Transport", "confidence": 0.7,
                       "why": "commute band"}]))
    await C.categorise(db_session, user, D(18))
    review = (await client.get("/paisa/summary", params={
        "to": DAYS[27], "fields": "to_review"})).json()["to_review"]
    mine = [r for r in review if r["transaction_id"] == row["id"]]
    assert mine and mine[0]["guess"]["category"] == "Test Transport"

    r = await client.patch(f"/transactions/{row['id']}", json={"category": "Test Rare"})
    assert r.status_code == 200
    pred = await db_session.scalar(select(Prediction).where(Prediction.transaction_id == row["id"]))
    await db_session.refresh(pred)
    assert pred.actual_category == "Test Rare" and pred.corrected_at is not None
    review = (await client.get("/paisa/summary", params={
        "to": DAYS[27], "fields": "to_review"})).json()["to_review"]
    assert not [x for x in review if x["transaction_id"] == row["id"]], "answered, so not asked"
    learned = await C.learn(db_session, user)
    assert any("Sunday fruit" in c and "Test Rare" in c and "not Test Transport" in c
               for c in learned.corrections)


async def test_the_skill_file_is_the_static_half_plus_what_the_rows_say(client, db_session):
    from app.agent import categorise as C
    user = await _user(db_session)
    text = C.skill_file(await C.learn(db_session, user))
    assert text.startswith("# You categorise one person's payments")
    assert "# Learned from this ledger" in text
    assert "| CAT PAAN WALA | Cat-Paan | Test Treat |" in text
    assert "Test Transport: ₹120–₹150" in text
    assert "MOHAN LAL" not in text.split("# Learned from this ledger")[0], \
        "nothing about this user's rows lives in the static half"


async def test_the_tool_and_the_cards(client, db_session, model):
    from app.agent import cards
    from app.agent import tools as T
    user = await _user(db_session)
    row = await tx(client, DAYS[19], 12900, "Other", "COCO TEST MOTH",
                   counterparty_name="COCO TEST MOTH")
    model(json.dumps([{"id": row["id"], "category": "Test Rare", "confidence": 0.95,
                       "description": "cafe", "why": "first-time payee"}]))
    out = await T.run(db_session, user, "categorise_now", {"local_day": DAYS[19]})
    assert not out.get("error"), out
    assert out["written"] == [], "a first-time payee is capped below the write line"
    # `to_review` is every open question, not only this run's, so the card for
    # this row is found among them rather than assumed to be alone.
    card = next(c for c in cards.from_tool("categorise_now", {}, out) if c.row_id == row["id"])
    assert card.kind == "confirm" and card.state == "proposed"
    keys = {f.key: f for f in card.fields}
    assert keys["category"].guessed and keys["category"].value == "Test Rare"
    assert keys["description"].value == "cafe"
    assert "84% sure" in card.lede

    report = await T.run(db_session, user, "paisa_report",
                         {"to": DAYS[27], "fields": ["to_review"]})
    got = cards.from_tool("paisa_report", {"to": DAYS[27]}, report)
    assert any(c.kind == "confirm" and c.row_id == row["id"] for c in got)


async def test_the_tool_never_touches_kind(client, db_session, model):
    from app.agent import categorise as C
    user = await _user(db_session)
    row = await tx(client, DAYS[20], 400000, "Other", "Dost ko diye", confidence=0.7)
    model(json.dumps([{"id": row["id"], "category": "Test Rare", "confidence": 0.9,
                       "why": "round amount to a person; may be udhaar"}]))
    report = await C.categorise(db_session, user, D(20))
    mine = (await rows_by_id(client, row["id"]))[row["id"]]
    assert mine["kind"] == "expense", "kind is the user's to set"
    # A never-seen payee is capped below the write line, so this is proposed —
    # the row keeps Other and the user is asked, udhaar or not.
    assert mine["category"] == "Other" and report["proposed"][0]["guess"]["confidence"] == 0.84


async def test_the_batch_thinks_even_when_the_agent_does_not(client, monkeypatch):
    """Two callers, two settings, each measured where it runs: the agent's
    (medium since the 2026-10-10 chat eval) and the batch's (medium, a nightly
    call with no user waiting). Setting one must never move the other — so the
    agent is turned down here and the batch must not follow it."""
    from app.config import Settings

    cfg = Settings()
    assert cfg.llm_effort == "medium"
    assert cfg.categorise_effort == "medium"
    monkeypatch.setattr("app.llm.settings", lambda: Settings(llm_effort="none"))

    sent = {}

    async def spy(**kw):
        sent.update(kw)
        return SimpleNamespace(output=[], output_text="[]",
                               usage=SimpleNamespace(input_tokens=1, output_tokens=1))

    monkeypatch.setattr("app.llm.client", lambda: SimpleNamespace(
        responses=SimpleNamespace(create=spy)))
    from app import llm
    _, stamp = await llm.categorise("skill file", "[]")
    assert sent["reasoning"] == {"effort": "medium"}, "the batch must not follow the agent"
    assert sent["store"] is False, "the ledger is not kept on the provider's side"
    assert stamp.endswith("@medium"), "the prediction records what produced it"


async def test_agreeing_with_the_row_is_not_a_question(client, db_session, model):
    """The first live run asked five of nineteen about rows it agreed with —
    *EMI → EMI?*. Agreement corroborates: the confidence moves up, the category
    does not move, the dot stays, and nothing is asked. Only the user's own
    word makes a row certain."""
    from app.agent import categorise as C
    user = await _user(db_session)
    row = await tx(client, DAYS[22], 1000000, "Test Rare", "Test EMI payment", confidence=0.7)
    model(json.dumps([{"id": row["id"], "category": "Test Rare", "confidence": 0.84,
                       "why": "explicit description"}]))
    report = await C.categorise(db_session, user, D(22))
    assert report["proposed"] == [] and report["written"] == []
    [ok] = report["agreed"]
    assert ok["transaction_id"] == row["id"]

    after = (await rows_by_id(client, row["id"]))[row["id"]]
    assert after["category"] == "Test Rare", "agreement never moves the category"
    assert after["confidence"] == 0.84, "it moves how sure the ledger is"
    assert after["confidence"] < 1.0, "only the user's word makes it certain"

    review = (await client.get("/paisa/summary", params={
        "to": DAYS[27], "fields": "to_review"})).json()["to_review"]
    assert not [r for r in review if r["transaction_id"] == row["id"]]


async def test_the_review_answer_does_not_depend_on_what_ran_tonight(client, db_session, model):
    """Asked to look at doubtful payments, the agent ran the batch, read
    `examined: 0` — nothing new since last night — and said there were none,
    while fourteen questions sat open. The tool now answers the question it
    was asked: everything still waiting, whatever this run did."""
    from app.agent import cards
    from app.agent import tools as T
    user = await _user(db_session)
    row = await tx(client, DAYS[23], 77700, "Other", "Test open question", confidence=0.7)
    model(json.dumps([{"id": row["id"], "category": "Test Rare", "confidence": 0.6,
                       "why": "unsure"}]))
    first = await T.run(db_session, user, "categorise_now", {"local_day": DAYS[23]})
    assert len(first["proposed"]) == 1

    # A later run that finds nothing new must still surface the open question.
    again = await T.run(db_session, user, "categorise_now", {"local_day": DAYS[23]})
    assert again["examined"] == 0 and again["proposed"] == []
    assert row["id"] in [r["transaction_id"] for r in again["to_review"]], \
        "a question from an earlier run is still a question"
    card = next(c for c in cards.from_tool("categorise_now", {}, again) if c.row_id == row["id"])
    assert card.state == "proposed"
