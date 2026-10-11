package com.sonu.spica.ui.profile

import com.sonu.spica.ui.common.BackStep
import com.sonu.spica.ui.common.AddRow
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
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
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.em
import androidx.compose.ui.unit.sp
import com.sonu.spica.data.Api
import com.sonu.spica.data.Project
import com.sonu.spica.data.ProjectRow
import com.sonu.spica.data.body
import com.sonu.spica.data.status
import com.sonu.spica.ui.common.PROJECT_ICONS
import com.sonu.spica.ui.common.InlineField
import com.sonu.spica.ui.common.ProjectIcon
import com.sonu.spica.ui.common.tap
import com.sonu.spica.ui.theme.C
import com.sonu.spica.ui.theme.T
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/** Made here, placed into by chat and the work sync alike. spec/done/projects.md. */
@Composable
fun ProjectsSection(rows: List<ProjectRow>, open: String?, toggle: (String) -> Unit, close: () -> Unit, changed: () -> Unit) {
    val home = rows.firstOrNull { it.project.isDefault }
    Text(
        "A task lands in the project you name. When you name none, Spica puts it where one plainly fits — the description is what it reads — and anything else goes to ${home?.project?.name ?: "the default"}.",
        style = T.sans.copy(fontSize = 15.sp), modifier = Modifier.padding(start = 18.dp, end = 18.dp, top = 10.dp, bottom = 4.dp),
    )
    rows.forEachIndexed { i, r ->
        val pr = r.project
        Cell(first = i == 0) {
            Row(
                Modifier.fillMaxWidth().alpha(if (r.archived) 0.55f else 1f).tap { toggle("project:${pr.id}") }.padding(horizontal = 18.dp, vertical = 15.dp),
                verticalAlignment = Alignment.Top,
                horizontalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                Box(Modifier.padding(top = 1.dp)) { ProjectIcon(pr, 16.dp) }
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                    Text(pr.name, style = T.sans.copy(fontSize = 15.sp))
                    Text(
                        when {
                            pr.isDefault -> "default — tasks with no project land here"
                            r.archived -> "archived"
                            else -> pr.description?.ifEmpty { null } ?: "no description — add one so tasks can find it"
                        },
                        style = T.mono.copy(fontSize = 12.5.sp, color = C.muted),
                        maxLines = 1, overflow = TextOverflow.Ellipsis,
                    )
                }
                Text("${r.openTasks} open", style = T.mono.copy(fontSize = 15.sp, color = C.muted))
            }
            if (open == "project:${pr.id}") ProjectEditor(r, home, onDone = { close(); changed() }, onCancel = close)
        }
    }
    Cell {
        AddRow("New project", { toggle("project:new") })
        if (open == "project:new") ProjectEditor(null, home, onDone = { close(); changed() }, onCancel = close)
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun ProjectEditor(row: ProjectRow?, home: ProjectRow?, onDone: () -> Unit, onCancel: () -> Unit) {
    val pr = row?.project
    var name by remember { mutableStateOf(pr?.name ?: "") }
    var description by remember { mutableStateOf(pr?.description ?: "") }
    var icon by remember { mutableStateOf(pr?.icon ?: "") }
    var aliases by remember { mutableStateOf(pr?.aliases?.joinToString(", ") ?: "") }
    var busy by remember { mutableStateOf(false) }
    var note by remember { mutableStateOf("") }
    var confirmDelete by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    // Back is Keep while Delete is asked, before it closes the editor.
    BackStep(confirmDelete && row != null) { confirmDelete = false }

    // Say what the server did beyond the obvious — an alias taken from another project.
    fun run(work: suspend () -> ProjectRow?) {
        busy = true
        note = ""
        scope.launch {
            try {
                val r = work()
                val moved = r?.movedAliases ?: emptyList()
                if (moved.isNotEmpty()) {
                    note = moved.joinToString(" · ") { "${it.alias} moved here from ${it.from}" }
                    delay(1400)
                }
                onDone()
            } catch (e: Exception) {
                busy = false
                note = if (e.status() == 409) "Not saved — another project already has that name." else "Not saved — the server refused."
            }
        }
    }
    fun save() {
        if (name.isBlank()) {
            note = "A project needs a name."
            return
        }
        val b = body(
            "name" to name.trim(),
            "description" to description.trim().ifEmpty { null },
            "icon" to icon.trim().ifEmpty { null },
            "aliases" to aliases.split(',').map { it.trim() }.filter { it.isNotEmpty() },
        )
        run { if (row != null) Api.patchProject(row.project.id, b) else Api.createProject(b) }
    }

    val preview = Project("preview", name.ifEmpty { "?" }, pr?.color ?: "#16604A")

    @Composable
    fun iconChoice(value: String, mark: @Composable () -> Unit) {
        val on = icon == value
        val shape = RoundedCornerShape(7.dp)
        Box(
            Modifier.size(28.dp).clip(shape).background(if (on) C.chip else C.white).border(1.dp, if (on) C.brand else C.line, shape).tap { icon = value },
            contentAlignment = Alignment.Center,
        ) { mark() }
    }

    Column(Modifier.padding(start = 18.dp, end = 18.dp, top = 2.dp, bottom = 12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        InlineField(name, { name = it }, Modifier.fillMaxWidth(), placeholder = "NovaCart-chan", autoFocus = row == null)
        InlineField(description, { description = it }, Modifier.fillMaxWidth(), placeholder = "What it is, in a line — the chatbot for the shop's catalogue", mono = false, singleLine = false)
        Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("ICON — AN EMOJI, OR ONE OF THESE", style = T.mono.copy(fontSize = 12.5.sp, color = C.muted))
            FlowRow(horizontalArrangement = Arrangement.spacedBy(5.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                iconChoice("") { ProjectIcon(preview, 15.dp) }
                PROJECT_ICONS.keys.forEach { n -> iconChoice("icon:$n") { ProjectIcon(preview.copy(icon = "icon:$n"), 15.dp) } }
                InlineField(if (icon.startsWith("icon:")) "" else icon, { icon = it.trim() }, Modifier.width(52.dp), placeholder = "🛒", mono = false)
            }
        }
        InlineField(aliases, { aliases = it }, Modifier.fillMaxWidth(), placeholder = "Also known as — linear:Kestrel, novachan", onDone = ::save)
        if (note.isNotEmpty()) Text(note, style = T.sans.copy(fontSize = 13.sp))
        if (confirmDelete && row != null) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(
                    "Delete ${row.project.name}? ${if (row.openTasks > 0) "Its ${row.openTasks} open tasks move to " else "Its tasks move to "}${home?.project?.name ?: "the default"}.",
                    style = T.sans.copy(fontSize = 14.sp), modifier = Modifier.weight(1f),
                )
                QuietButton("Keep") { confirmDelete = false }
                SaveButton("Delete", busy, C.red) { run { Api.deleteProject(row.project.id); null } }
            }
        } else {
            FlowRow(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp, Alignment.End), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                if (row != null && !row.project.isDefault) {
                    QuietButton("Make default") { run { Api.patchProject(row.project.id, body("is_default" to true)) } }
                    QuietButton(if (row.archived) "Unarchive" else "Archive") { run { Api.patchProject(row.project.id, body("archived" to !row.archived)) } }
                    QuietButton("Delete", C.red) { confirmDelete = true }
                }
                if (row?.project?.isDefault == true) {
                    // The buttons the others have are missing on purpose; say so.
                    Text(
                        "The default can't be archived or deleted — every task without a project lands here. To remove it, open another project and choose Make default.",
                        style = T.sans.copy(fontSize = 13.sp, color = C.muted, lineHeight = 16.sp),
                    )
                }
                Spacer(Modifier.weight(1f))
                QuietButton("Cancel", onClick = onCancel)
                SaveButton(if (row != null) "Save" else "Create", busy, onClick = ::save)
            }
        }
    }
}
