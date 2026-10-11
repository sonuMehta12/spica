package com.sonu.spica.ui.nudges

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.IntrinsicSize
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.sonu.spica.data.NudgeRow
import com.sonu.spica.lib.Day
import com.sonu.spica.lib.Fmt
import com.sonu.spica.logic.Tasks
import com.sonu.spica.state.AppState
import com.sonu.spica.state.SpicaViewModel
import com.sonu.spica.state.DerivedView
import com.sonu.spica.state.Landing
import com.sonu.spica.state.NudgePage
import com.sonu.spica.ui.chat.Fig
import com.sonu.spica.ui.chat.SET_PROTEIN_TARGET
import com.sonu.spica.ui.common.Back
import com.sonu.spica.ui.common.BackButton
import com.sonu.spica.ui.common.Coin
import com.sonu.spica.ui.common.Glyph
import com.sonu.spica.ui.common.Ground
import com.sonu.spica.ui.common.Panel
import com.sonu.spica.ui.common.Ph
import com.sonu.spica.ui.common.PhBold
import com.sonu.spica.ui.common.TopFade
import com.sonu.spica.ui.common.fadeUp
import com.sonu.spica.ui.common.panel
import com.sonu.spica.ui.common.plainTap
import com.sonu.spica.ui.common.tap
import com.sonu.spica.ui.home.Link
import com.sonu.spica.ui.home.PlanMealItem
import com.sonu.spica.ui.home.PlanPicture
import com.sonu.spica.ui.home.PlanState
import com.sonu.spica.ui.home.PlanWorkoutItem
import com.sonu.spica.ui.home.Small
import com.sonu.spica.ui.home.TaskRow
import com.sonu.spica.ui.home.g
import com.sonu.spica.ui.home.workoutMeta
import com.sonu.spica.ui.home.workoutTitle
import com.sonu.spica.ui.theme.C
import com.sonu.spica.ui.theme.S
import com.sonu.spica.ui.theme.T

/*
 * Where each nudge lands — `spec/in-progress/nudges.md` § The pages. The
 * nudge's line is what was said at that hour, history like any chat message;
 * every number under it is worked out from live rows as the page is drawn.
 */

/** A nudge page's name — its title, and where a screen reader hears the ← of a page over it goes. */
internal fun titleOf(l: Landing) = when (l) {
    Landing.Day -> "Your day"
    Landing.Meals -> "Meals today"
    Landing.Workout -> "Workout today"
}

/**
 * A nudge's page, over Nudges — or over the nudge page that led to it. Each
 * is a stack entry of its own, so its scroll is its own; ← at the top right
 * goes back to the page under it, and that is the only exit.
 */
@Composable
fun NudgeLanding(vm: SpicaViewModel, s: AppState, v: DerivedView, page: NudgePage, back: Back) {
    val nudge = page.nudgeId?.let { id -> s.nudges.firstOrNull { it.id == id } }
    Box(Modifier.fillMaxSize().background(Ground).plainTap { }) {
        Column(Modifier.fillMaxSize().statusBarsPadding().padding(top = 8.dp).fadeUp(280)) {
            Row(Modifier.fillMaxWidth().padding(start = 14.dp, end = 14.dp, top = 10.dp, bottom = 2.dp), horizontalArrangement = Arrangement.End) {
                BackButton(back)
            }
            Box(Modifier.weight(1f)) {
                Column(
                    Modifier
                        .fillMaxSize()
                        .verticalScroll(rememberScrollState())
                        .navigationBarsPadding()
                        .padding(start = 16.dp, end = 16.dp, top = 8.dp, bottom = 28.dp),
                ) {
                    when (page.landing) {
                        Landing.Day -> DayPage(vm, s, v, nudge)
                        Landing.Meals -> MealsPage(vm, s, nudge)
                        Landing.Workout -> WorkoutPage(vm, s, nudge, page)
                    }
                }
                TopFade()
            }
        }
    }
}

/** A page's title, large, in the kit's face. */
@Composable
private fun PageTitle(text: String) =
    Text(
        text,
        style = T.sans.copy(fontSize = 30.sp, lineHeight = 34.sp, fontWeight = FontWeight.SemiBold, letterSpacing = (-0.4).sp),
        modifier = Modifier.padding(start = 4.dp, bottom = 4.dp),
    )

/** A panel's name, inside it: small, medium, never tracked caps. */
@Composable
private fun PanelLabel(text: String, modifier: Modifier = Modifier) =
    Text(text, style = T.sans.copy(fontSize = 13.sp, lineHeight = 16.sp, fontWeight = FontWeight.Medium, color = C.muted), modifier = modifier)

/** A word that leads on to another page: the brand's, with its caret. */
@Composable
private fun Onward(text: String) {
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(3.dp)) {
        Text(text, style = T.sans.copy(fontSize = 13.sp, lineHeight = 16.sp, fontWeight = FontWeight.Medium, color = C.brand))
        Glyph(PhBold.caretRight, 11.dp, C.brand)
    }
}

/** The way into the conversation: a white pill floating on the ground. */
@Composable
private fun AskPill(text: String, onClick: () -> Unit, modifier: Modifier = Modifier) {
    val pill = RoundedCornerShape(50)
    Box(modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
        Box(
            Modifier.height(46.dp).then(S.bubble(pill)).clip(pill).background(C.white).tap(onClick = onClick).padding(horizontal = 22.dp),
            contentAlignment = Alignment.Center,
        ) {
            Text(text, style = T.sans.copy(fontSize = 15.sp, lineHeight = 18.sp, fontWeight = FontWeight.Medium))
        }
    }
}

/** A page's last line: the plan is not the only answer, and Chat is a tap away. */
@Composable
private fun AskLine(onAsk: () -> Unit) {
    Row(Modifier.fillMaxWidth().padding(top = 20.dp), horizontalArrangement = Arrangement.Center, verticalAlignment = Alignment.CenterVertically) {
        Text("Something else in mind? ", style = T.sans.copy(fontSize = 13.sp, lineHeight = 17.sp, color = C.faint))
        Link("Ask Spica", onAsk)
    }
}

/* ─── Your day ────────────────────────────────────────────────────────── */

/**
 * The morning brief: the date as a journal heading, the agent's line as it
 * was said, then the day as it stands now — three tasks to start with, what
 * is left to spend, the protein to go, the next meal and the workout — and
 * the way to ask about it.
 */
@Composable
private fun ColumnScope.DayPage(vm: SpicaViewModel, s: AppState, v: DerivedView, n: NudgeRow?) {
    Text(
        Day.longDay(n?.let { dayOf(it, s.todayIso) } ?: s.todayIso),
        style = T.display.copy(fontStyle = FontStyle.Italic, fontWeight = FontWeight.Normal, fontSize = 28.sp, lineHeight = 34.sp),
        modifier = Modifier.padding(start = 4.dp, end = 4.dp),
    )
    n?.line?.let { Text(it, style = T.agentVoice.copy(fontSize = 16.5.sp, lineHeight = 24.sp), modifier = Modifier.padding(start = 4.dp, end = 4.dp, top = 10.dp)) }
    Text(
        listOfNotNull("Spica", n?.let(::clockOf), "the numbers below are live").joinToString(" · "),
        style = T.sans.copy(fontSize = 12.sp, lineHeight = 16.sp, color = C.faint),
        modifier = Modifier.padding(start = 4.dp, top = 6.dp),
    )

    // Start with: Today's three, tickable — ticking one is acting on the brief.
    Panel(Modifier.padding(top = 18.dp)) {
        PanelLabel("Start with")
        val focus = Tasks.focus(s.todos, s.todayIso)
        if (focus.isEmpty()) {
            Small("Nothing on your list. Say what needs doing.", Modifier.padding(top = 8.dp), C.muted)
        } else {
            Column(Modifier.padding(top = 10.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                focus.forEachIndexed { i, t ->
                    TaskRow(t, s.projects, s.todayIso, onToggle = { id ->
                        vm.toggleTodo(id)
                        if (!t.done) n?.let { vm.markNudgeDone(it.id) }
                    }, next = i == 0 && !t.done)
                }
            }
        }
    }

    Row(Modifier.fillMaxWidth().padding(top = 12.dp).height(IntrinsicSize.Min), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        // Left to spend: the server's limit, less today's spending. Until the limit lands, a dash.
        // Past it, the overage with a minus — Home's rule.
        val p = v.paisa
        val limit = p.limit
        val overBy = p.overToday
        FigurePanel(
            label = "Left to spend",
            figure = when {
                limit == null -> "—"
                overBy != null -> Fmt.rupees(-overBy)
                else -> Fmt.rupees(limit - p.spentToday)
            },
            sub = if (limit == null) (if (p.salaryPending) "Salary not in yet" else null) else when {
                limit < 0 -> "Past the line — more is committed than is left this month"
                overBy == null -> "of ${Fmt.rupees(limit)} today"
                limit > 0 -> "${Fmt.rupees(p.spentToday)} spent of ${Fmt.rupees(limit)} today"
                else -> "${Fmt.rupees(p.spentToday)} spent today · everything left this month is committed"
            },
            red = overBy != null,
            modifier = Modifier.weight(1f),
            // At 0 or below, or unknown, the page behind the number.
            link = if (limit == null && !p.salaryPending) null else if (limit == null || limit <= 0) "See what's committed" to vm::openCommitments else null,
        )
        // Protein to go: today's meals against the target. No target says so.
        val d = v.diet
        val target = d.proteinTarget?.takeIf { it > 0 }
        FigurePanel(
            label = if (target != null && d.protein >= target) "Protein" else "Protein to go",
            figure = when {
                target == null -> "—"
                d.protein >= target -> "Met"
                else -> g(target - d.protein)
            },
            sub = target?.let { "${Fmt.jsRound(d.protein)} of ${g(it)} so far" },
            modifier = Modifier.weight(1f),
            link = if (target == null) "Set target" to { vm.setTargetFromNudge(SET_PROTEIN_TARGET) } else null,
        )
    }

    DueSoon(vm, s, n)

    // The next meal from the plan — the whole plan is Meals today.
    val plan = s.plan
    val next = plan?.takeIf { it.available }?.meals?.firstOrNull()
    Panel(Modifier.padding(top = 12.dp), onClick = { vm.openLanding(Landing.Meals) }) {
        when {
            next != null -> Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                PlanPicture(next.imageUrl, Ph.forkKnife, C.dietInk, C.dietTint, 60.dp)
                Column(Modifier.weight(1f)) {
                    Small("Next meal · ${next.slot.lowercase()}")
                    Text(next.name, style = T.sans.copy(fontSize = 16.sp, lineHeight = 20.sp, fontWeight = FontWeight.Medium), maxLines = 2, overflow = TextOverflow.Ellipsis)
                    Small("${Fmt.indian(next.kcal)} kcal · ${g(next.protein)} protein", color = C.muted)
                }
                Onward("All meals")
            }
            plan == null || !plan.available -> Row(verticalAlignment = Alignment.CenterVertically) {
                Small(if (s.planLoading) "Planning the rest of your day…" else "No plan for the rest of today yet.", Modifier.weight(1f), C.muted)
                Onward("Meals")
            }
            else -> Row(verticalAlignment = Alignment.CenterVertically) {
                Small("Today's meals are done.", Modifier.weight(1f), C.muted)
                Onward("Meals")
            }
        }
    }

    // The workout — the whole suggestion is Workout today.
    val w = plan?.takeIf { it.available }?.workout
    if (w != null) {
        Panel(Modifier.padding(top = 12.dp), onClick = { vm.openLanding(Landing.Workout) }) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Coin(Ph.barbell, C.dietInk, C.dietTint, 40.dp)
                Column(Modifier.weight(1f)) {
                    workoutMeta(w).takeIf { it.isNotEmpty() }?.let { Small(it) }
                    Text(workoutTitle(w), style = T.sans.copy(fontSize = 16.sp, lineHeight = 20.sp, fontWeight = FontWeight.Medium), maxLines = 2, overflow = TextOverflow.Ellipsis)
                }
                Onward("See it")
            }
        }
    }

    AskPill("Ask about your day", { vm.askAboutNudge("Your day", n?.line) }, Modifier.padding(top = 22.dp))
}

/**
 * What falls due within three days, as the brief named it: only the lines its
 * `refs.commitment_ids` carry, drawn from the commitments as they are now — a
 * line paid, skipped or deleted since is simply gone. No ids, nothing drawn.
 */
@Composable
private fun DueSoon(vm: SpicaViewModel, s: AppState, n: NudgeRow?) {
    val ids = n?.commitmentIds.orEmpty()
    if (ids.isEmpty()) return
    val lines = ids.mapNotNull { id -> s.commitments?.items?.firstOrNull { it.id == id } }
        .filter { !it.skipped && it.owed > 0 && it.dueDay != null }
    if (lines.isEmpty()) return
    Panel(Modifier.padding(top = 12.dp), onClick = vm::openCommitments) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            PanelLabel("Due soon", Modifier.weight(1f))
            Onward("Commitments")
        }
        Column(Modifier.padding(top = 8.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            lines.forEach { c ->
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        "${c.name} · due ${com.sonu.spica.ui.commitments.dueWeekday(c.dueDay!!, s.todayIso)}",
                        style = T.sans.copy(fontSize = 15.sp, lineHeight = 20.sp, fontWeight = FontWeight.Medium),
                        maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f),
                    )
                    Fig(Fmt.rupees(c.owed), 15.sp)
                }
            }
        }
    }
}

/** One figure on its own panel: its name, the figure, and what it is out of. */
@Composable
private fun FigurePanel(
    label: String, figure: String, sub: String?, modifier: Modifier = Modifier,
    red: Boolean = false, link: Pair<String, () -> Unit>? = null,
) {
    Column(modifier.fillMaxHeight().panel().padding(16.dp)) {
        PanelLabel(label, Modifier)
        Fig(figure, 30.sp, if (red) C.red else C.ink, modifier = Modifier.padding(top = 4.dp))
        sub?.let { Small(it, Modifier.padding(top = 2.dp), if (red) C.red else C.faint) }
        link?.let { Link(it.first, it.second, Modifier.padding(top = 4.dp)) }
    }
}

/* ─── Meals today ─────────────────────────────────────────────────────── */

/**
 * Today's plan, given a page: protein and calories as logged-then-planned
 * bars, so the plan's claim to close the gap can be checked, and one card per
 * meal still ahead. Logging one re-plans the rest, and marks the nudge done.
 */
@Composable
private fun ColumnScope.MealsPage(vm: SpicaViewModel, s: AppState, n: NudgeRow?) {
    PageTitle("Meals today")
    val p = s.plan
    if (p == null || !p.available) {
        Panel(Modifier.padding(top = 12.dp)) { PlanState(p, s.planLoading, vm::loadPlan) }
        return
    }
    Panel(Modifier.padding(top = 12.dp)) {
        val proteinT = p.proteinTarget?.takeIf { it > 0 }
        val kcalT = p.kcalTarget?.takeIf { it > 0 }?.toDouble()
        Stack("Protein", p.loggedProtein, p.plannedProtein, proteinT, ::g)
        Stack("Calories", p.loggedKcal.toDouble(), p.plannedKcal.toDouble(), kcalT, { Fmt.indian(it) }, Modifier.padding(top = 12.dp))
        if (proteinT == null && kcalT == null) {
            Row(Modifier.padding(top = 10.dp), verticalAlignment = Alignment.CenterVertically) {
                Small("No targets yet — these are ordinary meals. ", color = C.muted)
                Link("Set target", { vm.setTargetFromNudge(SET_PROTEIN_TARGET) })
            }
        } else {
            Small("Logged, then planned. Log a meal and the rest re-plans.", Modifier.padding(top = 10.dp))
        }
    }
    if (p.done || p.meals.isEmpty()) {
        Panel(Modifier.padding(top = 12.dp)) {
            Small("Today's meals are done — ${Fmt.indian(p.loggedKcal)} kcal and ${g(p.loggedProtein)} protein logged.", color = C.muted)
        }
    }
    p.meals.forEach { m ->
        PlanMealItem(
            m, s.planDone, onLog = { vm.logPlanMeal(it, n?.id) }, onSave = vm::savePlanIdea,
            modifier = Modifier.padding(top = 12.dp).fillMaxWidth().panel(), page = true,
        )
    }
    AskLine { vm.askAboutNudge("Meals today", n?.line) }
}

/**
 * One quantity: what is logged, solid, then what the plan adds, soft, against
 * the target. With no target there is no denominator, so no bar — the figures
 * stand alone. Logged past the target is red: over a limit, nothing else.
 */
@Composable
private fun Stack(label: String, logged: Double, planned: Double, target: Double?, unit: (Double) -> String, modifier: Modifier = Modifier) {
    Column(modifier.fillMaxWidth()) {
        Row(verticalAlignment = Alignment.Bottom) {
            Text(label, style = T.sans.copy(fontSize = 13.sp, lineHeight = 17.sp, color = C.muted), modifier = Modifier.weight(1f))
            Text(
                buildAnnotatedString {
                    withStyle(SpanStyle(color = C.ink, fontWeight = FontWeight.Medium)) { append(unit(logged)) }
                    append(" + ${unit(planned)} planned")
                    if (target != null) append(" · ${unit(target)}")
                },
                style = T.sans.copy(fontSize = 13.sp, lineHeight = 17.sp, color = C.faint),
            )
        }
        if (target != null) {
            val total = maxOf(target, logged + planned)
            val fl = (logged / total).toFloat().coerceIn(0f, 1f)
            val fp = (planned / total).toFloat().coerceIn(0f, 1f - fl)
            val rest = (1f - fl - fp).coerceAtLeast(0f)
            val shape = RoundedCornerShape(50)
            Row(Modifier.padding(top = 6.dp).fillMaxWidth().height(8.dp).clip(shape).background(C.lineSoft)) {
                if (fl > 0f) Box(Modifier.weight(fl).fillMaxHeight().background(if (logged > target) C.red else C.diet))
                if (fp > 0f) Box(Modifier.weight(fp).fillMaxHeight().background(C.dietSoft))
                if (rest > 0f) Spacer(Modifier.weight(rest))
            }
        }
    }
}

/* ─── Workout today ───────────────────────────────────────────────────── */

/**
 * The plan's workout, given a page: picture, kind and minutes, the name,
 * why, the exercises. *Done* logs it and marks the nudge done; *Not today*
 * puts the nudge away for the day.
 */
@Composable
private fun ColumnScope.WorkoutPage(vm: SpicaViewModel, s: AppState, n: NudgeRow?, page: NudgePage) {
    PageTitle("Workout today")
    val p = s.plan
    if (p == null || !p.available) {
        Panel(Modifier.padding(top = 12.dp)) { PlanState(p, s.planLoading, vm::loadPlan) }
        return
    }
    val w = p.workout
    if (w == null) {
        Panel(Modifier.padding(top = 12.dp)) { Small("Nothing planned for today.", color = C.muted) }
        return
    }
    Column(Modifier.padding(top = 12.dp).fillMaxWidth().panel()) {
        PlanWorkoutItem(
            w, done = "workout" in s.planDone || n?.done == true,
            onDone = { vm.doneWorkout(it, n?.id) }, page = true,
            onNotToday = n?.let { nudge -> { vm.notToday(nudge.id, page) } },
        )
    }
    if (w.kind != "rest") {
        Small(
            "Done marks today's exercises done, and ticks your workout habit if you track one.",
            Modifier.fillMaxWidth().padding(start = 8.dp, end = 8.dp, top = 14.dp),
        )
    }
    AskLine { vm.askAboutNudge("Workout today", n?.line) }
}
