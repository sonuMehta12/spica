package com.sonu.spica.data

import androidx.compose.ui.graphics.Color

/**
 * The app's own shapes — the prototype's `types.ts`, field for field. The
 * server speaks the database's language (`local_day`, `amount_paise`); these
 * speak the screen's (`day`, `amt` in rupees). `Api.kt` is the one place that
 * knows both, so nothing downstream ever sees a paise.
 */

/** Work is called To-do on screen: the list's name, where a task is the thing in it. */
enum class Mode(val id: String, val label: String) {
    Paisa("paisa", "Money"), Diet("diet", "Diet"), Work("work", "To-do");

    companion object {
        fun of(id: String) = entries.firstOrNull { it.id == id } ?: Paisa
    }
}

enum class Range(val id: String) { Aaj("aaj"), Din7("7din"), Din30("30din"), Sab("sab") }

data class Tx(
    val id: String,
    /** Day of the month. */
    val day: Int,
    val name: String,
    val cat: String,
    /** Rupees. */
    val amt: Int,
    /** Written optimistically; the server has not confirmed it yet. */
    val pending: Boolean = false,
    /** The server refused or never answered. The row STAYS — visibly unsaved. */
    val failed: Boolean = false,
    /** The commitment this payment settles, if any — the server's link, never a flag on the row. */
    val commitmentId: String? = null,
    /** The link was guessed from the category, not said — the amber dot, until it is confirmed or moved. */
    val commitmentInferred: Boolean = false,
    /** Money coming IN — renders +green, never counts as an expense. */
    val credit: Boolean = false,
    /** ISO local day. */
    val date: String? = null,
    /** Soft-deleted on the server. Only the by-id read returns such rows. */
    /** When it happened, if the server said — Home's day rail places the row there. Null is unknown, never guessed. */
    val at: java.time.Instant? = null,
    val deleted: Boolean = false,
    /** Below 1 means a value on it was the agent's guess — the amber dot. */
    val confidence: Double? = null,
    /** The server's kind — `expense`, `income`, or udhaar's `lent` · `borrowed` · `repayment`. */
    val kind: String = "expense",
) {
    /** Committed money is not discretionary spend — derived from the link, never stored. */
    val fixed: Boolean get() = commitmentId != null
}

/** Udhaar's kinds, as a row of a table names them. A lending is never a category question. */
val UDHAAR_KINDS = mapOf("lent" to "Lent", "borrowed" to "Borrowed", "repayment" to "Repaid")

data class Meal(
    val id: String,
    val day: Int,
    val name: String,
    val type: String? = null,
    /** Protein, grams. */
    val p: Double,
    /** Energy, kcal. */
    val k: Int,
    /** Carbs, grams. Null = not known — never 0 standing in for unknown. */
    val c: Double? = null,
    val f: Double? = null,
    val pending: Boolean = false,
    val failed: Boolean = false,
    val date: String? = null,
    /** When it was eaten, if the server said. */
    val at: java.time.Instant? = null,
    val deleted: Boolean = false,
    val confidence: Double? = null,
)

enum class TaskKind { Work, Paisa, Diet }

data class Todo(
    val id: String,
    val name: String,
    val done: Boolean,
    val kind: TaskKind,
    /** The ISO local day it was ticked. */
    /** The moment it was ticked, when the server knows it — the day rail's place for it. */
    val doneAt: java.time.Instant? = null,
    val doneOn: String? = null,
    val project: String? = null,
    /** The model chose the project, not the person — the amber dot. */
    val projectGuessed: Boolean = false,
    /** ISO local day it is due. Null means backlog: real, but undated. */
    val due: String? = null,
    /** 1 is most urgent. Null sorts last. */
    val priority: Int? = null,
    /** Where it came from — `Linear · ENG-142`, a meeting's title. */
    val src: String? = null,
    val link: String? = null,
    /** The tracker's stage, in the team's own word. */
    val stage: String? = null,
    val tracked: Boolean = false,
    /** The tracker's name — `Linear`. */
    val origin: String? = null,
    /** Done here, not yet moved in the tracker — the reminder is showing. */
    val awaitingMove: Boolean = false,
)

data class HabitMark(val habit: String, val count: Double)

data class ChainDay(
    val day: Int,
    val date: String,
    val letter: String,
    val done: Boolean,
    val habits: List<HabitMark>,
    val isToday: Boolean,
    val future: Boolean,
)

data class Workout(val id: String, val day: Int, val kind: String, val minutes: Double? = null)

data class ProjectStat(
    val id: String,
    val name: String,
    val color: Color,
    val done: Int,
    val total: Int,
    val late: Int,
)

data class Project(
    val id: String,
    val name: String,
    val color: String,
    val description: String? = null,
    /** An emoji, or `icon:<name>` from the app's set. Null draws the first letter. */
    val icon: String? = null,
    val aliases: List<String> = emptyList(),
    val isDefault: Boolean = false,
)

/** One editable field on a confirm card. `guessed` draws the amber dot. */
data class ConfirmField(val key: String, val label: String, val value: String, val guessed: Boolean)

data class SuggestItem(
    val type: String,
    val ref: String,
    val name: String,
    val why: String,
    val saved: Boolean,
    val mealType: String?,
    val minutes: Int?,
    val proteinG: Double?,
    val kcal: Int?,
    val imageUrl: String?,
    val missing: List<String>,
    val exerciseKind: String?,
    val muscleGroup: String?,
    val tried: Int?,
)

/**
 * What a Change on a card attaches to the composer: a label you read above
 * the input, and the opening of the sentence the agent is sent. Nothing is
 * typed for you — your words follow the prefix on the way out.
 */
data class ComposeContext(val label: String, val prefix: String)

/** The thread's messages — one class per card the conversation can draw. */
sealed interface ChatMsg {
    val id: String

    /**
     * `failed` is why it did not go — set only when the send failed; Retry
     * resends `text` with its `context`, the label drawn above the bubble.
     */
    data class User(override val id: String, val text: String, val failed: String? = null, val context: ComposeContext? = null) : ChatMsg

    /** The nightly review's guesses from one turn, asked one at a time. */
    data class Review(override val id: String, val items: List<Confirm>) : ChatMsg

    /** The agent's reply: a formatted line and its explanation. */
    data class Agent(
        override val id: String,
        val title: String,
        val hl: String,
        val hlColor: Color,
        val body: String,
    ) : ChatMsg

    /** Row ids, not snapshots, so deleting a row updates every table showing it. */
    data class Table(override val id: String, val heading: String, val source: String, val ids: List<String>) : ChatMsg

    /**
     * The + menu's cards carry only an id (and which list): the card and its
     * line are read from the live rows every time they are drawn, so neither
     * goes stale after a meal lands or a row is deleted.
     */
    data class Flow(override val id: String) : ChatMsg

    /**
     * The task list. `project` narrows it to one project, by name. `line` is
     * the card's own sentence above it — the + menu's has one; the agent's
     * has none, since its reply is the text.
     */
    data class Todos(override val id: String, val scope: String, val project: String? = null, val line: Boolean = true) : ChatMsg

    /**
     * What is owed this month — live, with no rows: it draws the month's
     * commitments from state every time, so an edit or a delete anywhere
     * updates every card that showed them.
     */
    data class Commitments(override val id: String) : ChatMsg

    /** `list` is "pantry" or "dishes". */
    data class Pantry(override val id: String, val list: String) : ChatMsg

    data class Confirm(
        override val id: String,
        val source: String,
        val rowId: String?,
        /** `deleted` strikes the lede and drops the tray — the row is history. */
        val state: String,
        val lede: String,
        val fields: List<ConfirmField>,
        val unresolved: List<String>,
        val needsQuantity: List<String>,
    ) : ChatMsg

    data class Suggest(override val id: String, val items: List<SuggestItem>) : ChatMsg

    data class Ask(override val id: String, val question: String, val options: List<String>, val pendingRowId: String?) : ChatMsg
}

data class Suggestion(val id: String, val name: String, val tag: String, val tap: () -> Unit)

/** One arc of the concentric hero, with the numbers for its legend. */
data class RingSpec(
    val key: String,
    val caption: String,
    val valueStr: String,
    val totalStr: String,
    /** 0–1 of the way round. Over 1 is clamped when drawn. */
    val pct: Double,
    val color: Color,
    /** A paler leading segment — money already committed for the month. */
    val basePct: Double = 0.0,
)

/*
 * Home's widgets, worked out from live rows on every render and never stored
 * (Home's widgets). To-do needs no shape of its own: it reads
 * the tasks as they are.
 */

/** Money: what today still allows, the month in and out, then three figures. */
data class PaisaGlance(
    /** The server's daily limit. Null until it lands, or while it is unknown — a dash, never ₹0. May be negative: past the line. */
    val limit: Int?,
    val spentToday: Int,
    /** Everything that came in this month — salary, repayments, borrowings. */
    val cameIn: Int,
    /** This month's spending, fixed costs included; lending is not spending. */
    val goneOut: Int,
    /** Where the month is heading. Null while the limit is loading. */
    val saving: Int?,
    /** 0 is none set. */
    val savingsTarget: Int,
    /** What is still owed this month — the server's total. Null while the limit is loading. */
    val committed: Int?,
    val lentOut: Int,
    val lentOpen: Int,
    /** The server answered and has no limit yet: no income this month. A dash that says why — not a loading dash. */
    val salaryPending: Boolean = false,
) {
    /**
     * How far today's spending is past today's limit — null when it is not,
     * or the limit has not landed. Worked out from spent and limit, never the
     * server's `left`, so a clamped `left` could not hide it behind a ₹0.
     */
    val overToday: Int? get() = limit?.let { spentToday - it }?.takeIf { it > 0 }
}

/** Diet: today's food against its targets. */
data class DietGlance(
    val protein: Double,
    val proteinTarget: Double?,
    val kcal: Double,
    val kcalTarget: Int?,
    /** Null when no meal today records it: unknown, not zero. */
    val carbs: Double?,
    val carbsTarget: Double?,
    val fat: Double?,
    val meals: Int,
)

/** One habit's row: a build habit fills its days, a break habit counts them. */
data class HabitLine(val name: String, val counted: Boolean)

/** Habits: this calendar week, Monday first, one row per habit. */
data class HabitsGlance(val lines: List<HabitLine>, val week: List<ChainDay>)

/* ─── today's plan — spec/in-progress/today-plan.md ─────────────────────── */

/** One meal still ahead today: a library dish at its own numbers, or an idea whose macros are an estimate. */
data class PlanMeal(
    val slot: String,
    val dishId: String?,
    val name: String,
    val kcal: Int,
    val protein: Double,
    val carbs: Double?,
    val fat: Double?,
    val why: String,
    val idea: Boolean,
    val imageUrl: String?,
    val imageCredit: String?,
)

data class PlanExercise(val exerciseId: String?, val name: String, val detail: String, val idea: Boolean)

/** Today's one workout: a gym session with its exercises, a run, a ride, a walk — or a rest day. */
data class PlanWorkout(
    val kind: String,
    val name: String,
    val minutes: Int?,
    val why: String,
    val exercises: List<PlanExercise>,
    val idea: Boolean,
    val imageUrl: String?,
    val imageCredit: String?,
)

/** The server's plan for the rest of today. `available` false: it could not plan just now. */
data class TodayPlan(
    val available: Boolean,
    val done: Boolean,
    val proteinTarget: Double?,
    val kcalTarget: Int?,
    val loggedProtein: Double,
    val loggedKcal: Int,
    val plannedProtein: Double,
    val plannedKcal: Int,
    val meals: List<PlanMeal>,
    val workout: PlanWorkout?,
)

/* ─── commitments — spec/done/commitments.md ─────────────────────── */

/**
 * One line of what is owed: a commitment the person owns, or a borrowing
 * worked out live from udhaar (`source == "borrowing"`, read-only here). Paid
 * and owed are the server's, worked out from the linked payments — never kept.
 */
data class Commitment(
    val id: String,
    val name: String,
    /** `commitment` · `borrowing`. */
    val source: String,
    /** `manual` · `rolled` · `carried` · `borrowing`. */
    val origin: String,
    val category: String,
    /** Rupees. */
    val expected: Int,
    val paid: Int,
    val owed: Int,
    val over: Int,
    val settled: Boolean,
    val skipped: Boolean,
    val dueDay: Int?,
    val repeats: Boolean,
    /** `rolled` — copied from last month, not stated: the amber dot. */
    val rolled: Boolean,
    val inferredLinks: Int,
    /** ISO first-of-month of the line this is the unpaid remainder of. */
    val carriedFrom: String?,
    /** Written optimistically; the server has not confirmed it yet. */
    val pending: Boolean = false,
) {
    val isBorrowing: Boolean get() = source == "borrowing"
}

/** The page: the month's lines, and the chain from the pool to the limit so a zero is never a mystery. */
data class CommitmentsPage(
    /** ISO first of the month. */
    val month: String,
    val editable: Boolean,
    val owed: Int,
    val pool: Int,
    val savingsTarget: Int,
    /** Null before the month's first income: unknown, not zero. */
    val limit: Int?,
    val daysLeft: Int,
    val paidCount: Int,
    val openCount: Int,
    val items: List<Commitment>,
)

/**
 * What the add/edit sheet holds. `id` set is an edit. `linkTx` is the payment
 * *Make this a commitment* started from, linked on save.
 */
data class CommitmentDraft(
    val id: String? = null,
    val name: String = "",
    val amount: Int? = null,
    val category: String = "",
    val dueDay: Int? = null,
    val repeats: Boolean = true,
    val linkTx: String? = null,
)
