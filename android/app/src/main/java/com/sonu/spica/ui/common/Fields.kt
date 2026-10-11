package com.sonu.spica.ui.common

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.text.TextRange
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.sonu.spica.ui.theme.C
import com.sonu.spica.ui.theme.T

/**
 * The prototype's small inline inputs — paper fill, a line border, radius 8.
 * Enter saves; that is the contract every inline editor in the app keeps.
 *
 * An editor that opens already holding a value selects it, as the web's
 * `onFocus={select}` does: the usual edit is a replacement, and a cursor at the
 * start would type in front of the old number.
 */
@Composable
fun InlineField(
    value: String,
    onChange: (String) -> Unit,
    modifier: Modifier = Modifier,
    placeholder: String = "",
    numeric: Boolean = false,
    decimal: Boolean = false,
    autoFocus: Boolean = false,
    mono: Boolean = true,
    singleLine: Boolean = true,
    style: TextStyle = if (mono) T.mono.copy(fontSize = 15.sp, color = C.ink) else T.sans.copy(fontSize = 15.sp),
    onDone: () -> Unit = {},
) {
    val focus = remember { FocusRequester() }
    var focused by remember { mutableStateOf(false) }
    // Selected on arrival when it gains focus by itself; otherwise the cursor sits at the end.
    var field by remember { mutableStateOf(TextFieldValue(value, if (autoFocus) TextRange(0, value.length) else TextRange(value.length))) }
    // The caller owns the text; a change from outside moves the cursor to the end.
    if (field.text != value) field = TextFieldValue(value, TextRange(value.length))
    if (autoFocus) LaunchedEffect(Unit) { focus.requestFocus() }
    // A soft well, not a drawn box: the surface tint at rest, a Jamun edge
    // while it has the cursor — the field says where typing goes.
    val shape = RoundedCornerShape(12.dp)
    Box(
        modifier
            .background(C.surface, shape)
            .border(1.dp, if (focused) C.brandSoft else C.surface, shape)
            // The text field is only as wide as its text; the whole box is the
            // target, or a tap on an empty field's placeholder would miss it.
            .pointerInput(Unit) { detectTapGestures { focus.requestFocus() } }
            .padding(horizontal = 14.dp, vertical = 11.dp),
    ) {
        if (value.isEmpty() && placeholder.isNotEmpty()) Text(placeholder, style = style.copy(color = C.faint), maxLines = 1)
        BasicTextField(
            value = field,
            onValueChange = {
                field = it
                if (it.text != value) onChange(it.text)
            },
            singleLine = singleLine,
            textStyle = style,
            cursorBrush = SolidColor(C.brand),
            keyboardOptions = KeyboardOptions(
                keyboardType = if (decimal) KeyboardType.Decimal else if (numeric) KeyboardType.Number else KeyboardType.Text,
                imeAction = if (singleLine) ImeAction.Done else ImeAction.Default,
            ),
            keyboardActions = KeyboardActions(onDone = { onDone() }),
            modifier = Modifier.focusRequester(focus).onFocusChanged { focused = it.isFocused },
        )
    }
}
