package com.sonu.spica.ui.chat

import android.content.Intent
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.TextUnit
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.net.toUri
import com.sonu.spica.data.Api
import com.sonu.spica.data.ChatMsg
import com.sonu.spica.data.Commitment
import com.sonu.spica.data.ComposeContext
import com.sonu.spica.data.DishRow
import com.sonu.spica.data.ExerciseRow
import com.sonu.spica.data.HabitLogRow
import com.sonu.spica.data.Meal
import com.sonu.spica.data.PendingItem
import com.sonu.spica.data.Profile
import com.sonu.spica.data.Project
import com.sonu.spica.data.RepaymentItem
import com.sonu.spica.data.Todo
import com.sonu.spica.data.Tx
import com.sonu.spica.data.UDHAAR_KINDS
import com.sonu.spica.data.WeighInRow
import com.sonu.spica.lib.Day
import com.sonu.spica.lib.Fmt
import com.sonu.spica.logic.FieldId
import com.sonu.spica.logic.Tasks
import com.sonu.spica.ui.common.AgentCard
import com.sonu.spica.ui.common.BackStep
import com.sonu.spica.ui.common.Dot
import com.sonu.spica.ui.common.Glyph
import com.sonu.spica.ui.common.Ph
import com.sonu.spica.ui.common.PhBold
import com.sonu.spica.ui.common.PhFill
import com.sonu.spica.ui.common.ProjectIcon
import com.sonu.spica.ui.common.habitGlyph
import com.sonu.spica.ui.common.habitTone
import com.sonu.spica.ui.common.tap
import com.sonu.spica.ui.commitments.CommitmentReceipt
import com.sonu.spica.ui.commitments.PaymentLinks
import com.sonu.spica.ui.commitments.choiceLabel
import com.sonu.spica.ui.theme.C
import com.sonu.spica.ui.theme.T

/*
 * The confirm card, redesigned — spec/done/card-redesign.md.
 *
 * Every write comes back as one receipt line: a mode coin, what happened, its
 * meta, the figure on the right. A guess asks in place; the actions a person
 * needs are text under the line, never behind ⋮. The card reads the live row
 * it points at, so a change anywhere shows here and a deletion strikes it.
 * No sentence of the agent's is ever drawn inside a card.
 */

/** What a card may read besides its own payload: the live rows. */
data class CardWorld(
    val tx: List<Tx>,
    val meals: List<Meal>,
    val todos: List<Todo>,
    val projects: List<Project>,
    val habitLogs: List<HabitLogRow>,
    val exercises: List<ExerciseRow>,
    val dishes: List<DishRow>,
    val pending: List<PendingItem>,
    val weighIns: List<WeighInRow>,
    val profile: Profile,
    val today: String,
    val deletedRows: List<String>,
    /** Udhaar's other lists — what a payment card is, when its row is not held. */
    val borrowed: List<PendingItem> = emptyList(),
    val repayments: List<RepaymentItem> = emptyList(),
    /** This month's commitments — what a commitment card and a payment's link are read from. */
    val commitments: List<Commitment> = emptyList(),
    /** The weigh-ins have been read: until then a weight card says nothing about the reading before. */
    val weighInsLoaded: Boolean = false,
)

class ConfirmActions(
    /** A Change: what it is about rides above the composer. */
    val onContext: (ComposeContext) -> Unit,
    val onConfirm: (ChatMsg.Confirm) -> Unit,
    val onEdit: (String, String, String) -> Unit,
    val onDelete: (ChatMsg.Confirm) -> Unit,
    /** Undo on a removed receipt — the restore route. */
    val onRestore: (ChatMsg.Confirm) -> Unit,
    val onDeleteTask: (String) -> Unit,
    val onToggleTodo: (String) -> Unit,
    /** What a payment's tray needs to say it settles a commitment. */
    val links: PaymentLinks = PaymentLinks.None,
    /** The first run's cards: Edit and Undo in place of a receipt's own actions. Null in the chat. */
    val firstRun: FirstRunActions? = null,
)

/**
 * What a card on the first run's screen 3 can do: Edit puts it above the bar;
 * Undo takes the write back. `superseded`: a later write to the same profile
 * column holds the value now, so this card has no Undo.
 */
class FirstRunActions(
    val onEdit: (ChatMsg.Confirm) -> Unit,
    val onUndo: (ChatMsg.Confirm) -> Unit,
    /** Whether this card's write can be taken back now: [firstRunCanUndo], and no later write holds the value. */
    val canUndo: (ChatMsg.Confirm) -> Boolean = { false },
)

/** What the client knows about the row a card points at. Port of `messages/live.ts`. */
data class LiveRow(
    val deleted: Boolean,
    val confidence: Double? = null,
    val values: Map<String, String> = emptyMap(),
    val tx: Tx? = null,
    val meal: Meal? = null,
)

/**
 * The live row wins: held, it says whether it is gone — so a card born from
 * a delete is a plain receipt again once its row is restored. Not held, the
 * card's own state says it, and so does a delete made this session.
 */
fun liveFor(msg: ChatMsg.Confirm, tx: List<Tx>, meals: List<Meal>, deletedRows: List<String>): LiveRow {
    val born = msg.state == "deleted"
    val id = msg.rowId ?: return LiveRow(born)
    val gone = id in deletedRows
    if (msg.source == "paisa") {
        val t = tx.firstOrNull { it.id == id } ?: return LiveRow(gone || born)
        return LiveRow(gone || t.deleted, t.confidence, mapOf("amount_paise" to Fmt.rupees(t.amt), "category" to t.cat, "description" to t.name), tx = t)
    }
    if (msg.source == "diet") {
        val m = meals.firstOrNull { it.id == id } ?: return LiveRow(gone || born)
        val v = mutableMapOf("dish" to m.name, "kcal" to m.k.toString(), "protein_g" to "${Fmt.num(m.p)} g")
        m.type?.let { v["meal_type"] = it }
        return LiveRow(gone || m.deleted, m.confidence, v, meal = m)
    }
    return LiveRow(gone || born)
}

/* ─── the composer's context ──────────────────────────────────────────── */

/*
 * What a Change attaches to the composer: a label to read, and the opening of
 * the sentence the agent is sent — completed by what is typed, "Change the
 * category of the ₹80 Auto payment on 1 Oct to" + "transport". Built from the
 * live row when the tap happens, never stored on a card. Each names the row
 * the way the data does — amounts as rupees, days as "1 Oct" — so the
 * sentence cannot be read as a new log. A day nobody knows is left out.
 */

private fun on(dayIso: String?) = dayIso?.let { " on ${Day.shortDay(it)}" } ?: ""

/** A payment's guessed category: `Auto · category`. */
fun categoryContext(what: String, amount: String, dayIso: String?) =
    ComposeContext("$what · category", "Change the category of the $amount $what payment${on(dayIso)} to")

/** The review's question, said as the statement its answer completes. */
fun reviewContext(payee: String, amount: String, dayIso: String?) =
    ComposeContext("$payee · category", "The category of the $amount $payee payment${on(dayIso)} is")

/** A meal's estimated protein: `The 3 eggs I had for breakfast today actually had` — "today" only when it is. */
fun mealContext(dish: String, slot: String?, dayIso: String?, today: String) = ComposeContext(
    "$dish · protein",
    "The $dish I had${slot?.let { " for ${it.lowercase()}" } ?: ""}${if (dayIso == today) " today" else on(dayIso)} actually had",
)

/** A target, and what it is now: `Savings target · ₹10,000`. */
fun targetContext(label: String, value: String?) =
    ComposeContext(if (value != null) "$label · $value" else label, "Change my ${label.lowercase()} to")

/** No protein target yet — the meal card offers to set one. */
val SET_PROTEIN_TARGET = ComposeContext("Protein target", "Set my daily protein target to")

/** Any field without words of its own: `Dal · weight`. */
fun fieldContext(what: String, field: String) = ComposeContext("$what · $field", "Change the $field of $what to")

/**
 * Edit, on a first-run card: what the card holds, and the sentence the
 * onboarding agent is sent ahead of the correction — "Change my height to"
 * + "180". The agent writes the row again with the new value.
 */
fun firstRunContext(msg: ChatMsg.Confirm): ComposeContext {
    val f = msg.fields.firstOrNull()
    return when {
        msg.source == "profile" && f != null -> targetContext(f.label, f.value)
        msg.source == "body" && f?.key == "weight_kg" -> ComposeContext("Weight · ${f.value}", "Change my weight to")
        msg.source == "body" -> (msg.field("name")?.value ?: msg.lede.substringBefore(" · ")).let { ComposeContext("$it · habit", "Change the habit $it to") }
        msg.source == "memory" && f != null -> ComposeContext(f.value, "Change what you remember, “${f.value}”, to")
        msg.source == "work" -> taskTitle(msg).let { ComposeContext("$it · task", "Change the task “$it” to") }
        else -> ComposeContext(msg.lede, "Change “${msg.lede}” to")
    }
}

/**
 * Whether Undo can take a first-run card's write back: a name goes back to
 * the one before it — sign-in's, on a first run — and is never removed, so
 * with none before there is nothing to put back; a column this build does not
 * know has nothing to put back; and a habit already tracked or a task already
 * on the list was not written by this answer.
 */
fun firstRunCanUndo(msg: ChatMsg.Confirm, nameBefore: String): Boolean = msg.state != "deleted" && when (msg.source) {
    "profile" -> msg.fields.firstOrNull()?.key
        ?.let { key -> if (key == "age") "dob" else key }
        .let { column -> column != null && FieldId.entries.any { it.wire == column } && (column != FieldId.Name.wire || nameBefore.isNotBlank()) }
    "body" -> msg.rowId != null && !msg.lede.endsWith("already tracked")
    "memory" -> msg.rowId != null
    "work" -> msg.rowId != null && (TASK_STATE.find(msg.lede)?.groupValues?.get(1) ?: "added") == "added"
    else -> false
}

/* ─── the pieces ──────────────────────────────────────────────────────── */

@Composable
fun Coin(bg: Color, size: Dp = 34.dp, content: @Composable BoxScope.() -> Unit) {
    Box(Modifier.size(size).background(bg, CircleShape), contentAlignment = Alignment.Center, content = content)
}

@Composable
fun IconCoin(icon: ImageVector, ink: Color, tint: Color, size: Dp = 34.dp) = Coin(tint, size) { Glyph(icon, size / 2, ink) }

@Composable
fun InitialCoin(name: String, ink: Color, tint: Color, size: Dp = 34.dp) = Coin(tint, size) {
    Text(name.trim().take(1).uppercase(), style = T.sans.copy(fontSize = (size.value * 0.45f).sp, fontWeight = FontWeight.SemiBold, color = ink))
}

/** A figure: the interface face, medium, tabular. */
@Composable
fun Fig(text: String, size: TextUnit = 17.sp, color: Color = C.ink, struck: Boolean = false, modifier: Modifier = Modifier) =
    Text(text, style = T.figure.copy(fontSize = size, color = color, textDecoration = if (struck) TextDecoration.LineThrough else null), maxLines = 1, modifier = modifier)

/**
 * The receipt line: coin · what and its meta · the figure. A figure with a
 * line under it — a meal's protein over its kcal, carbs and fat — sits on the
 * title's line with that line on the meta's, so a long one never squeezes
 * the title.
 */
@Composable
fun ReceiptHead(
    coin: @Composable () -> Unit, title: String, meta: String, struck: Boolean = false,
    figureUnder: String? = null, figure: (@Composable () -> Unit)? = null,
) {
    @Composable
    fun Title(modifier: Modifier = Modifier) = Text(
        title,
        style = T.sans.copy(
            fontSize = 15.sp, lineHeight = 20.sp, fontWeight = FontWeight.Medium,
            color = if (struck) C.faint else C.ink, textDecoration = if (struck) TextDecoration.LineThrough else null,
        ),
        maxLines = 2, overflow = TextOverflow.Ellipsis, modifier = modifier,
    )
    val metaStyle = T.sans.copy(fontSize = 12.5.sp, lineHeight = 17.sp, color = C.faint)
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        coin()
        if (figureUnder == null) {
            Column(Modifier.weight(1f)) {
                Title()
                if (meta.isNotEmpty()) Text(meta, style = metaStyle, modifier = Modifier.padding(top = 1.dp))
            }
            figure?.invoke()
        } else {
            Column(Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Title(Modifier.weight(1f))
                    figure?.invoke()
                }
                Row(Modifier.padding(top = 1.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text(meta, style = metaStyle, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f))
                    Text(figureUnder, style = T.sans.copy(fontSize = 12.sp, lineHeight = 17.sp, color = C.faint), maxLines = 1)
                }
            }
        }
    }
}

/** A text action under a card. Never a pill: the one filled button on a card is its primary action. */
data class Quiet(val label: String, val color: Color = C.muted, val icon: ImageVector? = null, val onClick: () -> Unit)

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun QuietActions(vararg actions: Quiet?) {
    val list = actions.filterNotNull()
    if (list.isEmpty()) return
    FlowRow(Modifier.padding(top = 10.dp), horizontalArrangement = Arrangement.spacedBy(18.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
        list.forEach { a ->
            Row(
                Modifier.clip(RoundedCornerShape(6.dp)).tap(onClick = a.onClick).padding(vertical = 3.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(5.dp),
            ) {
                a.icon?.let { Glyph(it, 15.dp, a.color) }
                Text(a.label, style = T.sans.copy(fontSize = 13.5.sp, fontWeight = FontWeight.Medium, color = a.color))
            }
        }
    }
}

/** A receipt's own text actions — or, on the first run, Edit and Undo in their place. */
@Composable
private fun ReceiptActions(msg: ChatMsg.Confirm, ca: ConfirmActions, vararg own: Quiet?) {
    val first = ca.firstRun
    if (first == null) return QuietActions(*own)
    if (msg.state == "deleted") return
    QuietActions(
        Quiet("Edit", icon = Ph.pencilSimple) { first.onEdit(msg) },
        if (first.canUndo(msg)) Quiet("Undo", icon = Ph.arrowCounterClockwise) { first.onUndo(msg) } else null,
    )
}

/** Above a rule: something that needs you, asked in place. */
@Composable
fun GuessLine(text: String, rightLabel: String = "Right", changeLabel: String = "Change", onRight: () -> Unit, onChange: () -> Unit) {
    RuleAbove {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Dot()
            Text(text, style = T.sans.copy(fontSize = 13.sp, color = C.muted), modifier = Modifier.weight(1f))
            Text(rightLabel, style = T.sans.copy(fontSize = 13.5.sp, fontWeight = FontWeight.Medium, color = C.brand), modifier = Modifier.clip(RoundedCornerShape(6.dp)).tap(onClick = onRight).padding(horizontal = 6.dp, vertical = 3.dp))
            Text(changeLabel, style = T.sans.copy(fontSize = 13.5.sp, fontWeight = FontWeight.Medium, color = C.muted), modifier = Modifier.clip(RoundedCornerShape(6.dp)).tap(onClick = onChange).padding(horizontal = 6.dp, vertical = 3.dp))
        }
    }
}

@Composable
fun RuleAbove(top: Dp = 12.dp, content: @Composable ColumnScope.() -> Unit) {
    Column(Modifier.fillMaxWidth().padding(top = top).topRuleLine().padding(top = 10.dp), content = content)
}

/** A label and its figure on one line — "This month · ₹40,000 in · ₹0 out". */
@Composable
fun InfoLine(label: String, value: String, valueColor: Color = C.muted) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Text(label, style = T.sans.copy(fontSize = 12.5.sp, color = C.faint), modifier = Modifier.weight(1f))
        Fig(value, 12.5.sp, valueColor)
    }
}

@Composable
fun FactChip(text: String, color: Color = C.muted, bg: Color = C.surface) {
    Text(text, style = T.sans.copy(fontSize = 12.sp, color = color), maxLines = 1, modifier = Modifier.background(bg, RoundedCornerShape(50)).padding(horizontal = 9.dp, vertical = 3.dp))
}

@Composable
fun FilledButton(text: String, enabled: Boolean = true, onClick: () -> Unit) {
    Text(
        text,
        style = T.sans.copy(fontSize = 13.5.sp, fontWeight = FontWeight.Medium, color = Color.White),
        modifier = Modifier.clip(RoundedCornerShape(50)).background(if (enabled) C.brand else C.grey).tap(enabled = enabled, onClick = onClick).padding(horizontal = 14.dp, vertical = 7.dp),
    )
}

private val ISO_DAY = Regex("""\d{4}-\d{2}-\d{2}""")

@Composable
fun OutlineButton(text: String, icon: ImageVector? = null, onClick: () -> Unit) {
    Row(
        Modifier.clip(RoundedCornerShape(50)).border(1.dp, C.border, RoundedCornerShape(50)).tap(onClick = onClick).padding(horizontal = 13.dp, vertical = 6.dp),
        horizontalArrangement = Arrangement.spacedBy(4.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(text, style = T.sans.copy(fontSize = 13.5.sp, fontWeight = FontWeight.Medium, color = C.muted))
        icon?.let { Glyph(it, 13.dp, C.muted) }
    }
}

@Composable
fun ThinBar(fraction: Float, color: Color, modifier: Modifier = Modifier) {
    Box(modifier.fillMaxWidth().height(4.dp).clip(RoundedCornerShape(2.dp)).background(C.ringIdle)) {
        Box(Modifier.fillMaxWidth(fraction.coerceIn(0f, 1f)).height(4.dp).background(color))
    }
}

/** "Today", "Yesterday", or "Wed, 16 Sep". */
fun dayWord(iso: String?, today: String): String = when {
    iso == null || iso == today -> "Today"
    iso == Day.addDays(today, -1) -> "Yesterday"
    else -> Day.cardDay(iso)
}

private fun cap(s: String) = s.replaceFirstChar { it.uppercase() }

/** Grams as a person reads them: 18, 18.5 — never 18.900000000000002. */
private fun grams(n: Double) = Fmt.num(Math.round(n * 10) / 10.0)

private fun ChatMsg.Confirm.field(key: String) = fields.firstOrNull { it.key == key }

/**
 * Which udhaar kind a payment card's row is — the live row says, or the list
 * it lives in while open; a loan settled in full is still known by the
 * repayments that name it. Null for anything else; a lending is never a
 * category question.
 */
private fun udhaarKind(id: String?, t: Tx?, w: CardWorld): String? {
    t?.kind?.takeIf { it in UDHAAR_KINDS }?.let { return it }
    if (id == null) return null
    return when {
        w.pending.any { it.id == id } -> "lent"
        w.borrowed.any { it.id == id } -> "borrowed"
        w.repayments.any { it.id == id } -> "repayment"
        else -> w.repayments.firstOrNull { it.lendingId == id }?.leg
    }
}

/** A quiet Undo on a removed receipt: the row comes back through the restore route. */
@Composable
private fun RestoreAction(msg: ChatMsg.Confirm, ca: ConfirmActions) {
    if (msg.rowId != null) QuietActions(Quiet("Undo", icon = Ph.arrowCounterClockwise) { ca.onRestore(msg) })
}

private fun Modifier.topRuleLine() = drawBehind { drawLine(C.line, Offset(0f, 0f), Offset(size.width, 0f), 1.dp.toPx()) }

/* ─── the card ────────────────────────────────────────────────────────── */

@Composable
fun ConfirmCard(msg: ChatMsg.Confirm, live: LiveRow, w: CardWorld, ca: ConfirmActions) {
    val card = PaddingValues(horizontal = 14.dp, vertical = 12.dp)
    when (msg.source) {
        "paisa" -> if (msg.state == "proposed") ReviewCard(listOf(msg), { live }, w, ca) else AgentCard(padding = card) { Column { PaymentReceipt(msg, live, w, ca) } }
        "diet" -> AgentCard(padding = card) { Column { if (msg.lede.startsWith("Saved ·")) DishSaved(msg, w) else MealReceipt(msg, live, w, ca) } }
        "body" -> BodyCard(msg, w, card, ca)
        "pantry" -> AgentCard(padding = card) { Column { PantryMove(msg, live, w, ca) } }
        "work" -> AgentCard(padding = card) { Column { if (msg.fields.any { it.key == "name" }) ProjectReceipt(msg, w) else TaskReceipt(msg, w, ca) } }
        "people" -> AgentCard(padding = card) { Column { PersonReceipt(msg) } }
        "places" -> AgentCard(padding = card) { Column { PlaceReceipt(msg, live, ca) } }
        "memory" -> AgentCard(padding = card) { Column { MemoryReceipt(msg, live, ca) } }
        "profile" -> AgentCard(padding = card) { Column { ProfileReceipt(msg, ca) } }
        "commitment" -> AgentCard(padding = card) { Column { CommitmentReceipt(msg, w.commitments.firstOrNull { it.id == msg.rowId }, ca) } }
        else -> AgentCard(padding = card) { Column { GenericReceipt(msg) } }
    }
}

/* ─── money ───────────────────────────────────────────────────────────── */

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun PaymentReceipt(msg: ChatMsg.Confirm, live: LiveRow, w: CardWorld, ca: ConfirmActions) {
    val t = live.tx
    val id = msg.rowId
    val gone = live.deleted
    val what = t?.name ?: msg.field("description")?.value ?: msg.lede.substringAfter(" · ")
    val cat = t?.cat ?: msg.field("category")?.value
    val dayIso = t?.date ?: msg.field("local_day")?.value
    val amount = t?.let { Fmt.rupees(it.amt) } ?: msg.field("amount_paise")?.value ?: msg.lede.substringBefore(" · ")
    // The card carries no direction; the live row does.
    val credit = t?.credit == true
    val lent = id?.let { rid -> w.pending.firstOrNull { it.id == rid && it.leg == "lent" } }
    // Udhaar never asks a category, whatever the confidence: the row's kind
    // says it is one, or the server's own Udhaar does.
    val udhaar = udhaarKind(id, t, w)
    val isUdhaar = udhaar != null || cat == "Udhaar"
    val guessed = msg.field("category")?.guessed == true && !(live.confidence != null && live.confidence >= 1) && !gone && !isUdhaar
    val day = dayWord(dayIso, w.today)
    val meta = when {
        gone -> "Removed · $day"
        credit -> "Came in · $day"
        lent != null -> "Lent · comes back · $day"
        isUdhaar -> "${UDHAAR_KINDS[udhaar] ?: "Udhaar"} · $day"
        guessed || cat == null -> day
        else -> "$cat · $day"
    }
    ReceiptHead(
        { IconCoin(Ph.currencyInr, if (gone) C.grey else C.paisaInk, if (gone) C.lineSoft else C.paisaTint) },
        what, meta, gone,
    ) { Fig(if (credit) "+$amount" else amount, color = if (gone) C.faint else if (credit) C.paisaInk else C.ink, struck = gone) }
    if (gone) return RestoreAction(msg, ca)
    if (guessed && cat != null) GuessLine(
        "${cap(cat)}, I guessed",
        onRight = { ca.onConfirm(msg) },
        onChange = { ca.onContext(categoryContext(what, amount, dayIso)) },
    )
    if (credit) RuleAbove { MonthLine(w) }
    if (lent != null && lent.remaining > 0) RuleAbove {
        InfoLine("Still out", Fmt.rupees(lent.remaining) + if (lent.remaining != lent.amount) " of ${Fmt.rupees(lent.amount)}" else "")
    }
    // The commitment this payment settles. A guess is asked in place — the amber
    // dot and a one-tap *Not this*; a statement is only named.
    val links = ca.links
    val linkedName = t?.commitmentId?.let { links.nameOf(it) ?: "a commitment" }
    if (t != null && linkedName != null && links.applies(t) && !isUdhaar) {
        if (t.commitmentInferred) GuessLine("Settles $linkedName", rightLabel = "Right", changeLabel = "Not this", onRight = { links.countsToward(t.id, t.commitmentId!!) }, onChange = { links.notCommitment(t.id) })
        else RuleAbove { InfoLine("Counts toward", linkedName) }
    }
    if (id != null) {
        var choosing by remember(id) { mutableStateOf(false) }
        val canLink = t != null && links.applies(t) && !isUdhaar && !credit
        val choices = if (canLink) links.choicesFor(t!!) else emptyList()
        // Back puts the choices away first, as it does in a ledger row's tray.
        BackStep(choosing && choices.isNotEmpty()) { choosing = false }
        QuietActions(
            Quiet("Undo", icon = Ph.arrowCounterClockwise) { ca.onDelete(msg) },
            Quiet("Edit") { ca.onEdit("paisa", id, "$what ${amount.replace(Regex("[₹,+−]"), "")}".trim()) },
            if (choices.isNotEmpty()) Quiet("Counts toward…", if (choosing) C.brand else C.muted) { choosing = !choosing } else null,
            if (canLink && t!!.commitmentId != null && !t.commitmentInferred) Quiet("Not a commitment") { links.notCommitment(t.id) } else null,
            if (canLink && t!!.commitmentId == null) Quiet("Make this a commitment") { links.make(t) } else null,
        )
        if (choosing && choices.isNotEmpty()) {
            FlowRow(Modifier.padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(6.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                choices.forEach { c -> OutlineButton(choiceLabel(c)) { links.countsToward(t!!.id, c.id); choosing = false } }
            }
        }
    }
}

/** This month, from the live rows: what came in and what went out. */
@Composable
private fun MonthLine(w: CardWorld) {
    val month = w.today.take(7)
    val rows = w.tx.filter { !it.deleted && it.id !in w.deletedRows && (it.date ?: w.today).take(7) == month }
    InfoLine("This month", "${Fmt.rupees(rows.filter { it.credit }.sumOf { it.amt })} in · ${Fmt.rupees(rows.filter { !it.credit }.sumOf { it.amt })} out")
}

/**
 * The nightly review's guesses: one question at a time, "1 of N". A guess is
 * answered when its row holds the category and is certain; Skip only moves on.
 * No "80% sure" — the model's confidence is not a measured number.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun ReviewCard(items: List<ChatMsg.Confirm>, liveOf: (ChatMsg.Confirm) -> LiveRow, w: CardWorld, ca: ConfirmActions) {
    val skipped = remember(items.map { it.id }) { mutableStateListOf<String>() }
    fun guessOf(m: ChatMsg.Confirm) = m.field("category")?.value
    fun answered(m: ChatMsg.Confirm): Boolean {
        val l = liveOf(m)
        if (l.deleted) return true
        val t = l.tx ?: return false
        return (t.confidence ?: 0.0) >= 1 && t.cat == guessOf(m)
    }
    val current = items.firstOrNull { !answered(it) && it.id !in skipped }
    AgentCard(padding = PaddingValues(horizontal = 14.dp, vertical = 12.dp)) {
        Column {
            if (current == null) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Glyph(Ph.checkCircle, 17.dp, C.brand)
                    val done = items.count(::answered)
                    Text(if (done == items.size) "All ${items.size} sorted" else "$done of ${items.size} sorted · the rest skipped", style = T.sans.copy(fontSize = 13.5.sp, color = C.muted))
                }
                return@Column
            }
            val parts = current.lede.split(" · ")
            val amount = parts.firstOrNull() ?: ""
            val payee = parts.getOrNull(1) ?: current.field("description")?.value ?: ""
            val guess = guessOf(current)
            val dayIso = current.field("local_day")?.value
            ReceiptHead({ IconCoin(Ph.currencyInr, C.paisaInk, C.paisaTint) }, payee, dayWord(dayIso, w.today)) { Fig(amount) }
            RuleAbove {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Dot()
                    Text("${guess ?: "Category"}?", style = T.sans.copy(fontSize = 14.sp, fontWeight = FontWeight.Medium))
                }
                val why = current.field("why")?.value?.takeIf { it.isNotBlank() && it != "—" }
                if (why != null) {
                    FlowRow(Modifier.padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(6.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        why.split(";").map { it.trim() }.filter { it.isNotEmpty() }.forEach { FactChip(it) }
                    }
                }
                Row(Modifier.padding(top = 12.dp), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                    if (guess != null) FilledButton("Yes, $guess") { ca.onConfirm(current) }
                    OutlineButton("Change") { ca.onContext(reviewContext(payee, amount, dayIso)) }
                }
            }
            if (items.size > 1) {
                Row(Modifier.fillMaxWidth().padding(top = 12.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text("${items.indexOf(current) + 1} of ${items.size}", style = T.sans.copy(fontSize = 12.5.sp, color = C.faint), modifier = Modifier.weight(1f))
                    Text("Skip", style = T.sans.copy(fontSize = 13.5.sp, fontWeight = FontWeight.Medium, color = C.muted), modifier = Modifier.clip(RoundedCornerShape(6.dp)).tap { skipped += current.id }.padding(horizontal = 6.dp, vertical = 3.dp))
                }
            }
        }
    }
}

/* ─── food ────────────────────────────────────────────────────────────── */

@Composable
private fun MealReceipt(msg: ChatMsg.Confirm, live: LiveRow, w: CardWorld, ca: ConfirmActions) {
    val m = live.meal
    val id = msg.rowId
    val gone = live.deleted
    val dish = m?.name ?: msg.field("dish")?.value ?: msg.lede.substringBefore(" · ")
    val slot = m?.type ?: msg.field("meal_type")?.value
    val dayIso = m?.date ?: msg.field("local_day")?.value
    val kcalF = msg.field("kcal")
    val protF = msg.field("protein_g")
    val liveKnown = m != null && (m.k > 0 || m.p > 0.0)
    val unknown = !liveKnown && (kcalF?.value == "—" || protF?.value == "—")
    val kcal = if (liveKnown) "${Fmt.indian(m!!.k)} kcal" else kcalF?.value?.takeIf { it != "—" }?.let { v -> "${v.toIntOrNull()?.let { Fmt.indian(it) } ?: v} kcal" }
    val protein = if (liveKnown) "${grams(m!!.p)} g" else protF?.value?.takeIf { it != "—" }
    // Carbs and fat only where something knows them — the live row, else the
    // card. An unknown one is left out of the line, never written as 0.
    val carbs = m?.c?.let { "${grams(it)} g" } ?: msg.field("carbs_g")?.value?.takeIf { it != "—" }
    val fat = m?.f?.let { "${grams(it)} g" } ?: msg.field("fat_g")?.value?.takeIf { it != "—" }
    val guessed = (kcalF?.guessed == true || protF?.guessed == true) && !(live.confidence != null && live.confidence >= 1) && !gone
    val day = dayWord(dayIso, w.today)
    val under = if (gone || unknown) null
    else listOfNotNull(kcal, carbs?.let { "$it carbs" }, fat?.let { "$it fat" }).joinToString(" · ").ifEmpty { null }
    ReceiptHead(
        { IconCoin(Ph.bowlFood, if (gone) C.grey else C.dietInk, if (gone) C.lineSoft else C.dietTint) },
        dish,
        if (gone) "Removed · $day" else listOfNotNull(slot, day).joinToString(" · "),
        gone,
        figureUnder = under,
    ) {
        when {
            gone -> Unit
            unknown -> Text("macros unknown", style = T.sans.copy(fontSize = 12.5.sp, color = C.faint))
            else -> Row(verticalAlignment = Alignment.CenterVertically) {
                if (guessed) Dot()
                Fig(protein ?: "—", 15.sp)
            }
        }
    }
    if (gone) return RestoreAction(msg, ca)
    // Each thing said that did not count is its own line — nothing to decode.
    val gaps = buildList {
        msg.field("assumption")?.let { add(Triple(true, "Assumed: ${it.value}", "")) }
        msg.needsQuantity.forEach { add(Triple(false, "${cap(it)} — how much?", "not counted")) }
        msg.unresolved.forEach { add(Triple(false, "${cap(it)} — not found", "not counted")) }
    }
    if (gaps.isNotEmpty()) RuleAbove {
        gaps.forEachIndexed { i, (dotted, text, right) ->
            Row(Modifier.fillMaxWidth().padding(top = if (i == 0) 0.dp else 6.dp), verticalAlignment = Alignment.CenterVertically) {
                if (dotted) Dot()
                Text(text, style = T.sans.copy(fontSize = 13.sp, color = C.muted), modifier = Modifier.weight(1f))
                if (right.isNotEmpty()) Text(right, style = T.sans.copy(fontSize = 12.sp, color = C.faint))
            }
        }
    }
    if (guessed) GuessLine(protein?.let { "$it protein, I estimated" } ?: "Macros estimated",
        onRight = { ca.onConfirm(msg) }, onChange = { ca.onContext(mealContext(dish, slot, dayIso, w.today)) })
    // Protein today, from the live meals — only under a meal eaten today:
    // under an older one, today's total would be read as that day's.
    if (!unknown && (dayIso ?: w.today) == w.today) {
        val todayP = w.meals.filter { !it.deleted && it.id !in w.deletedRows && (it.date ?: w.today) == w.today }.sumOf { it.p }
        val target = w.profile.proteinTarget
        RuleAbove {
            if (target != null && target > 0) {
                InfoLine("Protein today", "${grams(todayP)} of ${grams(target)} g")
                ThinBar((todayP / target).toFloat(), C.diet, Modifier.padding(top = 6.dp))
            } else {
                // No target, no bar to fill: the figure, and the one tap that sets one.
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Text("Protein today", style = T.sans.copy(fontSize = 12.5.sp, color = C.faint), modifier = Modifier.weight(1f))
                    Fig("${grams(todayP)} g · no target · ", 12.5.sp, C.muted)
                    Text(
                        "Set target",
                        style = T.sans.copy(fontSize = 12.5.sp, fontWeight = FontWeight.Medium, color = C.brand),
                        modifier = Modifier.clip(RoundedCornerShape(6.dp)).tap { ca.onContext(SET_PROTEIN_TARGET) }.padding(vertical = 2.dp),
                    )
                }
            }
        }
    }
    if (id != null) QuietActions(
        if (unknown) Quiet("Add weight", C.brand) { ca.onContext(fieldContext(dish, "weight")) } else null,
        Quiet("Undo", icon = Ph.arrowCounterClockwise) { ca.onDelete(msg) },
        if (!unknown) Quiet("Edit") { ca.onEdit("diet", id, dish) } else null,
    )
}

@Composable
private fun DishSaved(msg: ChatMsg.Confirm, w: CardWorld) {
    val d = w.dishes.firstOrNull { it.id == msg.rowId }
    val name = d?.name ?: msg.lede.removePrefix("Saved ·").trim()
    ReceiptHead(
        { IconCoin(Ph.cookingPot, C.dietInk, C.dietTint, 40.dp) },
        name,
        listOfNotNull(d?.minutes?.let { "$it min" }, d?.kcal?.let { "$it kcal" }).joinToString(" · "),
    ) { d?.let { Fig("${Fmt.num(it.proteinG)} g", 16.sp) } }
    Row(Modifier.padding(top = 10.dp, start = 52.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        Glyph(Ph.pushPin, 14.dp, C.brand)
        Text("Saved", style = T.sans.copy(fontSize = 12.5.sp, color = C.muted))
    }
}

@Composable
private fun PantryMove(msg: ChatMsg.Confirm, live: LiveRow, w: CardWorld, ca: ConfirmActions) {
    val gone = live.deleted || msg.state == "deleted"
    val food = msg.field("food")?.value ?: msg.lede
    val kind = msg.field("kind")?.value ?: ""
    // "500 g" → what moved, in the food's own unit. The wire's quantity is
    // signed, so a negative carries its own minus — never a second one from the kind.
    val q = Regex("^(-?[\\d.]+) (\\S+)$").find(msg.field("quantity")?.value ?: "")
    val n = q?.groupValues?.get(1)?.toDoubleOrNull()
    val moved = if (q != null && n != null) {
        val sign = when {
            n < 0 || kind == "used" || kind == "waste" -> "−"
            kind == "bought" -> "+"
            else -> ""
        }
        "$sign${Api.inUnit(kotlin.math.abs(n), q.groupValues[2])} $kind".trim()
    } else kind
    // "700 g Paneer left" → the level now: "700 g", "6 pcs", "−15 g".
    val level = Regex("^(-?[\\d.]+) (\\S+) .+ left$").find(msg.lede)
        ?.let { m -> m.groupValues[1].toDoubleOrNull()?.let { Api.inUnit(it, m.groupValues[2]) } }
    // The card's own day, from its id — a card from an earlier day does not say today.
    val day = dayOf(msg.id, w.today)
    ReceiptHead(
        { IconCoin(Ph.`package`, if (gone) C.grey else C.dietInk, if (gone) C.lineSoft else C.dietTint) },
        food,
        if (gone) "Removed" else cap(listOf(moved, if (day == w.today) "today" else Day.cardDay(day)).filter { it.isNotEmpty() }.joinToString(" · ")),
        gone,
    ) { level?.let { Fig(it, struck = gone, color = if (gone) C.faint else C.ink) } }
    if (!gone && msg.rowId != null) QuietActions(Quiet("Undo", icon = Ph.arrowCounterClockwise) { ca.onDelete(msg) })
}

/* ─── the body ────────────────────────────────────────────────────────── */

@Composable
private fun BodyCard(msg: ChatMsg.Confirm, w: CardWorld, pad: PaddingValues, ca: ConfirmActions) {
    val keys = msg.fields.map { it.key }
    when {
        // A weight is a weigh-in, on a card of its own that holds the reading's id.
        keys == listOf("weight_kg") -> AgentCard(padding = pad) { Column { WeighInReceipt(msg, w, ca) } }
        keys.any { it.startsWith("habit:") } || "sleep_hours" in keys || "weight_kg" in keys -> DayFacts(msg, w, pad)
        "direction" in keys || msg.lede.contains("· tracking") || msg.lede.endsWith("already tracked") || msg.lede.endsWith("no longer tracked") ->
            AgentCard(padding = pad) { Column { HabitManaged(msg, w, ca) } }
        else -> AgentCard(padding = pad) { Column { ExerciseDone(msg, w) } }
    }
}

/**
 * A weigh-in: the scale's coin, the reading, and what it moved since the
 * one before. Said as a guess, it wears the dot until an exact reading the
 * same day replaces it — the live row says which. Deleted anywhere, struck.
 */
@Composable
private fun WeighInReceipt(msg: ChatMsg.Confirm, w: CardWorld, ca: ConfirmActions) {
    val said = msg.field("weight_kg") ?: return
    val gone = msg.state == "deleted" || (msg.rowId != null && msg.rowId in w.deletedRows)
    // Its own reading, when the card holds a live weigh-in — an old card of a day's weight holds the day instead.
    val row = msg.rowId?.let { id -> w.weighIns.firstOrNull { it.id == id } }
    val kg = row?.kg ?: said.value.removeSuffix(" kg").toDoubleOrNull()
    val estimated = row?.estimated ?: said.guessed
    val day = row?.day ?: dayOf(msg.id, w.today)
    // The weigh-in before this one — never an invented change, and nothing said before the list is read.
    val prev = w.weighIns.filter { it.day < day && it.id != msg.rowId }.maxByOrNull { it.day }
    val meta = when {
        gone -> "Removed"
        !w.weighInsLoaded -> "—"
        kg != null && prev != null -> {
            val d = kg - prev.kg
            "${if (d > 0) "+" else if (d < 0) "−" else "±"}${Fmt.num(Math.round(kotlin.math.abs(d) * 10) / 10.0)} since ${dayWord(prev.day, w.today)}"
        }
        else -> "no earlier weigh-in"
    }
    ReceiptHead({ IconCoin(Ph.scales, if (gone) C.grey else C.dietInk, if (gone) C.lineSoft else C.dietTint) }, "Weight", meta, gone) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            if (estimated && !gone) Dot()
            Fig(kg?.let { "${Fmt.num(it)} kg" } ?: said.value, struck = gone, color = if (gone) C.faint else C.ink)
        }
    }
    // Undo deletes the weigh-in, so only a card holding a live one offers it.
    ReceiptActions(msg, ca, if (!gone && row != null) Quiet("Undo", icon = Ph.arrowCounterClockwise) { ca.onDelete(msg) } else null)
}

@Composable
private fun DayFacts(msg: ChatMsg.Confirm, w: CardWorld, pad: PaddingValues) {
    val day = dayOf(msg.id, w.today)
    val sleep = msg.field("sleep_hours")?.value
    val weight = msg.field("weight_kg")?.value
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        if (sleep != null || weight != null) Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            if (sleep != null) AgentCard(Modifier.weight(1f), padding = pad) {
                Column {
                    Text("Sleep", style = T.sans.copy(fontSize = 12.5.sp, color = C.faint))
                    Fig(sleep, 20.sp)
                    val target = w.profile.sleepTargetMin
                    val mins = Regex("(\\d+) h(?: (\\d+) m)?").find(sleep)?.let { it.groupValues[1].toInt() * 60 + (it.groupValues[2].toIntOrNull() ?: 0) }
                    if (target != null && target > 0 && mins != null) {
                        ThinBar(mins.toFloat() / target, C.diet, Modifier.padding(top = 8.dp, bottom = 4.dp))
                        Text("of ${target / 60} h${if (target % 60 > 0) " ${target % 60} m" else ""}", style = T.sans.copy(fontSize = 12.sp, color = C.faint))
                    }
                }
            }
            if (weight != null) AgentCard(Modifier.weight(1f), padding = pad) {
                Column {
                    Text("Weight", style = T.sans.copy(fontSize = 12.5.sp, color = C.faint))
                    Fig(weight, 20.sp)
                    val kg = weight.removeSuffix(" kg").toDoubleOrNull()
                    // The weigh-in before that day's — never an invented change, and nothing said before the list is read.
                    val prev = w.weighIns.filter { it.day < day }.maxByOrNull { it.day }
                    val line = if (!w.weighInsLoaded) "—" else if (kg != null && prev != null) {
                        val d = kg - prev.kg
                        "${if (d > 0) "+" else if (d < 0) "−" else "±"}${Fmt.num(Math.round(kotlin.math.abs(d) * 10) / 10.0)} since ${dayWord(prev.day, w.today)}"
                    } else "no earlier weigh-in"
                    Text(line, style = T.sans.copy(fontSize = 12.sp, color = C.muted), modifier = Modifier.padding(top = 12.dp))
                }
            }
        }
        msg.fields.filter { it.key.startsWith("habit:") }.forEach { f -> AgentCard(padding = pad) { Column { HabitTicked(f.label, w) } } }
    }
}

/** The week as seven marks, each with that day's count. */
@Composable
private fun WeekMarks(habit: String, w: CardWorld) {
    val tone = habitTone(habit)
    val monday = Day.addDays(w.today, -Day.weekIndex(w.today))
    Row(Modifier.fillMaxWidth().padding(top = 14.dp), horizontalArrangement = Arrangement.SpaceBetween) {
        listOf("M", "T", "W", "T", "F", "S", "S").forEachIndexed { i, letter ->
            val date = Day.addDays(monday, i)
            val n = w.habitLogs.filter { it.habit.equals(habit, true) && it.date == date }.sumOf { it.amount ?: 1.0 }
            val future = date > w.today
            Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(letter, style = T.sans.copy(fontSize = 10.5.sp, color = if (date == w.today) C.ink else C.faint, fontWeight = if (date == w.today) FontWeight.Medium else FontWeight.Normal))
                Box(
                    Modifier.size(26.dp).background(if (n > 0) tone.bg else C.white, CircleShape).border(1.dp, if (n > 0) tone.line else if (future) C.lineSoft else C.line, CircleShape),
                    contentAlignment = Alignment.Center,
                ) { if (n > 0) Text(Fmt.num(n), style = T.figure.copy(fontSize = 11.sp, color = tone.ink)) }
            }
        }
    }
}

@Composable
private fun HabitTicked(habit: String, w: CardWorld) {
    // The count from the live log — "2", not "Ticked".
    val n = w.habitLogs.filter { it.habit.equals(habit, true) && it.date == w.today }.sumOf { it.amount ?: 1.0 }
    ReceiptHead({ HabitCoin(habit) }, habit, "Today") { if (n > 0) Fig(Fmt.num(n), 20.sp) else Text("logged", style = T.sans.copy(fontSize = 12.5.sp, color = C.faint)) }
    WeekMarks(habit, w)
    val week = w.habitLogs.filter { it.habit.equals(habit, true) && it.date >= Day.addDays(w.today, -Day.weekIndex(w.today)) && it.date <= w.today }.sumOf { it.amount ?: 1.0 }
    if (week > 0) Text("${Fmt.num(week)} this week so far", style = T.sans.copy(fontSize = 12.5.sp, color = C.faint), modifier = Modifier.padding(top = 10.dp))
}

@Composable
private fun HabitCoin(habit: String) {
    val tone = habitTone(habit)
    val g = habitGlyph(habit)
    if (g != null) IconCoin(g, tone.ink, tone.bg) else InitialCoin(habit, tone.ink, tone.bg)
}

@Composable
private fun HabitManaged(msg: ChatMsg.Confirm, w: CardWorld, ca: ConfirmActions) {
    val name = msg.field("name")?.value ?: msg.lede.substringBefore(" · ")
    val gone = msg.state == "deleted" || (msg.rowId != null && msg.rowId in w.deletedRows)
    val aim = if (msg.field("direction")?.value == "break") "to cut down" else "to build"
    // A name already tracked was reused as it was: nothing was written, and the card says so.
    val meta = when {
        gone -> "Stopped · its history stays"
        msg.lede.endsWith("already tracked") -> "Already tracked"
        else -> "Tracking · $aim"
    }
    ReceiptHead({ if (gone) IconCoin(Ph.x, C.grey, C.lineSoft) else HabitCoin(name) }, name, meta, gone)
    if (!gone) WeekMarks(name, w)
    ReceiptActions(msg, ca)
}

@Composable
private fun ExerciseDone(msg: ChatMsg.Confirm, w: CardWorld) {
    val name = msg.field("name")?.value ?: msg.lede.substringBefore(" · ")
    val times = Regex("(\\d+)×").find(msg.lede)?.groupValues?.get(1)?.toIntOrNull()
    val ex = w.exercises.firstOrNull { it.id == msg.rowId }
    val meta = if (times == 0) "Added to your library" else "Done today"
    ReceiptHead({ IconCoin(PhFill.barbell, C.dietInk, C.dietTint) }, name, meta) {
        val n = ex?.tried ?: times
        if (n != null && n > 0) Column(horizontalAlignment = Alignment.End) {
            Fig("$n×")
            Text("in all", style = T.sans.copy(fontSize = 11.sp, color = C.faint))
        }
    }
}

/* ─── work ────────────────────────────────────────────────────────────── */

private val TASK_STATE = Regex(" · (added|done|already on the list|moved to .+|archived|updated)$")

/** A task card's title, as its lede names it — before the state. */
private fun taskTitle(msg: ChatMsg.Confirm): String {
    val match = TASK_STATE.find(msg.lede)
    return if (match != null) msg.lede.substring(0, match.range.first) else msg.lede
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun TaskReceipt(msg: ChatMsg.Confirm, w: CardWorld, ca: ConfirmActions) {
    val todo = w.todos.firstOrNull { it.id == msg.rowId }
    val match = TASK_STATE.find(msg.lede)
    val state = match?.groupValues?.get(1) ?: "added"
    val title = todo?.name ?: taskTitle(msg)
    // Undone here, or deleted anywhere this session: the card is the task, struck.
    val gone = msg.state == "deleted" || (msg.rowId != null && msg.rowId in w.deletedRows)
    val done = todo?.done ?: (state == "done")
    val due = todo?.due ?: msg.field("due")?.value
    val project = todo?.project?.let { Tasks.projectOf(it, w.projects)?.name } ?: msg.field("project")?.value
    val guessed = todo?.projectGuessed ?: (msg.field("project")?.guessed == true)
    val caption = when {
        gone -> "Removed"
        state.startsWith("moved to ") -> "Moved to ${state.removePrefix("moved to ")}"
        state == "already on the list" -> "Already on your list"
        state == "archived" -> "Archived"
        state == "updated" -> "Updated"
        else -> null
    }
    val struck = done || gone
    Row(verticalAlignment = Alignment.Top, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        Box(
            Modifier.padding(top = 1.dp).size(20.dp).clip(CircleShape)
                .background(if (done && !gone) C.work else C.white).border(1.5.dp, if (gone) C.lineSoft else if (done) C.work else C.border, CircleShape)
                .tap(enabled = todo != null && !gone) { todo?.let { ca.onToggleTodo(it.id) } },
            contentAlignment = Alignment.Center,
        ) { if (done && !gone) Glyph(PhBold.check, 12.dp, Color.White) }
        Column(Modifier.weight(1f)) {
            caption?.let { Text(it, style = T.sans.copy(fontSize = 12.sp, color = C.faint), modifier = Modifier.padding(bottom = 2.dp)) }
            Text(
                title,
                style = T.sans.copy(fontSize = 15.sp, lineHeight = 20.sp, fontWeight = FontWeight.Medium, color = if (struck) C.faint else C.ink, textDecoration = if (struck) TextDecoration.LineThrough else null),
                maxLines = 2, overflow = TextOverflow.Ellipsis,
            )
            if (!gone && (due != null || project != null)) FlowRow(Modifier.padding(top = 6.dp), horizontalArrangement = Arrangement.spacedBy(6.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                if (due != null) Row(
                    Modifier.background(C.workTint, RoundedCornerShape(50)).padding(horizontal = 9.dp, vertical = 3.dp),
                    verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp),
                ) {
                    Glyph(Ph.calendarBlank, 12.dp, C.workInk)
                    Text(Tasks.dueLabel(due, w.today), style = T.sans.copy(fontSize = 12.sp, color = C.workInk))
                }
                if (project != null) Row(Modifier.background(C.surface, RoundedCornerShape(50)).padding(horizontal = 9.dp, vertical = 3.dp), verticalAlignment = Alignment.CenterVertically) {
                    if (guessed) Dot()
                    Text(project, style = T.sans.copy(fontSize = 12.sp, color = C.muted))
                }
            }
        }
    }
    // Just added: one tap takes it back. "Already on your list" added nothing, so it has no Undo.
    if (ca.firstRun != null) {
        if (!gone) ReceiptActions(msg, ca)
    } else if (state == "added" && !gone && todo != null) QuietActions(Quiet("Undo", icon = Ph.arrowCounterClockwise) { ca.onDeleteTask(todo.id) })
    if (gone) return
    // A tracker's task ticked here but not moved there: the one thing left, as its own line.
    val move = msg.field("move_in")?.value
    if (move != null && (todo == null || todo.awaitingMove)) {
        val context = LocalContext.current
        RuleAbove {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(cap(move), style = T.sans.copy(fontSize = 13.sp, color = C.muted), modifier = Modifier.weight(1f))
                todo?.link?.let { link -> OutlineButton("Move it", Ph.arrowUpRight) { context.startActivity(Intent(Intent.ACTION_VIEW, link.toUri())) } }
            }
        }
    }
}

@Composable
private fun ProjectReceipt(msg: ChatMsg.Confirm, w: CardWorld) {
    val name = msg.field("name")?.value ?: msg.lede.substringBefore(" · ")
    val state = msg.lede.substringAfterLast(" · ", "")
    val gone = msg.state == "deleted"
    val project = w.projects.firstOrNull { it.id == msg.rowId }
    val open = w.todos.count { it.project == msg.rowId && !it.done }
    val meta = when {
        gone -> msg.field("tasks")?.value?.let { "Deleted · $it" } ?: "Deleted"
        state == "archived" -> "Archived"
        state == "created" -> if (open == 0) "New project · no tasks yet" else "New project · $open open"
        else -> if (open == 0) "No open tasks" else "$open open"
    }
    ReceiptHead({ Coin(if (gone) C.lineSoft else C.workTint) { ProjectIcon(project, 18.dp) } }, name, meta, gone)
}

/* ─── people, places, memory, profile ─────────────────────────────────── */

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun PersonReceipt(msg: ChatMsg.Confirm) {
    val name = msg.lede.substringBefore(" · ")
    val relation = msg.field("relation")?.value?.takeIf { it != "—" }
    val kind = msg.field("kind")?.value?.takeIf { it != "—" && it != "person" }
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        InitialCoin(name, C.paisaInk, C.paisaTint, 40.dp)
        Column(Modifier.weight(1f)) {
            Text(name, style = T.sans.copy(fontSize = 15.sp, fontWeight = FontWeight.Medium))
            if (relation != null || kind != null) FlowRow(Modifier.padding(top = 5.dp), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                relation?.let { FactChip(cap(it)) }
                kind?.let { FactChip(cap(it)) }
            }
        }
    }
    msg.field("note")?.value?.let { Text(it, style = T.sans.copy(fontSize = 13.sp, color = C.muted), modifier = Modifier.padding(top = 10.dp)) }
}

@Composable
private fun PlaceReceipt(msg: ChatMsg.Confirm, live: LiveRow, ca: ConfirmActions) {
    val gone = live.deleted || msg.state == "deleted"
    val name = msg.lede.substringBefore(" · ")
    val kind = msg.field("kind")?.value?.takeIf { it != "—" }?.let(::cap)
    val visits = msg.field("payments")?.value?.replace("payments", "visits")?.replace("payment", "visit")
    val spent = msg.field("spent")?.value
    ReceiptHead(
        { IconCoin(Ph.mapPin, if (gone) C.grey else C.paisaInk, if (gone) C.lineSoft else C.paisaTint) },
        name, if (gone) "Removed" else listOfNotNull(kind, visits).joinToString(" · "), gone,
    ) { spent?.let { Fig(it, struck = gone, color = if (gone) C.faint else C.ink) } }
    if (!gone && msg.rowId != null) QuietActions(Quiet("Undo", icon = Ph.arrowCounterClockwise) { ca.onDelete(msg) })
}

@Composable
private fun MemoryReceipt(msg: ChatMsg.Confirm, live: LiveRow, ca: ConfirmActions) {
    val gone = live.deleted || msg.state == "deleted"
    val f = msg.fields.firstOrNull()
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        // A fact about the person is their data: Diet's tint, never the brand, which is an action.
        IconCoin(Ph.brain, if (gone) C.grey else C.dietInk, if (gone) C.lineSoft else C.dietTint)
        Text(if (gone) "Forgotten" else "I’ll remember", style = T.sans.copy(fontSize = 13.sp, color = C.faint), modifier = Modifier.weight(1f))
        f?.label?.takeIf { it.isNotBlank() }?.let { FactChip(cap(it)) }
    }
    f?.value?.let {
        Text(
            it,
            style = T.sans.copy(fontSize = 15.sp, lineHeight = 22.sp, color = if (gone) C.faint else C.ink, textDecoration = if (gone) TextDecoration.LineThrough else null),
            modifier = Modifier.padding(top = 10.dp),
        )
    }
    ReceiptActions(msg, ca, if (!gone && msg.rowId != null) Quiet("Forget", C.red) { ca.onDelete(msg) } else null)
}

/**
 * One fact about the person, or a target. A coin in its mode's tint — money
 * the paisa tint, everything about the person and their health the diet
 * tint — never a coloured dot, which would read as a second estimate. An age
 * is the field it was said as: the date it became is never drawn.
 */
@Composable
private fun ProfileReceipt(msg: ChatMsg.Confirm, ca: ConfirmActions) {
    val f = msg.fields.firstOrNull() ?: return GenericReceipt(msg)
    val gone = msg.state == "deleted"
    val icon = when (f.key) {
        "savings_target_paise" -> Ph.currencyInr
        "sleep_target_min" -> PhFill.moon
        "step_target" -> PhFill.sneakerMove
        "display_name", "gender" -> Ph.user
        "age", "dob" -> Ph.cake
        "height_cm" -> Ph.ruler
        "city" -> Ph.mapPin
        "diet" -> Ph.bowlFood
        "weight_target_kg" -> Ph.scales
        else -> Ph.bowlFood
    }
    val money = f.key == "savings_target_paise"
    val coin: @Composable () -> Unit = {
        when {
            gone -> IconCoin(icon, C.grey, C.lineSoft)
            money -> IconCoin(icon, C.paisaInk, C.paisaTint)
            else -> IconCoin(icon, C.dietInk, C.dietTint)
        }
    }
    ReceiptHead(coin, f.label, if (gone) "Removed" else if (money) "each month" else "", gone) {
        Fig(f.value, struck = gone, color = if (gone) C.faint else C.ink)
    }
    // Said in words, like the target was: Change attaches it to the composer, it does not open a page.
    ReceiptActions(msg, ca, Quiet("Change") { ca.onContext(targetContext(f.label, f.value)) })
}

/** A source this app does not know yet: the lede, and its fields as small facts. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun GenericReceipt(msg: ChatMsg.Confirm) {
    Text(msg.lede, style = T.sans.copy(fontSize = 15.sp, fontWeight = FontWeight.Medium))
    if (msg.fields.isNotEmpty()) FlowRow(Modifier.padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(6.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        // A day reads as a day, never as its ISO form.
        msg.fields.forEach { f -> FactChip("${f.label} ${if (ISO_DAY.matches(f.value)) Day.cardDay(f.value) else f.value}") }
    }
}
