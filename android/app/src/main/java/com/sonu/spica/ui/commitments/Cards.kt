package com.sonu.spica.ui.commitments

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.sonu.spica.data.ChatMsg
import com.sonu.spica.data.Commitment
import com.sonu.spica.data.CommitmentsPage
import com.sonu.spica.data.ComposeContext
import com.sonu.spica.lib.Fmt
import com.sonu.spica.ui.chat.ConfirmActions
import com.sonu.spica.ui.chat.Fig
import com.sonu.spica.ui.chat.IconCoin
import com.sonu.spica.ui.chat.Quiet
import com.sonu.spica.ui.chat.QuietActions
import com.sonu.spica.ui.chat.ReceiptHead
import com.sonu.spica.ui.chat.FactChip
import com.sonu.spica.ui.common.AgentCard
import com.sonu.spica.ui.common.Dot
import com.sonu.spica.ui.common.Ph
import com.sonu.spica.ui.common.tap
import com.sonu.spica.ui.theme.C
import com.sonu.spica.ui.theme.T

/**
 * The live Commitments card — what the agent shows for *kya kya committed
 * hai*. It carries no rows: every line is read from the month's commitments as
 * the card is drawn, so an edit or a delete anywhere changes every card that
 * showed them, and the figure is never a sentence the agent wrote. Tapping the
 * heading opens the page; the ⋮ on a line is the page's.
 */
@Composable
fun CommitmentsCard(a: CommitmentActions, page: CommitmentsPage?) {
    var confirm by remember { mutableStateOf<Commitment?>(null) }
    AgentCard(padding = PaddingValues(start = 14.dp, end = 10.dp, top = 12.dp, bottom = 6.dp)) {
        Column {
            Row(
                Modifier.fillMaxWidth().clip(RoundedCornerShape(8.dp)).tap(onClick = a.open).padding(end = 4.dp, bottom = 4.dp),
                verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Text(
                    "Commitments" + (page?.let { " · ${monthName(it.month)}" } ?: ""),
                    style = T.sans.copy(fontSize = 13.sp, fontWeight = FontWeight.Medium, color = C.muted), modifier = Modifier.weight(1f),
                )
                // Nothing owed is said as nothing — never a ₹0.
                if (page != null && page.items.isNotEmpty()) Fig("${Fmt.rupees(page.owed)} owed", 14.sp)
                com.sonu.spica.ui.common.Glyph(com.sonu.spica.ui.common.PhBold.caretRight, 12.dp, C.faint)
            }
            when {
                page == null -> Text("Loading…", style = T.sans.copy(fontSize = 13.sp, color = C.faint), modifier = Modifier.padding(vertical = 8.dp))
                page.items.isEmpty() -> Text("No commitments yet", style = T.sans.copy(fontSize = 14.sp, color = C.muted), modifier = Modifier.padding(vertical = 8.dp))
                else -> {
                    val g = group(page.items)
                    (g.open + g.settled + g.skipped).forEachIndexed { i, c ->
                        CommitmentRow(
                            c, menu = if (page.editable) commitmentMenu(a, c) { confirm = it } else null,
                            modifier = Modifier.then(if (i > 0) Modifier.drawTopRule() else Modifier), compact = true,
                            action = if (c.isBorrowing) "Repay" to a.repay else null,
                        )
                    }
                    coverage(page.paidCount, page.openCount)?.let {
                        Text(it, style = T.sans.copy(fontSize = 12.sp, color = C.faint), modifier = Modifier.padding(top = 2.dp, bottom = 6.dp))
                    }
                }
            }
        }
    }
    confirm?.let { c -> DeleteCommitmentDialog(c, onConfirm = { a.delete(c) }, onDismiss = { confirm = null }) }
}

/** A hairline across the top of a line, so the lines read as a list. */
private fun Modifier.drawTopRule(): Modifier = drawBehind {
    drawLine(C.lineSoft, Offset(0f, 0f), Offset(size.width, 0f), 1.dp.toPx())
}

/**
 * A commitment the agent made, changed, skipped or deleted — the receipt. The
 * lede says what happened; the figure is the line's own, live, so a later edit
 * shows here. A guessed category wears the amber dot. Change attaches the line
 * to the composer, so the next sentence edits it; a deleted one is history and
 * has no tray.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun CommitmentReceipt(msg: ChatMsg.Confirm, live: Commitment?, ca: ConfirmActions) {
    val gone = msg.state == "deleted"
    fun field(k: String) = msg.fields.firstOrNull { it.key == k }
    val name = live?.name ?: field("name")?.value ?: msg.lede.substringBefore(" · ")
    val amount = live?.let { Fmt.rupees(it.expected) } ?: field("amount_paise")?.value
    ReceiptHead(
        { IconCoin(Ph.wallet, if (gone) C.grey else C.paisaInk, if (gone) C.lineSoft else C.paisaTint) },
        name, if (gone) "Deleted" else msg.lede.substringAfter(" · ", "").substringAfter(" · ", ""), gone,
    ) { amount?.let { Fig(it, color = if (gone) C.faint else C.ink, struck = gone) } }
    if (gone) {
        field("payments")?.value?.let { Text(it, style = T.sans.copy(fontSize = 12.5.sp, color = C.faint), modifier = Modifier.padding(top = 8.dp)) }
        return
    }
    val facts = msg.fields.filter { it.key in setOf("category", "due_day", "repeats") }
    if (facts.isNotEmpty()) FlowRow(Modifier.padding(top = 10.dp), horizontalArrangement = Arrangement.spacedBy(6.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        facts.forEach { f ->
            if (f.guessed) Row(verticalAlignment = Alignment.CenterVertically) {
                Dot()
                FactChip("${f.value}, I guessed")
            } else FactChip(f.value)
        }
    }
    if (msg.rowId != null) QuietActions(Quiet("Change") { ca.onContext(ComposeContext("Commitment · $name", "Change my $name commitment:")) })
}
