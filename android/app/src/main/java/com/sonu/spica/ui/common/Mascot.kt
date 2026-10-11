package com.sonu.spica.ui.common

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.EaseIn
import androidx.compose.animation.core.EaseInOut
import androidx.compose.animation.core.EaseOut
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.StartOffset
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.drawscope.scale
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.sonu.spica.ui.theme.C

/**
 * `saving` is the one-shot beat; `done` is the same beat, then held at rest —
 * the newest reply wears it until the next turn starts.
 */
enum class MascotState { Still, Idle, Thinking, Saving, Done, Listening }

/** Below this, the diagonal dots land under a pixel: small sizes get their own build. */
private val COMPACT_BELOW = 24.dp

/** Below this, the full build's outer dots gain half a unit so they keep their weight. */
private val HEAVY_BELOW = 48.dp

/** One outer dot, in 96-unit space, with its turn in the thinking pulse. */
private class Dot(val x: Float, val y: Float, val r: Float, val delay: Int)

/**
 * Clockwise from the top. A mid dot every 300 ms, and each diagonal 150 ms
 * behind the mid dot before it: one wave round the ring, 1.2 s a lap.
 */
private fun ring(mid: Float, diagonal: Float) = listOf(
    Dot(48f, 20f, mid, 0), Dot(68f, 28f, diagonal, 150),
    Dot(76f, 48f, mid, 300), Dot(68f, 68f, diagonal, 450),
    Dot(48f, 76f, mid, 600), Dot(28f, 68f, diagonal, 750),
    Dot(20f, 48f, mid, 900), Dot(28f, 28f, diagonal, 1050),
)

private val FULL = ring(6f, 3.5f)
private val HEAVY = ring(6.5f, 4f)

/** The centre dot's radius in the full build. */
private const val CORE_R = 10f

/** One dot of the mark in 96-unit space: where it sits and how big. */
data class MarkDot(val x: Float, val y: Float, val r: Float)

/**
 * The full build as geometry, for a drawing that has to land exactly on the
 * mark — the door's film gathers its dots into it. The centre, then the ring
 * clockwise from the top, the order `Mascot` draws them in.
 */
val MARK_CORE = MarkDot(48f, 48f, CORE_R)
val MARK_RING: List<MarkDot> = FULL.map { MarkDot(it.x, it.y, it.r) }

/** The compact build: no diagonals, and the four mid dots heavier and further out. */
private val COMPACT = listOf(
    Dot(48f, 18f, 8f, 0), Dot(78f, 48f, 8f, 300), Dot(48f, 78f, 8f, 600), Dot(18f, 48f, 8f, 900),
)

/**
 * Spica, as a constellation — port of `Mascot.tsx` and its `.cx-mascot` keyframes.
 *
 * Every dot is one colour, the brand. Motion moves dots, never resizes the
 * outer ones: the outer dots travel along their own spoke from the centre, so
 * the mark keeps its shape whatever state it is in.
 * `Still` is a real state: exactly one mark on screen is ever alive.
 */
@Composable
fun Mascot(size: Dp, state: MascotState = MascotState.Idle, compact: Boolean? = null, modifier: Modifier = Modifier) {
    val small = compact ?: (size < COMPACT_BELOW)
    val dots = when {
        small -> COMPACT
        size < HEAVY_BELOW -> HEAVY
        else -> FULL
    }

    val loop = rememberInfiniteTransition(label = "mascot")

    // idle: the centre breathes, and nothing else moves.
    val breath = if (state == MascotState.Idle) loop.animateFloat(
        1f, 1.06f, infiniteRepeatable(tween(2500, easing = EaseInOut), RepeatMode.Reverse), label = "breath",
    ).value else 1f

    // thinking: the outer dots dim in turn, clockwise from the top.
    val thinking = state == MascotState.Thinking
    val alphas = dots.map { d ->
        if (thinking) loop.animateFloat(
            1f, 0.2f,
            infiniteRepeatable(tween(600, easing = EaseInOut), RepeatMode.Reverse, StartOffset(d.delay)),
            label = "pulse",
        ).value else 1f
    }

    // listening: sound travels outward, so the outer dots do — 6% and back.
    val drift = if (state == MascotState.Listening) loop.animateFloat(
        1f, 1.06f, infiniteRepeatable(tween(950, easing = EaseInOut), RepeatMode.Reverse), label = "drift",
    ).value else 1f

    // saving / done: the outer dots draw in, spring back out past their place
    // and settle — and the mark holds still where it lands.
    val beating = state == MascotState.Saving || state == MascotState.Done
    val beat = remember { Animatable(1f) }
    LaunchedEffect(beating) {
        beat.snapTo(1f)
        if (beating) {
            beat.animateTo(0.75f, tween(180, easing = EaseIn))
            beat.animateTo(1.08f, tween(200, easing = EaseOut))
            beat.animateTo(1f, tween(220, easing = EaseInOut))
        }
    }

    Canvas(modifier.size(size)) {
        val k = this.size.width / 96f
        scale(k, k, pivot = Offset.Zero) {
            val spread = drift * beat.value
            dots.forEachIndexed { i, d ->
                val at = Offset(48f + (d.x - 48f) * spread, 48f + (d.y - 48f) * spread)
                drawCircle(C.brand, radius = d.r, center = at, alpha = alphas[i])
            }
            drawCircle(C.brand, radius = (if (small) 12f else CORE_R) * breath, center = Offset(48f, 48f))
        }
    }
}
