package com.sonu.spica.ui.home

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.key
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.paneTitle
import androidx.compose.ui.semantics.semantics
import com.sonu.spica.state.AppState
import com.sonu.spica.state.DerivedView
import com.sonu.spica.state.Screen
import com.sonu.spica.state.SpicaViewModel
import com.sonu.spica.ui.common.Back
import com.sonu.spica.ui.common.Ground
import com.sonu.spica.ui.common.LocalOnTop
import com.sonu.spica.ui.common.layerFocus
import com.sonu.spica.ui.commitments.CommitmentSheet
import com.sonu.spica.ui.commitments.CommitmentsPageView
import com.sonu.spica.ui.data.DataPage
import com.sonu.spica.ui.nudges.NudgeLanding
import com.sonu.spica.ui.nudges.NudgesPage
import com.sonu.spica.ui.nudges.titleOf
import com.sonu.spica.ui.profile.ProfilePage
import com.sonu.spica.ui.profile.title
import com.sonu.spica.ui.report.ReportPage

/** What a screen is called — on its ←, from the screen above it, and to a screen reader as it opens. */
val Screen.title: String
    get() = when (this) {
        Screen.Menu -> "Menu"
        Screen.Report -> "Report"
        is Screen.Data -> section?.label ?: "Your data"
        is Screen.Profile -> group?.title ?: "Profile"
        Screen.Commitments -> "Commitments"
        Screen.Nudges -> "Nudges"
        is Screen.Nudge -> titleOf(page.landing)
    }

/**
 * Everything over Home, drawn from the back stack in order — the menu, the
 * pages, each level inside a page — each entry its own composition. The ones
 * under the top stay composed, so going back finds them as they were left:
 * the same scroll, the same tab, no entrance played again. They are hidden
 * from screen readers, take no back and no focus, and the top's ground takes
 * every tap.
 * Each page's ← names the entry under it, or Home or Chat for the first.
 *
 * The Report and Profile carry the composer, on top only. A question sent
 * from one leaves every screen for Chat, where the answer lands; a correction
 * stays on the page, where its row changes in place. Your data has none — as
 * on the web.
 */
@Composable
fun Overlays(
    vm: SpicaViewModel, s: AppState, v: DerivedView, composer: ComposerActions,
    /** The pager page under the stack, by name: where the first entry's ← goes. */
    home: String,
    onSignOut: () -> Unit,
) {
    @Composable
    fun bar() = Composer(
        typed = s.typed, focusKey = s.composeFocus, composing = s.composing, canLog = v.canLog, hint = null,
        editing = s.editing?.label,
        a = ComposerActions(
            composer.onType, { if (vm.send() == SpicaViewModel.Sent.Ask) vm.goChat() }, composer.onMic, composer.onMedia, composer.onComposing,
            composer.onCancelEdit,
            composer.onClearContext,
        ),
        context = s.context,
        // The pages stand on the shared ground; the composer's fade must be that, not white.
        ground = Ground,
        // A photo is read in Chat, and Chat is under the page: here the button would answer out of sight.
        media = false,
    )
    s.stack.forEachIndexed { i, sc ->
        key(i, sc) {
            val top = i == s.stack.lastIndex
            // Under the top, an entry draws from the state it was left with:
            // a keystroke above it does not redraw it. On top again, it is live.
            val held = remember(top) { s to v }
            val (st, sv) = if (top) s to v else held
            val to = if (i == 0) home else s.stack[i - 1].title
            val back = remember(to) { Back(to) { vm.pop(sc) } }
            val withBar: (@Composable () -> Unit)? = if (top) ({ bar() }) else null
            CompositionLocalProvider(LocalOnTop provides top) {
                Box(
                    Modifier
                        .fillMaxSize()
                        // Under the top: no focus, so a field left open there drops the keyboard and takes no keys.
                        .then(layerFocus(top))
                        .then(if (top) Modifier.semantics { paneTitle = sc.title } else Modifier.clearAndSetSemantics {}),
                ) {
                    when (sc) {
                        Screen.Menu -> Drawer(st.profile.displayName, st.profile.avatarUrl, back.onClick, vm::openMenuRow, onSignOut)
                        Screen.Report -> ReportPage(vm, st, back, withBar)
                        is Screen.Data -> DataPage(vm, st, sc.section, back)
                        is Screen.Profile -> ProfilePage(vm, st, sc.group, back, withBar)
                        Screen.Commitments -> CommitmentsPageView(vm, st, back)
                        Screen.Nudges -> NudgesPage(vm, st, back)
                        is Screen.Nudge -> NudgeLanding(vm, st, sv, sc.page, back)
                    }
                }
            }
        }
    }
    // The sheet is a window of its own, so a payment's tray can open it from anywhere; it takes its own back.
    s.commitmentSheet?.let { CommitmentSheet(vm, s, it) }
}
