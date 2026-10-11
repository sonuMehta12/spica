package com.sonu.spica.ui.profile

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.em
import androidx.compose.ui.unit.sp
import com.sonu.spica.data.Api
import com.sonu.spica.data.ProjectRow
import com.sonu.spica.lib.Fmt
import com.sonu.spica.logic.FieldId
import com.sonu.spica.logic.Kind
import com.sonu.spica.logic.ProfileEdit
import com.sonu.spica.state.AppState
import com.sonu.spica.state.ProfileGroup
import com.sonu.spica.state.SpicaViewModel
import com.sonu.spica.ui.chat.bottomRule
import com.sonu.spica.ui.common.AddRow
import com.sonu.spica.ui.common.Back
import com.sonu.spica.ui.common.BackStep
import com.sonu.spica.ui.common.Coin
import com.sonu.spica.ui.common.Dot
import com.sonu.spica.ui.common.Ground
import com.sonu.spica.ui.common.LocalOnTop
import com.sonu.spica.ui.common.PageHeader
import com.sonu.spica.ui.common.Switch
import com.sonu.spica.ui.common.TopFade
import com.sonu.spica.ui.common.panel
import androidx.compose.ui.draw.rotate
import com.sonu.spica.ui.common.InlineField
import com.sonu.spica.ui.common.fadeUp
import com.sonu.spica.ui.common.plainTap
import com.sonu.spica.ui.common.tap
import com.sonu.spica.ui.home.UserAvatar
import com.sonu.spica.ui.home.topRule
import com.sonu.spica.ui.theme.C
import com.sonu.spica.ui.theme.T
import kotlinx.coroutines.launch
import com.sonu.spica.ui.common.Glyph
import com.sonu.spica.ui.common.Ph
import com.sonu.spica.ui.common.PhBold
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.border
import com.sonu.spica.lib.Day

/**
 * Drawer → Profile. Quick edit, the way a settings app does it: tap a row and
 * it opens into a small editor right there. Two levels — seven group tiles,
 * each with a one-line glance, and a group pushed over the grid as a page of
 * its own; a deep link (Nudges' *Change when nudges come*) pushes the group
 * alone, so its ← names where you came from. Unset values show as a dash,
 * never an invented default. Port of `ProfilePage.tsx`.
 */
@Composable
fun ProfilePage(vm: SpicaViewModel, s: AppState, group: ProfileGroup?, back: Back, composer: (@Composable () -> Unit)?) {
    val p = s.profile
    var open by remember { mutableStateOf<String?>(null) }
    var projects by remember { mutableStateOf<List<ProjectRow>?>(null) }
    val scope = rememberCoroutineScope()
    // Back closes the open editor before it leaves the group.
    BackStep(open != null) { open = null }

    suspend fun loadProjects() {
        projects = try { Api.fetchProjects() } catch (_: Exception) { projects ?: emptyList() }
    }
    // On top, and on top again: the projects are read afresh when a group is popped off it.
    val top = LocalOnTop.current
    LaunchedEffect(top) { if (top) loadProjects() }
    val projectsChanged: () -> Unit = {
        scope.launch { loadProjects() }
        vm.reloadDeckAsync()
    }

    fun toggle(id: String) { open = if (open == id) null else id }

    val latest = s.weighIns.firstOrNull()

    @Composable
    fun fieldRows(fields: List<FieldId>, firstIsFirst: Boolean = true) {
        fields.forEachIndexed { i, f ->
            val ask = ProfileEdit.inputFor(f)
            Cell(first = firstIsFirst && i == 0) {
                RowButton(f.label, ProfileEdit.formatValue(f, p), open = open == f.id, onClick = { toggle(f.id) })
                if (open == f.id) {
                    if (f.kind == Kind.Choice) {
                        ChoiceEditor(ProfileEdit.options(f), ProfileEdit.raw(f, p) as String?, onSave = { v -> vm.saveField(f, v ?: "") }, onClose = { open = null })
                    } else if (f.kind == Kind.Date) {
                        DateEditor(ProfileEdit.raw(f, p) as String?, ask.hint, onSave = { v -> vm.saveField(f, v ?: "") }, onClose = { open = null })
                    } else {
                        // Saved empty, a field is cleared — every one but the name and the timezone.
                        val hint = listOf(ask.hint, if (f.clearable && ProfileEdit.raw(f, p) != null) "Save it empty to clear it." else "").filter { it.isNotEmpty() }.joinToString(" ")
                        Editor(
                            ProfileEdit.draftValue(f, p), numeric = ask.numeric, decimal = ask.decimal, prefix = ask.prefix,
                            suffix = ask.suffix, hint = hint, onSave = { raw -> vm.saveField(f, raw) }, onClose = { open = null },
                        )
                    }
                }
            }
        }
    }

    @Composable
    fun ColumnScope.groupBody(g: ProfileGroup) {
        when (g) {
            ProfileGroup.Finance -> fieldRows(ProfileEdit.FINANCE)
            ProfileGroup.Health -> {
                fieldRows(ProfileEdit.HEALTH)
                HabitsSection(vm, s, open, ::toggle) { open = null }
            }
            // Projects: made here, placed into by chat and the work sync alike.
            ProfileGroup.Projects -> ProjectsSection(projects ?: emptyList(), open, ::toggle, { open = null }, projectsChanged)
            ProfileGroup.Runs -> {
                if (s.schedules.isEmpty()) Text("Nothing runs on its own yet.", style = T.sans.copy(fontSize = 15.sp), modifier = Modifier.padding(horizontal = 18.dp, vertical = 14.dp))
                s.schedules.forEachIndexed { i, sc ->
                    Cell(first = i == 0) {
                        Row(verticalAlignment = Alignment.Top) {
                            Column(Modifier.weight(1f).tap { toggle("sched:${sc.id}") }.padding(horizontal = 18.dp, vertical = 15.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                                Text(sc.label + if (sc.pending) " · saving" else "", style = T.sans.copy(fontSize = 15.sp))
                                // A failure outranks everything: a job that silently stopped is worse than none.
                                Text(
                                    when {
                                        sc.lastError != null -> "failed · ${sc.lastError.take(40)}"
                                        !sc.enabled -> "off"
                                        sc.lastRunDay != null -> "${sc.repeat} · last run ${Day.cardDay(sc.lastRunDay)}"
                                        else -> "${sc.repeat} · ${sc.blurb.lowercase()}"
                                    },
                                    style = T.mono.copy(fontSize = 12.5.sp, color = if (sc.lastError != null) C.red else C.muted),
                                )
                            }
                            Text(sc.at, style = T.figure.copy(fontSize = 16.sp, fontWeight = FontWeight.SemiBold, color = if (sc.enabled) C.ink else C.faint), modifier = Modifier.padding(horizontal = 8.dp, vertical = 15.dp))
                            Box(Modifier.padding(top = 13.dp, end = 16.dp)) {
                                Switch(sc.enabled, { scope.launch { vm.editSchedule(sc.id, enabled = !sc.enabled) } }, sc.label)
                            }
                        }
                        if (open == "sched:${sc.id}") {
                            Editor(
                                sc.at, hint = "24-hour clock, your time. A run missed while the app was closed still happens when it next opens.",
                                onSave = { raw ->
                                    val t = raw.trim()
                                    if (!Regex("^\\d{1,2}:\\d{2}$").matches(t)) false else vm.editSchedule(sc.id, at = t.padStart(5, '0'))
                                },
                                onClose = { open = null },
                            )
                        }
                    }
                }
            }
            ProfileGroup.Weight -> {
                fieldRows(ProfileEdit.WEIGHT)
                Cell {
                    RowButton(
                        if (latest != null) "Last weigh-in" else "Weigh-in",
                        latest?.let { "${Fmt.num(it.kg)} kg" },
                        latest?.let { "· ${Day.cardDay(it.day)}${if (it.pending) " · saving" else if (it.failed) " · unsaved" else ""}" },
                        open == "weigh-in",
                        dotted = latest?.estimated == true,
                    ) { toggle("weigh-in") }
                    if (open == "weigh-in") {
                        Editor(
                            latest?.let { Fmt.num(it.kg) } ?: "", numeric = true, decimal = true, suffix = "kg",
                            hint = "Today's weight. A second reading today replaces the first.",
                            onSave = vm::saveWeighIn, onClose = { open = null },
                        )
                    }
                }
                WeighIns(vm, s)
            }
            ProfileGroup.About -> fieldRows(ProfileEdit.ABOUT)
            ProfileGroup.Memory -> MemorySection(vm, s, open, ::toggle) { open = null }
        }
    }

    Box(Modifier.fillMaxSize().background(Ground).plainTap { }.imePadding()) {
        Column(Modifier.fillMaxSize().statusBarsPadding().padding(top = 8.dp).fadeUp(280)) {
            val g = group
            if (g == null) {
                // The signed-in address: which account is this, before anyone signs out.
                PageHeader(null, p.displayName.ifEmpty { "Profile" }, back, sub = p.email ?: "Tap a group to change it", lead = { UserAvatar(p.displayName, p.avatarUrl, 56.dp) })
            } else {
                val (ink, tint) = g.coin
                PageHeader("Profile", g.title, back, lead = { Coin(g.icon, ink, tint, 48.dp) })
            }

            Box(Modifier.weight(1f)) {
                Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(start = 16.dp, end = 16.dp, top = 14.dp, bottom = 110.dp)) {
                    if (g == null) {
                        ProfileGrid(vm::openProfileGroup)
                    } else {
                        Column(Modifier.fillMaxWidth().panel()) { groupBody(g) }
                    }
                }
                TopFade()
            }
        }
        if (composer != null) Box(Modifier.align(Alignment.BottomCenter)) { composer() }
    }
}


/** A group's coin: a domain's ink and tint where it belongs to one, the neutral surface where it does not. */
private val ProfileGroup.coin get() = when (this) {
    ProfileGroup.Finance -> C.paisaInk to C.paisaTint
    ProfileGroup.Health, ProfileGroup.Weight -> C.dietInk to C.dietTint
    ProfileGroup.Projects -> C.workInk to C.workTint
    ProfileGroup.Runs, ProfileGroup.About, ProfileGroup.Memory -> C.ink to C.surface
}

/** A group's name — its page's title, and what the ← of a page over it says. */
internal val ProfileGroup.title get() = when (this) {
    ProfileGroup.Finance -> "Finance"
    ProfileGroup.Health -> "Health"
    ProfileGroup.Projects -> "Projects"
    ProfileGroup.Runs -> "Daily runs"
    ProfileGroup.Weight -> "Weight"
    ProfileGroup.About -> "About you"
    ProfileGroup.Memory -> "Memory"
}

private val ProfileGroup.icon get() = when (this) {
    ProfileGroup.Finance -> Ph.wallet
    ProfileGroup.Health -> Ph.heartbeat
    ProfileGroup.Projects -> Ph.kanban
    ProfileGroup.Runs -> Ph.alarm
    ProfileGroup.Weight -> Ph.scales
    ProfileGroup.About -> Ph.identificationCard
    ProfileGroup.Memory -> Ph.brain
}

/**
 * The groups as tiles, two to a row: an icon and the name, nothing else —
 * what a group holds is one tap away, and the heading is enough to find it.
 */
@Composable
private fun ProfileGrid(onOpen: (ProfileGroup) -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        ProfileGroup.entries.chunked(2).forEach { pair ->
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                pair.forEach { g ->
                    Column(
                        Modifier
                            .weight(1f)
                            .panel()
                            .tap { onOpen(g) }
                            .padding(16.dp),
                    ) {
                        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.Top) {
                            val (ink, tint) = g.coin
                            Coin(g.icon, ink, tint, 40.dp)
                            Spacer(Modifier.weight(1f))
                            Glyph(PhBold.caretRight, 11.dp, C.grey, Modifier.padding(top = 6.dp))
                        }
                        Text(g.title, style = T.sans.copy(fontSize = 16.sp, lineHeight = 20.sp, fontWeight = FontWeight.SemiBold), modifier = Modifier.padding(top = 14.dp))
                    }
                }
                if (pair.size == 1) Spacer(Modifier.weight(1f))
            }
        }
    }
}

/**
 * Every reading, newest first, each with its own delete — the reading goes,
 * and the day's copy of it with it. One said as a guess keeps its dot.
 */
@Composable
private fun WeighIns(vm: SpicaViewModel, s: AppState) {
    if (s.weighIns.isEmpty()) return
    Text("Weigh-ins", style = T.sans.copy(fontSize = 14.sp, lineHeight = 18.sp, fontWeight = FontWeight.SemiBold), modifier = Modifier.fillMaxWidth().background(C.surface).padding(horizontal = 18.dp, vertical = 12.dp))
    s.weighIns.forEachIndexed { i, w ->
        Cell(first = i == 0) {
            Row(Modifier.fillMaxWidth().padding(start = 18.dp), verticalAlignment = Alignment.CenterVertically) {
                Text(
                    Day.cardDay(w.day) + if (w.pending) " · saving" else if (w.failed) " · unsaved" else "",
                    style = T.sans.copy(fontSize = 15.sp), modifier = Modifier.weight(1f).padding(vertical = 15.dp),
                )
                if (w.estimated) Dot()
                Text("${Fmt.num(w.kg)} kg", style = T.figure.copy(fontSize = 15.sp))
                Glyph(Ph.x, 15.dp, C.faint, Modifier.padding(start = 4.dp).clip(CircleShape).tap { vm.deleteWeighIn(w.id) }.padding(horizontal = 14.dp, vertical = 15.dp), label = "Delete this weigh-in")
            }
        }
    }
}

@Composable
private fun HabitsSection(vm: SpicaViewModel, s: AppState, open: String?, toggle: (String) -> Unit, close: () -> Unit) {
    val scope = rememberCoroutineScope()
    Text("Habits", style = T.sans.copy(fontSize = 14.sp, lineHeight = 18.sp, fontWeight = FontWeight.SemiBold), modifier = Modifier.fillMaxWidth().background(C.surface).padding(start = 18.dp, end = 18.dp, top = 12.dp, bottom = 12.dp))
    if (s.habits.isEmpty()) {
        Text(
            "Nothing tracked yet. A habit is a yes-or-no you tick each day — gym, cigarettes, meditation — and the week strip on the deck counts it.",
            style = T.sans.copy(fontSize = 15.sp), modifier = Modifier.padding(horizontal = 18.dp, vertical = 6.dp),
        )
    }
    s.habits.forEach { h ->
        Cell {
            Row(verticalAlignment = Alignment.Top) {
                Column(Modifier.weight(1f).tap { toggle("habit:${h.id}") }.padding(horizontal = 18.dp, vertical = 15.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                    Text(h.name + if (h.pending) " · saving" else "", style = T.sans.copy(fontSize = 15.sp))
                    Text("${h.direction}${h.unit?.let { " · $it" } ?: ""} · ${h.daysThisWeek}/7 this week", style = T.mono.copy(fontSize = 12.5.sp, color = C.muted))
                }
                // Up is something you want more of; down, less.
                Box(Modifier.padding(top = 10.dp).size(34.dp).clip(CircleShape).background(if (h.direction == "build") C.brandTint else C.redTint).tap { vm.flipHabit(h) }, contentAlignment = Alignment.Center) {
                    Glyph(Ph.arrowUp, 17.dp, if (h.direction == "build") C.brand else C.red, Modifier.rotate(if (h.direction == "build") 0f else 180f), label = if (h.direction == "build") "Build — tap to flip" else "Break — tap to flip")
                }
                Glyph(Ph.x, 17.dp, C.grey, Modifier.padding(top = 4.dp).clip(CircleShape).tap { vm.removeHabit(h.id) }.padding(horizontal = 14.dp, vertical = 15.dp), label = "Stop tracking")
            }
            if (open == "habit:${h.id}") {
                Editor(
                    h.name, hint = if (h.loggedEver > 0) "Ticked ${h.loggedEver}× so far. Renaming keeps every one." else "Never ticked yet.",
                    onSave = { name -> vm.editHabit(h.id, name = name) }, onClose = close,
                )
            }
        }
    }
    Cell {
        AddRow("Track a habit", { toggle("habit:new") })
        if (open == "habit:new") {
            var name by remember { mutableStateOf("") }
            var direction by remember { mutableStateOf("build") }
            var unit by remember { mutableStateOf("") }
            fun add() {
                val n = name.trim()
                if (n.isEmpty()) return
                scope.launch {
                    // Blank means a tick is the whole fact — NULL, never an empty string.
                    if (vm.addHabit(n, direction, unit.trim().ifEmpty { null })) close()
                }
            }
            Column(Modifier.padding(start = 18.dp, end = 18.dp, top = 2.dp, bottom = 16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                    InlineField(name, { name = it }, Modifier.weight(1f), placeholder = "Meditation", autoFocus = true)
                    SelectPill(direction, listOf("build", "break")) { direction = it }
                }
                InlineField(unit, { unit = it }, Modifier.fillMaxWidth(), placeholder = "unit — minutes, units… or leave blank", onDone = ::add)
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp, Alignment.End)) {
                    QuietButton("Cancel", onClick = close)
                    SaveButton("Track it", onClick = ::add)
                }
            }
        }
    }
}

@Composable
private fun MemorySection(vm: SpicaViewModel, s: AppState, open: String?, toggle: (String) -> Unit, close: () -> Unit) {
    val scope = rememberCoroutineScope()
    if (s.memories.isEmpty()) {
        Text(
            "Nothing remembered yet. Facts about you — profession, how you like answers — live here, one per line, and any agent you connect reads them from this one place.",
            style = T.sans.copy(fontSize = 15.sp), modifier = Modifier.padding(start = 18.dp, end = 18.dp, top = 12.dp, bottom = 4.dp),
        )
    }
    s.memories.forEachIndexed { i, m ->
        Cell(first = i == 0) {
            Row(verticalAlignment = Alignment.Top) {
                Column(Modifier.weight(1f).tap { toggle("memory:${m.id}") }.padding(horizontal = 18.dp, vertical = 15.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        // Nobody has said "still true": the value is inferred, so it wears the dot.
                        if (m.confirmedAt == null) Dot()
                        Text(
                            "${m.slug} · ${m.kind}${if (m.pending) " · saving" else if (m.failed) " · unsaved" else ""}",
                            style = T.mono.copy(fontSize = 12.5.sp, color = C.muted),
                        )
                    }
                    Text(m.text, style = T.sans.copy(fontSize = 15.sp), maxLines = if (open == "memory:${m.id}") Int.MAX_VALUE else 2, overflow = TextOverflow.Ellipsis)
                }
                Glyph(Ph.x, 15.dp, C.faint, Modifier.clip(CircleShape).tap { vm.removeMemory(m.id) }.padding(horizontal = 12.dp, vertical = 11.dp))
            }
            if (open == "memory:${m.id}") {
                Editor(m.text, multiline = true, hint = "Save keeps the new text.", onSave = { t -> vm.saveMemory(m.id, t) }, onClose = close)
            }
        }
    }
    Cell {
        AddRow("Add memory", { toggle("memory:new") })
        if (open == "memory:new") {
            var slug by remember { mutableStateOf("") }
            var kind by remember { mutableStateOf("preference") }
            var text by remember { mutableStateOf("") }
            var failed by remember { mutableStateOf(false) }
            fun add() = scope.launch { if (vm.addMemory(slug, kind, text)) close() else failed = true }
            Column(Modifier.padding(start = 18.dp, end = 18.dp, top = 2.dp, bottom = 16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                    InlineField(slug, { slug = it }, Modifier.weight(1f), placeholder = "slug, like profession", autoFocus = true)
                    SelectPill(kind, ProfileEdit.MEMORY_KINDS) { kind = it }
                }
                InlineField(text, { text = it }, Modifier.fillMaxWidth(), placeholder = "The fact, in your words", mono = false, singleLine = false)
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(
                        if (failed) "Not saved — slug is lowercase letters, digits and dashes; the fact cannot be empty." else "Same slug as an existing memory updates it.",
                        style = T.sans.copy(fontSize = 13.sp, color = if (failed) C.red else C.muted), modifier = Modifier.weight(1f),
                    )
                    QuietButton("Cancel", onClick = close)
                    SaveButton("Save") { add() }
                }
            }
        }
    }
}
