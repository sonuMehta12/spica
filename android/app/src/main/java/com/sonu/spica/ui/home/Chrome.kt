package com.sonu.spica.ui.home

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.CubicBezierEasing
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.pager.PagerState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.semantics.disabled
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil3.compose.AsyncImage
import com.sonu.spica.state.Toast
import com.sonu.spica.ui.chat.bottomRule
import com.sonu.spica.ui.common.ActionPill
import com.sonu.spica.ui.common.BackStep
import com.sonu.spica.ui.common.Coin
import com.sonu.spica.ui.common.Ground
import com.sonu.spica.ui.common.LocalOnTop
import com.sonu.spica.ui.common.PillKind
import com.sonu.spica.ui.common.Mascot
import com.sonu.spica.ui.common.PagePill
import com.sonu.spica.ui.common.RoundIcon
import com.sonu.spica.ui.common.Tag
import com.sonu.spica.ui.common.divider
import com.sonu.spica.ui.common.panel
import com.sonu.spica.ui.common.MascotState
import com.sonu.spica.ui.common.Spinner
import com.sonu.spica.ui.common.fadeUp
import com.sonu.spica.ui.common.plainTap
import com.sonu.spica.ui.common.tap
import com.sonu.spica.ui.theme.C
import com.sonu.spica.ui.theme.S
import com.sonu.spica.ui.theme.T
import com.sonu.spica.ui.common.Glyph
import com.sonu.spica.ui.common.Ph
import com.sonu.spica.ui.common.PhBold

/** The two pages, left to right. */
const val HOME_PAGE = 0
const val CHAT_PAGE = 1
private val PAGES = listOf("Home", "Chat")

/** A round button in the bar. */
private val DISC = 40.dp

/**
 * Each side of the bar: one fixed width, the same on both sides and on both
 * pages — room for the clear button beside the bell — so the pill stays
 * centred whatever the right side holds.
 */
private val SLOT = DISC * 2 + 4.dp

/**
 * The bar over both pages: the menu, the Home | Chat pill in the middle, and
 * the bell on the right — with, on Chat, the clear button before it. Clear
 * spins and stops taking presses while the fold runs. The date that headed
 * the old bar now heads Home.
 */
@Composable
fun TopBar(
    pager: PagerState, onPick: (Int) -> Unit, onMenu: () -> Unit, onClear: () -> Unit, canClear: Boolean, clearing: Boolean,
    onBell: () -> Unit, bellDot: Boolean,
) {
    Row(Modifier.fillMaxWidth().padding(horizontal = 10.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
        Row(Modifier.width(SLOT)) {
            BarDisc(onMenu) { Glyph(Ph.list, 22.dp, C.ink, label = "Menu") }
        }
        Box(Modifier.weight(1f), contentAlignment = Alignment.Center) { PagePill(pager, PAGES, onPick) }
        Row(Modifier.width(SLOT), horizontalArrangement = Arrangement.spacedBy(4.dp, Alignment.End), verticalAlignment = Alignment.CenterVertically) {
            if (pager.currentPage == CHAT_PAGE && (canClear || clearing)) {
                BarDisc(onClear, enabled = !clearing) {
                    if (clearing) Spinner() else Glyph(Ph.broom, 21.dp, C.muted, label = "Clear conversation")
                }
            }
            Bell(bellDot, onBell)
        }
    }
}

/** A white disc floating on the ground, as the pages' close is. Disabled, it stops taking presses; what it holds says why. */
@Composable
private fun BarDisc(onClick: () -> Unit, modifier: Modifier = Modifier, enabled: Boolean = true, content: @Composable () -> Unit) {
    Box(
        modifier.size(DISC).then(S.bubble(CircleShape)).clip(CircleShape).background(C.white).tap(enabled = enabled, onClick = onClick),
        contentAlignment = Alignment.Center,
    ) { content() }
}

/**
 * The caret where the bell was: today at a glance — the key numbers and the
 * nudges — slides in from the right, the way it points. A Jamun dot when a
 * nudge was written since it was last opened — no count and no red: a number
 * to clear is a chore. `spec/home-day-rail.md`.
 */
@Composable
private fun Bell(dot: Boolean, onClick: () -> Unit) {
    Box(Modifier.size(DISC)) {
        BarDisc(onClick, Modifier.semantics { if (dot) stateDescription = "New" }) { Glyph(Ph.caretLeft, 20.dp, C.ink, label = "Today at a glance") }
        if (dot) {
            Box(
                Modifier
                    .align(Alignment.TopEnd)
                    .padding(top = 7.dp, end = 8.dp)
                    .size(12.dp)
                    .background(C.white, CircleShape)
                    .padding(2.dp)
                    .background(C.brand, CircleShape),
            )
        }
    }
}

/**
 * A receipt: above the composer for a few seconds, then gone. The thread is
 * for things that were said; the ledger holds the fact. Tap to dismiss.
 */
@Composable
fun ToastView(toast: Toast?, onDismiss: () -> Unit, modifier: Modifier = Modifier) {
    if (toast == null) return
    val shape = RoundedCornerShape(14.dp)
    Box(modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
        Row(
            Modifier
                .fadeUp(280)
                .widthIn(max = 420.dp)
                .padding(horizontal = 16.dp)
                .then(S.popover(shape))
                .clip(shape)
                .background(C.ink)
                .plainTap(onClick = onDismiss)
                .padding(start = 12.dp, end = 14.dp, top = 9.dp, bottom = 9.dp),
            horizontalArrangement = Arrangement.spacedBy(9.dp),
        ) {
            if (toast.failed) Glyph(PhBold.x, 14.dp, C.red, Modifier.padding(top = 2.dp))
            else Glyph(PhBold.check, 14.dp, C.brandSoft, Modifier.padding(top = 2.dp))
            Column {
                Text(toast.text, style = T.sans.copy(fontSize = 12.5.sp, lineHeight = 17.5.sp, color = C.paper))
                toast.sub?.let { Text(it, style = T.mono.copy(fontSize = 12.5.sp, color = C.ringIdle), modifier = Modifier.padding(top = 2.dp)) }
            }
        }
    }
}

/** The user's face: Google's picture when there is one, the initial when not, or when it fails. */
@Composable
fun UserAvatar(name: String, url: String?, size: Dp = 46.dp) {
    var broken by remember(url) { mutableStateOf(false) }
    if (url != null && !broken) {
        AsyncImage(
            url, null, Modifier.size(size).clip(CircleShape), contentScale = ContentScale.Crop,
            onError = { broken = true },
        )
    } else {
        Box(Modifier.size(size).background(C.brand, CircleShape), contentAlignment = Alignment.Center) {
            Text(name.trim().take(1).uppercase(), style = T.figure.copy(fontWeight = FontWeight.SemiBold, fontSize = (size.value * 0.41f).sp, color = C.white))
        }
    }
}

/** The menu's rows, in three groups: what is yours, how the app reaches you, and help. Profile is the card above them. */
private val MENU_GROUPS = listOf(
    listOf("Reports" to Ph.chartBar, "Your data" to Ph.database),
    listOf("Notifications" to Ph.bell, "Permissions" to Ph.shieldCheck, "Billing" to Ph.creditCard),
    listOf("Help & feedback" to Ph.question),
)

/** The rows that open a page today; the rest are honest about being next. */
private val BUILT = setOf("Reports", "Your data")

/**
 * The menu: a full-height sheet that slides in from the left, on the ground
 * every page shares. You at the top as a card — a tap is your profile — then
 * the rows in panels, each with its coin. A place you come back to: a row
 * pushes its page over the menu, and that page's ← returns here as it was
 * left. X, or Back, goes to where the menu was opened. Port of `Drawer.tsx`.
 */
@Composable
fun Drawer(userName: String, avatarUrl: String?, onClose: () -> Unit, onRow: (String) -> Unit, onSignOut: () -> Unit) {
    // Sign out asks first. Back, Cancel or a row's page put the question away.
    var confirming by remember { mutableStateOf(false) }
    val top = LocalOnTop.current
    LaunchedEffect(top) { if (!top) confirming = false }
    BackStep(confirming) { confirming = false }
    // Once per opening: the menu stays drawn under the pages its rows open.
    val slide = remember { Animatable(-1f) }
    LaunchedEffect(Unit) { slide.animateTo(0f, tween(280, easing = CubicBezierEasing(0.3f, 0.7f, 0.3f, 1f))) }
    Column(
        Modifier
            .fillMaxSize()
            .graphicsLayer { translationX = slide.value * size.width }
            .background(Ground)
            .plainTap { }
            .safeDrawingPadding()
            .padding(top = 8.dp, bottom = 12.dp),
    ) {
        Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp), horizontalArrangement = Arrangement.End) {
            RoundIcon(Ph.x, onClose, "Close")
        }
        Column(Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(horizontal = 16.dp)) {
            Row(
                Modifier.padding(top = 10.dp).fillMaxWidth().panel().tap { onRow("Profile") }.padding(18.dp),
                horizontalArrangement = Arrangement.spacedBy(14.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                UserAvatar(userName, avatarUrl, 56.dp)
                Column(Modifier.weight(1f)) {
                    Text(userName, style = T.sans.copy(fontSize = 21.sp, lineHeight = 25.sp, fontWeight = FontWeight.SemiBold))
                    // What the row opens: Profile, where the goals and the memories live.
                    Text("Your goals, and what Spica remembers", style = T.sans.copy(fontSize = 13.sp, lineHeight = 17.sp, color = C.faint), modifier = Modifier.padding(top = 2.dp))
                }
                Glyph(PhBold.caretRight, 12.dp, C.grey)
            }
            MENU_GROUPS.forEach { group ->
                Column(Modifier.padding(top = 14.dp).fillMaxWidth().panel()) {
                    group.forEachIndexed { i, (name, icon) ->
                        val built = name in BUILT
                        Row(
                            Modifier
                                .fillMaxWidth()
                                .then(if (i > 0) Modifier.divider(66.dp, 18.dp) else Modifier)
                                // A row that leads nowhere yet is not a door: no tap, and said to be off.
                                .then(if (built) Modifier.tap { onRow(name) } else Modifier.semantics(mergeDescendants = true) { disabled() })
                                .padding(horizontal = 16.dp, vertical = 13.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(14.dp),
                        ) {
                            Coin(icon, C.ink, C.surface, 36.dp)
                            Text(name, style = T.sans.copy(fontSize = 16.sp, lineHeight = 20.sp, fontWeight = FontWeight.Medium), modifier = Modifier.weight(1f))
                            // A row that leads nowhere yet says so, rather than looking like a door.
                            if (built) Glyph(PhBold.caretRight, 11.dp, C.grey) else Tag("Soon", C.faint)
                        }
                    }
                }
            }
        }
        // One footer row: who made this on the left, the way out on the right.
        Row(
            Modifier.fillMaxWidth().padding(start = 22.dp, end = 16.dp, top = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Mascot(28.dp, MascotState.Still)
            if (confirming) {
                // The question, then the two answers: stay, or go.
                Text("Sign out?", style = T.sans.copy(fontWeight = FontWeight.SemiBold, fontSize = 15.sp, lineHeight = 17.sp), modifier = Modifier.weight(1f))
                ActionPill("Cancel", { confirming = false })
                ActionPill("Sign out", onSignOut, PillKind.Danger, icon = Ph.signOut)
            } else {
                Column(Modifier.weight(1f)) {
                    Text("Spica", style = T.sans.copy(fontWeight = FontWeight.SemiBold, fontSize = 15.sp, lineHeight = 17.sp))
                    Text("v0.1 · Android", style = T.sans.copy(fontSize = 12.sp, color = C.faint), modifier = Modifier.padding(top = 2.dp))
                }
                val pill = RoundedCornerShape(999.dp)
                Row(
                    Modifier.clip(pill).background(C.redTint).tap { confirming = true }.padding(horizontal = 14.dp, vertical = 9.dp),
                    horizontalArrangement = Arrangement.spacedBy(7.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Glyph(Ph.signOut, 17.dp, C.red)
                    Text("Sign out", style = T.sans.copy(fontSize = 14.sp, lineHeight = 16.sp, fontWeight = FontWeight.Medium, color = C.red))
                }
            }
        }
    }
}

fun Modifier.bottomLine(color: androidx.compose.ui.graphics.Color = C.line) = bottomRule(color)
