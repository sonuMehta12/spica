package com.sonu.spica.logic

import com.sonu.spica.data.PlanMeal
import com.sonu.spica.data.PlanWorkout
import com.sonu.spica.lib.Day
import com.sonu.spica.lib.Fmt
import com.sonu.spica.state.AppState
import java.time.Instant
import java.time.LocalTime
import java.time.ZoneId

/** The widget a row opens, as a sheet over the day. */
enum class DaySheet { Money, Diet, Habits, Work, Activity }

/** What a row is, which decides its glyph and its one action. */
enum class RailKind { Spend, Meal, Habit, Task, PlanMeal, Workout, Schedule }

/**
 * One moment on the day rail. `time` is what the time column says: the clock
 * (`10:30`), a plan slot (`Lunch`), or a dash when the row has no time — a row
 * is never given one.
 */
data class RailRow(
    val key: String,
    val kind: RailKind,
    val sheet: DaySheet,
    val time: String,
    val title: String,
    /** One figure on the right: `−₹200`, `14g`, `2nd today`. */
    val figure: String? = null,
    /** A task's project, under its title. */
    val sub: String? = null,
    /** `2 days late` — said in red after the project. */
    val late: String? = null,
    /** Happened, or ticked: the node is solid. */
    val done: Boolean = false,
    /** Spica's estimate or suggestion, not yet confirmed — the amber dot. */
    val estimate: Boolean = false,
    val taskId: String? = null,
    val planMeal: PlanMeal? = null,
    val workout: PlanWorkout? = null,
    /** A schedule's own sentence, for its card. */
    val blurb: String? = null,
    /** A habit log's habit — its sheet is that habit's alone. */
    val habit: String? = null,
    /** A schedule's repeat, said for its card: `Every day`, `Mon · Thu`. */
    val repeat: String? = null,
    /** Where a task came from — a meeting's title, `Linear · ENG-142`. */
    val taskSource: String? = null,
)

/** The day: what happened, the one thing next, the rest with a time, the rest without. */
data class Rail(val past: List<RailRow>, val next: RailRow?, val later: List<RailRow>, val anytime: List<RailRow>)

/** Which day the rail shows, against today. */
enum class DayKind { Past, Today, Ahead }

/** A day's line of totals, each a dash when the day has no rows of its kind. */
data class DayTotals(val spent: String, val protein: String, val tasksDone: String, val empty: Boolean)

/** A key number in the glance panel. Unknown is a dash, never 0. */
data class KeyNumber(val sheet: DaySheet, val value: String, val label: String, val labelIsLate: Boolean = false)

/**
 * Home's day, worked out from the rows each time it is drawn — nothing here is
 * stored. `spec/home-day-rail.md`.
 */
object DayRail {
    private val zone: ZoneId get() = ZoneId.systemDefault()

    /**
     * A row's words as they are stored, set the way a person writes them: one
     * space between words and a capital to start. Only the first letter
     * changes — the rest is the data as written, so `AnyMall` stays `AnyMall`
     * and nothing is translated.
     */
    fun cap(text: String?): String = text.orEmpty().trim().replace(Regex("\\s+"), " ").replaceFirstChar { it.titlecase() }

    /** Connectors that stay small inside a title — English and the Hinglish the user writes in. */
    private val SMALL = setOf(
        "a", "an", "the", "and", "or", "but", "nor", "for", "with", "from", "to", "of", "in", "on", "at", "by", "as", "vs",
        "ki", "ka", "ke", "aur", "se", "mein", "me", "ko", "par", "pe", "ya",
    )

    /**
     * A title in title case: each word's first letter capital, the small
     * connectors lower — unless one starts the title. Only first letters
     * change; `AnyMall` and `10:30pm` stay as written.
     */
    fun title(text: String?): String =
        cap(text).split(" ").mapIndexed { i, w ->
            val bare = w.lowercase().trimEnd(',', '.', ':', ';')
            when {
                w.isEmpty() || !w[0].isLetter() -> w
                i > 0 && bare in SMALL -> w.replaceFirstChar { it.lowercase() }
                else -> w.replaceFirstChar { it.titlecase() }
            }
        }.joinToString(" ")

    fun clock(at: Instant): String = at.atZone(zone).toLocalTime().let { "%02d:%02d".format(it.hour, it.minute) }

    /** Where a plan slot falls, for order only — the slot's name is what is shown. */
    private fun slotMinute(slot: String): Int = when (slot.lowercase()) {
        "breakfast" -> 9 * 60
        "lunch" -> 13 * 60
        "snack" -> 17 * 60
        "dinner" -> 20 * 60 + 30
        else -> 18 * 60
    }

    private fun ordinal(n: Int) = n.toString() + when {
        n % 100 in 11..13 -> "th"
        n % 10 == 1 -> "st"
        n % 10 == 2 -> "nd"
        n % 10 == 3 -> "rd"
        else -> "th"
    }

    fun kindOf(day: String, today: String) = when {
        day < today -> DayKind.Past
        day > today -> DayKind.Ahead
        else -> DayKind.Today
    }

    /** A schedule's repeat in words: every day, or its weekdays. */
    fun repeatOf(repeat: String, days: List<Int>): String =
        if (repeat != "weekly" || days.size == 7) "Every day"
        else days.sorted().joinToString(" · ") { listOf("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")[it] }

    /** Spends, meals and ticked tasks of one day, live from the rows. */
    fun spendsOn(s: AppState, day: String) =
        (s.tx + s.fixedTx).filter { (it.date ?: s.todayIso) == day && !it.deleted && it.id !in s.deletedRows && !it.credit }

    fun mealsOn(s: AppState, day: String) =
        s.meals.filter { (it.date ?: s.todayIso) == day && !it.deleted && it.id !in s.deletedRows }

    fun totals(s: AppState, day: String): DayTotals {
        val spends = spendsOn(s, day)
        val meals = mealsOn(s, day)
        val done = s.todos.count { it.done && it.doneOn == day }
        return DayTotals(
            spent = if (spends.isEmpty()) "— spent" else "${Fmt.rupees(-spends.sumOf { it.amt })} spent",
            protein = if (meals.isEmpty()) "— protein" else "${Fmt.grams(meals.sumOf { it.p })} protein",
            tasksDone = when (done) { 0 -> "no tasks done"; 1 -> "1 task done"; else -> "$done tasks done" },
            empty = spends.isEmpty() && meals.isEmpty() && done == 0 && s.habitLogs.none { it.date == day },
        )
    }

    /**
     * The rail for any day. Today: what happened, Now, what is ahead. A past
     * day: what happened, nothing ahead. A day ahead: its schedules at their
     * times and the tasks due that day — the plan is made on the day.
     */
    fun rail(s: AppState, day: String, now: LocalTime): Rail {
        val kind = kindOf(day, s.todayIso)
        if (kind == DayKind.Ahead) return ahead(s, day)
        val today = day
        val isToday = kind == DayKind.Today
        val nowMin = if (isToday) now.hour * 60 + now.minute else 24 * 60
        val gone = s.deletedRows.toSet()

        // What happened today, each at its own moment.
        val happened = mutableListOf<Pair<Instant?, RailRow>>()
        (s.tx + s.fixedTx).filter { (it.date ?: today) == today && !it.deleted && it.id !in gone && !it.credit }.forEach { t ->
            happened += t.at to RailRow(
                key = "tx:${t.id}", kind = RailKind.Spend, sheet = DaySheet.Money, time = "",
                title = title(t.name), figure = Fmt.rupees(-t.amt), done = true, estimate = (t.confidence ?: 1.0) < 1.0,
            )
        }
        s.meals.filter { (it.date ?: today) == today && !it.deleted && it.id !in gone }.forEach { m ->
            happened += m.at to RailRow(
                key = "meal:${m.id}", kind = RailKind.Meal, sheet = DaySheet.Diet, time = "",
                title = title(m.name), figure = Fmt.grams(m.p), done = true, estimate = (m.confidence ?: 1.0) < 1.0,
            )
        }
        // A habit you are cutting is counted through the day: the 2nd today.
        val cutting = s.habits.filter { it.direction == "break" }.map { it.name.lowercase() }.toSet()
        s.habitLogs.filter { it.date == today }
            .sortedBy { it.at ?: Instant.MAX }
            .groupBy { it.habit.lowercase() }
            .forEach { (name, logs) ->
                logs.forEachIndexed { i, h ->
                    happened += h.at to RailRow(
                        key = "habit:${h.id}", kind = RailKind.Habit, sheet = DaySheet.Habits, time = "",
                        title = title(h.habit), figure = if (name in cutting) "${ordinal(i + 1)} ${if (isToday) "today" else "that day"}" else null, done = true,
                        habit = h.habit,
                    )
                }
            }
        s.todos.filter { it.done && it.doneOn == today }.forEach { t ->
            happened += t.doneAt to RailRow(
                key = "task:${t.id}", kind = RailKind.Task, sheet = DaySheet.Work, time = "",
                title = title(t.name), sub = Tasks.projectOf(t.project, s.projects)?.name?.let(::title), done = true, taskId = t.id,
            )
        }
        // Oldest first; a row whose time is unknown waits at the end, its time a dash.
        val past = happened.sortedWith(compareBy<Pair<Instant?, RailRow>> { it.first == null }.thenBy { it.first })
            .map { (at, r) -> r.copy(time = at?.let(::clock) ?: "—") }

        if (!isToday) return Rail(past, null, emptyList(), emptyList())

        // What is still ahead, with a time or a slot.
        val ahead = mutableListOf<Pair<Int, RailRow>>()
        s.plan?.meals.orEmpty().filter { "meal:${it.slot}" !in s.planDone }.forEach { m ->
            ahead += slotMinute(m.slot) to RailRow(
                key = "plan:${m.slot}", kind = RailKind.PlanMeal, sheet = DaySheet.Diet,
                // The slot is not a clock: it goes under the title, the time column stays empty.
                time = "", sub = cap(m.slot), title = title(m.name),
                figure = Fmt.grams(m.protein), estimate = m.idea, planMeal = m,
            )
        }
        val weekday = Day.weekIndex(today)
        s.schedules.filter { it.enabled && (it.repeat != "weekly" || weekday in it.days) && it.lastRunDay != today }.forEach { sc ->
            val parts = sc.at.split(":")
            val min = (parts.getOrNull(0)?.toIntOrNull() ?: 0) * 60 + (parts.getOrNull(1)?.toIntOrNull() ?: 0)
            if (min > nowMin) ahead += min to RailRow(
                key = "schedule:${sc.id}", kind = RailKind.Schedule, sheet = DaySheet.Work, time = sc.at.take(5),
                title = title(sc.label), blurb = cap(sc.blurb), repeat = repeatOf(sc.repeat, sc.days),
            )
        }
        val timed = ahead.sortedBy { it.first }.map { it.second }

        // What is due today or late, and the plan's workout: no clock time of their own.
        val anytime = mutableListOf<RailRow>()
        // A rest day has no row: nothing to do, nothing to open (spec/home-day-rail.md § Decided against).
        s.plan?.workout?.takeIf { it.kind != "rest" && "workout" !in s.planDone && s.plan?.done != true }?.let { w ->
            anytime += RailRow(
                key = "workout", kind = RailKind.Workout, sheet = DaySheet.Activity, time = "",
                title = title(w.name), figure = w.minutes?.let { "$it min" }, estimate = w.idea, workout = w,
            )
        }
        Tasks.sortTasks(s.todos.filter { !it.done && it.due != null && it.due <= today }).forEach { t ->
            anytime += RailRow(
                key = "task:${t.id}", kind = RailKind.Task, sheet = DaySheet.Work, time = "",
                title = title(t.name), sub = Tasks.projectOf(t.project, s.projects)?.name?.let(::title) ?: "No project",
                late = if (t.due!! < today) Tasks.dueLabel(t.due, today) else null, taskId = t.id, taskSource = t.src,
            )
        }

        // One open card: the first thing ahead with a time, else the first without.
        val next = timed.firstOrNull() ?: anytime.firstOrNull()
        return Rail(
            past = past,
            next = next,
            later = timed.filter { it !== next },
            anytime = anytime.filter { it !== next },
        )
    }

    private fun ahead(s: AppState, day: String): Rail {
        val weekday = Day.weekIndex(day)
        val timed = s.schedules.filter { it.enabled && (it.repeat != "weekly" || weekday in it.days) }
            .sortedBy { it.at }
            .map { sc ->
                RailRow(
                    key = "schedule:${sc.id}", kind = RailKind.Schedule, sheet = DaySheet.Work, time = sc.at.take(5),
                    title = title(sc.label), blurb = cap(sc.blurb), repeat = repeatOf(sc.repeat, sc.days),
                )
            }
        val due = Tasks.sortTasks(s.todos.filter { !it.done && it.due == day }).map { t ->
            RailRow(
                key = "task:${t.id}", kind = RailKind.Task, sheet = DaySheet.Work, time = "",
                title = title(t.name), sub = Tasks.projectOf(t.project, s.projects)?.name?.let(::title) ?: "No project",
                taskId = t.id, taskSource = t.src,
            )
        }
        return Rail(emptyList(), null, timed, due)
    }

    /** The glance panel's six numbers, each counted from the rows now. */
    fun keyNumbers(s: AppState, protein: Double, kcal: Double): List<KeyNumber> {
        val today = s.todayIso
        val left = s.limitInfo?.left
        val pTarget = s.profile.proteinTarget
        val kTarget = s.profile.kcalTarget
        val slept = s.sleep.firstOrNull { it.second == today }?.third
        val due = s.todos.filter { !it.done && it.due != null && it.due <= today }
        val late = Tasks.lateCount(s.todos, today)
        val steps = s.activity?.steps
        return listOf(
            KeyNumber(DaySheet.Money, left?.let { if (it >= 0) Fmt.rupees(it) else Fmt.rupees(-it) + " over" } ?: "—", if (left != null && left < 0) "spent past today's limit" else "left today", labelIsLate = left != null && left < 0),
            KeyNumber(DaySheet.Diet, pTarget?.let { Fmt.grams(maxOf(0.0, it - protein)) } ?: "—", if (pTarget == null) "protein · no target" else "protein to go"),
            KeyNumber(DaySheet.Diet, kTarget?.let { Fmt.indian(maxOf(0.0, it - kcal)) } ?: "—", if (kTarget == null) "kcal · no target" else "kcal to go"),
            KeyNumber(DaySheet.Activity, slept?.let { "${it.toInt()}h ${Fmt.jsRound((it - it.toInt()) * 60)}m" } ?: "—", "slept last night"),
            KeyNumber(DaySheet.Work, "${due.size} open", if (late > 0) "$late late" else "tasks today", labelIsLate = late > 0),
            KeyNumber(DaySheet.Activity, steps?.let { Fmt.indian(it) } ?: "—", "steps"),
        )
    }
}
