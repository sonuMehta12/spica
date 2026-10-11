package com.sonu.spica.ui.report

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.em
import androidx.compose.ui.unit.sp
import com.sonu.spica.lib.Fmt
import com.sonu.spica.logic.Metrics
import com.sonu.spica.ui.common.BackStep
import com.sonu.spica.ui.common.Coin
import com.sonu.spica.ui.common.InlineField
import com.sonu.spica.ui.common.PanelShape
import com.sonu.spica.ui.common.Tag
import com.sonu.spica.ui.common.divider
import com.sonu.spica.ui.common.panel
import com.sonu.spica.ui.common.KebabIcon
import com.sonu.spica.ui.common.MenuItem
import com.sonu.spica.ui.common.MenuRow
import com.sonu.spica.ui.common.Popover
import com.sonu.spica.ui.common.fadeUp
import com.sonu.spica.ui.common.tap
import com.sonu.spica.ui.home.topRule
import com.sonu.spica.ui.theme.C
import com.sonu.spica.ui.theme.S
import com.sonu.spica.ui.theme.T
import kotlinx.coroutines.launch
import kotlin.math.roundToInt
import com.sonu.spica.ui.common.Glyph
import com.sonu.spica.ui.common.Ph

val Card = PanelShape

/** Every report block is a panel: white, floating on the ground, no border. */
fun Modifier.reportCard() = this.panel()

/* ─── the scorecard ───────────────────────────────────────────────────── */

private fun deltaColor(t: Metrics.Tile) = when {
    t.delta == null || t.delta == 0.0 || t.good == Metrics.Good.None -> C.muted
    (t.good == Metrics.Good.Up) == (t.delta > 0) -> C.brand
    else -> C.red
}

/**
 * One card: the answer, then the context. The first `lead` tiles are the
 * headline; the rest are rows. Port of `Scorecard.tsx`.
 */
@Composable
fun Scorecard(tiles: List<Metrics.Tile>, hasPrev: Boolean, lead: Int, extra: List<Metrics.Tile>) {
    var menu by remember { mutableStateOf(false) }
    var showExtra by remember { mutableStateOf(false) }
    val shown = if (showExtra) tiles + extra else tiles
    val heads = shown.take(lead)
    val rows = shown.drop(lead)
    Box(Modifier.fillMaxWidth().reportCard().padding(start = 20.dp, end = 20.dp, top = 18.dp, bottom = 6.dp)) {
        Column {
            Row(horizontalArrangement = Arrangement.spacedBy(18.dp)) {
                heads.forEach { t ->
                    val one = heads.size == 1
                    Column(Modifier.weight(1f).padding(end = if (extra.isNotEmpty()) 30.dp else 0.dp)) {
                        Text(t.label, style = T.sans.copy(fontSize = 13.sp, lineHeight = 16.sp, fontWeight = FontWeight.Medium, color = C.faint))
                        Text(
                            t.value,
                            style = T.figure.copy(fontWeight = FontWeight.SemiBold, fontSize = if (one) 44.sp else 32.sp, lineHeight = if (one) 48.sp else 36.sp, letterSpacing = (-0.5).sp),
                            modifier = Modifier.padding(top = 4.dp),
                        )
                        // "73% more" — the sign becomes the word.
                        val s = t.deltaLabel
                        Box(Modifier.padding(top = 8.dp, bottom = 14.dp)) {
                            when {
                                s.isNullOrEmpty() -> if (!t.noDelta) Tag(if (hasPrev) "—" else "no prior data", C.faint)
                                else -> {
                                    val word = when (s[0]) {
                                        '+' -> "more"
                                        '−', '-' -> "less"
                                        else -> null
                                    }
                                    Text(
                                        buildAnnotatedString {
                                            withStyle(SpanStyle(color = deltaColor(t), fontWeight = FontWeight.SemiBold)) { append(if (word != null) s.drop(1) else s) }
                                            if (word != null) withStyle(SpanStyle(color = C.muted)) { append(" $word than before") }
                                        },
                                        style = T.sans.copy(fontSize = 13.sp, lineHeight = 16.sp),
                                    )
                                }
                            }
                        }
                    }
                }
            }
            rows.forEach { t ->
                Row(Modifier.fillMaxWidth().divider().padding(vertical = 14.dp), horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text(t.label, style = T.sans.copy(fontSize = 14.5.sp, lineHeight = 18.sp, color = C.ink), modifier = Modifier.weight(1f))
                    if (!t.deltaLabel.isNullOrEmpty()) Text(t.deltaLabel, style = T.sans.copy(fontSize = 13.sp, fontWeight = FontWeight.SemiBold, color = deltaColor(t)))
                    else t.sub?.let { Text(it, style = T.sans.copy(fontSize = 12.5.sp, color = C.faint)) }
                    Text(t.value, style = T.figure.copy(fontSize = 15.sp, fontWeight = FontWeight.SemiBold, color = C.ink), maxLines = 1)
                }
            }
        }
        if (extra.isNotEmpty()) {
            Box(Modifier.align(Alignment.TopEnd)) {
                Box(Modifier.size(32.dp).clip(CircleShape).background(C.surface).tap { menu = !menu }, contentAlignment = Alignment.Center) { KebabIcon(16.dp) }
                if (menu) {
                    Popover(onDismiss = { menu = false }, offset = IntOffset(0, with(LocalDensity.current) { 34.dp.roundToPx() })) {
                        MenuRow(MenuItem("more", if (showExtra) "Hide" else "More") { showExtra = !showExtra }) { menu = false }
                    }
                }
            }
        }
    }
}

/* ─── the donut ───────────────────────────────────────────────────────── */

/**
 * One ring, one legend. Selecting a category dims the rest and puts that
 * slice's figure in the middle. Port of `DonutChart.tsx`.
 */
@Composable
fun DonutChart(rows: List<Metrics.BreakdownRow>, selected: String?, totalStr: String, centreSub: String, fill: Pair<Double, String>?) {
    val scale = fill?.first?.coerceIn(0.0, 1.0) ?: 1.0
    val focus = selected?.let { s -> rows.firstOrNull { it.label == s } }
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(14.dp)) {
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(11.dp)) {
            rows.forEach { r ->
                val dim by animateFloatAsState(if (focus != null && r.label != focus.label) 0.35f else 1f, label = "dim")
                Row(Modifier.alpha(dim), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Box(Modifier.size(10.dp).background(r.color, CircleShape))
                    Text(r.label, style = T.sans.copy(fontSize = 14.sp, lineHeight = 18.sp), maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f))
                    Text("${Fmt.jsRound(r.share * 100)}%", style = T.sans.copy(fontSize = 14.sp, fontWeight = FontWeight.Medium, color = C.muted))
                }
            }
        }
        Box(Modifier.size(140.dp), contentAlignment = Alignment.Center) {
            Canvas(Modifier.size(140.dp)) {
                val k = size.width / 128f
                val r = 52f * k
                val stroke = 16f * k
                val tl = Offset(size.width / 2 - r, size.height / 2 - r)
                val box = Size(r * 2, r * 2)
                drawCircle(C.lineSoft, radius = r, style = Stroke(stroke))
                var start = -90f
                rows.forEach { row ->
                    val sweep = (row.share * scale * 360).toFloat()
                    val dim = focus != null && row.label != focus.label
                    drawArc(row.color, start, sweep, false, tl, box, alpha = if (dim) 0.22f else 1f, style = Stroke(stroke))
                    start += sweep
                }
            }
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text(
                    focus?.valueStr ?: totalStr,
                    style = T.figure.copy(fontWeight = FontWeight.SemiBold, fontSize = if (focus != null) 18.sp else 20.sp, lineHeight = 22.sp, color = focus?.color ?: C.ink),
                )
                Text(
                    when {
                        focus != null -> "${Fmt.jsRound(focus.share * 100)}% of spend"
                        fill != null -> "${Fmt.jsRound(fill.first * 100)}% of ${fill.second}"
                        else -> centreSub
                    },
                    style = T.sans.copy(fontSize = 11.5.sp, color = C.faint, lineHeight = 14.sp, textAlign = TextAlign.Center),
                    modifier = Modifier.padding(top = 3.dp).widthIn(max = 90.dp),
                )
            }
        }
    }
}

/* ─── the item list ───────────────────────────────────────────────────── */

enum class ItemTone { Good, Bad, Warn, Muted }

data class Prompt(val initial: String, val prefix: String? = null, val hint: String, val refused: String)

/** One of the places an action can go — *Counts toward…* offers the month's open commitments, in place. */
data class ItemChoice(val label: String, val run: () -> Unit)

data class ItemAction(
    val label: String, val good: Boolean = false, val prompt: Prompt? = null,
    val choices: List<ItemChoice> = emptyList(), val danger: Boolean = false, val run: suspend (String?) -> Boolean,
)

data class Item(
    val id: String,
    val label: String,
    val sub: String? = null,
    val valueStr: String,
    val tone: ItemTone,
    /** paisa · diet · habit · task · repayment. Null = a read-only row. */
    val kind: String? = null,
    val editText: String? = null,
    val actions: List<ItemAction> = emptyList(),
    /** The commitment a payment settles, and whether that was only a guess — the amber dot before it. */
    val link: String? = null,
    val linkGuess: Boolean = false,
    /** The amber dot before the figure — it was copied from last month, not stated. */
    val valueDot: Boolean = false,
)

private fun toneColor(t: ItemTone) = when (t) {
    ItemTone.Good -> C.brand
    ItemTone.Bad -> C.red
    ItemTone.Warn -> C.ink
    ItemTone.Muted -> C.faint
}

/** An action on a row: a soft pill — Jamun's tint for the good one, red's for delete, the brand filled to confirm. */
@Composable
private fun Tray(label: String, color: androidx.compose.ui.graphics.Color = C.ink, bg: androidx.compose.ui.graphics.Color = C.surface, onClick: () -> Unit) {
    Text(
        label,
        style = T.sans.copy(fontSize = 13.5.sp, lineHeight = 16.sp, fontWeight = FontWeight.Medium, color = color),
        modifier = Modifier.clip(RoundedCornerShape(50)).background(bg).tap(onClick = onClick).padding(horizontal = 14.dp, vertical = 8.dp),
    )
}

/**
 * The selected tab's contents. Money, meals, habits and sleep all reduce to
 * label · sub · value, and one ⋮ tray. Port of `ItemList.tsx`.
 */
@Composable
fun ItemList(items: List<Item>, onEdit: (String, String, String) -> Unit, onDelete: (String, String) -> Unit, empty: String = "Nothing in this period.") {
    var open by remember { mutableStateOf<String?>(null) }
    var choosing by remember { mutableStateOf<Pair<String, String>?>(null) }
    var prompt by remember { mutableStateOf<Triple<String, String, String>?>(null) }
    var refused by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    // Back closes what is open in the list before it leaves the page: the
    // amount being typed, then the lines it could count toward, then the
    // tray. Only what is on screen — a tab switch can leave a row's state
    // behind, and a press must never close something unseen.
    fun shown(id: String?) = id != null && items.any { it.id == id }
    BackStep(shown(open)) {
        open = null
        choosing = null
    }
    BackStep(choosing?.first?.let { it == open && shown(it) } == true) { choosing = null }
    BackStep(shown(prompt?.first)) { prompt = null }

    if (items.isEmpty()) {
        Text(
            empty,
            style = T.sans.copy(fontSize = 14.sp, color = C.faint, textAlign = TextAlign.Center),
            modifier = Modifier.fillMaxWidth().reportCard().padding(vertical = 26.dp, horizontal = 18.dp),
        )
        return
    }
    Column(Modifier.fillMaxWidth().reportCard().clip(Card)) {
        items.forEachIndexed { i, it ->
            Column(if (i > 0) Modifier.divider(18.dp, 18.dp) else Modifier) {
                Row(
                    Modifier.fillMaxWidth().padding(start = 18.dp, end = 8.dp, top = 14.dp, bottom = 14.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    // The label takes the slack, so every amount ends at the same edge.
                    Column(Modifier.weight(1f)) {
                        Text(it.label, style = T.sans.copy(fontSize = 15.sp, lineHeight = 20.sp, fontWeight = FontWeight.Medium), maxLines = 2, overflow = TextOverflow.Ellipsis)
                        if (!it.sub.isNullOrEmpty() || it.link != null) Row(Modifier.padding(top = 2.dp), verticalAlignment = Alignment.CenterVertically) {
                            it.sub?.takeIf { s -> s.isNotEmpty() }?.let { s ->
                                Text(s, style = T.sans.copy(fontSize = 12.5.sp, lineHeight = 16.sp, color = C.faint), maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f, fill = false))
                            }
                            it.link?.let { l -> com.sonu.spica.ui.commitments.LinkWord(l, it.linkGuess, size = 12) }
                        }
                    }
                    // A task's state is a word, not a figure: a pill in its tone's tint.
                    if (it.kind == "task") Tag(
                        it.valueStr.replaceFirstChar { c -> c.uppercase() },
                        when (it.tone) {
                            ItemTone.Bad -> C.red
                            ItemTone.Warn -> C.ink
                            ItemTone.Good -> C.workInk
                            ItemTone.Muted -> C.faint
                        },
                        when (it.tone) {
                            ItemTone.Bad -> C.redTint
                            ItemTone.Warn -> C.surface
                            ItemTone.Good -> C.workTint
                            ItemTone.Muted -> C.surface
                        },
                    )
                    else if (it.valueStr.isNotEmpty()) Row(verticalAlignment = Alignment.CenterVertically) {
                        if (it.valueDot) com.sonu.spica.ui.common.Dot()
                        Text(
                            it.valueStr,
                            style = T.figure.copy(fontSize = 14.5.sp, fontWeight = FontWeight.SemiBold, color = toneColor(it.tone), textAlign = TextAlign.End),
                            maxLines = 1,
                        )
                    }
                    if (it.kind != null) {
                        Box(Modifier.size(32.dp).clip(CircleShape).background(if (open == it.id) C.surface else androidx.compose.ui.graphics.Color.Transparent).tap { open = if (open == it.id) null else it.id }, contentAlignment = Alignment.Center) {
                            Glyph(Ph.dotsThreeVertical, 19.dp, C.grey, label = "More")
                        }
                    } else Spacer(Modifier.width(10.dp))
                }
                if (open == it.id && it.kind != null) {
                    @OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
                    androidx.compose.foundation.layout.FlowRow(Modifier.fillMaxWidth().fadeUp(200).padding(start = 14.dp, end = 14.dp, bottom = 14.dp), horizontalArrangement = Arrangement.spacedBy(8.dp, Alignment.End), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        it.actions.forEach { act ->
                            Tray(act.label, if (act.danger) C.red else if (act.good) C.brand else C.ink, if (act.danger) C.redTint else if (act.good) C.brandTint else C.surface) {
                                if (act.choices.isNotEmpty()) {
                                    choosing = if (choosing == it.id to act.label) null else it.id to act.label
                                } else if (act.prompt != null) {
                                    prompt = Triple(it.id, act.label, act.prompt.initial)
                                    refused = false
                                } else {
                                    scope.launch { act.run(null) }
                                    open = null
                                }
                            }
                        }
                        if (it.editText != null && (it.kind == "paisa" || it.kind == "diet")) {
                            Tray("Edit") {
                                onEdit(it.kind, it.id, it.editText)
                                open = null
                            }
                        }
                        if (it.kind != "repayment" && it.kind != "commitment") {
                            Tray("Delete", C.red, C.redTint) {
                                onDelete(it.kind, it.id)
                                open = null
                            }
                        }
                    }
                }
                // *Counts toward…*: the lines it could go to, in place.
                val pick = choosing
                if (open == it.id && pick != null && pick.first == it.id) {
                    val act = it.actions.firstOrNull { a -> a.label == pick.second }
                    if (act != null) @OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class) androidx.compose.foundation.layout.FlowRow(
                        Modifier.fillMaxWidth().fadeUp(200).padding(start = 14.dp, end = 14.dp, bottom = 14.dp),
                        horizontalArrangement = Arrangement.spacedBy(8.dp, Alignment.End), verticalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        act.choices.forEach { c -> Tray(c.label) { c.run(); choosing = null; open = null } }
                    }
                }
                val p = prompt
                if (p != null && p.first == it.id) {
                    val act = it.actions.firstOrNull { a -> a.label == p.second }
                    val pr = act?.prompt
                    if (act != null && pr != null) {
                        fun submit() = scope.launch {
                            if (act.run(p.third)) {
                                prompt = null
                                open = null
                            } else refused = true
                        }
                        Column(Modifier.fadeUp(200).padding(start = 18.dp, end = 14.dp, bottom = 14.dp)) {
                            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                pr.prefix?.let { px -> Text(px, style = T.sans.copy(fontSize = 14.sp, color = C.muted)) }
                                InlineField(p.third, { v -> prompt = p.copy(third = v); refused = false }, Modifier.width(110.dp), numeric = true, decimal = true, autoFocus = true, onDone = { submit() })
                                Spacer(Modifier.weight(1f))
                                Tray("Cancel") { prompt = null }
                                Tray(act.label, C.white, C.brand) { submit() }
                            }
                            Text(if (refused) pr.refused else pr.hint, style = T.sans.copy(fontSize = 11.5.sp, color = if (refused) C.red else C.muted), modifier = Modifier.padding(top = 6.dp))
                        }
                    }
                }
            }
        }
    }
}

/* ─── + Lent / + Borrowed ─────────────────────────────────────────────── */

/** Who, and how much. Two fields — nothing else can create a lending until the agent does. */
@Composable
fun AddOpenRow(leg: String, onAdd: suspend (String, String, Int) -> Boolean) {
    var open by remember { mutableStateOf(false) }
    var who by remember { mutableStateOf("") }
    var amt by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var failed by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    fun reset() {
        open = false; who = ""; amt = ""; failed = false
    }
    // Back is Cancel while the form is open.
    BackStep(open, ::reset)
    fun save() {
        if (busy) return
        busy = true
        scope.launch {
            val ok = onAdd(leg, who, amt.trim().toDoubleOrNull()?.roundToInt() ?: 0)
            busy = false
            if (ok) reset() else failed = true
        }
    }
    if (!open) {
        Row(
            Modifier.padding(top = 12.dp).fillMaxWidth().reportCard().tap { open = true }.padding(horizontal = 18.dp, vertical = 15.dp),
            verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Coin(Ph.plus, C.brand, C.brandTint, 30.dp)
            Text(if (leg == "lent") "Add money you lent" else "Add money you borrowed", style = T.sans.copy(fontSize = 15.sp, fontWeight = FontWeight.Medium, color = C.brand))
        }
        return
    }
    Column(Modifier.padding(top = 12.dp).fillMaxWidth().reportCard().padding(horizontal = 18.dp, vertical = 16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            InlineField(who, { who = it }, Modifier.weight(1f), placeholder = if (leg == "lent") "who you gave it to" else "who you took it from", mono = false, autoFocus = true, onDone = ::save)
            Text("₹", style = T.sans.copy(fontSize = 14.sp, color = C.muted))
            InlineField(amt, { amt = it }, Modifier.width(96.dp), placeholder = "0", numeric = true, onDone = ::save)
        }
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(
                if (failed) "Not saved — a name and an amount above zero." else "Today. Enter saves.",
                style = T.sans.copy(fontSize = 11.5.sp, color = if (failed) C.red else C.muted), modifier = Modifier.weight(1f),
            )
            Tray("Cancel", onClick = ::reset)
            Box(Modifier.alpha(if (busy) 0.6f else 1f)) { Tray(if (busy) "Saving…" else "Save", C.white, C.brand, onClick = ::save) }
        }
    }
}
