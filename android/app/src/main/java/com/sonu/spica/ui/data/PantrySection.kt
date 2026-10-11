package com.sonu.spica.ui.data

import com.sonu.spica.ui.common.ActionPill
import com.sonu.spica.ui.common.AddRow
import com.sonu.spica.ui.common.BackStep
import com.sonu.spica.ui.common.FilterPill
import com.sonu.spica.ui.common.PillKind
import com.sonu.spica.ui.common.divider
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.sonu.spica.data.Api
import com.sonu.spica.data.PantryRow
import com.sonu.spica.data.PantryStatus
import com.sonu.spica.lib.Day
import com.sonu.spica.lib.Fmt
import com.sonu.spica.state.AppState
import com.sonu.spica.state.SpicaViewModel
import com.sonu.spica.ui.common.InlineField
import com.sonu.spica.ui.common.TrayToggle
import com.sonu.spica.ui.common.fadeUp
import com.sonu.spica.ui.common.plainTap
import com.sonu.spica.ui.common.tap
import com.sonu.spica.ui.home.topRule
import com.sonu.spica.ui.profile.SelectPill
import com.sonu.spica.ui.report.Card
import com.sonu.spica.ui.report.reportCard
import com.sonu.spica.ui.theme.C
import com.sonu.spica.ui.theme.F
import com.sonu.spica.ui.theme.T
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.launch
import kotlin.math.abs
import kotlin.math.max
import kotlin.math.roundToInt
import com.sonu.spica.ui.common.Glyph
import com.sonu.spica.ui.common.PhBold

// Class names carry the section's prefix: private top-level classes still share
// the package's JVM namespace with the other sections' files.
private enum class PantryTab { Buy, Stock, Moves, Staple }

private enum class PantryAsk { Purchase, Opening, Settings }

private data class PantryPrompt(val row: String, val kind: PantryAsk)

/** The section's shared UI state — one tray and one prompt open at a time, across every tab. */
private class PantryUi {
    var view by mutableStateOf(PantryTab.Buy)
    var open by mutableStateOf<String?>(null)
    var prompt by mutableStateOf<PantryPrompt?>(null)

    /** Moves filtered to one food, set from a row's History. */
    var focus by mutableStateOf<PantryRow?>(null)

    fun toggle(id: String) {
        open = if (open == id) null else id
        prompt = null
    }
}

/** Buy is the shopping list: things that ran out or went off. No cadence. */
private val BUY = setOf(PantryStatus.Out, PantryStatus.Stale, PantryStatus.Soon)

private fun word(s: PantryStatus) = when (s) {
    PantryStatus.Staple -> ""
    PantryStatus.New -> "not counted"
    PantryStatus.Out -> "out"
    PantryStatus.Stale -> "stale"
    PantryStatus.Soon -> "soon"
    PantryStatus.Ok -> "ok"
}

/** Past its life or gone is red; running low is plain ink. Amber is only the estimate dot. */
private fun toneOf(s: PantryStatus) = when (s) {
    PantryStatus.Staple, PantryStatus.New -> C.faint
    PantryStatus.Out, PantryStatus.Stale -> C.red
    PantryStatus.Soon -> C.ink
    PantryStatus.Ok -> C.muted
}

private fun unitLabel(unit: String) = if (unit == "piece") "pcs" else unit

/** A settings field: blank or unreadable is no rule, as the web's `Number()` → null is. */
private fun ruleValue(raw: String): Double? = raw.trim().toDoubleOrNull()?.takeIf { it.isFinite() }

/**
 * When it came in, then what that means now: *11 Aug*, *22 Aug · 2d left*,
 * *22 Aug · 1d over*. The date answers "is this the one I bought last week";
 * the days answer "can I still eat it". A shelf-stable food that is fine
 * shows only its date.
 */
private fun whenLine(r: PantryRow, today: String): String {
    if (r.status == PantryStatus.Staple) return ""
    if (r.status == PantryStatus.New) return "not counted yet"
    val parts = mutableListOf<String>()
    if (r.lastIn != null) parts += Day.shortDay(r.lastIn)
    val life = r.shelfLifeDays
    if (r.status == PantryStatus.Out) {
        parts += "nothing left"
    } else if (life != null && life != 0 && r.lastIn != null) {
        val left = life - Day.diffDays(r.lastIn, today)
        parts += when {
            left < 0 -> "${-left}d over"
            left == 0 -> "today"
            else -> "${left}d left"
        }
    } else if (r.status == PantryStatus.Soon && r.reorderAtG != null) {
        parts += "below ${Api.inUnit(r.reorderAtG, r.unit)}"
    }
    return parts.joinToString(" · ")
}

private val PillShape = RoundedCornerShape(14.dp)
private val FieldShape = RoundedCornerShape(8.dp)

/** The white bordered card every tab's list sits in. */
private fun Modifier.shell() = this.fillMaxWidth().reportCard().clip(Card)

/** The section's small mono buttons. Filled green is the one that saves. */
@Composable
private fun PantryPill(
    label: String,
    color: Color = C.muted,
    border: Color = C.border,
    bg: Color = C.paper,
    modifier: Modifier = Modifier,
    onClick: () -> Unit,
) {
    // The callers still say it in the web's colours; the kit's pill reads them as a kind.
    Box(modifier) {
        when {
            bg == C.brand -> ActionPill(label, onClick, PillKind.Primary)
            color == C.red -> ActionPill(label, onClick, PillKind.Danger)
            color == C.brand -> Text(
                label,
                style = T.sans.copy(fontSize = 16.sp, lineHeight = 20.4.sp, fontWeight = androidx.compose.ui.text.font.FontWeight.Medium, color = C.brand),
                modifier = Modifier.clip(PillShape).background(C.brandTint).tap(onClick = onClick).padding(horizontal = 16.dp, vertical = 9.dp),
            )
            else -> ActionPill(label, onClick)
        }
    }
}

/** The web's checkbox: a 13dp square, green when ticked. */
@Composable
private fun PantryTick(on: Boolean) {
    val shape = RoundedCornerShape(3.dp)
    Box(
        Modifier.size(20.dp).clip(CircleShape).background(if (on) C.brand else C.white).border(1.5.dp, if (on) C.brand else C.border, CircleShape),
        contentAlignment = Alignment.Center,
    ) {
        if (on) Glyph(PhBold.check, 11.dp, C.white)
    }
}

/**
 * Your data → Pantry. `spec/done/pantry-view.md`, port of `PantrySection.tsx`.
 *
 * Four tabs. **Buy** is the shopping list — what ran out, went off, or fell
 * below its reorder level. **Stock** is everything counted, with its status.
 * **Moves** is the ledger those numbers come from. **Staple** is what is always
 * in the house, where a quantity would be meaningless.
 *
 * Nothing here edits a quantity: a wrong number gets a correction, a drifted
 * one gets a stock-take. Staple is the user's declaration, not a derivation —
 * eggs cycle even when no purchase has been logged, and atta never will.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun PantrySection(vm: SpicaViewModel, s: AppState) {
    val ui = remember { PantryUi() }
    val scope = rememberCoroutineScope()

    var adding by remember { mutableStateOf(false) }
    var newName by remember { mutableStateOf("") }
    var newGrams by remember { mutableStateOf("") }
    var newStaple by remember { mutableStateOf(false) }
    var newUnit by remember { mutableStateOf("g") }
    var addFailed by remember { mutableStateOf(false) }
    var addBusy by remember { mutableStateOf(false) }

    // Refetching on focus is the point: History narrows the ledger to one food.
    LaunchedEffect(ui.focus?.foodId) { vm.loadPantryMoves(ui.focus?.foodId) }

    val rows = s.pantry
    val buy = rows.filter { it.status in BUY }
    // Stock is the whole counted inventory, Buy the subset that needs action —
    // the same relationship the Paisa report's All and Pending have.
    val stock = rows.filter { !it.staple }
    val staples = rows.filter { it.staple }

    // Back closes what is open before it leaves the section — a quantity
    // prompt, then the row's tray, then the add form, then History's one-food
    // filter (back to Stock). Only what is on screen: the tray is shared
    // across tabs, and a press must never close something unseen. The last
    // one listed goes first.
    val tabRows = when (ui.view) {
        PantryTab.Buy -> buy
        PantryTab.Stock -> stock
        PantryTab.Staple -> staples
        PantryTab.Moves -> emptyList()
    }
    fun onScreen(id: String?) = id != null && tabRows.any { it.id == id }
    BackStep(ui.focus != null && ui.view == PantryTab.Moves) {
        ui.focus = null
        ui.view = PantryTab.Stock
    }
    BackStep(adding && ui.view == PantryTab.Stock) { adding = false }
    BackStep(onScreen(ui.open)) {
        ui.open = null
        ui.prompt = null
    }
    BackStep(onScreen(ui.prompt?.row)) { ui.prompt = null }

    fun addFood() {
        if (addBusy) return
        addBusy = true
        scope.launch {
            // A staple's quantity field is disabled and shows empty, so nothing
            // typed into it before the tick may land as an opening stock.
            val qty = if (!newStaple && newGrams.isNotEmpty()) Api.parseQuantity(newGrams, newUnit) else null
            val ok = vm.addPantryFood(newName, qty, newStaple, newUnit)
            addBusy = false
            if (ok) {
                newName = ""
                newGrams = ""
                newStaple = false
                newUnit = "g"
                adding = false
                addFailed = false
            } else {
                addFailed = true
            }
        }
    }

    FlowRow(Modifier.padding(bottom = 14.dp), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        listOf(
            PantryTab.Buy to "Buy${if (buy.isNotEmpty()) " · ${buy.size}" else ""}",
            PantryTab.Stock to "Stock · ${stock.size}",
            PantryTab.Moves to (ui.focus?.let { "Moves · ${it.name}" } ?: "Moves"),
            PantryTab.Staple to "Staple · ${staples.size}",
        ).forEach { (id, label) ->
            FilterPill(label, ui.view == id, {
                ui.view = id
                if (id != PantryTab.Moves) ui.focus = null
            })
        }
    }

    when (ui.view) {
        PantryTab.Buy -> Column(Modifier.shell()) {
            if (buy.isEmpty()) {
                Text(
                    "Nothing to buy — nothing is out, stale or running low.",
                    style = T.sans.copy(fontSize = 15.sp, color = C.muted),
                    modifier = Modifier.padding(horizontal = 18.dp, vertical = 14.dp),
                )
            }
            buy.forEachIndexed { i, r -> key(r.id) { PantryItem(r, i == 0, s.todayIso, ui, vm, scope) } }
        }

        // No quantities, by design: nobody weighs the family's atta.
        // 'Count it' moves a row over to Stock.
        PantryTab.Staple -> Column(Modifier.shell()) {
            staples.forEachIndexed { i, r -> key(r.id) { PantryItem(r, i == 0, s.todayIso, ui, vm, scope) } }
        }

        PantryTab.Stock -> {
            Column(Modifier.shell()) {
                stock.forEachIndexed { i, r -> key(r.id) { PantryItem(r, i == 0, s.todayIso, ui, vm, scope) } }
            }
            Column(Modifier.fillMaxWidth().padding(top = 10.dp)) {
                if (adding) {
                    Column(Modifier.shell().padding(horizontal = 18.dp, vertical = 14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                            InlineField(
                                newName, { newName = it }, Modifier.weight(1f),
                                placeholder = "What is it — soya chunks", mono = false, autoFocus = true, onDone = ::addFood,
                            )
                            if (newStaple) {
                                // Disabled, as the web's input is: a staple has no quantity to give.
                                Text(
                                    "how much",
                                    style = T.mono.copy(fontSize = 15.sp, color = C.faint),
                                    maxLines = 1,
                                    modifier = Modifier.width(84.dp).alpha(0.6f).background(C.paper, FieldShape).border(1.dp, C.line, FieldShape)
                                        .padding(horizontal = 10.dp, vertical = 7.dp),
                                )
                            } else {
                                InlineField(
                                    newGrams, { newGrams = it }, Modifier.width(84.dp),
                                    placeholder = "how much", decimal = newUnit != "piece", onDone = ::addFood,
                                )
                            }
                            // What it is counted in. Eggs by the piece, milk in ml.
                            SelectPill(unitLabel(newUnit), listOf("g", "ml", "pcs")) { newUnit = if (it == "pcs") "piece" else it }
                        }
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                            Row(
                                Modifier.plainTap { newStaple = !newStaple },
                                horizontalArrangement = Arrangement.spacedBy(6.dp),
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                PantryTick(newStaple)
                                Text("always here", style = T.sans.copy(fontSize = 13.sp, color = C.muted))
                            }
                            Text(
                                if (addFailed) "Not saved — it may already be tracked." else "How much is optional.",
                                style = T.sans.copy(fontSize = 13.sp, color = if (addFailed) C.red else C.muted),
                                modifier = Modifier.weight(1f),
                            )
                            PantryPill("Cancel") { adding = false }
                            PantryPill("Save", C.white, C.brand, C.brand, onClick = ::addFood)
                        }
                    }
                } else {
                    AddRow("Add item", { adding = true }, Modifier.shell())
                }
            }
        }

        PantryTab.Moves -> Column(Modifier.shell()) {
            val moves = s.pantryMoves
            if (moves.isEmpty()) {
                Text(
                    "Nothing moved yet.",
                    style = T.sans.copy(fontSize = 15.sp, color = C.muted),
                    modifier = Modifier.padding(horizontal = 18.dp, vertical = 14.dp),
                )
            }
            moves.forEachIndexed { i, m ->
                Row(
                    Modifier.fillMaxWidth().then(if (i > 0) Modifier.divider(18.dp, 18.dp) else Modifier).padding(start = 13.dp, end = 8.dp, top = 10.dp, bottom = 10.dp),
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    Text(Day.shortDay(m.day), style = T.mono.copy(fontSize = 12.5.sp, color = C.faint), maxLines = 1, modifier = Modifier.width(44.dp).alignByBaseline())
                    Text(
                        (if (m.quantity > 0) "+" else "−") + Api.inUnit(abs(m.quantity), m.unit),
                        // Food in is Diet's ink; food out is plain. Never Jamun — this is data.
                        style = T.mono.copy(fontSize = 13.sp, fontWeight = FontWeight.SemiBold, color = if (m.quantity > 0) C.dietInk else C.muted),
                        maxLines = 1,
                        modifier = Modifier.width(68.dp).alignByBaseline(),
                    )
                    Text(
                        buildAnnotatedString {
                            append(m.name)
                            withStyle(SpanStyle(fontFamily = F.mono, fontSize = 12.5.sp, color = C.faint)) { append("  ${m.dish ?: m.kind}") }
                        },
                        style = T.sans.copy(fontSize = 15.sp),
                        modifier = Modifier.weight(1f).alignByBaseline(),
                    )
                    // Consumption belongs to its meal — undoing it here would
                    // strand the meal, so only user-written moves offer it.
                    if (m.kind != "consumption") PantryPill("Undo", modifier = Modifier.alignByBaseline()) { vm.undoPantryMove(m.id) }
                }
            }
        }
    }
}

/** One pantry row: name and its when-line, the stock figure, the status word, and its ⋮ tray. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun PantryItem(r: PantryRow, first: Boolean, today: String, ui: PantryUi, vm: SpicaViewModel, scope: CoroutineScope) {
    val line = whenLine(r, today)
    val ask = ui.prompt?.takeIf { it.row == r.id }?.kind
    Column(if (first) Modifier.fillMaxWidth() else Modifier.fillMaxWidth().topRule()) {
        Row(Modifier.fillMaxWidth().padding(start = 13.dp, end = 6.dp, top = 11.dp, bottom = 11.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            // Opens the row where it stands. It used to jump to the Moves tab,
            // which read as the item having moved — and nothing moves except by
            // a purchase or a meal.
            Text(
                buildAnnotatedString {
                    append(r.name)
                    if (line.isNotEmpty()) withStyle(SpanStyle(fontFamily = F.mono, fontSize = 12.5.sp, color = C.faint)) { append("  $line") }
                },
                style = T.sans.copy(fontSize = 15.sp),
                modifier = Modifier.weight(1f).alignByBaseline().clip(RoundedCornerShape(6.dp)).tap { ui.toggle(r.id) },
            )
            // No number for a staple or a food nothing has been logged into:
            // there is no stock figure, and a negative consumption sum is not one.
            if (r.status != PantryStatus.Staple && r.status != PantryStatus.New) {
                Text(
                    Api.inUnit(r.stockG, r.unit),
                    style = T.mono.copy(
                        fontSize = 13.sp,
                        fontWeight = FontWeight.SemiBold,
                        // Stale still shows the number, greyed: it is what the ledger
                        // says, and the word beside it says why not to trust it.
                        color = when (r.status) {
                            PantryStatus.Stale -> C.faint
                            PantryStatus.Out -> C.red
                            else -> C.muted
                        },
                    ),
                    maxLines = 1,
                    softWrap = false,
                    modifier = Modifier.alignByBaseline(),
                )
            }
            val w = word(r.status)
            if (w.isNotEmpty()) {
                Text(w, style = T.mono.copy(fontSize = 12.5.sp, color = toneOf(r.status)), maxLines = 1, softWrap = false, modifier = Modifier.alignByBaseline())
            }
            Box(Modifier.alignByBaseline()) { TrayToggle { ui.toggle(r.id) } }
        }

        if (ui.open == r.id && ui.prompt == null) {
            FlowRow(
                Modifier.fillMaxWidth().fadeUp(200).padding(start = 8.dp, end = 8.dp, bottom = 9.dp),
                horizontalArrangement = Arrangement.spacedBy(7.dp, Alignment.End),
                verticalArrangement = Arrangement.spacedBy(7.dp),
            ) {
                PantryPill("Bought", C.brand, C.brand) { ui.prompt = PantryPrompt(r.id, PantryAsk.Purchase) }
                PantryPill("Have") { ui.prompt = PantryPrompt(r.id, PantryAsk.Opening) }
                if (!r.staple) PantryPill("Settings") { ui.prompt = PantryPrompt(r.id, PantryAsk.Settings) }
                PantryPill(if (r.staple) "Count it" else "Always here") {
                    scope.launch { vm.setStaple(r.id, !r.staple) }
                    ui.open = null
                }
                PantryPill("History") {
                    ui.focus = r
                    ui.view = PantryTab.Moves
                    ui.open = null
                }
                PantryPill("Stop tracking", C.red, C.redBorder) {
                    vm.stopTrackingFood(r.id)
                    ui.open = null
                }
            }
        }

        if (ask == PantryAsk.Purchase || ask == PantryAsk.Opening) {
            val purchase = ask == PantryAsk.Purchase
            QuantityPrompt(
                initial = if (purchase) r.lastInG?.let { Fmt.num(it) } ?: "" else Fmt.num(max(0.0, r.stockG)),
                unit = r.unit,
                label = if (purchase) "Bought" else "Have",
                hint = when {
                    !purchase -> "What is actually on the shelf — a stock-take, counted from now."
                    r.unit == "piece" -> "How many came in today — \"1 dozen\" works."
                    else -> "How much came in today."
                },
                onSave = { g ->
                    vm.addPantryMove(r.foodId, g, if (purchase) "purchase" else "opening").also { if (it) ui.open = null }
                },
                onClose = { ui.prompt = null },
            )
        }
        if (ask == PantryAsk.Settings) {
            PantrySettings(
                r,
                onSave = { reorder, life -> vm.savePantrySettings(r.id, reorder, life).also { if (it) ui.open = null } },
                onClose = { ui.prompt = null },
            )
        }
    }
}

/**
 * One number, in the food's own unit. Enter saves; a refusal keeps it open.
 * For a food counted in pieces it also understands "1 dozen".
 */
@Composable
private fun QuantityPrompt(
    initial: String,
    unit: String,
    label: String,
    hint: String,
    onSave: suspend (Double) -> Boolean,
    onClose: () -> Unit,
) {
    var draft by remember { mutableStateOf(initial) }
    var failed by remember { mutableStateOf(false) }
    var busy by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    fun save() {
        if (busy) return
        busy = true
        scope.launch {
            val ok = onSave(Api.parseQuantity(draft, unit))
            busy = false
            if (ok) onClose() else failed = true
        }
    }
    Column(Modifier.fillMaxWidth().fadeUp(200).padding(start = 18.dp, end = 18.dp, bottom = 11.dp)) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            // Pieces take text, so "1 dozen" can be typed.
            InlineField(
                draft, {
                    draft = it
                    failed = false
                },
                Modifier.width(90.dp), decimal = unit != "piece", autoFocus = true, onDone = ::save,
            )
            Text(unitLabel(unit), style = T.mono.copy(fontSize = 14.sp, color = C.muted))
            Spacer(Modifier.weight(1f))
            PantryPill("Cancel", onClick = onClose)
            PantryPill(label, C.white, C.brand, C.brand, onClick = ::save)
        }
        Text(
            if (failed) "Not saved — it must be a number above zero." else hint,
            style = T.sans.copy(fontSize = 13.sp, color = if (failed) C.red else C.muted),
            modifier = Modifier.padding(top = 6.dp),
        )
    }
}

/** The two rules a counted food can carry: when to buy more, and how long it keeps. Neither is a quantity. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun PantrySettings(r: PantryRow, onSave: suspend (Double?, Int?) -> Boolean, onClose: () -> Unit) {
    var reorder by remember { mutableStateOf(r.reorderAtG?.let { Fmt.num(it) } ?: "") }
    var life by remember { mutableStateOf(r.shelfLifeDays?.toString() ?: "") }
    var failed by remember { mutableStateOf(false) }
    var busy by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    fun save() {
        if (busy) return
        busy = true
        scope.launch {
            val ok = onSave(ruleValue(reorder), ruleValue(life)?.roundToInt())
            busy = false
            if (ok) onClose() else failed = true
        }
    }
    val label = T.sans.copy(fontSize = 13.sp, color = C.muted)
    val unitStyle = T.mono.copy(fontSize = 14.sp, color = C.muted)
    Column(Modifier.fillMaxWidth().fadeUp(200).padding(start = 18.dp, end = 18.dp, bottom = 11.dp)) {
        FlowRow(
            Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
            itemVerticalAlignment = Alignment.CenterVertically,
        ) {
            Text("buy below", style = label)
            InlineField(reorder, { reorder = it }, Modifier.width(70.dp), numeric = true, onDone = ::save)
            Text(unitLabel(r.unit), style = unitStyle)
            Text("good for", style = label, modifier = Modifier.padding(start = 6.dp))
            InlineField(life, { life = it }, Modifier.width(60.dp), numeric = true, onDone = ::save)
            Text("days", style = unitStyle)
            // Takes what is left of its line, so the buttons end at the right edge
            // wherever the wrap puts them.
            Row(Modifier.weight(1f), horizontalArrangement = Arrangement.spacedBy(8.dp, Alignment.End), verticalAlignment = Alignment.CenterVertically) {
                PantryPill("Cancel", onClick = onClose)
                PantryPill("Save", C.white, C.brand, C.brand, onClick = ::save)
            }
        }
        Text(
            if (failed) "Not saved — the server refused." else "Blank means no rule. Neither is a quantity.",
            style = T.sans.copy(fontSize = 13.sp, color = if (failed) C.red else C.muted),
            modifier = Modifier.padding(top = 6.dp),
        )
    }
}
