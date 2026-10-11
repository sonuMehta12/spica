package com.sonu.spica.ui.common

import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.sonu.spica.ui.theme.C

/**
 * An icon: one Phosphor glyph (`Ph`, `PhFill`, `PhBold`), tinted. A drawn
 * icon set, not paths improvised per screen, so every mark shares one
 * stroke, one corner and one optical size.
 *
 * `label` is what a screen reader says; leave it null when the glyph sits
 * beside words that already say it.
 */
@Composable
fun Glyph(icon: ImageVector, size: Dp = 20.dp, tint: Color = C.ink, modifier: Modifier = Modifier, label: String? = null) =
    androidx.compose.material3.Icon(icon, contentDescription = label, modifier = modifier.size(size), tint = tint)

/** Three dots, upright: the ⋮ menu. */
@Composable
fun KebabIcon(size: Dp = 16.dp, tint: Color = C.faint) = Glyph(Ph.dotsThreeVertical, size + 2.dp, tint, label = "More")

/** A button is busy. One gap in the ring so the rotation is visible. */
@Composable
fun Spinner(size: Dp = 16.dp, tint: Color = C.muted) {
    val t = rememberInfiniteTransition(label = "spin")
    val a = t.animateFloat(0f, 360f, infiniteRepeatable(tween(750, easing = LinearEasing)), label = "a")
    Canvas(Modifier.size(size).rotate(a.value)) {
        val k = this.size.width / 20f
        drawCircle(tint, radius = 7f * k, alpha = 0.25f, style = Stroke(2f * k))
        drawArc(
            tint, startAngle = -90f, sweepAngle = 90f, useCenter = false,
            topLeft = Offset(3f * k, 3f * k), size = Size(14f * k, 14f * k),
            style = Stroke(2f * k, cap = StrokeCap.Round),
        )
    }
}
