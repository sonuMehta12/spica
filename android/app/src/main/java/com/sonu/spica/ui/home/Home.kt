package com.sonu.spica.ui.home

import android.content.ActivityNotFoundException
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.snapshotFlow
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LifecycleEventEffect
import androidx.health.connect.client.PermissionController
import com.sonu.spica.data.Health
import com.sonu.spica.state.AppState
import com.sonu.spica.state.SpicaViewModel
import com.sonu.spica.ui.common.rememberListen
import com.sonu.spica.ui.chat.Conversation
import com.sonu.spica.ui.common.LocalOnTop
import com.sonu.spica.ui.common.layerFocus
import com.sonu.spica.ui.theme.C
import kotlinx.coroutines.launch

/**
 * Agent hi app hai, on two pages: Home on the left — today's tasks, Money,
 * Diet, Activity and Habits at a glance — and the conversation on the right. The pill in the bar
 * and a swipe both switch; the composer sits at the foot of both, and
 * anything that means talking moves to Chat.
 */
@Composable
fun Home(vm: SpicaViewModel, s: AppState, onSignedOut: () -> Unit) {
    val v = remember(s) { vm.view(s) }
    val suggestions = remember(s.usedSuggs, v.canLog, s.tx, s.meals, s.todayIso) { vm.suggestions(s, v) }
    LaunchedEffect(v.salaryLineShown) { if (v.salaryLineShown) vm.markGreeted() }
    LifecycleEventEffect(Lifecycle.Event.ON_RESUME) { vm.resumed() }

    // Home first, always — the first run's questions were asked before Home was drawn.
    val pager = rememberPagerState(initialPage = HOME_PAGE) { 2 }
    val scope = rememberCoroutineScope()
    val go: (Int) -> Unit = { page -> scope.launch { pager.animateScrollToPage(page) } }

    val atRoot = s.stack.isEmpty()

    // Talking happens in Chat: the composer's focus, the tray, a Change or the
    // mic on Home all slide there first, so the answer lands where you look.
    // Not under a page: a page's own composer never moves the pager it hides.
    LaunchedEffect(s.composing, atRoot) {
        if (s.composing && atRoot && pager.targetPage != CHAT_PAGE) pager.animateScrollToPage(CHAT_PAGE)
    }
    // Arriving on Home lets the keyboard and the tray go.
    LaunchedEffect(pager) { snapshotFlow { pager.settledPage }.collect { if (it == HOME_PAGE) vm.leaveChat() } }
    // A nudge's *Ask about this*, or a question from a page, lands in Chat. The
    // request is spent before the slide, which runs in the screen's scope, so
    // a rotation mid-slide never replays it.
    LaunchedEffect(s.toChat) {
        if (s.toChat > 0) {
            vm.chatShown()
            go(CHAT_PAGE)
        }
    }

    // Back walks out the way you came in. Composed before every page, so a
    // page's own steps (an open editor, a form — each `enabled && top`) and
    // the windows (keyboard, popover, dialog, sheet) take it first. Then
    // vm.back(): the composer's edit, its context, the top screen, Chat's
    // tray — in that order. Then Chat back to Home. On Home at rest nothing
    // is enabled, so the system's back-to-home takes it.
    BackHandler(enabled = pager.currentPage == CHAT_PAGE) { go(HOME_PAGE) }
    BackHandler(enabled = !atRoot || s.editing != null || s.context != null || s.openRow != null) { vm.back() }

    // What the recogniser heard lands in the composer, never sent on its own.
    val listen = rememberListen("Say what you spent, ate, or need to do", { said -> said?.let(vm::heard) }) {
        vm.notify("Voice input isn't available on this phone.")
    }

    // Health Connect's own permission sheet; whatever comes back, read again.
    val health = rememberLauncherForActivityResult(PermissionController.createRequestPermissionResultContract()) { vm.loadActivity() }
    val connectHealth: () -> Unit = {
        try {
            health.launch(Health.PERMISSIONS)
        } catch (_: ActivityNotFoundException) {
            vm.notify("Health Connect isn't available on this phone.")
        }
    }

    val composerActions = remember(vm, listen) {
        ComposerActions(
            onType = vm::setTyped, onSend = vm::send, onMic = listen, onMedia = vm::pickMedia,
            onComposing = vm::setComposing, onCancelEdit = vm::cancelEdit,
            onClearContext = vm::clearContext,
        )
    }

    // One ground under both pages — the tint Home's cards and the thread's
    // float on — so a swipe moves the page, never the light behind it.
    val ground = C.lineSoft

    Box(Modifier.fillMaxSize().background(ground).imePadding()) {
        // Under a screen, the pager keeps its place but is out of reach: no
        // screen reader, no focus, and no back for anything open in it.
        CompositionLocalProvider(LocalOnTop provides atRoot) {
            Column(Modifier.fillMaxSize().statusBarsPadding().then(layerFocus(atRoot)).then(if (atRoot) Modifier else Modifier.clearAndSetSemantics {})) {
                TopBar(pager, go, vm::openMenu, vm::clearConversation, s.chat.size > 1, s.chatClearing, vm::openNudges, s.bellDot)
                // Both pages stay composed, so the thread keeps its place while you look at Home.
                HorizontalPager(pager, Modifier.weight(1f), beyondViewportPageCount = 1) { page ->
                    // The page beside this one is drawn too, but Back belongs to the one you see:
                    // a receipt's open choices in Chat never keep Home from leaving.
                    CompositionLocalProvider(LocalOnTop provides (atRoot && pager.currentPage == page)) {
                        if (page == HOME_PAGE) HomePage(vm, s, v, onChat = { go(CHAT_PAGE) }, onConnectHealth = connectHealth)
                        else Conversation(vm, s, v, suggestions, Modifier.fillMaxSize())
                    }
                }
            }
        }

        if (atRoot) {
            Composer(
                typed = s.typed, focusKey = s.composeFocus, composing = s.composing, canLog = v.canLog, hint = null,
                editing = s.editing?.label,
                a = composerActions, modifier = Modifier.align(Alignment.BottomCenter), context = s.context, ground = ground,
                // Back from a screen, or a nudge's Ask: the cursor is where it was meant to be.
                focusOnMount = s.composing,
            )
        }

        // The menu, every page, each level inside one: the back stack, in order.
        Overlays(vm, s, v, composerActions, home = if (pager.currentPage == CHAT_PAGE) "Chat" else "Home") { vm.signOut(onSignedOut) }

        // Receipts go over every page: a refusal must be seen wherever it came from.
        ToastView(s.toast, vm::dismissToast, Modifier.align(Alignment.BottomCenter).navigationBarsPadding().padding(bottom = 92.dp))
    }
}
