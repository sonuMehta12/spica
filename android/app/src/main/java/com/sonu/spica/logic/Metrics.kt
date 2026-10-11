package com.sonu.spica.logic

import androidx.compose.ui.graphics.Color
import com.sonu.spica.data.Meal
import com.sonu.spica.data.PendingItem
import com.sonu.spica.data.RingSpec
import com.sonu.spica.data.Todo
import com.sonu.spica.data.Tx
import com.sonu.spica.lib.Day
import com.sonu.spica.lib.Fmt
import com.sonu.spica.state.ReportMode
import com.sonu.spica.state.ReportRange
import com.sonu.spica.ui.theme.C
import kotlin.math.abs

/**
 * A glance, not an analysis. Port of `report/metrics.ts` — the numbers the
 * Reports page shows, from the same rows the deck holds.
 */
object Metrics {
    data class Span(val from: String, val to: String, val days: Int)

    enum class Good { Up, Down, None }

    data class Tile(
        val key: String,
        val label: String,
        val value: String,
        val sub: String? = null,
        /** Some figures have no previous-period equivalent — no placeholder. */
        val noDelta: Boolean = false,
        val delta: Double? = null,
        val deltaLabel: String? = null,
        val good: Good = Good.None,
    )

    data class BreakdownRow(val label: String, val valueStr: String, val share: Double, val delta: Double?, val color: Color)

    data class Chart(val key: String, val title: String, val rows: List<BreakdownRow>, val totalStr: String, val centreSub: String, val fill: Pair<Double, String>?)

    data class Report(
        val span: Span,
        val prevSpan: Span,
        val hasPrev: Boolean,
        val tiles: List<Tile>,
        val charts: List<Chart>,
        val rings: List<RingSpec>?,
        val chartsTitle: String,
        val extraTiles: List<Tile>,
        val coverage: String,
    )

    /** "1 day", "7 days" — the report can span a single day. */
    private fun days(n: Int) = "$n day${if (n == 1) "" else "s"}"

    private fun targetSub(t: Double?, show: (Double) -> String) = if (t == null) "no target set" else "target ${show(t)}"

    fun spanFor(range: ReportRange, today: String): Span {
        if (range == ReportRange.Mahina) {
            val from = Day.monthStart(today)
            return Span(from, today, Day.diffDays(from, today) + 1)
        }
        // Today compares against yesterday — `previous` needs no special case.
        val n = when (range) {
            ReportRange.Aaj -> 1
            ReportRange.Din7 -> 7
            else -> 14
        }
        return Span(Day.addDays(today, -(n - 1)), today, n)
    }

    /** The span before this one, clamped to the start of its month. */
    private fun previous(s: Span): Span {
        val to = Day.addDays(s.from, -1)
        val from = Day.maxDay(Day.monthStart(s.from), Day.addDays(to, -(s.days - 1)))
        return Span(from, to, maxOf(0, Day.diffDays(from, to) + 1))
    }

    private fun inSpan(iso: String, s: Span) = iso >= s.from && iso <= s.to

    private fun pct(cur: Double, prev: Double): Double? = if (prev == 0.0) null else (cur - prev) / prev

    private fun signed(n: Long, unit: String = "") = "${if (n > 0) "+" else if (n < 0) "−" else ""}${abs(n)}$unit"

    private fun pctLabel(d: Double?) = d?.let { "${if (it > 0) "+" else if (it < 0) "−" else ""}${abs(Fmt.jsRound(it * 100))}%" }

    // The three mode hues at base then soft: equal lightness, so no category shouts.
    // Red is kept for over and amber for estimates, so neither appears here.
    private val CAT_COLORS = listOf(C.paisa, C.work, C.diet, C.paisaSoft, C.workSoft, C.dietSoft, C.grey)

    private class PaisaRoll(tx: List<Tx>, s: Span, today: String) {
        val rows = tx.filter { inSpan(it.date ?: today, s) }
        val byDay = LinkedHashMap<String, Int>().also { m -> rows.forEach { m[it.date ?: today] = (m[it.date ?: today] ?: 0) + it.amt } }
        val total = rows.sumOf { it.amt }
        val activeDays = byDay.size
        val txCount = rows.size
    }

    private fun paisa(tx: List<Tx>, span: Span, limit: Int, today: String, salary: Int, pending: List<PendingItem>, borrowed: List<PendingItem>): Report {
        val prevSpan = previous(span)
        val cur = PaisaRoll(tx, span, today)
        val prev = PaisaRoll(tx, prevSpan, today)
        val hasPrev = prevSpan.days > 0 && prev.txCount > 0

        // How many payments landed while that day was still inside the limit.
        fun withinLimit(rows: List<Tx>): Int {
            val running = HashMap<String, Int>()
            var ok = 0
            for (t in rows) {
                val d = t.date ?: today
                val before = running[d] ?: 0
                if (before + t.amt <= limit) ok += 1
                running[d] = before + t.amt
            }
            return ok
        }
        val withinCur = withinLimit(cur.rows)
        val withinPrev = withinLimit(prev.rows)
        val rateCur = if (cur.txCount > 0) withinCur.toDouble() / cur.txCount else 0.0
        val ratePrev = if (prev.txCount > 0) withinPrev.toDouble() / prev.txCount else 0.0
        val avgCur = cur.total.toDouble() / span.days
        val avgPrev = if (prevSpan.days > 0) prev.total.toDouble() / prevSpan.days else 0.0

        val out = pending.sumOf { it.remaining }
        val owe = borrowed.sumOf { it.remaining }
        val tiles = buildList {
            add(
                Tile(
                    "total", if (span.days == 1) "Spent today" else "Total spend", Fmt.rupees(cur.total),
                    sub = if (hasPrev) "${Fmt.rupees(prev.total)} before" else null,
                    delta = if (hasPrev) pct(cur.total.toDouble(), prev.total.toDouble()) else null,
                    deltaLabel = if (hasPrev) pctLabel(pct(cur.total.toDouble(), prev.total.toDouble())) else null,
                    good = Good.Down,
                ),
            )
            // Over a single day this is the headline again — noise, not context.
            if (span.days != 1) {
                add(
                    Tile(
                        "perday", "Daily average", Fmt.rupees(avgCur),
                        sub = if (hasPrev) "${Fmt.rupees(avgPrev)} before" else null,
                        delta = if (hasPrev) pct(avgCur, avgPrev) else null,
                        deltaLabel = if (hasPrev) pctLabel(pct(avgCur, avgPrev)) else null,
                        good = Good.Down,
                    ),
                )
            }
            add(
                Tile(
                    // Payments, not days: `31/38` read as "31 of 38 days".
                    "within", "Payments within limit", "$withinCur of ${cur.txCount}",
                    sub = "limit ${Fmt.rupees(limit)}",
                    delta = if (hasPrev) rateCur - ratePrev else null,
                    deltaLabel = if (hasPrev) "from $withinPrev/${prev.txCount}" else null,
                    good = Good.Up,
                ),
            )
            add(
                Tile(
                    "udhaar", "Udhaar", "out ${Fmt.rupees(out)}",
                    sub = if (owe > 0) "owe ${Fmt.rupees(owe)}"
                    else if (pending.isNotEmpty()) "${pending.size} lending${if (pending.size > 1) "s" else ""} open"
                    else "nothing out, nothing owed",
                ),
            )
        }

        val catCur = LinkedHashMap<String, Int>()
        val catPrev = HashMap<String, Int>()
        cur.rows.forEach { catCur[it.cat] = (catCur[it.cat] ?: 0) + it.amt }
        prev.rows.forEach { catPrev[it.cat] = (catPrev[it.cat] ?: 0) + it.amt }
        val rows = catCur.entries.sortedByDescending { it.value }.mapIndexed { i, (label, v) ->
            BreakdownRow(
                label, Fmt.rupees(v), if (cur.total > 0) v.toDouble() / cur.total else 0.0,
                if (hasPrev) pct(v.toDouble(), (catPrev[label] ?: 0).toDouble()) else null,
                CAT_COLORS[i % CAT_COLORS.size],
            )
        }
        return Report(
            span, prevSpan, hasPrev, tiles,
            listOf(
                Chart(
                    "cat", "Where it went", rows, Fmt.rupees(cur.total), "total",
                    (if (salary != 0) cur.total.toDouble() / salary else 0.0) to Fmt.rupees(salary),
                ),
            ),
            null, "Where it went", emptyList(), "${cur.activeDays} of ${span.days} days logged",
        )
    }

    /** Calories cut both ways — over the band is as much a miss as under it. */
    private const val KCAL_SLACK = 200

    private class DietRoll(meals: List<Meal>, s: Span, today: String, proteinTarget: Double?) {
        val rows = meals.filter { inSpan(it.date ?: today, s) }
        val p = LinkedHashMap<String, Double>()
        val k = LinkedHashMap<String, Double>()

        init {
            rows.forEach {
                val d = it.date ?: today
                p[d] = (p[d] ?: 0.0) + it.p
                k[d] = (k[d] ?: 0.0) + it.k
            }
        }

        val loggedDays = p.size
        val avgP = if (p.isNotEmpty()) p.values.sum() / p.size else 0.0
        val avgK = if (p.isNotEmpty()) p.keys.sumOf { k[it] ?: 0.0 } / p.size else 0.0
        val hitDays = if (proteinTarget == null) 0 else p.values.count { it >= proteinTarget }
    }

    private fun diet(meals: List<Meal>, span: Span, today: String, proteinT: Double?, kcalT: Int?, sleepT: Int?, stepT: Int?): Report {
        val prevSpan = previous(span)
        val cur = DietRoll(meals, span, today, proteinT)
        val prev = DietRoll(meals, prevSpan, today, proteinT)
        val hasPrev = prevSpan.days > 0 && prev.loggedDays > 0
        val rateCur = if (cur.loggedDays > 0) cur.hitDays.toDouble() / cur.loggedDays else 0.0
        val ratePrev = if (prev.loggedDays > 0) prev.hitDays.toDouble() / prev.loggedDays else 0.0

        val proteinInBand = cur.p.values.count { it >= 90 }
        val kcalInBand = if (kcalT == null) 0 else cur.k.values.count { abs(it - kcalT) <= KCAL_SLACK }

        // Sleep and steps have no rows to draw yet: empty is the honest value.
        val tiles = listOf(
            Tile(
                "protein", if (span.days == 1) "Protein today" else "Protein a day", "${Fmt.jsRound(cur.avgP)}g",
                sub = if (hasPrev) "${Fmt.jsRound(prev.avgP)}g before" else targetSub(proteinT) { "${Fmt.num(it)}g" },
                delta = if (hasPrev) pct(cur.avgP, prev.avgP) else null,
                deltaLabel = if (hasPrev) signed(Fmt.jsRound(cur.avgP - prev.avgP), "g") else null,
                good = Good.Up,
            ),
            Tile(
                "kcal", if (span.days == 1) "Calories today" else "Calories a day", Fmt.indian(Fmt.jsRound(cur.avgK)),
                sub = if (hasPrev) "${Fmt.indian(Fmt.jsRound(prev.avgK))} before" else targetSub(kcalT?.toDouble()) { Fmt.indian(it) },
                delta = if (hasPrev) pct(cur.avgK, prev.avgK) else null,
                deltaLabel = if (hasPrev) pctLabel(pct(cur.avgK, prev.avgK)) else null,
            ),
            Tile("sleep", if (span.days == 1) "Sleep" else "Sleep a day", "—", sub = targetSub(sleepT?.toDouble()) { Fmt.duration(it) }, good = Good.Up),
            Tile("steps", if (span.days == 1) "Steps" else "Steps a day", "—", sub = targetSub(stepT?.toDouble()) { Fmt.indian(it) }, good = Good.Up),
        )
        val extra = listOf(
            Tile(
                "hit", "Target hit", "${cur.hitDays}/${cur.loggedDays}", sub = targetSub(proteinT) { "${Fmt.num(it)}g" },
                delta = if (hasPrev) rateCur - ratePrev else null,
                deltaLabel = if (hasPrev) "from ${prev.hitDays}/${prev.loggedDays}" else null, good = Good.Up,
            ),
            Tile(
                "logged", "Days logged", "${cur.loggedDays}/${span.days}",
                sub = if (hasPrev) "${prev.loggedDays}/${prevSpan.days} before" else null,
                delta = if (hasPrev) pct(cur.loggedDays.toDouble(), prev.loggedDays.toDouble()) else null,
                deltaLabel = if (hasPrev) signed((cur.loggedDays - prev.loggedDays).toLong(), " days") else null, good = Good.Up,
            ),
        )
        return Report(
            span, prevSpan, hasPrev, tiles, emptyList(),
            listOf(
                RingSpec("kcal", "Calories", "$kcalInBand", days(cur.loggedDays), if (cur.loggedDays > 0) kcalInBand.toDouble() / cur.loggedDays else 0.0, C.diet),
                RingSpec("protein", "Protein", "$proteinInBand", days(cur.loggedDays), if (cur.loggedDays > 0) proteinInBand.toDouble() / cur.loggedDays else 0.0, C.brand),
            ),
            "How often in band", extra, "${cur.loggedDays} of ${days(span.days)} logged",
        )
    }

    /** To-do has no trend and no distribution — a task is done or it is not. Every task counts, money and food ones too. */
    private fun kaam(todos: List<Todo>, span: Span, today: String, projectCount: Int): Report {
        val open = todos.filter { !it.done }
        val late = open.filter { it.due != null && it.due < today }
        val backlog = open.filter { it.due == null }
        val doneIn = todos.filter { it.done && it.doneOn != null && inSpan(it.doneOn, span) }
        return Report(
            span, previous(span), false,
            listOf(
                Tile("open", "Open", "${open.size}", noDelta = true),
                // The only tile the range moves — say so, or the dropdown looks dead.
                Tile("done", "Done", "${doneIn.size}", sub = if (span.days == 1) "today" else "in ${days(span.days)}", noDelta = true),
                Tile("late", "Past date", "${late.size}", noDelta = true),
                Tile("backlog", "No date", "${backlog.size}", noDelta = true),
            ),
            emptyList(), null, "Project", emptyList(), "${todos.size} tasks, $projectCount projects",
        )
    }

    fun build(
        mode: ReportMode, range: ReportRange, tx: List<Tx>, meals: List<Meal>, limit: Int, todos: List<Todo>,
        today: String, salary: Int, pending: List<PendingItem>, borrowed: List<PendingItem>,
        proteinT: Double?, kcalT: Int?, sleepT: Int?, stepT: Int?, projectCount: Int,
    ): Report {
        val span = spanFor(range, today)
        return when (mode) {
            ReportMode.Kaam -> kaam(todos, span, today, projectCount)
            ReportMode.Paisa -> paisa(tx, span, limit, today, salary, pending, borrowed)
            ReportMode.Diet -> diet(meals, span, today, proteinT, kcalT, sleepT, stepT)
        }
    }
}
