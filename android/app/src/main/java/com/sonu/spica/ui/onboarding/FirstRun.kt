package com.sonu.spica.ui.onboarding

import android.os.SystemClock
import androidx.activity.compose.BackHandler
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
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawWithContent
import androidx.compose.ui.graphics.BlendMode
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.CompositingStrategy
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.toggleableState
import androidx.compose.ui.state.ToggleableState
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.sonu.spica.state.AppState
import com.sonu.spica.state.FirstRunLine
import com.sonu.spica.state.FirstRunStep
import com.sonu.spica.state.Load
import com.sonu.spica.state.Pick
import com.sonu.spica.state.SpicaViewModel
import com.sonu.spica.logic.YourStart
import com.sonu.spica.ui.chat.AVATAR
import com.sonu.spica.ui.chat.AgentRow
import com.sonu.spica.ui.chat.CardWorld
import com.sonu.spica.ui.chat.ConfirmActions
import com.sonu.spica.ui.chat.ConfirmCard
import com.sonu.spica.ui.chat.FirstRunActions
import com.sonu.spica.ui.chat.NEW_SPEAKER
import com.sonu.spica.ui.chat.SAME_SPEAKER
import com.sonu.spica.ui.chat.UserRow
import com.sonu.spica.ui.chat.firstRunCanUndo
import com.sonu.spica.ui.chat.firstRunContext
import com.sonu.spica.ui.chat.liveFor
import com.sonu.spica.ui.common.Chip
import com.sonu.spica.ui.common.Coin
import com.sonu.spica.ui.common.Dot
import com.sonu.spica.ui.common.Glyph
import com.sonu.spica.ui.common.habitGlyph
import com.sonu.spica.ui.common.Ground
import com.sonu.spica.ui.common.Logo
import com.sonu.spica.ui.common.Mascot
import com.sonu.spica.ui.common.MascotState
import com.sonu.spica.ui.common.Ph
import com.sonu.spica.ui.common.RoundIcon
import com.sonu.spica.ui.common.PhBold
import com.sonu.spica.ui.common.divider
import com.sonu.spica.ui.common.fadeUp
import com.sonu.spica.ui.common.panel
import com.sonu.spica.ui.common.rememberListen
import com.sonu.spica.ui.common.tap
import com.sonu.spica.ui.home.Composer
import com.sonu.spica.ui.home.ComposerActions
import com.sonu.spica.ui.home.ToastView
import com.sonu.spica.ui.theme.C
import com.sonu.spica.ui.theme.T

/*
 * The first run's screens 2–4, between sign-in and Home — spec/done/onboarding-goals.md.
 * Built from the phone's own kit: the ground, white panels, coins, and the
 * chat's own parts and confirm cards for the questions.
 */

/** Screens 2–4, whichever the person is on. Home is not composed underneath. */
@Composable
fun FirstRun(vm: SpicaViewModel, s: AppState) {
    Box(Modifier.fillMaxSize().background(Ground)) {
        when (s.firstRun.step) {
            FirstRunStep.Choose -> TakeControl(vm, s)
            FirstRunStep.Ask -> AboutYou(vm, s)
            FirstRunStep.Ready -> AllSet(vm, s)
        }
        // A refusal is seen wherever it came from.
        ToastView(s.toast, vm::dismissToast, Modifier.align(Alignment.BottomCenter).navigationBarsPadding().padding(bottom = 92.dp))
    }
}

/* ─── the pieces ──────────────────────────────────────────────────────── */

/**
 * The logo top left; *Skip* top right where the screen has one. Screens 3 and
 * 4 put ← before the logo: the same call as the system's back there, so the
 * arrow and the gesture are one path.
 */
@Composable
private fun TopBar(onSkip: (() -> Unit)?, modifier: Modifier = Modifier, onBack: (() -> Unit)? = null) {
    Row(modifier.fillMaxWidth().height(44.dp), verticalAlignment = Alignment.CenterVertically) {
        if (onBack != null) {
            RoundIcon(Ph.arrowLeft, onBack, "Back")
            Spacer(Modifier.width(12.dp))
        }
        Logo()
        Spacer(Modifier.weight(1f))
        if (onSkip != null) {
            Text(
                "Skip",
                style = T.sans.copy(fontSize = 15.sp, lineHeight = 19.sp, color = C.muted),
                modifier = Modifier.clip(RoundedCornerShape(8.dp)).tap(onClick = onSkip).padding(horizontal = 6.dp, vertical = 12.dp),
            )
        }
    }
}

/** The one button a screen is for: a full-width Jamun pill. */
@Composable
private fun PrimaryButton(label: String, onClick: () -> Unit, modifier: Modifier = Modifier, enabled: Boolean = true) {
    val pill = RoundedCornerShape(50)
    Box(
        modifier.fillMaxWidth().height(52.dp).alpha(if (enabled) 1f else 0.6f).clip(pill).background(C.brand).tap(enabled = enabled, onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Text(label, style = T.sans.copy(fontSize = 16.sp, lineHeight = 20.sp, fontWeight = FontWeight.Medium, color = C.white))
    }
}

/** A screen's opening, in the agent's voice: the large line and the one under it. */
@Composable
private fun Opening(title: String, line: String, modifier: Modifier = Modifier) {
    Column(modifier.padding(horizontal = 4.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(title, style = T.display.copy(fontSize = 30.sp, lineHeight = 36.sp, letterSpacing = (-0.3).sp))
        Text(line, style = T.agentVoice.copy(fontSize = 17.sp, lineHeight = 25.sp))
    }
}

/* ─── 2 · Take control ────────────────────────────────────────────────── */

/** Each pick's coin: its domain's ink on its tint. */
private val Pick.coin: Triple<ImageVector, Color, Color>
    get() = when (this) {
        Pick.Money -> Triple(Ph.wallet, C.paisaInk, C.paisaTint)
        Pick.Food -> Triple(Ph.bowlFood, C.dietInk, C.dietTint)
        Pick.Health -> Triple(Ph.heartbeat, C.dietInk, C.dietTint)
        Pick.Habits -> Triple(Ph.repeat, C.dietInk, C.dietTint)
        Pick.Time -> Triple(Ph.clock, C.workInk, C.workTint)
    }

/**
 * What do you want to take control of? Five picks, none chosen for them.
 * Continue goes to the questions; with nothing picked it reads *Skip for
 * now* and goes Home. Back leaves the app, as on the door.
 */
@Composable
private fun TakeControl(vm: SpicaViewModel, s: AppState) {
    val f = s.firstRun
    Column(Modifier.fillMaxSize().safeDrawingPadding().padding(start = 16.dp, end = 16.dp, top = 18.dp, bottom = 24.dp)) {
        TopBar(vm::skipFirstRun, Modifier.padding(horizontal = 4.dp))
        Column(Modifier.weight(1f).verticalScroll(rememberScrollState())) {
            Opening("Hi, I’m Spica.", "What do you want to take control of? I’ll help you get there.", Modifier.padding(top = 34.dp))
            Column(Modifier.padding(top = 24.dp, bottom = 16.dp).fillMaxWidth().panel()) {
                Pick.entries.forEachIndexed { i, p -> PickRow(p, p in f.picks, first = i == 0) { vm.togglePick(p) } }
            }
        }
        PrimaryButton(if (f.picks.isEmpty()) "Skip for now" else "Continue", vm::choosePicks, enabled = !f.leaving)
    }
}

@Composable
private fun PickRow(p: Pick, on: Boolean, first: Boolean, onToggle: () -> Unit) {
    val (icon, ink, tint) = p.coin
    Row(
        Modifier
            .fillMaxWidth()
            .then(if (first) Modifier else Modifier.divider())
            .semantics(mergeDescendants = true) {
                role = Role.Checkbox
                toggleableState = ToggleableState(on)
            }
            .tap(onClick = onToggle)
            .heightIn(min = 68.dp)
            .padding(horizontal = 16.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Coin(icon, ink, tint, 40.dp)
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(p.title, style = T.sans.copy(fontSize = 16.sp, lineHeight = 21.sp, fontWeight = FontWeight.Medium))
            Text(p.line, style = T.sans.copy(fontSize = 13.5.sp, lineHeight = 18.sp, color = C.muted))
        }
        // Picked is a selection: Jamun, with a tick. Not picked, an empty ring.
        Box(
            Modifier
                .size(24.dp)
                .clip(CircleShape)
                .background(if (on) C.brand else C.white)
                .then(if (on) Modifier else Modifier.border(1.5.dp, C.border, CircleShape)),
            contentAlignment = Alignment.Center,
        ) { if (on) Glyph(PhBold.check, 13.dp, C.white) }
    }
}

/* ─── 3 · A little about you ──────────────────────────────────────────── */

/** How far the thread fades in under the logo. */
private val TOP_FADE = 28.dp

/** One row of the thread as drawn, and whether the person said it — the rhythm says who is talking. */
private class ThreadItem(val key: String, val yours: Boolean, val draw: @Composable (gap: Dp) -> Unit)

/**
 * The questions, in the chat's own parts: the agent's serif, your tint
 * pill, the input bar, and every write as the app's confirm card with Edit
 * and Undo. Nothing here goes into the chat thread.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun AboutYou(vm: SpicaViewModel, s: AppState) {
    val f = s.firstRun
    BackHandler { vm.firstRunBack() }
    val listen = rememberListen("Say your answer", vm::firstRunHeard) {
        vm.firstRunHeard(null)
        vm.notify("Voice input isn't available on this phone.")
    }
    val actions = remember(vm, listen) {
        ComposerActions(
            onType = vm::setFirstRunTyped, onSend = vm::sendFirstRunAnswer,
            onMic = {
                vm.firstRunListening()
                listen()
            },
            onMedia = {}, onComposing = {}, onCancelEdit = {}, onClearContext = vm::clearFirstRunContext,
        )
    }
    // What a card may read besides its payload: the live rows.
    val world = remember(s.tx, s.meals, s.todos, s.projects, s.habitLogs, s.exercises, s.dishes, s.pending, s.weighIns, s.weighInsLoad, s.profile, s.todayIso, s.deletedRows) {
        CardWorld(
            s.tx, s.meals, s.todos, s.projects, s.habitLogs, s.exercises, s.dishes, s.pending, s.weighIns, s.profile, s.todayIso, s.deletedRows,
            weighInsLoaded = s.weighInsLoad == Load.Loaded,
        )
    }
    val ca = remember(vm, f.thread) {
        ConfirmActions(
            onContext = {}, onConfirm = {}, onEdit = { _, _, _ -> }, onDelete = {}, onRestore = {}, onDeleteTask = {}, onToggleTodo = {},
            firstRun = FirstRunActions(
                onEdit = { msg ->
                    val q = f.thread.firstNotNullOfOrNull { (it as? FirstRunLine.Card)?.takeIf { c -> c.msg.id == msg.id }?.question }
                    if (q != null) vm.editFirstRunCard(q, firstRunContext(msg))
                },
                onUndo = vm::undoFirstRunCard,
                canUndo = { msg ->
                    f.thread.any { it is FirstRunLine.Card && it.msg.id == msg.id && firstRunCanUndo(msg, it.before.displayName) && !f.superseded(it) }
                },
            ),
        )
    }

    val rows = buildList {
        f.thread.forEach { line ->
            when (line) {
                is FirstRunLine.Agent -> add(ThreadItem(line.id, false) { gap -> AgentRow(gap) { Text(line.text, style = T.agentVoice, modifier = Modifier.fadeUp()) } })
                is FirstRunLine.Said -> add(ThreadItem(line.id, true) { gap -> UserRow(line.text, gap, context = line.context) })
                is FirstRunLine.Card -> add(ThreadItem(line.id, false) { gap -> AgentRow(gap) { ConfirmCard(line.msg, liveFor(line.msg, s.tx, s.meals, s.deletedRows), world, ca) } })
            }
        }
        if (f.busy) add(ThreadItem("thinking", false) { gap ->
            // The mark is only here while the agent works.
            Row(Modifier.padding(bottom = gap), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Mascot(AVATAR, MascotState.Thinking)
                // A status, not the agent's words: sans, as the web sets it.
                Text("Thinking…", style = T.sans.copy(fontSize = 12.5.sp, color = C.muted))
            }
        })
        f.problem?.let { p -> add(ThreadItem("problem", false) { gap -> AgentRow(gap) { Text(p, style = T.agentVoice) } }) }
        if (f.finished && !f.busy && !f.capped) {
            val last = if (f.gaveAny || f.asked.isEmpty()) "That’s everything I need. Here’s your start." else "You can tell me any of this later."
            add(ThreadItem("done", false) { gap -> AgentRow(gap) { Text(last, style = T.agentVoice, modifier = Modifier.fadeUp()) } })
        }
    }

    val list = rememberLazyListState()
    val newest = rows.lastOrNull()?.key
    LaunchedEffect(newest, rows.size) { if (rows.isNotEmpty()) list.animateScrollToItem(0) }

    val asking = !f.finished || f.context != null || f.busy
    Column(Modifier.fillMaxSize().imePadding()) {
        TopBar(vm::skipFirstRunQuestions, Modifier.statusBarsPadding().padding(start = 20.dp, end = 14.dp, top = 18.dp), onBack = vm::firstRunBack)
        LazyColumn(
            state = list,
            reverseLayout = true,
            contentPadding = PaddingValues(start = 20.dp, end = 20.dp, top = TOP_FADE, bottom = 12.dp),
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth()
                // The thread fades out under the logo instead of being sliced there.
                .graphicsLayer { compositingStrategy = CompositingStrategy.Offscreen }
                .drawWithContent {
                    drawContent()
                    drawRect(Brush.verticalGradient(0f to Color.Transparent, 1f to Color.Black, startY = 0f, endY = TOP_FADE.toPx()), blendMode = BlendMode.DstIn)
                },
        ) {
            for (i in rows.indices.reversed()) {
                val r = rows[i]
                val next = rows.getOrNull(i + 1)
                val gap = if (next != null && next.yours == r.yours) SAME_SPEAKER else NEW_SPEAKER
                item(key = r.key) { r.draw(gap) }
            }
        }
        if (asking) {
            // A chip adds its word to the bar; the question's own, and none while an Edit is on it.
            val chips = if (f.context == null) f.at?.chips.orEmpty() else emptyList()
            if (chips.isNotEmpty()) {
                FlowRow(
                    Modifier.fillMaxWidth().padding(start = 18.dp, end = 18.dp, top = 4.dp),
                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                    verticalArrangement = Arrangement.spacedBy(6.dp),
                ) { chips.forEach { c -> Chip(c, { vm.firstRunChip(c) }) } }
            }
            Composer(
                typed = f.typed, focusKey = f.focus, composing = true, canLog = true,
                hint = if (f.listening) "Listening…" else "Say it, or type it…", editing = null,
                a = actions, context = f.context, ground = Ground, media = false, waiting = f.busy,
            )
        } else {
            PrimaryButton("Continue", vm::openAllSet, Modifier.navigationBarsPadding().padding(start = 16.dp, end = 16.dp, top = 8.dp, bottom = 24.dp))
        }
    }
}

/* ─── 4 · You're all set ──────────────────────────────────────────────── */

/** Each goal's mode coin: the body and habits in Diet's tint — a habit with its own glyph when it has one — money in Paisa's. */
private val YourStart.Goal.coin: Triple<ImageVector, Color, Color>
    get() = when (kind) {
        YourStart.GoalKind.Weight, YourStart.GoalKind.Words -> Triple(Ph.heartbeat, C.dietInk, C.dietTint)
        YourStart.GoalKind.Money -> Triple(Ph.wallet, C.paisaInk, C.paisaTint)
        YourStart.GoalKind.Habit -> Triple(habitGlyph(title) ?: Ph.repeat, C.dietInk, C.dietTint)
    }

/**
 * How long a tap is ignored once screen 4 is up. Get started sits where
 * screen 3's Continue was, and a double tap on that would otherwise finish
 * past the summary unseen — the input protection Chrome gives a permission
 * prompt, at its 500 ms.
 */
private const val SETTLE_MS = 500L

/**
 * Where they are starting, and where they are headed — read from the rows
 * on the way in, never the cards. A card with nothing in it is not drawn. No
 * calories, no protein, no daily targets: the goals are the person's, a
 * daily target is the app's. Get started sends the flag and opens Home.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun AllSet(vm: SpicaViewModel, s: AppState) {
    val f = s.firstRun
    val shownAt = remember { SystemClock.uptimeMillis() }
    BackHandler { vm.firstRunBack() }
    val latest = s.weighIns.firstOrNull()
    val about = remember(s.profile, latest, s.memories, s.todayIso) { YourStart.about(s.profile, latest, s.memories, s.todayIso) }
    val goals = remember(s.profile, latest, s.memories, s.habits) { YourStart.goals(s.profile, latest, s.memories, s.habits) }
    val name = s.profile.displayName.trim()
    Column(Modifier.fillMaxSize().safeDrawingPadding().padding(start = 16.dp, end = 16.dp, top = 18.dp, bottom = 24.dp)) {
        TopBar(null, Modifier.padding(horizontal = 4.dp), onBack = vm::firstRunBack)
        Column(Modifier.weight(1f).verticalScroll(rememberScrollState())) {
            Opening(
                if (name.isNotEmpty()) "You’re all set, $name." else "You’re all set.",
                if (about.isEmpty() && goals.isEmpty()) "You can tell me any of this later." else "Here’s where you’re starting, and where you’re headed.",
                Modifier.padding(top = 26.dp),
            )
            if (about.isNotEmpty()) StartCard("About you", vm::editFromAllSet, Modifier.padding(top = 20.dp)) {
                FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    about.forEach { FactTag(it) }
                }
            }
            if (goals.isNotEmpty()) StartCard("Your goals", vm::editFromAllSet, Modifier.padding(top = 12.dp)) {
                goals.forEachIndexed { i, g -> GoalRow(g, first = i == 0) }
            }
            Spacer(Modifier.height(16.dp))
        }
        PrimaryButton(
            "Get started",
            { if (SystemClock.uptimeMillis() - shownAt >= SETTLE_MS) vm.getStarted() },
            enabled = !f.leaving,
        )
    }
}

/** A panel with its name and an Edit that goes back to the thread, where each write has its own. */
@Composable
private fun StartCard(title: String, onEdit: () -> Unit, modifier: Modifier = Modifier, content: @Composable () -> Unit) {
    Column(modifier.fillMaxWidth().panel().padding(start = 16.dp, end = 16.dp, top = 8.dp, bottom = 14.dp)) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text(title, style = T.cardHeading, modifier = Modifier.weight(1f))
            Text(
                "Edit",
                style = T.sans.copy(fontSize = 12.5.sp, fontWeight = FontWeight.Medium, color = C.brand),
                modifier = Modifier.clip(RoundedCornerShape(6.dp)).tap(onClick = onEdit).padding(start = 12.dp, top = 6.dp, bottom = 6.dp),
            )
        }
        // A Column, not a Box: Your goals is several rows, and a Box stacks them on one another.
        Column(Modifier.padding(top = 6.dp)) { content() }
    }
}

@Composable
private fun FactTag(fact: YourStart.Fact) {
    Row(
        Modifier.background(C.lineSoft, RoundedCornerShape(50)).padding(horizontal = 11.dp, vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (fact.estimated) Dot()
        Text(fact.text, style = T.sans.copy(fontSize = 13.5.sp, lineHeight = 18.sp))
    }
}

@Composable
private fun GoalRow(g: YourStart.Goal, first: Boolean) {
    val (icon, ink, tint) = g.coin
    Row(
        Modifier.fillMaxWidth().then(if (first) Modifier else Modifier.divider()).padding(vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Coin(icon, ink, tint, 40.dp)
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                if (g.titleEstimated) Dot()
                Text(g.title, style = T.sans.copy(fontSize = 16.sp, lineHeight = 21.sp, fontWeight = FontWeight.Medium))
            }
            if (g.sub.isNotEmpty()) Row(verticalAlignment = Alignment.CenterVertically) {
                g.sub.forEach { part ->
                    if (part.estimated) Dot()
                    Text(part.text, style = T.sans.copy(fontSize = 13.5.sp, lineHeight = 18.sp, color = C.muted))
                }
            }
        }
    }
}
