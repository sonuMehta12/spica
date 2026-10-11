package com.sonu.spica.ui.commitments

import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.sonu.spica.data.Commitment
import com.sonu.spica.data.Tx
import com.sonu.spica.lib.Fmt
import com.sonu.spica.state.AppState
import com.sonu.spica.state.SpicaViewModel
import com.sonu.spica.ui.common.BackStep
import com.sonu.spica.ui.common.Dot
import com.sonu.spica.ui.common.TrayAction
import com.sonu.spica.ui.common.TrayActions
import com.sonu.spica.ui.theme.C
import com.sonu.spica.ui.theme.T

/**
 * What a payment's tray needs to say it settles a commitment — the verbs, and
 * the lines it could count toward. A payment links to one commitment; the
 * link is a statement once the person has made or confirmed it, and a guess
 * (the amber dot) until then. `spec/done/commitments.md` § The payment tray.
 */
class PaymentLinks(
    /** This month's own lines still waiting for a payment: not skipped, not settled, not a borrowing. */
    val open: List<Commitment>,
    /** Every line known this month, for naming the one a payment is linked to. */
    val all: List<Commitment>,
    /** *Counts toward…* a line — and, said again for the line it already has, the confirm of a guess. */
    val countsToward: (txId: String, commitmentId: String) -> Unit,
    /** *Not a commitment*, and *Not this* on a guess. */
    val notCommitment: (txId: String) -> Unit,
    /** *Make this a commitment* — the sheet, filled from the payment. */
    val make: (Tx) -> Unit,
) {
    fun nameOf(id: String?): String? = id?.let { i -> all.firstOrNull { it.id == i }?.name }

    /** Only a payment out is ever a commitment's: not money in, not a lending. */
    fun applies(t: Tx) = t.kind == "expense" && !t.credit

    /** Where it could go instead of where it is. */
    fun choicesFor(t: Tx) = open.filter { it.id != t.commitmentId }

    companion object {
        val None = PaymentLinks(emptyList(), emptyList(), { _, _ -> }, {}, {})
    }
}

fun paymentLinks(vm: SpicaViewModel, s: AppState) = PaymentLinks(
    open = s.commitments?.items?.filter { !it.isBorrowing && !it.skipped && !it.settled }.orEmpty(),
    all = s.commitments?.items.orEmpty(),
    countsToward = vm::linkPayment,
    notCommitment = { vm.linkPayment(it, null) },
    make = vm::commitmentFromPayment,
)

/** The label of a line a payment could count toward: its name and what it still owes. */
fun choiceLabel(c: Commitment) = "${c.name} · ${Fmt.rupees(c.owed)}"

/** A payment's link as a line of words: `Rent`, and the amber dot before it while it is only a guess. */
@Composable
fun LinkWord(name: String, guessed: Boolean, modifier: Modifier = Modifier, size: Int = 11) {
    Row(modifier, verticalAlignment = Alignment.CenterVertically) {
        Text(" · ", style = T.sans.copy(fontSize = (size + 0.5f).sp, color = C.faint), maxLines = 1)
        if (guessed) Dot()
        Text(name, style = T.sans.copy(fontSize = (size + 0.5f).sp, color = C.faint), maxLines = 1)
    }
}

/**
 * The tray under a payment in a table: the commitment verbs the payment's
 * state allows, then its own (Edit, Delete). *Counts toward…* opens the lines
 * it could go to, in place.
 */
@Composable
fun PaymentTray(t: Tx, links: PaymentLinks, trailing: List<TrayAction>, modifier: Modifier = Modifier) {
    var choosing by remember(t.id) { mutableStateOf(false) }
    val choices = links.choicesFor(t)
    // Back closes the lines it could count toward before the tray itself.
    BackStep(choosing && choices.isNotEmpty()) { choosing = false }
    val own = buildList {
        if (links.applies(t)) {
            if (t.commitmentId != null) {
                // A guess is asked in place; a statement can only be ended.
                if (t.commitmentInferred) add(TrayAction("Right") { links.countsToward(t.id, t.commitmentId) })
                add(TrayAction(if (t.commitmentInferred) "Not this" else "Not a commitment") { links.notCommitment(t.id) })
            }
            if (choices.isNotEmpty()) add(TrayAction("Counts toward…") { choosing = !choosing })
            if (t.commitmentId == null) add(TrayAction("Make this a commitment") { links.make(t) })
        }
    }
    TrayActions(own + trailing, modifier)
    if (choosing && choices.isNotEmpty()) {
        TrayActions(choices.map { c -> TrayAction(choiceLabel(c)) { links.countsToward(t.id, c.id); choosing = false } }, Modifier.padding(top = 7.dp))
    }
}
