package com.sonu.spica.ui.chat

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil3.compose.AsyncImage
import com.sonu.spica.data.Api
import com.sonu.spica.data.ChatMsg
import com.sonu.spica.data.DishRow
import com.sonu.spica.data.LimitInfo
import com.sonu.spica.data.Meal
import com.sonu.spica.data.PantryRow
import com.sonu.spica.data.PantryStatus
import com.sonu.spica.data.PendingItem
import com.sonu.spica.data.Project
import com.sonu.spica.data.SuggestItem
import com.sonu.spica.data.TaskKind
import com.sonu.spica.data.Todo
import com.sonu.spica.data.Tx
import com.sonu.spica.data.UDHAAR_KINDS
import com.sonu.spica.lib.Day
import com.sonu.spica.lib.Fmt
import com.sonu.spica.logic.Notes
import com.sonu.spica.logic.Tasks
import com.sonu.spica.ui.common.AgentCard
import com.sonu.spica.ui.common.CardHeading
import com.sonu.spica.ui.common.Dot
import com.sonu.spica.ui.common.Glyph
import com.sonu.spica.ui.common.MoveReminder
import com.sonu.spica.ui.common.Ph
import com.sonu.spica.ui.common.PhBold
import com.sonu.spica.ui.common.PhFill
import com.sonu.spica.ui.common.Tone
import com.sonu.spica.ui.common.TrayAction
import com.sonu.spica.ui.common.TrayActions
import com.sonu.spica.ui.common.TrayToggle
import com.sonu.spica.ui.common.fadeUp
import com.sonu.spica.ui.commitments.LinkWord
import com.sonu.spica.ui.commitments.PaymentLinks
import com.sonu.spica.ui.commitments.PaymentTray
import com.sonu.spica.ui.common.tap
import com.sonu.spica.ui.theme.C
import com.sonu.spica.ui.theme.T

/*
 * The cards in the thread — spec/done/card-redesign.md. The rule they all keep:
 * text first, the card below, never a sentence inside a card. A card the phone
 * builds (Cash flow, To-do, Pantry, Recipes) has no reply above it, so its own line —
 * worked out from the live rows when it is drawn — stands above it instead. The
 * agent's To-do card has its reply, so it draws none.
 */

/** A 1dp rule along the bottom edge, as `border-bottom` draws it. */
fun Modifier.bottomRule(color: Color = C.lineSoft) = drawBehind {
    drawLine(color, Offset(0f, size.height), Offset(size.width, size.height), 1.dp.toPx())
}

private fun Modifier.topRule(color: Color = C.lineSoft) = drawBehind {
    drawLine(color, Offset(0f, 0f), Offset(size.width, 0f), 1.dp.toPx())
}

private fun dayLabel(day: Int, date: String?) = date?.let(Day::shortDay) ?: "$day"

/** The agent's line above a card it did not write a reply for. */
@Composable
private fun AgentLine(text: String) {
    if (text.isNotBlank()) Text(text, style = T.agentVoice, modifier = Modifier.padding(bottom = 8.dp))
}

/* ─── agent ───────────────────────────────────────────────────────────── */

/**
 * The agent's reply. The headline row is only drawn when there is one. A send
 * that fails is marked on your own message, so no agent bubble carries a Retry.
 */
@Composable
fun AgentBubble(msg: ChatMsg.Agent) {
    // No container: the agent's prose is the page itself, set in its serif.
    Column(Modifier.fadeUp()) {
        if (msg.title.isNotEmpty()) {
            Text(
                buildAnnotatedString {
                    append(msg.title)
                    if (msg.hl.isNotEmpty()) withStyle(SpanStyle(color = msg.hlColor)) { append(" ${msg.hl}") }
                },
                style = T.display.copy(fontSize = 17.sp),
                modifier = Modifier.padding(bottom = 4.dp),
            )
        }
        MarkdownBody(msg.body)
    }
}

/* ─── table ───────────────────────────────────────────────────────────── */

class RowActions(
    val openRow: String?,
    val onToggleRow: (String) -> Unit,
    val onDelete: (String, String) -> Unit,
    val onEdit: (String, String, String) -> Unit,
    /** What a payment's tray needs to say it settles a commitment. */
    val links: PaymentLinks = PaymentLinks.None,
)

/** One row of a ledger table, as the old design drew it: date · what, its line under it · figure · ⋮. */
@Composable
private fun LedgerRow(
    id: String, date: String, name: String, sub: String, figure: String, figureColor: Color, struck: Boolean,
    actions: List<TrayAction>, ra: RowActions, first: Boolean,
    /** The commitment this payment settles, and whether that was only a guess — the amber dot. */
    link: String? = null, linkGuess: Boolean = false,
    /** The tray, when it is more than a list of actions — a payment's, with its commitment verbs. */
    tray: (@Composable () -> Unit)? = null,
) {
    val open = ra.openRow == id
    Column(Modifier.fillMaxWidth().then(if (first) Modifier else Modifier.topRule())) {
        Row(Modifier.fillMaxWidth().padding(vertical = 8.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(date, style = T.sans.copy(fontSize = 11.5.sp, color = C.muted), modifier = Modifier.width(44.dp))
            Column(Modifier.weight(1f)) {
                Text(
                    name,
                    style = T.sans.copy(fontSize = 14.sp, fontWeight = FontWeight.Medium, color = if (struck) C.faint else C.ink, textDecoration = if (struck) TextDecoration.LineThrough else null),
                    maxLines = 1, overflow = TextOverflow.Ellipsis,
                )
                Row(Modifier.padding(top = 1.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text(sub, style = T.sans.copy(fontSize = 11.5.sp, color = C.faint), maxLines = 1, modifier = Modifier.weight(1f, fill = false))
                    if (link != null) LinkWord(link, linkGuess)
                }
            }
            Fig(figure, 14.sp, if (struck) C.faint else figureColor, struck)
            if (struck) Spacer(Modifier.width(26.dp)) else TrayToggle { ra.onToggleRow(id) }
        }
        if (open && !struck) {
            if (tray != null) Column(Modifier.padding(bottom = 9.dp)) { tray() } else TrayActions(actions, Modifier.padding(bottom = 9.dp))
        }
    }
}

/**
 * A ledger table. Resolves its stored row ids against live data, so a row
 * deleted anywhere is struck here too — drawn faint, without its ⋮, and left
 * out of the total and the count. The total leads; no note under it — the
 * agent's reply above is the commentary.
 */
@Composable
fun TableCard(
    msg: ChatMsg.Table, tx: List<Tx>, meals: List<Meal>, deleted: List<String>, ra: RowActions, proteinTarget: Double?,
    onNeedRows: (String, List<String>) -> Unit,
) {
    val paisa = msg.source == "paisa"
    val txRows = if (paisa) tx.associateBy { it.id }.let { by -> msg.ids.mapNotNull(by::get) } else emptyList()
    val mealRows = if (!paisa) meals.associateBy { it.id }.let { by -> msg.ids.mapNotNull(by::get) } else emptyList()
    // A card can name a row from before the deck's window: ask for it once.
    val held = (if (paisa) txRows.map { it.id } else mealRows.map { it.id }).toSet()
    val missing = msg.ids.filter { it !in held }
    LaunchedEffect(missing.joinToString(",")) { if (missing.isNotEmpty()) onNeedRows(msg.source, missing) }

    val loading = missing.isNotEmpty()
    val word = T.sans.copy(fontSize = 13.sp, color = C.faint)
    AgentCard(padding = PaddingValues(horizontal = 14.dp, vertical = 12.dp)) {
        Column {
            if (paisa) {
                fun gone(t: Tx) = t.deleted || t.id in deleted
                val live = txRows.filter { !gone(it) }
                // A loan is neither spending nor income: a lent, borrowed or repaid
                // row stays on the card, named for what it is, but out of its sums
                // and its count — a ₹4,000 lending was read as ₹4,000 spent, and a
                // borrowing is not money that came in.
                val money = live.filter { it.kind !in UDHAAR_KINDS }
                val spends = money.filter { !it.credit }
                val came = money.filter { it.credit }
                val cameIn = came.sumOf { it.amt }
                fun payments(n: Int) = "$n ${if (n == 1) "payment" else "payments"}"
                // A lead with a figure has a rule under it; words alone, or none, do not.
                val rule = spends.isNotEmpty() || came.isNotEmpty()
                when {
                    spends.isNotEmpty() -> Row(verticalAlignment = Alignment.Bottom, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Fig(Fmt.rupees(spends.sumOf { it.amt }), 26.sp)
                        Text("spent · ${payments(spends.size)}" + if (cameIn > 0) " · +${Fmt.rupees(cameIn)} in" else "", style = word, modifier = Modifier.padding(bottom = 4.dp))
                    }
                    came.isNotEmpty() -> Row(verticalAlignment = Alignment.Bottom, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Fig("+${Fmt.rupees(cameIn)}", 26.sp, C.paisaInk)
                        Text("came in · ${payments(came.size)}", style = word, modifier = Modifier.padding(bottom = 4.dp))
                    }
                    // Every row deleted: the caption says so.
                    !loading && live.isEmpty() -> Text("no payments yet", style = word)
                    // Only loans left: no lead at all. The rows say what each one is,
                    // and "no payments yet" over rows that are there would be false.
                }
                if (rule && txRows.isNotEmpty()) Spacer(Modifier.fillMaxWidth().padding(top = 12.dp).height(1.dp).background(C.line))
                txRows.forEachIndexed { i, t ->
                    // Udhaar says what it is, never a category: Lent, Borrowed, Repaid.
                    val udhaar = UDHAAR_KINDS[t.kind]
                    val sub = (udhaar ?: t.cat) + (if (t.failed) " · unsaved" else if (t.pending) " · saving" else "")
                    // The commitment it settles, named from the live lines; the dot while only guessed.
                    val link = if (udhaar == null && t.commitmentId != null) ra.links.nameOf(t.commitmentId) ?: "Committed" else null
                    LedgerRow(
                        t.id, dayLabel(t.day, t.date), t.name, if (gone(t)) "Removed" else sub,
                        // A credit ARRIVED — never drawn as an expense. Spending is ink, not red.
                        if (t.credit) "+${Fmt.rupees(t.amt)}" else Fmt.rupees(t.amt),
                        if (t.credit) C.paisaInk else C.ink, gone(t),
                        buildList {
                            add(TrayAction("Edit") { ra.onEdit("paisa", t.id, "${t.name} ${t.amt}") })
                            add(TrayAction("Delete", Tone.Danger) { ra.onDelete("paisa", t.id) })
                        },
                        ra, i == 0, link = link, linkGuess = t.commitmentInferred,
                        tray = if (udhaar == null) ({
                            PaymentTray(t, ra.links, listOf(
                                TrayAction("Edit") { ra.onEdit("paisa", t.id, "${t.name} ${t.amt}") },
                                TrayAction("Delete", Tone.Danger) { ra.onDelete("paisa", t.id) },
                            ))
                        }) else null,
                    )
                }
            } else {
                fun gone(m: Meal) = m.deleted || m.id in deleted
                val live = mealRows.filter { !gone(it) }
                val p = live.sumOf { it.p }
                val k = live.sumOf { it.k }
                // A daily target only means something against one day's meals.
                val target = proteinTarget?.takeIf { it > 0 && live.map { m -> m.date ?: "${m.day}" }.toSet().size == 1 }
                if (live.isNotEmpty()) {
                    Row(verticalAlignment = Alignment.Bottom, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Fig("${Fmt.num(Math.round(p * 10) / 10.0)} g", 26.sp)
                        Text(
                            if (target != null) "of ${Fmt.num(target)} g protein" else "protein · ${live.size} ${if (live.size == 1) "meal" else "meals"}",
                            style = word, modifier = Modifier.weight(1f).padding(bottom = 4.dp),
                        )
                        if (k > 0) Fig("${Fmt.indian(k.toLong())} kcal", 13.sp, C.faint, modifier = Modifier.padding(bottom = 4.dp))
                    }
                    if (target != null) ThinBar((p / target).toFloat(), C.diet, Modifier.padding(top = 10.dp))
                } else if (!loading) Text("no meals yet", style = word)
                if (live.isNotEmpty() && mealRows.isNotEmpty()) Spacer(Modifier.fillMaxWidth().padding(top = 12.dp).height(1.dp).background(C.line))
                mealRows.forEachIndexed { i, m ->
                    val empty = m.k == 0 && m.p == 0.0
                    val sub = (if (empty) "nothing recorded" else listOfNotNull(m.type, "${m.k} kcal").joinToString(" · ")) +
                        (if (m.failed) " · unsaved" else if (m.pending) " · saving" else "")
                    LedgerRow(
                        m.id, dayLabel(m.day, m.date), m.name, if (gone(m)) "Removed" else sub,
                        if (empty) "—" else "${Fmt.num(m.p)} g", C.ink, gone(m),
                        listOf(TrayAction("Edit") { ra.onEdit("diet", m.id, m.name) }, TrayAction("Delete", Tone.Danger) { ra.onDelete("diet", m.id) }),
                        ra, i == 0,
                    )
                }
            }
            if (missing.isNotEmpty() && held.size < msg.ids.size) {
                Text(
                    if (missing.size == msg.ids.size) "Loading rows…" else "${missing.size} more loading…",
                    style = T.sans.copy(fontSize = 12.sp, color = C.faint), modifier = Modifier.padding(top = 6.dp),
                )
            }
        }
    }
}

/* ─── suggest ─────────────────────────────────────────────────────────── */

class SuggestActions(
    val openRef: String?,
    val onToggle: (String) -> Unit,
    val onLog: (SuggestItem) -> Unit,
    val onSave: (String, SuggestItem) -> Unit,
    val onDismiss: (String, String) -> Unit,
)

/** What to eat or do next — each one tap from logged, with a real button for it. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun SuggestCard(msg: ChatMsg.Suggest, loggedRefs: Set<String>, pendingRefs: List<String>, sa: SuggestActions) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        msg.items.forEach { item ->
            val logged = item.ref in loggedRefs
            val pending = item.ref in pendingRefs
            val dish = item.type == "dish"
            val meta = if (dish) listOfNotNull(item.mealType, item.minutes?.let { "$it min" }, item.kcal?.let { "$it kcal" }).joinToString(" · ")
            else listOfNotNull(item.muscleGroup?.replaceFirstChar { it.uppercase() }, item.minutes?.let { "$it min" }).joinToString(" · ")
            // The reasons as small facts — what the meta line or the figure already says is left out.
            val facts = item.why.split(" · ").map { it.trim() }.filter {
                it.isNotEmpty() && (dish || (it != item.exerciseKind && it != item.muscleGroup && !it.startsWith("done ") && it != "not tried yet"))
            }
            AgentCard(Modifier.alpha(if (pending) 0.7f else 1f), padding = PaddingValues(horizontal = 14.dp, vertical = 12.dp)) {
                Column {
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        // The dish's own image or a flat mark — never a stock photo.
                        if (item.imageUrl != null) {
                            AsyncImage(item.imageUrl, null, Modifier.size(44.dp).clip(RoundedCornerShape(10.dp)), contentScale = ContentScale.Crop)
                        } else if (dish) IconCoin(Ph.cookingPot, C.dietInk, C.dietTint, 44.dp)
                        else IconCoin(PhFill.barbell, C.dietInk, C.dietTint, 44.dp)
                        Column(Modifier.weight(1f)) {
                            Text(item.name, style = T.sans.copy(fontSize = 15.sp, fontWeight = FontWeight.Medium), maxLines = 2, overflow = TextOverflow.Ellipsis)
                            if (meta.isNotEmpty()) Text(meta, style = T.sans.copy(fontSize = 12.5.sp, color = C.faint))
                        }
                        if (dish) item.proteinG?.let { Fig("${Fmt.num(it)} g", 17.sp) }
                        else if ((item.tried ?: 0) > 0) Column(horizontalAlignment = Alignment.End) {
                            Fig("${item.tried}×", 15.sp)
                            Text("done", style = T.sans.copy(fontSize = 11.sp, color = C.faint))
                        } else Text("new", style = T.sans.copy(fontSize = 12.5.sp, color = C.faint))
                    }
                    if (facts.isNotEmpty() || (dish && item.missing.isNotEmpty())) {
                        FlowRow(Modifier.padding(start = 56.dp, top = 10.dp), horizontalArrangement = Arrangement.spacedBy(6.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                            facts.forEach { FactChip(it) }
                        }
                    }
                    Row(Modifier.padding(start = 56.dp, top = 12.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                        when {
                            logged -> Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                Glyph(Ph.checkCircle, 16.dp, C.brand)
                                Text(if (dish) "Logged" else "Done", style = T.sans.copy(fontSize = 13.5.sp, fontWeight = FontWeight.Medium, color = C.brand))
                            }
                            pending -> Text("Logging…", style = T.sans.copy(fontSize = 13.5.sp, color = C.muted))
                            else -> FilledButton(if (dish) "Log it" else "Done") { sa.onLog(item) }
                        }
                        if (dish) Text(
                            if (item.saved) "Saved" else "Save",
                            style = T.sans.copy(fontSize = 13.5.sp, fontWeight = FontWeight.Medium, color = if (item.saved) C.brand else C.muted),
                            modifier = Modifier.clip(RoundedCornerShape(6.dp)).tap { sa.onSave(msg.id, item) }.padding(vertical = 3.dp),
                        )
                        if (!logged) Text(
                            "Not this",
                            style = T.sans.copy(fontSize = 13.5.sp, fontWeight = FontWeight.Medium, color = C.muted),
                            modifier = Modifier.clip(RoundedCornerShape(6.dp)).tap { sa.onDismiss(msg.id, item.ref) }.padding(vertical = 3.dp),
                        )
                    }
                }
            }
        }
    }
}

/* ─── ask ─────────────────────────────────────────────────────────────── */

/**
 * One question, and only when the answer changes a number. The question is the
 * agent's text, above; the options are full-width rows in the card under it,
 * and an option answers as the next thing said.
 */
@Composable
fun AskCard(msg: ChatMsg.Ask, pending: String?, onAnswer: (String) -> Unit) {
    Column {
        pending?.let {
            Text(it, style = T.sans.copy(fontSize = 13.sp, color = C.faint, textDecoration = TextDecoration.LineThrough), modifier = Modifier.padding(bottom = 6.dp))
        }
        AgentLine(msg.question)
        if (msg.options.isNotEmpty()) AgentCard(padding = PaddingValues(horizontal = 14.dp, vertical = 2.dp)) {
            Column {
                msg.options.forEachIndexed { i, o ->
                    Row(
                        Modifier.fillMaxWidth().then(if (i == 0) Modifier else Modifier.topRule(C.line)).tap { onAnswer(o) }.padding(vertical = 12.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text(o, style = T.sans.copy(fontSize = 15.sp, fontWeight = FontWeight.Medium), modifier = Modifier.weight(1f))
                        Glyph(PhBold.caretRight, 13.dp, C.faint)
                    }
                }
            }
        }
    }
}

/* ─── todo ────────────────────────────────────────────────────────────── */

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun TaskLine(task: Todo, projects: List<Project>, today: String, onToggle: (String) -> Unit, first: Boolean, showProject: Boolean = true) {
    val proj = Tasks.projectOf(task.project, projects)
    // A list already narrowed to one project does not repeat its name on every line.
    val chip = proj?.takeIf { showProject }
    // The small print beside the project: how late, which day, P1, where it came from.
    val due = when {
        task.due == null || task.due == today -> null
        task.due < today -> Day.diffDays(task.due, today).let { "$it ${if (it == 1) "day" else "days"} late" }
        else -> Day.cardDay(task.due)
    }
    val meta = listOfNotNull(due, task.priority?.takeIf { it <= 2 && !task.done }?.let { "P$it" }, task.src).joinToString(" · ")
    // Filled in the project's colour once done.
    val tint = proj?.let { C.hex(it.color) } ?: C.work
    Row(
        Modifier.fillMaxWidth().then(if (first) Modifier else Modifier.topRule()).tap { onToggle(task.id) }.padding(vertical = 8.dp),
        verticalAlignment = Alignment.Top, horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Box(
            Modifier.padding(top = 1.dp).size(18.dp).clip(CircleShape).background(if (task.done) tint else C.white).border(1.5.dp, if (task.done) tint else C.border, CircleShape),
            contentAlignment = Alignment.Center,
        ) { if (task.done) Glyph(PhBold.check, 11.dp, Color.White) }
        Column(Modifier.weight(1f)) {
            Text(
                task.name,
                style = T.sans.copy(fontSize = 14.5.sp, lineHeight = 20.sp, color = if (task.done) C.faint else C.ink, textDecoration = if (task.done) TextDecoration.LineThrough else null),
            )
            if (chip != null || meta.isNotEmpty()) FlowRow(Modifier.padding(top = 4.dp), horizontalArrangement = Arrangement.spacedBy(6.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                if (chip != null) Row(Modifier.background(C.surface, RoundedCornerShape(50)).padding(horizontal = 9.dp, vertical = 3.dp), verticalAlignment = Alignment.CenterVertically) {
                    if (task.projectGuessed) Dot()
                    Text(chip.name, style = T.sans.copy(fontSize = 12.sp, color = C.muted))
                }
                if (meta.isNotEmpty()) Text(meta, style = T.sans.copy(fontSize = 12.sp, color = C.faint), modifier = Modifier.padding(top = 3.dp))
            }
        }
    }
    MoveReminder(task, 28.dp)
}

/**
 * The task list, by when it is due: late, today, this week, later — each
 * project a chip, not a block. A task ticked today stays where it was, struck,
 * so a tick never makes the list jump out from under your finger; one finished
 * on an earlier day is done and gone.
 *
 * `project` narrows it to one project, matched by name (an alias as a last
 * resort); a name that matches none is an empty list, never everything.
 * `line` is the card's own sentence above it — the agent's card has none,
 * because its reply is the text.
 */
@Composable
fun TodoCard(
    todos: List<Todo>, scope: String, projects: List<Project>, today: String,
    project: String? = null, line: Boolean = true, onToggle: (String) -> Unit,
) {
    val scoped = project?.let { name ->
        projects.firstOrNull { it.name.equals(name, ignoreCase = true) }
            ?: projects.firstOrNull { p -> p.aliases.any { it.equals(name, ignoreCase = true) } }
    }
    val pool = when {
        project != null -> todos.filter { scoped != null && it.project == scoped.id }
        scope == "work" -> todos.filter { it.kind == TaskKind.Work }
        else -> todos
    }
    val open = pool.filter { !it.done }
    val late = Tasks.lateCount(pool, today)
    val groups = Tasks.byWhen(Tasks.onList(pool, today), today)
    Column {
        if (line) AgentLine(Notes.todo(pool, today))
        if (groups.isNotEmpty()) AgentCard(padding = PaddingValues(horizontal = 14.dp, vertical = 12.dp)) {
            Column {
                Row(verticalAlignment = Alignment.Bottom, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    Fig("${open.size}", 22.sp)
                    Text("open", style = T.sans.copy(fontSize = 13.sp, color = C.faint), modifier = Modifier.padding(bottom = 3.dp))
                    if (late > 0) {
                        Text("·", style = T.sans.copy(fontSize = 13.sp, color = C.faint), modifier = Modifier.padding(bottom = 3.dp))
                        Fig("$late", 22.sp, C.red)
                        Text("late", style = T.sans.copy(fontSize = 13.sp, color = C.faint), modifier = Modifier.padding(bottom = 3.dp))
                    }
                }
                groups.forEach { (label, color, tasks) ->
                    Text(label, style = T.sans.copy(fontSize = 12.sp, fontWeight = FontWeight.Medium, color = color), modifier = Modifier.padding(top = 14.dp, bottom = 2.dp))
                    tasks.forEachIndexed { i, t -> TaskLine(t, projects, today, onToggle, i == 0, showProject = scoped == null) }
                }
            }
        }
    }
}

/* ─── pantry and dishes (+ menu) ──────────────────────────────────────── */

@Composable
private fun GroupLabel(text: String, color: Color) =
    Text(text, style = T.sans.copy(fontSize = 12.sp, fontWeight = FontWeight.Medium, color = color), modifier = Modifier.padding(top = 12.dp))

/** A count that leads a card, with its word beside it: "11 in the kitchen". */
@Composable
private fun Lead(figure: String, word: String) {
    Row(verticalAlignment = Alignment.Bottom, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        Fig(figure, 20.sp)
        Text(word, style = T.sans.copy(fontSize = 13.sp, color = C.faint), modifier = Modifier.padding(bottom = 2.dp))
    }
}

/** A name with its small print under it, and a figure on the right. */
@Composable
private fun ListLine(name: String, sub: String?, right: String, rightColor: Color, first: Boolean) {
    Row(Modifier.fillMaxWidth().then(if (first) Modifier else Modifier.topRule()).padding(vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text(name, style = T.sans.copy(fontSize = 14.5.sp), maxLines = 1, overflow = TextOverflow.Ellipsis)
            if (!sub.isNullOrEmpty()) Text(sub, style = T.sans.copy(fontSize = 12.sp, color = C.faint))
        }
        Fig(right, 13.5.sp, rightColor)
    }
}

private fun stockOf(r: PantryRow) = when {
    r.staple -> "always"
    r.status == PantryStatus.New -> "not counted"
    else -> Api.inUnit(r.stockG, r.unit)
}

private fun days(n: Int) = "$n ${if (n == 1) "day" else "days"}"

/** Shared by the pantry and recipes cards — which list, read live; nothing is stored on the message. */
@Composable
fun PantryCard(msg: ChatMsg.Pantry, pantry: List<PantryRow>, dishes: List<DishRow>, today: String) {
    if (msg.list == "dishes") DishesList(dishes) else PantryList(msg.id, pantry, today)
}

/**
 * What is at home, grouped by what to do about it: use soon, running low, and
 * the rest folded. The status is derived every render from the live rows, and
 * so is the agent's line above the card.
 */
@Composable
private fun PantryList(id: String, rows: List<PantryRow>, today: String) {
    var unfold by remember(id) { mutableStateOf(false) }
    Column {
        AgentLine(Notes.pantry(rows, today))
        // Nothing tracked: the line alone, never an empty box under it.
        if (rows.isEmpty()) return@Column
        // Past its shelf life, oldest first: the one that has sat longest goes first.
        val useSoon = rows.filter { it.status == PantryStatus.Stale }.sortedBy { it.lastIn ?: "" }
        val low = rows.filter { it.status == PantryStatus.Soon || it.status == PantryStatus.Out }
        val stocked = rows.filter { it.status == PantryStatus.Ok || it.status == PantryStatus.Staple || it.status == PantryStatus.New }
        AgentCard(padding = PaddingValues(horizontal = 14.dp, vertical = 12.dp)) {
            Column {
                Lead("${rows.count { it.status != PantryStatus.Out }}", "in the kitchen")
                if (useSoon.isNotEmpty()) {
                    GroupLabel("Use soon", C.red)
                    useSoon.forEachIndexed { i, r ->
                        ListLine(r.name, stockOf(r), r.lastIn?.let { days(Day.diffDays(it, today)) } ?: "—", C.muted, i == 0)
                    }
                }
                if (low.isNotEmpty()) {
                    GroupLabel("Running low", C.ink)
                    low.forEachIndexed { i, r ->
                        val out = r.status == PantryStatus.Out
                        ListLine(r.name, null, if (out) "out" else "${Api.inUnit(r.stockG, r.unit)} left", if (out) C.red else C.muted, i == 0)
                    }
                }
                if (stocked.isNotEmpty()) {
                    Row(
                        Modifier.fillMaxWidth().padding(top = 14.dp).clip(RoundedCornerShape(6.dp)).tap { unfold = !unfold },
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text("Stocked · ${stocked.size}", style = T.sans.copy(fontSize = 12.sp, fontWeight = FontWeight.Medium, color = C.faint), modifier = Modifier.weight(1f))
                        Glyph(PhBold.caretDown, 12.dp, C.faint, Modifier.rotate(if (unfold) 180f else 0f))
                    }
                    if (unfold) stocked.forEachIndexed { i, r -> ListLine(r.name, null, stockOf(r), C.muted, i == 0) }
                }
            }
        }
    }
}

/** Your dishes — tried or saved — as suggestions draw them. */
@Composable
private fun DishesList(dishes: List<DishRow>) {
    Column {
        AgentLine(Notes.dishes(dishes))
        if (dishes.isEmpty()) return@Column
        val tried = dishes.count { it.tried > 0 }
        AgentCard(padding = PaddingValues(horizontal = 14.dp, vertical = 4.dp)) {
            Column {
                Box(Modifier.padding(top = 8.dp, bottom = 2.dp)) {
                    Lead("${dishes.size}", "${if (dishes.size == 1) "dish" else "dishes"} · $tried eaten")
                }
                dishes.forEach { d ->
                    Row(
                        Modifier.fillMaxWidth().topRule().padding(vertical = 9.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(10.dp),
                    ) {
                        IconCoin(Ph.cookingPot, C.dietInk, C.dietTint, 32.dp)
                        Column(Modifier.weight(1f)) {
                            Text(d.name, style = T.sans.copy(fontSize = 14.5.sp), maxLines = 1, overflow = TextOverflow.Ellipsis)
                            val meta = listOfNotNull(d.mealType, d.minutes?.let { "$it min" }, d.kcal?.let { "$it kcal" }).joinToString(" · ")
                            if (meta.isNotEmpty()) Text(meta, style = T.sans.copy(fontSize = 12.sp, color = C.faint))
                        }
                        Fig("${Fmt.num(d.proteinG)} g", 14.sp)
                        Text(
                            if (d.tried > 0) "${d.tried}×" else if (d.saved) "saved" else "new",
                            style = T.sans.copy(fontSize = 12.sp, color = if (d.tried > 0) C.dietInk else C.faint, textAlign = TextAlign.End),
                            modifier = Modifier.width(40.dp),
                        )
                    }
                }
            }
        }
    }
}

/* ─── cash flow (+ menu) ──────────────────────────────────────────────── */

@Composable
private fun FlowLine(name: String, whenText: String, figure: String, tone: Color, first: Boolean = false) {
    Row(
        Modifier.fillMaxWidth().then(if (first) Modifier else Modifier.topRule()).padding(vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Text(name, style = T.sans.copy(fontSize = 14.5.sp), maxLines = 1, overflow = TextOverflow.Ellipsis)
        Text(whenText, style = T.sans.copy(fontSize = 12.sp, color = C.faint), maxLines = 1, modifier = Modifier.weight(1f))
        Fig(figure, 14.5.sp, tone)
    }
}

/**
 * The month from the + menu: what is left at month end leads, one bar shows
 * how much of what came in is going out, then the lines it is made of.
 *
 * The figures are the server's — `pool` and `locked` from `GET /paisa/summary`,
 * the same function the Paisa card and the agent read — so this card cannot
 * disagree with either. What is lent out is listed but never counted: a
 * friend's promise is not money in hand. The line above is worked out from
 * the same rows each time the card is drawn.
 */
@Composable
fun FlowCard(limit: LimitInfo?, cameIn: Int, pending: List<PendingItem>, today: String) {
    val left = limit?.let { it.pool - it.locked }
    Column {
        AgentLine(Notes.flow(cameIn, left, limit?.locked, pending.sumOf { it.remaining }))
        // Not loaded yet, or a month with nothing in it: the line says so, and
        // no empty box of ₹0s sits under it.
        if (limit == null || left == null) return@Column
        val gone = cameIn - limit.pool
        if (cameIn == 0 && gone == 0 && limit.locked == 0 && pending.isEmpty()) return@Column
        val goingOut = gone + limit.locked
        val share = if (cameIn > 0) (goingOut.toFloat() / cameIn).coerceIn(0f, 1f) else 1f
        val over = goingOut > cameIn
        AgentCard(padding = PaddingValues(start = 14.dp, end = 14.dp, top = 12.dp, bottom = 6.dp)) {
            Column {
                Text("Left at month end", style = T.sans.copy(fontSize = 12.5.sp, color = C.faint))
                Fig(Fmt.rupees(left), 28.sp, if (left < 0) C.red else C.ink)
                if (cameIn > 0) {
                    // Going out fills; what stays is the track. Red only when
                    // going out is more than came in — spending is not an alarm.
                    Box(Modifier.fillMaxWidth().padding(top = 12.dp, bottom = 6.dp).height(8.dp).clip(RoundedCornerShape(4.dp)).background(C.ringIdle)) {
                        Box(Modifier.fillMaxWidth(share).fillMaxHeight().background(if (over) C.red else C.paisa))
                    }
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text("${Fmt.rupees(goingOut)} going out", style = T.sans.copy(fontSize = 12.sp, color = C.faint), modifier = Modifier.weight(1f))
                        Text(if (left >= 0) "${Fmt.rupees(left)} stays" else "${Fmt.rupees(-left)} short", style = T.sans.copy(fontSize = 12.sp, color = C.faint))
                    }
                }
                Spacer(Modifier.padding(top = 12.dp, bottom = 2.dp).fillMaxWidth().height(1.dp).background(C.line))
                FlowLine("Came in", "this month", "+${Fmt.rupees(cameIn)}", C.paisaInk, first = true)
                FlowLine("Gone out", "so far", Fmt.rupees(gone), C.ink)
                if (limit.locked > 0) FlowLine("Still to go", "committed", Fmt.rupees(limit.locked), C.ink)
                pending.forEach { p ->
                    val age = Day.diffDays(p.date, today)
                    FlowLine(p.label, if (age > 0) "owes you · ${days(age)}" else "owes you", Fmt.rupees(p.remaining), C.muted)
                }
            }
        }
    }
}
