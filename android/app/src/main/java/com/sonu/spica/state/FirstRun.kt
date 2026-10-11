package com.sonu.spica.state

import com.sonu.spica.data.ChatMsg
import com.sonu.spica.data.ComposeContext
import com.sonu.spica.data.HabitRow
import com.sonu.spica.data.MemoryRow
import com.sonu.spica.data.Profile
import com.sonu.spica.data.WeighInRow

/*
 * The first run, after sign-in and before Home — spec/done/onboarding-goals.md.
 * Screen 2 asks what to take control of, screen 3 asks a few fixed questions
 * that the onboarding agent writes through the app's own tools, screen 4
 * reads back what was set. The door is screen 1, and is `ui/door`.
 */

/** Screens 2–4. */
enum class FirstRunStep { Choose, Ask, Ready }

/**
 * Screen 2's picks, each said as what you get, and the Home widgets each
 * switches on. Five picks, three domains — not a fourth mode. The picks are
 * not stored on the server: they choose the questions and the phone's layout.
 */
enum class Pick(val title: String, val line: String, val widgets: List<HomeWidget>) {
    Money("Your money", "Know where it goes. Keep more of it.", listOf(HomeWidget.Money)),
    Food("Eating healthy", "Better meals, no counting.", listOf(HomeWidget.Diet, HomeWidget.Meals)),
    Health("Your health", "Weight, sleep, workouts — moving right.", listOf(HomeWidget.Activity, HomeWidget.Workout)),
    Habits("Your habits", "Build the good ones. Cut the rest.", listOf(HomeWidget.Habits)),
    // Today is always first on Home: the time pick switches nothing more on.
    Time("Your time", "Work on track, and your evenings back.", emptyList()),
}

/**
 * Screen 3's questions, fixed copy, in the order they are asked. `id` is the
 * name the server's agent knows each by; `pick` is what asks for it — the
 * first two are always asked. Each that stores something that changes what
 * Spica does says why it asks.
 */
enum class Question(val id: String, val lines: List<String>, val chips: List<String>, val pick: Pick?) {
    About(
        "about",
        listOf(
            "Let’s start with a little about you. Would you share your name, gender, age, height and weight?",
            "It helps me work out your BMI, so every suggestion fits you. Just say it — or type it.",
        ),
        emptyList(), null,
    ),
    Place(
        "place",
        listOf("Where do you live, and what do you eat? Then the meals I suggest are ones you can get, and actually want."),
        listOf("Veg", "Non-veg", "Eggetarian", "Anything"), null,
    ),
    Health(
        "health",
        listOf("What’s your health goal? Give me a number if there is one — like lose 5 kg."),
        listOf("Lose weight", "Gain muscle", "Eat cleaner"), Pick.Health,
    ),
    Money(
        "money",
        listOf("How much do you want to save every month? I’ll keep your daily spending to what’s left after it."),
        emptyList(), Pick.Money,
    ),
    Habits(
        "habits",
        listOf("Which habits do you want to track?"),
        listOf("Gym", "Running", "Sleep early", "Fewer cigarettes"), Pick.Habits,
    ),
}

/** One line of screen 3's thread. Kept on the phone only: the server writes rows, never the turns. */
sealed interface FirstRunLine {
    val id: String

    data class Agent(override val id: String, val text: String) : FirstRunLine

    /** Yours; `context` is the card an Edit was about, drawn above your words. */
    data class Said(override val id: String, val text: String, val context: String? = null) : FirstRunLine

    /**
     * A write, as the app's own confirm card. `question` is the one it
     * answered; `before` is the person as they were when the answer was sent,
     * so Undo puts a profile fact back to what it was — empty on a first run,
     * the old value on a correction or coming back — never blindly to null.
     */
    data class Card(override val id: String, val msg: ChatMsg.Confirm, val question: Question, val before: Profile) : FirstRunLine {
        /** The profile column it wrote — an age is the date of birth — or null for any other write. */
        val column: String? get() = if (msg.source != "profile") null else msg.fields.firstOrNull()?.key?.let { if (it == "age") "dob" else it }
    }
}

/**
 * The first run's state. Answers are written as they come, so this holds only
 * what spans them — the thread, the picks, the question asked — and goes with
 * the process: coming back starts on screen 2 with nothing picked, and screen
 * 3 skips what the rows already hold.
 */
data class FirstRun(
    val step: FirstRunStep = FirstRunStep.Choose,
    val picks: Set<Pick> = emptySet(),
    val thread: List<FirstRunLine> = emptyList(),
    /** Every question put to them this run, in order. */
    val asked: List<Question> = emptyList(),
    /** The question waiting for its answer. Null before the first, and once there are no more. */
    val at: Question? = null,
    /** "Say that again?" said on `at` — a second unreadable answer moves on as a skip. */
    val again: Int = 0,
    val typed: String = "",
    /** An Edit: the card it is about rides above the bar, and its sentence goes ahead of your words. */
    val context: ComposeContext? = null,
    /** The question the edited card answered — sent with the correction once no question is open. */
    val contextOf: Question? = null,
    /** Bumped to hand the bar the cursor — a chip, an Edit. */
    val focus: Int = 0,
    /** Reading the rows before the first question, or an answer with the agent. */
    val busy: Boolean = false,
    /** The phone's recogniser is up. */
    val listening: Boolean = false,
    /** The last answer did not go through — said once, under the thread, until the next send. */
    val problem: String? = null,
    /** The questions have been chosen against the rows: until then nothing is asked. */
    val started: Boolean = false,
    /** The day's cap on answers was reached: the questions end there, with nothing written. */
    val capped: Boolean = false,
    /** Skip on screen 3: the rest go unasked, even by an answer or a read that lands after it. A new Continue on screen 2 clears it. */
    val skipped: Boolean = false,
    /** Get started (or a Skip) on its way. */
    val leaving: Boolean = false,
) {
    /** Screen 3 is done: every question it asked has been answered or skipped. */
    val finished: Boolean get() = started && at == null

    /** A write still standing — an undone one does not count. */
    val gaveAny: Boolean get() = thread.any { it is FirstRunLine.Card && it.msg.state != "deleted" }

    /**
     * A later write to the same profile column, still standing, holds the
     * value now: undoing this card would quietly overwrite it, so it has no Undo.
     */
    fun superseded(card: FirstRunLine.Card): Boolean {
        val column = card.column ?: return false
        val at = thread.indexOfFirst { it.id == card.id }
        if (at < 0) return false
        return thread.drop(at + 1).any { it is FirstRunLine.Card && it.column == column && it.msg.state != "deleted" }
    }
}

/** A goal said in words, as the onboarding agent keeps one. */
fun isGoal(m: MemoryRow): Boolean = m.kind == "project" && m.slug.startsWith("goal-")

/** What a diet leaves out, as the agent keeps it: "Never eats beef", "Vegan — never eats dairy". */
fun isDietNote(m: MemoryRow): Boolean = m.kind == "preference" && (m.slug.startsWith("never-eats-") || m.slug.startsWith("diet-"))

/**
 * What the rows already hold, read live — so a question with any of its facts
 * set is not asked again, the same test as the web's `facts.ts`. The name does
 * not count: Google's fills it at sign-in, before anything is asked.
 */
fun alreadyAnswered(q: Question, p: Profile, weighIns: List<WeighInRow>, memories: List<MemoryRow>, habits: List<HabitRow>): Boolean = when (q) {
    Question.About -> p.gender != null || p.dob != null || p.heightCm != null || weighIns.isNotEmpty()
    Question.Place -> p.city != null || p.diet != null || memories.any(::isDietNote)
    Question.Health -> p.weightTargetKg != null || memories.any(::isGoal)
    Question.Money -> p.savingsTarget != null
    Question.Habits -> habits.isNotEmpty()
}

/** The phone's widget list for these picks: exactly what they switch on, in Home's own order. */
fun widgetsFor(picks: Set<Pick>): List<String> {
    val on = picks.flatMap { it.widgets }.toSet()
    return HomeWidget.entries.filter { it in on }.map { it.id }
}
