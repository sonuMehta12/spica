package com.sonu.spica.ui.common

import android.content.Intent
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.net.toUri
import com.sonu.spica.data.Project
import com.sonu.spica.data.Todo
import com.sonu.spica.ui.theme.C
import com.sonu.spica.ui.theme.T

/* ─── habits ──────────────────────────────────────────────────────────── */

/** What kind of thing a habit is — the strip's one opinion. Port of `HabitIcon.tsx`. */
private enum class Nature { Build, Harm, Ease, Neutral }

data class Tone3(val ink: Color, val bg: Color, val line: Color)

private fun tone(n: Nature) = when (n) {
    // A coin on the Diet card draws in the Diet card's own hue; harm in red.
    Nature.Build -> Tone3(C.dietInk, C.dietTint, C.dietSoft)
    Nature.Harm -> Tone3(C.red, C.redTint, C.redBorder)
    Nature.Ease -> Tone3(C.muted, C.lineSoft, C.border)
    Nature.Neutral -> Tone3(C.muted, C.white, C.border)
}

/** Which Phosphor glyph a habit's name asks for, and what kind of habit it is. */
private val GLYPHS: List<Triple<Regex, String, Nature>> = listOf(
    Triple(Regex("workout|gym|lift", RegexOption.IGNORE_CASE), "barbell", Nature.Build),
    Triple(Regex("smok|cigg?|sutta", RegexOption.IGNORE_CASE), "cigarette", Nature.Harm),
    Triple(Regex("beer|alcohol|drink|daru", RegexOption.IGNORE_CASE), "beer-stein", Nature.Ease),
    Triple(Regex("run|daud", RegexOption.IGNORE_CASE), "sneaker-move", Nature.Build),
    Triple(Regex("meditat|dhyan|yoga", RegexOption.IGNORE_CASE), "flower-lotus", Nature.Build),
    Triple(Regex("fast|vrat", RegexOption.IGNORE_CASE), "moon", Nature.Build),
)

private fun match(habit: String) = GLYPHS.firstOrNull { it.first.containsMatchIn(habit) }

fun habitTone(habit: String): Tone3 = tone(match(habit)?.third ?: Nature.Neutral)

/** The habit's Phosphor glyph, when its name asks for one — for coins drawn larger than the chain's. */
fun habitGlyph(habit: String) = match(habit)?.let { PhFill.of(it.second) }

/** A tinted coin with a border, so stacked icons read as separate coins. */
@Composable
fun HabitIcon(habit: String, size: Dp = 15.dp) {
    val glyph = match(habit)?.let { PhFill.of(it.second) }
    val t = habitTone(habit)
    Box(
        Modifier.size(size).background(t.bg, CircleShape).border(1.2.dp, t.line, CircleShape),
        contentAlignment = Alignment.Center,
    ) {
        if (glyph != null) Glyph(glyph, size - 5.dp, t.ink)
        else Text(habit.take(1).uppercase(), style = T.sans.copy(fontSize = 8.sp, color = t.ink, lineHeight = 8.sp))
    }
}

/* ─── projects ────────────────────────────────────────────────────────── */

/**
 * The icons a project can carry, by the key stored on it (`icon:<key>`) →
 * the Phosphor glyph drawn. Keys are data and never change; the glyph can.
 */
val PROJECT_ICONS: Map<String, String> = linkedMapOf(
    "briefcase" to "briefcase", "code" to "code", "home" to "house", "heart" to "heart",
    "book" to "book-open", "cart" to "shopping-cart", "rocket" to "rocket", "star" to "star",
    "bolt" to "lightning", "leaf" to "leaf", "chat" to "chat-circle", "money" to "money",
    "globe" to "globe", "tool" to "wrench", "person" to "user", "flag" to "flag",
)

/**
 * A project's mark: an emoji, one of the app's own icons, or its first letter.
 * A name the app does not know draws the letter — the contract, not an edge case.
 */
@Composable
fun ProjectIcon(project: Project?, size: Dp = 16.dp) {
    val tint = C.hex(project?.color)
    val icon = project?.icon
    val named = icon?.takeIf { it.startsWith("icon:") }?.let { PROJECT_ICONS[it.removePrefix("icon:")] }?.let { PhFill.of(it) }
    when {
        named != null -> Glyph(named, size, tint)
        icon != null && !icon.startsWith("icon:") -> Box(Modifier.size(size), contentAlignment = Alignment.Center) {
            Text(icon, style = T.sans.copy(fontSize = (size.value * 0.85f).sp, lineHeight = (size.value).sp))
        }
        else -> Box(
            Modifier.size(size).background(tint, RoundedCornerShape(size * 0.28f)),
            contentAlignment = Alignment.Center,
        ) {
            Text(
                (project?.name ?: "?").trim().take(1).uppercase(),
                style = T.sans.copy(fontSize = (size.value * 0.6f).sp, lineHeight = (size.value * 0.6f).sp, fontWeight = FontWeight.SemiBold, color = C.white),
            )
        }
    }
}

/* ─── the tracker reminder ────────────────────────────────────────────── */

/**
 * The one thing Spica asks after a tracker's task is ticked: move it there.
 * It names the stage the issue is in, never the one after — Spica does not
 * know a team's order. Port of `MoveReminder.tsx`.
 */
@Composable
fun MoveReminder(task: Todo, indent: Dp) {
    if (!task.done || !task.awaitingMove) return
    val ask = "move it forward in ${task.origin ?: "the tracker"}"
    val context = LocalContext.current
    Row(
        Modifier.padding(start = indent, end = 4.dp, bottom = 5.dp),
        horizontalArrangement = Arrangement.spacedBy(5.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        task.stage?.let { Text("$it ·", style = T.mono.copy(fontSize = 9.5.sp, color = C.faint), maxLines = 1) }
        if (task.link != null) {
            Row(
                Modifier.weight(1f, fill = false).tap { context.startActivity(Intent(Intent.ACTION_VIEW, task.link.toUri())) },
                horizontalArrangement = Arrangement.spacedBy(2.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(ask, style = T.sans.copy(fontSize = 11.5.sp, color = C.brand), maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f, fill = false))
                Glyph(Ph.arrowUpRight, 12.dp, C.brand)
            }
        } else {
            Text(ask, style = T.sans.copy(fontSize = 11.5.sp))
        }
    }
}
