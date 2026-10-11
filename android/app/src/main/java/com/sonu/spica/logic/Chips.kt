package com.sonu.spica.logic

import com.sonu.spica.data.Meal
import com.sonu.spica.data.Tx
import com.sonu.spica.lib.Day
import com.sonu.spica.lib.Fmt

/**
 * The greeting's quick chips: your own most repeated entries, worked out from
 * the rows at render time and never stored. `THEME.md`.
 */
object Chips {
    /** How far back a habit is looked for. */
    const val WINDOW_DAYS = 30

    /** One chai is not a habit. */
    const val MIN_TIMES = 2

    const val TOP = 3

    /** A chip: what it shows, and the sentence a tap sends. */
    data class Pick(val id: String, val name: String, val tag: String, val send: String)

    private data class Seen(val key: String, val name: String, val times: Int, val last: String, val amount: Int)

    /**
     * Groups by the name as said, case and spacing aside. The newest row names
     * the chip; the most frequent amount is its usual one, ties to the newest.
     * Ranked by how often, then how recently.
     */
    private fun <R> rank(rows: List<R>, today: String, name: (R) -> String, day: (R) -> String, amount: (R) -> Int): List<Seen> {
        val from = Day.addDays(today, -(WINDOW_DAYS - 1))
        return rows
            .filter { day(it) in from..today && name(it).isNotBlank() }
            .groupBy { name(it).trim().lowercase().replace(Regex("\\s+"), " ") }
            .filter { it.value.size >= MIN_TIMES }
            .map { (key, group) ->
                val newestFirst = group.sortedByDescending(day)
                val usual = newestFirst.groupingBy(amount).eachCount().let { counts ->
                    val top = counts.values.max()
                    newestFirst.map(amount).first { counts[it] == top }
                }
                Seen(key, name(newestFirst.first()).trim(), group.size, day(newestFirst.first()), usual)
            }
            .sortedWith(compareByDescending<Seen> { it.times }.thenByDescending { it.last })
            .take(TOP)
    }

    /** Paisa: "Chai ₹20". Money coming in is not a spend. */
    fun spends(tx: List<Tx>, today: String): List<Pick> =
        rank(tx.filter { !it.credit && !it.deleted && !it.failed }, today, { it.name }, { it.date ?: today }, { it.amt })
            .map { Pick("spend:${it.key}", it.name, Fmt.rupees(it.amount), "${it.name} ${Fmt.rupees(it.amount)}") }

    /** Diet: the dish, sent with the slot the clock says — "Lunch: dal chawal". */
    fun meals(meals: List<Meal>, today: String, slot: String = Day.mealTypeNow()): List<Pick> =
        rank(meals.filter { !it.deleted && !it.failed }, today, { it.name }, { it.date ?: today }, { 0 })
            .map { Pick("meal:${it.key}", it.name, "", "$slot: ${it.name}") }
}
