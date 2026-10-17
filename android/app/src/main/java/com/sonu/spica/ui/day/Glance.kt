package com.sonu.spica.ui.day

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.paneTitle
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.sonu.spica.data.NudgeRow
import com.sonu.spica.lib.Day
import com.sonu.spica.logic.DaySheet
import com.sonu.spica.logic.KeyNumber
import com.sonu.spica.state.Load
import com.sonu.spica.ui.common.Glyph
import com.sonu.spica.ui.common.Ph
import com.sonu.spica.ui.common.PhFill
import com.sonu.spica.ui.common.RoundIcon
import com.sonu.spica.ui.common.plainTap
import com.sonu.spica.ui.common.tap
import com.sonu.spica.ui.theme.C
import com.sonu.spica.ui.theme.S
import com.sonu.spica.ui.theme.T

/**
 * Today at a glance, slid in from the right by the caret where the bell was:
 * the six key numbers, then the nudges. A tile opens its widget; a nudge, its
 * page. The day stays drawn under it, a strip of it showing; a tap there
 * closes the panel. `spec/home-day-rail.md` § The glance panel.
 */
@Composable
fun GlancePanel(
    open: Boolean, todayIso: String, now: String, numbers: List<KeyNumber>, nudges: List<NudgeRow>, nudgesLoad: Load,
    onClose: () -> Unit, onNumber: (DaySheet) -> Unit, onNudge: (NudgeRow) -> Unit, onAllNudges: () -> Unit,
) {
    Box(Modifier.fillMaxSize()) {
        AnimatedVisibility(open, enter = fadeIn(tween(220)), exit = fadeOut(tween(200))) {
            Box(Modifier.fillMaxSize().background(C.shadow.copy(alpha = 0.32f)).plainTap(onClick = onClose))
        }
        BoxWithConstraints(Modifier.fillMaxSize(), contentAlignment = Alignment.CenterEnd) {
            val width = maxWidth - 38.dp
            AnimatedVisibility(
                open,
                enter = slideInHorizontally(tween(320)) { it },
                exit = slideOutHorizontally(tween(260)) { it },
            ) {
                Column(
                    Modifier
                        .width(width)
                        .fillMaxHeight()
                        .then(S.popover(PANEL))
                        .clip(PANEL)
                        .background(C.white)
                        .semantics { paneTitle = "Today at a glance" }
                        .statusBarsPadding()
                        .navigationBarsPadding()
                        .verticalScroll(rememberScrollState())
                        .padding(horizontal = 18.dp),
                ) {
                    Row(Modifier.padding(top = 14.dp), verticalAlignment = Alignment.CenterVertically) {
                        RoundIcon(Ph.caretRight, onClose, "Close")
                        Spacer(Modifier.width(12.dp))
                        Column {
                            Text("Today so far", style = T.day.copy(fontSize = 21.sp, fontWeight = FontWeight.ExtraBold, letterSpacing = (-0.4).sp))
                            Text("${Day.cardDay(todayIso)} · $now", style = T.day.copy(fontSize = 12.sp, fontWeight = FontWeight.Medium, color = C.faint))
                        }
                    }
                    Column(Modifier.padding(top = 14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        numbers.chunked(2).forEach { pair ->
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                pair.forEach { k -> Tile(k, Modifier.weight(1f)) { onNumber(k.sheet) } }
                                if (pair.size == 1) Spacer(Modifier.weight(1f))
                            }
                        }
                    }
                    Row(Modifier.padding(top = 22.dp, bottom = 8.dp, start = 4.dp), verticalAlignment = Alignment.Bottom) {
                        Text("Nudges", style = T.day.copy(fontSize = 15.sp, fontWeight = FontWeight.ExtraBold))
                    }
                    when {
                        nudges.isNotEmpty() -> Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            nudges.forEach { n -> NudgeCard(n, todayIso) { onNudge(n) } }
                        }
                        nudgesLoad == Load.Loaded -> Quiet("Nothing waiting. When Spica has something for you, it lands here.")
                        nudgesLoad == Load.Failed -> Quiet("Nudges could not load. They will try again when you next open this.")
                        else -> Quiet("—")
                    }
                    Text(
                        "All nudges", style = T.day.copy(fontSize = 13.5.sp, fontWeight = FontWeight.ExtraBold, color = C.brand),
                        modifier = Modifier.padding(top = 16.dp, start = 4.dp, bottom = 28.dp).tap(onClick = onAllNudges),
                    )
                }
            }
        }
    }
}

private val PANEL = RoundedCornerShape(topStart = 32.dp, bottomStart = 32.dp)

/** A key number: big in its mode's ink, one grey line under it — red only when something is late or over. */
@Composable
private fun Tile(k: KeyNumber, modifier: Modifier, onClick: () -> Unit) {
    val t = toneOf(k.sheet)
    Column(
        modifier
            .clip(RoundedCornerShape(20.dp))
            .background(C.lineSoft)
            .tap(onClick = onClick)
            .semantics(mergeDescendants = true) { contentDescription = "${k.value} ${k.label}" }
            .padding(horizontal = 12.dp, vertical = 10.dp),
    ) {
        Text(k.value, style = T.day.copy(fontSize = 18.sp, fontWeight = FontWeight.ExtraBold, letterSpacing = (-0.3).sp, color = if (k.value == "—") C.faint else t.ink), maxLines = 1)
        Text(
            k.label, maxLines = 1, overflow = TextOverflow.Ellipsis,
            style = T.day.copy(fontSize = 12.sp, fontWeight = if (k.labelIsLate) FontWeight.Bold else FontWeight.Medium, color = if (k.labelIsLate) C.red else C.faint),
        )
    }
}

/** A nudge as a card: what it is about, its line, when — and a Jamun dot while it is unopened. */
@Composable
private fun NudgeCard(n: NudgeRow, today: String, onClick: () -> Unit) {
    val (glyph, tone) = when (n.kind) {
        "meals", "dinner" -> PhFill.bowlFood to toneOf(DaySheet.Diet)
        "workout" -> PhFill.barbell to toneOf(DaySheet.Activity)
        "day" -> PhFill.checkSquare to toneOf(DaySheet.Work)
        else -> PhFill.bell to toneOf(DaySheet.Habits)
    }
    Row(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(22.dp)).background(C.lineSoft).tap(onClick = onClick).padding(12.dp),
        verticalAlignment = Alignment.Top,
    ) {
        Box(Modifier.size(34.dp).clip(CircleShape).background(tone.base), contentAlignment = Alignment.Center) { Glyph(glyph, 15.dp, C.white) }
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(com.sonu.spica.logic.DayRail.title(n.title), style = T.day.copy(fontSize = 14.sp, fontWeight = FontWeight.ExtraBold, lineHeight = 18.sp), modifier = Modifier.weight(1f), maxLines = 2, overflow = TextOverflow.Ellipsis)
                if (!n.seen) Box(Modifier.padding(start = 6.dp).size(7.dp).background(C.brand, CircleShape).semantics { contentDescription = "New" })
                Text(if (n.day == today) "Today" else Day.shortDay(n.day), style = T.day.copy(fontSize = 12.sp, fontWeight = FontWeight.Medium, color = C.faint), modifier = Modifier.padding(start = 6.dp))
            }
            if (!n.line.isNullOrBlank()) {
                Text(com.sonu.spica.logic.DayRail.cap(n.line), style = T.day.copy(fontSize = 12.5.sp, fontWeight = FontWeight.Medium, lineHeight = 17.sp, color = C.muted), modifier = Modifier.padding(top = 2.dp), maxLines = 3, overflow = TextOverflow.Ellipsis)
            }
        }
    }
}

@Composable
private fun Quiet(text: String) {
    Box(Modifier.fillMaxWidth().clip(RoundedCornerShape(22.dp)).background(C.lineSoft).padding(16.dp)) {
        Text(text, style = T.day.copy(fontSize = 13.sp, fontWeight = FontWeight.Medium, color = C.muted))
    }
}

