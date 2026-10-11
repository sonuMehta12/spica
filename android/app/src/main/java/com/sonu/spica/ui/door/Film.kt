package com.sonu.spica.ui.door

import android.content.Context
import android.provider.Settings
import androidx.compose.foundation.Canvas
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableDoubleStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.withFrameNanos
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.clipRect
import androidx.compose.ui.graphics.drawscope.scale
import androidx.compose.ui.graphics.drawscope.translate
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.text.TextMeasurer
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.text.style.LineHeightStyle
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Constraints
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.sp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LifecycleEventEffect
import com.sonu.spica.logic.FilmDots
import com.sonu.spica.ui.theme.C
import com.sonu.spica.ui.theme.T
import kotlin.math.min

/** A frame step longer than this — a hidden app, a stalled frame — counts as this: the film resumes where it was. */
private const val STEP_CAP_MS = 100.0

/** *Remove animations* in the phone's settings: the film holds its seven frames instead. */
private fun motionOff(context: Context): Boolean =
    Settings.Global.getFloat(context.contentResolver, Settings.Global.ANIMATOR_DURATION_SCALE, 1f) == 0f

/** CSS's half-leading: a line's spare height split above and below, never trimmed. */
private val CSS_LINE = LineHeightStyle(LineHeightStyle.Alignment.Center, LineHeightStyle.Trim.None)

/** The film's words, laid out once in stage units — one unit to one px — so they scale with the dots. */
private class FilmText(
    val figures: List<TextLayoutResult>,
    val lines: List<TextLayoutResult>,
    val days: List<TextLayoutResult>,
    val captions: List<TextLayoutResult>,
) {
    companion object {
        private val UNIT = Density(1f, 1f)

        /** Lines centred in their own line boxes, across the stage — as the web's SVG sets them. */
        private fun TextMeasurer.lay(text: String, style: TextStyle, width: Float) =
            measure(text, style.copy(textAlign = TextAlign.Center, lineHeightStyle = CSS_LINE), constraints = Constraints.fixedWidth(width.toInt()), density = UNIT)

        fun of(m: TextMeasurer): FilmText {
            val f = FilmDots.LAYOUT.figure
            val d = FilmDots.LAYOUT.days
            val w = FilmDots.STAGE.w
            return FilmText(
                // A figure is data: the sans, medium, tabular, in its scene's ink.
                figures = FilmDots.WINS.map { m.lay(it.figure, T.figure.copy(fontSize = f.size.sp, lineHeight = f.lineHeight.sp, letterSpacing = f.tracking.sp, color = it.ink), w) },
                lines = FilmDots.WINS.map { m.lay(it.line, T.agentVoice.copy(fontSize = f.lineSize.sp, lineHeight = f.lineLineHeight.sp, color = C.ink), w) },
                days = FilmDots.WEEKDAYS.map { m.lay(it, T.sans.copy(fontSize = d.size.sp, lineHeight = d.lineHeight.sp, color = C.faint), d.cell) },
                captions = FilmDots.CAPTIONS.mapIndexed { n, lines ->
                    val c = FilmDots.LAYOUT.captions[n]
                    m.lay(lines.joinToString("\n"), T.agentVoice.copy(fontSize = c.size.sp, lineHeight = c.lineHeight.sp, fontWeight = FontWeight(c.weight), color = C.ink), w)
                },
            )
        }
    }
}

/**
 * The door's film: dots only, no controls, no labels, looping — a life
 * slipping out of hand, put in order, and the results. One clock in film
 * time, sampled with the frame clock and read only inside the draw, so a
 * frame redraws the canvas and never recomposes anything. The stage is
 * 390 × 560 units, scaled to fit — centred, never cropped, never past one
 * unit to one dp. What moves where is `FilmDots.frame`.
 *
 * `freezeAt` holds the film at that millisecond — for checking it against
 * the web's frame for frame; only the debug gallery passes it.
 */
@Composable
fun DotFilm(modifier: Modifier = Modifier, freezeAt: Double? = null) {
    val context = LocalContext.current
    var reduced by remember { mutableStateOf(motionOff(context)) }
    LifecycleEventEffect(Lifecycle.Event.ON_RESUME) { reduced = motionOff(context) }

    val clock = remember { mutableDoubleStateOf(freezeAt ?: 0.0) }
    LaunchedEffect(freezeAt) {
        if (freezeAt != null) {
            clock.doubleValue = freezeAt
            return@LaunchedEffect
        }
        var last = -1L
        while (true) {
            withFrameNanos { now ->
                if (last >= 0) {
                    var t = clock.doubleValue + min(STEP_CAP_MS, (now - last) / 1e6)
                    // Past the second loop, back one: every loop after the first is the same.
                    if (t >= 2.0 * FilmDots.LOOP_MS) t -= FilmDots.LOOP_MS
                    clock.doubleValue = t
                }
                last = now
            }
        }
    }

    val measurer = rememberTextMeasurer()
    val text = remember(measurer) { FilmText.of(measurer) }

    Canvas(
        modifier.semantics {
            contentDescription = FilmDots.LABEL
            role = Role.Image
        },
    ) {
        val f = FilmDots.frame(clock.doubleValue, reduced)
        val stage = FilmDots.STAGE
        val k = minOf(size.width / stage.w, size.height / stage.h, density)
        translate((size.width - stage.w * k) / 2, (size.height - stage.h * k) / 2) {
            scale(k, k, pivot = Offset.Zero) {
                clipRect(0f, 0f, stage.w, stage.h) { drawFrame(f, text) }
            }
        }
    }
}

private fun DrawScope.drawFrame(f: FilmDots.Frame, text: FilmText) {
    val layout = FilmDots.LAYOUT
    // The small mark: arrives with the order, from `Mascot`'s geometry, scaled about its centre.
    if (f.mark.opacity > 0f) {
        val box = layout.mark
        val u = box.size / 96f
        scale(f.mark.scale, f.mark.scale, pivot = Offset(box.x + box.size / 2, box.y + box.size / 2)) {
            FilmDots.MARK.forEach { m -> drawCircle(FilmDots.MARK_INK, m.r * u, Offset(box.x + m.x * u, box.y + m.y * u), alpha = f.mark.opacity) }
        }
    }
    if (f.days.opacity > 0f) {
        val d = layout.days
        val left = FilmDots.STAGE.w / 2 - FilmDots.WEEKDAYS.size * d.cell / 2
        text.days.forEachIndexed { i, t -> drawText(t, topLeft = Offset(left + i * d.cell, d.top), alpha = f.days.opacity) }
    }
    // Each dot is its box, as the prototype positions a span: a circle filling it, shaken in the mess.
    f.dots.forEach { d ->
        if (d.opacity > 0f) drawCircle(d.fill, d.size / 2, Offset(d.x + d.size / 2 + d.jx, d.y + d.size / 2 + d.jy), alpha = d.opacity)
    }
    // The outcome: a figure, in the scene's ink, over the agent's line.
    if (f.figure.opacity > 0f) {
        val fig = layout.figure
        drawText(text.figures[f.figure.win], topLeft = Offset(0f, fig.top + f.figure.drop), alpha = f.figure.opacity)
        drawText(text.lines[f.figure.win], topLeft = Offset(0f, fig.lineTop + f.figure.drop), alpha = f.figure.opacity)
    }
    text.captions.forEachIndexed { n, t ->
        val a = f.captions[n]
        if (a > 0f) drawText(t, topLeft = Offset(0f, layout.captions[n].top), alpha = a)
    }
}
