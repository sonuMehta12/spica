package com.sonu.spica.ui.nudges

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.sonu.spica.data.NudgeRow
import com.sonu.spica.lib.Day
import com.sonu.spica.state.AppState
import com.sonu.spica.state.SpicaViewModel
import com.sonu.spica.state.Load
import com.sonu.spica.ui.common.Back
import com.sonu.spica.ui.common.Coin
import com.sonu.spica.ui.common.Glyph
import com.sonu.spica.ui.common.Ground
import com.sonu.spica.ui.common.MenuItem
import com.sonu.spica.ui.common.MenuRow
import com.sonu.spica.ui.common.PageHeader
import com.sonu.spica.ui.common.Panel
import com.sonu.spica.ui.common.Ph
import com.sonu.spica.ui.common.Popover
import com.sonu.spica.ui.common.SectionLabel
import com.sonu.spica.ui.common.Spinner
import com.sonu.spica.ui.common.Tag
import com.sonu.spica.ui.common.TopFade
import com.sonu.spica.ui.common.fadeUp
import com.sonu.spica.ui.common.panel
import com.sonu.spica.ui.common.plainTap
import com.sonu.spica.ui.common.tap
import com.sonu.spica.ui.theme.C
import com.sonu.spica.ui.theme.T
import java.time.ZoneId

/*
 * Nudges — what Spica prepared without being asked, behind the bell.
 * `spec/in-progress/nudges.md`. The thread stays a conversation the person
 * starts: a nudge lives here, and enters Chat only through *Ask about this*.
 */

/** A nudge's identity: its icon in its mode's ink on its mode's tint. Neutral where it has no mode. */
private data class Look(val icon: ImageVector, val ink: Color, val tint: Color)

private fun lookOf(kind: String) = when (kind) {
    "day" -> Look(Ph.sunHorizon, C.brand, C.brandTint)
    "meals", "dinner" -> Look(Ph.forkKnife, C.dietInk, C.dietTint)
    "workout" -> Look(Ph.barbell, C.dietInk, C.dietTint)
    "reminder" -> Look(Ph.bellRinging, C.ink, Ground)
    "review" -> Look(Ph.receipt, C.paisaInk, C.paisaTint)
    else -> Look(Ph.bell, C.ink, C.surface)
}

/** The day a nudge belongs to: its `local_day`, else the day its stamp falls on here. */
internal fun dayOf(n: NudgeRow, today: String): String =
    n.day.takeIf { it.length >= 10 } ?: n.created?.atZone(ZoneId.systemDefault())?.toLocalDate()?.toString() ?: today

/** "8:00" — the 24-hour clock Daily runs are set in, for today's. */
internal fun clockOf(n: NudgeRow): String? =
    n.created?.atZone(ZoneId.systemDefault())?.let { "${it.hour}:${it.minute.toString().padStart(2, '0')}" }

/** "10:30 pm", for a day that is not today. */
private fun ampm(n: NudgeRow): String? = n.created?.atZone(ZoneId.systemDefault())?.let {
    val h = if (it.hour % 12 == 0) 12 else it.hour % 12
    "$h:${it.minute.toString().padStart(2, '0')} ${if (it.hour < 12) "am" else "pm"}"
}

/** When it came: "8:00" today, "Yesterday, 10:30 pm", "6 Oct, 10:30 pm" before that. */
private fun whenOf(n: NudgeRow, today: String): String {
    val day = dayOf(n, today)
    if (day == today) return clockOf(n) ?: ""
    val date = if (runCatching { Day.diffDays(day, today) }.getOrNull() == 1) "Yesterday" else Day.shortDay(day)
    return listOfNotNull(date, ampm(n)).joinToString(", ")
}

/** One run's nudges share a stamp; within it they read as the brief does — Your day leads. */
private val KIND_ORDER = listOf("day", "meals", "workout", "dinner", "review", "reminder")

private val newestFirst = compareByDescending<NudgeRow> { it.created }
    .thenBy { KIND_ORDER.indexOf(it.kind).let { i -> if (i < 0) KIND_ORDER.size else i } }

/**
 * The second line when the nudge kept none — worked out from the live plan as
 * the card is drawn, never stored: a sentence about meals goes stale by lunch.
 * Only today's Meals today has one: the slots still ahead, or done. A plan not
 * read yet says nothing.
 */
private fun liveLineOf(n: NudgeRow, s: AppState): String? {
    if (n.kind != "meals" || dayOf(n, s.todayIso) != s.todayIso) return null
    val p = s.plan?.takeIf { it.available } ?: return null
    val ahead = p.meals.filter { "meal:${it.slot}" !in s.planDone }.map { it.slot.lowercase() }
    if (p.done || ahead.isEmpty()) return "Today's meals are done"
    val slots = if (ahead.size == 1) ahead[0] else ahead.dropLast(1).joinToString(", ") + " and " + ahead.last()
    return slots.replaceFirstChar { it.uppercase() } + " planned"
}

/** The run that made a nudge, as Daily runs shows it: "From Your day · daily at 08:00". Unknown, nothing — never a guess. */
private fun runOf(n: NudgeRow, s: AppState): String? = n.scheduleId?.let { sid ->
    s.schedules.firstOrNull { it.id == sid }?.let { "From ${it.label} · ${it.repeat} at ${it.at}" }
}

/** A title the server left blank, from its kind — never an empty card. */
internal fun titleOf(n: NudgeRow) = n.title.ifBlank {
    when (n.kind) {
        "day" -> "Your day"
        "meals" -> "Meals today"
        "workout" -> "Workout"
        "dinner" -> "Dinner check"
        "reminder" -> "Reminder"
        "review" -> "Payments to check"
        else -> "Nudge"
    }
}

/**
 * The bell's page: Today first, then Earlier — the six days before it. One
 * card per nudge not put away. Today's open their pages; Earlier's are
 * history, read-only, as their day has gone. At the foot, the way to change
 * when they come — Daily runs, pushed over this page, whose ← comes back here.
 */
@Composable
fun NudgesPage(vm: SpicaViewModel, s: AppState, back: Back) {
    val today = s.todayIso
    val shown = s.nudges.filter { n ->
        !n.dismissed && runCatching { Day.diffDays(dayOf(n, today), today) in 0..6 }.getOrDefault(false)
    }.sortedWith(newestFirst)
    val todays = shown.filter { dayOf(it, today) == today }
    val earlier = shown.filter { dayOf(it, today) != today }

    Box(Modifier.fillMaxSize().background(Ground).plainTap { }) {
        Column(Modifier.fillMaxSize().statusBarsPadding().padding(top = 8.dp).fadeUp(280)) {
            PageHeader(null, "Nudges", back, sub = "What Spica got ready, without being asked")
            Box(Modifier.weight(1f)) {
                Column(
                    Modifier
                        .fillMaxSize()
                        .verticalScroll(rememberScrollState())
                        .navigationBarsPadding()
                        .padding(start = 16.dp, end = 16.dp, top = 4.dp, bottom = 28.dp),
                ) {
                    // Unknown is not zero: "Nothing yet" only when the server answered with none.
                    if (shown.isEmpty()) when (s.nudgesLoad) {
                        Load.Loading -> EmptyCard({ Box(Modifier.size(40.dp).background(C.surface, CircleShape), contentAlignment = Alignment.Center) { Spinner() } }) {
                            Text("Loading…", style = EmptyStyle)
                        }
                        Load.Failed -> EmptyCard({ Coin(Ph.bell, C.ink, C.surface, 40.dp) }) {
                            Text("Couldn't load nudges.", style = EmptyStyle)
                            Text(
                                "Try again",
                                style = EmptyStyle.copy(fontWeight = FontWeight.Medium, color = C.brand),
                                modifier = Modifier.padding(top = 1.dp).clip(RoundedCornerShape(4.dp)).tap(onClick = vm::retryNudges).padding(vertical = 3.dp),
                            )
                        }
                        Load.Loaded -> EmptyCard({ Coin(Ph.sunHorizon, C.brand, C.brandTint, 40.dp) }) {
                            Text("Nothing yet. Your day arrives each morning — change when in Daily runs.", style = EmptyStyle)
                        }
                    }
                    if (todays.isNotEmpty()) {
                        SectionLabel("Today")
                        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                            todays.forEach { n -> NudgeCard(vm, s, n, onOpen = { vm.openNudge(n) }) }
                        }
                    }
                    if (earlier.isNotEmpty()) {
                        SectionLabel("Earlier")
                        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                            earlier.forEach { n -> NudgeCard(vm, s, n, onOpen = null) }
                        }
                    }
                    Column(Modifier.fillMaxWidth().padding(top = 26.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                        Text(
                            "Change when nudges come",
                            style = T.sans.copy(fontSize = 14.sp, lineHeight = 18.sp, fontWeight = FontWeight.Medium, color = C.brand),
                            modifier = Modifier.tap(onClick = vm::openDailyRuns).padding(horizontal = 10.dp, vertical = 6.dp),
                        )
                        Text("Each one is a Daily run in Profile", style = T.sans.copy(fontSize = 12.sp, lineHeight = 16.sp, color = C.faint))
                    }
                }
                TopFade()
            }
        }
    }
}

private val EmptyStyle = T.sans.copy(fontSize = 15.sp, lineHeight = 21.sp, color = C.muted)

/** The page with no cards to show: a coin, and why — still reading, could not, or none. */
@Composable
private fun EmptyCard(coin: @Composable () -> Unit, words: @Composable ColumnScope.() -> Unit) {
    Panel(Modifier.padding(top = 14.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(14.dp)) {
            coin()
            Column(Modifier.weight(1f), content = words)
        }
    }
}

private val CardShape = RoundedCornerShape(20.dp)

/**
 * One nudge: its coin, title and time, the line as it was said — in the
 * agent's serif, two lines at most — and a dot until it is opened. With no
 * line kept, Meals today's live line in the kit's face, muted — not the agent
 * speaking; with neither, the card is one line, centred on its coin. Done says
 * so. ⋮ names the run that made it, then Dismiss and Turn these off.
 * `onOpen` null is history: the card does not open.
 */
@Composable
private fun NudgeCard(vm: SpicaViewModel, s: AppState, n: NudgeRow, onOpen: (() -> Unit)?) {
    val today = s.todayIso
    val look = lookOf(n.kind)
    val live = if (n.line == null) liveLineOf(n, s) else null
    val oneLine = n.line == null && live == null
    Row(
        Modifier
            .fillMaxWidth()
            .panel(CardShape)
            .then(if (onOpen != null) Modifier.tap(onClick = onOpen) else Modifier)
            .padding(start = 14.dp, top = 14.dp, bottom = 14.dp, end = 4.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
        verticalAlignment = if (oneLine) Alignment.CenterVertically else Alignment.Top,
    ) {
        Coin(look.icon, look.ink, look.tint, 36.dp)
        Column(Modifier.weight(1f).padding(top = if (oneLine) 0.dp else 1.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Row(Modifier.weight(1f), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(
                        titleOf(n),
                        style = T.sans.copy(fontSize = 16.sp, lineHeight = 20.sp, fontWeight = FontWeight.Medium),
                        maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f, fill = false),
                    )
                    if (n.done) Tag(if (n.kind == "meals" || n.kind == "dinner") "Logged" else "Done")
                }
                Text(whenOf(n, today), style = T.sans.copy(fontSize = 12.sp, lineHeight = 15.sp, color = C.faint), maxLines = 1)
                // Unopened, and still today's to open.
                if (!n.seen && onOpen != null) Box(Modifier.size(8.dp).background(C.brand, CircleShape))
            }
            n.line?.let {
                Text(it, style = T.agentVoice.copy(fontSize = 15.sp, lineHeight = 21.sp), maxLines = 2, overflow = TextOverflow.Ellipsis, modifier = Modifier.padding(top = 3.dp))
            }
            live?.let {
                Text(it, style = T.sans.copy(fontSize = 14.sp, lineHeight = 19.sp, color = C.muted), maxLines = 2, overflow = TextOverflow.Ellipsis, modifier = Modifier.padding(top = 3.dp))
            }
        }
        val items = buildList {
            runOf(n, s)?.let { add(MenuItem("run", it, info = true) {}) }
            add(MenuItem("dismiss", "Dismiss") { vm.dismissNudge(n.id) })
            if (n.scheduleId != null) add(MenuItem("off", "Turn these off") { vm.turnOffNudges(n) })
        }
        NudgeMenu(items)
    }
}

/** ⋮, and the menu it opens under itself. */
@Composable
private fun NudgeMenu(items: List<MenuItem>) {
    var open by remember { mutableStateOf(false) }
    Box {
        Box(Modifier.size(32.dp).clip(CircleShape).tap { open = true }, contentAlignment = Alignment.Center) {
            Glyph(Ph.dotsThreeVertical, 18.dp, C.faint, label = "More")
        }
        if (open) {
            Popover(onDismiss = { open = false }, alignment = Alignment.TopEnd, offset = IntOffset(0, with(LocalDensity.current) { 30.dp.roundToPx() }), minWidth = 150.dp) {
                items.forEach { MenuRow(it) { open = false } }
            }
        }
    }
}
