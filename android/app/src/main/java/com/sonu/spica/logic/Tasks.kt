package com.sonu.spica.logic

import androidx.compose.ui.graphics.Color
import com.sonu.spica.data.Project
import com.sonu.spica.data.ProjectStat
import com.sonu.spica.data.Range
import com.sonu.spica.data.TaskKind
import com.sonu.spica.data.Todo
import com.sonu.spica.lib.Day
import com.sonu.spica.ui.theme.C

/** Port of `frontend/src/work/tasks.ts`. */
object Tasks {
    /** Sorts after every real date, so an undated task lands at the bottom. */
    private const val NO_DATE = "9999-12-31"

    fun projectOf(id: String?, projects: List<Project>): Project? = id?.let { i -> projects.firstOrNull { it.id == i } }

    /** The window's first and last ISO day: the calendar week or month. */
    private fun bounds(range: Range, today: String): Pair<String, String> {
        if (range == Range.Din30) {
            val last = Day.monthDays(today)
            return "${today.take(7)}-01" to "${today.take(7)}-${last.toString().padStart(2, '0')}"
        }
        val monday = Day.addDays(today, -Day.weekIndex(today))
        return monday to Day.addDays(monday, 6)
    }

    /**
     * Work windows look FORWARD — whole week, whole month — where paisa and
     * diet look back. A task due tomorrow belongs to this week today.
     */
    private fun inWindow(task: Todo, range: Range, today: String): Boolean {
        if (range == Range.Sab) return true
        val (start, end) = bounds(range, today)
        fun within(d: String?) = d != null && d >= start && d <= end
        // Finished: it belongs to the window it was finished in, or was due in.
        if (task.done) return within(task.doneOn) || within(task.due)
        // Still open: undated, due in the window, or already late. Hiding the
        // undated ones left the card at 0/0 while seven tasks sat open.
        return task.due == null || task.due <= end
    }

    /** `2 days late` · `Today` · `Tomorrow` · `4 days`. */
    fun dueLabel(due: String?, today: String): String {
        if (due == null) return "no date"
        val d = Day.diffDays(today, due)
        return when {
            d == 0 -> "Today"
            d == 1 -> "Tomorrow"
            d < 0 -> "${-d} ${if (d == -1) "day" else "days"} late"
            else -> "$d days"
        }
    }

    /** A finished task reports that it is finished, not the date it met. */
    fun statusLabel(task: Todo, today: String): String = when {
        task.done -> "done"
        task.due == null -> ""
        else -> dueLabel(task.due, today)
    }

    fun dueTone(task: Todo, today: String): Color {
        if (task.done || task.due == null) return C.faint
        val d = Day.diffDays(today, task.due)
        return when {
            d < 0 -> C.red
            d == 0 -> C.ink
            else -> C.muted
        }
    }

    /**
     * Overdue first, then by date, then by priority within the same day.
     * Blind to `done` — a task you tick keeps its place under your finger.
     */
    fun sortTasks(list: List<Todo>): List<Todo> = list.sortedWith(
        compareBy<Todo> { it.due ?: NO_DATE }.thenBy { it.priority ?: 9 },
    )

    /** A To-do group: when its tasks are due, the colour of its label, and the tasks in order. */
    data class WhenGroup(val label: String, val color: Color, val tasks: List<Todo>)

    /**
     * Tasks by when they are due — Late, Today, This week, Later — sorted
     * inside each, empty groups dropped. Undated is later, not never: it is
     * still on the plate. The To-do card and Home's To-do both read this.
     */
    fun byWhen(tasks: List<Todo>, today: String): List<WhenGroup> {
        val sunday = Day.addDays(today, 6 - Day.weekIndex(today))
        fun whenOf(t: Todo) = when {
            t.due == null -> "Later"
            t.due < today -> "Late"
            t.due == today -> "Today"
            t.due <= sunday -> "This week"
            else -> "Later"
        }
        return listOf("Late" to C.red, "Today" to C.ink, "This week" to C.muted, "Later" to C.faint)
            .map { (label, tone) -> WhenGroup(label, tone, sortTasks(tasks.filter { whenOf(it) == label })) }
            .filter { it.tasks.isNotEmpty() }
    }

    /**
     * What to do now, at most `n`: late first, then due today, then a P1 or
     * P2, then the rest of the week, then everything else. Blind to `done`,
     * like `sortTasks`: a task ticked today keeps its place, struck, so a tick
     * never pulls the next one up under your finger.
     */
    fun focus(todos: List<Todo>, today: String, n: Int = 3): List<Todo> {
        val sunday = Day.addDays(today, 6 - Day.weekIndex(today))
        fun rank(t: Todo) = when {
            t.due != null && t.due < today -> 0
            t.due == today -> 1
            (t.priority ?: 9) <= 2 -> 2
            t.due != null && t.due <= sunday -> 3
            else -> 4
        }
        return onList(todos, today)
            .sortedWith(compareBy<Todo>({ rank(it) }, { it.due ?: NO_DATE }, { it.priority ?: 9 }))
            .take(n)
    }

    /**
     * What a to-do list shows: everything open, and anything ticked today —
     * it stays where it was, struck, so a tick never makes the list jump.
     */
    fun onList(todos: List<Todo>, today: String) = todos.filter { !it.done || it.doneOn == today }

    /** One bar per project — bars share a baseline, arcs did not. */
    fun projectStats(todos: List<Todo>, range: Range, projects: List<Project>, today: String): List<ProjectStat> =
        projects.map { proj ->
            val rows = todos.filter { it.project == proj.id && inWindow(it, range, today) }
            ProjectStat(
                id = proj.id,
                name = proj.name,
                color = C.hex(proj.color),
                done = rows.count { it.done },
                total = rows.size,
                late = rows.count { !it.done && it.due != null && it.due < today },
            )
        }

    data class TaskGroup(val key: String, val label: String, val color: Color, val tasks: List<Todo>)

    /**
     * Tasks gathered into blocks rather than one flat date-sorted run: every
     * project's work in one block, chores after. Dates still order rows
     * within a group, so nothing late gets buried.
     */
    fun groupTasks(todos: List<Todo>, scope: String, projects: List<Project>): List<TaskGroup> {
        val groups = projects.map { proj ->
            TaskGroup(
                proj.id, proj.name, C.hex(proj.color),
                sortTasks(todos.filter { it.project == proj.id && (scope == "work" || it.kind == TaskKind.Work) }),
            ).copy()
        }.toMutableList()
        val loose = todos.filter { it.kind == TaskKind.Work && projectOf(it.project, projects) == null }
        if (loose.isNotEmpty()) groups += TaskGroup("work", "Work", C.grey, sortTasks(loose))
        if (scope == "all") {
            groups += TaskGroup("paisa", "Money", C.border, sortTasks(todos.filter { it.kind == TaskKind.Paisa }))
            groups += TaskGroup("diet", "Diet", C.border, sortTasks(todos.filter { it.kind == TaskKind.Diet }))
        }
        return groups.filter { it.tasks.isNotEmpty() }
    }

    fun openTasks(todos: List<Todo>) = todos.filter { !it.done }

    fun lateCount(todos: List<Todo>, today: String) = todos.count { !it.done && it.due != null && it.due < today }
}
