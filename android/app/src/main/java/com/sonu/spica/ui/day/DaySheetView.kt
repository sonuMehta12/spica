package com.sonu.spica.ui.day

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
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
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.layout.ContentScale
import coil3.compose.SubcomposeAsyncImage
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.TextUnit
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.sonu.spica.data.HabitLogRow
import com.sonu.spica.data.HealthAccess
import com.sonu.spica.data.Meal
import com.sonu.spica.data.Mode
import com.sonu.spica.data.PlanMeal
import com.sonu.spica.data.PlanWorkout
import com.sonu.spica.lib.Day
import com.sonu.spica.lib.Fmt
import com.sonu.spica.logic.DayKind
import com.sonu.spica.logic.DayRail
import com.sonu.spica.logic.DaySheet
import com.sonu.spica.logic.Tasks
import com.sonu.spica.state.AppState
import com.sonu.spica.state.DerivedView
import com.sonu.spica.state.SpicaViewModel
import com.sonu.spica.ui.chat.SET_PROTEIN_TARGET
import com.sonu.spica.ui.common.Glyph
import com.sonu.spica.ui.common.PhBold
import com.sonu.spica.ui.common.PhFill
import com.sonu.spica.ui.common.habitGlyph
import com.sonu.spica.ui.common.tap
import com.sonu.spica.ui.theme.C
import com.sonu.spica.ui.theme.T
import java.time.Instant
import java.time.ZoneId

/*
 * A row's sheet, in the day look: plain white, one surface — a handle and a
 * close, the mode and the day it shows, the big numbers, that day's rows with
 * the tapped one picked out, and the way to the mode's report. Opened from
 * another day it shows that day; a limit or a target belongs to today, so
 * there the rings give way to totals. `spec/home-day-rail.md` § A row's sheet.
 */

private object SheetType {
    val title = T.day.copy(fontSize = 26.sp, fontWeight = FontWeight.ExtraBold, lineHeight = 32.sp)
    val sub = T.day.copy(fontSize = 13.sp, fontWeight = FontWeight.Medium, color = C.faint)
    val lab = T.day.copy(fontSize = 12.5.sp, fontWeight = FontWeight.Medium, lineHeight = 16.sp, color = C.faint)
    val stat = T.day.copy(fontSize = 17.sp, fontWeight = FontWeight.ExtraBold, lineHeight = 22.sp)
    val mid = T.day.copy(fontSize = 22.sp, fontWeight = FontWeight.ExtraBold, lineHeight = 28.sp)
    val big = T.day.copy(fontSize = 34.sp, fontWeight = FontWeight.ExtraBold, lineHeight = 40.sp)
    val row = T.day.copy(fontSize = 15.sp, fontWeight = FontWeight.SemiBold, lineHeight = 20.sp)
    val meta = T.day.copy(fontSize = 12.sp, fontWeight = FontWeight.Medium, lineHeight = 16.sp, color = C.faint)
    val figure = T.day.copy(fontSize = 13.sp, fontWeight = FontWeight.SemiBold, color = C.muted)
    val time = T.day.copy(fontSize = 10.5.sp, fontWeight = FontWeight.Medium, color = C.faint, textAlign = TextAlign.End)
    val sec = T.day.copy(fontSize = 13.sp, fontWeight = FontWeight.Bold, color = C.muted)
    val link = T.day.copy(fontSize = 13.5.sp, fontWeight = FontWeight.ExtraBold, color = C.brand)
}

private fun titleOf(s: DaySheet) = when (s) {
    DaySheet.Money -> "Money"
    DaySheet.Diet -> "Diet"
    DaySheet.Habits -> "Habits"
    DaySheet.Work -> "To-do"
    DaySheet.Activity -> "Activity"
}

private val zone: ZoneId get() = ZoneId.systemDefault()
private fun clockOf(at: Instant?) = at?.let(DayRail::clock) ?: "—"

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DaySheetView(
    open: SheetOpen, vm: SpicaViewModel, s: AppState, v: DerivedView,
    onConnectHealth: () -> Unit, onChat: () -> Unit, onDismiss: () -> Unit,
) {
    val state = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    val day = open.day.ifEmpty { s.todayIso }
    val kind = DayRail.kindOf(day, s.todayIso)
    ModalBottomSheet(
        onDismissRequest = onDismiss, sheetState = state, containerColor = C.white,
        shape = RoundedCornerShape(topStart = 32.dp, topEnd = 32.dp), dragHandle = null,
        scrimColor = C.shadow.copy(alpha = 0.36f),
    ) {
        Box(Modifier.fillMaxWidth().padding(start = 18.dp, end = 16.dp, top = 10.dp)) {
            Box(Modifier.align(Alignment.TopCenter).size(40.dp, 5.dp).clip(CircleShape).background(C.border))
            Box(
                Modifier.align(Alignment.TopEnd).padding(top = 6.dp).size(36.dp).clip(CircleShape).background(C.lineSoft).tap(onClick = onDismiss),
                contentAlignment = Alignment.Center,
            ) { Glyph(PhBold.x, 14.dp, C.ink, label = "Close ${titleOf(open.sheet)}") }
        }
        Column(
            Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(start = 20.dp, end = 20.dp, bottom = 16.dp).navigationBarsPadding(),
        ) {
            when (open.sheet) {
                DaySheet.Money -> MoneySheet(s, v, day, kind, open.key, vm)
                DaySheet.Diet -> DietSheet(s, v, day, kind, open.key, vm)
                DaySheet.Habits -> HabitSheet(s, day, kind, open.key, open.habit, vm)
                DaySheet.Work -> TodoSheet(s, day, kind, open.key, vm, onChat)
                DaySheet.Activity -> ActivitySheet(s, day, kind, vm, onConnectHealth)
            }
            Spacer(Modifier.height(8.dp))
        }
    }
}

/* ─── the parts every sheet is built from ─────────────────────────────── */

@Composable
private fun Head(title: String, day: String, kind: DayKind, glyph: ImageVector? = null, sub: String? = null) {
    Row(Modifier.padding(top = 14.dp), verticalAlignment = Alignment.CenterVertically) {
        if (glyph != null) {
            Box(Modifier.padding(end = 12.dp).size(44.dp).background(C.deepHabit, CircleShape), contentAlignment = Alignment.Center) { Glyph(glyph, 22.dp, C.white) }
        }
        Column {
            Text(title, style = SheetType.title)
            Text(sub ?: if (kind == DayKind.Today) "Today · ${Day.cardDay(day)}" else Day.cardDay(day), style = SheetType.sub, modifier = Modifier.padding(top = 1.dp))
        }
    }
}

/** A ring round a target — the one quantity a ring is for. Full and red when past it. */
@Composable
private fun Ring(fraction: Float, color: Color, size: Dp = 104.dp, centre: @Composable ColumnScope.() -> Unit) {
    Box(Modifier.size(size), contentAlignment = Alignment.Center) {
        Canvas(Modifier.size(size)) {
            val w = 11.dp.toPx()
            val d = this.size.minDimension - w
            val tl = Offset(w / 2, w / 2)
            drawArc(C.lineSoft, 0f, 360f, false, tl, Size(d, d), style = Stroke(w))
            if (fraction > 0f) drawArc(color, -90f, 360f * fraction.coerceIn(0f, 1f), false, tl, Size(d, d), style = Stroke(w, cap = StrokeCap.Round))
        }
        Column(horizontalAlignment = Alignment.CenterHorizontally, content = centre)
    }
}

@Composable
private fun RingFigure(value: String, label: String, size: TextUnit = 22.sp) {
    Text(value, style = T.day.copy(fontSize = size, fontWeight = FontWeight.ExtraBold, lineHeight = 26.sp))
    Text(label, style = SheetType.lab.copy(fontSize = 11.sp))
}

@Composable
private fun RowScope.Stat(value: String, label: String, valueColor: Color = C.ink, onClick: (() -> Unit)? = null) {
    Column(Modifier.weight(1f)) {
        Text(value, style = SheetType.stat.copy(color = if (value == "—") C.faint else valueColor), maxLines = 1)
        Text(label, style = if (onClick != null) SheetType.lab.copy(fontWeight = FontWeight.Bold, color = C.brand) else SheetType.lab,
            maxLines = 2, modifier = if (onClick != null) Modifier.tap(onClick = onClick) else Modifier)
    }
}

@Composable
private fun Stats(content: @Composable RowScope.() -> Unit) =
    Row(Modifier.fillMaxWidth().padding(top = 16.dp), horizontalArrangement = Arrangement.spacedBy(12.dp), content = content)

@Composable
private fun Rule() = Box(Modifier.padding(top = 18.dp).fillMaxWidth().height(1.dp).background(C.line))

@Composable
private fun Section(left: String, right: String? = null, top: Dp = 16.dp) {
    Row(Modifier.fillMaxWidth().padding(top = top, bottom = 4.dp), verticalAlignment = Alignment.Bottom) {
        Text(left, style = SheetType.sec, modifier = Modifier.weight(1f))
        if (right != null) Text(right, style = SheetType.lab.copy(fontWeight = FontWeight.SemiBold))
    }
}

@Composable
private fun Bar(fraction: Float, color: Color, modifier: Modifier = Modifier, height: Dp = 8.dp) {
    Box(modifier.fillMaxWidth().height(height).clip(CircleShape).background(C.lineSoft)) {
        Box(Modifier.fillMaxWidth(fraction.coerceIn(0f, 1f)).fillMaxHeight().clip(CircleShape).background(color))
    }
}

/** One row on a sheet: its time, its mark, the title and its line, a figure — picked out in the mode's tint when it is the row tapped. */
@Composable
private fun SheetRow(
    time: String?, title: String, tone: DayTone, picked: Boolean,
    mark: @Composable () -> Unit, sub: String? = null, subColor: Color? = null, figure: String? = null, estimate: Boolean = false,
    trailing: (@Composable () -> Unit)? = null, onClick: (() -> Unit)? = null,
) {
    Row(
        Modifier.fillMaxWidth().padding(vertical = 2.dp).clip(RoundedCornerShape(20.dp))
            .background(if (picked) tone.tint else Color.Transparent)
            .then(if (onClick != null) Modifier.tap(onClick = onClick) else Modifier)
            .padding(horizontal = 8.dp, vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (time != null) {
            Text(time, style = SheetType.time.copy(color = if (picked) tone.ink else C.faint, fontWeight = if (picked) FontWeight.Bold else FontWeight.Medium),
                maxLines = 1, modifier = Modifier.width(36.dp))
            Spacer(Modifier.width(10.dp))
        }
        mark()
        Spacer(Modifier.width(10.dp))
        Column(Modifier.weight(1f)) {
            Text(title, style = SheetType.row, maxLines = 2, overflow = TextOverflow.Ellipsis)
            if (sub != null) Text(sub, style = SheetType.meta.copy(color = subColor ?: (if (picked) tone.ink else C.faint)), maxLines = 1, overflow = TextOverflow.Ellipsis)
        }
        if (figure != null) {
            Row(Modifier.padding(start = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                if (estimate) AmberDot()
                Text(figure, style = SheetType.figure.copy(color = if (picked) tone.ink else C.muted, fontWeight = if (picked) FontWeight.ExtraBold else FontWeight.SemiBold))
            }
        }
        if (trailing != null) {
            Spacer(Modifier.width(10.dp))
            trailing()
        }
    }
}

@Composable
private fun Coin(glyph: ImageVector, tone: DayTone, solid: Boolean = true, size: Dp = 40.dp) =
    Box(Modifier.size(size).background(if (solid) tone.base else tone.mist, CircleShape), contentAlignment = Alignment.Center) {
        Glyph(glyph, size * 0.48f, if (solid) C.white else tone.base)
    }

@Composable
private fun ReportButton(text: String, onClick: () -> Unit) {
    Box(
        Modifier.fillMaxWidth().padding(top = 18.dp).height(52.dp).clip(CircleShape).background(C.brand).tap(onClick = onClick),
        contentAlignment = Alignment.Center,
    ) { Text(text, style = T.day.copy(fontSize = 15.sp, fontWeight = FontWeight.ExtraBold, color = C.white)) }
}

@Composable
private fun Quiet(text: String) = Text(text, style = SheetType.meta.copy(fontSize = 13.sp), modifier = Modifier.padding(vertical = 10.dp))

@Composable
private fun Link(text: String, modifier: Modifier = Modifier, onClick: () -> Unit) =
    Text(text, style = SheetType.link, modifier = modifier.tap(onClick = onClick))

/* ─── Money ───────────────────────────────────────────────────────────── */

@Composable
private fun ColumnScope.MoneySheet(s: AppState, v: DerivedView, day: String, kind: DayKind, picked: String?, vm: SpicaViewModel) {
    val tone = toneOf(DaySheet.Money)
    val spends = DayRail.spendsOn(s, day).sortedWith(compareBy({ it.at == null }, { it.at }))
    Head("Money", day, kind)
    if (kind == DayKind.Today) {
        val p = v.paisa
        val limit = p.limit
        val over = p.overToday
        Row(Modifier.padding(top = 18.dp), verticalAlignment = Alignment.CenterVertically) {
            Ring(
                fraction = when { over != null -> 1f; limit != null && limit > 0 -> p.spentToday.toFloat() / limit; else -> 0f },
                color = if (over != null) C.red else tone.base,
            ) { RingFigure(Fmt.rupees(p.spentToday), "spent", if (p.spentToday >= 1000) 20.sp else 22.sp) }
            Spacer(Modifier.width(20.dp))
            Column {
                when {
                    over != null -> {
                        Text("${Fmt.rupees(over)} over", style = SheetType.mid.copy(color = C.red))
                        Text("today's limit was ${Fmt.rupees(limit!!)}", style = SheetType.lab)
                    }
                    limit == null -> {
                        Text("— left", style = SheetType.mid.copy(color = C.faint))
                        Text(if (p.salaryPending) "No limit yet: salary isn't in." else "No limit yet.", style = SheetType.lab)
                        Link("See what's committed", Modifier.padding(top = 4.dp), vm::openCommitments)
                    }
                    limit <= 0 -> {
                        Text("${Fmt.rupees(0)} left", style = SheetType.mid)
                        Text("Everything left this month is committed.", style = SheetType.lab)
                        Link("See what's committed", Modifier.padding(top = 4.dp), vm::openCommitments)
                    }
                    else -> {
                        Text("${Fmt.rupees(limit - p.spentToday)} left", style = SheetType.mid)
                        Text("of ${Fmt.rupees(limit)} today", style = SheetType.lab)
                    }
                }
            }
        }
        Stats {
            val target = p.savingsTarget
            Stat(p.saving?.let(Fmt::rupees) ?: "—", "expected saving", if (p.saving != null && target > 0 && p.saving < target) C.red else C.ink)
            Stat(p.committed?.let(Fmt::rupees) ?: "—", "committed", onClick = vm::openCommitments)
            Stat(Fmt.rupees(p.lentOut), "lent out")
        }
        Row(Modifier.fillMaxWidth().padding(top = 16.dp), verticalAlignment = Alignment.Bottom) {
            Text("Total", style = SheetType.lab.copy(fontWeight = FontWeight.Bold, color = C.muted), modifier = Modifier.weight(1f))
            Text(
                if (p.cameIn > 0) "${Fmt.rupees(p.goneOut)} out · ${Fmt.rupees(p.cameIn)} in" else "${Fmt.rupees(p.goneOut)} out · nothing in yet",
                style = SheetType.lab.copy(color = C.muted),
            )
        }
        // Nothing in yet: no denominator, so no bar — never 0 of 0.
        if (p.cameIn > 0) Bar(p.goneOut.toFloat() / p.cameIn, if (p.goneOut > p.cameIn) C.red else tone.base, Modifier.padding(top = 8.dp))
    } else if (kind == DayKind.Past) {
        val monthStart = Day.monthStart(day)
        val month = (s.tx + s.fixedTx).filter { val d = it.date ?: ""; d in monthStart..day && !it.deleted && it.id !in s.deletedRows && !it.credit }
        val total = spends.sumOf { it.amt }
        Column(Modifier.padding(top = 18.dp)) {
            Text(if (spends.isEmpty()) "—" else Fmt.rupees(total), style = SheetType.big.copy(fontSize = 40.sp, lineHeight = 44.sp, color = if (spends.isEmpty()) C.faint else C.ink))
            Text(if (spends.isEmpty()) "nothing spent that day" else "spent that day · ${spends.size} ${if (spends.size == 1) "spend" else "spends"}", style = SheetType.lab)
        }
        Stats {
            Stat(if (month.isEmpty()) "—" else Fmt.rupees(Fmt.jsRound(month.sumOf { it.amt }.toDouble() / Day.dayOfMonth(day))), "a day on average this month")
            Stat(if (month.isEmpty()) "—" else Fmt.rupees(month.sumOf { it.amt }), "spent from 1 to ${Day.shortDay(day)}")
        }
        Text("A day's limit is worked out each morning, so a past day has none to show.", style = SheetType.lab, modifier = Modifier.padding(top = 14.dp))
    }
    Rule()
    Section(if (kind == DayKind.Today) "Today" else Day.cardDay(day), if (spends.isEmpty()) null else "${spends.size} ${if (spends.size == 1) "spend" else "spends"} · ${Fmt.rupees(spends.sumOf { it.amt })}")
    if (spends.isEmpty()) Quiet(if (kind == DayKind.Ahead) "Spends land here on the day." else "No spends ${if (kind == DayKind.Today) "yet today" else "that day"}.")
    spends.forEach { t ->
        SheetRow(
            time = clockOf(t.at), title = DayRail.title(t.name), tone = tone, picked = picked == "tx:${t.id}",
            mark = { Coin(PhFill.wallet, tone) }, figure = Fmt.rupees(-t.amt), estimate = (t.confidence ?: 1.0) < 1.0,
        )
    }
    ReportButton("Open Money") { vm.openReport(Mode.Paisa) }
}

/* ─── Diet ────────────────────────────────────────────────────────────── */

@Composable
private fun ColumnScope.DietSheet(s: AppState, v: DerivedView, day: String, kind: DayKind, picked: String?, vm: SpicaViewModel) {
    val tone = toneOf(DaySheet.Diet)
    val meals = DayRail.mealsOn(s, day).sortedWith(compareBy({ it.at == null }, { it.at }))
    val protein = meals.sumOf { it.p }
    val kcal = meals.sumOf { it.k }
    val carbs = meals.mapNotNull { it.c }
    val fats = meals.mapNotNull { it.f }
    Head("Diet", day, kind)
    if (kind == DayKind.Today) {
        val target = v.diet.proteinTarget?.takeIf { it > 0 }
        Row(Modifier.padding(top = 18.dp), verticalAlignment = Alignment.CenterVertically) {
            Ring(if (target != null) (protein / target).toFloat() else 0f, tone.base) {
                RingFigure(if (meals.isEmpty()) "—" else Fmt.grams(protein), "protein", 24.sp)
            }
            Spacer(Modifier.width(20.dp))
            Column {
                when {
                    target == null -> {
                        Text("No protein target", style = SheetType.mid.copy(fontSize = 18.sp))
                        Link("Set target", Modifier.padding(top = 4.dp)) { vm.setContext(SET_PROTEIN_TARGET) }
                    }
                    protein < target -> {
                        Text("${Fmt.grams(target - protein)} to go", style = SheetType.mid)
                        Text("of ${Fmt.grams(target)} today", style = SheetType.lab)
                    }
                    else -> {
                        Text("Target met", style = SheetType.mid.copy(color = tone.ink))
                        Text("${Fmt.grams(protein - target)} past ${Fmt.grams(target)}", style = SheetType.lab)
                    }
                }
            }
        }
    } else if (kind == DayKind.Past) {
        Row(Modifier.padding(top = 18.dp), verticalAlignment = Alignment.Bottom) {
            Text(if (meals.isEmpty()) "—" else Fmt.grams(protein), style = SheetType.big.copy(color = if (meals.isEmpty()) C.faint else C.ink))
            Text("  protein that day", style = SheetType.lab, modifier = Modifier.padding(bottom = 6.dp))
        }
    }
    if (kind != DayKind.Ahead) Stats {
        val kT = if (kind == DayKind.Today) v.diet.kcalTarget?.takeIf { it > 0 } else null
        Stat(if (meals.isEmpty()) "—" else Fmt.indian(kcal) + (kT?.let { " / ${Fmt.indian(it)}" } ?: ""), "kcal", if (kT != null && kcal > kT) C.red else C.ink)
        Stat(if (carbs.isEmpty()) "—" else Fmt.grams(carbs.sum()), "carbs" + unrecorded(meals.size - carbs.size, carbs.isEmpty()))
        Stat(if (fats.isEmpty()) "—" else Fmt.grams(fats.sum()), "fat" + unrecorded(meals.size - fats.size, fats.isEmpty()))
    }
    Rule()
    Section("Eaten", if (meals.isEmpty()) null else if (meals.size == 1) "1 meal" else "${meals.size} meals")
    if (meals.isEmpty()) Quiet(if (kind == DayKind.Ahead) "Meals land here on the day." else "Nothing eaten logged ${if (kind == DayKind.Today) "yet" else "that day"}.")
    meals.forEach { m -> MealRow(m, s, tone, picked == "meal:${m.id}") }
    if (kind == DayKind.Today) {
        val planned = s.plan?.meals.orEmpty().filter { "meal:${it.slot}" !in s.planDone }
        if (planned.isNotEmpty()) {
            Section("Still planned", "${Fmt.grams(planned.sumOf { it.protein })} protein", top = 14.dp)
            planned.forEach { m -> PlannedRow(m, tone, picked == "plan:${m.slot}") { vm.logPlanMeal(m) } }
        }
    }
    ReportButton("Open Diet") { vm.openReport(Mode.Diet) }
}

private fun unrecorded(n: Int, none: Boolean) = if (n > 0 && !none) " · $n unrecorded" else ""

/** A meal eaten: its dish's photo on a tile (the bowl when there is none), the slot and time, the name, one macro line. */
@Composable
private fun MealRow(m: Meal, s: AppState, tone: DayTone, picked: Boolean) {
    val photo = m.dishId?.let { id -> s.dishes.firstOrNull { it.id == id }?.imageUrl }
    DishRow(
        picture = { Picture(photo, PhFill.bowlFood, tone, 64.dp, 16.dp, DayRail.title(m.name)) },
        meta = listOfNotNull(m.type?.takeIf { it.isNotBlank() }?.let(DayRail::cap), m.at?.let(DayRail::clock)).joinToString(" · ").ifEmpty { null },
        name = DayRail.title(m.name), macros = shortMacros(m.p, m.k, m.c, m.f), estimate = (m.confidence ?: 1.0) < 1.0,
        tone = tone, picked = picked,
    )
}

/** A meal still planned: the plan's photo in a dashed frame — not yet, as on the rail — and *Log it*. */
@Composable
private fun PlannedRow(m: PlanMeal, tone: DayTone, picked: Boolean, onLog: () -> Unit) {
    DishRow(
        picture = {
            Box(Modifier.size(64.dp).dashedFrame(tone), contentAlignment = Alignment.Center) {
                Picture(m.imageUrl, PhFill.bowlFood, tone, 52.dp, 12.dp, DayRail.title(m.name))
            }
        },
        meta = DayRail.cap(m.slot), name = DayRail.title(m.name), macros = shortMacros(m.protein, m.kcal, m.carbs, m.fat),
        estimate = m.idea, tone = tone, picked = picked,
        trailing = {
            Box(Modifier.clip(CircleShape).background(C.brand).tap(onClick = onLog).padding(horizontal = 14.dp, vertical = 7.dp)) {
                Text("Log it", style = T.day.copy(fontSize = 13.sp, fontWeight = FontWeight.ExtraBold, color = C.white))
            }
        },
    )
}

private fun Modifier.dashedFrame(tone: DayTone) = drawBehind {
    val w = 2.dp.toPx()
    drawRoundRect(
        color = tone.soft, topLeft = Offset(w / 2, w / 2), size = Size(size.width - w, size.height - w),
        cornerRadius = CornerRadius(16.dp.toPx()),
        style = Stroke(w, pathEffect = PathEffect.dashPathEffect(floatArrayOf(5.dp.toPx(), 4.dp.toPx()))),
    )
}

@Composable
private fun DishRow(
    picture: @Composable () -> Unit, meta: String?, name: String, macros: String, estimate: Boolean,
    tone: DayTone, picked: Boolean, trailing: (@Composable () -> Unit)? = null,
) {
    Row(
        Modifier.fillMaxWidth().padding(vertical = 2.dp).clip(RoundedCornerShape(22.dp))
            .background(if (picked) tone.tint else Color.Transparent).padding(8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        picture()
        Spacer(Modifier.width(14.dp))
        Column(Modifier.weight(1f)) {
            if (meta != null) Text(meta, style = SheetType.meta.copy(fontWeight = FontWeight.SemiBold, color = if (picked) tone.ink else C.faint))
            Text(name, style = T.day.copy(fontSize = 16.sp, fontWeight = FontWeight.Bold, lineHeight = 20.sp), maxLines = 2, overflow = TextOverflow.Ellipsis)
            Row(Modifier.padding(top = 3.dp), verticalAlignment = Alignment.CenterVertically) {
                if (estimate) AmberDot()
                Text(macros, style = SheetType.meta.copy(fontSize = 12.5.sp, color = tone.ink), maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
        }
        if (trailing != null) {
            Spacer(Modifier.width(8.dp))
            trailing()
        }
    }
}

/* ─── A habit ─────────────────────────────────────────────────────────── */

@Composable
private fun ColumnScope.HabitSheet(s: AppState, day: String, kind: DayKind, picked: String?, habitName: String?, vm: SpicaViewModel) {
    val tone = toneOf(DaySheet.Habits)
    val name = habitName ?: s.habits.firstOrNull()?.name ?: s.habitLogs.lastOrNull()?.habit
    if (name == null) {
        Head("Habits", day, kind)
        Quiet("Nothing tracked yet. Say “track workouts” to start one.")
        ReportButton("Open Habits", vm::openHabits)
        return
    }
    val row = s.habits.firstOrNull { it.name.equals(name, ignoreCase = true) }
    val logs = s.habitLogs.filter { it.habit.equals(name, ignoreCase = true) }
    val cutting = row?.direction == "break"
    val minutes = row?.unit?.contains("min", ignoreCase = true) == true
    val monday = Day.addDays(day, -Day.weekIndex(day))
    val week = (0..6).map { Day.addDays(monday, it) }
    fun amountOn(d: String) = logs.filter { it.date == d }.sumOf { it.amount ?: 1.0 }
    fun loggedOn(d: String) = logs.any { it.date == d }
    val glyph = habitGlyph(name) ?: PhFill.checkSquare
    Head(
        DayRail.title(name), day, kind, glyph,
        sub = when {
            cutting -> "Cutting down · counted each time"
            minutes -> "Building · a day counts when you do it"
            else -> "Building · a day counts when you do it"
        },
    )
    val thisWeek = week.filter { it <= s.todayIso }
    Stats {
        if (cutting) {
            val lastMonday = Day.addDays(monday, -7)
            val lastWeek = (0..6).map { Day.addDays(lastMonday, it) }
            Stat(if (loggedOn(day)) Fmt.num(amountOn(day)) else "—", if (kind == DayKind.Today) "today" else "that day")
            Stat(thisWeek.sumOf { amountOn(it) }.let { if (it == 0.0) "—" else Fmt.num(it) }, "this week")
            Stat(lastWeek.sumOf { amountOn(it) }.let { if (it == 0.0) "—" else Fmt.num(it) }, "last week")
        } else {
            val days = thisWeek.count { loggedOn(it) }
            Stat("$days of 7", "days this week")
            if (minutes) {
                val mins = thisWeek.sumOf { d -> logs.filter { it.date == d }.sumOf { it.amount ?: 0.0 } }
                val sessions = thisWeek.sumOf { d -> logs.count { it.date == d && it.amount != null } }
                Stat(if (mins == 0.0) "—" else "${Fmt.num(mins)} min", "this week")
                Stat(if (sessions == 0) "—" else "${Fmt.jsRound(mins / sessions)} min", "a session")
            } else {
                Stat(if (loggedOn(day)) "Done" else "—", if (kind == DayKind.Today) "today" else "that day")
            }
        }
    }
    Section(if (cutting) "This week" else if (minutes) "Minutes, this week" else "This week", "${Day.shortDay(monday)} – ${Day.shortDay(week.last())}", top = 18.dp)
    if (cutting || minutes) WeekBars(week, day, s.todayIso, { amountOn(it) }, { loggedOn(it) })
    else WeekMarks(week, day, s.todayIso, { loggedOn(it) }, { d -> logs.filter { it.date == d }.mapNotNull { it.amount }.sum().takeIf { it > 0 } })
    Rule()
    if (cutting) {
        val today = logs.filter { it.date == day }.sortedWith(compareBy({ it.at == null }, { it.at }))
        Section(if (kind == DayKind.Today) "Today" else Day.cardDay(day), if (today.isEmpty()) null else "${Fmt.num(amountOn(day))} counted")
        if (today.isEmpty()) Quiet("None logged ${if (kind == DayKind.Today) "today" else "that day"}.")
        // A log can count more than one: "2 cigarettes" is one row that counts 2.
        today.forEachIndexed { i, h ->
            val n = h.amount ?: 1.0
            HabitLogRowView(h, glyph, tone, picked, if (n > 1.0) "${Fmt.num(n)} at once" else "${ordinal(i + 1)} ${if (kind == DayKind.Today) "today" else "that day"}", null)
        }
    } else {
        val recent = logs.filter { it.date <= day }.sortedWith(compareByDescending<HabitLogRow> { it.date }.thenByDescending { it.at }).take(3)
        Section("Recent", if (minutes) "minutes" else null)
        if (recent.isEmpty()) Quiet("Nothing logged yet.")
        recent.forEach { h ->
            HabitLogRowView(h, glyph, tone, picked, h.amount?.takeIf { minutes }?.let { "${Fmt.num(it)} min" },
                if (h.date == s.todayIso) "Today" else Day.cardDay(h.date))
        }
    }
    ReportButton("Open Habits", vm::openHabits)
}

private fun ordinal(n: Int) = n.toString() + when {
    n % 100 in 11..13 -> "th"
    n % 10 == 1 -> "st"
    n % 10 == 2 -> "nd"
    n % 10 == 3 -> "rd"
    else -> "th"
}

@Composable
private fun HabitLogRowView(h: HabitLogRow, glyph: ImageVector, tone: DayTone, picked: String?, figure: String?, sub: String?) {
    val isPicked = picked == "habit:${h.id}"
    SheetRow(
        time = clockOf(h.at), title = h.note?.takeIf { it.isNotBlank() }?.let(DayRail::title) ?: DayRail.title(h.habit),
        tone = tone, picked = isPicked, mark = { Coin(glyph, tone) }, sub = sub, figure = figure,
    )
}

/** A bar per day with its figure on top, today in ink; a day with no log is an empty ring, never a zero bar. */
@Composable
private fun WeekBars(week: List<String>, day: String, today: String, value: (String) -> Double, logged: (String) -> Boolean) {
    val max = week.maxOf { value(it) }.coerceAtLeast(1.0)
    Row(Modifier.fillMaxWidth().height(118.dp).padding(top = 6.dp), horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.Bottom) {
        week.forEach { d ->
            Column(Modifier.weight(1f).fillMaxHeight(), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Bottom) {
                when {
                    d > today -> Box(Modifier.padding(bottom = 6.dp).size(4.dp).background(C.line, CircleShape))
                    !logged(d) -> Box(Modifier.padding(bottom = 2.dp).size(14.dp).border(1.4.dp, C.border, CircleShape))
                    else -> {
                        val v = value(d)
                        Text(Fmt.num(v), style = T.day.copy(fontSize = 12.sp, fontWeight = FontWeight.ExtraBold), modifier = Modifier.padding(bottom = 5.dp))
                        Box(Modifier.width(30.dp).height((88 * (v / max)).coerceAtLeast(8.0).dp).clip(RoundedCornerShape(9.dp)).background(if (d == day) C.ink else C.deepHabit))
                    }
                }
            }
        }
    }
    DayLetters(week, day)
}

/** The week as marks: filled on a day logged, with its minutes inside when the log has them. */
@Composable
private fun WeekMarks(week: List<String>, day: String, today: String, logged: (String) -> Boolean, minutes: (String) -> Double?) {
    Row(Modifier.fillMaxWidth().padding(top = 10.dp), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        week.forEach { d ->
            Box(Modifier.weight(1f).height(34.dp), contentAlignment = Alignment.Center) {
                when {
                    d > today -> Box(Modifier.size(6.dp).background(C.line, CircleShape))
                    logged(d) -> Box(Modifier.size(34.dp).background(C.deepHabit, CircleShape), contentAlignment = Alignment.Center) {
                        minutes(d)?.let { Text(Fmt.num(it), style = T.day.copy(fontSize = 11.sp, fontWeight = FontWeight.ExtraBold, color = C.white)) }
                    }
                    else -> Box(Modifier.size(34.dp).border(if (d == day) 2.dp else 1.5.dp, if (d == day) C.ink else C.border, CircleShape))
                }
            }
        }
    }
    DayLetters(week, day)
}

@Composable
private fun DayLetters(week: List<String>, day: String) {
    Row(Modifier.fillMaxWidth().padding(top = 6.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        week.forEachIndexed { i, d ->
            Text(
                listOf("M", "T", "W", "T", "F", "S", "S")[i],
                style = T.day.copy(fontSize = 11.5.sp, fontWeight = if (d == day) FontWeight.ExtraBold else FontWeight.SemiBold, color = if (d == day) C.ink else C.faint, textAlign = TextAlign.Center),
                modifier = Modifier.weight(1f),
            )
        }
    }
}

/* ─── To-do ───────────────────────────────────────────────────────────── */

@Composable
private fun ColumnScope.TodoSheet(s: AppState, day: String, kind: DayKind, picked: String?, vm: SpicaViewModel, onChat: () -> Unit) {
    val tone = toneOf(DaySheet.Work)
    val open = when (kind) {
        DayKind.Today -> Tasks.sortTasks(s.todos.filter { !it.done && it.due != null && it.due <= day })
        DayKind.Ahead -> Tasks.sortTasks(s.todos.filter { !it.done && it.due == day })
        DayKind.Past -> emptyList()
    }
    val late = if (kind == DayKind.Today) Tasks.lateCount(s.todos, day) else 0
    val done = s.todos.filter { it.done && it.doneOn == day }.sortedWith(compareBy({ it.doneAt == null }, { it.doneAt }))
    Head("To-do", day, kind)
    Stats {
        if (kind != DayKind.Past) Stat("${open.size}", if (kind == DayKind.Today) "open today" else "due that day")
        if (kind == DayKind.Today) Stat("$late", "late", if (late > 0) C.red else C.ink)
        if (kind != DayKind.Ahead) Stat("${done.size}", if (kind == DayKind.Today) "done today" else "done that day")
    }
    Rule()
    if (kind != DayKind.Past) {
        Section("Open", if (kind == DayKind.Today) "due today or late" else null)
        if (open.isEmpty()) Quiet(if (kind == DayKind.Today) "Nothing due today." else "Nothing due that day.")
        open.forEach { t ->
            val project = Tasks.projectOf(t.project, s.projects)?.name?.let(DayRail::title) ?: "No project"
            val lateBy = if (t.due != null && t.due < s.todayIso) Tasks.dueLabel(t.due, s.todayIso) else null
            SheetRow(
                time = null, title = DayRail.title(t.name), tone = tone, picked = picked == "task:${t.id}",
                mark = { Coin(PhFill.checkSquare, tone, solid = false) },
                sub = project + (lateBy?.let { " · $it" } ?: ""), subColor = if (lateBy != null) C.red else null,
                trailing = { TaskBox(false, tone.base, t.name) { vm.toggleTodo(t.id) } },
            )
        }
    }
    if (kind != DayKind.Ahead) {
        Section(if (kind == DayKind.Today) "Done today" else "Done that day", if (done.isEmpty()) null else "${done.size}", top = 14.dp)
        if (done.isEmpty()) Quiet("Nothing ticked ${if (kind == DayKind.Today) "yet" else "that day"}.")
        done.forEach { t ->
            val project = Tasks.projectOf(t.project, s.projects)?.name?.let(DayRail::title)
            SheetRow(
                time = null, title = DayRail.title(t.name), tone = tone, picked = picked == "task:${t.id}",
                mark = { Coin(PhFill.checkSquare, tone) }, sub = listOfNotNull(project, t.doneAt?.let(DayRail::clock)).joinToString(" · ").ifEmpty { null },
                trailing = { TaskBox(true, tone.base, t.name) { vm.toggleTodo(t.id) } },
            )
        }
    }
    val allOpen = s.todos.count { !it.done }
    Link("All tasks · $allOpen open", Modifier.padding(top = 14.dp).align(Alignment.CenterHorizontally)) {
        vm.showAllTasks()
        onChat()
    }
    ReportButton("Open Work") { vm.openReport(Mode.Work) }
}

/* ─── Activity ────────────────────────────────────────────────────────── */

@Composable
private fun ColumnScope.ActivitySheet(s: AppState, day: String, kind: DayKind, vm: SpicaViewModel, onConnectHealth: () -> Unit) {
    val tone = toneOf(DaySheet.Activity)
    val w = s.plan?.workout?.takeIf { kind == DayKind.Today && it.kind != "rest" }
    val done = "workout" in s.planDone || s.plan?.done == true
    if (w == null) {
        Head("Activity", day, kind, sub = if (kind == DayKind.Today) "Today · from Health Connect" else Day.cardDay(day))
    } else {
        // On foot, the picture leads, the sheet's full width and cropped to fit — it is the session.
        if (onFoot(w)) Cover(w.imageUrl, tone, DayRail.title(w.name), Modifier.padding(top = 16.dp))
        Text("Activity · today, ${if (onFoot(w)) "on foot" else "strength"}", style = T.day.copy(fontSize = 12.5.sp, fontWeight = FontWeight.Bold, color = tone.ink), modifier = Modifier.padding(top = 14.dp))
        Text(DayRail.title(w.name), style = SheetType.title, modifier = Modifier.padding(top = 2.dp))
        Row(Modifier.padding(top = 2.dp), verticalAlignment = Alignment.CenterVertically) {
            if (w.idea) AmberDot()
            Text(
                listOfNotNull(if (w.idea) "Suggested" else "Planned", w.minutes?.let { "$it min" }, w.exercises.size.takeIf { it > 0 }?.let { if (it == 1) "1 exercise" else "$it exercises" })
                    .joinToString(" · "),
                style = SheetType.lab,
            )
        }
        if (w.exercises.isNotEmpty()) Session(w, s, tone)
        else Stats {
            // What the walk is for: its minutes, the steps so far, the day's step target. Unknown is a dash.
            Stat(w.minutes?.let { "$it min" } ?: "—", "planned")
            Stat(s.activity?.steps?.let(Fmt::indian) ?: "—", "steps so far")
            Stat(s.profile.stepTarget?.let(Fmt::indian) ?: "—", "step target")
        }
    }
    ThisWeek(s, kind, tone, onConnectHealth)
    if (w != null && !done) ReportButton("Done") { vm.doneWorkout(w) }
}

/** A picture across the sheet's full width, cropped to fit; the glyph on the same tile while it loads, when there is none or when it fails. */
@Composable
private fun Cover(url: String?, tone: DayTone, label: String, modifier: Modifier = Modifier) {
    val shape = RoundedCornerShape(22.dp)
    val fallback: @Composable () -> Unit = {
        Box(Modifier.fillMaxSize().background(tone.mist), contentAlignment = Alignment.Center) { Glyph(PhFill.sneakerMove, 48.dp, tone.base) }
    }
    Box(modifier.fillMaxWidth().height(176.dp).clip(shape).background(tone.mist).semantics { contentDescription = label }) {
        if (url.isNullOrBlank()) fallback()
        else SubcomposeAsyncImage(
            model = url, contentDescription = null, contentScale = ContentScale.Crop, modifier = Modifier.fillMaxSize(),
            loading = { fallback() }, error = { fallback() },
        )
    }
}

/** The session: four exercises, the rest a tap away. A library exercise shows its picture and opens its video; one the model invented has a numbered mark. */
@Composable
private fun Session(w: PlanWorkout, s: AppState, tone: DayTone) {
    var all by remember { mutableStateOf(false) }
    val uri = LocalUriHandler.current
    Section("The session", top = 16.dp)
    val shown = if (all) w.exercises else w.exercises.take(4)
    shown.forEachIndexed { i, x ->
        val lib = x.exerciseId?.let { id -> s.exercises.firstOrNull { it.id == id } }
        Row(Modifier.fillMaxWidth().padding(vertical = 5.dp), verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.then(if (lib?.sourceUrl != null) Modifier.tap { runCatching { uri.openUri(lib.sourceUrl) } } else Modifier)) {
                if (lib?.imageUrl != null || lib?.sourceUrl != null) {
                    Picture(lib.imageUrl, PhFill.barbell, tone, 56.dp, 12.dp, "Watch ${x.name}")
                    if (lib.sourceUrl != null) Box(Modifier.align(Alignment.Center).size(22.dp).background(C.white, CircleShape), contentAlignment = Alignment.Center) {
                        Glyph(PhFill.play, 9.dp, C.ink)
                    }
                } else {
                    Box(Modifier.size(56.dp).clip(RoundedCornerShape(12.dp)).background(tone.mist), contentAlignment = Alignment.Center) {
                        Text("${i + 1}", style = T.day.copy(fontSize = 16.sp, fontWeight = FontWeight.ExtraBold, color = tone.base))
                    }
                }
            }
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(DayRail.title(x.name), style = T.day.copy(fontSize = 15.sp, fontWeight = FontWeight.Bold, lineHeight = 19.sp))
                if (x.detail.isNotBlank()) Text(x.detail, style = SheetType.meta.copy(fontSize = 12.5.sp, color = C.muted))
            }
        }
    }
    if (!all && w.exercises.size > 4) Link("+ ${w.exercises.size - 4} more · see the whole session", Modifier.padding(top = 4.dp)) { all = true }
}

/** This week's active minutes from Health Connect: a bar per day, strength and on-foot told apart by lightness, then the totals. */
@Composable
private fun ColumnScope.ThisWeek(s: AppState, kind: DayKind, tone: DayTone, onConnectHealth: () -> Unit) {
    Section("This week", "active minutes", top = 18.dp)
    when (s.healthAccess) {
        HealthAccess.Unavailable -> { Quiet("Steps and workouts come from Health Connect, which isn't on this phone."); return }
        HealthAccess.NotGranted -> {
            Quiet("Steps, runs and workouts — read from Health Connect, on this phone only.")
            Link("Connect Health Connect", onClick = onConnectHealth)
            return
        }
        else -> Unit
    }
    val today = s.todayIso
    val monday = Day.addDays(today, -Day.weekIndex(today))
    val week = (0..6).map { Day.addDays(monday, it) }
    val sessions = s.activity?.week.orEmpty()
    fun foot(k: String) = k.equals("Running", true) || k.equals("Walking", true)
    val max = week.maxOf { d -> sessions.filter { it.date == d }.sumOf { it.minutes } }.coerceAtLeast(1)
    Row(Modifier.fillMaxWidth().height(70.dp).padding(top = 6.dp), horizontalArrangement = Arrangement.spacedBy(12.dp), verticalAlignment = Alignment.Bottom) {
        week.forEach { d ->
            val ds = sessions.filter { it.date == d }
            Column(Modifier.weight(1f).fillMaxHeight(), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Bottom) {
                when {
                    d > today -> Box(Modifier.padding(bottom = 4.dp).size(4.dp).background(C.line, CircleShape))
                    ds.isEmpty() -> Box(Modifier.size(14.dp).border(if (d == today) 2.dp else 1.4.dp, if (d == today) C.ink else C.border, CircleShape))
                    else -> {
                        val strength = ds.filter { !foot(it.kind) }.sumOf { it.minutes }
                        val onFoot = ds.filter { foot(it.kind) }.sumOf { it.minutes }
                        if (onFoot > 0) Box(Modifier.width(26.dp).height((60f * onFoot / max).coerceAtLeast(6f).dp).clip(RoundedCornerShape(7.dp)).background(C.deepDietSoft))
                        if (strength > 0) Box(Modifier.padding(top = 2.dp).width(26.dp).height((60f * strength / max).coerceAtLeast(6f).dp).clip(RoundedCornerShape(7.dp)).background(tone.base))
                    }
                }
            }
        }
    }
    DayLetters(week, today)
    val strength = sessions.filter { !foot(it.kind) }
    val onFoot = sessions.filter { foot(it.kind) }
    Stats {
        Stat(if (strength.isEmpty()) "—" else "${strength.sumOf { it.minutes }} min", "strength · ${strength.size}")
        Stat(if (onFoot.isEmpty()) "—" else "${onFoot.sumOf { it.minutes }} min", "on foot · ${onFoot.size}")
        Stat(s.activity?.steps?.let(Fmt::indian) ?: "—", "steps today")
    }
    if (s.healthAccess == HealthAccess.Granted && s.activity == null) Quiet("Couldn't read Health Connect just now.")
}
