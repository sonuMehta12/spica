package com.sonu.spica.ui.common

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.TextUnit
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.sonu.spica.ui.theme.T

/** The wordmark: `spica`, lowercase, the sans at semibold, drawn a touch tight — `THEME.md` § Type. Never the serif. */
@Composable
fun Wordmark(size: TextUnit, modifier: Modifier = Modifier) {
    Text(
        "spica",
        style = T.sans.copy(fontWeight = FontWeight.SemiBold, fontSize = size, lineHeight = size * 1.2f, letterSpacing = (-0.5).sp),
        modifier = modifier,
    )
}

/**
 * The logo, top left of the first run's screens: the mark at 24 — the
 * smallest size it draws all nine dots — still, beside the wordmark.
 */
@Composable
fun Logo(modifier: Modifier = Modifier) {
    Row(modifier, verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(7.dp)) {
        Mascot(24.dp, MascotState.Still)
        Wordmark(19.sp)
    }
}
