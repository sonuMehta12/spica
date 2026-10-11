package com.sonu.spica.ui.common

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.ripple
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.composed
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.sonu.spica.ui.theme.C
import com.sonu.spica.ui.theme.S
import com.sonu.spica.ui.theme.T

/** A card in the thread: plain corners — with no face beside it there is nothing for a tail to point at. */
val AgentShape = RoundedCornerShape(20.dp)

/** Yours: a brand-tint pill, the tail at the bottom right where the thread grows. */
val UserShape = RoundedCornerShape(topStart = 18.dp, topEnd = 18.dp, bottomEnd = 4.dp, bottomStart = 18.dp)

/** `fadeup`: rise 8dp into place as it mounts. */
fun Modifier.fadeUp(ms: Int = 350): Modifier = composed {
    val a = remember { Animatable(0f) }
    LaunchedEffect(Unit) { a.animateTo(1f, tween(ms)) }
    graphicsLayer {
        alpha = a.value
        translationY = (1f - a.value) * 8.dp.toPx()
    }
}

@Composable
fun AgentCard(
    modifier: Modifier = Modifier,
    padding: PaddingValues = PaddingValues(horizontal = 13.dp, vertical = 12.dp),
    content: @Composable BoxScope.() -> Unit,
) {
    // White, floating on the tinted ground with Home's soft shadow: the thread's
    // cards and Home's widgets are one family of objects.
    Box(
        modifier
            .fadeUp()
            .then(S.widget(AgentShape))
            .background(C.white, AgentShape)
            .padding(padding),
        content = content,
    )
}

/** Sentence case, as written. The tracked-out caps were the generated look. */
@Composable
fun CardHeading(text: String, modifier: Modifier = Modifier) {
    Text(text, style = T.cardHeading, modifier = modifier)
}

/**
 * The confidence mark, drawn before a value the agent worked out rather than
 * was told. There is no "confirmed" dot — certainty is the default.
 */
@Composable
fun Dot(modifier: Modifier = Modifier) {
    Box(modifier.padding(end = 6.dp).size(6.dp).background(C.amber, CircleShape))
}

@Composable
fun UserBubble(text: String, modifier: Modifier = Modifier) {
    Text(
        text,
        style = T.sans.copy(fontSize = 15.sp, lineHeight = 21.sp, color = C.ink),
        // The brand's deeper tint, lifted a hair: on the tinted ground the pale
        // one sat at the same lightness as the page and all but disappeared.
        modifier = modifier
            .fadeUp()
            .then(S.bubble(UserShape))
            .background(C.chipHover, UserShape)
            .padding(horizontal = 15.dp, vertical = 10.dp),
    )
}

/** A tap target with the prototype's `hov-tint` feel: a soft ripple, no Material chrome. */
fun Modifier.tap(enabled: Boolean = true, onClick: () -> Unit): Modifier = composed {
    clickable(
        interactionSource = remember { MutableInteractionSource() },
        indication = ripple(color = C.muted),
        enabled = enabled,
        onClick = onClick,
    )
}

/** A tap with no ripple — for surfaces whose own change is the feedback. */
fun Modifier.plainTap(enabled: Boolean = true, onClick: () -> Unit): Modifier = composed {
    clickable(
        interactionSource = remember { MutableInteractionSource() },
        indication = null,
        enabled = enabled,
        onClick = onClick,
    )
}

/** A pill chip: white with a border — it is your own entry, not the brand's. */
@Composable
fun Chip(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    tag: String? = null,
    style: TextStyle = T.sans.copy(fontSize = 14.sp, fontWeight = androidx.compose.ui.text.font.FontWeight.Medium),
) {
    val shape = RoundedCornerShape(50)
    androidx.compose.foundation.layout.Row(
        modifier
            .clip(shape)
            .background(C.chip)
            .border(1.dp, C.chipBorder, shape)
            .tap(onClick = onClick)
            .padding(horizontal = 14.dp, vertical = 8.dp),
        horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(6.dp),
        verticalAlignment = androidx.compose.ui.Alignment.CenterVertically,
    ) {
        Text(text, style = style)
        // A figure beside the name is data: grey, tabular.
        if (!tag.isNullOrEmpty()) Text(tag, style = T.mono.copy(fontSize = 14.sp, color = C.muted))
    }
}

enum class Tone { Default, Danger, Good }

data class TrayAction(val label: String, val tone: Tone = Tone.Default, val disabled: Boolean = false, val onClick: () -> Unit)

/**
 * The one ⋮ tray: a row of chips under a card's row. Every card draws this
 * one, so the actions cannot drift between a payment in the Paisa card and the same
 * payment in a confirm card. Port of `messages/Tray.tsx`.
 */
@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@Composable
fun TrayActions(actions: List<TrayAction>, modifier: Modifier = Modifier) {
    if (actions.isEmpty()) return
    androidx.compose.foundation.layout.FlowRow(
        modifier.fillMaxWidth().fadeUp(200).padding(bottom = 2.dp),
        horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(7.dp, androidx.compose.ui.Alignment.End),
        verticalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(7.dp),
    ) {
        actions.forEach { TrayButton(it) }
    }
}

@Composable
fun TrayButton(a: TrayAction) {
    val shape = RoundedCornerShape(50)
    val (border, bg, fg) = when (a.tone) {
        Tone.Danger -> Triple(C.redBorder, C.redSurface, C.red)
        Tone.Good -> Triple(C.chipBorder, C.chip, C.brand)
        Tone.Default -> Triple(C.border, C.paper, C.muted)
    }
    Text(
        a.label,
        style = T.mono.copy(fontSize = 12.5.sp, color = fg),
        modifier = Modifier
            .graphicsLayer { alpha = if (a.disabled) 0.7f else 1f }
            .clip(shape)
            .background(bg)
            .border(1.dp, border, shape)
            .tap(enabled = !a.disabled, onClick = a.onClick)
            .padding(horizontal = 11.dp, vertical = 5.dp),
    )
}

/** The ⋮ toggle that sits inline on a row. */
@Composable
fun TrayToggle(onToggle: () -> Unit) {
    Box(
        Modifier.size(26.dp).clip(CircleShape).tap(onClick = onToggle),
        contentAlignment = androidx.compose.ui.Alignment.Center,
    ) {
        Glyph(Ph.dotsThreeVertical, 18.dp, C.faint, label = "More")
    }
}
