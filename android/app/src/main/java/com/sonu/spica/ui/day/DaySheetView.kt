package com.sonu.spica.ui.day

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.sonu.spica.data.Mode
import com.sonu.spica.logic.DaySheet
import com.sonu.spica.state.AppState
import com.sonu.spica.state.DerivedView
import com.sonu.spica.state.SpicaViewModel
import com.sonu.spica.ui.chat.SET_PROTEIN_TARGET
import com.sonu.spica.ui.chat.targetContext
import com.sonu.spica.ui.common.Glyph
import com.sonu.spica.ui.common.PhBold
import com.sonu.spica.ui.common.PhFill
import com.sonu.spica.ui.common.tap
import com.sonu.spica.ui.home.ActivityWidget
import com.sonu.spica.ui.home.DietWidget
import com.sonu.spica.ui.home.HabitsWidget
import com.sonu.spica.ui.home.LocalBareWidget
import com.sonu.spica.ui.home.MealsWidget
import com.sonu.spica.ui.home.MoneyWidget
import com.sonu.spica.ui.home.TodayWidget
import com.sonu.spica.ui.home.WorkoutWidget
import com.sonu.spica.ui.theme.C
import com.sonu.spica.ui.theme.T

private fun titleOf(s: DaySheet) = when (s) {
    DaySheet.Money -> "Money"
    DaySheet.Diet -> "Diet"
    DaySheet.Habits -> "Habits"
    DaySheet.Work -> "To-do"
    DaySheet.Activity -> "Activity"
}

/**
 * A row's widget, opened over the day as a sheet: the mode's colour on top,
 * the same widget Home used to show, and the way to its report. One sheet at
 * a time, and never over the glance panel — Home closes one before it opens
 * the other.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DaySheetView(
    sheet: DaySheet, vm: SpicaViewModel, s: AppState, v: DerivedView,
    onConnectHealth: () -> Unit, onChat: () -> Unit, onDismiss: () -> Unit,
) {
    val state = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    ModalBottomSheet(
        onDismissRequest = onDismiss, sheetState = state, containerColor = C.white,
        shape = RoundedCornerShape(topStart = 32.dp, topEnd = 32.dp), dragHandle = null,
        scrimColor = C.shadow.copy(alpha = 0.36f),
    ) {
        // White, one surface: the handle and a close, then the widget itself — its own title heads the sheet.
        Box(Modifier.fillMaxWidth().padding(start = 18.dp, end = 14.dp, top = 10.dp)) {
            Box(Modifier.align(Alignment.TopCenter).size(40.dp, 5.dp).clip(CircleShape).background(C.border))
            Box(
                Modifier.align(Alignment.TopEnd).padding(top = 6.dp).size(36.dp).clip(CircleShape).background(C.lineSoft).tap(onClick = onDismiss),
                contentAlignment = Alignment.Center,
            ) { Glyph(PhBold.x, 14.dp, C.ink, label = "Close ${titleOf(sheet)}") }
        }
        Column(
            Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(start = 16.dp, end = 16.dp, bottom = 16.dp).navigationBarsPadding(),
        ) {
          CompositionLocalProvider(LocalBareWidget provides true) {
            when (sheet) {
                DaySheet.Money -> MoneyWidget(v.paisa, onOpen = { vm.openReport(Mode.Paisa) }, onSetTarget = { vm.setContext(targetContext("Savings target", null)) }, onCommitted = vm::openCommitments)
                DaySheet.Diet -> {
                    DietWidget(v.diet, onOpen = { vm.openReport(Mode.Diet) }, onSetTarget = { vm.setContext(SET_PROTEIN_TARGET) })
                    Hairline()
                    MealsWidget(s.plan, s.planLoading, s.planDone, vm::logPlanMeal, vm::savePlanIdea, vm::loadPlan)
                }
                DaySheet.Habits -> HabitsWidget(v.habits, onOpen = vm::openHabits)
                DaySheet.Work -> TodayWidget(
                    s.todos, s.projects, s.todayIso, onToggle = vm::toggleTodo, onOpen = { vm.openReport(Mode.Work) },
                    onAll = {
                        vm.showAllTasks()
                        onChat()
                    },
                )
                DaySheet.Activity -> {
                    ActivityWidget(s.healthAccess, s.activity, onConnectHealth)
                    Hairline()
                    WorkoutWidget(s.plan, s.planLoading, "workout" in s.planDone, vm::doneWorkout, vm::loadPlan)
                }
            }
          }
            val report: (() -> Unit)? = when (sheet) {
                DaySheet.Money -> ({ vm.openReport(Mode.Paisa) })
                DaySheet.Diet -> ({ vm.openReport(Mode.Diet) })
                DaySheet.Habits -> vm::openHabits
                DaySheet.Work -> ({ vm.openReport(Mode.Work) })
                DaySheet.Activity -> null
            }
            if (report != null) {
                Box(
                    Modifier.fillMaxWidth().padding(top = 8.dp).height(50.dp).clip(CircleShape).background(C.brand).tap(onClick = report),
                    contentAlignment = Alignment.Center,
                ) { Text("Open ${titleOf(sheet)}", style = T.day.copy(fontSize = 15.sp, fontWeight = FontWeight.ExtraBold, color = C.white)) }
            }
            Spacer(Modifier.height(8.dp))
        }
    }
}

@Composable
private fun Hairline() = Box(Modifier.fillMaxWidth().padding(horizontal = 4.dp).height(1.dp).background(C.line))
