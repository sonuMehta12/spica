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
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil3.compose.SubcomposeAsyncImage
import com.sonu.spica.data.PlanMeal
import com.sonu.spica.data.PlanWorkout
import com.sonu.spica.lib.Day
import com.sonu.spica.lib.Fmt
import com.sonu.spica.logic.DayKind
import com.sonu.spica.logic.DayRail
import com.sonu.spica.logic.DaySheet
import com.sonu.spica.logic.DayTotals
import com.sonu.spica.logic.Rail
import com.sonu.spica.logic.RailKind
import com.sonu.spica.logic.RailRow
import com.sonu.spica.ui.common.Glyph
import com.sonu.spica.ui.common.PhBold
import com.sonu.spica.ui.common.PhFill
import com.sonu.spica.ui.common.habitGlyph
import com.sonu.spica.ui.common.tap
import com.sonu.spica.ui.theme.C
import com.sonu.spica.ui.theme.S
import com.sonu.spica.ui.theme.T

/** A mode's stops in the day look. `THEME.md` § The day look. */
data class DayTone(val base: Color, val ink: Color, val mist: Color, val tint: Color, val soft: Color)

fun toneOf(sheet: DaySheet) = when (sheet) {
    DaySheet.Money -> DayTone(C.deepPaisa, C.deepPaisaInk, C.deepPaisaMist, C.deepPaisaTint, C.deepPaisaSoft)
    DaySheet.Diet, DaySheet.Activity -> DayTone(C.deepDiet, C.deepDietInk, C.deepDietMist, C.deepDietTint, C.deepDietSoft)
    DaySheet.Work -> DayTone(C.deepWork, C.deepWorkInk, C.deepWorkMist, C.deepWorkTint, C.deepWorkSoft)
    DaySheet.Habits -> DayTone(C.deepHabit, C.ink, C.deepHabitMist, C.lineSoft, C.border)
}

private val ON_FOOT = Regex("walk|run|step|jog", RegexOption.IGNORE_CASE)

/** A workout on foot — a run, a walk — rather than one with weights. */
fun onFoot(w: PlanWorkout?) = w != null && ON_FOOT.containsMatchIn(w.kind + " " + w.name)

fun glyphOf(r: RailRow): ImageVector = when (r.kind) {
    RailKind.Spend -> PhFill.wallet
    RailKind.Meal, RailKind.PlanMeal -> PhFill.bowlFood
    RailKind.Habit -> habitGlyph(r.title) ?: PhFill.checkSquare
    RailKind.Task -> PhFill.checkSquare
    RailKind.Workout -> if (onFoot(r.workout) || ON_FOOT.containsMatchIn(r.title)) PhFill.sneakerMove else PhFill.barbell
    RailKind.Schedule -> PhFill.bell
}

/**
 * The day's type scale: five styles, nothing else on the rail. A time is the
 * smallest thing on it; a title the largest; the figure and the project sit
 * between, in grey.
 */
internal object DayType {
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
private val TEXT_X = TIME_W + GAP + NODE + GAP

/** What Home's day can do; every action is the view model's own. */
class DayActions(
    /** A row's sheet, opened on that row and that day. */
    val onRow: (RailRow) -> Unit,
    /** A sheet with no row picked — *Something else*, *See the session*. */
    val onSheet: (DaySheet) -> Unit,
    /** A day in the week; today returns to Now. */
    val onDay: (String) -> Unit,
    val onToggleTask: (String) -> Unit,
    val onLogPlanMeal: (PlanMeal) -> Unit,
    val onDoneWorkout: (PlanWorkout) -> Unit,
)

/**
 * Home as the day: the week on the ground, then the day on a white sheet.
 * Today: what happened, Now, the one thing next as a card, the rest of today,
 * opening at Now. Another day: its date, its totals and a way back to today,
 * then what happened that day, or what is due on it. `spec/home-day-rail.md`.
 */
@Composable
fun DayHome(
    todayIso: String, day: String, now: String, source: DaySource, rail: Rail?, totals: DayTotals?,
    a: DayActions, modifier: Modifier = Modifier,
) {
    val kind = DayRail.kindOf(day, todayIso)
    Column(modifier.fillMaxSize()) {
        WeekStrip(todayIso, day, a.onDay)
        Box(
            Modifier
                .weight(1f)
                .fillMaxWidth()
                .then(S.widget(SHEET))
                .clip(SHEET)
                .background(C.white),
        ) {
            when (kind) {
                DayKind.Today -> if (rail != null) TodayRail(now, rail, a)
                else -> OtherDay(day, todayIso, kind, source, rail, totals, a)
            }
        }
    }
}

@Composable
private fun TodayRail(now: String, rail: Rail, a: DayActions) {
    val nowIndex = rail.past.size.coerceAtLeast(1)
    val list = rememberLazyListState(initialFirstVisibleItemIndex = (nowIndex - 1).coerceAtLeast(0))
    LazyColumn(state = list, modifier = Modifier.fillMaxSize().padding(start = 16.dp, end = 16.dp, top = 10.dp)) {
        if (rail.past.isEmpty()) item("empty-past") { Quiet("Nothing logged yet today.") }
        items(rail.past, key = { it.key }) { r -> RowView(r, solid = true, a) }
        item("now") { NowRow(now) }
        rail.next?.let { n -> item("next") { NextCard(n, a) } }
        items(rail.later, key = { it.key }) { r -> RowView(r, solid = false, a) }
        if (rail.anytime.isNotEmpty()) {
            item("anytime") { AnyTime() }
            items(rail.anytime, key = { it.key }) { r -> RowView(r, solid = false, a) }
        }
        if (rail.next == null) item("empty-ahead") { Quiet("Nothing planned for the rest of today.") }
        // Room for the composer, which floats over the day.
        item("foot") { Spacer(Modifier.fillParentMaxHeight(0.75f)) }
    }
}

/** A past day, or one ahead: its date and totals on top, then its rows. */
@Composable
private fun OtherDay(day: String, today: String, kind: DayKind, source: DaySource, rail: Rail?, totals: DayTotals?, a: DayActions) {
    LazyColumn(Modifier.fillMaxSize().padding(start = 16.dp, end = 16.dp, top = 14.dp)) {
        item("head") { DayHead(day, today, kind, source, totals) { a.onDay(today) } }
        when {
            source is DaySource.Loading -> items(3) { GhostRow() }
            source is DaySource.Failed -> item("failed") {
                Column(Modifier.padding(start = 4.dp, top = 14.dp)) {
                    Text("Couldn't read ${Day.cardDay(day)}.", style = DayType.meta.copy(fontSize = 13.sp))
                    Text("Try again", style = T.day.copy(fontSize = 13.5.sp, fontWeight = FontWeight.ExtraBold, color = C.brand), modifier = Modifier.padding(top = 4.dp).tap(onClick = source.retry))
                }
            }
            rail == null -> Unit
            kind == DayKind.Past -> {
                if (rail.past.isEmpty()) item("empty") { Quiet("Nothing logged on ${Day.cardDay(day)}.", start = 4.dp) }
                items(rail.past, key = { it.key }) { r -> RowView(r, solid = true, a) }
            }
            else -> {
                items(rail.later, key = { it.key }) { r -> RowView(r, solid = false, a) }
                if (rail.anytime.isNotEmpty()) {
                    item("anytime") { AnyTime() }
                    items(rail.anytime, key = { it.key }) { r -> RowView(r, solid = false, a) }
                }
                if (rail.later.isEmpty() && rail.anytime.isEmpty()) item("empty") { Quiet("Nothing due on ${Day.cardDay(day)}.", start = 4.dp) }
                item("plan-note") { Quiet("Meals are planned on the day.", start = if (rail.later.isEmpty() && rail.anytime.isEmpty()) 4.dp else TEXT_X) }
            }
        }
        item("foot") { Spacer(Modifier.fillParentMaxHeight(0.6f)) }
    }
}

/** The day, its totals counted from its rows, and the way back to today — its caret points the way today lies. */
@Composable
private fun DayHead(day: String, today: String, kind: DayKind, source: DaySource, totals: DayTotals?, onToday: () -> Unit) {
    Row(Modifier.fillMaxWidth().padding(start = 4.dp, bottom = 8.dp), verticalAlignment = Alignment.Top) {
        Column(Modifier.weight(1f)) {
            Text(Day.cardDay(day), style = T.day.copy(fontSize = 20.sp, fontWeight = FontWeight.ExtraBold, lineHeight = 26.sp))
            val line = when {
                kind == DayKind.Ahead -> if (day == Day.addDays(today, 1)) "Tomorrow" else null
                source !is DaySource.Ready || totals == null -> "— spent · — protein · — tasks done"
                else -> "${totals.spent} · ${totals.protein} · ${totals.tasksDone}"
            }
            if (line != null) Text(line, style = DayType.meta.copy(fontSize = 12.5.sp, lineHeight = 17.sp), modifier = Modifier.padding(top = 1.dp))
        }
        Row(
            Modifier.clip(CircleShape).background(C.brandTint).tap(onClick = onToday)
                .semantics { contentDescription = "Back to today" }
                .padding(start = if (kind == DayKind.Past) 14.dp else 10.dp, end = if (kind == DayKind.Past) 10.dp else 14.dp, top = 8.dp, bottom = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            if (kind == DayKind.Ahead) Glyph(PhBold.caretLeft, 11.dp, C.brand)
            Text("Today", style = T.day.copy(fontSize = 13.5.sp, fontWeight = FontWeight.ExtraBold, color = C.brand))
            if (kind == DayKind.Past) Glyph(PhBold.caretRight, 11.dp, C.brand)
        }
    }
}

/** A row standing in while a day of an earlier month is read: grey shapes, no figures. */
@Composable
private fun GhostRow() {
    Row(Modifier.fillMaxWidth().railLine(true, C.line).padding(vertical = 7.dp), verticalAlignment = Alignment.CenterVertically) {
        Text("—", style = DayType.time, modifier = Modifier.width(TIME_W))
        Spacer(Modifier.width(GAP))
        Box(Modifier.size(NODE).background(C.lineSoft, CircleShape))
        Spacer(Modifier.width(GAP))
        Box(Modifier.width(140.dp).height(12.dp).background(C.lineSoft, CircleShape))
    }
}

private val SHEET = RoundedCornerShape(topStart = 32.dp, topEnd = 32.dp)

/** Weeks the strip can swipe to: a year back, eight weeks ahead. */
private const val WEEKS_BACK = 52
private const val WEEKS_AHEAD = 8

/**
 * The week, Monday first, swiped left and right a week at a time; it opens on
 * this week. The box on its left names the month of the week showing. Today
 * is in Jamun; the picked day, when it is another, is a ring. Tapping a day
 * shows it; the strip follows when the day changes from outside (*Today*).
 */
@Composable
private fun WeekStrip(today: String, selected: String, onDay: (String) -> Unit) {
    val thisMonday = Day.addDays(today, -Day.weekIndex(today))
    val pager = rememberPagerState(initialPage = WEEKS_BACK) { WEEKS_BACK + 1 + WEEKS_AHEAD }
    val pickedPage = WEEKS_BACK + Math.floorDiv(
        java.time.temporal.ChronoUnit.DAYS.between(java.time.LocalDate.parse(thisMonday), java.time.LocalDate.parse(selected)).toInt(), 7,
    )
    LaunchedEffect(pickedPage) {
        val target = pickedPage.coerceIn(0, WEEKS_BACK + WEEKS_AHEAD)
        if (pager.currentPage != target) pager.animateScrollToPage(target)
    }
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
                            .clip(RoundedCornerShape(16.dp))
                            .tap { onDay(iso) }
                            .semantics {
                                contentDescription = "$name ${Day.dayOfMonth(iso)} ${Day.monthName(iso)}" +
                                    (if (isToday) ", today" else "") + (if (isPicked) ", showing" else "")
                            },
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
private fun Modifier.railLine(solid: Boolean, color: Color = C.border) = drawBehind {
    val x = LINE_X.toPx()
    drawLine(
        color = color, start = Offset(x, 0f), end = Offset(x, size.height), strokeWidth = 3.dp.toPx(), cap = StrokeCap.Butt,
        pathEffect = if (solid) null else PathEffect.dashPathEffect(floatArrayOf(7.dp.toPx(), 6.dp.toPx())),
    )
}

private fun Modifier.dashedLine() = railLine(false)

@Composable
private fun AnyTime() {
    Text("Any time", style = DayType.label, modifier = Modifier.dashedLine().padding(start = TEXT_X, top = 14.dp, bottom = 4.dp))
}

/** A done row's node is solid with a white glyph; a planned one is the mist stop with the glyph in colour. */
@Composable
private fun Node(r: RailRow, onClick: () -> Unit) {
    val t = toneOf(r.sheet)
    Box(
        Modifier
            .size(NODE)
            .background(C.white, CircleShape)
            .clip(CircleShape)
            .background(if (r.done) t.base else t.mist)
            .tap(onClick = onClick),
        contentAlignment = Alignment.Center,
    ) { Glyph(glyphOf(r), 21.dp, if (r.done) C.white else t.base) }
}

@Composable
internal fun AmberDot(end: Dp = 5.dp) = Box(Modifier.padding(end = end).size(6.dp).background(C.amber, CircleShape))

/**
 * One moment: its time, its node on the line, the title, and on the right its
 * figure — or, for a task, a round box that ticks it. Tapping it opens its
 * sheet on this row.
 */
@Composable
private fun RowView(r: RailRow, solid: Boolean, a: DayActions) {
    val open = { a.onRow(r) }
    val t = toneOf(r.sheet)
    // The same space above and below every row: a two-line title makes its row taller, never the gap uneven.
    Row(Modifier.fillMaxWidth().railLine(solid).padding(vertical = 7.dp), verticalAlignment = Alignment.CenterVertically) {
        Text(r.time, style = DayType.time, maxLines = 1, modifier = Modifier.width(TIME_W))
        Spacer(Modifier.width(GAP))
        Node(r, open)
        Spacer(Modifier.width(GAP))
        Column(Modifier.weight(1f).tap(onClick = open)) {
            Text(
                r.title,
                style = DayType.title.copy(color = when { solid -> C.muted; r.done -> C.faint; else -> C.ink }),
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
internal fun TaskBox(done: Boolean, color: Color, title: String, onToggle: () -> Unit) {
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
 * A picture from the web — a dish's, a workout's, an exercise's — or, while
 * it loads, when there is none or when it fails, the glyph on the same tile.
 * A picture is never load-bearing.
 */
@Composable
internal fun Picture(url: String?, glyph: ImageVector, tone: DayTone, size: Dp, corner: Dp, label: String, modifier: Modifier = Modifier) {
    val shape = RoundedCornerShape(corner)
    val fallback: @Composable () -> Unit = {
        Box(Modifier.size(size).background(tone.mist, shape), contentAlignment = Alignment.Center) { Glyph(glyph, size * 0.4f, tone.base) }
    }
    Box(modifier.size(size).clip(shape).background(tone.mist).semantics { contentDescription = label }) {
        if (url.isNullOrBlank()) fallback()
        else SubcomposeAsyncImage(
            model = url, contentDescription = null, contentScale = ContentScale.Crop, modifier = Modifier.size(size),
            loading = { fallback() }, error = { fallback() },
        )
    }
}

/** A plan meal's macros, short: `P 46 · 720 kcal · C 84 · F 18`. A macro the plan does not carry is a dash. */
internal fun shortMacros(p: Double, kcal: Int, c: Double?, f: Double?) =
    "P ${Fmt.jsRound(p)} · ${Fmt.indian(kcal)} kcal · C ${c?.let { Fmt.jsRound(it).toString() } ?: "—"} · F ${f?.let { Fmt.jsRound(it).toString() } ?: "—"}"

/**
 * The one open card: the first thing still ahead, in one shape for every
 * kind — the mode's tint, the badge, the picture on the left when the item has
 * one, the name, one short line, one button and at most one link.
 * `spec/home-day-rail.md` § The Up next card.
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
        Box(Modifier.padding(top = 8.dp)) { Node(r) { a.onRow(r) } }
        Spacer(Modifier.width(GAP))
        Column(
            Modifier
                .weight(1f)
                .padding(top = 4.dp, bottom = 12.dp)
                .clip(RoundedCornerShape(24.dp))
                .background(t.tint)
                .tap { a.onRow(r) }
                .padding(12.dp),
        ) {
            val picture = when (r.kind) {
                RailKind.PlanMeal -> r.planMeal?.imageUrl
                RailKind.Workout -> r.workout?.imageUrl
                else -> null
            }
            val hasPicture = r.kind == RailKind.PlanMeal || r.kind == RailKind.Workout
            val badge = when (r.kind) {
                RailKind.PlanMeal -> "Up next · ${r.sub ?: "Meal"}"
                RailKind.Workout -> "Up next · Workout"
                RailKind.Task -> "Up next · Task"
                RailKind.Schedule -> "Up next · Reminder"
                else -> "Up next"
            }
            val line: String? = when (r.kind) {
                RailKind.PlanMeal -> r.planMeal?.let { shortMacros(it.protein, it.kcal, it.carbs, it.fat) }
                RailKind.Workout -> r.workout?.let { w ->
                    listOfNotNull(w.minutes?.let { "$it min" }, w.exercises.size.takeIf { it > 0 }?.let { if (it == 1) "1 exercise" else "$it exercises" })
                        .joinToString(" · ").ifEmpty { null }
                }
                RailKind.Task -> listOfNotNull(r.sub, r.taskSource?.let { "from $it" }).joinToString(" · ").ifEmpty { null }
                RailKind.Schedule -> listOfNotNull(r.repeat, r.blurb).joinToString(" · ").ifEmpty { null }
                else -> null
            }
            Row(verticalAlignment = Alignment.Top) {
                if (hasPicture) {
                    Picture(picture, glyphOf(r), t, 60.dp, 14.dp, r.title, Modifier.padding(end = 10.dp))
                }
                Column(Modifier.weight(1f)) {
                    Box(Modifier.clip(CircleShape).background(C.white).padding(horizontal = 9.dp, vertical = 3.dp)) {
                        Text(badge, style = T.day.copy(fontSize = 11.sp, fontWeight = FontWeight.ExtraBold, color = t.ink), maxLines = 1)
                    }
                    Text(
                        r.title, style = DayType.title.copy(fontWeight = FontWeight.Bold, lineHeight = 19.sp),
                        maxLines = 2, overflow = TextOverflow.Ellipsis, modifier = Modifier.padding(top = 5.dp),
                    )
                    if (line != null || r.late != null) {
                        Row(Modifier.padding(top = 3.dp), verticalAlignment = Alignment.CenterVertically) {
                            if (r.estimate) AmberDot()
                            if (line != null) Text(line, style = DayType.meta.copy(color = t.ink), maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f, fill = false))
                            if (r.late != null) Text(" · ${r.late}", style = DayType.meta.copy(fontWeight = FontWeight.Bold, color = C.red), maxLines = 1)
                        }
                    }
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
                    when (r.kind) {
                        RailKind.PlanMeal -> Link("Something else") { a.onSheet(DaySheet.Diet) }
                        RailKind.Workout -> Link("See the session") { a.onRow(r) }
                        else -> Unit
                    }
                }
            }
        }
    }
}

@Composable
private fun Link(text: String, onClick: () -> Unit) =
    Text(text, style = T.day.copy(fontSize = 14.sp, fontWeight = FontWeight.Bold, color = C.brand), modifier = Modifier.tap(onClick = onClick))

@Composable
private fun Quiet(text: String, start: Dp = TEXT_X) {
    Text(text, style = DayType.meta.copy(fontSize = 13.sp), modifier = Modifier.padding(start = start, top = 14.dp, bottom = 14.dp))
}
