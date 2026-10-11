package com.sonu.spica.ui.commitments

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.sonu.spica.data.Commitment
import com.sonu.spica.data.CommitmentsPage
import com.sonu.spica.lib.Fmt
import com.sonu.spica.state.AppState
import com.sonu.spica.state.SpicaViewModel
import com.sonu.spica.state.Load
import com.sonu.spica.ui.common.AddRow
import com.sonu.spica.ui.common.Back
import com.sonu.spica.ui.common.Coin
import com.sonu.spica.ui.common.Ground
import com.sonu.spica.ui.common.PageHeader
import com.sonu.spica.ui.common.Panel
import com.sonu.spica.ui.common.Ph
import com.sonu.spica.ui.common.PhBold
import com.sonu.spica.ui.common.SectionLabel
import com.sonu.spica.ui.common.Spinner
import com.sonu.spica.ui.common.TopFade
import com.sonu.spica.ui.common.divider
import com.sonu.spica.ui.common.fadeUp
import com.sonu.spica.ui.common.panel
import com.sonu.spica.ui.common.plainTap
import com.sonu.spica.ui.common.tap
import com.sonu.spica.ui.common.RoundIcon
import com.sonu.spica.ui.theme.C
import com.sonu.spica.ui.theme.T
import java.time.LocalDate

/*
 * Commitments — what you still owe this month, in Home's clothes. Opened from
 * the Money widget's Committed, the line under a limit that is 0 or below, a
 * chat card's lines and the day's nudge page; the Money report holds the same
 * lines in its Commits tab. `spec/done/commitments.md` § The page.
 *
 * The lines are the server's: owed is worked out there from the payments that
 * settle each one, so deleting a payment gives its commitment the debt back.
 * Past months open read-only — what was recorded, nothing more — and a future
 * one does not exist, so › stops at this month. Month paging is not
 * navigation: Back leaves the page from any month, and ← sits in the head at
 * the top right, apart from the ‹ › discs under the title, so they never read
 * as Back. A borrowing's Repay pushes the Report over this page.
 */
@Composable
fun CommitmentsPageView(vm: SpicaViewModel, s: AppState, up: Back) {
    val back = s.commitmentsBack
    val page: CommitmentsPage? = if (back == 0) s.commitments else s.commitmentsPast
    val load = if (back == 0) (if (s.commitments != null) Load.Loaded else Load.Loading) else s.commitmentsPastLoad
    var confirm by remember { mutableStateOf<Commitment?>(null) }

    Box(Modifier.fillMaxSize().background(Ground).plainTap { }) {
        Column(Modifier.fillMaxSize().statusBarsPadding().padding(top = 8.dp).fadeUp(280)) {
            PageHeader("Money", "Commitments", up, lead = { Coin(Ph.wallet, C.paisaInk, C.paisaTint, 48.dp) })
            MonthNav(s.todayIso, back, vm::setCommitmentsBack)
            Box(Modifier.weight(1f)) {
                Column(
                    Modifier.fillMaxSize().verticalScroll(rememberScrollState()).navigationBarsPadding()
                        .padding(start = 16.dp, end = 16.dp, top = 6.dp, bottom = 40.dp),
                ) {
                    when {
                        page == null && load == Load.Failed -> Panel { Text("Couldn't load that month.", style = EmptyStyle) }
                        page == null -> Panel(Modifier.padding(top = 4.dp)) {
                            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                                Spinner()
                                Text("Loading…", style = EmptyStyle)
                            }
                        }
                        else -> Body(vm, page, s.todayIso) { confirm = it }
                    }
                }
                TopFade()
            }
        }
    }
    confirm?.let { c -> DeleteCommitmentDialog(c, onConfirm = { vm.deleteCommitment(c) }, onDismiss = { confirm = null }) }
}

private val EmptyStyle = T.sans.copy(fontSize = 15.sp, lineHeight = 21.sp, color = C.muted)

/** ‹ October ›. This month is the end of the road: a future month has no commitments yet. */
@Composable
private fun MonthNav(todayIso: String, back: Int, onBack: (Int) -> Unit) {
    val month = LocalDate.parse(todayIso).withDayOfMonth(1).minusMonths(back.toLong())
    Row(
        Modifier.fillMaxWidth().padding(start = 18.dp, end = 18.dp, top = 6.dp, bottom = 4.dp),
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        RoundIcon(PhBold.caretLeft, { onBack(back + 1) }, "Earlier month", 34.dp, tint = if (back >= 24) C.grey else C.ink)
        Text(
            monthName(month.toString()) + if (month.year != LocalDate.parse(todayIso).year) " ${month.year}" else "",
            style = T.sans.copy(fontSize = 15.sp, lineHeight = 19.sp, fontWeight = FontWeight.Medium),
            modifier = Modifier.padding(horizontal = 4.dp),
        )
        RoundIcon(PhBold.caretRight, { if (back > 0) onBack(back - 1) }, "Later month", 34.dp, tint = if (back == 0) C.grey else C.ink)
        if (back > 0) Text("read-only", style = T.sans.copy(fontSize = 12.sp, color = C.faint), modifier = Modifier.padding(start = 4.dp))
    }
}

@Composable
private fun Body(vm: SpicaViewModel, page: CommitmentsPage, todayIso: String, askDelete: (Commitment) -> Unit) {
    val g = group(page.items)
    val own = page.items.filter { !it.isBorrowing }
    val edit = page.editable

    Chain(page)

    if (page.items.isEmpty()) {
        // Never a ₹0 card: nothing owed is said as nothing.
        Panel(Modifier.padding(top = 14.dp)) {
            Text(if (edit) "No commitments yet" else "Nothing recorded for this month", style = EmptyStyle)
            if (edit) Text("Rent, an EMI, a subscription — what is owed whether or not you spend.", style = T.sans.copy(fontSize = 13.sp, lineHeight = 18.sp, color = C.faint), modifier = Modifier.padding(top = 4.dp))
        }
        if (edit) Column(Modifier.padding(top = 12.dp).fillMaxWidth().panel()) { AddRow("Add commitment", { vm.openCommitmentSheet() }) }
        return
    }

    val lines = g.open + g.settled
    if (lines.isNotEmpty()) {
        Column(Modifier.padding(top = 14.dp).fillMaxWidth().panel()) {
            lines.forEachIndexed { i, c -> Line(vm, c, edit, askDelete, Modifier.then(if (i > 0) Modifier.divider(18.dp, 18.dp) else Modifier)) }
        }
    }
    if (g.skipped.isNotEmpty()) {
        SectionLabel("Skipped")
        Column(Modifier.fillMaxWidth().panel()) {
            g.skipped.forEachIndexed { i, c -> Line(vm, c, edit, askDelete, Modifier.then(if (i > 0) Modifier.divider(18.dp, 18.dp) else Modifier)) }
        }
    }
    coverage(page.paidCount, page.openCount)?.takeIf { own.isNotEmpty() }?.let {
        Text(it, style = T.sans.copy(fontSize = 13.sp, lineHeight = 17.sp, color = C.faint), modifier = Modifier.padding(start = 6.dp, top = 12.dp))
    }
    if (edit) Column(Modifier.padding(top = 12.dp).fillMaxWidth().panel()) { AddRow("Add commitment", { vm.openCommitmentSheet() }) }
}

@Composable
private fun Line(vm: SpicaViewModel, c: Commitment, editable: Boolean, askDelete: (Commitment) -> Unit, modifier: Modifier) {
    CommitmentRow(
        c, menu = if (editable) commitmentMenu(commitmentActions(vm), c, askDelete) else null, modifier = modifier,
        // A borrowing's action is Repay — udhaar's own flow, on the Borrowed tab.
        action = if (c.isBorrowing && editable) "Repay" to vm::repayFromCommitments else null,
    )
}

/**
 * The sum worked out in one place, so a zero is never a mystery: what is owed,
 * what is free once it is paid, and the limit that leaves — in red, with a
 * minus, when it is below the line. Before the month's first income the limit
 * is unknown, and says so.
 */
@Composable
private fun Chain(page: CommitmentsPage) {
    val free = page.pool - page.owed
    Column(Modifier.fillMaxWidth().panel().padding(18.dp)) {
        Text("Owed this month", style = T.sans.copy(fontSize = 12.5.sp, lineHeight = 16.sp, fontWeight = FontWeight.Medium, color = C.muted))
        com.sonu.spica.ui.chat.Fig(Fmt.rupees(page.owed), 34.sp, C.ink, modifier = Modifier.padding(top = 2.dp))
        if (page.editable) {
            Text(chainLine(free, page.limit), style = T.sans.copy(fontSize = 13.sp, lineHeight = 18.sp, color = C.muted), modifier = Modifier.padding(top = 6.dp))
            if (page.limit == null) Text("Salary not in yet", style = T.sans.copy(fontSize = 12.sp, lineHeight = 16.sp, color = C.faint), modifier = Modifier.padding(top = 2.dp))
            else if (page.limit < 0) Text("Past the line — what is committed is more than what is left.", style = T.sans.copy(fontSize = 12.sp, lineHeight = 16.sp, color = C.red), modifier = Modifier.padding(top = 2.dp))
        }
    }
}

/** `₹8,215 free · limit ₹0 a day` — the limit red when it is negative, a dash when it is unknown. */
private fun chainLine(free: Int, limit: Int?) = buildAnnotatedString {
    withStyle(SpanStyle(color = if (free < 0) C.red else C.muted)) { append("${Fmt.rupees(free)} free") }
    append(" · limit ")
    when {
        limit == null -> append("—")
        else -> withStyle(SpanStyle(color = if (limit < 0) C.red else C.muted, fontWeight = FontWeight.Medium)) { append(Fmt.rupees(limit)) }
    }
    if (limit != null) append(" a day")
}
