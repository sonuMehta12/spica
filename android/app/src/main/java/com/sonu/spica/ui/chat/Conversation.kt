package com.sonu.spica.ui.chat

import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawWithContent
import androidx.compose.ui.graphics.BlendMode
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.CompositingStrategy
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.em
import androidx.compose.ui.unit.sp
import com.sonu.spica.data.ChatMsg
import com.sonu.spica.data.Suggestion
import com.sonu.spica.lib.Fmt
import com.sonu.spica.state.AppState
import com.sonu.spica.state.SpicaViewModel
import com.sonu.spica.state.DerivedView
import com.sonu.spica.state.Load
import com.sonu.spica.state.Phase
import com.sonu.spica.ui.common.AgentShape
import com.sonu.spica.ui.commitments.CommitmentsCard
import com.sonu.spica.ui.commitments.commitmentActions
import com.sonu.spica.ui.commitments.paymentLinks
import com.sonu.spica.ui.common.Chip
import com.sonu.spica.ui.common.Mascot
import com.sonu.spica.ui.common.MascotState
import com.sonu.spica.ui.common.UserBubble
import com.sonu.spica.ui.common.tap
import com.sonu.spica.ui.theme.C
import com.sonu.spica.ui.theme.S
import com.sonu.spica.ui.theme.T
import androidx.compose.ui.draw.alpha
import com.sonu.spica.ui.common.Glyph
import com.sonu.spica.ui.common.Ph
import com.sonu.spica.ui.common.PhBold

/** The live row's mark — the one place a face still appears in the thread. */
val AVATAR = 22.dp

/** Swallows taps a bubble's own controls did not take, so they never dismiss the composer. */
private fun Modifier.bubble() = pointerInput(Unit) { detectTapGestures { } }

/** How far the thread fades in below the deck. */
private val TOP_FADE = 24.dp

/** Rows asked for by id at a time — the most one read takes. */
private const val ID_BATCH = 50

/** The rows the thread's receipts name that nobody holds yet, one source at a time. */
private fun wantedRows(msgs: List<ChatMsg>, source: String, missing: (String) -> Boolean): List<String> =
    msgs.flatMap { m -> if (m is ChatMsg.Review) m.items else listOfNotNull(m as? ChatMsg.Confirm) }
        .filter { it.source == source && (source == "paisa" || it.fields.none { f -> f.key == "name" }) }
        .mapNotNull { it.rowId }
        .distinct()
        .filter(missing)

/** Within one speaker's run. */
val SAME_SPEAKER = 8.dp

private const val CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

/**
 * The local day a message was written. A server turn's id is a ULID, whose
 * first ten characters are its millisecond clock, and a card's id is its
 * turn's with an index after it — so the day is read off the id, not guessed.
 * A message made on the phone this session has no such id: it is today's.
 */
fun dayOf(id: String, today: String): String {
    if (id.length < 26) return today
    var ms = 0L
    for (c in id.take(10)) {
        val v = CROCKFORD.indexOf(c.uppercaseChar())
        if (v < 0) return today
        ms = ms * 32 + v
    }
    val day = java.time.Instant.ofEpochMilli(ms).atZone(java.time.ZoneId.systemDefault()).toLocalDate()
    return if (day.year in 2020..2100) day.toString() else today
}

/** A day's name between days: a small white pill, centred on the ground. */
@Composable
fun DaySeparator(label: String) {
    Box(Modifier.fillMaxWidth().padding(top = 6.dp, bottom = 18.dp), contentAlignment = Alignment.Center) {
        Text(
            label,
            style = T.sans.copy(fontSize = 11.5.sp, lineHeight = 14.sp, fontWeight = FontWeight.Medium, color = C.muted),
            modifier = Modifier.background(C.white, RoundedCornerShape(50)).padding(horizontal = 11.dp, vertical = 4.dp),
        )
    }
}

/** Where the speaker changes — the rhythm says who is talking before the type does. */
val NEW_SPEAKER = 20.dp

/**
 * The agent's side: the full width of the thread, no face and no gutter.
 * The serif already says who is speaking; a mascot beside every reply only
 * repeated it.
 */
@Composable
fun AgentRow(gap: Dp = NEW_SPEAKER, content: @Composable BoxScope.() -> Unit) {
    Box(Modifier.fillMaxWidth().padding(bottom = gap).bubble(), content = content)
}

/**
 * You on the right, unlabelled — a tint of the brand, never wider than most of
 * the row. A message that did not go is marked on itself, with Retry: it is
 * yours that failed, so no agent bubble speaks for it. One sent with a
 * context carries its label on a faint line above — what your words were
 * about; the bubble keeps only what you typed.
 */
@Composable
fun UserRow(text: String, gap: Dp = NEW_SPEAKER, failed: String? = null, context: String? = null, onRetry: () -> Unit = {}) {
    Column(Modifier.fillMaxWidth().padding(start = 56.dp, bottom = gap), horizontalAlignment = Alignment.End) {
        if (context != null) Row(
            Modifier.padding(end = 4.dp, bottom = 4.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            Glyph(Ph.arrowElbowDownRight, 12.dp, C.faint)
            Text(context, style = T.sans.copy(fontSize = 12.sp, lineHeight = 16.sp, color = C.faint), maxLines = 1, overflow = TextOverflow.Ellipsis)
        }
        UserBubble(text, Modifier.bubble().alpha(if (failed != null) 0.7f else 1f))
        if (failed != null) Row(Modifier.padding(top = 5.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(5.dp)) {
            Glyph(PhBold.x, 11.dp, C.red)
            Text("Not sent", style = T.sans.copy(fontSize = 12.sp, color = C.red))
            Text("·", style = T.sans.copy(fontSize = 12.sp, color = C.faint))
            Text(
                "Retry",
                style = T.sans.copy(fontSize = 13.sp, fontWeight = FontWeight.Medium, color = C.brand),
                modifier = Modifier.clip(RoundedCornerShape(6.dp)).tap(onClick = onRetry).padding(horizontal = 4.dp, vertical = 2.dp),
            )
        }
    }
}

/** Head of the conversation: the agent's voice, and your own most-repeated things as chips. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun Greeting(body: String, suggestions: List<Suggestion>) {
    // Nothing to say and nothing to offer: no row at all. An empty thread is empty.
    if (body.isBlank() && suggestions.isEmpty()) return
    AgentRow {
        Column {
            if (body.isNotBlank()) {
                Text(body, style = T.agentVoice, modifier = Modifier.padding(bottom = if (suggestions.isNotEmpty()) 12.dp else 0.dp))
            }
            if (suggestions.isNotEmpty()) {
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    suggestions.forEach { s -> Chip(s.name, s.tap, tag = s.tag) }
                }
            }
        }
    }
}

/**
 * The thread. Newest at the bottom; older pages arrive as you scroll back.
 * The agent's words are serif at full width, yours an ink pill — who is
 * speaking is typography, not a face. Port of `Conversation.tsx`.
 */
@Composable
fun Conversation(vm: SpicaViewModel, s: AppState, v: DerivedView, suggestions: List<Suggestion>, modifier: Modifier = Modifier) {
    val msgs = s.chat
    val list = rememberLazyListState()

    // All the rows the deck holds, and the ones fetched by id to fill in.
    val allTx = remember(s.tx, s.fixedTx, s.fetchedTx) {
        val deck = s.tx + s.fixedTx
        deck + s.fetchedTx.filter { f -> deck.none { it.id == f.id } }
    }
    val allMeals = remember(s.meals, s.fetchedMeals) { s.meals + s.fetchedMeals.filter { f -> s.meals.none { it.id == f.id } } }

    // A receipt reads its live row, and one from outside the deck — last
    // month's, an income, a lending, one deleted before this session — is
    // asked for by id, as a table's are; until it lands the card draws from
    // its payload. A card built by a delete asks too: its row may have been
    // put back since. A dish save names a dish, not a meal.
    val wantTx = remember(msgs, allTx) { wantedRows(msgs, "paisa") { id -> allTx.none { it.id == id } } }
    val wantMeals = remember(msgs, allMeals) { wantedRows(msgs, "diet") { id -> allMeals.none { it.id == id } } }
    LaunchedEffect(wantTx, wantMeals) {
        wantTx.chunked(ID_BATCH).forEach { vm.ensureRows("paisa", it) }
        wantMeals.chunked(ID_BATCH).forEach { vm.ensureRows("diet", it) }
    }

    val newest = msgs.lastOrNull()?.id
    // Pin to the newest message when one ARRIVES — keyed on its id, not the
    // count, so an older page landing above never yanks the reader down.
    LaunchedEffect(newest, s.phase) { if (msgs.isNotEmpty() || s.phase != Phase.Idle) list.animateScrollToItem(0) }

    // Near the top and there is more: fetch the previous page.
    val nearTop by remember { derivedStateOf { val info = list.layoutInfo; info.visibleItemsInfo.lastOrNull()?.index?.let { it >= info.totalItemsCount - 3 } ?: false } }
    LaunchedEffect(nearTop, s.chatHasMore, s.chatLoadingOlder) { if (nearTop && s.chatHasMore && !s.chatLoadingOlder) vm.loadOlderChat(false) }

    // The model is working on a turn. Speech is the phone's own sheet, so
    // there is no listening state to draw here.
    val liveRow = s.phase != Phase.Idle

    val links = paymentLinks(vm, s)
    val ra = RowActions(s.openRow, vm::toggleRow, vm::deleteRow, vm::editRow, links)
    val ca = ConfirmActions(
        onContext = vm::setContext, onConfirm = vm::confirmRow, onEdit = vm::editRow, onDelete = vm::deleteConfirmRow,
        onRestore = vm::restoreRow, onDeleteTask = vm::deleteTask,
        onToggleTodo = vm::toggleTodo, links = links,
    )
    // What a card may read besides its payload: the live rows.
    val world = remember(allTx, allMeals, s.todos, s.projects, s.habitLogs, s.exercises, s.dishes, s.pending, s.borrowed, s.repayments, s.weighIns, s.weighInsLoad, s.profile, s.todayIso, s.deletedRows, s.commitments) {
        CardWorld(
            allTx, allMeals, s.todos, s.projects, s.habitLogs, s.exercises, s.dishes, s.pending, s.weighIns, s.profile, s.todayIso, s.deletedRows,
            borrowed = s.borrowed, repayments = s.repayments, commitments = s.commitments?.items.orEmpty(),
            weighInsLoaded = s.weighInsLoad == Load.Loaded,
        )
    }
    val sa = SuggestActions(s.openRow, vm::toggleRow, vm::logSuggested, vm::saveSuggested, vm::dismissSuggested)

    LazyColumn(
        state = list,
        reverseLayout = true,
        contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 4.dp, bottom = 118.dp),
        modifier = modifier
            .fillMaxSize()
            // The thread fades out at its top edge instead of being sliced there:
            // a line cut flat under the deck read as the card lying on the text.
            .graphicsLayer { compositingStrategy = CompositingStrategy.Offscreen }
            .drawWithContent {
                drawContent()
                drawRect(
                    Brush.verticalGradient(0f to Color.Transparent, 1f to Color.Black, startY = 0f, endY = TOP_FADE.toPx()),
                    blendMode = BlendMode.DstIn,
                )
            }
            // Tapping empty space leaves compose mode.
            .pointerInput(Unit) { detectTapGestures { vm.setComposing(false) } },
    ) {
        if (liveRow) {
            item(key = "live") {
                // The one face left in the thread: it is only here while the agent works.
                Row(Modifier.padding(bottom = NEW_SPEAKER), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Mascot(AVATAR, if (s.phase == Phase.Thinking) MascotState.Thinking else MascotState.Saving)
                    // A status, not the agent's words: sans, as the web sets it.
                    if (s.phase == Phase.Thinking) Text("Thinking…", style = T.sans.copy(fontSize = 12.5.sp, color = C.muted))
                }
            }
        }
        val days = msgs.map { dayOf(it.id, s.todayIso) }
        for (i in msgs.indices.reversed()) {
            val m = msgs[i]
            // The gap below a message: tight when the same side speaks next.
            val next = msgs.getOrNull(i + 1)
            val gap = if (next != null && (next is ChatMsg.User) == (m is ChatMsg.User)) SAME_SPEAKER else NEW_SPEAKER
            item(key = m.id) {
                when (m) {
                    is ChatMsg.User -> UserRow(m.text, gap, m.failed, m.context?.label) { vm.retrySend(m.id) }
                    else -> AgentRow(gap) {
                        when (m) {
                            is ChatMsg.Agent -> AgentBubble(m)
                            is ChatMsg.Table -> TableCard(m, allTx, allMeals, s.deletedRows, ra, s.profile.proteinTarget, vm::ensureRows)
                            is ChatMsg.Flow -> FlowCard(s.limitInfo, s.salary, s.pending, s.todayIso)
                            is ChatMsg.Commitments -> CommitmentsCard(commitmentActions(vm), s.commitments)
                            is ChatMsg.Todos -> TodoCard(s.todos, m.scope, s.projects, s.todayIso, m.project, m.line, vm::toggleTodo)
                            is ChatMsg.Pantry -> PantryCard(m, s.pantry, s.dishes, s.todayIso)
                            is ChatMsg.Confirm -> ConfirmCard(m, liveFor(m, allTx, allMeals, s.deletedRows), world, ca)
                            is ChatMsg.Review -> ReviewCard(m.items, { liveFor(it, allTx, allMeals, s.deletedRows) }, world, ca)
                            is ChatMsg.Suggest -> {
                                // "Logged" is read from the ledger — a meal today by that name.
                                val logged = m.items.filter { it2 ->
                                    s.suggestLogged.containsKey(it2.ref) ||
                                        (it2.type == "dish" && allMeals.any { ml -> (ml.date ?: s.todayIso) == s.todayIso && !ml.deleted && ml.name == it2.name })
                                }.map { it.ref }.toSet()
                                SuggestCard(m, logged, s.pendingLogs, sa)
                            }
                            is ChatMsg.Ask -> {
                                val lede = m.pendingRowId?.let { id ->
                                    allTx.firstOrNull { it.id == id }?.let { "${Fmt.rupees(it.amt)} · ${it.name}" }
                                        ?: allMeals.firstOrNull { it.id == id }?.let { "${it.name} · ${Fmt.num(it.p)} g protein" }
                                }
                                AskCard(m, lede, vm::ask)
                            }
                            is ChatMsg.User -> Unit
                        }
                    }
                }
            }
            // Where a day begins, its name above its first message — the thread
            // reads as days, not as one endless page.
            if (i == 0 || days[i] != days[i - 1]) {
                item(key = "day-${days[i]}-$i") { DaySeparator(dayWord(days[i], s.todayIso)) }
            }
        }
        item(key = "greeting") { Greeting(v.greetBody, suggestions) }
        if (s.chatLoadingOlder || (!s.chatHasMore && s.chatCleared > 0)) {
            item(key = "older") {
                // Plain words on the ground, not another pill: the day's name
                // just below is the one chip at the top of the thread.
                Row(Modifier.fillMaxWidth().padding(top = 4.dp, bottom = 14.dp), horizontalArrangement = Arrangement.Center, verticalAlignment = Alignment.CenterVertically) {
                    val small = T.sans.copy(fontSize = 12.5.sp, lineHeight = 16.sp, color = C.faint)
                    if (s.chatLoadingOlder) Text("Loading older…", style = small)
                    else {
                        Text("Earlier messages are hidden · ", style = small)
                        Text("Show", style = small.copy(color = C.brand, fontWeight = FontWeight.Medium), modifier = Modifier.tap { vm.loadOlderChat(true) })
                    }
                }
            }
        }
    }
}
