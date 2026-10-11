package com.sonu.spica.ui.common

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.pager.PagerState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.foundation.focusGroup
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.compositionLocalOf
import androidx.compose.runtime.key
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.focus.focusProperties
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.graphics.lerp
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.runtime.getValue
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.sonu.spica.ui.theme.C
import com.sonu.spica.ui.theme.S
import com.sonu.spica.ui.theme.T
import kotlin.math.abs
import kotlin.math.roundToInt

/*
 * The pages over Home — Reports, Your data, Profile, the menu — wear Home's
 * clothes: the same tinted ground, white panels that float on it, a coin per
 * thing in its mode's ink, and selection in Jamun. One kit, so a page never
 * has to decide again what a card or a tab looks like.
 */

/** Every page's ground: the tint Home and the thread stand on. */
val Ground get() = C.lineSoft

/** A panel's corners — Home's widget, so a page's cards read as the same objects. */
val PanelShape = RoundedCornerShape(24.dp)

/** A white panel floating on the ground: the soft shadow, no border. */
fun Modifier.panel(shape: Shape = PanelShape) = this.then(S.widget(shape)).clip(shape).background(C.white)

/** A rule between rows inside a panel, held off its edges so the row reads, not the line. */
fun Modifier.divider(start: Dp = 0.dp, end: Dp = 0.dp) = drawBehind {
    drawLine(C.lineSoft, Offset(start.toPx(), 0f), Offset(size.width - end.toPx(), 0f), 1.dp.toPx())
}

/*
 * Back. Screens over Home form one stack (`AppState.stack`): a page has one
 * exit, ← at the top right of its head, where a close once sat. It is an
 * arrow alone — no name beside it — and a screen reader hears where it goes;
 * system back pops the same entry. X is only for the root of a modal layer —
 * the menu, a sheet, a dialog — never on a page. THEME.md § Back.
 */

/** Where a page's ← goes: the name of the screen under it — said to a screen reader, not shown — and the pop. */
data class Back(val to: String, val onClick: () -> Unit)

/**
 * Whether the layer this is drawn in is the top one. Home's overlays provide
 * it per stack entry, and the pager per page; everything under the top keeps
 * its state but takes no back — so a hidden page's open editor can never
 * swallow a press.
 */
val LocalOnTop = compositionLocalOf { true }

/**
 * Back closes this first, while it is open and its layer is on top. One per
 * open thing, never a branch inside. The step opened last closes first — it
 * registers again each time it opens, as the web's `useBack` does — and steps
 * that open together close in reverse of where they are written, so list a
 * page's steps outermost first and the innermost last.
 */
@Composable
fun BackStep(open: Boolean, onBack: () -> Unit) {
    val on = open && LocalOnTop.current
    key(on) { BackHandler(enabled = on, onBack = onBack) }
}

/**
 * A layer's hold on focus: on top, as usual; under the top, none. A field it
 * held lets go when something is pushed over it — the keyboard drops, and
 * neither a keystroke nor the keyboard's Done reaches a page no one can see —
 * and nothing in it can take focus again until it is on top.
 */
@Composable
fun layerFocus(top: Boolean): Modifier {
    val fm = LocalFocusManager.current
    val holds = remember { booleanArrayOf(false) }
    LaunchedEffect(top) { if (!top && holds[0]) fm.clearFocus(force = true) }
    return Modifier
        .onFocusChanged { holds[0] = it.hasFocus }
        .focusProperties { onEnter = { if (!top) cancelFocusChange() } }
        .focusGroup()
}

/**
 * A page's ←: a white disc with the arrow, at the head's top right — the size
 * and place a page's close had. One tap target that reads as "Back to Menu".
 */
@Composable
fun BackButton(back: Back) {
    Box(
        Modifier
            .size(40.dp)
            .then(S.bubble(CircleShape))
            .clip(CircleShape)
            .background(C.white)
            .semantics(mergeDescendants = true) {
                role = Role.Button
                contentDescription = "Back to ${back.to}"
            }
            .tap(onClick = back.onClick),
        contentAlignment = Alignment.Center,
    ) { Glyph(Ph.arrowLeft, 19.dp, C.ink) }
}

/**
 * A page's head: a small word that says which page, the title large under it,
 * and ← on the right. `lead` puts a face before the title. No close: the
 * page's one exit is the ←.
 */
@Composable
fun PageHeader(
    kicker: String?,
    title: String,
    back: Back,
    modifier: Modifier = Modifier,
    lead: (@Composable () -> Unit)? = null,
    sub: String? = null,
) {
    Row(modifier.fillMaxWidth().padding(start = 20.dp, end = 14.dp, top = 10.dp, bottom = 6.dp), verticalAlignment = Alignment.CenterVertically) {
        if (lead != null) {
            lead()
            Box(Modifier.size(14.dp))
        }
        Column(Modifier.weight(1f)) {
            if (kicker != null) Text(kicker, style = T.sans.copy(fontSize = 13.sp, lineHeight = 16.sp, fontWeight = FontWeight.Medium, color = C.faint))
            Text(
                title,
                style = T.sans.copy(fontSize = 30.sp, lineHeight = 34.sp, fontWeight = FontWeight.SemiBold, letterSpacing = (-0.4).sp),
                maxLines = 1, overflow = TextOverflow.Ellipsis,
            )
            if (sub != null) Text(sub, style = T.sans.copy(fontSize = 13.sp, lineHeight = 17.sp, color = C.faint), modifier = Modifier.padding(top = 1.dp))
        }
        BackButton(back)
    }
}

/** A white disc with a glyph in it — close, back, more — floating like a panel. */
@Composable
fun RoundIcon(icon: ImageVector, onClick: () -> Unit, label: String, size: Dp = 40.dp, tint: Color = C.ink) {
    Box(
        Modifier.size(size).then(S.bubble(CircleShape)).clip(CircleShape).background(C.white).tap(onClick = onClick),
        contentAlignment = Alignment.Center,
    ) { Glyph(icon, 19.dp, tint, label = label) }
}

/** Who a thing is: its icon in its mode's ink on its mode's tint. */
@Composable
fun Coin(icon: ImageVector, ink: Color, tint: Color, size: Dp = 36.dp, modifier: Modifier = Modifier) {
    Box(modifier.size(size).background(tint, CircleShape), contentAlignment = Alignment.Center) {
        Glyph(icon, size * 0.52f, ink)
    }
}

/** A group's name above its panel: small, medium weight, never tracked caps. */
@Composable
fun SectionLabel(text: String, modifier: Modifier = Modifier, aside: (@Composable () -> Unit)? = null) {
    Row(modifier.fillMaxWidth().padding(start = 6.dp, end = 4.dp, top = 26.dp, bottom = 10.dp), verticalAlignment = Alignment.CenterVertically) {
        Text(text, style = T.sans.copy(fontSize = 14.sp, lineHeight = 18.sp, fontWeight = FontWeight.SemiBold, color = C.ink), modifier = Modifier.weight(1f))
        aside?.invoke()
    }
}

/** One word's width in a [PagePill]. */
private val PILL_SEG = 84.dp

/**
 * One choice of a few laid side by side in a pager — Home | Chat, a report's
 * modes. The current word is filled in Jamun — selection is the brand's job —
 * and the fill rides the pager: it slides with the finger, not after the page
 * lands, and each word turns white as the fill comes under it.
 */
@Composable
fun PagePill(pager: PagerState, labels: List<String>, onPick: (Int) -> Unit, seg: Dp = PILL_SEG) {
    val pill = RoundedCornerShape(50)
    val pos = (pager.currentPage + pager.currentPageOffsetFraction).coerceIn(0f, (labels.size - 1).toFloat())
    Box(
        Modifier
            .height(40.dp)
            .clip(pill)
            // White on the tinted ground every page shares.
            .background(C.white)
            .border(1.dp, C.line, pill)
            .padding(3.dp),
    ) {
        Box(
            Modifier
                .offset { IntOffset((seg.toPx() * pos).roundToInt(), 0) }
                .width(seg)
                .fillMaxHeight()
                .background(C.brand, pill),
        )
        Row(Modifier.fillMaxHeight()) {
            labels.forEachIndexed { i, label ->
                // How much of the fill sits under this word.
                val under = (1f - abs(pos - i)).coerceIn(0f, 1f)
                Box(
                    Modifier
                        .width(seg)
                        .fillMaxHeight()
                        .clip(pill)
                        .semantics {
                            role = Role.Tab
                            selected = under > 0.5f
                        }
                        .plainTap { onPick(i) },
                    contentAlignment = Alignment.Center,
                ) {
                    Text(label, style = T.sans.copy(fontSize = 15.sp, lineHeight = 18.sp, fontWeight = FontWeight.Medium, color = lerp(C.muted, C.white, under)))
                }
            }
        }
    }
}

/** A filter: white on the ground at rest, Jamun when chosen. */
@Composable
fun FilterPill(label: String, on: Boolean, onClick: () -> Unit, icon: ImageVector? = null) {
    val pill = RoundedCornerShape(50)
    Row(
        Modifier
            .then(if (on) Modifier else S.bubble(pill))
            .clip(pill)
            .background(if (on) C.brand else C.white)
            .tap(onClick = onClick)
            .padding(horizontal = 15.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        if (icon != null) Glyph(icon, 14.dp, if (on) C.white else C.muted)
        Text(label, style = T.sans.copy(fontSize = 13.5.sp, lineHeight = 16.sp, fontWeight = FontWeight.Medium, color = if (on) C.white else C.ink), maxLines = 1)
    }
}

/** A strip of filters that scrolls sideways, with room for their shadows. */
@Composable
fun FilterStrip(modifier: Modifier = Modifier, content: @Composable () -> Unit) {
    Row(
        modifier.fillMaxWidth().horizontalScroll(rememberScrollState()).padding(vertical = 4.dp, horizontal = 2.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) { content() }
}

/** A small word on the surface tint, in a pill — a window, a count, a state. */
@Composable
fun Tag(text: String, color: Color = C.muted, bg: Color = C.surface, modifier: Modifier = Modifier) =
    Text(
        text,
        style = T.sans.copy(fontSize = 12.sp, lineHeight = 15.sp, fontWeight = FontWeight.Medium, color = color),
        modifier = modifier.background(bg, RoundedCornerShape(50)).padding(horizontal = 9.dp, vertical = 4.dp),
        maxLines = 1,
    )

/** A panel with the standard inset, for content that is not a list of rows. */
@Composable
fun Panel(modifier: Modifier = Modifier, onClick: (() -> Unit)? = null, content: @Composable ColumnScope.() -> Unit) {
    Column(
        modifier.fillMaxWidth().panel().then(if (onClick != null) Modifier.tap(onClick = onClick) else Modifier).padding(18.dp),
        content = content,
    )
}

/** Where a page's list slides under its head: the ground fading in, not a hard cut. */
@Composable
fun TopFade(modifier: Modifier = Modifier) =
    Box(modifier.fillMaxWidth().height(18.dp).background(androidx.compose.ui.graphics.Brush.verticalGradient(listOf(Ground, Ground.copy(alpha = 0f)))))

/** How an action pill reads: the one to press (Jamun), a quiet one (surface), or a destructive one (red's tint). */
enum class PillKind { Primary, Quiet, Danger }

/** A button in a panel — Save, Add, Cancel, Delete — always a pill, never a slab. */
@Composable
fun ActionPill(label: String, onClick: () -> Unit, kind: PillKind = PillKind.Quiet, enabled: Boolean = true, icon: ImageVector? = null) {
    val (fg, bg) = when {
        !enabled -> C.grey to C.surface
        kind == PillKind.Primary -> C.white to C.brand
        kind == PillKind.Danger -> C.red to C.redTint
        else -> C.ink to C.surface
    }
    Row(
        Modifier.clip(RoundedCornerShape(50)).background(bg).tap(enabled = enabled, onClick = onClick).padding(horizontal = 16.dp, vertical = 9.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        if (icon != null) Glyph(icon, 15.dp, fg)
        Text(label, style = T.sans.copy(fontSize = 14.sp, lineHeight = 17.sp, fontWeight = FontWeight.Medium, color = fg), maxLines = 1)
    }
}

/** The last row of a list that grows: a plus in a Jamun coin and what it adds. */
@Composable
fun AddRow(label: String, onClick: () -> Unit, modifier: Modifier = Modifier) {
    Row(
        modifier.fillMaxWidth().tap(onClick = onClick).padding(horizontal = 18.dp, vertical = 14.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Coin(Ph.plus, C.brand, C.brandTint, 30.dp)
        Text(label, style = T.sans.copy(fontSize = 15.sp, lineHeight = 19.sp, fontWeight = FontWeight.Medium, color = C.brand))
    }
}

/** On or off: a track that fills with Jamun, a white knob that slides. */
@Composable
fun Switch(on: Boolean, onToggle: () -> Unit, label: String) {
    val x by androidx.compose.animation.core.animateDpAsState(if (on) 18.dp else 0.dp, label = "knob")
    val track by androidx.compose.animation.animateColorAsState(if (on) C.brand else C.border, label = "track")
    Box(
        Modifier
            .size(width = 44.dp, height = 26.dp)
            .clip(RoundedCornerShape(50))
            .background(track)
            .semantics {
                role = Role.Switch
                this.selected = on
                contentDescription = label
            }
            .tap(onClick = onToggle)
            .padding(3.dp),
    ) {
        Box(Modifier.padding(start = x).size(20.dp).then(S.bubble(CircleShape)).background(C.white, CircleShape))
    }
}
