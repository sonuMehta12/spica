package com.sonu.spica.logic

import com.sonu.spica.data.DishRow
import com.sonu.spica.data.PantryRow
import com.sonu.spica.data.PantryStatus
import com.sonu.spica.data.TaskKind
import com.sonu.spica.data.Todo
import com.sonu.spica.lib.Day
import com.sonu.spica.lib.Fmt

/**
 * The agent's line over a card the phone built — To-do, Pantry, Cash flow,
 * your dishes — where no reply exists to say it (spec/done/card-redesign.md).
 *
 * Two clauses: **what the data says**, then **what it means next**, and never
 * a figure the card already leads with. Worked out at render time from the
 * live rows, never stored: delete a row or tick a task and the sentence
 * re-reads correctly. Drawn above the card, never inside it. A server card
 * gets no note: the agent's own reply above it is the commentary.
 * Port of `agent/notes.ts`.
 */
object Notes {
    private fun n(count: Int, one: String, many: String) = "$count ${if (count == 1) one else many}"

    /** "Bread", "Bread and dahi", "Bread, dahi and 2 more". Names stay as said. */
    private fun list(names: List<String>): String = when {
        names.size <= 2 -> names.joinToString(" and ")
        names.size == 3 -> "${names[0]}, ${names[1]} and ${names[2]}"
        else -> "${names[0]}, ${names[1]} and ${names.size - 2} more"
    }

    fun todo(todos: List<Todo>, today: String): String {
        val left = todos.filter { !it.done }
        if (left.isEmpty()) return "All done — nothing left for today. Say if something for tomorrow needs remembering."
        val late = left.filter { it.due != null && it.due < today }
        val backlog = left.filter { it.kind == TaskKind.Work && it.due == null }
        val dated = Tasks.sortTasks(left.filter { it.due != null }).firstOrNull()
        // Late work outranks everything: it is the only thing here you are
        // already behind on, and saying it first is the whole point of the line.
        if (late.isNotEmpty()) {
            val worst = Tasks.sortTasks(late)[0]
            val days = worst.due?.let { Day.diffDays(it, today) } ?: 0
            val oldest = if (late.size == 1) "" else "the oldest is "
            return "${n(late.size, "task is", "tasks are")} past ${if (late.size == 1) "its" else "their"} date — " +
                "$oldest“${worst.name}”, ${n(days, "day", "days")} now. Clear that one first."
        }
        if (dated != null) {
            val rest = if (backlog.isNotEmpty()) " ${backlog.size} more sit undated — whenever there is room." else " Nothing else is on a deadline."
            return "${n(left.size, "task", "tasks")} left, “${dated.name}” first — ${Tasks.dueLabel(dated.due, today).lowercase()}.$rest"
        }
        return "${n(left.size, "task", "tasks")} left, none dated. Give the important ones a date, or this pile only grows."
    }

    fun pantry(rows: List<PantryRow>, today: String): String {
        if (rows.isEmpty()) return "Nothing in the pantry is counted yet."
        // Oldest first: the one that has sat longest is the one to use.
        val stale = rows.filter { it.status == PantryStatus.Stale }.sortedBy { it.lastIn ?: "" }
        val out = rows.filter { it.status == PantryStatus.Out }.map { it.name }
        val low = rows.filter { it.status == PantryStatus.Soon }.map { it.name }
        // "Out of" and "running low on" read right for "Eggs" and "Paneer" alike —
        // a name's own number never has to agree with a verb.
        val buy = when {
            out.isNotEmpty() && low.isNotEmpty() -> "Out of ${list(out)}, and running low on ${list(low)}."
            out.isNotEmpty() -> "Out of ${list(out)}."
            low.isNotEmpty() -> "Running low on ${list(low)}."
            else -> ""
        }
        if (stale.isNotEmpty()) {
            val first = stale[0]
            val age = first.lastIn?.let { Day.diffDays(it, today) }
            val lead = "Use the ${first.name} first${if (age != null) " — it came in ${n(age, "day", "days")} ago" else ""}."
            return if (buy.isNotEmpty()) "$lead $buy" else lead
        }
        if (buy.isNotEmpty()) return "${buy.dropLast(1)} — worth adding to the next shop."
        return "Nothing to use up or buy. Stock drops as meals are logged."
    }

    fun dishes(dishes: List<DishRow>): String {
        if (dishes.isEmpty()) return "No dishes yet — save one, or log a meal that matches one."
        val tried = dishes.count { it.tried > 0 }
        // The uncomfortable number: kept, and never cooked.
        val idle = dishes.count { it.saved && it.tried == 0 }
        if (tried == 0) {
            val kept = if (idle == dishes.size) (if (idle == 1) "saved" else "all saved") else "$idle saved"
            return "None eaten yet${if (idle > 0) " — $kept and never cooked." else "."}"
        }
        return "$tried of ${dishes.size} eaten${if (idle > 0) " — $idle saved and never cooked." else "."}"
    }

    /**
     * The month, as the server counts it: what is left once the committed costs
     * go out (`pool − locked`, `GET /paisa/summary`). Null while it loads.
     *
     * The card leads with that figure, so the line never says it again — it says
     * what the card cannot: that lent money is missing from it on purpose, or
     * that nothing more is free.
     */
    fun flow(cameIn: Int, left: Int?, locked: Int?, owed: Int): String {
        if (left == null || locked == null) return "This month's numbers are still loading."
        if (cameIn == 0 && left == 0 && locked == 0 && owed == 0) {
            return "Nothing has come in or gone out this month yet — the first payment starts the count."
        }
        // Below zero has three causes, and the line names the one that is true.
        val short = when {
            left >= 0 -> ""
            cameIn == 0 -> "Nothing has come in this month yet — until it does, what goes out shows below zero."
            left + locked < 0 -> "More has gone out than came in this month — nothing more is free to spend."
            else -> "The committed costs are more than this month has left — nothing more is free to spend."
        }
        val lent = if (owed > 0) "The ${Fmt.rupees(owed)} lent out is not counted until it comes back." else ""
        if (short.isNotEmpty() || lent.isNotEmpty()) return listOf(short, lent).filter { it.isNotEmpty() }.joinToString(" ")
        return if (locked > 0) "The committed costs are already taken out — anything spent from here comes out of what stays."
        else "Nothing committed is left to pay — anything spent from here comes out of what stays."
    }
}
