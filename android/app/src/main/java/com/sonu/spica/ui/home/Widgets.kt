package com.sonu.spica.ui.home

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.TextUnit
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.sonu.spica.data.ActivityDay
import com.sonu.spica.data.ChainDay
import com.sonu.spica.data.DietGlance
import com.sonu.spica.data.HabitLine
import com.sonu.spica.data.HabitsGlance
import com.sonu.spica.data.HealthAccess
import com.sonu.spica.data.PaisaGlance
import com.sonu.spica.data.PlanMeal
import com.sonu.spica.data.PlanWorkout
import com.sonu.spica.data.Project
import com.sonu.spica.data.Todo
import com.sonu.spica.data.TodayPlan
import coil3.compose.AsyncImage
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.layout.ContentScale
import com.sonu.spica.lib.Day
import com.sonu.spica.lib.Fmt
import com.sonu.spica.logic.Tasks
import com.sonu.spica.ui.chat.Fig
import com.sonu.spica.ui.common.ActionPill
import com.sonu.spica.ui.common.Dot
import com.sonu.spica.ui.common.PillKind
import com.sonu.spica.ui.common.Glyph
import com.sonu.spica.ui.common.HabitIcon
import com.sonu.spica.ui.common.MoveReminder
import com.sonu.spica.ui.common.Ph
import com.sonu.spica.ui.common.PhBold
import com.sonu.spica.ui.common.tap
import com.sonu.spica.ui.theme.C
import com.sonu.spica.ui.theme.S
import com.sonu.spica.ui.theme.T
import androidx.compose.foundation.layout.IntrinsicSize
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.ui.graphics.vector.ImageVector

/*
 * Home's widgets. Each answers one question
 * over one window, from live rows, in as few words as it can. Figures in ink;
 * a mode's colour only on its data — a bar, a filled day — and red means over
 * a limit, nothing else.
 */

/**
 * Home's card: larger than the thread's (14 small, 18 the thread's, 24 Home's,
 * full for pills), white, floating on the tinted ground with a soft shadow —
 * a glance is read as objects, not as a page of text.
 */
private val CardShape = RoundedCornerShape(24.dp)

/** Who a widget is: its icon, drawn in its mode's ink on its mode's tint — the receipts' coin, as a badge. */
class Badge(val icon: ImageVector, val ink: Color, val tint: Color)

private val TODAY = Badge(Ph.checkSquare, C.workInk, C.workTint)
private val MONEY = Badge(Ph.wallet, C.paisaInk, C.paisaTint)
private val DIET = Badge(Ph.bowlFood, C.dietInk, C.dietTint)
private val MEALS = Badge(Ph.cookingPot, C.dietInk, C.dietTint)
private val ACTIVITY = Badge(Ph.heartbeat, C.dietInk, C.dietTint)
private val WORKOUT = Badge(Ph.barbell, C.dietInk, C.dietTint)
private val HABITS = Badge(Ph.calendarBlank, C.dietInk, C.dietTint)

/** A widget's frame: its badge, name and window on top. With `onOpen`, the card opens its report. */
@Composable
private fun Widget(
    title: String,
    window: String?,
    onOpen: (() -> Unit)?,
    aside: (@Composable () -> Unit)? = null,
    badge: Badge? = null,
    content: @Composable ColumnScope.() -> Unit,
) {
    Column(
        Modifier
            .fillMaxWidth()
            .then(S.widget(CardShape))
            .clip(CardShape)
            .background(C.white)
            .then(if (onOpen != null) Modifier.tap(onClick = onOpen) else Modifier)
            .padding(start = 18.dp, end = 18.dp, top = 16.dp, bottom = 18.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            if (badge != null) {
                Box(Modifier.size(32.dp).background(badge.tint, CircleShape), contentAlignment = Alignment.Center) {
                    Glyph(badge.icon, 17.dp, badge.ink)
                }
            }
            Text(
                title,
                style = T.sans.copy(fontSize = 16.sp, lineHeight = 20.sp, fontWeight = FontWeight.SemiBold),
                modifier = Modifier.weight(1f).padding(start = if (badge != null) 10.dp else 0.dp),
            )
            when {
                aside != null -> aside()
                window != null -> Chip(window)
            }
            if (onOpen != null) Glyph(PhBold.caretRight, 11.dp, C.grey, Modifier.padding(start = 8.dp))
        }
        content()
    }
}

/** A window or a count, set apart from the title: small words on the surface tint, in a pill. */
@Composable
private fun Chip(text: String, color: Color = C.muted, modifier: Modifier = Modifier, bg: Color = C.surface) =
    Text(
        text,
        style = T.sans.copy(fontSize = 11.5.sp, lineHeight = 14.sp, fontWeight = FontWeight.Medium, color = color),
        modifier = modifier.background(bg, RoundedCornerShape(50)).padding(horizontal = 9.dp, vertical = 4.dp),
    )

/** The widget's answer: one figure and the few words that say what it is. */
@Composable
private fun Lead(figure: String, word: String, modifier: Modifier = Modifier, color: Color = C.ink, size: TextUnit = 34.sp) {
    Row(modifier, verticalAlignment = Alignment.Bottom, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Fig(figure, size, color)
        Text(word, style = T.sans.copy(fontSize = 13.5.sp, color = C.muted), modifier = Modifier.padding(bottom = 6.dp))
    }
}

/** How far along: the mode's colour on a pale track, rounded at both ends, red when over. */
@Composable
private fun Meter(fraction: Float, color: Color, modifier: Modifier = Modifier, height: androidx.compose.ui.unit.Dp = 8.dp, track: Color = C.lineSoft) {
    val shape = RoundedCornerShape(50)
    Box(modifier.fillMaxWidth().height(height).clip(shape).background(track)) {
        val f = fraction.coerceIn(0f, 1f)
        if (f > 0f) Box(Modifier.fillMaxWidth(f).height(height).clip(shape).background(color))
    }
}

/**
 * A ring for one quantity against its target — protein, today. Not for
 * comparing things (arc length cannot be compared; the reason Work's ring
 * became bars), only for "how far round am I".
 */
@Composable
private fun Ring(fraction: Float, color: Color, size: androidx.compose.ui.unit.Dp, stroke: androidx.compose.ui.unit.Dp, content: @Composable () -> Unit) {
    Box(Modifier.size(size), contentAlignment = Alignment.Center) {
        androidx.compose.foundation.Canvas(Modifier.size(size)) {
            val w = stroke.toPx()
            val arc = androidx.compose.ui.geometry.Size(this.size.width - w, this.size.height - w)
            val at = androidx.compose.ui.geometry.Offset(w / 2, w / 2)
            val cap = androidx.compose.ui.graphics.drawscope.Stroke(width = w, cap = androidx.compose.ui.graphics.StrokeCap.Round)
            drawArc(C.lineSoft, 0f, 360f, false, at, arc, style = cap)
            val f = fraction.coerceIn(0f, 1f)
            if (f > 0f) drawArc(color, -90f, 360f * f, false, at, arc, style = cap)
        }
        content()
    }
}

@Composable
internal fun Small(text: String, modifier: Modifier = Modifier, color: Color = C.faint) =
    Text(text, style = T.sans.copy(fontSize = 12.sp, lineHeight = 16.sp, color = color), modifier = modifier)

/** A word that does something: the brand's, as every link is. */
@Composable
internal fun Link(text: String, onClick: () -> Unit, modifier: Modifier = Modifier) =
    Text(
        text,
        style = T.sans.copy(fontSize = 12.5.sp, lineHeight = 16.sp, fontWeight = FontWeight.Medium, color = C.brand),
        modifier = modifier.clip(RoundedCornerShape(4.dp)).tap(onClick = onClick),
    )

/** One figure as a tile: its name small above, the figure under it, on the surface tint. */
@Composable
private fun Stat(label: String, value: String, modifier: Modifier, red: Boolean = false, link: Pair<String, () -> Unit>? = null, onClick: (() -> Unit)? = null) {
    val tile = RoundedCornerShape(16.dp)
    Column(modifier.fillMaxHeight().clip(tile).background(C.surface, tile).then(if (onClick != null) Modifier.tap(onClick = onClick) else Modifier).padding(horizontal = 12.dp, vertical = 10.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(3.dp)) {
            Text(label, style = T.sans.copy(fontSize = 11.5.sp, lineHeight = 14.sp, color = C.faint), maxLines = 2, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f, fill = false))
            if (onClick != null) Glyph(PhBold.caretRight, 9.dp, C.faint)
        }
        Fig(value, 16.sp, if (red) C.red else C.ink, modifier = Modifier.padding(top = 3.dp))
        if (link != null) Link(link.first, link.second, Modifier.padding(top = 2.dp))
    }
}

@Composable
private fun StatRow(content: @Composable RowScope.() -> Unit) =
    Row(
        Modifier.fillMaxWidth().padding(top = 14.dp).height(IntrinsicSize.Min),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        content = content,
    )

/** Whole grams: a glance does not need the decimal. */
internal fun g(n: Double) = "${Fmt.jsRound(n)} g"

/* ─── Today ───────────────────────────────────────────────────────────── */

/**
 * What to do now: three tasks at most, the most pressing first — late, due
 * today, P1 — so there is one thing to start on, not a list to read. Each task
 * is a tile, so the three read as three things to pick up. A tick toggles in
 * place and the tile stays, struck; the whole list is a tap into Chat.
 */
@Composable
fun TodayWidget(todos: List<Todo>, projects: List<Project>, today: String, onToggle: (String) -> Unit, onOpen: () -> Unit, onAll: () -> Unit) {
    val focus = Tasks.focus(todos, today)
    val open = Tasks.openTasks(todos).size
    val late = Tasks.lateCount(todos, today)
    Widget("Today", null, onOpen, badge = TODAY, aside = {
        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            if (late > 0) Chip("$late late", C.red)
            Chip("$open open")
        }
    }) {
        if (focus.isEmpty()) {
            Small("Nothing on your list. Say what needs doing.", Modifier.padding(top = 12.dp), C.muted)
            return@Widget
        }
        Column(Modifier.padding(top = 14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            focus.forEachIndexed { i, t -> TaskRow(t, projects, today, onToggle, next = i == 0 && !t.done) }
        }
        if (open > focus.count { !it.done }) {
            Row(Modifier.fillMaxWidth().padding(top = 12.dp), horizontalArrangement = Arrangement.Center) {
                Link("See all $open tasks", onAll)
            }
        }
    }
}

/**
 * A task at a glance, as a tile: its checkbox, one line of its name, and one
 * of small print — the project, how late or which day, P1 or P2. The whole
 * sentence is in the To-do card. Filled in the project's colour once done.
 */
@Composable
internal fun TaskRow(task: Todo, projects: List<Project>, today: String, onToggle: (String) -> Unit, next: Boolean = false) {
    val proj = Tasks.projectOf(task.project, projects)
    val tint = proj?.let { C.hex(it.color) } ?: C.work
    val late = !task.done && task.due != null && task.due < today
    val due = when {
        task.done || task.due == null -> null
        task.due == today -> "Today"
        late -> Day.diffDays(task.due!!, today).let { "$it ${if (it == 1) "day" else "days"} late" }
        else -> Day.cardDay(task.due!!)
    }
    val priority = task.priority?.takeIf { it <= 2 && !task.done }?.let { "P$it" }
    val tile = RoundedCornerShape(16.dp)
    // The first is the one to start on: it alone sits on the work tint.
    Column(Modifier.fillMaxWidth().clip(tile).background(if (next) C.workTint else C.surface).tap { onToggle(task.id) }.padding(horizontal = 12.dp, vertical = 11.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Box(
                Modifier.size(22.dp).clip(CircleShape).background(if (task.done) tint else C.white).border(1.6.dp, if (task.done) tint else C.border, CircleShape),
                contentAlignment = Alignment.Center,
            ) { if (task.done) Glyph(PhBold.check, 12.dp, C.white) }
            Column(Modifier.weight(1f)) {
                Text(
                    task.name,
                    style = T.sans.copy(
                        fontSize = 15.sp, lineHeight = 19.sp, fontWeight = FontWeight.Medium,
                        color = if (task.done) C.faint else C.ink,
                        textDecoration = if (task.done) TextDecoration.LineThrough else null,
                    ),
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Row(Modifier.padding(top = 3.dp), verticalAlignment = Alignment.CenterVertically) {
                    if (task.projectGuessed) Dot()
                    // The project's own colour as a small mark: the row keys back to it without a legend.
                    if (proj != null && !task.projectGuessed) Box(Modifier.padding(end = 6.dp).size(7.dp).background(tint, CircleShape))
                    Text(
                        buildAnnotatedString {
                            append(proj?.name ?: "No project")
                            if (due != null) {
                                append(" · ")
                                withStyle(SpanStyle(color = if (late) C.red else C.faint, fontWeight = if (late) FontWeight.Medium else FontWeight.Normal)) { append(due) }
                            }
                            if (priority != null) append(" · $priority")
                        },
                        style = T.sans.copy(fontSize = 12.sp, lineHeight = 15.sp, color = C.faint),
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }
        }
        MoveReminder(task, 34.dp)
    }
}

/* ─── Money ───────────────────────────────────────────────────────────── */

/**
 * What today still allows, big; the month — what went out against what came
 * in — in a tile of its own; then expected saving, committed and lent out as
 * tiles. A figure and its name, nothing more. Until the server's limit lands
 * every figure that needs it is a dash, never ₹0.
 */
@Composable
fun MoneyWidget(p: PaisaGlance, onOpen: () -> Unit, onSetTarget: () -> Unit, onCommitted: () -> Unit = {}) {
    Widget("Money", null, onOpen, badge = MONEY) {
        val limit = p.limit
        // Past the limit, the figure is the overage with a minus, as Expected
        // saving shows a shortfall — a ₹0 here would read as on track.
        val overBy = p.overToday
        val over = overBy != null
        // The answer Home is opened for, on its own panel: Paisa's tint, red's once over.
        Column(
            Modifier.fillMaxWidth().padding(top = 16.dp)
                .background(if (over) C.redTint else C.paisaTint, RoundedCornerShape(18.dp))
                .padding(start = 16.dp, end = 16.dp, top = 14.dp, bottom = 16.dp),
        ) {
            Text(
                "Left to spend today",
                style = T.sans.copy(fontSize = 12.5.sp, lineHeight = 16.sp, fontWeight = FontWeight.Medium, color = if (over) C.red else C.paisaInk),
            )
            Row(Modifier.fillMaxWidth().padding(top = 2.dp), verticalAlignment = Alignment.Bottom) {
                val figure = when {
                    limit == null -> "—"
                    overBy != null -> Fmt.rupees(-overBy)
                    else -> Fmt.rupees(limit - p.spentToday)
                }
                Fig(figure, 38.sp, if (over) C.red else C.ink, modifier = Modifier.weight(1f))
                if (limit != null && limit > 0) {
                    Text(
                        if (over) "${Fmt.rupees(p.spentToday)} spent of ${Fmt.rupees(limit)} today"
                        else "${Fmt.rupees(p.spentToday)} of ${Fmt.rupees(limit)} spent",
                        style = T.sans.copy(fontSize = 12.sp, lineHeight = 15.sp, color = if (over) C.red else C.paisaInk),
                        modifier = Modifier.padding(bottom = 8.dp),
                    )
                }
            }
            when {
                // Unknown, not zero: no income yet this month, so there is no limit to be past.
                limit == null -> {
                    if (p.salaryPending) Text("Salary not in yet.", style = T.sans.copy(fontSize = 12.sp, lineHeight = 15.sp, color = C.paisaInk), modifier = Modifier.padding(top = 6.dp))
                    if (p.salaryPending) Link("See what's committed", onCommitted, Modifier.padding(top = 2.dp))
                }
                limit > 0 -> Meter(if (over) 1f else p.spentToday.toFloat() / limit, if (over) C.red else C.paisa, Modifier.padding(top = 10.dp), 10.dp, C.white)
                // At 0 or below is a real state: what is left of the month is spoken for.
                // Below, the limit is past the line — a minus, in red — and the page says what it is made of.
                else -> {
                    Text(
                        when {
                            limit < 0 -> "Past the line — more is committed than is left this month."
                            over -> "${Fmt.rupees(p.spentToday)} spent today · everything left this month is committed"
                            else -> "Everything left this month is committed."
                        },
                        style = T.sans.copy(fontSize = 12.sp, lineHeight = 15.sp, color = if (over) C.red else C.paisaInk),
                        modifier = Modifier.padding(top = 6.dp),
                    )
                    Link("See what's committed", onCommitted, Modifier.padding(top = 2.dp))
                }
            }
        }

        // The month: out against in, as the old month arc said it — a line, not another box.
        Column(Modifier.fillMaxWidth().padding(start = 4.dp, end = 4.dp, top = 16.dp)) {
            Row(verticalAlignment = Alignment.Bottom) {
                Text("This month", style = T.sans.copy(fontSize = 12.5.sp, fontWeight = FontWeight.Medium, color = C.muted), modifier = Modifier.weight(1f))
                Text(
                    buildAnnotatedString {
                        withStyle(SpanStyle(color = C.ink, fontWeight = FontWeight.SemiBold)) { append(Fmt.rupees(p.goneOut)) }
                        append(" out  ")
                        withStyle(SpanStyle(color = C.paisaInk, fontWeight = FontWeight.SemiBold)) { append(Fmt.rupees(p.cameIn)) }
                        append(" in")
                    },
                    style = T.sans.copy(fontSize = 13.sp, lineHeight = 17.sp, color = C.faint),
                )
            }
            // Nothing in yet: no denominator, so no bar — never 0/0.
            if (p.cameIn > 0) Meter(p.goneOut.toFloat() / p.cameIn, if (p.goneOut > p.cameIn) C.red else C.paisa, Modifier.padding(top = 8.dp), 6.dp)
        }

        StatRow {
            val target = p.savingsTarget
            Stat(
                "Expected saving", p.saving?.let(Fmt::rupees) ?: "—", Modifier.weight(1f),
                red = p.saving != null && target > 0 && p.saving < target,
                link = if (target > 0) null else "Set target" to onSetTarget,
            )
            // A link: the lines behind the figure, and the way to change them.
            Stat("Committed", p.committed?.let(Fmt::rupees) ?: "—", Modifier.weight(1f), onClick = onCommitted)
            Stat("Lent out", Fmt.rupees(p.lentOut), Modifier.weight(1f))
        }
    }
}

/* ─── Diet ────────────────────────────────────────────────────────────── */

/**
 * How much protein still, as a ring round to the target — the one quantity
 * on Home a ring is for — and calories, carbs and fat as tiles, as far as
 * today's meals record them. A macro no meal records is a dash.
 */
@Composable
fun DietWidget(d: DietGlance, onOpen: () -> Unit, onSetTarget: () -> Unit) {
    Widget("Diet", "Today", onOpen, badge = DIET) {
        val target = d.proteinTarget?.takeIf { it > 0 }
        Row(Modifier.fillMaxWidth().padding(top = 16.dp), verticalAlignment = Alignment.CenterVertically) {
            Ring(if (target != null) (d.protein / target).toFloat() else 0f, C.diet, 92.dp, 10.dp) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Fig("${Fmt.jsRound(d.protein)}", 24.sp)
                    Text("g protein", style = T.sans.copy(fontSize = 10.5.sp, lineHeight = 12.sp, color = C.faint))
                }
            }
            Column(Modifier.weight(1f).padding(start = 18.dp)) {
                when {
                    target == null -> {
                        Text("No protein target", style = T.sans.copy(fontSize = 15.sp, fontWeight = FontWeight.Medium))
                        Link("Set target", onSetTarget, Modifier.padding(top = 4.dp))
                    }
                    d.protein < target -> {
                        Text("${g(target - d.protein)} to go", style = T.figure.copy(fontSize = 20.sp))
                        Small("of ${g(target)} today", Modifier.padding(top = 2.dp))
                    }
                    else -> {
                        Text("Target met", style = T.sans.copy(fontSize = 17.sp, fontWeight = FontWeight.Medium, color = C.dietInk))
                        Small("${g(d.protein - target)} past ${g(target)}", Modifier.padding(top = 2.dp))
                    }
                }
                Chip(
                    when (d.meals) {
                        0 -> "Nothing logged yet"
                        1 -> "1 meal logged"
                        else -> "${d.meals} meals logged"
                    },
                    modifier = Modifier.padding(top = 10.dp),
                )
            }
        }
        StatRow {
            val kcalT = d.kcalTarget?.takeIf { it > 0 }
            Stat("Calories", Fmt.indian(d.kcal) + (kcalT?.let { " / ${Fmt.indian(it)}" } ?: ""), Modifier.weight(1.4f), red = kcalT != null && d.kcal > kcalT)
            Stat("Carbs", d.carbs?.let(::g) ?: "—", Modifier.weight(1f))
            Stat("Fat", d.fat?.let(::g) ?: "—", Modifier.weight(1f))
        }
    }
}

/* ─── Activity ────────────────────────────────────────────────────────── */

/**
 * How much you moved: steps and active calories today, and the week's runs,
 * rides and workouts — from the phone's Health Connect, read here and sent
 * nowhere. Until it is connected the widget says where the numbers would come
 * from; a number it cannot read is a dash, never 0.
 */
@Composable
fun ActivityWidget(access: HealthAccess?, day: ActivityDay?, onConnect: () -> Unit) {
    Widget("Activity", "Today", null, badge = ACTIVITY) {
        when (access) {
            HealthAccess.Unavailable -> {
                Small("Steps and workouts come from Health Connect, which isn't on this phone.", Modifier.padding(top = 10.dp), C.muted)
                return@Widget
            }
            HealthAccess.NotGranted -> {
                Small("Steps, active calories, runs and rides — read from Health Connect, on this phone only.", Modifier.padding(top = 10.dp), C.muted)
                Link("Connect Health Connect", onConnect, Modifier.padding(top = 8.dp))
                return@Widget
            }
            else -> Unit
        }
        Row(Modifier.fillMaxWidth().padding(top = 10.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Lead(day?.steps?.let(Fmt::indian) ?: "—", "steps", Modifier.weight(1f))
            Lead(day?.activeKcal?.let(Fmt::indian) ?: "—", "kcal active", Modifier.weight(1f))
        }
        val week = day?.week.orEmpty()
        if (access == HealthAccess.Granted && day == null) {
            Small("Couldn't read Health Connect just now.", Modifier.padding(top = 10.dp))
            return@Widget
        }
        if (week.isEmpty()) {
            Small(if (day == null) "" else "No runs, rides or workouts this week", Modifier.padding(top = 12.dp))
            return@Widget
        }
        Column(Modifier.fillMaxWidth().padding(top = 14.dp).topRule(C.line).padding(top = 8.dp)) {
            Small("This week")
            week.groupBy { it.kind }.entries.sortedByDescending { e -> e.value.sumOf { it.minutes } }.forEach { (kind, sessions) ->
                Row(Modifier.fillMaxWidth().padding(top = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text(kind, style = T.sans.copy(fontSize = 14.sp, lineHeight = 18.sp), modifier = Modifier.weight(1f))
                    Small("${sessions.size} · ", color = C.faint)
                    Fig("${sessions.sumOf { it.minutes }} min", 13.5.sp)
                }
            }
        }
    }
}

/* ─── Meals and Workout: today's plan ─────────────────────────────────── */

/**
 * A plan item's picture: the stored Commons photo, or — with none, or one that
 * fails to load — the coin the receipts draw. A picture is never load-bearing.
 */
@Composable
internal fun PlanPicture(url: String?, icon: androidx.compose.ui.graphics.vector.ImageVector, ink: Color, tint: Color, size: androidx.compose.ui.unit.Dp = 76.dp) {
    var broken by remember(url) { mutableStateOf(false) }
    val shape = RoundedCornerShape(12.dp)
    if (url != null && !broken) {
        AsyncImage(
            url, null,
            Modifier.size(size).clip(shape).background(C.surface),
            contentScale = ContentScale.Crop,
            onError = { broken = true },
        )
    } else {
        Box(Modifier.size(size).clip(shape).background(tint), contentAlignment = Alignment.Center) {
            Glyph(icon, size * 0.4f, ink)
        }
    }
}

/** A small pill button: the brand's when it does the thing, quiet once it is done. */
@Composable
private fun PillButton(text: String, filled: Boolean, done: Boolean = false, onClick: () -> Unit) {
    val pill = RoundedCornerShape(50)
    Row(
        Modifier
            .clip(pill)
            .then(if (filled && !done) Modifier.background(C.brand) else Modifier.border(1.dp, C.border, pill))
            .tap(enabled = !done, onClick = onClick)
            .padding(horizontal = 13.dp, vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(5.dp),
    ) {
        if (done) Glyph(PhBold.check, 12.dp, C.muted)
        Text(text, style = T.sans.copy(fontSize = 12.5.sp, fontWeight = FontWeight.Medium, color = if (filled && !done) C.white else C.muted))
    }
}

/** What the plan says while it is not a plan: still working, or could not. Null when there is one. */
@Composable
internal fun PlanState(plan: TodayPlan?, loading: Boolean, onRetry: () -> Unit): Boolean {
    when {
        plan == null -> Small(if (loading) "Planning the rest of your day…" else "", Modifier.padding(top = 10.dp), C.muted)
        !plan.available -> Row(Modifier.padding(top = 10.dp), verticalAlignment = Alignment.CenterVertically) {
            Small("Couldn't plan just now. ", color = C.muted)
            if (!loading) Link("Try again", onRetry) else Small("Trying…", color = C.muted)
        }
        else -> return false
    }
    return true
}

/**
 * The rest of today, planned: one meal for each slot still ahead, sized so the
 * day lands on its targets — the sum is shown, so the claim can be checked. A
 * library dish carries its own numbers; an idea is marked and its numbers
 * carry the dot. *Log it* logs the meal; *Save* puts an idea in your dishes.
 */
@Composable
fun MealsWidget(
    plan: TodayPlan?, loading: Boolean, done: List<String>,
    onLog: (PlanMeal) -> Unit, onSave: (PlanMeal) -> Unit, onRetry: () -> Unit,
) {
    Widget("Meals", "Rest of today", null, badge = MEALS, aside = { Chip(if (loading && plan != null) "Updating…" else "Rest of today") }) {
        if (PlanState(plan, loading, onRetry)) return@Widget
        val p = plan!!
        if (p.done || p.meals.isEmpty()) {
            Small("Today's meals are done — ${Fmt.indian(p.loggedKcal)} kcal and ${g(p.loggedProtein)} protein logged.", Modifier.padding(top = 10.dp), C.muted)
            return@Widget
        }
        val lands = buildList {
            p.proteinTarget?.let { add("${g(p.loggedProtein + p.plannedProtein)} of ${g(it)} protein") }
            p.kcalTarget?.let { add("${Fmt.indian(p.loggedKcal + p.plannedKcal)} of ${Fmt.indian(it)} kcal") }
        }
        Small(if (lands.isEmpty()) "No targets yet — these are ordinary meals." else "With these, the day lands at " + lands.joinToString(" · "), Modifier.padding(top = 6.dp))
        p.meals.forEachIndexed { i, m ->
            PlanMealItem(
                m, done, onLog, onSave,
                Modifier.fillMaxWidth().padding(top = 12.dp).then(if (i == 0) Modifier else Modifier.topRule(C.line).padding(top = 12.dp)),
            )
        }
    }
}

/** A planned meal's numbers, as far as it records them. An idea's are estimates, so they carry the dot. */
@Composable
private fun MealMacros(m: PlanMeal, size: TextUnit, line: TextUnit, modifier: Modifier = Modifier) {
    Row(modifier, verticalAlignment = Alignment.CenterVertically) {
        if (m.idea) Dot()
        Text(
            listOfNotNull(
                "${Fmt.indian(m.kcal)} kcal", "${g(m.protein)} protein",
                m.carbs?.let { "${g(it)} carbs" }, m.fat?.let { "${g(it)} fat" },
            ).joinToString(" · "),
            style = T.sans.copy(fontSize = size, lineHeight = line, color = C.muted),
        )
    }
}

/** A Commons picture's credit: small, one line — owed, not read. */
@Composable
private fun Credit(text: String, modifier: Modifier = Modifier) =
    Text(text, style = T.sans.copy(fontSize = 10.sp, lineHeight = 13.sp, color = C.grey), maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = modifier)

/**
 * A plan item's picture across the top of its card, on a page. With no
 * picture — or one that fails — there is no banner at all: the card is the
 * words, and a picture is never load-bearing.
 */
@Composable
private fun Banner(url: String?, height: androidx.compose.ui.unit.Dp) {
    var broken by remember(url) { mutableStateOf(false) }
    if (url == null || broken) return
    AsyncImage(
        url, null,
        Modifier.fillMaxWidth().height(height).background(C.surface),
        contentScale = ContentScale.Crop,
        onError = { broken = true },
    )
}

/**
 * One planned meal: its picture and credit, the slot, the dish, its macros —
 * an idea's carry the estimate's dot — *Log it*, and *Save* on an idea.
 *
 * `page` is the card on Meals today (`spec/in-progress/nudges.md`): the
 * picture across the top, and neither the line on why it fits nor which
 * source it came from — the page is for logging, and the dot already says an
 * idea's numbers are estimates. Its idea button says *Save to dishes*.
 */
@Composable
internal fun PlanMealItem(
    m: PlanMeal, done: List<String>, onLog: (PlanMeal) -> Unit, onSave: (PlanMeal) -> Unit,
    modifier: Modifier = Modifier, page: Boolean = false,
) {
    val logged = "meal:${m.slot}" in done
    val saved = "save:${m.slot}" in done
    if (!page) {
        Row(modifier, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            PlanPicture(m.imageUrl, com.sonu.spica.ui.common.Ph.bowlFood, C.dietInk, C.dietTint)
            Column(Modifier.weight(1f)) {
                Small(m.slot + if (m.idea) " · idea" else "")
                Text(m.name, style = T.sans.copy(fontSize = 15.sp, lineHeight = 19.sp, fontWeight = FontWeight.Medium), maxLines = 2, overflow = TextOverflow.Ellipsis)
                MealMacros(m, 12.sp, 15.sp, Modifier.padding(top = 3.dp))
                if (m.why.isNotBlank()) Small(m.why, Modifier.padding(top = 3.dp))
                Row(Modifier.padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    PillButton(if (logged) "Logged" else "Log it", filled = true, done = logged) { onLog(m) }
                    if (m.idea) PillButton(if (saved) "Saved" else "Save", filled = false, done = saved) { onSave(m) }
                }
                m.imageCredit?.let { Credit(it, Modifier.padding(top = 6.dp)) }
            }
        }
        return
    }
    Column(modifier) {
        Banner(m.imageUrl, 128.dp)
        Column(Modifier.fillMaxWidth().padding(start = 16.dp, end = 16.dp, top = 14.dp, bottom = 16.dp)) {
            Chip(m.slot, C.dietInk, bg = C.dietTint)
            Text(
                m.name,
                style = T.sans.copy(fontSize = 18.sp, lineHeight = 23.sp, fontWeight = FontWeight.SemiBold),
                maxLines = 2, overflow = TextOverflow.Ellipsis, modifier = Modifier.padding(top = 8.dp),
            )
            MealMacros(m, 13.sp, 17.sp, Modifier.padding(top = 3.dp))
            Row(Modifier.padding(top = 12.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                ActionPill(if (logged) "Logged" else "Log it", { onLog(m) }, PillKind.Primary, enabled = !logged, icon = if (logged) PhBold.check else null)
                if (m.idea) ActionPill(if (saved) "Saved" else "Save to dishes", { onSave(m) }, enabled = !saved, icon = if (saved) PhBold.check else null)
            }
            m.imageCredit?.takeIf { m.imageUrl != null }?.let { Credit(it, Modifier.padding(top = 10.dp)) }
        }
    }
}

private val WORKOUT_WORDS = mapOf("gym" to "Gym", "run" to "Run", "ride" to "Ride", "walk" to "Walk", "yoga" to "Yoga")

/**
 * One workout for today, and why — from the week so far. A gym session lists
 * its exercises; a run or a ride its minutes and an easy target. A rest day is
 * an answer too. *Done* marks the library's exercises done and logs the
 * workout habit.
 */
@Composable
fun WorkoutWidget(plan: TodayPlan?, loading: Boolean, done: Boolean, onDone: (PlanWorkout) -> Unit, onRetry: () -> Unit) {
    Widget("Workout", "Today", null, badge = WORKOUT) {
        if (PlanState(plan, loading, onRetry)) return@Widget
        val w = plan!!.workout
        if (w == null) {
            Small("Nothing planned for today.", Modifier.padding(top = 10.dp), C.muted)
            return@Widget
        }
        PlanWorkoutItem(w, done, onDone)
    }
}

/** A rest day is called that, once — the plan's own name for it ("Rest") would only repeat it. */
internal fun workoutTitle(w: PlanWorkout) = if (w.kind == "rest") "Rest day" else w.name

/** What kind, how long, and whether it is only an idea: "Run · 30 min". A rest day's title already says its kind; empty when nothing is left. */
internal fun workoutMeta(w: PlanWorkout) =
    listOfNotNull(if (w.kind == "rest") null else WORKOUT_WORDS[w.kind] ?: w.kind, w.minutes?.let { "$it min" }, if (w.idea) "idea" else null).joinToString(" · ")

/** A gym session's exercises under a rule; an idea's carry the dot. */
@Composable
private fun WorkoutExercises(w: PlanWorkout) {
    if (w.exercises.isEmpty()) return
    Column(Modifier.fillMaxWidth().padding(top = 12.dp).topRule(C.line).padding(top = 4.dp)) {
        w.exercises.forEach { x ->
            Row(Modifier.fillMaxWidth().padding(top = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                if (x.idea) Dot()
                Text(x.name, style = T.sans.copy(fontSize = 14.sp, lineHeight = 18.sp), modifier = Modifier.weight(1f))
                Small(x.detail)
            }
        }
    }
}

/**
 * Today's workout: its picture, kind and minutes, the name, why — the agent's
 * reason, from the week so far — the exercises, and *Done*.
 *
 * `page` is Workout today's card (`spec/in-progress/nudges.md`): the picture
 * across the top, why in the agent's serif, and beside *Done* a *Not today*
 * when the page came from a nudge (`onNotToday`).
 */
@Composable
internal fun PlanWorkoutItem(
    w: PlanWorkout, done: Boolean, onDone: (PlanWorkout) -> Unit,
    page: Boolean = false, onNotToday: (() -> Unit)? = null,
) {
    if (!page) {
        Row(Modifier.fillMaxWidth().padding(top = 12.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            PlanPicture(w.imageUrl, com.sonu.spica.ui.common.Ph.barbell, C.dietInk, C.dietTint)
            Column(Modifier.weight(1f)) {
                workoutMeta(w).takeIf { it.isNotEmpty() }?.let { Small(it) }
                Text(workoutTitle(w), style = T.sans.copy(fontSize = 15.sp, lineHeight = 19.sp, fontWeight = FontWeight.Medium))
                if (w.why.isNotBlank()) Small(w.why, Modifier.padding(top = 3.dp))
            }
        }
        WorkoutExercises(w)
        if (w.kind != "rest") {
            Row(Modifier.padding(top = 12.dp)) {
                PillButton(if (done) "Done" else "Mark done", filled = true, done = done) { onDone(w) }
            }
        }
        w.imageCredit?.let { Credit(it, Modifier.padding(top = 8.dp)) }
        return
    }
    Column(Modifier.fillMaxWidth()) {
        Banner(w.imageUrl, 168.dp)
        Column(Modifier.fillMaxWidth().padding(start = 16.dp, end = 16.dp, top = 14.dp, bottom = 16.dp)) {
            val meta = workoutMeta(w)
            if (meta.isNotEmpty()) Small(meta)
            Text(
                workoutTitle(w),
                style = T.sans.copy(fontSize = 22.sp, lineHeight = 28.sp, fontWeight = FontWeight.SemiBold),
                modifier = Modifier.padding(top = if (meta.isNotEmpty()) 2.dp else 0.dp),
            )
            if (w.why.isNotBlank()) Text(w.why, style = T.agentVoice, modifier = Modifier.padding(top = 10.dp))
            WorkoutExercises(w)
            if (w.kind != "rest") {
                Row(Modifier.padding(top = 16.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    ActionPill("Done", { onDone(w) }, PillKind.Primary, enabled = !done, icon = if (done) PhBold.check else null)
                    if (onNotToday != null && !done) ActionPill("Not today", onNotToday)
                }
            }
            w.imageCredit?.takeIf { w.imageUrl != null }?.let { Credit(it, Modifier.padding(top = 10.dp)) }
        }
    }
}

/* ─── Habits ──────────────────────────────────────────────────────────── */

private val CELL = 26.dp
private val WEEK = 34.dp
private const val HABIT_ROWS = 6

/**
 * How the week is going: a row per habit, Monday to Sunday, its icon and name. A
 * habit you are building fills the days it happened; one with a count shows
 * the number. A day with no log is an empty mark, never a zero — not logged is
 * not none. Counts are in ink: manager, not coach.
 */
@Composable
fun HabitsWidget(h: HabitsGlance, onOpen: () -> Unit) {
    Widget("Habits", "This week", onOpen, badge = HABITS) {
        if (h.lines.isEmpty()) {
            Small("Nothing tracked yet. Say “track workouts” to start one.", Modifier.padding(top = 10.dp), C.muted)
            return@Widget
        }
        Row(Modifier.fillMaxWidth().padding(top = 12.dp), verticalAlignment = Alignment.CenterVertically) {
            Spacer(Modifier.weight(1f))
            h.week.forEach { d ->
                Text(
                    d.letter,
                    style = T.sans.copy(
                        fontSize = 11.sp, textAlign = TextAlign.Center,
                        fontWeight = if (d.isToday) FontWeight.SemiBold else FontWeight.Normal,
                        color = if (d.isToday) C.ink else C.faint,
                    ),
                    modifier = Modifier.width(CELL),
                )
            }
            Text("Week", style = T.sans.copy(fontSize = 11.sp, textAlign = TextAlign.End, color = C.faint), modifier = Modifier.width(WEEK))
        }
        h.lines.take(HABIT_ROWS).forEach { HabitWeek(it, h.week) }
        val rest = h.lines.size - HABIT_ROWS
        if (rest > 0) Small("$rest more", Modifier.padding(top = 10.dp))
    }
}

@Composable
private fun HabitWeek(line: HabitLine, week: List<ChainDay>) {
    val counts = week.map { d -> d.habits.firstOrNull { it.habit.equals(line.name, ignoreCase = true) }?.count ?: 0.0 }
    // The week's figure: days for a habit you are building, the sum for one you count.
    val total = if (line.counted) counts.sum() else counts.count { it > 0 }.toDouble()
    Row(Modifier.fillMaxWidth().padding(top = 10.dp), verticalAlignment = Alignment.CenterVertically) {
        HabitIcon(line.name, 22.dp)
        Text(
            line.name,
            style = T.sans.copy(fontSize = 14.sp, lineHeight = 18.sp),
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier.weight(1f).padding(start = 8.dp, end = 4.dp),
        )
        week.forEachIndexed { i, d ->
            Box(Modifier.width(CELL), contentAlignment = Alignment.Center) { DayMark(line.counted, counts[i], d) }
        }
        Text(
            if (total == 0.0) "—" else Fmt.num(Math.round(total * 10) / 10.0),
            style = T.figure.copy(fontSize = 14.sp, textAlign = TextAlign.End),
            modifier = Modifier.width(WEEK),
        )
    }
}

@Composable
private fun DayMark(counted: Boolean, n: Double, d: ChainDay) {
    when {
        d.future -> Box(Modifier.size(4.dp).background(C.line, CircleShape))
        n > 0 && counted -> Text(Fmt.num(Math.round(n * 10) / 10.0), style = T.figure.copy(fontSize = 13.sp, textAlign = TextAlign.Center))
        n > 0 -> Box(Modifier.size(12.dp).background(C.diet, CircleShape))
        else -> Box(Modifier.size(12.dp).border(1.3.dp, if (d.isToday) C.grey else C.ringIdle, CircleShape))
    }
}
