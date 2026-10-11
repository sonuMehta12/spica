package com.sonu.spica.ui.common

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.IntrinsicSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Popup
import androidx.compose.ui.window.PopupProperties
import com.sonu.spica.ui.theme.C
import com.sonu.spica.ui.theme.S
import com.sonu.spica.ui.theme.T

data class MenuItem(val key: String, val label: String, val info: Boolean = false, val color: Color = C.ink, val run: () -> Unit)

private val PopShape = RoundedCornerShape(12.dp)

/**
 * The card's overflow menu and the range picker: a white sheet with the
 * popover shadow, anchored under whatever opened it. A tap outside closes it.
 */
@Composable
fun Popover(
    onDismiss: () -> Unit,
    alignment: Alignment = Alignment.TopEnd,
    offset: IntOffset = IntOffset(0, 0),
    minWidth: Dp = 150.dp,
    content: @Composable () -> Unit,
) {
    Popup(alignment = alignment, offset = offset, onDismissRequest = onDismiss, properties = PopupProperties(focusable = true)) {
        Column(
            Modifier
                .padding(12.dp)
                .fadeUp(160)
                .then(S.popover(PopShape))
                .background(C.white, PopShape)
                .border(1.dp, C.line, PopShape)
                .padding(5.dp)
                .widthIn(min = minWidth)
                .width(IntrinsicSize.Max),
        ) { content() }
    }
}

/** One row of a menu. An `info` row is words, not a control: muted, and nothing to tap. */
@Composable
fun MenuRow(item: MenuItem, onDone: () -> Unit) {
    Text(
        item.label,
        style = T.sans.copy(fontSize = 12.5.sp, color = if (item.info) C.muted else item.color),
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(8.dp))
            .then(
                if (item.info) Modifier
                else Modifier.tap {
                    item.run()
                    onDone()
                },
            )
            .padding(horizontal = 11.dp, vertical = 9.dp),
    )
}
