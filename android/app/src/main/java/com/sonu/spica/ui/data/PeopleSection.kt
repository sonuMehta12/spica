package com.sonu.spica.ui.data

import com.sonu.spica.ui.common.ActionPill
import com.sonu.spica.ui.common.AddRow
import com.sonu.spica.ui.common.BackStep
import com.sonu.spica.ui.common.FilterPill
import com.sonu.spica.ui.common.PillKind
import com.sonu.spica.ui.common.divider
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.em
import androidx.compose.ui.unit.sp
import com.sonu.spica.data.PersonRow
import com.sonu.spica.data.body
import com.sonu.spica.lib.Day
import com.sonu.spica.lib.Fmt
import com.sonu.spica.state.AppState
import com.sonu.spica.state.SpicaViewModel
import com.sonu.spica.ui.common.Dot
import com.sonu.spica.ui.common.InlineField
import com.sonu.spica.ui.common.fadeUp
import com.sonu.spica.ui.common.tap
import com.sonu.spica.ui.home.topRule
import com.sonu.spica.ui.profile.SelectPill
import com.sonu.spica.ui.report.Card
import com.sonu.spica.ui.report.reportCard
import com.sonu.spica.ui.theme.C
import com.sonu.spica.ui.theme.F
import com.sonu.spica.ui.theme.T
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonObject

/** The four tabs. Unsorted is the rows with no kind at all. */
private enum class PeopleTab(val kind: String?) { Person("person"), Shop("shop"), Service("service"), Unsorted(null) }

private val KINDS = listOf("person", "shop", "service")
private const val NOT_SAID = "Not said"

private fun title(s: String) = s.replaceFirstChar { it }

private fun inRupees(paise: Long) = Fmt.rupees(paise / 100.0)

/** The five stored fields, as the form holds them. */
private data class PersonDraft(
    val kind: String = "",
    val displayName: String = "",
    val relation: String = "",
    val defaultCategory: String = "",
    val note: String = "",
) {
    /** By wire name — the PATCH body's keys. */
    fun columns() = listOf(
        "kind" to kind,
        "display_name" to displayName,
        "relation" to relation,
        "default_category" to defaultCategory,
        "note" to note,
    )
}

private val EMPTY = PersonDraft()

private fun draftOf(p: PersonRow) = PersonDraft(
    kind = p.kind ?: "",
    displayName = p.displayName ?: "",
    relation = p.relation ?: "",
    defaultCategory = p.defaultCategory ?: "",
    note = p.note ?: "",
)

/**
 * Only what changed — the web's `Edits`. Empty string clears the column
 * (JSON null); absent leaves it alone.
 */
private fun diff(d: PersonDraft, was: PersonDraft): JsonObject {
    val old = was.columns().toMap()
    val changed: List<Pair<String, Any?>> = d.columns()
        .filter { (k, v) -> v.trim() != old[k] }
        .map { (k, v) -> k to v.trim().ifEmpty { null } }
    return body(*changed.toTypedArray())
}

/**
 * Your data → People. Port of `vault/PeopleSection.tsx`; spec/done/people.md.
 *
 * A counterparty row plus what the ledger knows about it. Only five things
 * here are stored — kind, display name, relation, usual category, note — and
 * everything with a number beside it is computed per request, so deleting a
 * payment corrects the row with no write anywhere.
 *
 * **Unsorted never nags.** No badge, no count to clear: a shop with no kind
 * breaks nothing, and the rows that matter announce themselves when money
 * comes back. Classifying is a one-time pass, then a trickle.
 *
 * Adding and editing render the *same* fields, because they are the same five
 * columns; adding only puts `raw_name` on top, which is the one thing that can
 * never be changed afterwards.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun PeopleSection(vm: SpicaViewModel, s: AppState) {
    val scope = rememberCoroutineScope()
    var view by remember { mutableStateOf(PeopleTab.Person) }
    var open by remember { mutableStateOf<String?>(null) }
    var form by remember { mutableStateOf(EMPTY) }
    var adding by remember { mutableStateOf(false) }
    var newName by remember { mutableStateOf("") }
    var newForm by remember { mutableStateOf(EMPTY) }
    var busy by remember { mutableStateOf(false) }

    val people = s.people
    fun of(t: PeopleTab) = people.filter { it.kind == t.kind }
    val shown = of(view)

    // Back closes the editor before it leaves the section: the add form, then
    // an open row — one on screen; a row left open under another tab is not.
    BackStep(open != null && shown.any { it.id == open }) { open = null }
    BackStep(adding) { adding = false }

    // Only one editor at a time. Two open panels put two identical field sets
    // on screen, and there is no way to tell which one a keystroke belongs to.
    fun expand(p: PersonRow) {
        val same = open == p.id
        adding = false
        open = if (same) null else p.id
        if (!same) form = draftOf(p)
    }

    fun openAdd() {
        open = null
        newForm = EMPTY
        adding = true
    }

    // Everything commits together. The kind used to save on its own tap, which
    // re-filed the row into another tab mid-edit and stranded whatever was
    // still being typed — so one Save, and the row moves once.
    fun commit(p: PersonRow) {
        val b = diff(form, draftOf(p))
        if (b.isEmpty()) return
        busy = true
        scope.launch {
            vm.filePerson(p.id, b)
            busy = false
        }
    }

    fun add() {
        val clean = newName.trim()
        if (clean.isEmpty()) return
        busy = true
        scope.launch {
            val ok = vm.addPerson(clean, diff(newForm, EMPTY))
            busy = false
            if (ok) {
                newName = ""
                newForm = EMPTY
                adding = false
            }
        }
    }

    Column(Modifier.fillMaxWidth()) {
        FlowRow(
            Modifier.fillMaxWidth().padding(bottom = 14.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            PeopleTabPill("People · ${of(PeopleTab.Person).size}", view == PeopleTab.Person) { view = PeopleTab.Person }
            PeopleTabPill("Shops · ${of(PeopleTab.Shop).size}", view == PeopleTab.Shop) { view = PeopleTab.Shop }
            PeopleTabPill("Services · ${of(PeopleTab.Service).size}", view == PeopleTab.Service) { view = PeopleTab.Service }
            PeopleTabPill("Unsorted · ${of(PeopleTab.Unsorted).size}", view == PeopleTab.Unsorted) { view = PeopleTab.Unsorted }
        }

        Column(Modifier.fillMaxWidth().reportCard().clip(Card)) {
            if (shown.isEmpty()) {
                Text(
                    if (view == PeopleTab.Unsorted) "Everyone is filed. Nothing to do here."
                    else "No ${if (view == PeopleTab.Person) "people" else "${view.kind}s"} yet — tap a row under Unsorted to file it.",
                    style = T.sans.copy(fontSize = 15.sp, color = C.muted),
                    modifier = Modifier.padding(horizontal = 18.dp, vertical = 14.dp),
                )
            }

            shown.forEachIndexed { i, p ->
                key(p.id) {
                    val owed = p.stillOut > 0 || p.youOwe > 0
                    val isOpen = open == p.id
                    val dirty = isOpen && diff(form, draftOf(p)).isNotEmpty()
                    Column(Modifier.fillMaxWidth().then(if (i > 0) Modifier.divider(18.dp, 18.dp) else Modifier)) {
                        Row(
                            Modifier.fillMaxWidth().padding(horizontal = 18.dp, vertical = 14.dp),
                            horizontalArrangement = Arrangement.spacedBy(10.dp),
                        ) {
                            Column(Modifier.weight(1f).alignByBaseline().tap { expand(p) }) {
                                Text(
                                    buildAnnotatedString {
                                        append(p.name)
                                        // A mono space stands in for the web's 6px margin.
                                        p.relation?.takeIf { it.isNotEmpty() }?.let {
                                            withStyle(SpanStyle(fontFamily = F.mono, fontSize = 12.5.sp, color = C.faint)) { append(" $it") }
                                        }
                                    },
                                    style = T.sans.copy(fontSize = 15.sp),
                                )
                                Row(Modifier.padding(top = 3.dp), verticalAlignment = Alignment.CenterVertically) {
                                    // A kind nobody has said is the migration's or the agent's guess.
                                    if (p.kind != null && !p.confirmed) Dot()
                                    Text(
                                        buildString {
                                            if (p.txCount > 0) {
                                                append("${p.txCount}×")
                                                p.lastDay?.takeIf { it.isNotEmpty() }?.let { append(" · ${Day.shortDay(it)}") }
                                            } else {
                                                append("no payments")
                                            }
                                            p.typicalDays?.let { append(" · usually ${Fmt.num(it)}d to return") }
                                        },
                                        style = T.mono.copy(fontSize = 12.5.sp, color = C.faint),
                                    )
                                }
                            }

                            // One column, two meanings — outstanding money and money
                            // already spent — so every number carries its own word.
                            val (amount, word) = when {
                                p.stillOut > 0 -> inRupees(p.stillOut) to "still out"
                                p.youOwe > 0 -> inRupees(p.youOwe) to "you owe"
                                p.sent > 0 -> inRupees(p.sent) to "sent"
                                else -> "—" to ""
                            }
                            Column(Modifier.widthIn(min = 78.dp).alignByBaseline(), horizontalAlignment = Alignment.End) {
                                Text(
                                    amount,
                                    style = T.mono.copy(
                                        fontSize = 13.sp,
                                        fontWeight = if (owed) FontWeight.SemiBold else FontWeight.Normal,
                                        color = if (p.stillOut > 0) C.ink else if (p.youOwe > 0) C.red else C.muted,
                                    ),
                                    maxLines = 1,
                                    softWrap = false,
                                )
                                if (word.isNotEmpty()) {
                                    Text(
                                        word,
                                        style = T.mono.copy(fontSize = 12.5.sp, color = C.faint),
                                        maxLines = 1,
                                        softWrap = false,
                                        modifier = Modifier.padding(top = 2.dp),
                                    )
                                }
                            }
                        }

                        if (isOpen) {
                            Column(Modifier.fillMaxWidth().fadeUp(200).padding(start = 18.dp, end = 18.dp, bottom = 13.dp)) {
                                // The ledger's own words. `received`, not `is_peer` — that
                                // flag was hand-set on the imported rows and says money came
                                // back from people who have never repaid anything.
                                Text(
                                    buildString {
                                        append(if (p.txCount > 0) "sent ${inRupees(p.sent)}" else "nothing has moved yet")
                                        if (p.received > 0) append(" · back ${inRupees(p.received)}")
                                        if (p.stillOut > 0) append(" · ${inRupees(p.stillOut)} still out")
                                        if (p.youOwe > 0) append(" · you owe ${inRupees(p.youOwe)}")
                                    },
                                    style = T.mono.copy(fontSize = 15.sp, lineHeight = 20.4.sp, color = C.muted),
                                )

                                PersonFields(form, { form = it }, namePlaceholder = p.rawName)

                                Row(
                                    Modifier.fillMaxWidth().padding(top = 12.dp),
                                    verticalAlignment = Alignment.Bottom,
                                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                                ) {
                                    // raw_name is shown, never edited: it is how the next
                                    // notification finds this row again.
                                    Text(
                                        buildAnnotatedString {
                                            append("Pays as ")
                                            withStyle(SpanStyle(color = C.muted)) { append(p.rawName) }
                                            append("\nThe name a notification matches on — it cannot be changed.")
                                        },
                                        style = T.mono.copy(fontSize = 12.5.sp, lineHeight = 17.3.sp, color = C.faint),
                                        modifier = Modifier.weight(1f),
                                    )
                                    PeopleButton("Save", on = dirty && !busy) { commit(p) }
                                }
                            }
                        }
                    }
                }
            }

            // Almost everyone arrives from a payment. This is for the one who does
            // not: cash you owe, or a friend you are about to lend to.
            Column(Modifier.fillMaxWidth().then(if (shown.isNotEmpty()) Modifier.divider(18.dp, 18.dp) else Modifier)) {
                if (adding) {
                    Column(Modifier.fillMaxWidth().fadeUp(200).padding(start = 18.dp, end = 18.dp, top = 2.dp, bottom = 13.dp)) {
                        // The only field that exists here and not in the editor: once
                        // written it is the match key, so it is set exactly once.
                        PersonField(
                            name = "Name",
                            hint = "as their payments will show it",
                            value = newName,
                            placeholder = "Mohd Wasim",
                            onChange = { newName = it },
                        )
                        PersonFields(newForm, { newForm = it })
                        Row(Modifier.padding(top = 12.dp), horizontalArrangement = Arrangement.spacedBy(7.dp)) {
                            PeopleButton("Add", on = newName.trim().isNotEmpty() && !busy, onClick = ::add)
                            ActionPill("Cancel", {
                                adding = false
                                newName = ""
                                newForm = EMPTY
                            })
                        }
                    }
                } else {
                    AddRow("Add someone", ::openAdd)
                }
            }
        }
    }
}

/** A tab above the list. Selected is solid green; the rest sit on paper. */
@Composable
private fun PeopleTabPill(text: String, on: Boolean, onClick: () -> Unit) {
    FilterPill(text, on, onClick)
}

/** The web's `button(on)`: green when it would do something, a grey slab when it would not. */
@Composable
private fun PeopleButton(label: String, on: Boolean, onClick: () -> Unit) {
    ActionPill(label, onClick, PillKind.Primary, enabled = on)
}

/** A tiny mono caps label over a field; the hint after it keeps its own case. */
@Composable
private fun PersonLabelled(name: String, hint: String? = null, content: @Composable () -> Unit) {
    Column(Modifier.fillMaxWidth().padding(top = 10.dp)) {
        Text(
            buildAnnotatedString {
                append(name)
                if (!hint.isNullOrEmpty()) withStyle(SpanStyle(letterSpacing = 0.sp, color = C.faint)) { append(" $hint") }
            },
            style = T.mono.copy(fontSize = 12.5.sp, color = C.muted),
            modifier = Modifier.padding(bottom = 4.dp),
        )
        content()
    }
}

@Composable
private fun PersonField(name: String, value: String, onChange: (String) -> Unit, hint: String? = null, placeholder: String = "") {
    PersonLabelled(name, hint) {
        InlineField(
            value,
            onChange,
            Modifier.fillMaxWidth(),
            placeholder = placeholder,
            mono = false,
            style = T.sans.copy(fontSize = 14.sp),
        )
    }
}

/**
 * The five columns, identical whether you are adding or editing.
 *
 * `kind` is a dropdown, not a row of pills: pills were the same shape as the
 * tabs above the list, so the field read as navigation — and one of them filed
 * a sister as a shop.
 */
@Composable
private fun PersonFields(draft: PersonDraft, onChange: (PersonDraft) -> Unit, namePlaceholder: String? = null) {
    PersonLabelled("What is this") {
        SelectPill(
            if (draft.kind.isEmpty()) NOT_SAID else title(draft.kind),
            listOf(NOT_SAID) + KINDS.map(::title),
        ) { o -> onChange(draft.copy(kind = if (o == NOT_SAID) "" else o.lowercase())) }
    }
    PersonField(
        name = "What you call them",
        value = draft.displayName,
        placeholder = namePlaceholder ?: "Didi, chai wala…",
        onChange = { onChange(draft.copy(displayName = it)) },
    )
    PersonField(
        name = "Relation",
        hint = "your word for it",
        value = draft.relation,
        placeholder = "dost, badi behen, landlord…",
        onChange = { onChange(draft.copy(relation = it)) },
    )
    PersonField(
        name = "Usual category",
        hint = "where their payments land",
        value = draft.defaultCategory,
        placeholder = "Dost & Bahar, Transport, Rent…",
        onChange = { onChange(draft.copy(defaultCategory = it)) },
    )
    PersonField(
        name = "Note",
        value = draft.note,
        placeholder = "anything worth remembering",
        onChange = { onChange(draft.copy(note = it)) },
    )
}
