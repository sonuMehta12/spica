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
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.sonu.spica.data.Api
import com.sonu.spica.data.DishRow
import com.sonu.spica.data.PantryRow
import com.sonu.spica.data.PantryStatus
import com.sonu.spica.lib.Day
import com.sonu.spica.lib.Fmt
import com.sonu.spica.state.AppState
import com.sonu.spica.state.SpicaViewModel
import com.sonu.spica.ui.common.fadeUp
import com.sonu.spica.ui.common.tap
import com.sonu.spica.ui.home.topRule
import com.sonu.spica.ui.report.Card
import com.sonu.spica.ui.report.reportCard
import com.sonu.spica.ui.theme.C
import com.sonu.spica.ui.theme.F
import com.sonu.spica.ui.theme.T
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.text.InlineTextContent
import androidx.compose.foundation.text.appendInlineContent
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.Placeholder
import androidx.compose.ui.text.PlaceholderVerticalAlign
import androidx.compose.ui.unit.em
import com.sonu.spica.ui.common.Glyph
import com.sonu.spica.ui.common.Ph
import com.sonu.spica.ui.common.PhBold
import com.sonu.spica.ui.common.PhFill

private enum class DishTab { All, Cook, Saved }

private const val TRIED = "tried"
private const val SAVED = "saved"

/**
 * The marks line's glyphs, each a square the size of the text beside it: a
 * bold tick for tried (a glyph this small is bold), a filled star for saved,
 * each in its mark's colour. The placeholder sets the size — `fillMaxSize`
 * holds the glyph to it, whatever `Glyph`'s own size says.
 */
private val MarkGlyphs = mapOf(
    TRIED to InlineTextContent(Placeholder(1.em, 1.em, PlaceholderVerticalAlign.TextCenter)) {
        Glyph(PhBold.check, 12.dp, C.dietInk, Modifier.fillMaxSize())
    },
    SAVED to InlineTextContent(Placeholder(1.em, 1.em, PlaceholderVerticalAlign.TextCenter)) {
        Glyph(PhFill.star, 12.dp, C.brand, Modifier.fillMaxSize())
    },
)

/**
 * Can this be cooked from what is in the house right now? `missing` blocks the
 * dish; `iffy` does not. A staple is always present, and an untracked food is
 * unknowable rather than absent — nagging about eggs nobody logged would be the
 * confident wrong answer this app avoids. Stale is a warning, never a block.
 */
private fun checkStock(dish: DishRow, pantry: List<PantryRow>): Pair<List<String>, List<String>> {
    val byId = pantry.associateBy { it.foodId }
    val missing = mutableListOf<String>()
    val iffy = mutableListOf<String>()
    for (it in dish.items) {
        val row = it.foodId?.let(byId::get) ?: continue
        if (row.status == PantryStatus.Staple || row.status == PantryStatus.New) continue
        if (row.status == PantryStatus.Out || (it.quantity != null && row.stockG < it.quantity)) missing += row.name
        else if (row.status == PantryStatus.Stale) iffy += row.name
    }
    return missing to iffy
}

/**
 * Your data → Dishes. Your library, not the pool: a dish is here because you
 * tried it (counted from the ledger) or saved it (a bookmark row); both marks
 * can be on one dish. *Cook now* is the only computed tab. No ranking here —
 * that is the agent's job. Port of `DishesSection.tsx`.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun DishesSection(vm: SpicaViewModel, s: AppState) {
    var view by remember { mutableStateOf(DishTab.All) }
    var open by remember { mutableStateOf<String?>(null) }
    val dishes = s.dishes
    val cookable = dishes.filter { it.items.isNotEmpty() && checkStock(it, s.pantry).first.isEmpty() }
    val saved = dishes.filter { it.saved }
    val shown = when (view) {
        DishTab.Cook -> cookable
        DishTab.Saved -> saved
        DishTab.All -> dishes
    }
    // Back folds an open dish — one on screen — before it leaves the section.
    BackStep(open != null && shown.any { it.id == open }) { open = null }

    FlowRow(Modifier.padding(bottom = 14.dp), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        listOf(DishTab.All to "All · ${dishes.size}", DishTab.Cook to "Cook now · ${cookable.size}", DishTab.Saved to "Saved · ${saved.size}").forEach { (id, label) ->
            FilterPill(label, view == id, { view = id })
        }
    }

    Column(Modifier.fillMaxWidth().reportCard().clip(Card)) {
        if (shown.isEmpty()) {
            Text(
                when (view) {
                    DishTab.Cook -> "Nothing can be cooked from what is in the house right now."
                    DishTab.Saved -> "Nothing saved yet. Star a dish to try it later."
                    DishTab.All -> "No dishes yet."
                },
                style = T.sans.copy(fontSize = 15.sp, color = C.muted),
                modifier = Modifier.padding(horizontal = 18.dp, vertical = 14.dp),
            )
        }
        shown.forEachIndexed { i, d ->
            val (missing, iffy) = checkStock(d, s.pantry)
            val ready = d.items.isNotEmpty() && missing.isEmpty()
            Column(if (i > 0) Modifier.divider(18.dp, 18.dp) else Modifier) {
                Row(
                    Modifier.fillMaxWidth().padding(start = 13.dp, end = 6.dp, top = 11.dp, bottom = 11.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    Column(Modifier.weight(1f).clip(RoundedCornerShape(6.dp)).tap { open = if (open == d.id) null else d.id }) {
                        Text(
                            buildAnnotatedString {
                                append(d.name)
                                withStyle(SpanStyle(fontFamily = F.mono, fontSize = 12.5.sp, color = C.faint)) {
                                    append("  ${d.serving}")
                                    d.minutes?.let { append(" · ${it}m") }
                                    if (d.needsPrepAhead) append(" · prep ahead")
                                }
                            },
                            style = T.sans.copy(fontSize = 15.sp),
                        )
                        // Two marks, and a dish can carry both. Each may lead with a
                        // Phosphor glyph, drawn inline at the line's own size.
                        val marks = buildAnnotatedString {
                            val parts = mutableListOf<Triple<String?, String, Color>>()
                            if (d.tried > 0) parts += Triple(TRIED, "${d.tried}×${d.lastTried?.let { " · ${Day.cardDay(it)}" } ?: ""}", C.dietInk)
                            if (d.saved) parts += Triple(SAVED, "saved", C.brand)
                            if (missing.isNotEmpty()) parts += Triple(null, "need ${missing.take(2).joinToString(", ")}${if (missing.size > 2) " +${missing.size - 2}" else ""}", C.faint)
                            // Cookable, but something in it is past its life — said, not enforced.
                            else if (iffy.isNotEmpty()) parts += Triple(null, "${iffy.joinToString(", ")} is stale", C.red)
                            if (ready && iffy.isEmpty() && d.tried == 0 && !d.saved) parts += Triple(null, "can cook now", C.dietInk)
                            parts.forEachIndexed { n, (glyph, text, col) ->
                                if (n > 0) withStyle(SpanStyle(color = C.faint)) { append("  ·  ") }
                                withStyle(SpanStyle(color = col)) {
                                    // The tick is what "tried" means, so a screen reader hears it;
                                    // the star sits beside the word that says it, so it is silent.
                                    if (glyph != null) {
                                        appendInlineContent(glyph, if (glyph == TRIED) "Tried" else " ")
                                        append(" ")
                                    }
                                    append(text)
                                }
                            }
                        }
                        if (marks.isNotEmpty()) Text(marks, style = T.mono.copy(fontSize = 12.5.sp), inlineContent = MarkGlyphs, modifier = Modifier.padding(top = 3.dp))
                    }
                    Text("${Fmt.num(d.proteinG)}g", style = T.mono.copy(fontSize = 13.sp, fontWeight = FontWeight.SemiBold, color = C.muted), maxLines = 1)
                    Text("${d.kcal ?: "—"} kcal", style = T.mono.copy(fontSize = 12.5.sp, color = C.faint), maxLines = 1)
                    // Saving is a selection, so a saved star is Jamun, filled.
                    Box(
                        Modifier.size(28.dp).clip(CircleShape)
                            .semantics {
                                role = Role.Button
                                selected = d.saved
                                contentDescription = if (d.saved) "Unsave ${d.name}" else "Save ${d.name}"
                            }
                            .tap { vm.toggleSaveDish(d.id) },
                        contentAlignment = Alignment.Center,
                    ) {
                        Glyph(if (d.saved) PhFill.star else Ph.star, 16.dp, if (d.saved) C.brand else C.faint)
                    }
                }
                if (open == d.id) {
                    Column(Modifier.fadeUp(200).padding(start = 18.dp, end = 18.dp, bottom = 12.dp)) {
                        if (d.items.isNotEmpty()) {
                            Text(
                                buildAnnotatedString {
                                    d.items.forEachIndexed { n, it ->
                                        if (n > 0) append(" · ")
                                        withStyle(SpanStyle(color = if (it.fromDish != null) C.faint else C.muted)) {
                                            append("${it.name ?: "a dish"} ${if (it.quantity != null) Api.inUnit(it.quantity, it.unit) else "×${Fmt.num(it.servings)}"}")
                                        }
                                    }
                                },
                                style = T.mono.copy(fontSize = 15.sp, lineHeight = 20.4.sp),
                            )
                        } else {
                            Text("No ingredients — it cannot be broken into grams, so it never appears in Cook now.", style = T.sans.copy(fontSize = 13.sp, color = C.muted))
                        }
                        d.note?.let { Text(it, style = T.sans.copy(fontSize = 13.sp, color = C.muted), modifier = Modifier.padding(top = 6.dp)) }
                        Text(
                            (listOfNotNull(d.mealType) + d.tags).joinToString(" · ") + if (d.mine) " · yours" else "",
                            style = T.mono.copy(fontSize = 12.5.sp, color = C.faint), modifier = Modifier.padding(top = 6.dp),
                        )
                    }
                }
            }
        }
    }
}
