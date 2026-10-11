package com.sonu.spica.ui.commitments

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.sonu.spica.data.Commitment
import com.sonu.spica.lib.Fmt
import com.sonu.spica.state.SpicaViewModel
import com.sonu.spica.ui.chat.Fig
import com.sonu.spica.ui.common.Dot
import com.sonu.spica.ui.common.Glyph
import com.sonu.spica.ui.common.MenuItem
import com.sonu.spica.ui.common.MenuRow
import com.sonu.spica.ui.common.Ph
import com.sonu.spica.ui.common.Popover
import com.sonu.spica.ui.common.tap
import com.sonu.spica.ui.theme.C
import com.sonu.spica.ui.theme.T
import java.time.LocalDate
import java.time.format.TextStyle
import java.util.Locale

/*
 * One line of what is owed — the page's, and the chat card's, the same thing
 * drawn twice. `spec/done/commitments.md` § The surfaces. Paid and owed
 * are the server's; nothing here works out a figure it was not given, and no
 * sentence about the person's money is kept — every word below is drawn from
 * the row as it is now.
 */

/** 1 → 1st, 2 → 2nd, 11 → 11th. */
fun ordinal(n: Int): String {
    val suffix = if (n % 100 in 11..13) "th" else when (n % 10) { 1 -> "st"; 2 -> "nd"; 3 -> "rd"; else -> "th" }
    return "$n$suffix"
}

/** `2026-10-01` → `October`. */
fun monthName(iso: String): String =
    runCatching { LocalDate.parse(iso).month.getDisplayName(TextStyle.FULL, Locale.ENGLISH) }.getOrDefault(iso)

/** The weekday a line falls due on, this month — clamped to the month's last day, as the server clamps it. */
fun dueWeekday(dueDay: Int, todayIso: String): String {
    val today = LocalDate.parse(todayIso)
    val due = today.withDayOfMonth(minOf(dueDay, today.lengthOfMonth()))
    return if (due == today) "today" else due.dayOfWeek.getDisplayName(TextStyle.FULL, Locale.ENGLISH)
}

/** The lines as the page groups them: still open first, then settled, the skipped kept apart. */
data class Grouped(val open: List<Commitment>, val settled: List<Commitment>, val skipped: List<Commitment>)

fun group(items: List<Commitment>) = Grouped(
    open = items.filter { !it.skipped && !it.settled },
    settled = items.filter { !it.skipped && it.settled },
    skipped = items.filter { it.skipped },
)

/** What a line waits on, in words: its due day, `borrowed`, `this month only`, `from September`, `skipped this month`. */
fun commitmentSub(c: Commitment, withCarried: Boolean = false): String = listOfNotNull(
    if (withCarried) c.carriedFrom?.let { "from ${monthName(it)}" } else null,
    if (c.isBorrowing) "borrowed" else c.dueDay?.let { "due ${ordinal(it)}" },
    if (!c.isBorrowing && !c.repeats && c.carriedFrom == null && !c.skipped) "this month only" else null,
    if (c.skipped) "skipped this month" else null,
).joinToString(" · ")

/** What a line owes, in the words the page uses — `owed ₹1,950`, `₹50 paid · owed ₹1,950`, `paid ₹8,421`. */
fun standing(c: Commitment): String = when {
    c.skipped -> "skipped this month"
    c.settled -> "paid ${Fmt.rupees(c.paid)}" + if (c.over > 0) " · +${Fmt.rupees(c.over)}" else ""
    c.paid > 0 -> "${Fmt.rupees(c.paid)} paid · owed ${Fmt.rupees(c.owed)}"
    else -> "owed ${Fmt.rupees(c.owed)}"
}

/**
 * The line. Name (and the month a carried one comes from), then what it
 * waits on — its due day, or `borrowed`; on the right the amount with the
 * amber dot when it was copied from last month rather than stated, and what
 * it owes under it. Settled is struck. `menu` null draws no ⋮ — a past month,
 * and a borrowing, are read-only.
 */
@Composable
fun CommitmentRow(
    c: Commitment, menu: List<MenuItem>?, modifier: Modifier = Modifier, compact: Boolean = false,
    action: Pair<String, () -> Unit>? = null,
) {
    val struck = c.settled && !c.skipped
    val faint = c.skipped
    val ink = if (struck || faint) C.faint else C.ink
    Row(
        modifier.fillMaxWidth().alpha(if (c.pending) 0.6f else 1f).padding(start = if (compact) 0.dp else 18.dp, end = if (menu != null || action != null) 4.dp else if (compact) 0.dp else 18.dp, top = if (compact) 8.dp else 13.dp, bottom = if (compact) 8.dp else 13.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Column(Modifier.weight(1f)) {
            Text(
                buildAnnotatedString {
                    append(c.name)
                    c.carriedFrom?.let {
                        withStyle(SpanStyle(color = C.faint, fontWeight = FontWeight.Normal)) { append(" · from ${monthName(it)}") }
                    }
                },
                style = T.sans.copy(
                    fontSize = if (compact) 14.sp else 15.sp, lineHeight = 20.sp, fontWeight = FontWeight.Medium, color = ink,
                    textDecoration = if (struck) TextDecoration.LineThrough else null,
                ),
                maxLines = 2, overflow = TextOverflow.Ellipsis,
            )
            val sub = commitmentSub(c)
            if (sub.isNotEmpty()) Text(sub, style = T.sans.copy(fontSize = 12.sp, lineHeight = 16.sp, color = C.faint), modifier = Modifier.padding(top = 1.dp))
        }
        Column(horizontalAlignment = Alignment.End) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                // Amber: the amount was copied from last month, not said.
                if (c.rolled && !c.skipped) Dot()
                Fig(Fmt.rupees(c.expected), if (compact) 14.sp else 15.sp, ink, struck = struck)
            }
            Text(
                standing(c),
                style = T.sans.copy(fontSize = 12.sp, lineHeight = 16.sp, color = if (c.owed > 0 && !c.skipped) C.muted else C.faint, textAlign = TextAlign.End),
                maxLines = 1, modifier = Modifier.padding(top = 1.dp),
            )
        }
        if (menu != null) LineMenu(menu)
        else if (action != null) Text(
            action.first,
            style = T.sans.copy(fontSize = 13.5.sp, fontWeight = FontWeight.Medium, color = C.brand),
            modifier = Modifier.clip(RoundedCornerShape(6.dp)).tap(onClick = action.second).padding(horizontal = 6.dp, vertical = 6.dp),
        )
    }
}

/** ⋮, and the menu it opens under itself. */
@Composable
private fun LineMenu(items: List<MenuItem>) {
    var open by remember { mutableStateOf(false) }
    Box {
        Box(Modifier.size(32.dp).clip(CircleShape).tap { open = true }, contentAlignment = Alignment.Center) {
            Glyph(Ph.dotsThreeVertical, 18.dp, C.faint, label = "More")
        }
        if (open) {
            Popover(onDismiss = { open = false }, alignment = Alignment.TopEnd, offset = IntOffset(0, with(LocalDensity.current) { 30.dp.roundToPx() }), minWidth = 160.dp) {
                items.forEach { MenuRow(it) { open = false } }
            }
        }
    }
}

/** What a line's ⋮ can do — the view-model's, or nothing at all in the gallery. */
class CommitmentActions(
    val open: () -> Unit,
    val repay: () -> Unit,
    val edit: (Commitment) -> Unit,
    val skip: (Commitment) -> Unit,
    val repeat: (Commitment) -> Unit,
    val delete: (Commitment) -> Unit,
)

fun commitmentActions(vm: SpicaViewModel) = CommitmentActions(
    vm::openCommitments, vm::repayFromCommitments, vm::editCommitment, vm::skipCommitment, vm::repeatCommitment, vm::deleteCommitment,
)

/**
 * ⋮ on a line: Edit, Skip this month / Unskip, Stop repeating / Repeat,
 * Delete. A carried line is one-off by nature, so it has no Repeat. A
 * borrowing has none of these — its action is Repay.
 */
fun commitmentMenu(a: CommitmentActions, c: Commitment, askDelete: (Commitment) -> Unit): List<MenuItem>? {
    if (c.isBorrowing) return null
    return buildList {
        add(MenuItem("edit", "Edit") { a.edit(c) })
        add(MenuItem("skip", if (c.skipped) "Unskip" else "Skip this month") { a.skip(c) })
        if (c.carriedFrom == null) add(MenuItem("repeat", if (c.repeats) "Stop repeating" else "Repeat") { a.repeat(c) })
        add(MenuItem("delete", "Delete", color = C.red) { askDelete(c) })
    }
}

/**
 * Delete has no undo — the server ends the line, unlinks its payments and
 * stops it coming back — so it is asked first, in the words of what happens.
 */
@Composable
fun DeleteCommitmentDialog(c: Commitment, onConfirm: () -> Unit, onDismiss: () -> Unit) {
    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = C.white,
        title = { Text("Delete ${c.name}?", style = T.sans.copy(fontSize = 18.sp, fontWeight = FontWeight.SemiBold)) },
        text = {
            Text(
                "Its payments become ordinary spending. It will not come back next month.",
                style = T.sans.copy(fontSize = 14.sp, lineHeight = 20.sp, color = C.muted),
            )
        },
        confirmButton = {
            TextButton(onClick = { onConfirm(); onDismiss() }) {
                Text("Delete", style = T.sans.copy(fontSize = 14.sp, fontWeight = FontWeight.Medium, color = C.red))
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text("Cancel", style = T.sans.copy(fontSize = 14.sp, fontWeight = FontWeight.Medium, color = C.muted))
            }
        },
    )
}

/** What a page of lines says of itself: `3 of 6 commitments paid`. Null when there are none to count. */
fun coverage(paid: Int, open: Int): String? =
    if (open <= 0) null else "$paid of $open ${if (open == 1) "commitment" else "commitments"} paid"
