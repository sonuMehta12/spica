package com.sonu.spica.ui.day

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.semantics.role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.sonu.spica.data.PlanMeal
import com.sonu.spica.data.PlanWorkout
import com.sonu.spica.lib.Day
import com.sonu.spica.lib.Fmt
import com.sonu.spica.logic.DaySheet
import com.sonu.spica.logic.Rail
import com.sonu.spica.logic.RailKind
import com.sonu.spica.logic.RailRow
import com.sonu.spica.ui.common.Glyph
import com.sonu.spica.ui.common.Ph
import com.sonu.spica.ui.common.PhBold
import com.sonu.spica.ui.common.PhFill
import com.sonu.spica.ui.common.habitGlyph
import com.sonu.spica.ui.common.tap
import com.sonu.spica.ui.theme.C
import com.sonu.spica.ui.theme.S
import com.sonu.spica.ui.theme.T

/** A mode's stops in the day look. `THEME.md` § The day look. */
data class DayTone(val base: Color, val ink: Color, val mist: Color, val tint: Color)

fun toneOf(sheet: DaySheet) = when (sheet) {
    DaySheet.Money -> DayTone(C.deepPaisa, C.deepPaisaInk, C.deepPaisaMist, C.deepPaisaTint)
    DaySheet.Diet, DaySheet.Activity -> DayTone(C.deepDiet, C.deepDietInk, C.deepDietMist, C.deepDietTint)
    DaySheet.Work -> DayTone(C.deepWork, C.deepWorkInk, C.deepWorkMist, C.deepWorkTint)
    DaySheet.Habits -> DayTone(C.deepHabit, C.ink, C.deepHabitMist, C.lineSoft)
}

fun glyphOf(r: RailRow): ImageVector = when (r.kind) {
    RailKind.Spend -> PhFill.wallet
    RailKind.Meal, RailKind.PlanMeal -> PhFill.bowlFood
    RailKind.Habit -> habitGlyph(r.title) ?: PhFill.checkSquare
    RailKind.Task -> PhFill.checkSquare
    RailKind.Workout -> if (Regex("walk|run|step", RegexOption.IGNORE_CASE).containsMatchIn(r.title + " " + (r.workout?.kind ?: ""))) PhFill.sneakerMove else PhFill.barbell
    RailKind.Schedule -> PhFill.bell
}

/**
 * The day's type scale: five styles, nothing else on the rail. A time is the
 * smallest thing on it; a title the largest; the figure and the project sit
 * between, in grey.
 */
private object DayType {
    val time = T.day.copy(fontSize = 10.5.sp, fontWeight = FontWeight.Medium, color = C.faint, textAlign = TextAlign.End, letterSpacing = 0.1.sp)
    val title = T.day.copy(fontSize = 15.sp, fontWeight = FontWeight.SemiBold, lineHeight = 20.sp)
    val meta = T.day.copy(fontSize = 12.sp, fontWeight = FontWeight.Medium, lineHeight = 16.sp, color = C.faint)
    val figure = T.day.copy(fontSize = 13.sp, fontWeight = FontWeight.Medium, color = C.muted)
    val label = T.day.copy(fontSize = 12.sp, fontWeight = FontWeight.SemiBold, color = C.muted)
}

/** The time column and the node, so the line runs through every node's centre. */
private val TIME_W = 36.dp
private val GAP = 10.dp
private val NODE = 44.dp
private val LINE_X = TIME_W + GAP + NODE / 2

/** What Home's day can do; every action is the view model's own. */
class DayActions(
    val onRow: (DaySheet) -> Unit,
    val onToggleTask: (String) -> Unit,
    val onLogPlanMeal: (PlanMeal) -> Unit,
    val onDoneWorkout: (PlanWorkout) -> Unit,
)

/**
 * Home as the day: the date and the week on the ground, then the day on a
 * white sheet — what happened, Now, the one thing next as a card, the rest of
 * today. Opens at Now. `spec/home-day-rail.md`.
 */
@Composable
fun DayHome(todayIso: String, now: String, rail: Rail, a: DayActions, modifier: Modifier = Modifier) {
    Column(modifier.fillMaxSize()) {
        WeekStrip(todayIso)
        Box(
            Modifier
                .weight(1f)
                .fillMaxWidth()
                .then(S.widget(SHEET))
                .clip(SHEET)
                .background(C.white),
        ) {
            val nowIndex = rail.past.size.coerceAtLeast(1)
            val list = rememberLazyListState(initialFirstVisibleItemIndex = (nowIndex - 1).coerceAtLeast(0))
            Column {
                LazyColumn(state = list, modifier = Modifier.fillMaxSize().padding(start = 16.dp, end = 16.dp, top = 10.dp)) {
                    if (rail.past.isEmpty()) item("empty-past") { Quiet("Nothing logged yet today.") }
                    items(rail.past, key = { it.key }) { r -> RowView(r, solid = true, a) }
                    item("now") { NowRow(now) }
                    rail.next?.let { n -> item("next") { NextCard(n, a) } }
                    items(rail.later, key = { it.key }) { r -> RowView(r, solid = false, a) }
                    if (rail.anytime.isNotEmpty()) {
                        item("anytime") {
                            Text("Any time", style = DayType.label, modifier = Modifier.dashedLine().padding(start = TIME_W + GAP + NODE + GAP, top = 14.dp, bottom = 4.dp))
                        }
                        items(rail.anytime, key = { it.key }) { r -> RowView(r, solid = false, a) }
                    }
                    if (rail.next == null) item("empty-ahead") { Quiet("Nothing planned for the rest of today.") }
                    // Room for the composer, which floats over the day.
                    item("foot") { Spacer(Modifier.fillParentMaxHeight(0.75f)) }
                }
            }
        }
    }
}

private val SHEET = RoundedCornerShape(topStart = 32.dp, topEnd = 32.dp)

/** Weeks the strip can swipe to: a year back, eight weeks ahead. */
private const val WEEKS_BACK = 52
private const val WEEKS_AHEAD = 8

/**
 * The week, Monday first, swiped left and right a week at a time; it opens on
 * this week. The box on its left names the month of the week showing. Today
 * is in Jamun; `selected`, when it is another day, is a ring. A day opens only
 * when `onDay` is given — until then the strip is a picture of where you are.
 */
@Composable
private fun WeekStrip(today: String, selected: String = today, onDay: ((String) -> Unit)? = null) {
    val thisMonday = Day.addDays(today, -Day.weekIndex(today))
    val pager = rememberPagerState(initialPage = WEEKS_BACK) { WEEKS_BACK + 1 + WEEKS_AHEAD }
    val shownMonday = Day.addDays(thisMonday, (pager.currentPage - WEEKS_BACK) * 7)
    // A week's month is its Thursday's, so a week across two months is named the way a calendar would.
    val month = Day.monthName(Day.addDays(shownMonday, 3))
    Row(Modifier.fillMaxWidth().padding(start = 12.dp, end = 8.dp, top = 4.dp, bottom = 12.dp), verticalAlignment = Alignment.CenterVertically) {
        // The month, beside its week: three letters in a box exactly the height of a day, so it sits on the same line.
        Box(
            Modifier.padding(end = 6.dp).size(width = 46.dp, height = 56.dp).clip(RoundedCornerShape(16.dp)).background(C.white)
                .semantics { contentDescription = month },
            contentAlignment = Alignment.Center,
        ) {
            Text(month.take(3), style = T.day.copy(fontSize = 13.sp, fontWeight = FontWeight.ExtraBold))
        }
        HorizontalPager(pager, Modifier.weight(1f)) { page ->
            val monday = Day.addDays(thisMonday, (page - WEEKS_BACK) * 7)
            Row(Modifier.fillMaxWidth()) {
                listOf("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun").forEachIndexed { i, name ->
                    val iso = Day.addDays(monday, i)
                    val isToday = iso == today
                    val isPicked = iso == selected && !isToday
                    Column(
                        Modifier
                            .weight(1f)
                            .then(if (onDay != null) Modifier.clip(RoundedCornerShape(16.dp)).tap { onDay(iso) } else Modifier)
                            .semantics { contentDescription = "$name ${Day.dayOfMonth(iso)} ${Day.monthName(iso)}" + if (isToday) ", today" else "" },
                        horizontalAlignment = Alignment.CenterHorizontally,
                    ) {
                        Text(name, style = T.day.copy(fontSize = 12.sp, fontWeight = FontWeight.Medium, color = C.faint))
                        Box(
                            Modifier
                                .padding(top = 4.dp)
                                .size(36.dp)
                                .clip(CircleShape)
                                .background(if (isToday) C.brand else Color.Transparent)
                                .then(if (isPicked) Modifier.border(2.dp, C.brand, CircleShape) else Modifier),
                            contentAlignment = Alignment.Center,
                        ) {
                            Text(
                                "${Day.dayOfMonth(iso)}",
                                style = T.day.copy(
                                    fontSize = 16.sp, fontWeight = if (isToday) FontWeight.ExtraBold else FontWeight.Bold,
                                    color = when { isToday -> C.white; iso > today -> C.faint; else -> C.ink },
                                ),
                            )
                        }
                    }
                }
            }
        }
    }
}

/** The line through every node: solid where the day has happened, dashed where it is still a plan. */
private fun Modifier.railLine(solid: Boolean) = drawBehind {
    val x = LINE_X.toPx()
    drawLine(
        color = C.border, start = Offset(x, 0f), end = Offset(x, size.height), strokeWidth = 3.dp.toPx(), cap = StrokeCap.Butt,
        pathEffect = if (solid) null else PathEffect.dashPathEffect(floatArrayOf(7.dp.toPx(), 6.dp.toPx())),
    )
}

private fun Modifier.dashedLine() = railLine(false)

/** A done row's node is solid with a white glyph; a planned one is the mist stop with the glyph in colour. */
@Composable
private fun Node(r: RailRow, onClick: () -> Unit) {
    val t = toneOf(r.sheet)
    Box(
        Modifier
            .size(NODE)
            .background(C.white, CircleShape)
            .padding(0.dp)
            .clip(CircleShape)
            .background(if (r.done) t.base else t.mist)
            .tap(onClick = onClick),
        contentAlignment = Alignment.Center,
    ) { Glyph(glyphOf(r), 21.dp, if (r.done) C.white else t.base) }
}

@Composable
private fun AmberDot() = Box(Modifier.padding(end = 5.dp).size(6.dp).background(C.amber, CircleShape))

/**
 * One moment: its time, its node on the line, the title, and on the right its
 * figure — or, for a task, a round box that ticks it. Tapping it opens its
 * widget as a sheet.
 */
@Composable
private fun RowView(r: RailRow, solid: Boolean, a: DayActions) {
    val open = { a.onRow(r.sheet) }
    val t = toneOf(r.sheet)
    // The same space above and below every row: a two-line title makes its row taller, never the gap uneven.
    Row(Modifier.fillMaxWidth().railLine(solid).padding(vertical = 7.dp), verticalAlignment = Alignment.CenterVertically) {
        Text(
            r.time, style = DayType.time,
            maxLines = 1, modifier = Modifier.width(TIME_W),
        )
        Spacer(Modifier.width(GAP))
        Node(r, open)
        Spacer(Modifier.width(GAP))
        Column(Modifier.weight(1f).tap(onClick = open)) {
            val past = solid
            Text(
                r.title,
                style = DayType.title.copy(color = when { past -> C.muted; r.done -> C.faint; else -> C.ink }),
                maxLines = 2, overflow = TextOverflow.Ellipsis,
            )
            if (r.sub != null) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(r.sub, style = DayType.meta, maxLines = 1)
                    if (r.late != null) Text(" · ${r.late}", style = DayType.meta.copy(fontWeight = FontWeight.Bold, color = C.red), maxLines = 1)
                }
            }
        }
        if (r.figure != null) {
            Row(Modifier.padding(start = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                if (r.estimate) AmberDot()
                Text(r.figure, style = DayType.figure, maxLines = 1)
            }
        }
        if (r.taskId != null) {
            Spacer(Modifier.width(10.dp))
            TaskBox(r.done, t.base, r.title) { a.onToggleTask(r.taskId) }
        }
    }
}

/** A task's round box: an empty ring in its colour, or filled with a white tick. */
@Composable
private fun TaskBox(done: Boolean, color: Color, title: String, onToggle: () -> Unit) {
    Box(
        Modifier
            .size(24.dp)
            .semantics {
                role = Role.Checkbox
                stateDescription = if (done) "Done" else "Not done"
                contentDescription = title
            }
            .clip(CircleShape)
            .background(if (done) color else Color.Transparent)
            .border(2.dp, color, CircleShape)
            .tap(onClick = onToggle),
        contentAlignment = Alignment.Center,
    ) { if (done) Glyph(PhBold.check, 12.dp, C.white) }
}

/** Now: a dark pill on the line at the current time. */
@Composable
private fun NowRow(now: String) {
    Row(Modifier.fillMaxWidth().height(40.dp), verticalAlignment = Alignment.CenterVertically) {
        Spacer(Modifier.width(TIME_W + GAP - 4.dp))
        Box(Modifier.clip(CircleShape).background(C.ink).padding(horizontal = 12.dp, vertical = 6.dp)) {
            Text("Now · $now", style = T.day.copy(fontSize = 12.sp, fontWeight = FontWeight.ExtraBold, color = C.white))
        }
    }
}

/**
 * The one open card: the first thing still ahead, with its one action. A
 * planned meal is logged; the workout or a task is done; a schedule only says
 * what it will do.
 */
@Composable
private fun NextCard(r: RailRow, a: DayActions) {
    val t = toneOf(r.sheet)
    Row(Modifier.fillMaxWidth().railLine(false), verticalAlignment = Alignment.Top) {
        Text(
            r.time, style = DayType.time.copy(fontWeight = FontWeight.Bold, color = C.ink),
            maxLines = 1, modifier = Modifier.width(TIME_W).padding(top = 18.dp),
        )
        Spacer(Modifier.width(GAP))
        Box(Modifier.padding(top = 8.dp)) { Node(r) { a.onRow(r.sheet) } }
        Spacer(Modifier.width(GAP))
        Column(
            Modifier
                .weight(1f)
                .padding(top = 4.dp, bottom = 12.dp)
                .clip(RoundedCornerShape(24.dp))
                .background(t.tint)
                .tap { a.onRow(r.sheet) }
                .padding(14.dp),
        ) {
            Box(Modifier.clip(CircleShape).background(C.white).padding(horizontal = 9.dp, vertical = 3.dp)) {
                Text("Up next", style = T.day.copy(fontSize = 11.sp, fontWeight = FontWeight.ExtraBold, color = t.ink))
            }
            Text(
                r.title, style = DayType.title.copy(fontWeight = FontWeight.Bold),
                maxLines = 2, overflow = TextOverflow.Ellipsis, modifier = Modifier.padding(top = 7.dp),
            )
            val line = when (r.kind) {
                RailKind.PlanMeal -> r.planMeal?.let { "${Fmt.grams(it.protein)} protein · ${Fmt.indian(it.kcal)} kcal" }
                RailKind.Workout -> r.workout?.minutes?.let { "$it min" }
                RailKind.Schedule -> r.blurb
                RailKind.Task -> r.sub
                else -> null
            }
            if (line != null || r.late != null) {
                Row(Modifier.padding(top = 3.dp), verticalAlignment = Alignment.CenterVertically) {
                    if (r.estimate) AmberDot()
                    if (line != null) Text(line, style = DayType.meta.copy(fontSize = 13.sp, color = t.ink))
                    if (r.late != null) Text(" · ${r.late}", style = DayType.meta.copy(fontSize = 13.sp, fontWeight = FontWeight.Bold, color = C.red))
                }
            }
            val action: (() -> Unit)? = when (r.kind) {
                RailKind.PlanMeal -> r.planMeal?.let { m -> { a.onLogPlanMeal(m) } }
                RailKind.Workout -> r.workout?.let { w -> { a.onDoneWorkout(w) } }
                RailKind.Task -> r.taskId?.let { id -> { a.onToggleTask(id) } }
                else -> null
            }
            if (action != null) {
                Row(Modifier.padding(top = 12.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(14.dp)) {
                    Box(Modifier.clip(CircleShape).background(C.brand).tap(onClick = action).padding(horizontal = 18.dp, vertical = 9.dp)) {
                        Text(if (r.kind == RailKind.PlanMeal) "Log it" else "Done", style = T.day.copy(fontSize = 14.sp, fontWeight = FontWeight.ExtraBold, color = C.white))
                    }
                    if (r.kind == RailKind.PlanMeal) {
                        Text("Something else", style = T.day.copy(fontSize = 14.sp, fontWeight = FontWeight.Bold, color = C.brand), modifier = Modifier.tap { a.onRow(DaySheet.Diet) })
                    }
                }
            }
        }
    }
}

@Composable
private fun Quiet(text: String) {
    Text(text, style = DayType.meta.copy(fontSize = 13.sp), modifier = Modifier.padding(start = TIME_W + GAP + NODE + GAP, top = 14.dp, bottom = 14.dp))
}
