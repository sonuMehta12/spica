package com.sonu.spica.ui.home

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import com.sonu.spica.state.HomeWidget
import com.sonu.spica.ui.common.Glyph
import com.sonu.spica.ui.common.Ph
import com.sonu.spica.ui.common.tap
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.sonu.spica.data.Mode
import com.sonu.spica.lib.Day
import com.sonu.spica.state.AppState
import com.sonu.spica.state.SpicaViewModel
import com.sonu.spica.state.DerivedView
import com.sonu.spica.ui.chat.SET_PROTEIN_TARGET
import com.sonu.spica.ui.chat.targetContext
import com.sonu.spica.ui.theme.C
import com.sonu.spica.ui.theme.T
import java.time.LocalTime

/**
 * The left page: what to do now first, then the widgets you chose —
 * Money and Diet to start, Activity and Habits when added — each a tap from
 * its report, and at the foot the button that adds or takes them off. Anything that
 * means talking (Set target, the rest of the list) goes to Chat, where the
 * answer appears.
 */
@Composable
fun HomePage(vm: SpicaViewModel, s: AppState, v: DerivedView, onChat: () -> Unit, onConnectHealth: () -> Unit, modifier: Modifier = Modifier) {
    Column(
        modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            // Room at the foot for the composer, which floats over both pages.
            .padding(start = 16.dp, end = 16.dp, top = 4.dp, bottom = 118.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        TodayWidget(
            s.todos, s.projects, s.todayIso,
            onToggle = vm::toggleTodo,
            onOpen = { vm.openReport(Mode.Work) },
            onAll = {
                vm.showAllTasks()
                onChat()
            },
        )
        // The rest stand in one fixed order, whichever you added first.
        HomeWidget.entries.filter { it.id in s.homeWidgets }.forEach { w ->
            when (w) {
                HomeWidget.Money -> MoneyWidget(v.paisa, onOpen = { vm.openReport(Mode.Paisa) }, onSetTarget = { vm.setContext(targetContext("Savings target", null)) }, onCommitted = vm::openCommitments)
                HomeWidget.Diet -> DietWidget(v.diet, onOpen = { vm.openReport(Mode.Diet) }, onSetTarget = { vm.setContext(SET_PROTEIN_TARGET) })
                HomeWidget.Meals -> MealsWidget(s.plan, s.planLoading, s.planDone, vm::logPlanMeal, vm::savePlanIdea, vm::loadPlan)
                HomeWidget.Activity -> ActivityWidget(s.healthAccess, s.activity, onConnectHealth)
                HomeWidget.Workout -> WorkoutWidget(s.plan, s.planLoading, "workout" in s.planDone, vm::doneWorkout, vm::loadPlan)
                HomeWidget.Habits -> HabitsWidget(v.habits, onOpen = vm::openHabits)
            }
        }
        var picking by remember { mutableStateOf(false) }
        AddWidgetButton(allOn = HomeWidget.entries.all { it.id in s.homeWidgets }) { picking = true }
        if (picking) WidgetSheet(s.homeWidgets, vm::toggleWidget) { picking = false }
    }
}

/** The last thing on Home: the way to put more on it, or take some off. */
@Composable
private fun AddWidgetButton(allOn: Boolean, onClick: () -> Unit) {
    val pill = RoundedCornerShape(50)
    Row(
        Modifier
            .fillMaxWidth()
            .padding(top = 4.dp)
            .height(46.dp)
            .clip(pill)
            .border(1.dp, C.border, pill)
            .tap(onClick = onClick),
        horizontalArrangement = Arrangement.Center,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Glyph(Ph.plus, 16.dp, C.muted)
        Text(
            if (allOn) "Edit widgets" else "Add widget",
            style = T.sans.copy(fontSize = 14.sp, fontWeight = FontWeight.Medium, color = C.muted),
            modifier = Modifier.padding(start = 8.dp),
        )
    }
}

/**
 * The widgets Home can show, each with what it holds and one button: Add, or
 * Remove. It stays open, so several go on in one visit. Today is not listed —
 * it is always first.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun WidgetSheet(on: List<String>, onToggle: (String) -> Unit, onDismiss: () -> Unit) {
    ModalBottomSheet(onDismissRequest = onDismiss, containerColor = C.white, scrimColor = C.shadow.copy(alpha = 0.32f)) {
        Column(Modifier.fillMaxWidth().padding(start = 20.dp, end = 20.dp, bottom = 28.dp)) {
            Text("Widgets", style = T.sans.copy(fontSize = 16.sp, fontWeight = FontWeight.SemiBold))
            Text("Today is always first. The rest are yours to choose.", style = T.sans.copy(fontSize = 12.5.sp, color = C.faint), modifier = Modifier.padding(top = 2.dp, bottom = 8.dp))
            HomeWidget.entries.forEachIndexed { i, w ->
                val added = w.id in on
                Row(
                    Modifier.fillMaxWidth().then(if (i == 0) Modifier else Modifier.topRule(C.line)).padding(vertical = 12.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Column(Modifier.weight(1f)) {
                        Text(w.label, style = T.sans.copy(fontSize = 15.sp, fontWeight = FontWeight.Medium))
                        Text(w.blurb, style = T.sans.copy(fontSize = 12.5.sp, color = C.faint), modifier = Modifier.padding(top = 1.dp))
                    }
                    val pill = RoundedCornerShape(50)
                    Box(
                        Modifier
                            .clip(pill)
                            .then(if (added) Modifier.border(1.dp, C.border, pill) else Modifier.background(C.brand))
                            .tap { onToggle(w.id) }
                            .padding(horizontal = 16.dp, vertical = 7.dp),
                    ) {
                        Text(
                            if (added) "Remove" else "Add",
                            style = T.sans.copy(fontSize = 13.sp, fontWeight = FontWeight.Medium, color = if (added) C.muted else C.white),
                        )
                    }
                }
            }
        }
    }
}
