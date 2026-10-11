# AI Life Companion — Product Vision & Concept

**Status:** early concept / product discovery. Nothing here is decided, nothing
here is owed. Recorded 2026-09-18 so the thinking survives.

**Placed 2026-09-18: this is Cortex.** Not a fourth mode — the deck stays three
(money, health, work; `spec/archive/screen-time.md` says why a fourth card was
removed). It is a **layer across** the three: the agent gaining a sense of *now*
and *next* on top of the modes that already hold *what happened*.

**Why Cortex and not a second app.** Cortex already measures the whole person —
what was eaten, what was spent, what was done, what is owed, what is committed.
That measurement is the expensive part, and it is the exact input "what should I
do now?" needs. A second app would spend a year rebuilding the substrate before
it could say anything a stranger could not. The premise is also the same one:
*agent hi app hai* — one conversation, no forms.

**What Cortex genuinely does not have yet**, and what this doc is therefore
asking for:

- **Direction.** Cortex knows goals as targets (calories, a budget). It does not
  know *who the user is trying to become*, which is what turns a list into a
  next step.
- **Now.** Nothing in the schema knows what the user is doing at 3:40pm, or that
  the plan stopped being true at 10:15.
- **Park and return.** Capture exists for things from the outside world
  (`spec/capture.md`); there is nothing for a stray thought that arrives mid-task
  and needs to be taken off the user's hands without stopping them.
- **A proactive loop.** `spec/in-progress/schedules.md` is its spine — jobs that
  fire without a laptop open, a morning brief among them. It is built; the
  crontab line is not installed.

**Still open, and the hard part:** proactivity and silence. Everything Cortex
does today is user-initiated. The first thing Cortex says unprompted is a
product decision it has never had to make, and getting it wrong turns a
companion into a notification machine.

Everything below is the concept as written, unedited.

---

# 1. Executive Summary

The product is an **AI life companion** designed to help a person navigate their entire day—not simply manage tasks.

The fundamental idea is:

> **An AI that knows the context of your life and helps you live deliberately, one moment at a time, without turning your life into a rigid schedule.**

The product combines:

* persistent personal memory
* AI conversation
* daily planning
* adaptive scheduling
* work/project awareness
* emotional context
* relationships and social context
* personal goals
* routines
* calendar/tasks
* wearable, low-friction interaction
* proactive but non-intrusive assistance
* real-world execution through connected tools

The user should not have to constantly open an app and ask:

> "What should I do now?"

Instead, the system should understand:

> **Who I am → what I'm trying to achieve → what's happening today → what changed → how I'm feeling → what matters now → what should happen next.**

The long-term vision is an **AI personal operating system**.

---

# 2. The Core Problem

Modern productivity systems generally assume:

> **If I create a good plan, I will follow it.**

Real life doesn't work that way.

A person may create:

```text
09:00–11:00  Work
11:00–11:30  Break
11:30–13:00  Feature
14:00–16:00  Work
18:00        Gym
20:00        Learning
```

But during the day:

* a work issue appears
* someone sends a message
* a meeting takes longer
* an unexpected task appears
* the person becomes distracted
* an old memory comes up
* anxiety or loneliness appears
* energy changes
* an interesting idea appears
* the original task takes longer than expected

The plan becomes inaccurate.

Then the user often experiences:

**Plan → deviation → perceived failure → guilt → loss of confidence → avoidance → more deviation.**

The problem isn't necessarily lack of discipline.

The problem is that the system treats a **dynamic human life as a static schedule**.

---

# 3. The Central Insight

The product should not primarily optimize:

> **Task completion.**

It should optimize:

> **Intentional living.**

That means helping the user maintain a direction while remaining flexible about what happens in each moment.

The user should be able to say:

> "This is the kind of person I want to become."

And the system continuously helps translate that into:

> **What makes sense now?**

---

# 4. The "One Thing at a Time" Philosophy

One of the major ideas discovered during the conversation is that:

> **Being present does not mean having only one thought.**

A person's mind will naturally produce many thoughts.

While working on one feature, they may suddenly think:

* "I need to fix another issue."
* "What should I do tonight?"
* "I haven't replied to someone."
* "What am I doing with my career?"
* "I should go to the gym."
* "I have an idea for a product."
* "Why did that thing happen in the past?"

The product should **not try to eliminate thoughts**.

Instead:

### Capture → park → return.

For example:

> "I just remembered something I need to do tomorrow."

AI:

> "Got it. I've captured it. You don't need to solve it now."

Then:

> **"Continue with the feature?"**

The objective is not:

> "Think about only one thing."

It is:

> **"You can have many thoughts without having to follow every thought."**

---

# 5. The Product's Relationship With the User

The AI should behave more like a **companion/mentor** than a traditional productivity application.

A useful metaphor discovered during the discussion was:

> **Doraemon for adult life.**

Not literally copying Doraemon, but capturing the relationship:

* persistent presence
* knows the person's context
* understands the situation
* helps when the person is stuck
* provides the appropriate tool
* helps the person move forward

However, there is an important distinction:

### The AI must not control the person's life.

It should preserve **agency**.

The AI should help the user make decisions, not become another authority that the user must obey.

---

# 6. The AI's Core Principle

The system should continuously answer:

> **"Given everything I know about this person and what is happening right now, what would be the most useful next step?"**

Not:

> "What was written in the morning schedule?"

This distinction is fundamental.

---

# 7. Persistent Personal Context

The AI should gradually build a deep understanding of the user.

Potential context includes:

### Identity & values

* what the person cares about
* personal principles
* desired identity
* things they want to become
* things they don't want to become

### Goals

* career goals
* financial goals
* fitness goals
* learning goals
* personal goals
* long-term ambitions

### Work

* current job
* projects
* tasks
* repositories/projects
* deadlines
* recurring responsibilities
* work preferences
* current priorities

### Daily life

* routines
* sleep/wake preferences
* exercise
* meals
* commute
* free time
* recurring activities

### Relationships

* friends
* family
* important people
* social commitments
* important dates

### Preferences

* things the user likes
* things the user dislikes
* preferred routines
* preferred ways of working
* preferred communication style

### Past

The user may voluntarily share:

* important experiences
* mistakes
* regrets
* difficult periods
* lessons learned
* personal history

The purpose is **context**, not surveillance.

---

# 8. Memory Should Not Mean "Remember Everything"

An important future design principle:

> **The AI should maintain a useful model of the person, rather than becoming an infinite recording device.**

The system should distinguish between:

### Temporary context

Example:

> "I'm tired today."

and:

### Long-term context

Example:

> "I prefer working out in the evening."

and:

### Important life context

Example:

> "This is a major long-term career goal."

The AI should continuously organize these layers.

---

# 9. Daily Life Management

The product should manage the entire day, not just work.

For example:

```text
07:00
Wake up

07:30
Morning routine

09:00
Work

09:00–13:00
Work priorities

13:00
Lunch

14:00
Work

18:30
Leave work

19:15
Gym

20:30
Dinner

21:00
Personal time

22:00
Learning / project / relaxation

23:00
Wind down

23:30
Sleep
```

But this should **not be rigid**.

The system should continuously adapt.

---

# 10. Dynamic Planning

Suppose the user planned:

> 9–11 → Feature development.

At 10:15 an unexpected issue appears.

Instead of:

> ❌ "You failed your schedule."

The AI should understand:

> "The original plan no longer represents reality."

Then recalculate:

```text
Current situation
       ↓
What changed?
       ↓
What is still important?
       ↓
What can move?
       ↓
What should happen next?
```

The system creates a new realistic path.

---

# 11. The Evening Problem

A specific problem identified during the discussion:

The user can successfully finish work, but then reaches the evening and thinks:

> "Okay... what now?"

This is where conventional work planners fail.

The AI should understand that **life continues after work**.

It can consider:

* gym
* learning
* personal projects
* social activities
* relaxation
* errands
* dinner
* recovery
* hobbies
* preparation for tomorrow

But it shouldn't automatically fill every minute.

Sometimes the correct recommendation may simply be:

> **"You've done enough today. Have dinner and relax."**

---

# 12. Present-Moment Assistance

The AI shouldn't only plan the day in the morning.

It should operate throughout the day.

Example:

### User is working

> "I'm distracted."

AI:

> "You've got 40 minutes before your next commitment. The feature you're working on is still the highest-priority item. Want to stay with it until then?"

---

### User has a random thought

> "I should research another technology."

AI:

> "I'll capture that for later. You're currently working on X."

---

### User didn't follow the plan

AI:

> "That's okay. The plan was a prediction, not a test. It's 3:40 now. Let's work from here."

---

# 13. Handling Guilt

This is an important part of the product.

The system should **not reinforce guilt-based productivity**.

A traditional productivity system might effectively communicate:

> "You didn't complete 6/10 tasks."

The AI companion should instead ask:

> "What actually happened?"

Then:

```text
Planned
↓
Actual
↓
Why did it change?
↓
Was the change reasonable?
↓
What matters now?
```

The user shouldn't have to repeatedly prove that they're disciplined.

The system should help build **self-trust**.

---

# 14. Self-Trust Over Perfect Adherence

The objective isn't:

> **100% adherence to the plan.**

Instead:

> **Consistently returning to your direction after life pulls you away.**

This produces a more realistic definition of discipline:

> **Not never getting distracted.
> Being able to return.**

---

# 15. The "Straight Line" Concept

Another concept from the discussion is the desire for a **straight direction**.

Not necessarily:

```text
Goal
 ↓
Perfect schedule
 ↓
Perfect execution
 ↓
Success
```

But:

```text
Identity / Values
       ↓
Direction
       ↓
Today's priorities
       ↓
Current moment
       ↓
Next useful action
```

The path can bend.

The direction remains.

This is the philosophical foundation of the product.

---

# 16. Interaction Model

The product should minimize friction.

The user shouldn't constantly:

1. unlock phone
2. open app
3. type
4. wait
5. read
6. close app

Instead:

> **Speak naturally.**

Examples:

> "What's next?"

> "I'm getting distracted."

> "I finished that task."

> "Remind me about this tomorrow."

> "I don't feel like working."

> "I have an idea."

> "What should I do this evening?"

> "I feel lonely."

> "I can't focus."

The AI already has the context.

---

# 17. The AI Should Know When NOT to Talk

This is critical.

An always-present AI shouldn't become another source of notifications.

Sometimes:

> **Silence is the correct response.**

The AI should understand:

* when the user is focused
* when interruption would be harmful
* when the user is busy
* when a reminder can wait
* when the user needs space

The system should be **ambient, not annoying**.

---

# 18. Hardware Vision

We initially considered a dedicated microphone device.

The concept evolved.

### Current decision:

**Do not build dedicated hardware initially.**

Use existing hardware to validate the experience.

The dedicated microphone is therefore **removed from Phase 1**.

---

# 19. Phase 1 Hardware

The current preferred prototype ecosystem is:

### Android phone

The primary computing device.

Responsible for:

* main app
* AI interaction
* memory
* planning
* integrations
* network
* UI

### Wear OS smartwatch

Potentially a Samsung Galaxy Watch or another compatible Wear OS watch.

Responsible primarily for:

* microphone/input
* quick interaction
* haptic feedback
* optional tiny UI
* wearable presence

### Earbuds

Responsible primarily for:

* AI voice output
* natural conversational interaction

The user shouldn't need to take out their phone every time.

---

# 20. Phase 1 Architecture

Conceptually:

```text
             ┌─────────────────────┐
             │     AI Backend      │
             │                     │
             │ Reasoning           │
             │ Long-term Memory    │
             │ User Model          │
             │ Planning            │
             │ Agent               │
             └──────────▲──────────┘
                        │
                        │
                 Internet / API
                        │
             ┌──────────▼──────────┐
             │    Android App      │
             │                     │
             │ Life Context        │
             │ Calendar            │
             │ Tasks               │
             │ Memory              │
             │ Settings            │
             │ Agent Control       │
             └──────────▲──────────┘
                        │
                  Wear OS / BT
                        │
             ┌──────────▼──────────┐
             │    Smartwatch       │
             │                     │
             │ 🎙 Microphone       │
             │ Haptics             │
             │ Minimal UI          │
             └─────────────────────┘
                        │
                        │ Bluetooth
                        ▼
                  🎧 Earbuds
```

---

# 21. Why the Watch Is Interesting

The watch solves an important problem:

> **The AI is physically accessible without requiring the phone to be in the user's hand.**

This reduces friction.

The user can be:

* walking
* working
* cooking
* exercising
* commuting
* outside
* away from their desk

and still interact.

---

# 22. Interaction With the Watch

The initial version should probably be interaction-driven rather than attempting to record everything continuously.

Example:

**User taps watch**

🎙️

> "I just remembered something."

AI:

> "Tell me."

User speaks.

AI:

> "Captured. I'll put it in your ideas inbox."

Then the user returns to what they were doing.

This is much closer to the desired experience than creating a device that simply records the user's entire life.

---

# 23. Privacy Philosophy

Because the product deals with extremely personal context, privacy must be a fundamental product principle rather than a marketing feature.

The user should understand:

* when the microphone is active
* what is being captured
* what is stored
* what is sent to the cloud
* what the AI remembers
* what can be deleted
* what can be forgotten
* what integrations have access to

The device should have a **clear recording/privacy state**.

A physical or highly visible privacy mechanism may eventually be important for dedicated hardware.

---

# 24. Dedicated Hardware — Future Phase

A dedicated device remains part of the **long-term vision**, but not the initial product.

The idea is a tiny wearable that can be:

### Option A — Watch-style

A small device attached to the wrist.

### Option B — Pendant

A tiny device around the neck.

### Option C — Clip

A tiny device attached to:

* shirt
* jacket
* bag
* pocket

The generated concept exploration currently contains all three form factors.

---

# 25. Dedicated Hardware Philosophy

The dedicated device should **not attempt to replace the phone, smartwatch, or earbuds**.

It should be extremely simple.

Potential components:

```text
Microphone
    +
Button / gesture
    +
Haptic feedback
    +
Bluetooth
    +
Battery
```

Possibly no:

* display
* speaker
* large processor
* camera

because existing devices already provide those capabilities.

The core philosophy:

> **Don't build hardware until the software proves that existing hardware isn't enough.**

---

# 26. Future Hardware Interaction

The ideal future experience could become:

```text
User wears tiny companion
          ↓
User speaks naturally
          ↓
Companion captures input
          ↓
Phone / cloud processes it
          ↓
AI understands context
          ↓
Response delivered through earbuds
          ↓
User continues life
```

The user doesn't think:

> "I'm using an AI application."

It should feel closer to:

> **"My companion is with me."**

---

# 27. The Product Is Not Just a Chatbot

ChatGPT-like conversation is an important interface, but conversation alone isn't enough.

The system needs to **act**.

Potential actions:

* create tasks
* reschedule tasks
* manage calendar
* organize ideas
* capture notes
* prepare daily plans
* adapt schedules
* surface relevant information
* interact with connected services
* remind the user
* maintain personal context
* initiate appropriate workflows

The distinction is:

### Chatbot

> User asks → AI answers.

### Life Companion

> AI understands context → determines what is useful → assists → executes when appropriate → updates context.

---

# 28. Long-Term Agent Behavior

The AI should eventually maintain several continuously evolving models:

```text
                    USER
                     │
       ┌─────────────┼──────────────┐
       ↓             ↓              ↓
    Identity       Goals         Preferences
       │             │              │
       └─────────────┼──────────────┘
                     ↓
                Life Context
                     │
       ┌─────────────┼──────────────┐
       ↓             ↓              ↓
     Work          Health*       Relationships
       │                            │
       └──────────────┬─────────────┘
                      ↓
                Current Day
                      ↓
              Current Situation
                      ↓
               NEXT BEST ACTION
```

*Health-related functionality would require particularly careful privacy and safety design.

---

# 29. The Core Loop

The product's fundamental loop could be:

```text
UNDERSTAND
     ↓
PLAN
     ↓
ACT
     ↓
OBSERVE
     ↓
ADAPT
     ↓
ACT AGAIN
```

Instead of:

```text
PLAN
 ↓
FAIL
 ↓
GUILT
```

The system continuously adapts.

---

# 30. Morning Experience

The morning should not begin with a giant productivity dashboard.

Potential experience:

> **Good morning.**

> "Here's what matters today."

Then perhaps:

```text
TODAY'S DIRECTION

Work
→ Finish medical OCR feature

Personal
→ Gym

Learning
→ Optional 45 min

Evening
→ Keep open

Next
→ Start the first work block
```

The user should understand:

> **Where am I going?**

rather than memorizing 20 tasks.

---

# 31. During the Day

The AI continuously asks internally:

> What is the user doing?

> What did they intend to do?

> What changed?

> Is intervention useful?

> What's the next meaningful action?

But the user doesn't need to see this reasoning process.

They simply experience:

> **Useful assistance at the right moment.**

---

# 32. Evening Experience

The evening is treated as part of life rather than empty space after work.

The AI could say:

> "Work is done. You planned to train today. You've got enough time. Want to head to the gym?"

Or:

> "You had a heavy day. The gym is optional tonight. Dinner and rest may make more sense."

Again:

**suggestion, not command.**

---

# 33. Night Reflection

At night the system can help the user review the day.

Not:

> "You completed 63% of your tasks."

Instead:

```text
What happened today?

What went well?

What changed?

What did you learn?

What still matters tomorrow?

What can be dropped?

How should tomorrow adapt?
```

The AI learns from reality.

---

# 34. Relationship With Emotions

The AI should understand that emotions can influence behavior.

For example:

```text
Instagram
    ↓
Comparison
    ↓
Loneliness
    ↓
Rumination
    ↓
Loss of focus
    ↓
Avoidance
```

Rather than simply saying:

> "Stop using Instagram."

The companion could recognize the pattern and help the user return to the present.

The philosophy:

> **Observe → understand → choose → return.**

Not:

> **Suppress → fight → feel guilty.**

---

# 35. What the AI Should NOT Become

The product should avoid becoming:

### ❌ A rigid productivity system

"Follow your schedule or you failed."

### ❌ A surveillance device

"Record everything about your life."

### ❌ A notification machine

"Reminder! Reminder! Reminder!"

### ❌ A replacement for human relationships

The AI should support the user's life, not attempt to become their entire social world.

### ❌ An authority over the user

It should preserve user choice.

### ❌ A system that creates dependence

The goal should ultimately be:

> **Help the user develop greater ability to navigate their own life.**

---

# 36. Product North Star

A useful North Star could be:

> **Help people live more intentionally, with less cognitive friction, while preserving their freedom to choose.**

Or more simply:

> **Know my life. Understand my moment. Help me take the next step.**

---

# 37. What Makes This Different

The product isn't differentiated simply by:

* AI
* memory
* voice
* wearable
* calendar
* tasks

The differentiation comes from combining them around one philosophy:

> **Continuous contextual assistance throughout real life.**

The product understands:

**Long-term direction**

↓

**Today's reality**

↓

**Current moment**

↓

**Next action**

---

# 38. Product Phases

## Phase 0 — Concept Validation

Define:

* exact user problem
* interaction philosophy
* memory model
* agent behavior
* privacy model
* daily planning model

No hardware.

---

## Phase 1 — Existing Hardware

### Devices

* Android phone
* Wear OS smartwatch
* Bluetooth earbuds

### Build

* Android application
* Wear OS application
* AI backend
* personal memory
* daily planner
* task system
* voice interaction
* adaptive planning

### Goal

Prove:

> **Can an AI actually become useful throughout someone's day without becoming annoying or controlling?**

---

## Phase 2 — Deeper Agent

Add:

* richer personal memory
* calendar integration
* work context
* automated rescheduling
* proactive suggestions
* better context detection
* more tool execution
* stronger long-term user model

---

## Phase 3 — Dedicated Wearable

Only after identifying limitations of existing hardware.

Possible forms:

**Watch**

**Pendant**

**Clip**

The dedicated device would primarily provide:

> **low-friction voice input + haptic interaction + persistent presence.**

---

# 39. Current Decisions — Source of Truth

These are the decisions we've made so far.

| Area                    | Current decision                                                  |
| ----------------------- | ----------------------------------------------------------------- |
| Product                 | AI life companion / personal life OS                              |
| Primary purpose         | Help user navigate life, not merely manage tasks                  |
| Core philosophy         | Intentional living rather than perfect productivity               |
| Focus model             | One meaningful thing at a time                                    |
| Thoughts                | Capture/park thoughts rather than suppress them                   |
| Planning                | Dynamic and adaptive                                              |
| Plan failure            | Never treat deviation automatically as failure                    |
| Guilt                   | Avoid guilt-based productivity                                    |
| Agency                  | User remains in control                                           |
| Memory                  | Deep persistent personal context                                  |
| Interaction             | Natural conversational interface                                  |
| Phone                   | Main app / brain / interface                                      |
| Wearable                | Low-friction access                                               |
| Phase 1 wearable        | Wear OS smartwatch                                                |
| Android                 | Preferred initial ecosystem                                       |
| Watch microphone        | Use existing watch microphone                                     |
| Dedicated microphone    | **Not Phase 1**                                                   |
| Earbuds                 | Existing Bluetooth earbuds for AI voice                           |
| 24/7 recording          | **Not the initial approach**                                      |
| Dedicated hardware      | Future possibility                                                |
| Hardware forms explored | Watch, clip, pendant                                              |
| Hardware philosophy     | Minimal hardware, only build what existing devices cannot provide |
| AI behavior             | Proactive when useful, silent when appropriate                    |
| Long-term vision        | AI that accompanies the user throughout the day                   |

---

# 40. Open Questions

These are **not decided yet** and should remain open.

### Product

* Exactly how proactive should the AI be?
* When should it interrupt?
* When should it remain silent?
* How should it determine the "next useful action"?
* How much autonomy should the agent have?

### Memory

* What should be remembered automatically?
* What should require explicit user confirmation?
* How should memories decay or become less relevant?
* How should conflicting memories be handled?

### Voice

* Push-to-talk?
* Watch gesture?
* Wake word?
* Context-aware activation?
* How much voice interaction is practical?

### Wearable

* Samsung Galaxy Watch specifically?
* Other Wear OS watches?
* Which watch capabilities are actually required?
* How much battery impact is acceptable?

### Privacy

* What is processed locally?
* What goes to the cloud?
* How is recording visibly indicated?
* What data is retained?

### Agent

* What can it execute without asking?
* What requires confirmation?
* How should it handle uncertain situations?

### Dedicated hardware

* Is a dedicated device actually necessary?
* Watch vs pendant vs clip?
* Does it need a button?
* Does it need haptics?
* What battery life is necessary?

---

# 41. The Ultimate Experience

If we compress the entire product into one interaction:

You wake up.

The AI already knows:

> who you are,
> what you're trying to become,
> what matters today,
> what happened yesterday,
> what changed,
> and what you're doing right now.

It doesn't give you a giant list.

It gives you **direction**.

Then throughout the day:

> **"What's next?"**

And the answer changes based on reality.

You get distracted.

It helps you return.

You have an unexpected problem.

It adapts.

You don't follow the plan.

It doesn't punish you.

You have an emotional moment.

It understands the context.

You finish something.

It knows what comes next.

And eventually, you don't even need to open your phone.

You simply speak.

---

# 42. One-Sentence Product Definition

> **An always-available AI life companion that remembers your life, understands your current context, continuously adapts your day, and helps you take the next meaningful step—without taking control of your life.**

### The deeper philosophy

> **The goal isn't to make humans better at following plans.**
>
> **The goal is to build a system that helps humans stay connected to their direction while life inevitably changes the plan.**

That is the core idea we have established so far.
