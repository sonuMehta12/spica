package com.sonu.spica.ui.data

import androidx.compose.ui.Alignment
import com.sonu.spica.ui.common.ActionPill
import com.sonu.spica.ui.common.AddRow
import com.sonu.spica.ui.common.BackStep
import com.sonu.spica.ui.common.FilterPill
import com.sonu.spica.ui.common.Glyph
import com.sonu.spica.ui.common.Ph
import com.sonu.spica.ui.common.PhBold
import com.sonu.spica.ui.common.PillKind
import com.sonu.spica.ui.common.divider
import android.content.Intent
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.em
import androidx.compose.ui.unit.sp
import androidx.core.net.toUri
import com.sonu.spica.data.ExerciseRow
import com.sonu.spica.data.body
import com.sonu.spica.lib.Day
import com.sonu.spica.state.AppState
import com.sonu.spica.state.SpicaViewModel
import com.sonu.spica.ui.common.InlineField
import com.sonu.spica.ui.common.fadeUp
import com.sonu.spica.ui.common.tap
import com.sonu.spica.ui.home.topRule
import com.sonu.spica.ui.profile.SelectPill
import com.sonu.spica.ui.report.Card
import com.sonu.spica.ui.report.reportCard
import com.sonu.spica.ui.theme.C
import com.sonu.spica.ui.theme.T
import kotlinx.coroutines.launch

private val KINDS = listOf("strength", "cardio", "mobility", "stretch")

private enum class WorkoutTab { All, Done, New }

/** The add form's draft — every field a string until it is sent, as the web's is. */
private data class ExerciseDraft(
    val name: String = "",
    val kind: String = "strength",
    val muscleGroup: String = "",
    val equipment: String = "",
    val minutes: String = "",
    val steps: String = "",
    val sourceUrl: String = "",
)

private class ExerciseField(
    val label: String,
    val placeholder: String,
    val get: (ExerciseDraft) -> String,
    val set: (ExerciseDraft, String) -> ExerciseDraft,
    val numeric: Boolean = false,
)

private val FIELDS = listOf(
    ExerciseField("Name", "Copenhagen plank", { it.name }, { d, v -> d.copy(name = v) }),
    ExerciseField("Muscle group", "legs, chest, core…", { it.muscleGroup }, { d, v -> d.copy(muscleGroup = v) }),
    ExerciseField("Equipment", "barbell, bodyweight, none…", { it.equipment }, { d, v -> d.copy(equipment = v) }),
    ExerciseField("Minutes", "10", { it.minutes }, { d, v -> d.copy(minutes = v) }, numeric = true),
    ExerciseField("How to", "what to actually do", { it.steps }, { d, v -> d.copy(steps = v) }),
    ExerciseField("Link", "the YouTube or Instagram link", { it.sourceUrl }, { d, v -> d.copy(sourceUrl = v) }),
)

/** Only values the library actually has — an empty filter is a dead end. */
private class ExerciseOptions(val kind: List<String>, val muscle: List<String>, val gear: List<String>)

private fun optionsOf(exercises: List<ExerciseRow>) = ExerciseOptions(
    kind = KINDS.filter { k -> exercises.any { it.kind == k } },
    muscle = exercises.mapNotNull { it.muscleGroup?.takeIf(String::isNotEmpty) }.distinct().sorted(),
    gear = exercises.mapNotNull { it.equipment?.takeIf(String::isNotEmpty) }.distinct().sorted(),
)

private val FieldText = T.sans.copy(fontSize = 14.sp)

/** A field's tiny mono caps label. */
@Composable
private fun FieldLabel(text: String) {
    Text(
        text,
        style = T.mono.copy(fontSize = 12.5.sp, color = C.muted),
        modifier = Modifier.padding(bottom = 4.dp),
    )
}

/** The mono pill every control here is drawn as: tabs, filter chips, Clear, +1, Add, Cancel. */
@Composable
private fun Pill(
    text: String,
    fg: Color,
    bg: Color,
    line: Color?,
    modifier: Modifier = Modifier,
    radius: Dp = 14.dp,
    h: Dp = 12.dp,
    v: Dp = 5.dp,
    enabled: Boolean = true,
    onClick: () -> Unit,
) {
    // A pill, as the kit draws them: no drawn edge — paper becomes the surface tint.
    val shape = RoundedCornerShape(50)
    Text(
        text,
        style = T.sans.copy(fontSize = 16.sp, lineHeight = 20.4.sp, fontWeight = androidx.compose.ui.text.font.FontWeight.Medium, color = fg),
        maxLines = 1,
        softWrap = false,
        modifier = modifier
            .clip(shape)
            .background(if (bg == C.paper) C.surface else bg)
            .tap(enabled = enabled, onClick = onClick)
            .padding(horizontal = 14.dp, vertical = 8.dp),
    )
}

@Composable
private fun TabChip(on: Boolean, text: String, onClick: () -> Unit) = FilterPill(text, on, onClick)

/** One filter row. Tapping the lit chip again turns that filter off. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun FilterGroup(name: String, values: List<String>, current: String?, onPick: (String?) -> Unit) {
    Column(Modifier.padding(bottom = 10.dp)) {
        FieldLabel(name)
        FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            values.forEach { v -> TabChip(current == v, v) { onPick(if (current == v) null else v) } }
        }
    }
}

/**
 * Your data → Workouts. spec/done/workouts.md. Port of `WorkoutsSection.tsx`.
 *
 * A **library**, the way Dishes is one — what exists to suggest from, not a
 * record of what happened. *"Aaj leg lagana hai"* is a muscle-group query;
 * what the library does not hold, the agent finds and offers to keep.
 *
 * There is no session list, and that is the point of the 2026-09-07 revert: a
 * workout is logged as a habit, yes or no, the same as a cigarette. The Diet
 * card's strip still shows the days.
 *
 * `tried` is the only stored count in the app, because it is the only one with
 * no ledger under it — a declaration, not a measurement. 0 means bookmarked
 * but never done.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun WorkoutsSection(vm: SpicaViewModel, s: AppState) {
    val exercises = s.exercises
    val context = LocalContext.current
    val scope = rememberCoroutineScope()

    var view by remember { mutableStateOf(WorkoutTab.All) }
    var filterOpen by remember { mutableStateOf(false) }
    // Three independent filters rather than one shared slot: "cardio, at home"
    // is a real question and one slot could not hold it.
    var kind by remember { mutableStateOf<String?>(null) }
    var muscle by remember { mutableStateOf<String?>(null) }
    var gear by remember { mutableStateOf<String?>(null) }
    var q by remember { mutableStateOf("") }
    var open by remember { mutableStateOf<String?>(null) }
    var adding by remember { mutableStateOf(false) }
    var form by remember { mutableStateOf(ExerciseDraft()) }
    var busy by remember { mutableStateOf(false) }

    val options = remember(exercises) { optionsOf(exercises) }
    val active = listOfNotNull(kind, muscle, gear).size

    val shown = remember(exercises, view, kind, muscle, gear, q) {
        val hit = q.trim().lowercase()
        exercises.filter { e ->
            (view == WorkoutTab.All || (if (view == WorkoutTab.Done) e.tried > 0 else e.tried == 0)) &&
                (kind == null || e.kind == kind) &&
                (muscle == null || e.muscleGroup == muscle) &&
                (gear == null || e.equipment == gear) &&
                (hit.isEmpty() || e.name.lowercase().contains(hit) || e.aliases.any { it.contains(hit) })
        }
    }
    val done = exercises.count { it.tried > 0 }

    // Back closes what is open before it leaves the section — the add form,
    // then an open exercise on screen, then the filters. The last one listed goes first.
    BackStep(filterOpen) { filterOpen = false }
    BackStep(open != null && shown.any { it.id == open }) { open = null }
    BackStep(adding) { adding = false }

    fun add() {
        val f = form
        val name = f.name.trim()
        if (name.isEmpty() || busy) return
        busy = true
        scope.launch {
            val ok = vm.addExercise(
                body(
                    "name" to name,
                    "kind" to f.kind.ifEmpty { null },
                    "muscle_group" to f.muscleGroup.trim().ifEmpty { null },
                    "equipment" to f.equipment.trim().ifEmpty { null },
                    // Anything that is not a whole number goes as null, as the web's Number() → NaN → null does.
                    "typical_minutes" to f.minutes.trim().toIntOrNull(),
                    "steps" to f.steps.trim().ifEmpty { null },
                    "source_url" to f.sourceUrl.trim().ifEmpty { null },
                ),
            )
            busy = false
            if (ok) {
                form = ExerciseDraft()
                adding = false
            }
        }
    }

    // Three tabs and nothing else. Kind, muscle and equipment were two rows of
    // chips on arrival — noise before anyone had asked a question — so they
    // live behind Filter, which counts itself when it is on. A FlowRow so a
    // narrow phone wraps Filter to a second line rather than clipping it.
    FlowRow(
        Modifier.fillMaxWidth().padding(bottom = 6.dp),
        horizontalArrangement = Arrangement.spacedBy(7.dp),
        verticalArrangement = Arrangement.spacedBy(7.dp),
    ) {
        TabChip(view == WorkoutTab.All, "All · ${exercises.size}") { view = WorkoutTab.All }
        TabChip(view == WorkoutTab.Done, "Done · $done") { view = WorkoutTab.Done }
        TabChip(view == WorkoutTab.New, "Not tried · ${exercises.size - done}") { view = WorkoutTab.New }
        Spacer(Modifier.weight(1f))
        // Green whenever a filter is on, open or shut: a filtered list that
        // looks unfiltered is a lie by omission.
        val lit = active > 0 || filterOpen
        Pill(
            if (active > 0) "Filter · $active" else "Filter",
            fg = if (lit) C.brand else C.muted,
            bg = if (active > 0) C.brandTint else C.paper,
            line = if (lit) C.brand else C.border,
        ) { filterOpen = !filterOpen }
    }

    if (filterOpen) {
        Column(
            Modifier.padding(bottom = 6.dp).fadeUp(180).fillMaxWidth().reportCard().clip(Card)
                .padding(start = 18.dp, end = 18.dp, top = 11.dp, bottom = 13.dp),
        ) {
            FilterGroup("Type", options.kind, kind) { kind = it }
            FilterGroup("Muscle group", options.muscle, muscle) { muscle = it }
            FilterGroup("Equipment", options.gear, gear) { gear = it }
            Pill(
                "Clear",
                fg = if (active > 0) C.muted else C.faint,
                bg = C.paper,
                line = if (active > 0) C.border else C.line,
                radius = 12.dp,
                enabled = active > 0,
            ) {
                kind = null
                muscle = null
                gear = null
            }
        }
    }

    Column(Modifier.fillMaxWidth().reportCard().clip(Card)) {
        InlineField(
            q, { q = it },
            Modifier.padding(start = 18.dp, end = 18.dp, top = 11.dp, bottom = 2.dp).fillMaxWidth(),
            placeholder = "Search — the name, or what you call it",
            mono = false,
            style = FieldText,
        )

        if (shown.isEmpty()) {
            Text(
                "Nothing matches.",
                style = T.sans.copy(fontSize = 15.sp, color = C.muted),
                modifier = Modifier.padding(horizontal = 18.dp, vertical = 14.dp),
            )
        }

        shown.forEachIndexed { i, e ->
            key(e.id) {
                Column(Modifier.fillMaxWidth().then(if (i > 0) Modifier.divider(18.dp, 18.dp) else Modifier)) {
                    Row(
                        Modifier.fillMaxWidth().padding(horizontal = 18.dp, vertical = 10.dp),
                        horizontalArrangement = Arrangement.spacedBy(9.dp),
                    ) {
                        Column(
                            Modifier.alignByBaseline().weight(1f).clip(RoundedCornerShape(6.dp))
                                .tap { open = if (open == e.id) null else e.id },
                        ) {
                            Text(e.name, style = T.sans.copy(fontSize = 15.sp))
                            // `.filter(Boolean)` on the web: an empty string is no part.
                            val meta = listOf(e.kind, e.muscleGroup, e.equipment).filter { !it.isNullOrEmpty() }.joinToString(" · ") +
                                (e.typicalMinutes?.let { " · ${it}m" } ?: "")
                            if (meta.isNotEmpty()) {
                                Text(meta, style = T.mono.copy(fontSize = 12.5.sp, color = C.faint), modifier = Modifier.padding(top = 3.dp))
                            }
                        }

                        // 0 is a real answer, not missing data — it says bookmarked,
                        // never done, which is exactly what the old star meant.
                        Row(Modifier.alignByBaseline(), horizontalArrangement = Arrangement.spacedBy(3.dp), verticalAlignment = Alignment.CenterVertically) {
                            if (e.tried > 0) Glyph(PhBold.check, 12.dp, C.dietInk, label = "Tried")
                            Text(
                                (if (e.tried > 0) "${e.tried}×" else "not tried") + (e.lastTried?.let { " · ${Day.shortDay(it)}" } ?: ""),
                                style = T.mono.copy(fontSize = 12.5.sp, color = if (e.tried > 0) C.dietInk else C.faint),
                                maxLines = 1,
                                softWrap = false,
                            )
                        }
                        Pill(
                            "+1",
                            fg = C.muted,
                            bg = C.paper,
                            line = C.border,
                            modifier = Modifier.alignByBaseline().semantics { contentDescription = "Did ${e.name} today" },
                            radius = 11.dp,
                            h = 9.dp,
                            v = 3.dp,
                        ) { vm.didExerciseOnce(e.id) }
                    }

                    if (open == e.id) {
                        Column(Modifier.fillMaxWidth().padding(start = 18.dp, end = 18.dp, bottom = 12.dp).fadeUp(200)) {
                            if (e.aliases.isNotEmpty()) {
                                Text("also: ${e.aliases.joinToString(" · ")}", style = T.mono.copy(fontSize = 12.5.sp, color = C.faint))
                            }
                            // Empty on the seeded rows on purpose: forty form guides
                            // written from memory is forty chances to teach a lift wrong.
                            Text(
                                e.steps ?: "No how-to yet — ask the agent and keep what it finds.",
                                style = T.sans.copy(fontSize = 13.sp, lineHeight = 21.4.sp, color = if (!e.steps.isNullOrEmpty()) C.muted else C.faint),
                                modifier = Modifier.padding(top = 6.dp),
                            )
                            if (!e.note.isNullOrEmpty()) {
                                Text(e.note, style = T.sans.copy(fontSize = 13.sp, color = C.muted), modifier = Modifier.padding(top = 5.dp))
                            }
                            val url = e.sourceUrl
                            if (!url.isNullOrEmpty()) {
                                // Underlined: the web draws it as a bare `<a>`; the arrow is Phosphor's, never a character.
                                Row(
                                    Modifier.padding(top = 7.dp).tap {
                                        // A link nothing on the phone can open must not take the page down with it.
                                        runCatching { context.startActivity(Intent(Intent.ACTION_VIEW, url.toUri())) }
                                    },
                                    horizontalArrangement = Arrangement.spacedBy(2.dp),
                                    verticalAlignment = Alignment.CenterVertically,
                                ) {
                                    Text("Watch it", style = T.mono.copy(fontSize = 15.sp, color = C.brand, textDecoration = TextDecoration.Underline))
                                    Glyph(Ph.arrowUpRight, 13.dp, C.brand)
                                }
                            }
                            Text("from ${e.source}", style = T.mono.copy(fontSize = 12.5.sp, color = C.faint), modifier = Modifier.padding(top = 7.dp))
                        }
                    }
                }
            }
        }

        Column(Modifier.fillMaxWidth().topRule()) {
            if (adding) {
                Column(Modifier.fillMaxWidth().padding(start = 18.dp, end = 18.dp, top = 2.dp, bottom = 13.dp).fadeUp(200)) {
                    FIELDS.forEach { f ->
                        Column(Modifier.padding(top = 10.dp)) {
                            FieldLabel(f.label)
                            InlineField(
                                f.get(form), { form = f.set(form, it) },
                                Modifier.fillMaxWidth(),
                                placeholder = f.placeholder,
                                numeric = f.numeric,
                                mono = false,
                                style = FieldText,
                            )
                        }
                    }
                    Column(Modifier.padding(top = 10.dp)) {
                        FieldLabel("Type")
                        SelectPill(form.kind, KINDS) { form = form.copy(kind = it) }
                    }
                    val canAdd = form.name.isNotBlank() && !busy
                    Row(Modifier.padding(top = 12.dp), horizontalArrangement = Arrangement.spacedBy(7.dp)) {
                        Pill(
                            "Add",
                            fg = if (canAdd) C.white else C.faint,
                            bg = if (canAdd) C.brand else C.line,
                            line = null,
                            radius = 12.dp,
                            h = 14.dp,
                            v = 6.dp,
                            enabled = canAdd,
                            onClick = ::add,
                        )
                        Pill("Cancel", fg = C.muted, bg = C.paper, line = C.border, radius = 12.dp, v = 6.dp) {
                            adding = false
                            form = ExerciseDraft()
                        }
                    }
                }
            } else {
                AddRow("Add an exercise", {
                    open = null
                    adding = true
                })
            }
        }
    }

    Text(
        "Whether you trained is a habit — yes or no, on the Diet card. This is the library the agent suggests from.",
        style = T.sans.copy(fontSize = 13.sp, lineHeight = 20.7.sp, color = C.muted),
        modifier = Modifier.padding(start = 2.dp, end = 2.dp, top = 10.dp),
    )
}
