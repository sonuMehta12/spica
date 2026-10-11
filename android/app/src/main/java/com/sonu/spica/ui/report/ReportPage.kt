package com.sonu.spica.ui.report

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshotFlow
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.em
import androidx.compose.ui.unit.sp
import com.sonu.spica.data.Commitment
import com.sonu.spica.data.Meal
import com.sonu.spica.ui.commitments.DeleteCommitmentDialog
import com.sonu.spica.ui.commitments.commitmentSub
import com.sonu.spica.ui.commitments.coverage
import com.sonu.spica.ui.commitments.group
import com.sonu.spica.data.Range
import com.sonu.spica.data.Tx
import com.sonu.spica.data.HabitLogRow
import com.sonu.spica.lib.Day
import com.sonu.spica.lib.Fmt
import com.sonu.spica.logic.Metrics
import com.sonu.spica.logic.Tasks
import com.sonu.spica.state.AppState
import com.sonu.spica.state.SpicaViewModel
import com.sonu.spica.state.ReportMode
import com.sonu.spica.state.ReportRange
import com.sonu.spica.ui.common.Back
import com.sonu.spica.ui.common.Coin
import com.sonu.spica.ui.common.FilterPill
import com.sonu.spica.ui.common.FilterStrip
import com.sonu.spica.ui.common.Ground
import com.sonu.spica.ui.common.MenuItem
import com.sonu.spica.ui.common.PageHeader
import com.sonu.spica.ui.common.SectionLabel
import com.sonu.spica.ui.common.LocalOnTop
import com.sonu.spica.ui.common.PagePill
import com.sonu.spica.ui.common.Tag
import com.sonu.spica.ui.common.TopFade
import com.sonu.spica.ui.common.panel
import com.sonu.spica.ui.theme.S
import com.sonu.spica.ui.common.MenuRow
import com.sonu.spica.ui.common.Popover
import com.sonu.spica.ui.common.fadeUp
import com.sonu.spica.ui.common.layerFocus
import com.sonu.spica.ui.common.plainTap
import com.sonu.spica.ui.common.tap
import com.sonu.spica.ui.home.ConcentricRings
import com.sonu.spica.ui.home.ProjectChart
import com.sonu.spica.ui.home.RingLegend
import com.sonu.spica.ui.theme.C
import com.sonu.spica.ui.theme.F
import com.sonu.spica.ui.theme.T
import com.sonu.spica.ui.common.Glyph
import com.sonu.spica.ui.commitments.choiceLabel
import com.sonu.spica.ui.commitments.paymentLinks
import com.sonu.spica.ui.common.Ph
import com.sonu.spica.ui.common.PhBold
import kotlinx.coroutines.launch

private const val ALL = "__all"
private const val LENT = "__lent"
private const val BORROWED = "__borrowed"
private const val COMMITS = "__commits"
private const val MEALS = "__meals"
private const val HABITS = "__habits"
private const val SLEEP = "__sleep"

private val TAB_LABELS = mapOf(ALL to "All", LENT to "Lent", BORROWED to "Borrowed", COMMITS to "Commits", MEALS to "Meals", HABITS to "Habits", SLEEP to "Sleep")

/** The modes, left to right, as the pill names them. */
private val MODES = listOf(ReportMode.Kaam, ReportMode.Paisa, ReportMode.Diet)

/** One word's width in the modes' pill — narrower than Home's, so three sit beside the range. */
private val MODE_SEG = 68.dp

/**
 * A glance, not an analysis — anything deeper is the agent's job, so the
 * composer sits here too, while the page is on top. Back is the stack's;
 * what is open in the list closes first.
 *
 * The modes lie side by side in a pager, as Home and Chat do, under Home's
 * own pill: a tap slides to a mode, a swipe carries the fill with the finger,
 * and the mode is the page it settles on.
 */
@Composable
fun ReportPage(vm: SpicaViewModel, s: AppState, back: Back, composer: (@Composable () -> Unit)?) {
    // Home's Habits widget opens Diet on its Habits tab, Repay on Borrowed; everything else opens on All.
    // Asked again each time an opener asks — even of a Report already open under it.
    var tab by remember(s.reportAsk) { mutableStateOf(when (s.reportTab) { "habits" -> HABITS; "borrowed" -> BORROWED; "commits" -> COMMITS; else -> ALL }) }
    var pendingDelete by remember { mutableStateOf<Commitment?>(null) }

    val pager = rememberPagerState(initialPage = MODES.indexOf(s.reportMode)) { MODES.size }
    val scope = rememberCoroutineScope()
    val go: (Int) -> Unit = { page -> scope.launch { pager.animateScrollToPage(page) } }
    val mode by rememberUpdatedState(s.reportMode)
    // A swipe, or a tap's slide, sets the mode once it lands.
    LaunchedEffect(pager) { snapshotFlow { pager.settledPage }.collect { if (MODES[it] != mode) vm.setReportMode(MODES[it]) } }
    // An opener that asks for a mode — even of a Report open under it — puts the pager there.
    LaunchedEffect(s.reportMode) { MODES.indexOf(s.reportMode).let { if (pager.settledPage != it) pager.scrollToPage(it) } }
    val top = LocalOnTop.current
    // The head names the mode under the fill, so it turns as the words do.
    val shown = MODES[pager.currentPage]

    Box(Modifier.fillMaxSize().background(Ground).plainTap { }.imePadding()) {
        Column(Modifier.fillMaxSize().statusBarsPadding().padding(top = 8.dp).fadeUp(280)) {
            PageHeader("Report", shown.label, back, lead = { ModeCoin(shown, 48.dp) })
            Row(
                Modifier.fillMaxWidth().padding(start = 18.dp, end = 18.dp, top = 14.dp, bottom = 8.dp),
                horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.CenterVertically,
            ) {
                PagePill(pager, MODES.map { it.label }, go, MODE_SEG)
                Spacer(Modifier.weight(1f))
                RangeSelect(s.reportRange, vm::setReportRange)
            }
            Box(Modifier.weight(1f)) {
                HorizontalPager(pager, Modifier.fillMaxSize(), beyondViewportPageCount = 1) { page ->
                    // The report beside this one is drawn too, but Back and focus belong to the one you see:
                    // a field open on a mode that slides away lets go, and the keyboard drops with it.
                    val onTop = top && pager.currentPage == page
                    CompositionLocalProvider(LocalOnTop provides onTop) {
                        Box(Modifier.fillMaxSize().then(layerFocus(onTop))) {
                            ModeReport(vm, s, MODES[page], tab, { tab = it }, { pendingDelete = it }, atRest = pager.settledPage == page)
                        }
                    }
                }
                TopFade()
            }
        }
        if (composer != null) Box(Modifier.align(Alignment.BottomCenter)) { composer() }
    }
    pendingDelete?.let { c -> DeleteCommitmentDialog(c, onConfirm = { vm.deleteCommitment(c) }, onDismiss = { pendingDelete = null }) }
}

/**
 * One mode's report — its scorecard, its charts, its rows — as one page of
 * the pager, so the mode sliding in is drawn as itself under the finger.
 * The filter is the page's, shared: a tab a mode does not have reads as All.
 */
@Composable
private fun ModeReport(
    vm: SpicaViewModel, s: AppState, mode: ReportMode, tab: String, onTab: (String) -> Unit, onDelete: (Commitment) -> Unit, atRest: Boolean,
) {
    val limit = s.limitInfo?.limit ?: 0
    val today = s.todayIso
    val p = s.profile
    val data = remember(mode, s.reportRange, s.tx, s.meals, limit, s.todos, s.pending, s.borrowed, s.profile, s.salary) {
        Metrics.build(
            mode, s.reportRange, s.tx, s.meals, limit, s.todos, today, s.salary, s.pending, s.borrowed,
            p.proteinTarget, p.kcalTarget, p.sleepTargetMin, p.stepTarget, s.projects.size,
        )
    }
    // To-do holds every task, as the + menu's list always did — money and food ones too.
    val kaamGroups = Tasks.groupTasks(s.todos, "all", s.projects)
    val tabs = when (mode) {
        ReportMode.Paisa -> {
            val cats = data.charts.firstOrNull()?.rows?.map { it.label } ?: emptyList()
            // "Other" is the leftovers bucket, so it sits at the end rather than by size.
            listOf(ALL, LENT, BORROWED, COMMITS) + cats.filter { it != "Other" } + cats.filter { it == "Other" }
        }
        ReportMode.Kaam -> listOf(ALL) + kaamGroups.map { it.label }
        ReportMode.Diet -> listOf(ALL, MEALS, HABITS, SLEEP)
    }
    val active = if (tab in tabs) tab else tabs[0]
    val focus = if (mode == ReportMode.Paisa && active !in listOf(LENT, BORROWED, COMMITS, ALL)) active else null

    fun inSpan(iso: String?) = (iso ?: today).let { it >= data.span.from && it <= data.span.to }
    fun dayLabel(day: Int, date: String?) = date?.let(Day::shortDay) ?: "$day"

    fun mealItem(m: Meal) = Item(
        m.id, m.name, listOfNotNull(m.type, dayLabel(m.day, m.date)).joinToString(" · "),
        "${m.k} kcal · ${Fmt.jsRound(m.p)}g", ItemTone.Muted, "diet", m.name,
    )
    // A habit log carries its count in the label, and nothing on the right.
    fun habitItem(l: HabitLogRow) = Item(
        l.id, "${l.habit}${l.amount?.let { " ×${Fmt.num(it)}" } ?: ""}",
        listOfNotNull(Day.shortDay(l.date), l.note).joinToString(" · "), "", ItemTone.Muted, "habit",
    )
    val links = paymentLinks(vm, s)
    fun txItem(t: Tx, withCat: Boolean) = Item(
        t.id, t.name, if (withCat) "${t.cat} · ${dayLabel(t.day, t.date)}" else dayLabel(t.day, t.date),
        "−${Fmt.rupees(t.amt)}", if (t.fixed) ItemTone.Muted else ItemTone.Bad, "paisa", "${t.name} ${t.amt}",
        buildList {
            if (links.applies(t)) {
                if (t.commitmentId != null) {
                    // A guess is confirmed or refused in one tap; a statement can only be ended.
                    if (t.commitmentInferred) add(ItemAction("Right") { links.countsToward(t.id, t.commitmentId); true })
                    add(ItemAction(if (t.commitmentInferred) "Not this" else "Not a commitment") { links.notCommitment(t.id); true })
                }
                val choices = links.choicesFor(t)
                if (choices.isNotEmpty()) add(ItemAction("Counts toward…", choices = choices.map { c -> ItemChoice(choiceLabel(c)) { links.countsToward(t.id, c.id) } }) { true })
                if (t.commitmentId == null) add(ItemAction("Make this a commitment") { links.make(t); true })
            }
        },
        link = t.commitmentId?.let { links.nameOf(it) ?: "Committed" }, linkGuess = t.commitmentInferred,
    )

    // This month's lines as the page draws them — borrowings are left out: the Borrowed tab holds them.
    fun commitItem(c: Commitment) = Item(
        c.id, c.name, commitmentSub(c, withCarried = true).ifEmpty { null },
        when {
            c.skipped -> Fmt.rupees(c.expected)
            c.settled -> Fmt.rupees(c.paid)
            else -> Fmt.rupees(c.owed)
        },
        if (c.skipped || c.settled) ItemTone.Muted else ItemTone.Bad, "commitment",
        actions = buildList {
            add(ItemAction("Edit") { vm.editCommitment(c); true })
            add(ItemAction(if (c.skipped) "Unskip" else "Skip this month") { vm.skipCommitment(c); true })
            if (c.carriedFrom == null) add(ItemAction(if (c.repeats) "Stop repeating" else "Repeat") { vm.repeatCommitment(c); true })
            add(ItemAction("Delete", danger = true) { onDelete(c); true })
        },
        valueDot = c.rolled && !c.skipped,
    )
    val commits = s.commitments?.takeIf { it.editable }?.items?.filter { !it.isBorrowing }?.let { group(it) }
    val commitLines = commits?.let { it.open + it.settled + it.skipped }.orEmpty()

    val items: List<Item> = when {
        active == COMMITS -> commitLines.map(::commitItem)
        active == LENT || active == BORROWED -> {
            // Open first, oldest first — the one that has waited longest; then what was settled.
            val leg = if (active == LENT) "lent" else "borrowed"
            val openRows = if (leg == "lent") s.pending else s.borrowed
            val word = if (leg == "lent") "Repaid" else "Paid back"
            openRows.map { o ->
                Item(
                    o.id, o.label,
                    "${Day.shortDay(o.date)} · ${Day.diffDays(o.date, today)} days${if (o.remaining < o.amount) " · of ${Fmt.rupees(o.amount)}" else ""}${if (o.pending) " · saving" else ""}",
                    Fmt.rupees(o.remaining), if (leg == "lent") ItemTone.Good else ItemTone.Bad, "paisa", "${o.label} ${o.amount}",
                    buildList {
                        add(
                            ItemAction(
                                word, good = true,
                                prompt = Prompt(
                                    o.remaining.toString(), "₹", "Enter saves · less than ${Fmt.rupees(o.remaining)} is a partial",
                                    "More than the ${Fmt.rupees(o.remaining)} still ${if (leg == "lent") "out" else "owed"} — log the extra as ${if (leg == "lent") "income" else "an expense"}.",
                                ),
                            ) { v -> vm.markRepaid(o.id, v?.toDoubleOrNull()?.let { Fmt.jsRound(it).toInt() } ?: 0) },
                        )
                        if (leg == "lent") add(ItemAction("Gift") { vm.gift(o.id); true })
                    },
                )
            } + s.repayments.filter { it.leg == leg }.map { r ->
                Item(
                    r.id, r.label.replace(Regex("\\s+(ko diya|se liya)$", RegexOption.IGNORE_CASE), ""),
                    "${if (leg == "lent") "repaid" else "paid back"} ${Day.shortDay(r.date)}${if (r.pending) " · saving" else if (r.failed) " · unsaved" else ""}",
                    Fmt.rupees(r.amount), ItemTone.Muted, "repayment",
                    actions = listOf(ItemAction("Undo") { vm.undoRepayment(r.id); true }),
                )
            }
        }
        // Spend and fixed together, newest first — the month as it was paid.
        mode == ReportMode.Paisa && active == ALL -> (s.tx + s.fixedTx).filter { inSpan(it.date) }.sortedByDescending { it.day }.map { txItem(it, true) }
        // Meals and habits interleaved, newest first — the list reads like the day did.
        mode == ReportMode.Diet && active == ALL -> (
            s.meals.filter { inSpan(it.date) }.map { (it.date ?: today) to mealItem(it) } +
                s.habitLogs.filter { inSpan(it.date) }.map { it.date to habitItem(it) }
            ).sortedByDescending { it.first }.map { it.second }
        active == MEALS -> s.meals.filter { inSpan(it.date) }.reversed().map(::mealItem)
        active == HABITS -> s.habitLogs.filter { inSpan(it.date) }.sortedByDescending { it.date }.map(::habitItem)
        active == SLEEP -> s.sleep.filter { inSpan(it.second) }.sortedByDescending { it.second }.map { (_, date, hours) ->
            val t = p.sleepTargetMin
            Item("s$date", Day.shortDay(date), valueStr = "${Fmt.num(hours)} h", tone = if (t == null) ItemTone.Muted else if (hours * 60 >= t) ItemTone.Good else ItemTone.Warn)
        }
        mode == ReportMode.Kaam -> {
            val rows = if (active == ALL) kaamGroups.flatMap { it.tasks } else kaamGroups.firstOrNull { it.label == active }?.tasks ?: emptyList()
            rows.map { t ->
                Item(
                    t.id, t.name,
                    // On All a task says its project; inside a project tab that would repeat the tab.
                    if (active == ALL) listOfNotNull(Tasks.projectOf(t.project, s.projects)?.name, t.src).joinToString(" · ") else t.src ?: "said aloud",
                    Tasks.statusLabel(t, today).ifEmpty { "no date" },
                    when {
                        t.done || t.due == null -> ItemTone.Muted
                        t.due < today -> ItemTone.Bad
                        t.due == today -> ItemTone.Warn
                        else -> ItemTone.Good
                    },
                    "task",
                )
            }
        }
        else -> s.tx.filter { it.cat == active && inSpan(it.date) }.reversed().map { txItem(it, false) }
    }

    // Each report opens at its top: the scroll is the mode's, and a mode left behind goes back to it.
    val scroll = rememberScrollState()
    LaunchedEffect(atRest) { if (!atRest) scroll.scrollTo(0) }
    Column(Modifier.fillMaxSize().verticalScroll(scroll).padding(start = 16.dp, end = 16.dp, top = 10.dp, bottom = 116.dp)) {
        // Diet leads with two: protein and calories are one question asked twice.
        Scorecard(data.tiles, data.hasPrev, if (mode == ReportMode.Diet) 2 else 1, data.extraTiles)

        SectionLabel(data.chartsTitle)
        Column(Modifier.fillMaxWidth().panel().padding(18.dp), verticalArrangement = Arrangement.spacedBy(18.dp)) {
            when {
                mode == ReportMode.Kaam -> Box(Modifier.fillMaxWidth().padding(vertical = 4.dp), contentAlignment = Alignment.Center) {
                    Box(Modifier.widthIn(max = 220.dp).fillMaxWidth()) { ProjectChart(Tasks.projectStats(s.todos, Range.Sab, s.projects, today)) }
                }
                data.rings != null -> Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(14.dp)) {
                    Box(Modifier.weight(1f)) { RingLegend(data.rings) }
                    Box(Modifier.widthIn(max = 140.dp).weight(0.8f)) { ConcentricRings(data.rings) }
                }
                else -> data.charts.forEach { chart ->
                    if (chart.rows.isNotEmpty()) DonutChart(chart.rows, if (chart.key == "cat") focus else null, chart.totalStr, chart.centreSub, chart.fill)
                    else Text("Nothing in this period.", style = T.sans.copy(fontSize = 13.5.sp, color = C.faint))
                }
            }
        }

        SectionLabel(
            when (mode) {
                ReportMode.Kaam -> "Tasks"
                ReportMode.Paisa -> if (active == COMMITS) "Commitments" else "Payments"
                ReportMode.Diet -> "Logged"
            },
            aside = { if (items.isNotEmpty()) Tag("${items.size}") },
        )
        FilterStrip {
            tabs.forEach { t -> FilterPill(TAB_LABELS[t] ?: t, active == t, { onTab(t) }) }
        }

        Column(Modifier.padding(top = 12.dp)) {
            if (active == COMMITS) {
                val page = s.commitments
                val lead = page?.takeIf { it.items.any { i -> !i.isBorrowing } }?.let { pg ->
                    listOfNotNull("${Fmt.rupees(pg.owed)} owed", coverage(pg.paidCount, pg.openCount)).joinToString(" · ")
                }
                if (lead != null) Text(lead, style = T.sans.copy(fontSize = 13.5.sp, lineHeight = 18.sp, fontWeight = FontWeight.Medium, color = C.muted), modifier = Modifier.padding(start = 6.dp, bottom = 8.dp))
                // Commitments are monthly: the range above does not filter them.
                if (s.reportRange != ReportRange.Mahina) Text("Commitments are monthly — this is the whole month, whatever the range.", style = T.sans.copy(fontSize = 12.sp, lineHeight = 16.sp, color = C.faint), modifier = Modifier.padding(start = 6.dp, bottom = 8.dp))
            }
            // Edit fills the composer floating over this page; sending the fix keeps you here.
            ItemList(items, vm::editRow, vm::deleteAny, empty = if (active == COMMITS) (if (s.commitments == null) "Loading…" else "No commitments yet") else "Nothing in this period.")
            if (active == COMMITS && s.commitments?.editable == true) com.sonu.spica.ui.common.Panel(Modifier.padding(top = 12.dp).fillMaxWidth(), onClick = { vm.openCommitmentSheet() }) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Coin(Ph.plus, C.brand, C.brandTint, 30.dp)
                    Text("Add commitment", style = T.sans.copy(fontSize = 15.sp, fontWeight = FontWeight.Medium, color = C.brand))
                }
            }
            if (active == LENT || active == BORROWED) AddOpenRow(if (active == LENT) "lent" else "borrowed") { leg, who, amt -> vm.addOpen(leg, who, amt) }
        }
        Spacer(Modifier.height(18.dp))
    }
}

/** A mode's coin: its icon in its ink on its tint — the badge its Home widget wears. */
@Composable
fun ModeCoin(mode: ReportMode, size: androidx.compose.ui.unit.Dp = 36.dp) = when (mode) {
    ReportMode.Kaam -> Coin(Ph.checkSquare, C.workInk, C.workTint, size)
    ReportMode.Paisa -> Coin(Ph.wallet, C.paisaInk, C.paisaTint, size)
    ReportMode.Diet -> Coin(Ph.bowlFood, C.dietInk, C.dietTint, size)
}

@Composable
private fun RangeSelect(range: ReportRange, onRange: (ReportRange) -> Unit) {
    var open by remember { mutableStateOf(false) }
    val shape = RoundedCornerShape(20.dp)
    Box {
        Row(
            Modifier.height(40.dp).then(S.bubble(shape)).clip(shape).background(C.white).tap { open = true }.padding(horizontal = 14.dp),
            horizontalArrangement = Arrangement.spacedBy(7.dp), verticalAlignment = Alignment.CenterVertically,
        ) {
            Glyph(Ph.calendarBlank, 15.dp, C.muted)
            Text(range.label, style = T.sans.copy(fontSize = 14.sp, lineHeight = 17.sp, fontWeight = FontWeight.Medium, color = C.ink))
            Glyph(PhBold.caretDown, 10.dp, C.muted)
        }
        if (open) {
            Popover(onDismiss = { open = false }, alignment = Alignment.TopEnd, offset = IntOffset(0, with(LocalDensity.current) { 46.dp.roundToPx() }), minWidth = 140.dp) {
                ReportRange.entries.forEach { r -> MenuRow(MenuItem(r.name, r.label, color = if (r == range) C.brand else C.ink) { onRange(r) }) { open = false } }
            }
        }
    }
}
