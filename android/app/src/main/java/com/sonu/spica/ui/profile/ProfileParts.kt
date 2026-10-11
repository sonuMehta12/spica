package com.sonu.spica.ui.profile

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.DatePicker
import androidx.compose.material3.DatePickerDefaults
import androidx.compose.material3.DatePickerDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.SelectableDates
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.Typography
import androidx.compose.material3.rememberDatePickerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.sonu.spica.ui.chat.bottomRule
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import com.sonu.spica.ui.common.ActionPill
import com.sonu.spica.ui.common.Dot
import com.sonu.spica.ui.common.FilterPill
import com.sonu.spica.ui.common.InlineField
import com.sonu.spica.ui.common.Ph
import com.sonu.spica.ui.common.PillKind
import com.sonu.spica.ui.common.divider
import com.sonu.spica.ui.common.panel
import com.sonu.spica.ui.common.MenuItem
import com.sonu.spica.ui.common.MenuRow
import com.sonu.spica.ui.common.Popover
import com.sonu.spica.ui.common.tap
import com.sonu.spica.ui.home.topRule
import com.sonu.spica.ui.theme.C
import com.sonu.spica.ui.theme.F
import com.sonu.spica.ui.theme.T
import kotlinx.coroutines.launch
import com.sonu.spica.ui.common.Glyph
import com.sonu.spica.ui.common.PhBold

private val GroupShape = RoundedCornerShape(14.dp)

/** A `›` that turns to point down when its row is open. */
@Composable
fun Chevron(open: Boolean) {
    val a by animateFloatAsState(if (open) 90f else 0f, label = "chev")
    Glyph(PhBold.caretRight, 11.dp, C.grey, Modifier.rotate(a))
}

/** A collapsible card. Folded, a header with the glance line; unfolded, its rows. */
@Composable
fun Group(title: String, summary: String, open: Boolean, onToggle: () -> Unit, content: @Composable ColumnScope.() -> Unit) {
    Column(Modifier.padding(top = 12.dp).fillMaxWidth().panel()) {
        Row(
            Modifier.fillMaxWidth().then(if (open) Modifier.bottomRule(C.lineSoft) else Modifier).tap(onClick = onToggle).padding(horizontal = 18.dp, vertical = 16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                Text(title, style = T.sans.copy(fontWeight = FontWeight.SemiBold, fontSize = 16.sp, lineHeight = 20.sp))
                if (!open) Text(summary, style = T.sans.copy(fontSize = 13.sp, lineHeight = 17.sp, color = C.faint))
            }
            Chevron(open)
        }
        if (open) content()
    }
}

/** One row's container: the hairline above (none on the first), and the editor under it. */
@Composable
fun Cell(first: Boolean = false, content: @Composable ColumnScope.() -> Unit) {
    Column(Modifier.fillMaxWidth().then(if (first) Modifier else Modifier.divider(18.dp, 18.dp)), content = content)
}

/** `dotted`: the value is an estimate — the amber dot before it. */
@Composable
fun RowButton(label: String, value: String?, sub: String? = null, open: Boolean, dotted: Boolean = false, onClick: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().tap(onClick = onClick).padding(horizontal = 18.dp, vertical = 16.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Text(label, style = T.sans.copy(fontSize = 15.sp, lineHeight = 19.sp, fontWeight = FontWeight.Medium), modifier = Modifier.weight(1f))
        Row(verticalAlignment = Alignment.CenterVertically) {
            if (dotted && value != null) Dot()
            Text(
                buildAnnotatedString {
                    append(value ?: "—")
                    sub?.let { withStyle(SpanStyle(color = C.faint)) { append(" $it") } }
                },
                style = T.sans.copy(fontSize = 14.5.sp, lineHeight = 18.sp, color = if (value == null) C.faint else C.muted),
            )
        }
        Chevron(open)
    }
}

@Composable
fun SaveButton(label: String, busy: Boolean = false, color: androidx.compose.ui.graphics.Color = C.brand, onClick: () -> Unit) {
    Box(Modifier.alpha(if (busy) 0.6f else 1f)) {
        if (color == C.red) ActionPill(label, onClick, PillKind.Danger, enabled = !busy) else ActionPill(label, onClick, PillKind.Primary, enabled = !busy)
    }
}

@Composable
fun QuietButton(label: String, color: androidx.compose.ui.graphics.Color = C.muted, onClick: () -> Unit) {
    if (color == C.red) ActionPill(label, onClick, PillKind.Danger) else ActionPill(label, onClick)
}

/**
 * The editor that opens under a row. Owns its draft; closes on success. On
 * refusal it stays open and says so — a value that did not land must never
 * look like it did.
 */
@Composable
fun Editor(
    initial: String,
    numeric: Boolean = false,
    decimal: Boolean = false,
    prefix: String? = null,
    suffix: String? = null,
    hint: String? = null,
    multiline: Boolean = false,
    onSave: suspend (String) -> Boolean,
    onClose: () -> Unit,
) {
    var draft by remember { mutableStateOf(initial) }
    var busy by remember { mutableStateOf(false) }
    var failed by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    fun save() {
        if (busy) return
        busy = true
        scope.launch {
            val ok = onSave(draft)
            busy = false
            if (ok) onClose() else failed = true
        }
    }
    Column(Modifier.padding(start = 18.dp, end = 18.dp, top = 2.dp, bottom = 16.dp)) {
        if (multiline) {
            InlineField(draft, { draft = it }, Modifier.fillMaxWidth(), mono = false, singleLine = false, autoFocus = true)
        }
        Row(Modifier.padding(top = if (multiline) 8.dp else 0.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            if (!multiline) {
                prefix?.let { Text(it, style = T.sans.copy(fontSize = 15.sp, color = C.muted)) }
                InlineField(
                    draft, { draft = it }, if (prefix != null || suffix != null) Modifier.width(120.dp) else Modifier.weight(1f),
                    numeric = numeric, decimal = decimal, autoFocus = true, onDone = ::save,
                )
                suffix?.let { Text(it, style = T.sans.copy(fontSize = 15.sp, color = C.muted)) }
            }
            Spacer(Modifier.weight(1f))
            QuietButton("Cancel", onClick = onClose)
            SaveButton(if (busy) "Saving…" else "Save", busy, onClick = ::save)
        }
        Text(
            if (failed) "Not saved — check the value, or the server refused." else hint ?: "",
            style = T.sans.copy(fontSize = 13.sp, lineHeight = 18.sp, color = if (failed) C.red else C.faint),
            modifier = Modifier.padding(top = 8.dp),
        )
    }
}

/**
 * The editor for a field that is one of a few values — gender, diet. A tap
 * on a value saves it; Clear empties the field. Like `Editor`, it stays open
 * and says so when the server refuses.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun ChoiceEditor(options: List<Pair<String, String>>, current: String?, onSave: suspend (String?) -> Boolean, onClose: () -> Unit) {
    var busy by remember { mutableStateOf(false) }
    var failed by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    fun save(value: String?) {
        if (busy) return
        busy = true
        scope.launch {
            val ok = onSave(value)
            busy = false
            if (ok) onClose() else failed = true
        }
    }
    Column(Modifier.padding(start = 18.dp, end = 18.dp, top = 2.dp, bottom = 16.dp)) {
        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            options.forEach { (value, label) -> FilterPill(label, value == current, { if (value != current) save(value) }) }
        }
        Row(Modifier.fillMaxWidth().padding(top = 12.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(
                if (failed) "Not saved — the server refused." else "",
                style = T.sans.copy(fontSize = 13.sp, lineHeight = 18.sp, color = C.red),
                modifier = Modifier.weight(1f),
            )
            if (current != null) QuietButton("Clear") { save(null) }
            QuietButton("Cancel", onClick = onClose)
        }
    }
}

/**
 * The editor for a date — the date of birth, shown everywhere else as an age.
 * A calendar, never an ISO string to type over: it opens straight away, and
 * Save stores the day picked. Cancel leaves the day as a pill that opens the
 * calendar again, with Clear beside it. Nothing after today can be picked.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DateEditor(current: String?, hint: String, onSave: suspend (String?) -> Boolean, onClose: () -> Unit) {
    var busy by remember { mutableStateOf(false) }
    var failed by remember { mutableStateOf(false) }
    var picking by remember { mutableStateOf(true) }
    val scope = rememberCoroutineScope()
    fun save(value: String?) {
        if (busy) return
        busy = true
        scope.launch {
            val ok = onSave(value)
            busy = false
            if (ok) onClose() else failed = true
        }
    }
    Column(Modifier.padding(start = 18.dp, end = 18.dp, top = 2.dp, bottom = 16.dp)) {
        val shape = RoundedCornerShape(12.dp)
        Row(
            Modifier.clip(shape).background(C.surface).tap { picking = true }.padding(horizontal = 14.dp, vertical = 11.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically,
        ) {
            Glyph(Ph.calendarBlank, 16.dp, C.muted)
            Text(current?.let(::longDay) ?: "Choose a day", style = T.sans.copy(fontSize = 15.sp, lineHeight = 18.sp, color = if (current == null) C.faint else C.ink))
        }
        Text(hint, style = T.sans.copy(fontSize = 12.5.sp, lineHeight = 17.sp, color = C.faint), modifier = Modifier.padding(top = 8.dp))
        Row(Modifier.fillMaxWidth().padding(top = 12.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(
                if (failed) "Not saved — the server refused." else "",
                style = T.sans.copy(fontSize = 13.sp, lineHeight = 18.sp, color = C.red),
                modifier = Modifier.weight(1f),
            )
            if (current != null) QuietButton("Clear") { save(null) }
            QuietButton("Cancel", onClick = onClose)
        }
    }
    if (picking) {
        val today = java.time.LocalDate.now()
        val state = rememberDatePickerState(
            initialSelectedDateMillis = current?.let(::utcMillis),
            // With nothing set, the calendar opens on a grown-up's year, not on today.
            initialDisplayedMonthMillis = utcMillis((current?.let(java.time.LocalDate::parse) ?: today.minusYears(25)).toString()),
            yearRange = 1920..today.year,
            selectableDates = object : SelectableDates {
                override fun isSelectableDate(utcTimeMillis: Long) = utcTimeMillis <= utcMillis(today.toString())
                override fun isSelectableYear(year: Int) = year <= today.year
            },
        )
        val words = T.sans.copy(fontSize = 14.sp, fontWeight = FontWeight.Medium)
        // Material draws the calendar; its words are Spica's face, its colours Spica's tokens.
        MaterialTheme(colorScheme = MaterialTheme.colorScheme, typography = SpicaType) {
            DatePickerDialog(
                onDismissRequest = { picking = false },
                confirmButton = {
                    TextButton(onClick = { state.selectedDateMillis?.let { picking = false; save(isoDay(it)) } }, enabled = state.selectedDateMillis != null) {
                        Text("Save", style = words.copy(color = if (state.selectedDateMillis != null) C.brand else C.faint))
                    }
                },
                dismissButton = { TextButton(onClick = { picking = false }) { Text("Cancel", style = words.copy(color = C.muted)) } },
                colors = DatePickerDefaults.colors(containerColor = C.white),
            ) {
                // No pencil: it switches to typing the date, which is what the calendar replaces.
                DatePicker(
                    state,
                    showModeToggle = false,
                    title = { Text("Date of birth", style = T.sans.copy(fontSize = 13.sp, color = C.muted), modifier = Modifier.padding(start = 24.dp, top = 16.dp)) },
                    colors = DatePickerDefaults.colors(
                        containerColor = C.white, selectedDayContainerColor = C.brand, selectedYearContainerColor = C.brand,
                        todayDateBorderColor = C.brand, todayContentColor = C.brand, headlineContentColor = C.ink,
                    ),
                )
            }
        }
    }
}

/** Material's styles in Spica's sans — the calendar's numbers and words match the rest of the app. */
private val SpicaType: Typography = Typography().run {
    val f = F.sans
    Typography(
        displayLarge = displayLarge.copy(fontFamily = f), displayMedium = displayMedium.copy(fontFamily = f), displaySmall = displaySmall.copy(fontFamily = f),
        headlineLarge = headlineLarge.copy(fontFamily = f), headlineMedium = headlineMedium.copy(fontFamily = f), headlineSmall = headlineSmall.copy(fontFamily = f),
        titleLarge = titleLarge.copy(fontFamily = f), titleMedium = titleMedium.copy(fontFamily = f), titleSmall = titleSmall.copy(fontFamily = f),
        bodyLarge = bodyLarge.copy(fontFamily = f), bodyMedium = bodyMedium.copy(fontFamily = f), bodySmall = bodySmall.copy(fontFamily = f),
        labelLarge = labelLarge.copy(fontFamily = f), labelMedium = labelMedium.copy(fontFamily = f), labelSmall = labelSmall.copy(fontFamily = f),
    )
}

/** The picker counts days as UTC midnights; a day of birth has no time zone. */
private fun utcMillis(iso: String): Long = java.time.LocalDate.parse(iso).atStartOfDay(java.time.ZoneOffset.UTC).toInstant().toEpochMilli()
private fun isoDay(millis: Long): String = java.time.Instant.ofEpochMilli(millis).atZone(java.time.ZoneOffset.UTC).toLocalDate().toString()

/** `1 Jan 1998` — a birthday with its year, the month at three letters. */
private fun longDay(iso: String): String =
    runCatching { java.time.LocalDate.parse(iso).format(java.time.format.DateTimeFormatter.ofPattern("d MMM yyyy", java.util.Locale.ENGLISH)) }.getOrDefault(iso)

/** The web's `<select>`, as a field-shaped pill that opens a small menu. */
@Composable
fun SelectPill(value: String, options: List<String>, modifier: Modifier = Modifier, onPick: (String) -> Unit) {
    var open by remember { mutableStateOf(false) }
    // Shaped like the kit's fields: the surface well, a caret in it.
    val shape = RoundedCornerShape(12.dp)
    Box {
        Row(
            modifier.clip(shape).background(C.surface).tap { open = true }.padding(horizontal = 14.dp, vertical = 11.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(value, style = T.sans.copy(fontSize = 15.sp, lineHeight = 18.sp))
            Glyph(PhBold.caretDown, 10.dp, C.muted)
        }
        if (open) {
            Popover(onDismiss = { open = false }, alignment = Alignment.TopStart, offset = IntOffset(0, with(LocalDensity.current) { 44.dp.roundToPx() }), minWidth = 140.dp) {
                options.forEach { o -> MenuRow(MenuItem(o, o, color = if (o == value) C.brand else C.ink) { onPick(o) }) { open = false } }
            }
        }
    }
}
