"""
spec/done/projects.md — the Definition of done, row by row.

Projects through their routes, tasks through the agent's tools (called the way
the runner calls them), and placement through the work sync's upsert.
"""

import uuid

import pytest
from sqlalchemy import func, select

from tests.helpers import the_user, ulid

pytestmark = pytest.mark.asyncio(loop_scope="session")


def name(prefix="Test project") -> str:
    """Every test owns its projects, whatever ran before it."""
    return f"{prefix} {uuid.uuid4().hex[:6]}"


async def make(client, **over) -> dict:
    body = {"id": ulid(), "name": name()}
    body.update(over)
    r = await client.post("/projects", json=body)
    assert r.status_code in (200, 201), r.text
    return r.json()


async def default_of(client) -> dict:
    return next(p for p in (await client.get("/projects")).json() if p["is_default"])


async def tool(db_session, name_, **args) -> dict:
    from app.agent import tools as T
    user = await the_user(db_session)
    out = await T.run(db_session, user, name_, args)
    await db_session.commit()
    return out


# ─── 1 — the library shape ──────────────────────────────────────────────────

async def test_1_create_replay_and_patch(client):
    body = {"id": ulid(), "name": name("NovaCart-chan"), "description": "E-commerce chatbot",
            "icon": "🛒", "aliases": ["novachan", "Novachan", " novacart "]}
    first = await client.post("/projects", json=body)
    assert first.status_code == 201
    made = first.json()
    assert made["aliases"] == ["novachan", "novacart"], "trimmed, and case-folded once"
    assert made["color"].startswith("#") and made["key"]
    replay = await client.post("/projects", json={**body, "name": "ignored"})
    assert replay.status_code == 200 and replay.json()["name"] == made["name"]

    r = await client.patch(f"/projects/{made['id']}", json={
        "name": "NovaCart", "description": "The catalogue bot", "icon": "icon:cart",
        "aliases": ["amc"]})
    assert r.status_code == 200, r.text
    out = r.json()
    assert (out["name"], out["description"], out["icon"], out["aliases"]) == \
        ("NovaCart", "The catalogue bot", "icon:cart", ["amc"])


async def test_an_icon_is_an_emoji_or_one_of_the_set(client):
    assert (await client.post("/projects", json={"id": ulid(), "name": name(),
                                                 "icon": "icon:nonsense"})).status_code == 422
    assert (await client.post("/projects", json={"id": ulid(), "name": name(),
                                                 "icon": "abc"})).status_code == 422
    made = await make(client, icon="🚀")
    assert made["icon"] == "🚀"


# ─── 2 — the default ─────────────────────────────────────────────────────────

async def test_2_the_default_cannot_be_archived_or_deleted_but_can_be_renamed(client):
    home = await default_of(client)
    assert (await client.patch(f"/projects/{home['id']}",
                               json={"archived": True})).status_code == 409
    assert (await client.delete(f"/projects/{home['id']}")).status_code == 409
    assert (await client.patch(f"/projects/{home['id']}",
                               json={"is_default": False})).status_code == 409
    renamed = await client.patch(f"/projects/{home['id']}", json={"name": "Life"})
    assert renamed.status_code == 200 and renamed.json()["is_default"] is True
    await client.patch(f"/projects/{home['id']}", json={"name": "Personal"})


async def test_marking_another_default_moves_the_mark(client):
    home = await default_of(client)
    other = await make(client)
    r = await client.patch(f"/projects/{other['id']}", json={"is_default": True})
    assert r.status_code == 200 and r.json()["is_default"] is True
    rows = (await client.get("/projects")).json()
    assert [p["id"] for p in rows if p["is_default"]] == [other["id"]]
    await client.patch(f"/projects/{home['id']}", json={"is_default": True})


# ─── 3 — a delete never takes the tasks ──────────────────────────────────────

async def test_3_deleting_a_project_moves_its_tasks_home(client, db_session):
    from app.models.work import Task
    doomed = await make(client)
    t_open = (await client.post("/tasks", json={"id": ulid(), "title": "Open one",
                                                "source": "self",
                                                "project_id": doomed["id"]})).json()
    t_done = (await client.post("/tasks", json={"id": ulid(), "title": "Done one",
                                                "source": "self", "status": "done",
                                                "project_id": doomed["id"]})).json()
    assert (await client.delete(f"/projects/{doomed['id']}")).status_code == 204
    home = await default_of(client)
    db_session.expire_all()
    for t in (t_open, t_done):
        assert await db_session.scalar(select(Task.project_id).where(
            Task.id == t["id"])) == home["id"]
    assert doomed["id"] not in [p["id"] for p in (await client.get("/projects")).json()]


# ─── 4 — an alias belongs to one project ─────────────────────────────────────

async def test_4_an_alias_moves_to_the_project_that_claims_it(client):
    a = await make(client, aliases=["linear:Shared"])
    b = await client.patch(f"/projects/{(await make(client))['id']}",
                           json={"aliases": ["LINEAR:shared"]})
    assert b.json()["moved_aliases"] == [{"alias": "linear:Shared", "from": a["name"]}]
    rows = {p["id"]: p for p in (await client.get("/projects")).json()}
    assert rows[a["id"]]["aliases"] == []


# ─── 5 · 6 · 7 — the agent's tools ──────────────────────────────────────────

async def test_5_add_task_lands_in_the_named_project_and_an_unknown_one_writes_nothing(
        client, db_session):
    from app.models.work import Task
    proj = await make(client, name=name("NovaCart-chan"), aliases=["novachan-" + ulid()[-6:]])
    alias = proj["aliases"][0]
    out = await tool(db_session, "save_task", title="Replace the sheet with a DB",
                     project=alias)
    assert out["project_id"] == proj["id"] and out["guessed"] is False

    before = await db_session.scalar(select(func.count()).select_from(Task))
    miss = await tool(db_session, "save_task", title="x", project="No such project zz9")
    assert "error" in miss and miss["projects"]
    assert "manage_project" in miss["if_they_said_yes"], "the step after a yes is named"
    assert await db_session.scalar(select(func.count()).select_from(Task)) == before


async def test_6_no_project_named_lands_home_or_where_the_guess_put_it(client, db_session):
    home = await default_of(client)
    plain = await tool(db_session, "save_task", title="Buy a birthday gift")
    assert plain["project_id"] == home["id"] and plain["guessed"] is False

    proj = await make(client, description="The recipe app")
    guess = await tool(db_session, "save_task", title="Fix the recipe count",
                       project=proj["name"], guessed=True)
    assert guess["guessed"] is True
    deck = (await client.get("/deck?to=2026-09-27")).json()["work"]["tasks"]
    assert next(t for t in deck if t["id"] == guess["task_id"])["project_guessed"] is True
    # A guess of the default is no guess at all.
    homed = await tool(db_session, "save_task", title="Call home", project=home["name"],
                       guessed=True)
    assert homed["guessed"] is False


async def test_7_update_task_finds_by_title_ticks_and_moves_clearing_the_guess(
        client, db_session):
    from app.models.work import Task
    a, b = await make(client), await make(client)
    title = f"Ship the onboarding {uuid.uuid4().hex[:5]}"
    made = await tool(db_session, "save_task", title=title, project=a["name"], guessed=True)

    ticked = await tool(db_session, "save_task", task=title.split()[-1], done=True)
    assert ticked["status"] == "done" and ticked["task_id"] == made["task_id"]
    moved = await tool(db_session, "save_task", task=made["task_id"], project=b["name"])
    assert moved["moved_to"] == b["name"]
    db_session.expire_all()
    row = await db_session.scalar(select(Task).where(Task.id == made["task_id"]))
    assert row.project_id == b["id"] and row.project_guessed is False

    assert "error" in await tool(db_session, "save_task", task="zz-no-such-task-zz",
                                 done=True)


async def test_ticking_a_linear_task_in_chat_says_to_move_it(client, db_session):
    from app import work_sync as W
    user = await the_user(db_session)
    k = str(uuid.uuid4())
    title = f"Linear thing {k[:6]}"
    await W.tasks_upsert(db_session, user, [{
        "title": title, "source": "linear", "source_key": k, "source_ref": "ENG-5",
        "source_status": "open", "source_state": "In Progress"}])
    out = await tool(db_session, "save_task", task=title, done=True)
    assert out["move_in"] == {"source": "linear", "ref": "ENG-5", "stage": "In Progress"}


async def test_manage_project_makes_changes_and_deletes(client, db_session):
    n = name("Side project")
    made = await tool(db_session, "manage_project", name=n, description="Weekend build",
                      icon="icon:rocket", aliases=["sp"])
    assert made["created"] and made["icon"] == "icon:rocket"
    more = await tool(db_session, "manage_project", project=n, aliases=["weekend"])
    assert set(more["aliases"]) == {"sp", "weekend"}, "added to, not replaced"
    await tool(db_session, "save_task", title="Draft the README", project=n)
    gone = await tool(db_session, "manage_project", project=n, delete=True)
    assert gone["deleted"] and gone["tasks_moved_to_default"] == 1
    assert "error" in await tool(db_session, "manage_project", project=n)


async def test_the_prompt_lists_projects_for_placement(client, db_session):
    from app.agent import prompt as P
    proj = await make(client, description="Catalogue chatbot for a shop")
    await tool(db_session, "save_task", title="Wire the catalogue feed", project=proj["name"])
    text = await P.build(db_session, await the_user(db_session))
    section = text.split("## Their projects")[1].split("## Rules")[0]
    assert f"{proj['name']}: Catalogue chatbot for a shop" in section
    assert "Wire the catalogue feed" in section
    assert "(default" in section


# ─── 8 — work sync places by the same rule ───────────────────────────────────

async def test_8_source_project_resolves_by_alias_records_it_and_makes_one(
        client, db_session):
    from app import work_sync as W
    from app.models.work import Project, Task
    user = await the_user(db_session)
    mine = await make(client, name=name("kestrel"))
    src = f"linear:Kestrel-{uuid.uuid4().hex[:5]}"

    # The routine judged Linear's project to be theirs: the alias is recorded.
    [a] = await W.tasks_upsert(db_session, user, [{
        "title": "One", "source": "linear", "source_key": str(uuid.uuid4()),
        "source_status": "open", "project_id": mine["id"], "source_project": src}])
    rows = {p["id"]: p for p in (await client.get("/projects")).json()}
    assert src in rows[mine["id"]]["aliases"]

    # Next run: found by the alias alone, no judgement needed.
    [b] = await W.tasks_upsert(db_session, user, [{
        "title": "Two", "source": "linear", "source_key": str(uuid.uuid4()),
        "source_status": "open", "source_project": src}])
    db_session.expire_all()
    assert await db_session.scalar(select(Task.project_id).where(
        Task.id == b["id"])) == mine["id"]

    # A source project nobody has: made, carrying the alias.
    other = f"linear:Brand-new-{uuid.uuid4().hex[:5]}"
    [c] = await W.tasks_upsert(db_session, user, [{
        "title": "Three", "source": "linear", "source_key": str(uuid.uuid4()),
        "source_status": "open", "source_project": other,
        "new_project": {"key": other, "name": "Brand new"}}])
    pid = await db_session.scalar(select(Task.project_id).where(Task.id == c["id"]))
    made = await db_session.scalar(select(Project).where(Project.id == pid))
    assert made.name == "Brand new" and other in made.aliases

    # Nothing named, a guess sent: marked. Nothing at all: home, unmarked.
    [d] = await W.tasks_upsert(db_session, user, [{
        "title": "Four", "source": "wispr", "source_ref": "m-" + uuid.uuid4().hex,
        "project_id": mine["id"], "project_guessed": True}])
    [e] = await W.tasks_upsert(db_session, user, [{
        "title": "Five", "source": "wispr", "source_ref": "m-" + uuid.uuid4().hex}])
    db_session.expire_all()
    rd = await db_session.scalar(select(Task).where(Task.id == d["id"]))
    re_ = await db_session.scalar(select(Task).where(Task.id == e["id"]))
    home = await default_of(client)
    assert rd.project_guessed is True
    assert re_.project_id == home["id"] and re_.project_guessed is False


async def test_begin_hands_the_routine_what_placement_reads(client, db_session):
    from app import work_sync as W
    proj = await make(client, description="Weekend recipe app", aliases=["linear:Recipes"])
    begun = await W.begin(db_session, await the_user(db_session))
    p = next(x for x in begun["projects"] if x["id"] == proj["id"])
    assert p["description"] == "Weekend recipe app" and p["aliases"] == ["linear:Recipes"]
    assert "recent_tasks" in p and any(x["is_default"] for x in begun["projects"])


# ─── 9 — every task has a project ────────────────────────────────────────────

async def test_9_no_live_task_is_without_a_project_and_each_person_has_one_default(
        client, db_session):
    from sqlalchemy import text
    await client.post("/tasks", json={"id": ulid(), "title": "No project named",
                                      "source": "self"})
    orphans = await db_session.scalar(text(
        "SELECT count(*) FROM tasks WHERE deleted_at IS NULL AND project_id IS NULL"))
    assert orphans == 0
    bad = await db_session.scalar(text("""
        SELECT count(*) FROM (SELECT DISTINCT user_id FROM tasks) t
        WHERE (SELECT count(*) FROM projects p WHERE p.user_id = t.user_id
               AND p.is_default AND p.deleted_at IS NULL) <> 1"""))
    assert bad == 0


async def test_a_task_cannot_be_put_in_someone_elses_or_no_project(client):
    r = await client.post("/tasks", json={"id": ulid(), "title": "x", "source": "self",
                                          "project_id": "01NOSUCHPROJECT00000000000"})
    assert r.status_code == 404
    made = (await client.post("/tasks", json={"id": ulid(), "title": "y",
                                              "source": "self"})).json()
    home = await default_of(client)
    cleared = await client.patch(f"/tasks/{made['id']}", json={"project_id": None})
    assert cleared.status_code == 200 and cleared.json()["project_id"] == home["id"]


async def test_a_project_the_words_do_not_name_is_marked_a_guess(client, db_session):
    """The model placed a task well and forgot to say it guessed (seen live,
    2026-09-27). Whether the person named the project is read from their words,
    not trusted to a flag."""
    from app.agent import tools as T
    user = await the_user(db_session)
    proj = await make(client, name=name("Recipes"), aliases=["kitchen-app"])
    guessed = await T.run(db_session, user, "save_task",
                          {"title": "Show cooking time", "project": proj["name"]},
                          said="task add karo: cooking time bhi dikhana hai")
    named = await T.run(db_session, user, "save_task",
                        {"title": "Fix the photo upload", "project": proj["name"],
                         "guessed": True},
                        said="kitchen app me photo upload fix karna")
    await db_session.commit()
    assert guessed["guessed"] is True
    assert named["guessed"] is False, "an alias in their words is naming it"
    smuggled = await T.run(db_session, user, "save_task",
                           {"title": "x", "project": proj["name"], "_said": proj["name"]},
                           said="nothing named here")
    assert smuggled["guessed"] is True, "the model cannot supply the words itself"


async def test_a_task_is_found_the_way_it_is_said(client, db_session):
    """*"veg filter wala task"* names "Recipe list me veg filter lagana hai" —
    the filler is dropped and the words that carry it are matched."""
    tag = uuid.uuid4().hex[:5]
    made = await tool(db_session, "save_task", title=f"Recipe list me veg filter {tag} lagana hai")
    found = await tool(db_session, "save_task", task=f"veg filter {tag} wala task", done=True)
    assert found.get("task_id") == made["task_id"], found


async def test_the_same_task_said_twice_is_one_task(client, db_session):
    from app.models.work import Task
    proj = await make(client)
    title = f"Send the invoice {uuid.uuid4().hex[:5]}"
    first = await tool(db_session, "save_task", title=title, project=proj["name"])
    again = await tool(db_session, "save_task", title=f"  {title.upper()} ",
                       project=proj["name"])
    assert again["already"] is True and again["task_id"] == first["task_id"]
    n = await db_session.scalar(select(func.count()).select_from(Task).where(
        Task.project_id == proj["id"], Task.deleted_at.is_(None)))
    assert n == 1
    # Done, or in another project, it is a new task.
    await tool(db_session, "save_task", task=first["task_id"], done=True)
    fresh = await tool(db_session, "save_task", title=title, project=proj["name"])
    assert fresh.get("added") and fresh["task_id"] != first["task_id"]


async def test_a_project_word_narrows_the_search_and_the_best_overlap_wins(client, db_session):
    """*"Kestrel wala 3 recipes dikhane ka task"* names "By default we should show
    3 recipes…" in Kestrel: the project's name narrows, and two shared words win
    over a Hindi one the English title cannot contain."""
    tag = uuid.uuid4().hex[:4]
    proj = await make(client, name=f"Kestrel{tag}")
    target = await tool(db_session, "save_task", project=proj["name"],
                        title=f"By default we should show 3 recipes {tag}, now 6")
    await tool(db_session, "save_task", project=proj["name"],
               title=f"Suggest recipes from photos {tag}")
    found = await tool(db_session, "save_task",
                       task=f"{proj['name']} wala 3 recipes {tag} dikhane ka task", done=True)
    assert found.get("task_id") == target["task_id"], found


# ─── reading tasks ───────────────────────────────────────────────────────────

async def test_work_report_answers_what_is_due_late_open_and_done(client, db_session):
    """The agent could not read a task, and "aaj kya due hai?" reached for
    paisa_report (2026-09-27). Dates are pinned — a Wednesday — so nothing here
    moves with the clock."""
    from datetime import UTC, datetime

    from app.models.work import Task
    proj = await make(client)
    day = "2026-10-14"

    async def add(title, due=None):
        return (await tool(db_session, "save_task", title=title, project=proj["name"],
                           due=due))["task_id"]

    late = await add("Late one", "2026-10-12")
    now_ = await add("Due today", day)
    soon = await add("Due tomorrow", "2026-10-15")
    await add("Someday")
    done = await add("Finished Monday", "2026-10-20")
    await tool(db_session, "save_task", task=done, done=True)
    row = await db_session.scalar(select(Task).where(Task.id == done))
    row.done_at = datetime(2026, 10, 12, 6, 0, tzinfo=UTC)          # Monday, 11:30 IST
    await db_session.commit()

    async def report(**kw):
        return await tool(db_session, "work_report", today=day, project=proj["name"], **kw)

    ids = lambda r: {t["task_id"] for t in r["tasks"]}  # noqa: E731
    assert ids(await report(due="today")) == {now_}
    assert ids(await report(due="tomorrow")) == {soon}
    assert ids(await report(due="overdue")) == {late}
    assert (await report(due="undated"))["count"] == 1
    assert ids(await report(status="done", due="this_week")) == {done}, \
        "a finished task is in the week it was finished, not the week it was due"
    assert (await report())["count"] == 4, "open, any date"
    [counts] = (await report())["projects"]
    assert counts == {"project": proj["name"], "is_default": False, "open": 4,
                      "overdue": 1, "due_today": 1, "done_this_week": 1}

    assert "error" in await tool(db_session, "work_report", project="No such zz project")


async def test_every_turn_carries_where_work_stands(client, db_session):
    """Without a [work] line the model's day was money and food, and a task
    question went to paisa_report. Counts only — which tasks is work_report's."""
    from datetime import date

    from app.agent import prompt as P
    text = await P.now_block(db_session, await the_user(db_session), date(2026, 10, 14))
    line = next(x for x in text.splitlines() if x.startswith("[work]"))
    assert "open tasks" in line and "due today" in line and "late" in line
    assert "work_report" in line
    assert '"kal" is yesterday for something that\nhappened, and tomorrow' in text



async def test_a_number_is_a_whole_word_not_a_digit_inside_one(client, db_session):
    """Found by running the suite twenty times: "3 recipes" tied with a title
    whose tag held a 3. A number must match a number, never a digit in a word."""
    proj = await make(client)
    target = await tool(db_session, "save_task", project=proj["name"],
                        title="Show 3 recipes on the home screen")
    await tool(db_session, "save_task", project=proj["name"],
               title="Suggest recipes for ACM-123 on 2026-09-30")
    found = await tool(db_session, "save_task", task=f"{proj['name']} wala 3 recipes dikhane",
                       done=True)
    assert found.get("task_id") == target["task_id"], found


# ─── colour: the Work hue's family ───────────────────────────────────────────

async def test_a_new_project_takes_a_colour_from_the_work_hue_never_amber(client):
    """The palette was the pre-Jamun greens and ambers; amber is the estimate
    dot's alone (THEME.md § Colour). TODO.md § Project colours."""
    from app import projects as P
    made = (await client.post("/projects", json={"id": ulid(), "name": name("Hue")})).json()
    assert made["color"] in P.PALETTE, made["color"]
    assert not set(P.PALETTE) & set(P.OLD_PALETTE)


def test_every_project_colour_is_blue_and_readable_as_a_mark():
    """Work's family: blue the largest channel, and 3 : 1 on white for a bar."""
    from app import projects as P

    def lum(h):
        v = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        v = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in v]
        return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]

    for c in P.PALETTE:
        r, g, b = (int(c[i:i + 2], 16) for i in (1, 3, 5))
        assert b > r and b > g, c
        assert 1.05 / (lum(c) + 0.05) >= 3.0, c
