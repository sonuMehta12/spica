package com.sonu.spica.ui.data

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.em
import androidx.compose.ui.unit.sp
import com.sonu.spica.data.PantryStatus
import com.sonu.spica.lib.Fmt
import com.sonu.spica.state.AppState
import com.sonu.spica.state.SpicaViewModel
import com.sonu.spica.state.Section
import com.sonu.spica.ui.common.Back
import com.sonu.spica.ui.common.Coin
import com.sonu.spica.ui.common.Ground
import com.sonu.spica.ui.common.PageHeader
import com.sonu.spica.ui.common.TopFade
import com.sonu.spica.ui.common.fadeUp
import com.sonu.spica.ui.common.panel
import androidx.compose.foundation.layout.IntrinsicSize
import androidx.compose.foundation.layout.fillMaxHeight
import com.sonu.spica.ui.common.plainTap
import com.sonu.spica.ui.common.tap
import com.sonu.spica.ui.home.topRule
import com.sonu.spica.ui.theme.C
import com.sonu.spica.ui.theme.S
import com.sonu.spica.ui.theme.T
import com.sonu.spica.ui.common.Glyph
import com.sonu.spica.ui.common.Ph
import com.sonu.spica.ui.common.PhBold

/** A group's name over its panel — the kit's, so every page names its groups the same way. */
@Composable
fun SectionTitle(text: String, modifier: Modifier = Modifier) {
    Text(
        text,
        style = T.sans.copy(fontSize = 14.sp, lineHeight = 18.sp, fontWeight = FontWeight.SemiBold, color = C.ink),
        modifier = modifier.padding(start = 6.dp, top = 6.dp, bottom = 10.dp),
    )
}

private data class DataTile(val key: Section, val count: Int, val hint: String, val urgent: Boolean)

/**
 * The tiles — every one counts a real table. Port of `vault/stats.ts § sections`.
 * The hint says what is owed, not how many rows are unclassified.
 */
private fun tiles(s: AppState): List<DataTile> {
    val tried = s.dishes.count { it.tried > 0 }
    val toBuy = s.pantry.count { it.status == PantryStatus.Out || it.status == PantryStatus.Stale || it.status == PantryStatus.Soon }
    val counted = s.pantry.count { !it.staple }
    val humans = s.people.count { it.kind == "person" }
    val known = s.exercises.count { it.tried > 0 }
    val spentHere = s.places.sumOf { it.spent }
    val owed = s.people.sumOf { it.stillOut + it.youOwe }
    return listOf(
        DataTile(Section.Recipe, s.dishes.size, if (tried > 0) "$tried you have eaten" else "nothing tried yet", false),
        DataTile(Section.Pantry, counted, if (toBuy > 0) "$toBuy to buy" else "all good", toBuy > 0),
        DataTile(Section.People, humans, if (owed > 0) "₹${Fmt.indian(Fmt.jsRound(owed / 100.0))} outstanding" else "nothing owed", false),
        // What was spent there, not how many were visited — a pin exists because money moved.
        DataTile(Section.Place, s.places.size, if (spentHere > 0) "₹${Fmt.indian(Fmt.jsRound(spentHere / 100.0))} spent" else "nothing spent yet", false),
        DataTile(Section.Workout, s.exercises.size, if (known > 0) "$known you have done" else "none tried yet", false),
    )
}

/** Which domain a section belongs to: its coin wears that mode's ink and tint. */
private fun coinOf(key: Section) = when (key) {
    Section.People, Section.Place -> C.paisaInk to C.paisaTint
    else -> C.dietInk to C.dietTint
}

/**
 * Drawer → Your data. The overview is a grid; each tile pushes its section
 * over it. One page per level — the overview, then a section — so each keeps
 * its own scroll, and ← on a section returns to the overview where it was
 * left. Port of `DataPage.tsx`.
 */
@Composable
fun DataPage(vm: SpicaViewModel, s: AppState, section: Section?, back: Back) {
    Box(Modifier.fillMaxSize().background(Ground).plainTap { }.imePadding()) {
        Column(Modifier.fillMaxSize().statusBarsPadding().padding(top = 8.dp).fadeUp(280)) {
            PageHeader(
                "Your data", section?.label ?: "Everything", back,
                lead = {
                    if (section == null) Coin(Ph.database, C.ink, C.white, 48.dp)
                    else {
                        val (ink, tint) = coinOf(section)
                        Ph.of(section.icon)?.let { Coin(it, ink, tint, 48.dp) }
                    }
                },
            )
            Box(Modifier.weight(1f)) {
                Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).navigationBarsPadding().padding(start = 16.dp, end = 16.dp, top = 14.dp, bottom = 18.dp)) {
                    when (section) {
                        Section.Recipe -> DishesSection(vm, s)
                        Section.Pantry -> PantrySection(vm, s)
                        Section.People -> PeopleSection(vm, s)
                        Section.Place -> PlacesSection(vm, s)
                        Section.Workout -> WorkoutsSection(vm, s)
                        null -> {
                            tiles(s).chunked(2).forEach { pair ->
                                Row(Modifier.fillMaxWidth().padding(bottom = 12.dp).height(IntrinsicSize.Min), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                                    pair.forEach { t ->
                                        val (ink, tint) = coinOf(t.key)
                                        Column(Modifier.weight(1f).fillMaxHeight().panel().tap { vm.openDataSection(t.key) }.padding(16.dp)) {
                                            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.Top) {
                                                Ph.of(t.key.icon)?.let { Coin(it, ink, tint, 40.dp) }
                                                Spacer(Modifier.weight(1f))
                                                Glyph(PhBold.caretRight, 11.dp, C.grey, Modifier.padding(top = 6.dp))
                                            }
                                            Text("${t.count}", style = T.figure.copy(fontSize = 32.sp, lineHeight = 36.sp, fontWeight = FontWeight.SemiBold), modifier = Modifier.padding(top = 14.dp))
                                            Text(t.key.label, style = T.sans.copy(fontSize = 15.sp, lineHeight = 19.sp, fontWeight = FontWeight.Medium))
                                            Text(t.hint, style = T.sans.copy(fontSize = 12.5.sp, lineHeight = 16.sp, color = if (t.urgent) C.red else C.faint), modifier = Modifier.padding(top = 3.dp))
                                        }
                                    }
                                    if (pair.size == 1) Spacer(Modifier.weight(1f))
                                }
                            }
                            Row(Modifier.fillMaxWidth().padding(top = 14.dp, start = 8.dp, end = 8.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                                Glyph(Ph.lock, 16.dp, C.faint, Modifier.padding(top = 1.dp))
                                Text(
                                    "All of this is yours. Open anything to remove it — it goes at once.",
                                    style = T.sans.copy(fontSize = 13.sp, lineHeight = 19.sp, color = C.faint),
                                )
                            }
                        }
                    }
                }
                TopFade()
            }
        }
    }
}
