package com.sonu.spica.logic

import com.sonu.spica.data.ChainDay
import com.sonu.spica.data.HabitLogRow
import com.sonu.spica.data.HabitMark
import com.sonu.spica.lib.Day

/** Port of `frontend/src/diet/workouts.ts`. */
object Chain {
    /** Monday first — the letters read in the order people say them. */
    val DAY_LETTERS = listOf("M", "T", "W", "T", "F", "S", "S")

    /**
     * The calendar week containing `anchor`, Monday to Sunday — not a rolling
     * seven days, which would scramble the letters. Bucketed by ISO date: a
     * week starting in the previous month is an ordinary week.
     */
    fun weekChain(logs: List<HabitLogRow>, anchor: String): List<ChainDay> {
        val monday = Day.addDays(anchor, -Day.weekIndex(anchor))
        val byDay = LinkedHashMap<String, MutableList<HabitMark>>()
        for (l in logs) {
            val list = byDay.getOrPut(l.date) { mutableListOf() }
            val i = list.indexOfFirst { it.habit == l.habit }
            // One coin per habit whatever the count: two cigarettes is one
            // cigarette icon reading 2. A log with no amount counts as one.
            if (i >= 0) list[i] = list[i].copy(count = list[i].count + (l.amount ?: 1.0))
            else list += HabitMark(l.habit, l.amount ?: 1.0)
        }
        return DAY_LETTERS.mapIndexed { i, letter ->
            val date = Day.addDays(monday, i)
            val habits = byDay[date].orEmpty()
            ChainDay(
                day = Day.dayOfMonth(date),
                date = date,
                letter = letter,
                habits = habits,
                done = habits.isNotEmpty(),
                isToday = date == anchor,
                future = date > anchor,
            )
        }
    }

    /** Days with at least one habit logged. Plain count, never a streak. */
    fun weekCount(chain: List<ChainDay>) = chain.count { it.done }
}
