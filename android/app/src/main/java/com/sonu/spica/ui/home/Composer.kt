package com.sonu.spica.ui.home

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.input.key.Key
import androidx.compose.ui.input.key.KeyEventType
import androidx.compose.ui.input.key.key
import androidx.compose.ui.input.key.onPreviewKeyEvent
import androidx.compose.ui.input.key.type
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.text.TextRange
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.em
import androidx.compose.ui.unit.sp
import com.sonu.spica.data.ComposeContext
import com.sonu.spica.ui.common.fadeUp
import com.sonu.spica.ui.common.tap
import com.sonu.spica.ui.theme.C
import com.sonu.spica.ui.theme.S
import com.sonu.spica.ui.theme.T
import com.sonu.spica.ui.common.Glyph
import com.sonu.spica.ui.common.Ph
import com.sonu.spica.ui.common.PhBold

class ComposerActions(
    val onType: (String) -> Unit,
    val onSend: () -> Unit,
    val onMic: () -> Unit,
    val onMedia: () -> Unit,
    val onComposing: (Boolean) -> Unit,
    val onCancelEdit: () -> Unit,
    val onClearContext: () -> Unit,
)

/** Full at one line; a grown composer — three lines, or a context above them — keeps the same corners. */
private val BarShape = RoundedCornerShape(26.dp)

/**
 * One composer, wherever it is needed. A sentence wraps rather than scrolling
 * sideways, grows to three lines and then scrolls inside itself; Enter sends.
 * A context — what a card's Change is about — sits above the input as one
 * small pill, inside the bar, like a quoted line: never a box over the thread.
 * Port of `InputBar.tsx`.
 */
@Composable
fun Composer(
    typed: String,
    focusKey: Int,
    composing: Boolean,
    canLog: Boolean,
    hint: String?,
    editing: String?,
    a: ComposerActions,
    modifier: Modifier = Modifier,
    context: ComposeContext? = null,
    /** What the page under the bar is — Home's tint or the thread's white — so the fade behind it matches. */
    ground: Color = C.paper,
    /** The photo button — off where a photo has nowhere to go (the first run's questions). */
    media: Boolean = true,
    /** The agent is working on the last send: the words can be typed, not sent. */
    waiting: Boolean = false,
    /**
     * Take the cursor as it is drawn — read once, on mount. Home's composer
     * comes back from under a screen still composing (a nudge's Ask, a
     * question sent from a page); a focus asked for while it was gone would
     * otherwise be lost.
     */
    focusOnMount: Boolean = false,
) {
    val hasText = canLog && typed.isNotBlank()
    val focus = remember { FocusRequester() }
    val fm = LocalFocusManager.current
    // Drawn again with a draft in it — back from the menu — the cursor is at its end, not its start.
    var value by remember { mutableStateOf(TextFieldValue(typed, TextRange(typed.length))) }
    // The state owns the text; the field mirrors it. Filled from outside —
    // a chip, an Edit — the cursor goes to the end.
    LaunchedEffect(typed) { if (value.text != typed) value = TextFieldValue(typed, TextRange(typed.length)) }

    // Only on a change, never on mount: an autofocused composer would open
    // the keyboard over the deck every time the app starts. `focusOnMount`
    // is the one exception, asked for.
    var firstFocus by remember { mutableStateOf(!focusOnMount) }
    LaunchedEffect(focusKey) {
        if (firstFocus) {
            firstFocus = false
            return@LaunchedEffect
        }
        runCatching { focus.requestFocus() }
    }
    // The deck came back (a tap on empty space): let the keyboard go too.
    LaunchedEffect(composing) { if (!composing) fm.clearFocus() }

    Column(modifier.fillMaxWidth()) {
        Column(
            Modifier
                .fillMaxWidth()
                .background(Brush.verticalGradient(0f to Color.Transparent, 0.3f to ground))
                .navigationBarsPadding()
                .padding(start = 14.dp, end = 14.dp, top = 10.dp, bottom = 14.dp),
        ) {
        Column(
            Modifier
                .fillMaxWidth()
                // A field on the page: a border, not a lift.
                .background(C.white, BarShape)
                .border(1.dp, C.border, BarShape),
        ) {
        // Over the words it belongs to: the pill starts where the input does.
        if (context != null) ContextPill(context.label, a.onClearContext, Modifier.padding(start = 18.dp, end = 14.dp, top = 9.dp))
        Row(
            Modifier
                .fillMaxWidth()
                .padding(start = 18.dp, end = 6.dp, top = if (context != null) 4.dp else 6.dp, bottom = 6.dp),
            // Bottom, not centre: with three rows of text the buttons stay on the send line.
            verticalAlignment = Alignment.Bottom,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            if (editing != null) {
                val chip = RoundedCornerShape(999.dp)
                Row(
                    Modifier
                        .align(Alignment.CenterVertically)
                        .widthIn(max = 140.dp)
                        .clip(chip)
                        // Amber means an estimate now; an edit is a neutral tag.
                        .background(C.surface)
                        .border(1.dp, C.border, chip)
                        .padding(start = 8.dp, end = 6.dp, top = 3.dp, bottom = 3.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(4.dp),
                ) {
                    Glyph(Ph.pencilSimple, 13.dp, C.muted)
                    Text(editing, style = T.sans.copy(fontSize = 12.sp, color = C.muted), maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f, fill = false))
                    Glyph(PhBold.x, 12.dp, C.muted, Modifier.tap(onClick = a.onCancelEdit), label = "Cancel edit")
                }
            }

            Box(Modifier.weight(1f).align(Alignment.CenterVertically).padding(vertical = 4.dp)) {
                val placeholder = when {
                    editing != null -> "Fix it and send"
                    canLog -> hint ?: "Say what happened…"
                    else -> "Nothing to log here"
                }
                if (value.text.isEmpty()) Text(placeholder, style = T.sans.copy(fontSize = 15.sp, lineHeight = 21.sp, color = C.faint), maxLines = 1, overflow = TextOverflow.Ellipsis)
                BasicTextField(
                    value = if (canLog) value else TextFieldValue(""),
                    onValueChange = { nv ->
                        // Enter sends: a newline never lands in the text.
                        if (nv.text.contains('\n')) {
                            a.onType(nv.text.replace("\n", ""))
                            if (!waiting) a.onSend()
                        } else {
                            value = nv
                            a.onType(nv.text)
                        }
                    },
                    enabled = canLog,
                    textStyle = T.sans.copy(fontSize = 15.sp, lineHeight = 21.sp),
                    cursorBrush = SolidColor(C.brand),
                    maxLines = 3,
                    keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Sentences, imeAction = ImeAction.Send),
                    keyboardActions = androidx.compose.foundation.text.KeyboardActions(onSend = { if (!waiting) a.onSend() }),
                    modifier = Modifier
                        .fillMaxWidth()
                        .heightIn(min = 21.dp)
                        .focusRequester(focus)
                        // Focus enters compose mode. Blur deliberately does not leave it.
                        .onFocusChanged { if (it.isFocused) a.onComposing(true) }
                        // Esc walks back out: the edit, then the context, then the composer.
                        .onPreviewKeyEvent { e ->
                            if (e.key != Key.Escape) return@onPreviewKeyEvent false
                            if (e.type == KeyEventType.KeyDown) when {
                                editing != null -> a.onCancelEdit()
                                context != null -> a.onClearContext()
                                else -> a.onComposing(false)
                            }
                            true
                        },
                )
            }

            if (media) RoundBtn(onClick = a.onMedia, enabled = canLog, modifier = Modifier.alpha(if (canLog) 1f else 0.35f)) {
                Glyph(Ph.image, 22.dp, C.muted, label = "Photo")
            }

            if (hasText) {
                Box(
                    Modifier.size(40.dp).clip(CircleShape).background(if (waiting) C.ringIdle else C.brand).tap(enabled = !waiting, onClick = a.onSend),
                    contentAlignment = Alignment.Center,
                ) { Glyph(Ph.arrowUp, 19.dp, C.white, label = "Send") }
            } else {
                Box(
                    Modifier
                        .size(40.dp)
                        .clip(CircleShape)
                        .background(if (canLog && !waiting) C.brand else C.ringIdle)
                        .tap(enabled = canLog && !waiting, onClick = a.onMic),
                    contentAlignment = Alignment.Center,
                ) { Glyph(Ph.microphone, 20.dp, C.white, label = "Speak") }
            }
        }
        }
        }
    }
}

/**
 * What the next send is about: the label, muted, on one line, and a ✕ that
 * takes it off. A neutral tag on the surface tint — not the brand, which is
 * a selection, and not amber, which is only ever an estimate.
 */
@Composable
private fun ContextPill(label: String, onClear: () -> Unit, modifier: Modifier = Modifier) {
    val pill = RoundedCornerShape(50)
    Row(
        modifier
            .clip(pill)
            .background(C.surface)
            .border(1.dp, C.border, pill)
            .padding(start = 10.dp, end = 3.dp, top = 2.dp, bottom = 2.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(2.dp),
    ) {
        Text(
            label,
            style = T.sans.copy(fontSize = 12.5.sp, lineHeight = 17.sp, color = C.muted),
            maxLines = 1, overflow = TextOverflow.Ellipsis,
            modifier = Modifier.weight(1f, fill = false),
        )
        Box(Modifier.size(20.dp).clip(CircleShape).tap(onClick = onClear), contentAlignment = Alignment.Center) {
            Glyph(Ph.x, 13.dp, C.muted, label = "Remove")
        }
    }
}

@Composable
private fun RoundBtn(onClick: () -> Unit, enabled: Boolean = true, modifier: Modifier = Modifier, content: @Composable () -> Unit) {
    Box(modifier.size(38.dp).clip(CircleShape).tap(enabled = enabled, onClick = onClick), contentAlignment = Alignment.Center) { content() }
}
