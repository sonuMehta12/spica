package com.sonu.spica.ui.commitments

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.sonu.spica.data.CommitmentDraft
import com.sonu.spica.state.AppState
import com.sonu.spica.state.SpicaViewModel
import com.sonu.spica.ui.common.ActionPill
import com.sonu.spica.ui.common.FilterPill
import com.sonu.spica.ui.common.Glyph
import com.sonu.spica.ui.common.InlineField
import com.sonu.spica.ui.common.Ph
import com.sonu.spica.ui.common.PillKind
import com.sonu.spica.ui.common.Switch
import com.sonu.spica.ui.common.tap
import com.sonu.spica.ui.theme.C
import com.sonu.spica.ui.theme.T

/** What a commitment can be filed under before the ledger has filed one: the names an obligation usually goes by. */
private val USUAL = listOf("Rent", "EMI", "Ghar", "Subscriptions", "Bills/Recharge", "Other")

/** Categories to pick from: this month's lines' own, the ledger's, then the usual — each once, in that order. */
private fun categoriesFor(s: AppState): List<String> {
    val seen = linkedSetOf<String>()
    fun add(c: String) {
        if (c.isNotBlank() && seen.none { it.equals(c, ignoreCase = true) }) seen += c
    }
    s.commitments?.items?.forEach { add(it.category) }
    (s.fixedTx + s.tx).filter { it.kind == "expense" }.groupingBy { it.cat }.eachCount().entries.sortedByDescending { it.value }.take(8).forEach { add(it.key) }
    USUAL.forEach(::add)
    return seen.toList()
}

/**
 * Name, amount, category, due day, repeats — the one sheet for a new line, a
 * line's changes, and *Make this a commitment* from a payment, which opens it
 * filled from that payment. Repeats is on unless you say it is a one-off.
 */
@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun CommitmentSheet(vm: SpicaViewModel, s: AppState, draft: CommitmentDraft) {
    val state = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    var name by remember(draft) { mutableStateOf(draft.name) }
    var amount by remember(draft) { mutableStateOf(draft.amount?.toString() ?: "") }
    var category by remember(draft) { mutableStateOf(draft.category) }
    var due by remember(draft) { mutableStateOf(draft.dueDay?.toString() ?: "") }
    var repeats by remember(draft) { mutableStateOf(draft.repeats) }
    val cats = remember(s.commitments, s.tx, s.fixedTx) { categoriesFor(s) }

    val amountN = amount.trim().toDoubleOrNull()?.let { Math.round(it).toInt() }
    val dueN = due.trim().takeIf { it.isNotEmpty() }?.toIntOrNull()
    val dueOk = due.isBlank() || dueN in 1..31
    val ok = name.isNotBlank() && category.isNotBlank() && (amountN ?: 0) > 0 && dueOk
    fun save() {
        if (ok) vm.saveCommitment(draft.copy(name = name.trim(), amount = amountN, category = category.trim(), dueDay = dueN, repeats = repeats))
    }

    ModalBottomSheet(
        onDismissRequest = vm::closeCommitmentSheet, sheetState = state,
        containerColor = C.white, scrimColor = C.shadow.copy(alpha = 0.32f),
    ) {
        Column(
            Modifier.fillMaxWidth().imePadding().navigationBarsPadding().verticalScroll(rememberScrollState())
                .padding(start = 20.dp, end = 20.dp, bottom = 24.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            Column {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        when {
                            draft.id != null -> "Edit commitment"
                            draft.linkTx != null -> "Make this a commitment"
                            else -> "Add commitment"
                        },
                        style = T.sans.copy(fontSize = 18.sp, fontWeight = FontWeight.SemiBold),
                        modifier = Modifier.weight(1f),
                    )
                    // A sheet is the root of a modal layer, so it carries the X — as on the web.
                    Box(Modifier.size(40.dp).clip(CircleShape).tap(onClick = vm::closeCommitmentSheet), contentAlignment = Alignment.Center) {
                        Glyph(Ph.x, 19.dp, C.muted, label = "Close")
                    }
                }
                if (draft.linkTx != null) Text("This payment will count toward it.", style = T.sans.copy(fontSize = 12.5.sp, color = C.faint), modifier = Modifier.padding(top = 2.dp))
            }
            Labelled("Name") { InlineField(name, { name = it }, Modifier.fillMaxWidth(), placeholder = "Rent", mono = false, autoFocus = draft.id == null && draft.name.isEmpty()) }
            Labelled("Amount") {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("₹", style = T.sans.copy(fontSize = 15.sp, color = C.muted))
                    InlineField(amount, { amount = it.filter { c -> c.isDigit() || c == '.' } }, Modifier.weight(1f), placeholder = "0", numeric = true, mono = false)
                }
            }
            Labelled("Category") {
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    cats.forEach { c -> FilterPill(c, category.equals(c, ignoreCase = true), { category = c }) }
                }
                InlineField(category, { category = it }, Modifier.fillMaxWidth().padding(top = 10.dp), placeholder = "Or type a category", mono = false)
            }
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Column(Modifier.weight(1f)) {
                    Text("Due day", style = T.sans.copy(fontSize = 13.sp, fontWeight = FontWeight.Medium, color = C.muted))
                    Text(
                        if (dueOk) "Optional. It orders the list; it never changes the limit." else "A day from 1 to 31.",
                        style = T.sans.copy(fontSize = 12.sp, lineHeight = 16.sp, color = if (dueOk) C.faint else C.red), modifier = Modifier.padding(top = 2.dp),
                    )
                }
                InlineField(due, { due = it.filter { c -> c.isDigit() }.take(2) }, Modifier.width(72.dp), placeholder = "—", numeric = true, mono = false)
            }
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Column(Modifier.weight(1f)) {
                    Text("Repeats every month", style = T.sans.copy(fontSize = 15.sp, fontWeight = FontWeight.Medium))
                    Text(
                        if (repeats) "Comes back next month until you stop it." else "This month only.",
                        style = T.sans.copy(fontSize = 12.sp, lineHeight = 16.sp, color = C.faint), modifier = Modifier.padding(top = 2.dp),
                    )
                }
                Switch(repeats, { repeats = !repeats }, "Repeats every month")
            }
            Row(Modifier.fillMaxWidth().padding(top = 4.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp, Alignment.End)) {
                ActionPill("Cancel", vm::closeCommitmentSheet)
                ActionPill(if (draft.id != null) "Save" else "Add", ::save, PillKind.Primary, enabled = ok)
            }
            Spacer(Modifier.padding(bottom = 2.dp))
        }
    }
}

@Composable
private fun Labelled(label: String, content: @Composable () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text(label, style = T.sans.copy(fontSize = 13.sp, fontWeight = FontWeight.Medium, color = C.muted))
        content()
    }
}
