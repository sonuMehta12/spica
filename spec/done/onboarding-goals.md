# Onboarding — goals first

> Status: **shipped 2026-10-11** — built on the web, the server and the phone;
> `backend/tests/test_onboarding_goals.py` and the onboarding block of
> `n2n_eval`. Design: the "Spica onboarding" canvas in the artifact gallery
> (four screens, clickable). The film's frozen copy is
> `spec/reference/onboarding-film.dc.html`.
> Surface: frontend · android · backend — a dedicated onboarding agent on the
> app's own tools, two nullable columns on `users` and a turn counter, one flag
> on `weigh_ins`,
> changes to the main agent's prompt and two tools, and Home's meal plan
> reading the new facts.
> Supersedes `spec/done/onboarding.md`: its door replay, first-minute
> greeting and Getting started card. Its one stored column,
> `users.onboarding_done_at`, carries over with a new meaning.
> Related: `spec/in-progress/sign-in.md` (the door is sign-in),
> `spec/in-progress/today-plan.md` (Home's meal plan), `spec/in-progress/memory.md`,
> `spec/done/habits.md`, `THEME.md`.

## The problem

The shipped onboarding sells a logger. The door's replay shows a spend, a
meal and a task being recorded; the greeting says *"I keep your money, food
and work in one place"*; the checklist asks you to log things and set
calorie targets. A stranger leaves the first minute thinking Spica is a
tracker with a chat box — the general chatbot it is not. And it starts cold:
the first meal idea and the first answer about weight or savings know nothing
about the person, because nothing about them was asked.

## What it does

Four screens, from sign-in to Home. About a minute.

### 1 · The door — the film

The wordmark `spica` at the top, a film made only of dots, the headline
*"Less managing life. More achieving it."* (serif), then *Continue with
Google* and *Your data stays yours*. No subheading, no controls, no progress
bar, no labels on the film. It plays while the person signs in, and loops.
Google's own button stays on the web: the ID token only comes from it.

The film tells one story in four acts, on a 500 ms beat, 44 beats a loop
(22 s):

| Act | Beats | What the dots do | Line |
|---|---|---|---|
| Mess | 0–9 | 28 dots in mode colours, scattered, shaking, sliding down and fading as they fall — a life slipping | *Money slipping. Time slipping. Health slipping.* (from beat 2) |
| Order | 10–14 | Spica's mark appears at the top; the dots fly up into a calm month, 7 × 4, one colour per row | *Spica puts it in order.* (from beat 11) |
| Outcome | 15–34 | Four scenes of five beats. Weekday letters over the month; the month recolours to the scene's mode with some days grey (missed); from each scene's second beat a figure and a serif line fade in under it | see the scenes below |
| Close | 35–43 | Every dot flies into the Constellation mark (nine dots, the rest fade); the small mark fades | *Time for what matters.* (from beat 36) |

| Scene | Month colour | Figure (its ink) | Line | Grey days |
|---|---|---|---|---|
| Money | `paisa` | ₹15,000 (`paisaInk`) | *saved this month.* | 4, 13, 22 |
| Health | `diet` | −2 kg (`dietInk`) | *this month, and counting.* | 5, 6, 17, 26 |
| Time | `work` | 6 hours (`workInk`) | *a week, back for you.* | 9, 23 |
| Habit | `dietInk` | 4 weeks (`dietInk`) | *at the gym. Started, and stuck.* | — |

**The door is marketing, and its figures say so by how they are told.** They
are one person's month — the dots are days, the figures what those days added
up to — never framed as what users get. *6 hours a week* is the promise of
the *Your time* pick, not something Spica measures; it stays, by the owner's
decision, because the film sells the outcome and that is the outcome people
want from it.

**Colours, as tokens.** The mess cycles `i % 8` through `paisa`, `diet`,
`work`, `dietInk`, `grey`, `dietSoft`, `paisaSoft`, `workSoft`. The order rows
are `paisa`, `dietInk`, `diet`, `work`. A grey day is `ringIdle`; the mark is
`brand`. Amber and red never appear.

**It moves exactly like the approved prototype.** Positions, sizes, the
jitter, the easing (`cubic-bezier(.2,.75,.2,1)` over 1000 ms for position;
700 ms for size and colour; 600 ms for opacity) and every timing above are
the contract; the formulas and the jitter keyframe are in
`spec/reference/onboarding-film.dc.html`. Nothing in it is random — the
scatter is arithmetic on the dot's index, the jitter a keyframe with a
per-dot delay — so it is ported as-is.

**One clock, one pure function, on both surfaces.** `frame(ms)` returns every
dot's x, y, size, colour and opacity, the mark, the weekday row, the figure
block and the captions. It is built from a per-beat target table and applies
the prototype's transition rules explicitly — a transition starts from the
current value whenever its target changes. The web samples it with
`requestAnimationFrame` and draws one SVG (viewBox `0 0 390 560`); the phone
samples it with `withFrameNanos` and draws one Compose `Canvas` over the same
390 × 560 units, reading the clock only inside the draw. The table is written
twice with identical names and order — `frontend/src/door/filmDots.ts` and
`android/…/logic/FilmDots.kt` — the way `theme.ts` and `Tokens.kt` are kept,
colours as token names. A debug-only override freezes the film at a given
millisecond on both surfaces, for checking.

The clock is film time, not wall time: each frame step is capped at 100 ms,
so a hidden tab or a backgrounded app resumes where it was. The first loop
starts still at beat 0, as the prototype does. No sound.

**Size.** The film scales uniformly to the space left after the wordmark,
headline, button and footnote, centred, never cropped and never larger than
one unit to one px or dp. The door never scrolls.

**For a screen reader** the film is one image, described once — *"A short
film in dots: a life slipping out of hand is put in order, and becomes
results."* (`aria-label` on the web, `contentDescription` on the phone). The
captions are not read out as they change.

**Reduced motion** holds seven frames, each for its own length on the same
clock, cut hard, no jitter: the mess settled (beat 9), the order (14), each
outcome scene's last beat (19, 24, 29, 34) and the close (43). The web
follows `prefers-reduced-motion` live; the phone treats
`ANIMATOR_DURATION_SCALE = 0` (*Remove animations*) as reduced, re-read on
resume.

### 2 · Take control

The Spica logo top left — the mark at 24 px (its full nine-dot build) and the
wordmark — and *Skip* top right. Serif: *"Hi, I'm Spica."* and one line,
*"What do you want to take control of? I'll help you get there."* Five
options, multi-select, none picked to start, each said as what you get:

| Pick | Its line | Domain | Home widgets it switches on |
|---|---|---|---|
| Your money | Know where it goes. Keep more of it. | money | Money |
| Eating healthy | Better meals, no counting. | health | Diet, Meals |
| Your health | Weight, sleep, workouts — moving right. | health | Activity, Workout |
| Your habits | Build the good ones. Cut the rest. | health | Habits |
| Your time | Work on track, and your evenings back. | work | — (Today is always first) |

Five picks, three domains — not a fourth mode. *Continue* goes to screen 3;
with nothing picked it reads *Skip for now* and goes to Home. *Skip* top right
leaves the whole flow for Home.

**Home's widgets.** With at least one pick, the phone's widget list becomes
exactly the widgets the picks switch on, in the widgets' fixed order, with
Today first. With nothing picked, or after *Skip*, it stays the default
(Money, Diet). The list stays a layout kept on the phone, as it is today.

### 3 · A little about you

The app's own chat parts — the agent's serif, the person's tint pill, the
input bar (placeholder *Say it, or type it…*; *Listening…* while listening)
— on its own screen, logo top left, *Skip* top right. **The onboarding agent**
(below) takes each answer, writes what it hears through the app's own tools,
and shows each write as a card the person can confirm or change.

The questions are fixed copy, asked one at a time. Questions a and b are
always asked; c, d and e follow the picks — and because the person already
picked the goal, they ask for its details directly:

| # | Asked when | Spica says | Chips | What the agent writes |
|---|---|---|---|---|
| a | always | *Let's start with a little about you. Would you share your name, gender, age, height and weight?* · *It helps me work out your BMI, so every suggestion fits you. Just say it — or type it.* | — | name, gender, date of birth, height, a weigh-in |
| b | always | *Where do you live, and what do you eat? Then the meals I suggest are ones you can get, and actually want.* | Veg · Non-veg · Eggetarian · Anything | city, diet, foods never eaten |
| c | Your health | *What's your health goal? Give me a number if there is one — like lose 5 kg.* | Lose weight · Gain muscle · Eat cleaner | a weight target, or the goal in their words |
| d | Your money | *How much do you want to save every month? I'll keep your daily spending to what's left after it.* | — | savings target |
| e | Your habits | *Which habits do you want to track?* | Gym · Running · Sleep early · Fewer cigarettes | habits, each build or break |

Questions a, b and d say why they ask, because what they store changes what
Spica does; c and e ask for the goal itself.

**After each answer**, the agent's writes appear as cards — the app's own
confirm cards, one per write — each with *Edit* and *Undo*. A card's heading
takes a coin in the mode's tint (profile and health facts the diet tint, money
the paisa tint, work the work tint), never a coloured dot: a diet-orange dot
beside the amber estimate dot would read as two estimates. Only the weight can
carry the amber dot (below).

- **A chip adds its word to the input bar**, after anything already there,
  comma-separated; it does not send. Question b asks two things, and question
  e wants several habits at once.
- **While the agent works**, the mark beside the thread shows its thinking
  state and the input bar waits. If the call fails — a timeout, the network,
  the server — Spica says *"I couldn't take that in — try again?"*, nothing is
  written, and the answer stays in the bar to send again.
- **A follow-up, when it matters.** If an answer leaves out something the
  question asked for and the person seems to want to give it, the agent may
  ask once, in one line (*"And your height?"*). It never asks twice, and never
  asks about a field the person skipped on purpose.
- **A question is skipped by saying so** — *skip*, *nahi batana*, or an answer
  about something else — and nothing is written. *Skip* top right skips the
  rest and goes to screen 4.
- **An answer the agent can't read** writes nothing and it asks once more:
  *"Say that again?"* A second unreadable answer to the same question moves on
  as a skip. Never a zero, never a placeholder.
- **Edit** puts that card on the input bar as context, the way *Change* works
  in the chat; the agent corrects that row. **Undo** removes the write, the
  way it does in the chat.
- **Speech fills the input bar and is never sent on its own** — speech gets
  numbers wrong, and *"five nine"* or *"72 kilo"* matter. The phone uses its
  recogniser (`RecognizerIntent`, English (India), as Home does); the web uses
  the Web Speech API where the browser has it and shows no mic where it
  doesn't. The web's demo mic (`tapMic`), which logs a scripted payment or
  meal, is never wired here.
- When the last question is done: *"That's everything I need. Here's your
  start."* and *Continue*. If nothing at all was given: *"You can tell me any
  of this later."* and *Continue*.

**Coming back.** Answers are written as they come, but the flag is set only
at the end. A reload, a dead process or another device mid-flow brings back
screen 2 with nothing picked; screen 3 then skips any question whose facts are
already set. Back from screen 3 to screen 2 keeps the picks and the thread; a
new pick appends its question. Back first clears an Edit context, then
cancels a waiting answer, then changes screen.

### 4 · You're all set

Logo top left. Serif: *"You're all set, {name}."* (*"You're all set."* with no
name) and *"Here's where you're starting, and where you're headed."* Screen 4
reads live rows on entry — the profile, the latest weigh-in, the memories the
agent wrote, the habits — never the cards' copies.

- **About you** — tags: gender, *28 years*, *175 cm*, the weight, the BMI, the
  city, the diet with its exceptions. The weight and the BMI carry the dot
  when the weight was approximate. A field not given is not shown.
- **Your goals** — one row per goal, each with its mode's coin: *Lose 5 kg —
  72 kg → 67 kg*, *Save ₹15,000 — every month*, *Gym — a habit to build*,
  *Cigarettes — a habit to break*, or a goal in their words (*Eat cleaner*).
  While the latest weigh-in is approximate, its *72 kg* and the *Lose 5 kg*
  worked out from it carry the dot; the stored target (67 kg) does not.
- **A card with nothing in it is not drawn.** With both empty, the second line
  reads *"You can tell me any of this later."*
- **Edit** on a card returns to screen 3 with its thread, where the person
  taps *Edit* on the write to change; *Continue* comes back here.

**The BMI is a bare number** — no category word, no colour, no range. Any
category would be contested (23.4 is *normal* by WHO's cut-offs and
*overweight* by the Asian ones), and adult BMI is wrong for a child: it is
not shown when the date of birth makes the person under 18.

No calories, no protein, no daily targets: Spica is goal-first, and a daily
target is the app's number, not the person's goal. *Get started* sends
`PATCH /users/me {onboarding_done_at}` and reloads the deck — so the habits
and targets just set are on Home — then opens Home. If the PATCH fails, Home
still opens and the flag is sent again on the next start.

## Where the canvas is corrected

The canvas was approved as drawn; these changes keep its intent and fix what
would be false or against `THEME.md` once built:

- **Film, colours.** The mess's red becomes `dietSoft`: red means *over*,
  everywhere. The order rows and the outcome colours are unchanged.
- **Film, the figure text swap.** At each outcome cut the prototype switched
  to the next figure while the old one was still fading; the text now changes
  when the fade ends. The timing does not move.
- **Film, reduced motion.** The canvas note said *each act's last frame* —
  four frames, which would show only the gym scene of the four outcomes. It
  holds seven, one per outcome scene.
- **The logo's mark** is drawn at 24 px, the smallest size at which `Mascot`
  draws all nine dots, as the canvas shows.
- **Questions c and d** ask for the goal's details directly — the person
  already picked the goal on screen 2, so *"Are you planning to save?"* became
  *"How much do you want to save every month?"*.
- **Answer cards** are the app's confirm cards, one per write, with a coin,
  not a coloured dot.
- **Goal rows.** *"Gym, every day"* becomes *"Gym — a habit to build"*:
  `habits.md` decided against per-habit targets, so *every day* is not stored
  and is not shown. *"Fewer cigarettes — a habit to cut"* becomes
  *"Cigarettes — a habit to break"*, the habits feature's own word.
- **The BMI** reads 23.4, not 23.5: it is worked out from the height as
  stored (5′ 9″ is 175.3 cm).
- **On the web**, the screens wear the web's surfaces — a white page, hairline
  borders, no shadow — per `THEME.md`; the phone wears `Page.kt`'s.

## The onboarding agent

A dedicated agent for screen 3 — not the chat agent, and not in the person's
thread. It runs on the same runner and the **same tools the app already
has**, so what it writes is exactly what the app would write from a sentence
in the chat, and every write comes back as the same confirm card.

**Its tools** — a short list, so it cannot wander:

| Tool | For |
|---|---|
| `update_profile` | name, gender, age (the server turns it into a date of birth), height, city, diet, the weight target, the savings target |
| `log_day` | the weight, as a weigh-in, with *approximate* when said that way |
| `remember` | anything unstructured worth keeping — foods never eaten, a goal without a number, a fact about the person |
| `manage_habit` | habits to build or break |
| `save_task` | a piece of work the person names along the way |
| `next_question` | **new**, onboarding only: *answered* or *skipped* — tells the screen to move on |

**Its prompt** is its own skill file, `backend/app/agent/skills/onboarding.md`,
and carries: the question just asked, what is already known — read live
from the profile, the latest weigh-in, the memories and the habits, so a
re-entry never asks again — and the rules — write every fact the answer
gives, through the tool that owns it; treat these answers as the person
asking Spica to keep them (the chat's *remember only when asked* is met by the
question itself); one follow-up at most; never invent a value; call
`next_question` when the question is answered or skipped.

**A turn:** `POST /onboarding/turn`

```
request  {question: "about" | "place" | "health" | "money" | "habits", text, local_day}
response {cards: [the confirm cards for this turn's writes],
          reply,                       // a follow-up or "Say that again?", else null
          next: bool}                  // true once next_question was called
```

- A resent answer is safe without a replay store: every tool the agent writes
  through is already safe to repeat — profile fields and a day's weigh-in
  overwrite, habits and memories reuse by name or slug, and `save_task` refuses
  a duplicate. The screen never resends on its own.
- One answer is **one transaction**: the tool calls of a turn commit together,
  so a failed write leaves nothing behind (the savepoint per tool, as the
  runner already does, plus one commit at the end of the turn). One person's
  turns run one at a time, behind an advisory lock: the transaction is open
  across model calls, and two at once — an answer resent after the client gave
  up on the first — could take the same rows in opposite orders and deadlock.
- The endpoint answers `409` once `onboarding_done_at` is set, and `429` past
  40 turns a day for one account — the model is billed per call, and the
  chat's daily turn limit does not see this endpoint. Screen 3 shows a `429`
  as one agent line and moves on. The turns are written nowhere else, so the
  count is two columns on `users` — today's turns and the person's local day
  they are for — counted before the model is called and kept when the turn
  fails, because the call is billed either way. No table.
- A failed model call — a timeout, the provider down or refusing the prompt —
  answers `502` and writes nothing; the screen says *"I couldn't take that in
  — try again?"*.
- The server keeps no history of the turns, so the screen holds what spans
  them: a second *"Say that again?"* on one question moves on as a skip. The
  agent knows a follow-up's answer by `[already known]` already holding part
  of the question.
- The turns are not written to the chat thread. The facts live in rows, and
  the chat agent reads rows. The thread stays a conversation the person starts.

**Why a dedicated agent, not the chat agent:** the chat agent carries 27 tool
schemas and the day's rules, would paraphrase the fixed questions, cannot
draw the chips, and would put the first run in the person's thread. **Why an
agent, not a one-shot extraction:** an agent acting through the app's own
tools writes exactly what the app writes, can ask the one follow-up a form
can't, and handles *"Sonu, male, 28, five nine, around 72"* or *"paanch nau,
72 ke aas paas"* the way the chat already does — *agent hi app hai*.

## Data

**No new table. The answers go where the app already keeps them**: `users`,
`weigh_ins`, `habits`, `tasks`, and memories for anything unstructured.
`users` gains the two columns it is missing; `weigh_ins` gains one flag.

| Answer | Stored in | Change |
|---|---|---|
| name | `users.display_name` | — (Google's `given_name` fills it at sign-in; the answer corrects it) |
| gender | `users.gender` | **new**, text, nullable, check in (`female`, `male`, `other`) |
| age | `users.dob` | — : an age becomes 1 January of the birth year |
| height | `users.height_cm` | — |
| weight | `weigh_ins` row | **new** `weigh_ins.estimated` boolean, not null, default false |
| city | `users.city` | — |
| diet | `users.diet` | **new**, text, nullable, check in (`veg`, `nonveg`, `eggetarian`, `any`) |
| foods never eaten | memory (`remember`), kind `preference` | — |
| lose / gain *N* kg | `users.weight_target_kg` | — |
| eat cleaner, gain muscle (no number) | memory (`remember`), kind `project` | — |
| save ₹*X* a month | `users.savings_target_paise` | — |
| habits | `habits` rows, direction build or break | — |
| work named along the way | `tasks` row | — |
| finished | `users.onboarding_done_at` | — (new meaning, below) |

**Structured facts are columns; everything else is a memory.** Gender and
diet are categories the app computes with — diet limits what Home's meal plan
suggests, gender sizes it — so they are columns on `users`, the table that
already holds the person. *"No beef"*, *"eat cleaner"*, *"I work nights"* are
sentences in the person's words: the memory store already exists for exactly
these (Profile → Memory), and the agent writes them with `remember`. Memories
written here have source `user`, so they show as confirmed: the person said
them and the card showed them back. A diet outside the four — vegan, Jain — is
the nearest of them and a `preference` memory for what it adds (*Vegan — never
eats dairy*): the meal plan reads both, and `veg` alone would plan paneer.

**Age is stored as a date of birth: 1 January of the birth year.** *"28"* said
in 2026 is `1998-01-01`. Only the year means anything, so wherever a date of
birth is shown it is shown as an age (*28 years*), never as the date; a person
who wants the exact day sets it on Profile. No column is added for it.

**The weight is a weigh-in.** Everything that reads weight — the Profile page,
`diet_report`, screen 4 — reads `weigh_ins`. The agent's `log_day` writes
weight only to `days` today, so a weight said in chat reaches none of them; it
now writes a weigh-in too, as `spec/agent-tools.md` already says it should,
and keeps the `days` copy. `log_day` gains an `approximate` flag for the
weight, so *"aaj around 71"* in chat keeps the dot as well. The weight's
confirm card is its own, holding the weigh-in's id — the sleep and habit
ticks stay on the day's card — so *Undo* is `DELETE /weigh-ins/{id}` and a
weigh-in deleted on Profile reaches the card. Deleting a weigh-in clears that
day's `days` copy: the copy goes with the reading.

**Only the weight can be approximate.** It is the one answer people routinely
give as a guess, and the dot was approved on it. `weigh_ins.estimated` is the
one change outside `users`, because a weigh-in is its own row: `POST
/weigh-ins` sets it from the body on insert and on the same-day replace, so a
later exact reading clears it; `GET /weigh-ins` and `diet_report`'s weight
block return it. The BMI is not stored: it is worked out from the latest
weigh-in and the height wherever it is shown, and carries the dot when the
weight does. Every other fact is stored as said and never dotted.

**Goals are stored as units, shown as sentences.** *"Lose 5 kilo"* stores
`weight_target_kg` = the current weigh-in − 5 (67.0). *"Lose 5 kg — 72 kg →
67 kg"* is worked out at render from the latest weigh-in and the target, so it
stays true as the weight moves. With no weight given, the goal is remembered
in their words and no target is invented.

**A savings target set here shapes Home from the first day.** Once income is
recorded, *Left to spend today* takes the target out — which is why question d
says so.

**Habits keep no frequency.** *"Gym every day"* creates a build habit named
*Gym*; *every day* is not stored, because `habits.md` decided against
per-habit targets and nothing reads one. A habit name already tracked is
reused, never refused, and left as it is: its card reads *Gym · already
tracked*, and a direction said beside the name does not flip it — changing a
habit is `manage_habit` with `habit_id`.

**The picks are not stored on the server.** They decide the questions and the
phone's widget list — a layout. Nothing on the server reads them.

### What reads the answers

These reads ship with this change — they are what make question a's *"every
suggestion fits you"* and question b's *"meals … you can get, and actually
want"* true on the day it ships.

- **Home's meal plan** (`plan.py`) gets the diet, the person's memories, the
  city, the height, the latest weight, the date of birth and the gender in its
  payload, and `skills/plan.md` gains one hard rule: never plan a food the
  person does not eat — veg and eggetarian are limits, and so are the foods
  they said they never eat. The day's plan is made again when that payload
  changes — not when a sign-in or a flag touches `users`, each of which would
  be one more billed call.
- **The chat agent's prompt** (`prompt.build`): *Who they are* gains gender,
  *born 1998* (the year from the date of birth, not an age, so `build()` stays
  free of today's date, as `prompt-layout.md` requires — the model works the
  age out from the `[now]` line), height, the latest weight (with
  *approximately* when it is estimated), city and diet. *Their targets* gains
  the weight target. The identity line becomes: *"You are Spica — {name}'s
  personal agent for taking control of their money, health, habits and time,
  toward the goals they set. You log what they say and answer from their own
  data. You are not a chatbot with opinions."* — *"their ledger with a voice"*
  goes: a ledger is the logger this replaces.
- **`update_profile`** gains `gender`, `age`, `dob`, `height_cm`, `city` and `diet` — `age` is written as 1 January of the birth year, by the server, so the model never does date arithmetic —
  so the onboarding agent can write them and *"actually I'm 29"* in the chat
  corrects the row instead of being lost. It refuses an age outside 13–100, a
  `dob` that makes one, and a height outside 50–250 cm (*"five nine"* misread
  as 5.9). Its age card is keyed `age`, never `dob`, so no build draws the
  invented 1 January as a birthday.

These are prompt and tool changes: `n2n_eval` runs before they land, and the
day stays at its last score — 96.3% of cases and 98.7% of turns, with no case
that passed failing in two of three runs.

### Profile

On both surfaces, Profile's *About* group gains **Gender** and **Diet** rows,
and shows the date of birth as an **Age**. Every field on Profile except the
name can be cleared — an empty save sends `null`, which `PATCH /users/me`
already accepts; the name can be changed, not removed. The latest weigh-in
shows the amber dot when estimated, and a weigh-in can be deleted through the
existing route.

### Which flag, and who sees the flow

`users.onboarding_done_at` now means *finished or skipped the first run*. It
is set by *Get started*, by *Skip* on screen 2 and by *Skip for now*; once set
it stays set — `PATCH /users/me` ignores a null for it (200, the value kept).
The apps show screens 2–4 after sign-in while it is null.

On ship, a migration sets it for every existing account with any row,
soft-deleted or not, in `transactions`, `meal_logs`, `tasks`, `habits`,
`commitments`, `weigh_ins`, `memories` or `messages`, through a `backfill`
function tested the way `commitments` tested its own. Those people are past
their first run; the owner's dev data is never pushed through it.

The backfill runs once, at migration, so the migration, `/deck`'s change and
the apps' gates ship in one release. If the server goes first, a follow-up
migration calls `backfill` again when the apps ship — it only fills nulls, so
it is safe to repeat — or every account made in between, rows and all, meets
the first run.

The Getting started card, the first-minute greeting and its three chips, and
`/deck`'s Getting started steps are removed. `/deck` keeps `onboarding.done_at`,
which is what the apps read to decide. `onboarding.steps` stays on the wire as
an always-empty list: the web build before this change reads its length
unguarded, and a missing key would break its boot. It goes once no such build
is in use. `backend/tests/test_onboarding.py`'s step tests go with the steps;
its stays-set test moves to `test_onboarding_goals.py`.

### Where it lives

- **Web:** a new `Gate` state between loading the deck and `App`, drawn
  full-screen in the app column. The door is `Door.tsx` with the film in place
  of the replay.
- **Phone:** a fourth branch in `MainActivity.Gate` — no token → the door;
  booted and `onboarding_done_at` null → onboarding; else Home — so Home's
  pager is never composed underneath it. Built from `Page.kt`.
- **Back:** on screen 3 returns to screen 2; on screen 4, to screen 3; on
  screen 2 it leaves the app, as on the door.
- **Opening `/connect` before the first run** skips the flow; it shows on the
  next visit to the app.

## Rules and edge cases

- **Every reason given is true at ship.** The BMI is on screen 4; Home's meal
  plan and the chat agent read the body and food answers from this change on;
  a savings target shapes *Left to spend today*.
- **Unknown is not zero.** A skipped field is absent — never `0 kg`, never a
  default gender, never *Anything* for an unanswered diet.
- **The dot follows the weight.** An approximate weight is dotted on its card,
  on screen 4 (and in the BMI and the goal row worked out from it), on Profile
  and in the chat agent's prompt, until an exact weigh-in replaces it.
- **Height is stored at the column's precision.** 5′ 9″ is 175.3 cm, shown as
  *175 cm*; the BMI is worked out from the stored value (72 kg → 23.4).
- **A new account that started on another device** sees the flow once and
  never again: the flag is on the server.
- **What each field is for, and where it goes**, so the privacy policy and
  Play's Data safety form can say it plainly. Name: what Spica calls you.
  Gender, age, height, weight: the BMI, and sizing the meal plan and the
  agent's answers to your body. City, diet: meal ideas you can get and want.
  Goals: what Spica checks your progress against. Every answer is sent to the
  language-model provider to be read, and the profile facts go with every
  later chat turn and meal plan. Spoken answers go to the platform's speech
  recogniser (Google, on Android and in Chrome). Every field except the name
  can be cleared from Profile; there is no export.
- **"Your data stays yours"** means no export, no sale, and delete any item or
  the whole account. It must not suggest the data stays on the phone.

## Changes to decisions already made

- `spec/done/onboarding.md`:
  - *Nothing is asked* in the first minute is reversed: a few questions are
    asked, each skippable, because a cold start makes the first suggestion
    generic and a goal-first product needs the person's goals.
  - *Asking for targets up front* is reversed for the savings and weight
    targets: both are goals the person states, not numbers guessed before
    there are spends, and every question can be skipped. It still holds for
    calorie and protein targets, which are not asked.
  - *Nothing blocks* is reversed: screens 2–4 stand in front of Home until
    finished or skipped, because the questions need the person's attention
    once; *Skip* is one tap on every screen.
  - The Getting started card and its derived steps are removed; the replay
    becomes the film.
- `spec/done/users-profile.md` — `dob` may hold 1 January of a birth year
  worked out from an age, shown as an age; `users` gains `gender` and `diet`;
  Profile gains them, and every field but the name becomes clearable.
- `THEME.md` (*"Estimated gets the amber dot before the value"*), `CLAUDE.md`
  (*"Inferred values are marked — an amber dot before the value"*) and
  `spec/launch.md` (*"A value the agent worked out carries an amber dot until
  the person confirms it"*) — the dot also marks a weight the person said as
  approximate. That one leaves when an exact weight replaces it, not when it
  is confirmed: confirming *around 72* does not make it exact.
- Rent and EMIs are not asked on day one — deferred, `spec/notes.md` § *Rent and EMIs during onboarding*.
- The landing's honest-copy rule (*every number measured or removed*) does
  not bind the door's film: it is marketing, told as one person's month, by
  the owner's decision.
- `spec/notes.md` § *Onboarding nudges in the chat* — its reason was the
  Getting started card; it now rests on the first run asking once, and on
  unprompted agent turns staying the parked proactivity decision.

## Decided against

| Option | Why not |
|---|---|
| The chat agent asking the questions in the main chat | It paraphrases fixed copy, cannot draw chips, carries 27 tool schemas per answer, and puts the first run in the person's thread. |
| One extraction call, with server code writing the rows | It would be a second way to write the same rows; an agent on the app's own tools writes exactly what the app writes, and can ask the one follow-up. |
| Parsing answers in the app | *"Five nine, around 72 kilo"*, *"15k"*, Hindi numbers and speech defeat a parser short of a model; two parsers would drift. |
| Holding answers until *Get started* | Lost if the app dies; a card would claim a write that hasn't happened. |
| A `birth_year` column | `dob` already exists; 1 January of the year keeps the year, which is all an age gives. |
| Gender and diet as memories | They are categories the app computes with; memory text cannot be computed on. |
| An approximate flag on every field | Weight is the one answer people guess; a flag for each column is storage for a hypothetical use. |
| Storing the picks on the server | Nothing there reads them; Home's widgets are already a phone-side layout. |
| A per-habit frequency (*every day*) | `habits.md` decided against per-habit targets; a frequency nothing reads would be a stored claim. |
| Calories and protein on screen 4 | Spica is goal-first; a daily target is the app's number, not the person's goal. |
| A category beside the BMI | Contested cut-offs, and a judgement nobody asked for. |
| Keeping Getting started after the flow | Two first-day voices for one job, and its protein-and-calorie step contradicts the goal-first decision. |
| Rewording question a so it claims less | The reads that make it true are small; shipping them keeps the approved words. |
| Replacing *6 hours a week* with something Spica measures | The door is marketing; the owner keeps the promise the *Your time* pick makes. |
| Preselected picks | The person's choice would be made for them. |
| A coloured dot before each card's heading | Next to the amber estimate dot, a diet-orange dot reads as a second estimate. |
| CSS transitions or `Animatable` chains for the film | Two engines guessing the same rules can't be checked against each other; a clock and one pure function can, to the pixel. |
| One JSON timeline read by both apps | Neither build reads assets from outside its tree; the token files' twin-file pattern already works. |
| Replaying a resent answer by request id | It needs a store for the first response — a table, or the one chat thread; the tools are already safe to repeat, so a resend writes the same rows. |
| A frame-for-frame unit test for the phone's film | The backend-only testing rule stands: the owner kept it. Parity is checked by hand — both films frozen at the same milliseconds and compared. |

## Definition of done

`backend/tests/test_onboarding_goals.py` asserts the server side with the
fake model; `n2n_eval` gains an onboarding block on an empty account for the
real agent; the screens and the film are checked by hand.

| Check | How |
|---|---|
| A turn whose model calls `update_profile` and `log_day` for *"Sonu, male, 28. Five nine, around 72 kilo"* → name Sonu, gender male, dob 1998-01-01, height 175.3, a weigh-in of 72.0 marked estimated; one confirm card per write, the weight's holding the weigh-in, whose delete clears the day's copy | test |
| `log_day` with an exact weight → not estimated; a later exact weigh-in the same day clears the flag; `GET /weigh-ins` and `diet_report` return it | test |
| `update_profile` writes gender, dob, height, city and diet, turns an `age` of 28 into dob 1998-01-01, and refuses a value outside each check; `PATCH /users/me` refuses a null name and a future date of birth | test |
| `remember` from an onboarding turn writes a memory with source `user`, confirmed | test |
| *"Lose 5 kilo"* with a weigh-in of 72 → weight target 67.0; with no weigh-in → a memory, no target | test |
| `manage_habit` for a name already tracked reuses it, no error, leaves it as it was and says so on its card; no frequency is stored | test |
| `next_question` sets `next`; a turn with no write and no `next_question` returns the reply | test |
| A failing write mid-turn leaves nothing from that turn | test |
| The same answer sent twice writes the same rows once; two at once run one after the other; `409` once done; `429` past the daily cap, and on every turn at a cap of 0 | test |
| No turn is written to the chat thread, and no payment or meal is written | test |
| The backfill sets `onboarding_done_at` for accounts with a row in any listed table and leaves empty accounts null; PATCH with null keeps the flag | test |
| `/deck` sends `onboarding.done_at` and an empty `steps` | test |
| *Who they are* carries gender, *born 1998*, height, weight (*approximately* when estimated), city and diet; *Their targets* the weight target; `build()` reads no date | test |
| The meal plan's payload carries diet, memories, city and the body facts; a change outside it makes no new plan | test |
| The onboarding block of `n2n_eval` passes three runs in three: each sample answer through the real agent, metric and Hinglish forms, spoken digits, partial answers and the one follow-up, skips, *15k*, a diet outside the four (*vegan*), a goal with and without a weight, two habits in one sentence, an off-topic answer — the rows, the estimate flag and the cards checked | `n2n_eval` |
| A veg account's meal plan holds no meat or egg | `n2n_eval` |
| The 79-case day stays at 96.3% of cases and 98.7% of turns, no passing case failing two of three runs | `n2n_eval` |
| The web film matches `spec/reference/onboarding-film.dc.html` within 0.5 px in position and size at the sampled moments; colour matches except the corrected mess slot | by hand, scripted in Chrome |
| The phone film matches the web film, frozen at the same milliseconds | by hand |
| Profile on both surfaces shows and clears gender, age and diet, and dots an estimated weigh-in | by hand |
| The four screens on the web preview and the emulator: every pick combination's questions and widgets, Edit and Undo on a card, the follow-up, the failure and retry state, Skip, Back, coming back mid-flow, an empty screen 4 | by hand |
