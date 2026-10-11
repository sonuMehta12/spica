package com.sonu.spica.ui.home

import androidx.compose.animation.core.CubicBezierEasing
import androidx.compose.animation.core.animateDpAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.sonu.spica.data.ProjectStat
import com.sonu.spica.ui.theme.C
import com.sonu.spica.ui.theme.T

/** A 1dp rule along the top edge, as `border-top` draws it. */
fun Modifier.topRule(color: androidx.compose.ui.graphics.Color = C.lineSoft) = drawBehind {
    drawLine(color, Offset(0f, 0f), Offset(size.width, 0f), 1.dp.toPx())
}

/* ─── the project bars (the To-do report) ─────────────────────────────── */

private val BAR_H = 58.dp
private val BAR_W = 20.dp
private val EASE = CubicBezierEasing(0.4f, 0f, 0.2f, 1f)

/**
 * Tasks per project — count up the y, one bar per project across the x.
 * Stacked: solid is finished, translucent is what is left. A red pip sits
 * above any project with something overdue. Port of `ProjectChart.tsx`.
 */
@Composable
fun ProjectChart(projects: List<ProjectStat>) {
    val peak = maxOf(1, projects.maxOfOrNull { it.total } ?: 0)
    Column {
        Row(
            Modifier.fillMaxWidth().height(BAR_H).drawBehind {
                drawLine(C.line, Offset(0f, size.height), Offset(size.width, size.height), 1.dp.toPx())
            },
            horizontalArrangement = Arrangement.spacedBy(10.dp, Alignment.CenterHorizontally),
            verticalAlignment = Alignment.Bottom,
        ) {
            projects.forEach { p ->
                val h = ((p.total.toFloat() / peak) * (BAR_H.value - 8)).let { Math.round(it) }
                val fill = if (p.total > 0) Math.round(p.done.toFloat() / p.total * h) else 0
                val hh by animateDpAsState(maxOf(2, h).dp, tween(450, easing = EASE), label = "bar")
                val ff by animateDpAsState(fill.dp, tween(450, easing = EASE), label = "fill")
                Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(3.dp)) {
                    Box(Modifier.size(4.dp).background(if (p.late > 0) C.red else androidx.compose.ui.graphics.Color.Transparent, CircleShape))
                    Box(
                        Modifier
                            .width(BAR_W)
                            .height(hh)
                            .clip(RoundedCornerShape(topStart = 3.dp, topEnd = 3.dp))
                            .background(p.color.copy(alpha = 0x2E / 255f)),
                        contentAlignment = Alignment.BottomCenter,
                    ) {
                        Box(Modifier.fillMaxWidth().height(ff).background(p.color))
                    }
                }
            }
        }
        Row(Modifier.fillMaxWidth().padding(top = 6.dp), horizontalArrangement = Arrangement.spacedBy(10.dp, Alignment.CenterHorizontally)) {
            projects.forEach { p ->
                // Initials, not names: a name would wrap at this width.
                Column(Modifier.width(BAR_W), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(2.dp)) {
                    Text(p.name.take(1).uppercase(), style = T.sans.copy(fontSize = 11.sp, lineHeight = 11.sp, fontWeight = FontWeight.SemiBold, color = p.color))
                    Text("${p.done}/${p.total}", style = T.mono.copy(fontSize = 8.5.sp, lineHeight = 9.sp, color = C.faint), maxLines = 1, softWrap = false)
                }
            }
        }
    }
}
