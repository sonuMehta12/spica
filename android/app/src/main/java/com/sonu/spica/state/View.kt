package com.sonu.spica.state

import com.sonu.spica.data.DietGlance
import com.sonu.spica.data.HabitLine
import com.sonu.spica.data.HabitsGlance
import com.sonu.spica.data.PaisaGlance
import com.sonu.spica.lib.Fmt
import com.sonu.spica.logic.Chain
import kotlin.math.max

/** Everything derived from state once per change — the web hook's `view`. */
data class DerivedView(
    val paisa: PaisaGlance,
    val diet: DietGlance,
    val habits: HabitsGlance,
    val canLog: Boolean,
    val greetBody: String,
    val salaryLineShown: Boolean,
    val anchorDay: String,
)

/**
 * Paisa: what today still allows, then where the month is heading. The
 * arithmetic is the deck's, unchanged (`spec/done/projected-savings.md`).
 */
private fun paisa(s: AppState): PaisaGlance {
    val info = s.limitInfo
    val today = s.todayIso
    // `tx` is this month's discretionary spending: fixed costs and money in live elsewhere.
    val spentToday = s.tx.filter { (it.date ?: today) == today }.sumOf { it.amt }
    // Pace is discretionary spending only: the rest of the month's fixed costs
    // are already in `locked`.
    val pace = s.tx.sumOf { it.amt }.toDouble() / max(1, s.today)
    val daysLeft = s.monthDays - s.today + 1
    return PaisaGlance(
        limit = info?.limit,
        spentToday = spentToday,
        cameIn = s.salary,
        // The deck's month arc, as a figure: fixed costs paid plus everything spent.
        goneOut = s.fixedTx.sumOf { it.amt } + s.tx.sumOf { it.amt },
        saving = info?.let { Fmt.jsRound(it.pool - it.locked - pace * daysLeft).toInt() },
        savingsTarget = s.savingsTarget,
        // The server's total owed: this month's commitments plus the borrowings still out.
        committed = info?.locked,
        lentOut = s.pending.sumOf { it.remaining },
        lentOpen = s.pending.size,
        salaryPending = info != null && info.limit == null,
    )
}

/** Diet: today's meals summed — a macro no meal records stays unknown, never 0. */
private fun diet(s: AppState): DietGlance {
    val today = s.todayIso
    val meals = s.meals.filter { (it.date ?: today) == today }
    val carbs = meals.mapNotNull { it.c }
    val fats = meals.mapNotNull { it.f }
    val p = s.profile
    return DietGlance(
        protein = meals.sumOf { it.p },
        proteinTarget = p.proteinTarget,
        kcal = meals.sumOf { it.k.toDouble() },
        kcalTarget = p.kcalTarget,
        carbs = if (carbs.isEmpty()) null else carbs.sum(),
        carbsTarget = p.carbsTarget,
        fat = if (fats.isEmpty()) null else fats.sum(),
        meals = meals.size,
    )
}

/**
 * Habits: one line per habit you track, in Profile's order. One you are
 * cutting shows each day's count; one you are building fills its day — its
 * minutes are the report's, and a workout logged without them must not read
 * "1". A habit logged this week and stopped since keeps its line until the
 * week is out: the week happened.
 */
private fun habits(s: AppState): HabitsGlance {
    val week = Chain.weekChain(s.habitLogs, s.todayIso)
    val tracked = s.habits.map { HabitLine(it.name, counted = it.direction == "break") }
    val known = tracked.map { it.name.lowercase() }.toSet()
    val stopped = week.flatMap { d -> d.habits.map { it.habit } }
        .distinctBy { it.lowercase() }
        .filter { it.lowercase() !in known }
        .map { name -> HabitLine(name, counted = s.habitLogs.any { it.habit.equals(name, ignoreCase = true) && (it.amount ?: 1.0) != 1.0 }) }
    return HabitsGlance(tracked + stopped, week)
}

/** The web hook's `view` memo, as a pure function of state. */
fun derive(s: AppState, greetedToday: Boolean): DerivedView {
    // The thread opens on nothing you did not ask for. A time-of-day greeting
    // came back after every clear and only restated the numbers on Home
    // ("limit ₹0"), so it read as a dummy message. The agent speaks first only
    // when it has something you do not know yet: what salary day has already
    // locked. Who Spica is, the first run said before Home.
    //
    // The day salary lands, say what is already spoken for — once. Worked out
    // from the live open commitments (this month's, owed above 0) and the
    // borrowings still out; the figures are the server's, none is invented.
    val owing = s.commitments?.takeIf { it.month.take(7) == s.todayIso.take(7) }?.items
        ?.filter { !it.skipped && it.owed > 0 && !it.isBorrowing }.orEmpty()
    val borrowing = s.commitments?.items?.filter { it.isBorrowing && it.owed > 0 }.orEmpty()
    val lockedList = owing.map { it.name to it.owed } + borrowing.map { it.name to it.owed }
    val salaryLine = if (s.salaryToday && lockedList.isNotEmpty() && !greetedToday) {
        "Salary landed. ${Fmt.rupees(lockedList.sumOf { it.second })} is already committed — " +
            "${lockedList.joinToString(", ") { "${it.first} ${Fmt.rupees(it.second)}" }}. "
    } else ""

    return DerivedView(
        paisa = paisa(s),
        diet = diet(s),
        habits = habits(s),
        // Every page takes a sentence: a task said is a task added.
        canLog = true,
        greetBody = salaryLine.trim(),
        salaryLineShown = salaryLine.isNotEmpty(),
        anchorDay = s.todayIso,
    )
}
