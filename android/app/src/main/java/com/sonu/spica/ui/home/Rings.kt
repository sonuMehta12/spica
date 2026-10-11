package com.sonu.spica.ui.home

import androidx.compose.animation.core.CubicBezierEasing
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.sonu.spica.data.RingSpec
import com.sonu.spica.ui.theme.C
import com.sonu.spica.ui.theme.F
import com.sonu.spica.ui.theme.T

private const val SIZE = 148f
private const val STROKE = 8f

/** Outermost first; a mode uses as many slots as it has rings. */
private val RADII = listOf(66f, 52f, 38f)

private val EASE = CubicBezierEasing(0.4f, 0f, 0.2f, 1f)

/**
 * Concentric arcs, outermost first, every one starting at twelve o'clock.
 * Number-free: the figures live in the legend, keyed by colour, so nothing
 * collides or clips. Port of `ConcentricRings.tsx`.
 */
@Composable
fun ConcentricRings(rings: List<RingSpec>, modifier: Modifier = Modifier) {
    // One animated value per slot, so a changed number sweeps rather than jumps.
    val totals = rings.mapIndexed { i, ring ->
        val pct = if (ring.pct.isFinite()) ring.pct else 0.0
        animateFloatAsState(pct.coerceIn(0.0, 1.0).toFloat(), tween(600, easing = EASE), label = "ring$i").value
    }
    val bases = rings.mapIndexed { i, ring ->
        val b = if (ring.basePct.isFinite()) ring.basePct else 0.0
        animateFloatAsState(b.coerceAtLeast(0.0).toFloat(), tween(600, easing = EASE), label = "base$i").value
    }
    Canvas(modifier.fillMaxWidth().aspectRatio(1f)) {
        val k = size.width / SIZE
        val c = SIZE / 2 * k
        rings.forEachIndexed { i, ring ->
            val r = (RADII.getOrElse(i) { RADII.last() }) * k
            val topLeft = Offset(c - r, c - r)
            val box = Size(r * 2, r * 2)
            val stroke = STROKE * k
            drawCircle(C.ringIdle, radius = r, center = Offset(c, c), style = Stroke(stroke))
            val total = totals[i]
            val base = minOf(total, bases[i])
            val live = maxOf(0f, total - base)
            // Committed portion: the same hue, dialled back, so it keys to the
            // same legend dot rather than reading as a separate grey series.
            if (base > 0f) {
                drawArc(ring.color, -90f, base * 360f, false, topLeft, box, alpha = 0.32f, style = Stroke(stroke, cap = StrokeCap.Butt))
            }
            if (live > 0f) {
                // A round cap would bleed back over the committed segment.
                drawArc(
                    ring.color, -90f + base * 360f, live * 360f, false, topLeft, box,
                    style = Stroke(stroke, cap = if (base > 0f) StrokeCap.Butt else StrokeCap.Round),
                )
            }
        }
    }
}

/** Same footprint as the arcs, for pages with no data behind them. */
@Composable
fun DormantRing(glyph: String) {
    Box(Modifier.size(128.dp), contentAlignment = Alignment.Center) {
        Canvas(Modifier.size(128.dp)) {
            drawCircle(
                C.ringIdle, radius = size.width / 2 - 1.dp.toPx(),
                style = Stroke(2.dp.toPx(), pathEffect = PathEffect.dashPathEffect(floatArrayOf(6f, 6f))),
            )
        }
        Text(glyph, style = T.figure.copy(fontWeight = FontWeight.SemiBold, fontSize = 36.sp, color = C.ringIdle))
    }
}

/**
 * The numbers for each arc, keyed to it by a colour dot. A figure is data,
 * so it is the interface face at medium weight, tabular; its limit sits
 * beside it in grey.
 */
@Composable
fun RingLegend(rings: List<RingSpec>) {
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        rings.forEach { ring ->
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Box(Modifier.padding(top = 5.dp).size(8.dp).background(ring.color, CircleShape))
                Column {
                    Text(ring.caption, style = T.sans.copy(fontSize = 12.5.sp, lineHeight = 15.sp, color = C.faint))
                    Text(
                        buildAnnotatedString {
                            append(ring.valueStr)
                            if (ring.totalStr.isNotEmpty()) withStyle(SpanStyle(fontWeight = FontWeight.Normal, fontSize = 12.sp, color = C.faint)) { append(" / ${ring.totalStr}") }
                        },
                        style = T.figure.copy(fontSize = 20.sp, lineHeight = 24.sp),
                        maxLines = 1,
                        softWrap = false,
                        overflow = TextOverflow.Visible,
                    )
                }
            }
        }
    }
}
