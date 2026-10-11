package com.sonu.spica.state

import android.app.Application
import android.content.Context
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.sonu.spica.data.Api
import com.sonu.spica.data.ChatMsg
import com.sonu.spica.data.ChatPage
import com.sonu.spica.data.Commitment
import com.sonu.spica.data.CommitmentDraft
import com.sonu.spica.data.ComposeContext
import com.sonu.spica.data.DeckData
import com.sonu.spica.data.HabitRow
import com.sonu.spica.data.Health
import com.sonu.spica.data.HealthAccess
import com.sonu.spica.data.Meal
import com.sonu.spica.data.MemoryRow
import com.sonu.spica.data.Mode
import com.sonu.spica.data.NudgeRow
import com.sonu.spica.data.Onboarding
import com.sonu.spica.data.PendingItem
import com.sonu.spica.data.PlanMeal
import com.sonu.spica.data.PlanWorkout
import com.sonu.spica.data.RepaymentItem
import com.sonu.spica.data.TodayPlan
import com.sonu.spica.data.SuggestItem
import com.sonu.spica.data.Suggestion
import com.sonu.spica.data.Tx
import com.sonu.spica.data.WeighInRow
import com.sonu.spica.data.body
import com.sonu.spica.data.status
import com.sonu.spica.lib.Day
import com.sonu.spica.lib.Fmt
import com.sonu.spica.lib.Ulid
import com.sonu.spica.logic.Chips
import com.sonu.spica.logic.FieldId
import com.sonu.spica.logic.Ledger
import com.sonu.spica.logic.Msgs
import com.sonu.spica.logic.ProfileEdit
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.FlowPreview
import kotlinx.coroutines.Job
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.debounce
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.drop
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonObject
import java.time.Instant

/**
 * The app's one state holder — a port of `frontend/src/state/usePersonaOS.ts`.
 *
 * Every write is optimistic but never silent: the row lands at once, marked
 * pending, and the request runs behind it. If the server refuses, the row
 * STAYS and turns unsaved (or the old value comes back) — the screen must not
 * claim a number the server rejected.
 */
@OptIn(FlowPreview::class)
private const val WIDGETS_KEY = "home_widgets"

/** When the bell was last opened, on this phone — a layout fact like the widgets, not data about you. */
private const val BELL_KEY = "nudges_bell_opened_at"

/**
 * The account whose first run finished on this phone but whose flag has not
 * reached the server yet: it stays finished, and the flag is sent again on
 * the next start.
 */
private const val FIRST_RUN_KEY = "first_run_done_owed"

/** The agent's words for an answer it could not read. A second one on the same question moves on as a skip. */
private const val SAY_AGAIN = "Say that again?"

class SpicaViewModel(app: Application) : AndroidViewModel(app) {
    private val _state = MutableStateFlow(AppState())
    val state: StateFlow<AppState> = _state
    private val s get() = _state.value

    private val prefs = app.getSharedPreferences("spica", Context.MODE_PRIVATE)

    private fun patch(f: AppState.() -> AppState) = _state.update(f)

    private fun launch(block: suspend () -> Unit): Job = viewModelScope.launch { block() }

    /** Which of Home's widgets you chose, kept on this phone — a layout, not data about you. */
    private fun savedWidgets(): List<String> =
        prefs.getString(WIDGETS_KEY, null)?.split(',')?.filter { it in HomeWidget.ids } ?: HomeWidget.DEFAULT

    /** Add a widget to Home, or take it off. Today is always there. */
    fun toggleWidget(id: String) {
        val next = if (id in s.homeWidgets) s.homeWidgets - id else s.homeWidgets + id
        prefs.edit().putString(WIDGETS_KEY, next.joinToString(",")).apply()
        patch { copy(homeWidgets = next) }
        loadPlan()
    }

    private fun savedBell(): Instant? = prefs.getString(BELL_KEY, null)?.let { runCatching { Instant.parse(it) }.getOrNull() }

    private fun wantsPlan() =
        HomeWidget.Meals.id in s.homeWidgets || HomeWidget.Workout.id in s.homeWidgets || s.stack.any { it is Screen.Nudge } ||
            (Screen.Nudges in s.stack && s.nudges.any { it.kind == "meals" && it.line == null && it.day == s.todayIso && !it.dismissed })

    /**
     * Today's plan, from the server, only while Meals or Workout is on Home —
     * or a nudge's page that shows it is open, or Nudges with a Meals today
     * card whose line is the plan's.
     * Read on boot, on resume and after every write; the server reuses its
     * plan until something it read changes, so most reads are no model call.
     * A failed read keeps whatever was showing.
     */
    fun loadPlan() {
        if (!wantsPlan() || s.planLoading || !s.booted) return
        patch { copy(planLoading = true) }
        launch {
            val clock = java.time.LocalTime.now()
            val got = runCatching { Api.fetchPlan(s.todayIso, "%02d:%02d".format(clock.hour, clock.minute)) }.getOrNull()
            patch {
                copy(
                    plan = got ?: plan ?: TodayPlan(false, false, null, null, 0.0, 0, 0.0, 0, emptyList(), null),
                    planLoading = false,
                    planDone = if (got != null) emptyList() else planDone,
                )
            }
        }
    }

    /**
     * Log it, from the plan: a library dish by id at its own numbers, an idea
     * by name — priced like anything said, so it carries the estimate's dot.
     * From a nudge's page, the nudge is done once the meal is.
     */
    fun logPlanMeal(m: PlanMeal, nudgeId: String? = null) {
        val key = "meal:${m.slot}"
        if (key in s.planDone) return
        patch { copy(planDone = planDone + key) }
        launch {
            try {
                val args = listOfNotNull(
                    "text_said" to m.name, "meal_type" to m.slot, "local_day" to s.todayIso,
                    m.dishId?.let { "dish_id" to it },
                )
                val out = Api.actChat("log_meal", body(*args.toTypedArray()))
                val confirm = out.cards.mapIndexedNotNull { i, c -> Cards.toMsg(c, i, "act") }.filterIsInstance<ChatMsg.Confirm>().firstOrNull()
                notify("${m.name} logged", confirm?.lede)
                nudgeId?.let(::markNudgeDone)
                reloadDeck()
            } catch (_: Exception) {
                patch { copy(planDone = planDone - key) }
                refuse("Couldn't log it — the server refused.")
            }
        }
    }

    /** Save, on an idea: it joins the dish library and is a dish like any other after that. */
    fun savePlanIdea(m: PlanMeal) {
        val key = "save:${m.slot}"
        if (key in s.planDone || m.dishId != null) return
        patch { copy(planDone = planDone + key) }
        launch {
            try {
                Api.actChat("keep_dish", body("name" to m.name, "protein_g" to m.protein, "kcal" to m.kcal, "meal_type" to m.slot))
                notify("${m.name} saved to your dishes")
                runCatching { loadDishes() }
            } catch (_: Exception) {
                patch { copy(planDone = planDone - key) }
                refuse("Not saved — the server refused.")
            }
        }
    }

    /**
     * Done, on the workout: each library exercise is marked done today, and the
     * workout habit — if one is tracked — gets the session, its minutes and its
     * kind. An exercise that is only an idea is not added to the library by a tick.
     * From a nudge's page, the nudge is done with it.
     */
    fun doneWorkout(w: PlanWorkout, nudgeId: String? = null) {
        if ("workout" in s.planDone || w.kind == "rest") return
        patch { copy(planDone = planDone + "workout") }
        launch {
            try {
                val day = s.todayIso
                w.exercises.mapNotNull { it.exerciseId }.forEach {
                    Api.actChat("log_exercise", body("exercise_id" to it, "local_day" to day))
                }
                val habit = s.habits.firstOrNull { h ->
                    h.direction == "build" && listOf("workout", "gym", "exercise").any { h.name.lowercase().contains(it) }
                }
                if (habit != null) {
                    Api.actChat("log_day", body("local_day" to day, "habits" to listOf(
                        mapOf("habit" to habit.name, "amount" to w.minutes, "note" to w.kind),
                    )))
                }
                notify("${w.name} done", w.minutes?.let { "$it min" })
                nudgeId?.let(::markNudgeDone)
                reloadDeck()
                runCatching { loadExercises() }
            } catch (_: Exception) {
                patch { copy(planDone = planDone - "workout") }
                refuse("Couldn't log it — the server refused.")
            }
        }
    }

    init {
        patch { copy(homeWidgets = savedWidgets(), bellOpenedAt = savedBell()) }
        // The limit is the server's number, refetched whenever the rows it is
        // built from change — one per burst, not five in 160ms.
        viewModelScope.launch {
            _state.map { listOf(it.tx, it.fixedTx, it.borrowed, it.pending, it.profile, it.booted) }
                .distinctUntilChanged()
                .drop(1)
                .debounce(150)
                .collect {
                    if (s.booted) {
                        loadLimit()
                        // A payment gone or moved changes what is owed: the lines follow it.
                        loadCommitments()
                    }
                }
        }
    }

    /* ─── boot ─────────────────────────────────────────────────────────── */

    /** Load the deck, then everything the cards read from state. */
    fun boot() = launch {
        try {
            load()
        } catch (e: Exception) {
            if (e.status() == 401) return@launch
            patch { copy(bootError = e.message ?: "Didn't reach the server.") }
        }
    }

    /** The deck, then everything else, in parallel. Booted once the deck is in — the gate needs only that. */
    private suspend fun load() {
        seed(Api.fetchDeck())
        patch { copy(booted = true, bootError = null) }
        loadLimit()
        loadCommitments()
        loadActivity()
        loadPlan()
        listOf(
            viewModelScope.async { runCatching { loadPantry() } },
            viewModelScope.async { runCatching { loadDishes() } },
            viewModelScope.async { runCatching { loadHabits() } },
            viewModelScope.async { loadWeighIns() },
            viewModelScope.async { runCatching { loadSchedules() } },
            viewModelScope.async { runCatching { loadPeople() } },
            viewModelScope.async { runCatching { loadExercises() } },
            viewModelScope.async { runCatching { loadPlaces() } },
            viewModelScope.async { runCatching { loadChat() } },
            viewModelScope.async { loadNudges() },
        ).awaitAll()
    }

    /** A fresh deck re-seeds everything seeded from it. */
    private fun seed(d: DeckData) {
        val owedBy = prefs.getString(FIRST_RUN_KEY, null)
        // Finished here, not yet on the server: still finished, and said again.
        val owed = d.onboarding.doneAt == null && owedBy != null && owedBy == d.profile.id
        if (d.onboarding.doneAt != null && owedBy == d.profile.id) prefs.edit().remove(FIRST_RUN_KEY).apply()
        patch {
            copy(
                today = d.today, todayIso = d.todayIso, monthDays = d.monthDays,
                tx = d.tx, fixedTx = d.fixedTx, meals = d.meals, todos = d.todos, workouts = d.workouts,
                habitLogs = d.habitLogs, pending = d.pending, borrowed = d.borrowed, repayments = d.repayments,
                lentMonth = d.lentMonth, repaidMonth = d.repaidMonth, borrowedMonth = d.borrowedMonth,
                paidBackMonth = d.paidBackMonth, profile = d.profile,
                onboarding = if (owed) Onboarding(Instant.now().toString()) else d.onboarding,
                projects = d.projects, salary = d.income,
                salaryToday = d.salaryToday, incomeSources = d.incomeSources, bankBalance = d.bankBalance,
                sleep = d.sleep,
            )
        }
        if (owed) sendFirstRunDone(Instant.now().toString())
    }

    /**
     * Refetch the deck. The agent's writes are not optimistic — only the
     * server knows what its tools actually did — so a turn ends with this.
     */
    suspend fun reloadDeck() {
        seed(Api.fetchDeck())
        // A payment may have settled, or stopped settling, a commitment.
        loadCommitments()
        // A write the plan read may have happened; the server knows, and keeps
        // the plan when nothing it read changed.
        loadPlan()
    }

    fun reloadDeckAsync() = launch { runCatching { reloadDeck() } }

    /**
     * Back in front. A phone app sits in memory for days, where a web tab is
     * usually reloaded: it slept through midnight and still called yesterday
     * "today" (₹160 spent, on a day with nothing yet). The web, the nightly
     * run and the work sync may also have written since. So the deck — and
     * with it the anchor day — is fetched again, and the limit follows it.
     */
    fun resumed() {
        if (!s.booted) return
        launch {
            runCatching { reloadDeck() }
            loadLimit()
            loadActivity()
            // The morning's nudges may have been written while the app slept.
            loadNudges()
        }
    }

    /**
     * Home's Activity: whether Health Connect may be read, and if so today's
     * steps and calories and the week's sessions. On the phone only — a
     * failure leaves the widget saying what it can, never a made-up zero.
     */
    fun loadActivity() = launch {
        val app = getApplication<Application>()
        val access = runCatching { Health.access(app) }.getOrDefault(HealthAccess.Unavailable)
        val day = if (access == HealthAccess.Granted) runCatching { Health.read(app, s.todayIso) }.getOrNull() else null
        patch { copy(healthAccess = access, activity = day) }
    }

    fun reset() {
        _state.value = AppState(homeWidgets = savedWidgets(), bellOpenedAt = savedBell())
    }

    /* ─── receipts ─────────────────────────────────────────────────────── */

    private var toastJob: Job? = null

    /** A receipt, not a message: it shows above the composer and goes. */
    fun notify(text: String, sub: String? = null, failed: Boolean = false) {
        toastJob?.cancel()
        patch { copy(toast = Toast(System.currentTimeMillis(), text, sub, failed)) }
        toastJob = launch {
            delay(3200)
            patch { copy(toast = null) }
        }
    }

    /** A refusal, said as one: the same toast with a ✕, never the success tick. */
    private fun refuse(text: String) = notify(text, failed = true)

    fun dismissToast() {
        toastJob?.cancel()
        patch { copy(toast = null) }
    }

    private fun push(vararg msgs: ChatMsg, extra: AppState.() -> AppState = { this }) =
        patch { extra().copy(chat = chat + msgs) }

    private suspend fun loadLimit() {
        try {
            val info = Api.fetchLimit(s.todayIso)
            patch { copy(limitInfo = info) }
        } catch (_: Exception) {
            /* quiet: the card shows — and the deck does not depend on it */
        }
    }

    private val limit get() = s.limitInfo?.limit ?: 0

    /** What is owed this month, line by line. A failed read keeps what was showing — quiet, like the limit. */
    suspend fun loadCommitments() {
        try {
            val page = Api.fetchCommitments()
            patch { copy(commitments = page) }
        } catch (_: Exception) {
            /* quiet: the page says what it has, and Home does not depend on it */
        }
    }

    fun ledger(st: AppState = s) = Ledger(
        tx = st.tx, meals = st.meals, pantry = st.pantry, dishes = st.dishes, today = st.todayIso,
        proteinTarget = st.profile.proteinTarget,
    )

    /* ─── derived ──────────────────────────────────────────────────────── */

    private val greetedKey = "spica.lockedGreetedOn"

    fun view(st: AppState): DerivedView {
        val greeted = prefs.getString(greetedKey, null) == st.todayIso
        return derive(st, greeted)
    }

    /** Mark the salary line as shown for today, so tomorrow's greeting is the plain one. */
    fun markGreeted() = prefs.edit().putString(greetedKey, s.todayIso).apply()

    private fun settleMeal(id: String, failed: Boolean) =
        patch { copy(meals = meals.map { if (it.id == id) it.copy(pending = false, failed = failed) else it }) }

    /* ─── suggestion chips ─────────────────────────────────────────────── */

    /**
     * Every chip is a sentence, and a tap sends it to the agent. On the web the
     * regular chips wrote a row themselves with hardcoded macros and answered
     * with a line the phone made up — never saved to the thread, so the web
     * showed something different for the same moment. One path, one voice: a
     * reply on screen is always one the server has.
     *
     * The chips are your own repeats, or nothing. There is no card in front
     * any more to say which ledger you mean, so the repeats come from both, a
     * spend and a meal in turn.
     */
    fun suggestions(st: AppState, v: DerivedView): List<Suggestion> {
        if (!v.canLog) return emptyList()
        val spends = Chips.spends(st.tx, st.todayIso)
        val meals = Chips.meals(st.meals, st.todayIso)
        val picks = (0 until maxOf(spends.size, meals.size)).flatMap { i -> listOfNotNull(spends.getOrNull(i), meals.getOrNull(i)) }
        return picks.filter { it.id !in st.usedSuggs }.take(Chips.TOP + 1).map { p ->
            Suggestion(p.id, p.name, p.tag) {
                patch { copy(usedSuggs = usedSuggs + p.id) }
                ask(p.send)
            }
        }
    }

    /* ─── the back stack ───────────────────────────────────────────────── */

    /**
     * Open a screen over whatever is on top. One already on the stack is gone
     * back to instead, so nothing is stacked twice and Report ⇄ Commitments
     * cannot loop. Opening a screen is a context switch: the keyboard goes,
     * and so do the composer's edit and context — Back's edit step can then
     * only ever act on the layer that shows the composer.
     */
    fun pushScreen(sc: Screen) = patch {
        val at = stack.indexOf(sc)
        copy(
            stack = if (at >= 0) stack.take(at + 1) else stack + sc,
            composing = false, editing = null, context = null, typed = if (editing != null) "" else typed,
        )
    }

    /**
     * Back one level, to whatever opened the top. With `from`, only when that
     * is still the top — a page popping itself passes its own entry, so a
     * double tap cannot skip a level. Leaving a page leaves its composer's
     * edit and context behind with it.
     */
    fun pop(from: Screen? = null) = patch {
        val top = stack.lastOrNull()
        if (top == null || (from != null && top != from)) this
        else copy(
            stack = stack.dropLast(1),
            composing = false, editing = null, context = null, typed = if (editing != null) "" else typed,
        )
    }

    /**
     * System back, in one order: the composer's edit, then its context — only
     * where the composer is drawn — then the top screen, then Chat's open
     * tray. The keyboard, a popover, a dialog or a sheet take back before
     * this in their own windows; a page's open editor takes it in the page.
     */
    fun back() {
        val st = s
        when {
            st.editing != null && st.composerShown -> cancelEdit()
            st.context != null && st.composerShown -> clearContext()
            st.stack.isNotEmpty() -> pop()
            st.openRow != null -> patch { copy(openRow = null) }
        }
    }

    /** Leave every screen for Chat — a nudge's Ask, a question sent from a page. The pager slides there. */
    fun goChat() = patch { copy(stack = emptyList(), toChat = toChat + 1) }

    /** Home slid to Chat: the request is spent, so a recomposition never slides there again. */
    fun chatShown() {
        if (s.toChat != 0) patch { copy(toChat = 0) }
    }

    /* ─── chrome ───────────────────────────────────────────────────────── */

    /** ☰: the menu, a place you come back to — its rows push their pages over it. */
    fun openMenu() = pushScreen(Screen.Menu)

    /** Swiped back to Home: the keyboard and the tray belong to Chat. */
    fun leaveChat() {
        if (s.composing || s.openRow != null) patch { copy(composing = false, openRow = null) }
    }
    fun setTyped(t: String) = patch { copy(typed = t) }

    fun setComposing(c: Boolean) = patch { copy(composing = c) }

    /** Home's Today widget: every task, in the thread. */
    fun showAllTasks() = push(Msgs.user("show all tasks"), Msgs.todo("all"))

    /* ─── the person ───────────────────────────────────────────────────── */

    fun openProfile() = openProfileAt(null)

    /** A group of Profile, over the grid — or over whatever opened it, with no grid under it. */
    fun openProfileGroup(g: ProfileGroup) = pushScreen(Screen.Profile(g))

    private fun openProfileAt(group: ProfileGroup?) {
        pushScreen(Screen.Profile(group))
        launch {
            try {
                val m = viewModelScope.async { Api.listMemories() }
                val w = viewModelScope.async { Api.listWeighIns() }
                val memories = m.await()
                val weighIns = w.await()
                patch { copy(memories = memories, weighIns = weighIns, weighInsLoad = Load.Loaded) }
            } catch (_: Exception) {
                push(Msgs.stub("Profile —", "Memory and weigh-ins did not load. Is the server up?"))
            }
        }
    }

    /** Nudges' *Change when nudges come*: Daily runs alone, over Nudges — Back returns to them, not to a grid never seen. */
    fun openDailyRuns() {
        openProfileAt(ProfileGroup.Runs)
        launch { runCatching { loadSchedules() } }
    }

    /** Put the opening of a sentence in the composer and hand over the cursor. */
    fun compose(text: String) = patch { copy(composing = true, typed = text, composeFocus = composeFocus + 1) }

    /** One field. True when the server took it. */
    suspend fun saveField(id: FieldId, raw: String): Boolean {
        val before = s.profile
        // Saved empty: the field is cleared — null on the wire — where it can be.
        val edit = (if (raw.isBlank()) ProfileEdit.clear(id, before) else ProfileEdit.parse(id, "${id.id} $raw", before)) ?: return false
        patch { copy(profile = edit.profile) }
        return try {
            val saved = Api.patchUser(edit.json())
            patch { copy(profile = saved) }
            true
        } catch (_: Exception) {
            patch { copy(profile = before) }
            false
        }
    }

    /**
     * Every weigh-in, newest first — what a weight card counts its change
     * from. A failure before any list was read is Failed, and the cards say
     * nothing about the reading before; a refetch that fails keeps the list.
     */
    suspend fun loadWeighIns() {
        val rows = runCatching { Api.listWeighIns() }.getOrNull()
        if (rows != null) patch { copy(weighIns = rows, weighInsLoad = Load.Loaded) }
        else patch { if (weighInsLoad == Load.Loaded) this else copy(weighInsLoad = Load.Failed) }
    }

    suspend fun saveWeighIn(raw: String): Boolean {
        val kg = ProfileEdit.parseKg(raw) ?: return false
        val row = WeighInRow(Ulid.next(), s.todayIso, kg, pending = true)
        patch { copy(weighIns = listOf(row) + weighIns.filter { it.day != row.day }) }
        return try {
            val saved = Api.createWeighIn(row.id, row.day, kg)
            patch { copy(weighIns = weighIns.map { if (it.id == row.id) saved else it }) }
            true
        } catch (_: Exception) {
            patch { copy(weighIns = weighIns.map { if (it.id == row.id) it.copy(pending = false, failed = true) else it }) }
            false
        }
    }

    /** A reading deleted: gone from Profile, and struck on the card that logged it. The day's copy goes with it, on the server. */
    fun deleteWeighIn(id: String) {
        val before = s.weighIns
        patch { copy(weighIns = weighIns.filter { it.id != id }, deletedRows = if (id in deletedRows) deletedRows else deletedRows + id) }
        launch {
            try {
                Api.deleteWeighIn(id)
            } catch (e: Exception) {
                patch { copy(weighIns = before, deletedRows = deletedRows - id) }
                if (e.status() != 401) refuse("Not deleted — the server refused.")
            }
        }
    }

    suspend fun saveMemory(id: String, text: String): Boolean {
        val before = s.memories.firstOrNull { it.id == id }
        val clean = text.trim()
        if (before == null || clean.isEmpty()) return false
        patch { copy(memories = memories.map { if (it.id == id) it.copy(text = clean, pending = true) else it }) }
        return try {
            val saved = Api.patchMemory(id, clean)
            patch { copy(memories = memories.map { if (it.id == id) saved else it }) }
            true
        } catch (_: Exception) {
            patch { copy(memories = memories.map { if (it.id == id) before.copy(failed = true) else it }) }
            false
        }
    }

    suspend fun addMemory(slugIn: String, kind: String, textIn: String): Boolean {
        val slug = slugIn.trim().lowercase()
        val text = textIn.trim()
        if (!Regex("^[a-z0-9][a-z0-9-]*$").matches(slug) || text.isEmpty()) return false
        val row = MemoryRow(Ulid.next(), slug, kind, text, "user", Instant.now().toString(), pending = true)
        // Same slug → the server updates that row and returns its id.
        patch { copy(memories = listOf(row) + memories.filter { it.slug != slug }) }
        return try {
            val saved = Api.createMemory(row.id, slug, kind, text)
            patch { copy(memories = memories.map { if (it.id == row.id) saved else it }) }
            true
        } catch (_: Exception) {
            patch { copy(memories = memories.map { if (it.id == row.id) it.copy(pending = false, failed = true) else it }) }
            false
        }
    }

    fun removeMemory(id: String) {
        val before = s.memories
        patch { copy(memories = memories.filter { it.id != id }) }
        launch {
            try {
                Api.deleteMemory(id)
            } catch (_: Exception) {
                patch { copy(memories = before) }
                push(Msgs.stub("Not deleted —", "Server refused. The memory is back."))
            }
        }
    }

    /* ─── the first run — spec/done/onboarding-goals.md ──────────────────────── */

    private val fr get() = s.firstRun

    private fun putRun(f: FirstRun.() -> FirstRun) = patch { copy(firstRun = firstRun.f()) }

    /** Screen 2: a pick on, or off again. None is picked to start. */
    fun togglePick(p: Pick) = putRun { copy(picks = if (p in picks) picks - p else picks + p) }

    /**
     * Home's widgets, a layout kept on this phone: exactly what the picks
     * switch on, in Home's order, Today first. Nothing picked is the default.
     * Written only as the flow ends — Get started, or a Skip — so picks made
     * and then skipped, or left behind by a dead process, never reach Home.
     */
    private fun writeWidgets(picks: Set<Pick>) {
        val next = if (picks.isEmpty()) HomeWidget.DEFAULT else widgetsFor(picks)
        prefs.edit().putString(WIDGETS_KEY, next.joinToString(",")).apply()
        patch { copy(homeWidgets = next) }
    }

    /** Screen 2's Continue: on to the questions — or, with nothing picked, *Skip for now*, and Home. */
    fun choosePicks() {
        if (fr.picks.isEmpty()) return skipFirstRun()
        // A new Continue is a new go at the questions, even after a Skip on screen 3.
        putRun { copy(step = FirstRunStep.Ask, skipped = false) }
        // One mid-answer waits for it: the answer moves the questions on itself.
        if (fr.busy) return
        val open = fr.at
        if (open != null) {
            // Coming back: the open question stays — unless its pick was taken off, and then the next is asked.
            if (open.pick == null || open.pick in fr.picks) return
            putRun { copy(at = null, again = 0, asked = asked - open) }
            askNext()
            return
        }
        // The rows first, so nothing they hold is asked; a new pick appends its question.
        putRun { copy(busy = true) }
        launch {
            loadFirstRunRows()
            // Gone back to screen 2 while the rows were read: nothing is asked behind it.
            val here = fr.step == FirstRunStep.Ask
            putRun { copy(busy = false, started = started || here) }
            if (here) askNext()
        }
    }

    /** Screen 2's Skip, and *Skip for now*: Home keeps its default widgets, and the flow is over. */
    fun skipFirstRun() {
        writeWidgets(emptySet())
        finishFirstRun()
    }

    /**
     * What the rows already hold — the profile, the weigh-ins, the memories,
     * the habits. Read before questions are chosen, so nothing set is asked
     * again, after each answer, and on screen 4, which shows only live rows.
     * A failed read keeps what was there.
     */
    private suspend fun loadFirstRunRows() {
        try {
            val p = viewModelScope.async { Api.fetchMe() }
            val w = viewModelScope.async { Api.listWeighIns() }
            val m = viewModelScope.async { Api.listMemories() }
            val h = viewModelScope.async { Api.fetchHabits() }
            val profile = p.await()
            val weighIns = w.await()
            val memories = m.await()
            val habits = h.await()
            patch { copy(profile = profile, weighIns = weighIns, weighInsLoad = Load.Loaded, memories = memories, habits = habits) }
        } catch (e: kotlinx.coroutines.CancellationException) {
            throw e
        } catch (_: Exception) {
            /* quiet: a question already answered is asked again, and its answer writes the same rows */
        }
    }

    /** The next question the picks want and the rows do not hold — or none, and screen 3 is done. Never after a Skip. */
    private fun askNext() {
        if (fr.skipped) return
        val st = s
        val next = Question.entries.firstOrNull { q ->
            q !in st.firstRun.asked && (q.pick == null || q.pick in st.firstRun.picks) &&
                !alreadyAnswered(q, st.profile, st.weighIns, st.memories, st.habits)
        }
        putRun {
            if (next == null) copy(at = null, again = 0)
            else copy(
                at = next, again = 0, asked = asked + next,
                thread = thread + next.lines.mapIndexed { i, line -> FirstRunLine.Agent("ask-${next.id}-$i", line) },
            )
        }
    }

    fun setFirstRunTyped(t: String) = putRun { copy(typed = t) }

    /** A chip adds its word after what is in the bar, comma-separated. It never sends. */
    fun firstRunChip(word: String) = putRun {
        val base = typed.trimEnd().trimEnd(',').trimEnd()
        copy(typed = if (base.isEmpty()) word else "$base, $word", focus = focus + 1)
    }

    fun firstRunListening() = putRun { copy(listening = true) }

    /** What the recogniser heard goes in the bar, after anything there — never sent on its own. */
    fun firstRunHeard(said: String?) = putRun {
        val words = said?.trim().orEmpty()
        if (words.isEmpty()) copy(listening = false)
        else {
            val base = typed.trimEnd()
            copy(listening = false, typed = if (base.isEmpty()) words else "$base $words", focus = focus + 1)
        }
    }

    /** Edit on a card: it rides above the bar, and the correction goes ahead of your words — as Change does in the chat. */
    fun editFirstRunCard(question: Question, context: ComposeContext) =
        putRun { copy(step = FirstRunStep.Ask, context = context, contextOf = question, focus = focus + 1, problem = null) }

    fun clearFirstRunContext() = putRun { copy(context = null, contextOf = null) }

    /** The answer on its way — what Back puts back in the bar when it cancels the wait. */
    private class Waiting(val job: Job, val said: FirstRunLine.Said, val typed: String, val context: ComposeContext?, val contextOf: Question?)

    private var waiting: Waiting? = null

    /**
     * Send what is in the bar: an answer to the question asked, or — with an
     * Edit's card above it — a correction to that card's row. The agent
     * writes through the app's own tools and the writes come back as cards.
     * Nothing is resent on its own; a failure leaves the words in the bar.
     */
    fun sendFirstRunAnswer() {
        val f = fr
        val raw = f.typed.trim()
        if (raw.isEmpty() || f.busy) return
        val context = f.context
        val question = f.at ?: f.contextOf ?: return
        val said = FirstRunLine.Said("said-${System.currentTimeMillis()}", raw, context?.label)
        // The person as they were, for each card's Undo.
        val before = s.profile
        putRun { copy(thread = thread + said, typed = "", context = null, contextOf = null, busy = true, problem = null) }
        // Held until it is known as the wait Back can cancel.
        val job = viewModelScope.launch(start = CoroutineStart.LAZY) {
            try {
                val out = Api.onboardingTurn(question.id, context?.let { "${it.prefix} $raw" } ?: raw, s.todayIso)
                waiting = null
                val at = "turn-${System.currentTimeMillis()}"
                val cards = out.cards.mapIndexedNotNull { i, c -> Cards.toMsg(c, i, at) as? ChatMsg.Confirm }
                    .map { FirstRunLine.Card(it.id, it, question, before) }
                val reply = out.reply?.trim()?.takeIf { it.isNotEmpty() }
                putRun { copy(thread = thread + cards) }
                // Skipped past on the way, or a correction: the questions stay where they are.
                val open = context == null && fr.at == question
                // Done — or a second answer that cannot be read, which moves on as a skip.
                val moveOn = open && (out.next || reply == SAY_AGAIN && fr.again > 0)
                if (!moveOn && reply != null) putRun {
                    copy(thread = thread + FirstRunLine.Agent("reply-$at", reply), again = if (open && reply == SAY_AGAIN) again + 1 else again)
                }
                // The rows again before the next question, so one this answer already covered is not asked.
                loadFirstRunRows()
                putRun { copy(busy = false) }
                if (moveOn) askNext()
            } catch (e: kotlinx.coroutines.CancellationException) {
                throw e
            } catch (e: Exception) {
                waiting = null
                when (e.status()) {
                    401 -> Unit
                    // Finished elsewhere — another device: the flag is on the server, and Home is next.
                    409 -> finishFirstRun()
                    // The day's cap: nothing was written, and no more can be today.
                    429 -> putRun {
                        copy(
                            busy = false, at = null, capped = true,
                            thread = thread + FirstRunLine.Agent("cap-${System.currentTimeMillis()}", "That’s all I can take in today. You can tell me the rest later."),
                        )
                    }
                    // A timeout, the network, the model: nothing written, and the words go back in the bar.
                    else -> putRun {
                        copy(
                            busy = false, thread = thread.filter { it.id != said.id }, typed = raw, context = context,
                            contextOf = if (context != null) question else null, problem = "I couldn’t take that in — try again?",
                        )
                    }
                }
            }
        }
        waiting = Waiting(job, said, raw, context, if (context != null) question else null)
        job.start()
    }

    /** Back while the agent works: the wait is cancelled, and the answer is back in the bar to send again. */
    private fun cancelFirstRunAnswer() {
        val w = waiting ?: return
        waiting = null
        w.job.cancel()
        putRun { copy(busy = false, thread = thread.filter { it.id != w.said.id }, typed = w.typed, context = w.context, contextOf = w.contextOf) }
    }

    /**
     * Undo on a card: the write is taken back through the route that owns its
     * row, as Undo does in the chat — a profile fact put back to what it was
     * before the answer, the weigh-in, habit, memory or task deleted. The card
     * stays, struck. A refusal is said once under the thread, as the web does.
     */
    fun undoFirstRunCard(msg: ChatMsg.Confirm) {
        if (msg.state == "deleted") return
        val card = fr.thread.firstNotNullOfOrNull { (it as? FirstRunLine.Card)?.takeIf { c -> c.msg.id == msg.id } } ?: return
        // A later write to the same column holds the value now: putting this one back would overwrite it.
        if (fr.superseded(card)) return
        val id = msg.rowId
        putRun { copy(problem = null) }
        launch {
            try {
                when (msg.source) {
                    "profile" -> {
                        // The age card is the date of birth it was turned into.
                        val field = card.column?.let { c -> FieldId.entries.firstOrNull { it.wire == c } } ?: return@launch
                        val saved = Api.patchUser(body(field.wire to ProfileEdit.wireValue(field, card.before)))
                        patch { copy(profile = saved) }
                    }
                    "body" -> {
                        id ?: return@launch
                        if (msg.fields.any { it.key == "weight_kg" }) {
                            Api.deleteWeighIn(id)
                            patch { copy(weighIns = weighIns.filter { it.id != id }) }
                        } else {
                            Api.deleteHabit(id)
                            patch { copy(habits = habits.filter { it.id != id }) }
                        }
                    }
                    "memory" -> {
                        id ?: return@launch
                        Api.deleteMemory(id)
                        patch { copy(memories = memories.filter { it.id != id }) }
                    }
                    "work" -> {
                        id ?: return@launch
                        Api.deleteTask(id)
                        patch { copy(todos = todos.filter { it.id != id }) }
                    }
                    else -> return@launch
                }
                putRun { copy(thread = thread.map { if (it is FirstRunLine.Card && it.msg.id == msg.id) it.copy(msg = it.msg.copy(state = "deleted")) else it }) }
                if (id != null) patch { copy(deletedRows = if (id in deletedRows) deletedRows else deletedRows + id) }
            } catch (e: Exception) {
                if (e.status() != 401) putRun { copy(problem = "That didn’t undo — try again?") }
            }
        }
    }

    /**
     * Screen 3's Skip: the rest of the questions go unasked, and screen 4
     * shows what was given. An answer still with the agent is called off
     * first, and nothing that lands after asks another question.
     */
    fun skipFirstRunQuestions() {
        cancelFirstRunAnswer()
        putRun { copy(at = null, started = true, skipped = true, context = null, contextOf = null) }
        openAllSet()
    }

    /** Screen 4, which reads the rows again on the way in — never the cards' copies. */
    fun openAllSet() {
        putRun { copy(step = FirstRunStep.Ready, context = null, contextOf = null) }
        launch { loadFirstRunRows() }
    }

    /** Edit on screen 4: back to the thread, where each write has its own Edit. Continue comes back. */
    fun editFromAllSet() = putRun { copy(step = FirstRunStep.Ask) }

    /** Back: from screen 4 to 3; on 3 the Edit goes first, then a wait, then the screen. Screen 2 does not take it. */
    fun firstRunBack() {
        val f = fr
        when (f.step) {
            FirstRunStep.Ready -> putRun { copy(step = FirstRunStep.Ask) }
            FirstRunStep.Ask -> when {
                f.context != null -> clearFirstRunContext()
                waiting != null -> cancelFirstRunAnswer()
                else -> putRun { copy(step = FirstRunStep.Choose) }
            }
            FirstRunStep.Choose -> Unit
        }
    }

    /** Get started: the widgets the picks chose, then the flag. */
    fun getStarted() {
        if (fr.leaving) return
        writeWidgets(fr.picks)
        finishFirstRun()
    }

    /**
     * Over, for good — Get started, or a Skip. The flag goes to the server and
     * the deck is read again, so the habits and targets just set are on Home;
     * then Home. A flag that does not reach the server is kept on this phone
     * and sent again on the next start: Home opens either way.
     */
    private fun finishFirstRun() {
        if (fr.leaving) return
        putRun { copy(leaving = true) }
        val at = Instant.now().toString()
        prefs.edit().putString(FIRST_RUN_KEY, s.profile.id).apply()
        launch {
            sendFirstRunDone(at).join()
            try {
                load()
            } catch (e: Exception) {
                if (e.status() == 401) return@launch
            }
            patch { copy(onboarding = if (onboarding.doneAt == null) Onboarding(at) else onboarding, firstRun = FirstRun()) }
        }
    }

    private var sendingDone: Job? = null

    /** The flag, to the server. Once it is there, nothing is owed. */
    private fun sendFirstRunDone(at: String): Job {
        sendingDone?.takeIf { it.isActive }?.let { return it }
        return launch {
            if (runCatching { Api.patchUser(body("onboarding_done_at" to at)) }.isSuccess) prefs.edit().remove(FIRST_RUN_KEY).apply()
        }.also { sendingDone = it }
    }

    /* ─── nudges ───────────────────────────────────────────────────────── */

    /**
     * The last seven days of nudges. A server without `/nudges` — a 404 — or
     * any other failure before a list was read is Failed: no dot, the page
     * says it could not load, not that there are none, and no toast, because
     * nothing the person did went wrong. A refetch that fails keeps a list
     * already read — it was the server's answer.
     */
    suspend fun loadNudges() {
        if (s.nudgesLoad != Load.Loaded) patch { copy(nudgesLoad = Load.Loading) }
        val rows = runCatching { Api.fetchNudges(7) }.getOrNull()
        if (rows != null) patch { copy(nudges = rows, nudgesLoad = Load.Loaded) }
        else patch { if (nudgesLoad == Load.Loaded) this else copy(nudgesLoad = Load.Failed) }
    }

    /** *Try again*, on the page that could not load. */
    fun retryNudges() {
        launch { loadNudges() }
    }

    /**
     * The bell: Nudges opens, and the moment is kept on this phone, so the dot
     * clears. A card names the run that made it, so a run not known yet is
     * read; Meals today's line is the plan's, so the plan is read too.
     */
    fun openNudges() {
        val now = Instant.now()
        prefs.edit().putString(BELL_KEY, now.toString()).apply()
        patch { copy(bellOpenedAt = now) }
        pushScreen(Screen.Nudges)
        launch {
            loadNudges()
            loadPlan()
            if (s.nudges.any { n -> n.scheduleId != null && s.schedules.none { it.id == n.scheduleId } }) runCatching { loadSchedules() }
        }
    }

    /** Which page a kind opens. Reminder and review have none yet. */
    fun landingOf(kind: String): Landing? = when (kind) {
        "day" -> Landing.Day
        "meals", "dinner" -> Landing.Meals
        "workout" -> Landing.Workout
        else -> null
    }

    /** Today's nudge that opens this page, if one was written and not put away. */
    fun todaysNudge(st: AppState, landing: Landing): NudgeRow? =
        st.nudges.firstOrNull { it.day == st.todayIso && !it.dismissed && landingOf(it.kind) == landing }

    /**
     * A nudge's card, tapped: its page opens and the nudge is seen. Reminder
     * and review open Chat for now — no job writes them yet, and their own
     * cards (Done, Tomorrow) and the Payments-to-check page come with the jobs.
     */
    fun openNudge(n: NudgeRow) {
        val landing = landingOf(n.kind)
        markNudgeSeen(n.id)
        if (landing == null) {
            goChat()
            return
        }
        openLanding(landing, n.id)
    }

    /**
     * A page opened from another page — Your day's next meal, its workout —
     * carries today's nudge of that kind when there is one, so acting there
     * marks it done too.
     */
    fun openLanding(landing: Landing, nudgeId: String? = null) {
        val id = nudgeId ?: todaysNudge(s, landing)?.id
        id?.let(::markNudgeSeen)
        pushScreen(Screen.Nudge(NudgePage(landing, id)))
        loadPlan()
    }

    private fun putNudge(id: String, f: (NudgeRow) -> NudgeRow) = patch { copy(nudges = nudges.map { if (it.id == id) f(it) else it }) }

    /** The server's answer replaces the optimistic row; a refusal puts the old one back. */
    private fun writeNudge(before: NudgeRow, onRefused: () -> Unit = {}, call: suspend () -> NudgeRow) = launch {
        try {
            val saved = call()
            putNudge(before.id) { saved }
        } catch (_: Exception) {
            putNudge(before.id) { before }
            onRefused()
        }
    }

    /** Opened is read. Quiet on refusal: the card's dot comes back, nothing else is wrong. */
    fun markNudgeSeen(id: String) {
        val before = s.nudges.firstOrNull { it.id == id } ?: return
        if (before.seen) return
        putNudge(id) { it.copy(seenAt = Instant.now().toString()) }
        writeNudge(before) { Api.patchNudge(id, seen = true) }
    }

    /** Acted on — a meal logged from the plan, the workout done. The act itself already said whether it worked. */
    fun markNudgeDone(id: String) {
        val before = s.nudges.firstOrNull { it.id == id } ?: return
        if (before.done) return
        putNudge(id) { it.copy(doneAt = Instant.now().toString(), seenAt = it.seenAt ?: Instant.now().toString()) }
        writeNudge(before) { Api.patchNudge(id, done = true) }
    }

    /** ⋮ Dismiss, or *Not today*: hidden for the day. */
    fun dismissNudge(id: String) {
        val before = s.nudges.firstOrNull { it.id == id } ?: return
        if (before.dismissed) return
        putNudge(id) { it.copy(dismissedAt = Instant.now().toString()) }
        writeNudge(before, onRefused = { refuse("Not dismissed — the server refused.") }) { Api.patchNudge(id, dismissed = true) }
    }

    /** *Not today*, on the Workout page: the nudge goes for the day, and so does its page — that page only. */
    fun notToday(id: String, page: NudgePage) {
        dismissNudge(id)
        pop(Screen.Nudge(page))
    }

    /** ⋮ Turn these off: the Daily run that writes this nudge is switched off. */
    fun turnOffNudges(n: NudgeRow) {
        val sid = n.scheduleId ?: return
        val label = s.schedules.firstOrNull { it.id == sid }?.label
        launch {
            if (editSchedule(sid, enabled = false)) {
                notify(if (label != null) "$label turned off" else "Turned off", "Back on any time in Daily runs")
            }
        }
    }

    /**
     * *Ask about this*: the nudge enters the conversation only now, and only
     * as context on the composer — what it said, sent ahead of your words.
     */
    fun askAboutNudge(label: String, said: String?) {
        val about = label.lowercase()
        setContext(ComposeContext(label, if (said != null) "About $about — you said: “$said”." else "About $about:"))
        goChat()
    }

    /** No protein target on Meals today: Set target, on the composer, in Chat — as Diet does. */
    fun setTargetFromNudge(c: ComposeContext) {
        setContext(c)
        goChat()
    }

    /* ─── schedules and habits ─────────────────────────────────────────── */

    suspend fun loadSchedules() {
        val rows = Api.fetchSchedules()
        patch { copy(schedules = rows) }
    }

    /** Move a scheduled job, or turn it off. Reverted on refusal. */
    suspend fun editSchedule(id: String, at: String? = null, enabled: Boolean? = null): Boolean {
        val before = s.schedules
        patch {
            copy(schedules = schedules.map {
                if (it.id == id) it.copy(at = at ?: it.at, enabled = enabled ?: it.enabled, pending = true) else it
            })
        }
        return try {
            val pairs = buildList {
                if (at != null) add("at_local_time" to at)
                if (enabled != null) add("enabled" to enabled)
            }
            val saved = Api.patchSchedule(id, body(*pairs.toTypedArray()))
            patch { copy(schedules = schedules.map { if (it.id == id) saved else it }) }
            true
        } catch (_: Exception) {
            patch { copy(schedules = before) }
            refuse("Couldn't save — the server refused.")
            false
        }
    }

    suspend fun loadHabits() {
        val rows = Api.fetchHabits()
        patch { copy(habits = rows) }
    }

    suspend fun addHabit(name: String, direction: String, unit: String?): Boolean = try {
        val made = Api.createHabit(name, direction, unit)
        patch { copy(habits = (habits + made).sortedBy { it.name.lowercase() }) }
        true
    } catch (_: Exception) {
        refuse("Couldn't add $name — that name is probably already tracked.")
        false
    }

    suspend fun editHabit(id: String, name: String? = null, direction: String? = null, unit: String? = null, clearUnit: Boolean = false): Boolean {
        val before = s.habits
        patch {
            copy(habits = habits.map {
                if (it.id == id) it.copy(
                    name = name ?: it.name, direction = direction ?: it.direction,
                    unit = if (clearUnit) null else unit ?: it.unit, pending = true,
                ) else it
            })
        }
        return try {
            val pairs = buildList<Pair<String, Any?>> {
                if (name != null) add("name" to name)
                if (direction != null) add("direction" to direction)
                if (unit != null || clearUnit) add("unit" to unit)
            }
            val saved = Api.patchHabit(id, body(*pairs.toTypedArray()))
            patch { copy(habits = habits.map { if (it.id == id) saved else it }) }
            true
        } catch (_: Exception) {
            patch { copy(habits = before) }
            refuse("Couldn't save — the server refused.")
            false
        }
    }

    fun flipHabit(h: HabitRow) = launch { editHabit(h.id, direction = if (h.direction == "build") "break" else "build") }

    /** Stop tracking it. The ticks stay: that you went in August is still true. */
    fun removeHabit(id: String) {
        val before = s.habits
        patch { copy(habits = habits.filter { it.id != id }) }
        launch {
            try {
                Api.deleteHabit(id)
            } catch (_: Exception) {
                patch { copy(habits = before) }
                refuse("Couldn't stop tracking — the server refused.")
            }
        }
    }

    /* ─── library: dishes, people, exercises, places ──────────────────── */

    suspend fun loadDishes() {
        val rows = Api.fetchDishes(true)
        patch { copy(dishes = rows) }
    }

    fun toggleSaveDish(id: String) {
        val before = s.dishes
        val row = before.firstOrNull { it.id == id } ?: return
        patch { copy(dishes = dishes.map { if (it.id == id) it.copy(saved = !it.saved) else it }) }
        launch {
            try {
                if (row.saved) Api.unsaveDish(id) else Api.saveDish(id)
                loadDishes()
            } catch (_: Exception) {
                patch { copy(dishes = before) }
                push(Msgs.stub("Not saved —", "The server refused. Nothing changed."))
            }
        }
    }

    suspend fun loadPeople() {
        val rows = Api.fetchPeople()
        patch { copy(people = rows) }
    }

    /** Not optimistic: the server sends the row back with its derived numbers. */
    suspend fun filePerson(id: String, b: JsonObject): Boolean = try {
        val row = Api.patchCounterparty(id, b)
        patch { copy(people = people.map { if (it.id == id) row else it }) }
        true
    } catch (_: Exception) {
        push(Msgs.stub("Not saved —", "The server refused. Nothing changed."))
        false
    }

    suspend fun addPerson(name: String, b: JsonObject): Boolean = try {
        val full = JsonObject(b + mapOf("id" to com.sonu.spica.data.toJson(Ulid.next()), "raw_name" to com.sonu.spica.data.toJson(name)))
        val row = Api.createCounterparty(full)
        patch { copy(people = people + row) }
        true
    } catch (_: Exception) {
        push(Msgs.stub("Not added —", "Either that name is already here, or the server refused."))
        false
    }

    suspend fun loadExercises() {
        val rows = Api.fetchExercises()
        patch { copy(exercises = rows) }
    }

    /** One more time. The server increments and stamps the day in one write. */
    fun didExerciseOnce(id: String) = launch {
        try {
            val row = Api.didExercise(id, s.todayIso)
            patch { copy(exercises = exercises.map { if (it.id == id) row else it }) }
        } catch (_: Exception) {
            push(Msgs.stub("Not counted —", "The server refused. Nothing changed."))
        }
    }

    suspend fun addExercise(b: JsonObject): Boolean = try {
        val full = JsonObject(b + mapOf("id" to com.sonu.spica.data.toJson(Ulid.next()), "source" to com.sonu.spica.data.toJson("manual")))
        val made = Api.createExercise(full)
        patch { copy(exercises = exercises + made) }
        true
    } catch (_: Exception) {
        push(Msgs.stub("Not added —", "The server refused. Nothing changed."))
        false
    }

    suspend fun loadPlaces() {
        val rows = Api.fetchPlaces()
        patch { copy(places = rows) }
    }

    suspend fun addPlace(b: JsonObject): Boolean = try {
        val made = Api.createPlace(JsonObject(b + ("id" to com.sonu.spica.data.toJson(Ulid.next()))))
        patch { copy(places = places + made) }
        true
    } catch (_: Exception) {
        push(Msgs.stub("Not added —", "The server refused. Nothing changed."))
        false
    }

    suspend fun editPlace(id: String, b: JsonObject): Boolean = try {
        val row = Api.patchPlace(id, b)
        patch { copy(places = places.map { if (it.id == id) row else it }) }
        true
    } catch (_: Exception) {
        push(Msgs.stub("Not saved —", "The server refused. Nothing changed."))
        false
    }

    fun removePlace(id: String) {
        val before = s.places
        patch { copy(places = places.filter { it.id != id }) }
        launch {
            try {
                Api.deletePlace(id)
            } catch (_: Exception) {
                patch { copy(places = before) }
                push(Msgs.stub("Not removed —", "The server refused. Nothing changed."))
            }
        }
    }

    /* ─── pantry ───────────────────────────────────────────────────────── */

    suspend fun loadPantry(foodId: String? = null) {
        val rows = Api.fetchPantry(s.todayIso)
        val moves = Api.fetchPantryMoves(foodId)
        patch { copy(pantry = rows, pantryMoves = moves) }
    }

    fun loadPantryMoves(foodId: String? = null) = launch {
        runCatching { Api.fetchPantryMoves(foodId) }.onSuccess { m -> patch { copy(pantryMoves = m) } }
    }

    fun openData(section: Section? = null) {
        pushScreen(Screen.Data(section))
        launch {
            try {
                listOf(
                    viewModelScope.async { loadPantry() },
                    viewModelScope.async { loadDishes() },
                    viewModelScope.async { loadPeople() },
                    viewModelScope.async { loadExercises() },
                    viewModelScope.async { loadPlaces() },
                ).awaitAll()
            } catch (_: Exception) {
                push(Msgs.stub("Your data —", "It did not load. Is the server up?"))
            }
        }
    }

    /** A tile on the overview: its section, over the overview. Up a level is Back. */
    fun openDataSection(sec: Section) = pushScreen(Screen.Data(sec))

    /** Bought (a purchase) or Have (a stock-take). False when the amount is unusable. */
    suspend fun addPantryMove(foodId: String, grams: Double, kind: String): Boolean {
        if (!grams.isFinite() || grams <= 0) return false
        return try {
            Api.createPantryMove(Ulid.next(), foodId, grams, kind, s.todayIso)
            loadPantry()
            true
        } catch (_: Exception) {
            false
        }
    }

    /** Undo a move the user wrote. Consumption is refused by the server. */
    fun undoPantryMove(id: String) = launch {
        try {
            Api.deletePantryMove(id)
            loadPantry()
        } catch (_: Exception) {
            push(Msgs.stub("Not undone —", "The server refused. That move stands."))
        }
    }

    /** Start tracking a food. Grams, if given, land as an opening stock-take. */
    suspend fun addPantryFood(name: String, quantity: Double?, staple: Boolean, unit: String): Boolean {
        val clean = name.trim()
        if (clean.isEmpty()) return false
        return try {
            val foodId = Api.trackFood(Ulid.next(), clean, staple, unit)
            if (quantity != null && quantity > 0) Api.createPantryMove(Ulid.next(), foodId, quantity, "opening", s.todayIso)
            loadPantry()
            true
        } catch (_: Exception) {
            false
        }
    }

    suspend fun savePantrySettings(id: String, reorder: Double?, shelfLife: Int?): Boolean = try {
        Api.patchPantryItem(id, body("reorder_at_g" to reorder, "shelf_life_days" to shelfLife))
        loadPantry()
        true
    } catch (_: Exception) {
        false
    }

    suspend fun setStaple(id: String, staple: Boolean): Boolean = try {
        Api.patchPantryItem(id, body("staple" to staple))
        loadPantry()
        true
    } catch (_: Exception) {
        false
    }

    fun stopTrackingFood(id: String) {
        val before = s.pantry
        patch { copy(pantry = pantry.filter { it.id != id }) }
        launch {
            try {
                Api.stopTracking(id)
                loadPantry()
            } catch (_: Exception) {
                patch { copy(pantry = before) }
                push(Msgs.stub("Not removed —", "The server refused. It is still tracked."))
            }
        }
    }

    /* ─── udhaar ───────────────────────────────────────────────────────── */

    private data class Udhaar(
        val pending: List<PendingItem>, val borrowed: List<PendingItem>, val repayments: List<RepaymentItem>,
        val lentMonth: Int, val repaidMonth: Int, val borrowedMonth: Int, val paidBackMonth: Int,
    )

    private fun udhaarNow() = Udhaar(s.pending, s.borrowed, s.repayments, s.lentMonth, s.repaidMonth, s.borrowedMonth, s.paidBackMonth)

    private fun putUdhaar(u: Udhaar) = patch {
        copy(
            pending = u.pending, borrowed = u.borrowed, repayments = u.repayments, lentMonth = u.lentMonth,
            repaidMonth = u.repaidMonth, borrowedMonth = u.borrowedMonth, paidBackMonth = u.paidBackMonth,
        )
    }

    private fun thisMonth(iso: String) = iso.take(7) == s.todayIso.take(7)

    /** "Wapas aaya" on a lending, "wapas de diya" on a borrowing. False when refused. */
    suspend fun markRepaid(openId: String, amount: Int): Boolean {
        val before = udhaarNow()
        val open = before.pending.firstOrNull { it.id == openId } ?: before.borrowed.firstOrNull { it.id == openId } ?: return false
        if (amount <= 0 || amount > open.remaining) return false
        val day = s.todayIso
        val row = RepaymentItem(
            Ulid.next(), openId, open.label, amount, day, s.today, open.leg, open.date, open.amount, pending = true,
        )
        fun shrink(list: List<PendingItem>) =
            list.map { if (it.id == openId) it.copy(remaining = it.remaining - amount) else it }.filter { it.remaining > 0 }
        putUdhaar(
            before.copy(
                pending = if (open.leg == "lent") shrink(before.pending) else before.pending,
                borrowed = if (open.leg == "borrowed") shrink(before.borrowed) else before.borrowed,
                repayments = listOf(row) + before.repayments,
                repaidMonth = if (open.leg == "lent") before.repaidMonth + amount else before.repaidMonth,
                paidBackMonth = if (open.leg == "borrowed") before.paidBackMonth + amount else before.paidBackMonth,
            ),
        )
        return try {
            Api.createRepayment(row.id, open, amount, day)
            patch { copy(repayments = repayments.map { if (it.id == row.id) it.copy(pending = false) else it }) }
            true
        } catch (_: Exception) {
            putUdhaar(before)
            false
        }
    }

    /** A lending or a borrowing typed on the report. */
    suspend fun addOpen(leg: String, who: String, amount: Int): Boolean {
        val name = who.trim()
        if (name.isEmpty() || amount <= 0) return false
        val before = udhaarNow()
        val day = s.todayIso
        val row = PendingItem(
            Ulid.next(), leg, if (leg == "lent") "$name ko diya" else "$name se liya", amount, amount, day, s.today, pending = true,
        )
        putUdhaar(
            before.copy(
                pending = if (leg == "lent") before.pending + row else before.pending,
                borrowed = if (leg == "borrowed") before.borrowed + row else before.borrowed,
                lentMonth = if (leg == "lent") before.lentMonth + amount else before.lentMonth,
                borrowedMonth = if (leg == "borrowed") before.borrowedMonth + amount else before.borrowedMonth,
            ),
        )
        return try {
            Api.createOpen(row.id, leg, name, amount, day)
            patch {
                copy(
                    pending = pending.map { if (it.id == row.id) it.copy(pending = false) else it },
                    borrowed = borrowed.map { if (it.id == row.id) it.copy(pending = false) else it },
                )
            }
            true
        } catch (_: Exception) {
            putUdhaar(before)
            false
        }
    }

    /** Stop expecting it back. The lending becomes spend. */
    fun gift(lendingId: String) {
        val before = udhaarNow()
        val lending = before.pending.firstOrNull { it.id == lendingId } ?: return
        putUdhaar(
            before.copy(
                pending = before.pending.filter { it.id != lendingId },
                lentMonth = if (thisMonth(lending.date)) before.lentMonth - lending.amount else before.lentMonth,
            ),
        )
        if (thisMonth(lending.date)) {
            patch { copy(tx = tx + Tx(lending.id, lending.day, lending.label, "Logon ko diya", lending.amount, date = lending.date)) }
        }
        launch {
            try {
                Api.giftLending(lendingId)
            } catch (_: Exception) {
                putUdhaar(before)
                patch { copy(tx = tx.filter { it.id != lendingId }) }
                push(Msgs.stub("Not saved —", "${lending.label} is still pending; the server refused."))
            }
        }
    }

    /** Undo a repayment: the row is soft-deleted and the lending is open again. */
    fun undoRepayment(repaymentId: String) {
        val before = udhaarNow()
        val rep = before.repayments.firstOrNull { it.id == repaymentId } ?: return
        val isLent = rep.leg == "lent"
        val list = if (isLent) before.pending else before.borrowed
        val open = list.firstOrNull { it.id == rep.lendingId }
        val restored = if (open != null) {
            list.map { if (it.id == rep.lendingId) it.copy(remaining = it.remaining + rep.amount) else it }
        } else {
            // Fully repaid before this undo: rebuild the row from its own leg, date and size.
            (list + PendingItem(rep.lendingId, rep.leg, rep.label, rep.lentAmount, rep.amount, rep.lentDate, Day.dayOfMonth(rep.lentDate)))
                .sortedBy { it.date }
        }
        putUdhaar(
            before.copy(
                pending = if (isLent) restored else before.pending,
                borrowed = if (!isLent) restored else before.borrowed,
                repayments = before.repayments.filter { it.id != repaymentId },
                repaidMonth = if (isLent && thisMonth(rep.date)) before.repaidMonth - rep.amount else before.repaidMonth,
                paidBackMonth = if (!isLent && thisMonth(rep.date)) before.paidBackMonth - rep.amount else before.paidBackMonth,
            ),
        )
        launch {
            try {
                Api.deleteTransaction(repaymentId)
            } catch (_: Exception) {
                putUdhaar(before)
                push(Msgs.stub("Not undone —", "Server refused. The repayment stands."))
            }
        }
    }

    /* ─── commitments ──────────────────────────────────────────────────── */

    /**
     * The page, over whatever is open — or back to it, when it is already
     * under the top, on the month it was left at. It reads the month fresh,
     * rolling it forward on the server's first read.
     */
    fun openCommitments() {
        if (Screen.Commitments !in s.stack) patch { copy(commitmentsBack = 0, commitmentsPast = null) }
        pushScreen(Screen.Commitments)
        launch {
            loadCommitments()
            loadLimit()
        }
    }

    /** ‹ › on the page: 0 is this month; earlier months are read-only, and a future one does not exist. */
    fun setCommitmentsBack(n: Int) {
        val back = n.coerceIn(0, 24)
        if (back == s.commitmentsBack) return
        patch { copy(commitmentsBack = back, commitmentsPast = null, commitmentsPastLoad = if (back > 0) Load.Loading else Load.Loaded) }
        if (back == 0) {
            launch { loadCommitments() }
            return
        }
        val month = java.time.LocalDate.parse(s.todayIso).withDayOfMonth(1).minusMonths(back.toLong()).toString()
        launch {
            try {
                val page = Api.fetchCommitments(month)
                if (s.commitmentsBack == back) patch { copy(commitmentsPast = page, commitmentsPastLoad = Load.Loaded) }
            } catch (_: Exception) {
                if (s.commitmentsBack == back) patch { copy(commitmentsPastLoad = Load.Failed) }
            }
        }
    }

    /**
     * *Repay*, on a borrowing: udhaar's own flow — the Borrowed tab of Money's
     * report, where Paid back asks the amount. Over the page it came from, so
     * Back returns there; a Report already under it is gone back to instead.
     */
    fun repayFromCommitments() {
        patch { copy(commitmentSheet = null, reportMode = ReportMode.Paisa, reportTab = "borrowed", reportAsk = reportAsk + 1) }
        pushScreen(Screen.Report)
    }

    fun openCommitmentSheet(draft: CommitmentDraft = CommitmentDraft()) = patch { copy(commitmentSheet = draft, openRow = null) }

    fun closeCommitmentSheet() = patch { copy(commitmentSheet = null) }

    fun editCommitment(c: Commitment) = openCommitmentSheet(
        CommitmentDraft(id = c.id, name = c.name, amount = c.expected, category = c.category, dueDay = c.dueDay, repeats = c.repeats),
    )

    /** *Make this a commitment*, from a payment: the sheet opens filled from it, and the payment links on save. */
    fun commitmentFromPayment(t: Tx) = openCommitmentSheet(
        CommitmentDraft(name = t.name, amount = t.amt, category = t.cat, linkTx = t.id),
    )

    private fun putCommitment(id: String, f: (Commitment) -> Commitment) = patch {
        copy(commitments = commitments?.let { p -> p.copy(items = p.items.map { if (it.id == id) f(it) else it }) })
    }

    /** Owed, worked out as the server works it: nothing when skipped, else what is left of the expected. */
    private fun Commitment.reowed() = copy(owed = if (skipped) 0 else maxOf(0, expected - paid))

    /** Whatever a write moved — the lines, the limit, and the payments that link — comes from the server again. */
    private fun afterCommitmentWrite() {
        launch { runCatching { reloadDeck() } }
        launch { loadLimit() }
    }

    /** Save the sheet: a new line, or the changes to one. Optimistic; the server's page replaces it, a refusal says so. */
    fun saveCommitment(d: CommitmentDraft) {
        val amount = d.amount ?: return
        if (d.name.isBlank() || d.category.isBlank() || amount <= 0) return
        patch { copy(commitmentSheet = null) }
        val editing = d.id?.let { id -> s.commitments?.items?.firstOrNull { it.id == id } }
        if (d.id == null) {
            val id = Ulid.next()
            val line = Commitment(
                id = id, name = d.name.trim(), source = "commitment", origin = "manual", category = d.category.trim(),
                expected = amount, paid = 0, owed = amount, over = 0, settled = false, skipped = false, dueDay = d.dueDay,
                repeats = d.repeats, rolled = false, inferredLinks = 0, carriedFrom = null, pending = true,
            )
            patch { copy(commitments = commitments?.let { p -> p.copy(items = listOf(line) + p.items) }) }
            launch {
                try {
                    Api.createCommitment(d, id)
                    notify("${line.name} added", if (d.linkTx != null) "That payment counts toward it" else null)
                    afterCommitmentWrite()
                } catch (_: Exception) {
                    patch { copy(commitments = commitments?.let { p -> p.copy(items = p.items.filter { it.id != id }) }) }
                    refuse("Not saved — the server refused.")
                }
            }
            return
        }
        val id = d.id
        val before = editing ?: return
        // Only what changed is sent: an amount sent is an amount stated, and it would lose the amber dot.
        val pairs = buildList<Pair<String, Any?>> {
            if (d.name.trim() != before.name) add("name" to d.name.trim())
            if (d.category.trim() != before.category) add("category" to d.category.trim())
            if (amount != before.expected) add("amount_paise" to amount * 100L)
            if (d.dueDay != before.dueDay) add("due_day" to d.dueDay)
            if (d.repeats != before.repeats) add("repeats" to d.repeats)
        }
        if (pairs.isEmpty()) return
        putCommitment(id) {
            it.copy(
                name = d.name.trim(), category = d.category.trim(), expected = amount, dueDay = d.dueDay, repeats = d.repeats,
                rolled = it.rolled && amount == before.expected, pending = true,
            ).reowed()
        }
        launch {
            try {
                Api.patchCommitment(id, body(*pairs.toTypedArray()))
                afterCommitmentWrite()
            } catch (_: Exception) {
                putCommitment(id) { before }
                refuse("Not saved — the server refused.")
            }
        }
    }

    /** *Skip this month* and *Unskip*: the line stays, and owes nothing while skipped. */
    fun skipCommitment(c: Commitment) {
        val skip = !c.skipped
        putCommitment(c.id) { it.copy(skipped = skip, pending = true).reowed() }
        launch {
            try {
                Api.patchCommitment(c.id, body("skipped" to skip))
                notify(if (skip) "${c.name} skipped this month" else "${c.name} is back on")
                afterCommitmentWrite()
            } catch (_: Exception) {
                putCommitment(c.id) { c }
                refuse("Not saved — the server refused.")
            }
        }
    }

    /** *Stop repeating* and *Repeat*: whether it comes back next month. */
    fun repeatCommitment(c: Commitment) {
        val repeats = !c.repeats
        putCommitment(c.id) { it.copy(repeats = repeats, pending = true) }
        launch {
            try {
                Api.patchCommitment(c.id, body("repeats" to repeats))
                notify(if (repeats) "${c.name} comes back every month" else "${c.name} won't come back")
                afterCommitmentWrite()
            } catch (_: Exception) {
                putCommitment(c.id) { c }
                refuse("Not saved — the server refused.")
            }
        }
    }

    /** Delete: its payments become ordinary spending and it will not come back. There is no undo — the page asks first. */
    fun deleteCommitment(c: Commitment) {
        patch { copy(commitments = commitments?.let { p -> p.copy(items = p.items.filter { it.id != c.id }) }) }
        launch {
            try {
                Api.deleteCommitment(c.id)
                notify("${c.name} deleted", "Its payments count as spending now")
                afterCommitmentWrite()
            } catch (_: Exception) {
                launch { loadCommitments() }
                refuse("Not deleted — the server refused.")
            }
        }
    }

    /** The payment's link moved in every list that holds it: committed money leaves spend, and comes back. */
    private fun AppState.relinked(id: String, to: String?, inferred: Boolean): AppState {
        fun f(t: Tx) = if (t.id == id) t.copy(commitmentId = to, commitmentInferred = inferred) else t
        val deck = (tx + fixedTx).map(::f)
        return copy(
            tx = deck.filter { it.commitmentId == null }, fixedTx = deck.filter { it.commitmentId != null },
            fetchedTx = fetchedTx.map(::f), openRow = null,
        )
    }

    /**
     * Move a payment's link — *Counts toward…* — or end it (`to` null, *Not a
     * commitment*), or confirm a guessed one by saying it again. A statement:
     * the amber dot goes either way.
     */
    fun linkPayment(txId: String, to: String?) {
        val row = (s.tx + s.fixedTx + s.fetchedTx).firstOrNull { it.id == txId } ?: return
        patch { relinked(txId, to, false) }
        launch {
            try {
                Api.patchTransaction(txId, body("commitment_id" to to))
                val owed = s.commitments?.items?.firstOrNull { it.id == to }?.name
                if (row.commitmentId != to) notify(if (owed != null) "${row.name} counts toward $owed" else "${row.name} is spending again")
                afterCommitmentWrite()
            } catch (_: Exception) {
                patch { relinked(txId, row.commitmentId, row.commitmentInferred) }
                refuse("Not saved — the server refused.")
            }
        }
    }

    /* ─── voice and media ──────────────────────────────────────────────── */

    /**
     * What the phone's speech recogniser heard. It lands in the composer, not
     * straight in the ledger: speech gets amounts wrong ("one sixty" as 116),
     * and a wrong number is worse than one more tap. The web's mic replayed a
     * canned script that wrote a made-up row — a real payment nobody said.
     */
    fun heard(text: String) = compose(text.trim() + " ")

    /** Still the web's stub: reading a screenshot or a photo is its own feature. */
    fun pickMedia() {
        val m = Msgs.stub(
            "Send a payment screenshot or a photo of the food —",
            "Amount, payee and time read from the screenshot; portion and macros estimated from the photo.",
        ).copy(hl = "I will read it")
        push(m) { this }
    }

    /** A menu row: its page, over the menu. A row marked Soon has no tap, so it never reaches here. */
    fun openMenuRow(name: String) {
        when (name) {
            "Reports" -> openReportOn(s.reportMode, null)
            "Your data" -> openData()
            "Profile" -> openProfile()
        }
    }

    fun openReport(mode: Mode) = openReportOn(
        when (mode) {
            Mode.Work -> ReportMode.Kaam
            Mode.Diet -> ReportMode.Diet
            Mode.Paisa -> ReportMode.Paisa
        },
        null,
    )

    /** Home's Habits widget: the Diet report, on its Habits tab. */
    fun openHabits() = openReportOn(ReportMode.Diet, "habits")

    /** The Report on a mode and a tab — asked again even when it is already open, so the tab lands. */
    private fun openReportOn(mode: ReportMode, tab: String?) {
        patch { copy(reportMode = mode, reportTab = tab, reportAsk = reportAsk + 1) }
        pushScreen(Screen.Report)
    }
    fun setReportMode(m: ReportMode) = patch { copy(reportMode = m) }
    fun setReportRange(r: ReportRange) = patch { copy(reportRange = r) }

    /* ─── edits and the chat turn ──────────────────────────────────────── */

    /** Fix a row in place: optimistic, and the OLD values come back on refusal. */
    private fun applyEdit(target: Editing, label: String, num: Int) {
        val st = s
        if (target.source == "paisa" && st.tx.none { it.id == target.id } && st.fixedTx.none { it.id == target.id }) {
            // A lending or borrowing, edited from its tab.
            val isPending = st.pending.any { it.id == target.id }
            val list = if (isPending) st.pending else st.borrowed
            val open = list.firstOrNull { it.id == target.id } ?: return
            val amt = if (num > 0) num else open.amount
            val next = open.copy(label = label, amount = amt, remaining = maxOf(0, open.remaining + (amt - open.amount)))
            patch {
                if (isPending) copy(pending = pending.map { if (it.id == target.id) next else it })
                else copy(borrowed = borrowed.map { if (it.id == target.id) next else it })
            }
            push(Msgs.stub("Updated —", "$label · ${Fmt.rupees(amt)}"))
            launch {
                try {
                    Api.patchTransaction(target.id, body("description" to label, "amount_paise" to amt * 100L))
                } catch (_: Exception) {
                    patch {
                        if (isPending) copy(pending = pending.map { if (it.id == target.id) open else it })
                        else copy(borrowed = borrowed.map { if (it.id == target.id) open else it })
                    }
                }
            }
        } else if (target.source == "paisa") {
            val inTx = st.tx.any { it.id == target.id }
            val before = (if (inTx) st.tx else st.fixedTx).firstOrNull { it.id == target.id } ?: return
            val amt = if (num > 0) num else before.amt
            fun mapList(f: (Tx) -> Tx) = patch {
                if (inTx) copy(tx = tx.map { if (it.id == target.id) f(it) else it })
                else copy(fixedTx = fixedTx.map { if (it.id == target.id) f(it) else it })
            }
            mapList { it.copy(name = label, amt = amt, pending = true) }
            push(Msgs.stub("Updated —", "$label · ${Fmt.rupees(amt)}"))
            launch {
                try {
                    Api.patchTransaction(target.id, body("description" to label, "amount_paise" to amt * 100L))
                    mapList { it.copy(pending = false) }
                } catch (_: Exception) {
                    mapList { before.copy(failed = true) }
                }
            }
        } else {
            val before = st.meals.firstOrNull { it.id == target.id } ?: return
            val k = if (num > 40) num else before.k
            patch { copy(meals = meals.map { if (it.id == target.id) it.copy(name = label, k = k, pending = true) else it }) }
            push(Msgs.stub("Updated —", "$label · $k kcal"))
            launch {
                try {
                    Api.patchMeal(target.id, body("dish" to label, "kcal" to k))
                    settleMeal(target.id, false)
                } catch (_: Exception) {
                    patch { copy(meals = meals.map { if (it.id == target.id) before.copy(failed = true) else it }) }
                }
            }
        }
    }

    /**
     * Ask the agent. One turn, no streaming — the reply lands whole. With a
     * context, the agent is sent its prefix ahead of your words; your bubble
     * keeps only what you typed, the label riding above it.
     */
    fun ask(raw: String, context: ComposeContext? = null) {
        val said = Msgs.user(raw, context)
        push(said) { copy(typed = "", phase = Phase.Thinking) }
        launch {
            try {
                val out = Api.sendChat(context?.let { "${it.prefix} $raw" } ?: raw, s.todayIso)
                val at = "chat-${System.currentTimeMillis()}"
                val written = out.cards.mapIndexedNotNull { i, c -> Cards.toMsg(c, i, at) }
                val cards = Cards.group(written)
                learnDeleted(cards)
                // A weight said is a weigh-in now: its card finds its row, and the one before it, in the list.
                if (written.any { it is ChatMsg.Confirm && it.fields.any { f -> f.key == "weight_kg" } }) launch { loadWeighIns() }
                if (cards.isNotEmpty()) push(*cards.toTypedArray())
                else push(Msgs.stub("", out.reply.ifEmpty { "Nothing came back." }))
                // A turn may have written something; the deck and the limit follow.
                launch { runCatching { reloadDeck() } }
                launch { loadLimit() }
                launch { runCatching { loadPantry() } }
                launch { runCatching { loadExercises() } }
            } catch (e: Exception) {
                val code = e.status()
                if (code != 401) {
                    // Say which half failed — no answer, or an answer that was an error —
                    // because "didn't reach" over a server error sends you to check the
                    // Wi-Fi. English, and a way back: the bubble's Retry resends it.
                    val what = when {
                        code != null -> "The server couldn't answer that ($code)."
                        e is java.io.IOException -> "Didn't reach the server."
                        else -> "The reply didn't come through properly."
                    }
                    // Marked on the message itself — it is yours that did not go.
                    patch { copy(chat = chat.map { if (it.id == said.id) said.copy(failed = what) else it }) }
                }
            } finally {
                patch { copy(phase = Phase.Idle) }
            }
        }
    }

    /** Retry on a message that did not go: it is sent again, as itself — its context too. */
    fun retrySend(id: String) {
        val m = s.chat.firstOrNull { it.id == id } as? ChatMsg.User ?: return
        patch { copy(chat = chat.filter { it.id != id }) }
        ask(m.text, m.context)
    }

    /**
     * A Change on a card: what it is about is attached above the input, and
     * the cursor goes there. Nothing is typed for you — what you had already
     * typed stays. An edit in progress goes, its text with it: that text was
     * the row's, not yours.
     */
    fun setContext(c: ComposeContext) = patch {
        copy(
            context = c, editing = null, typed = if (editing != null) "" else typed,
            composing = true, openRow = null, composeFocus = composeFocus + 1,
        )
    }

    /** ✕ on the pill, or Back: the composer is plain again. */
    fun clearContext() = patch { copy(context = null) }

    /** What a send did: nothing (an empty composer), a correction to a row, or a question to the agent. */
    enum class Sent { Nothing, Edit, Ask }

    /**
     * Send whatever is in the composer: a correction, or the agent's. Says
     * which, so a page leaves for Chat only when there is an answer coming —
     * a correction stays where the row is.
     */
    fun send(): Sent {
        val raw = s.typed.trim()
        if (raw.isEmpty()) return Sent.Nothing
        // A context is spent by the send that carries it, whichever way it goes.
        val context = s.context
        if (context != null) patch { copy(context = null) }
        val editing = s.editing
        if (editing != null) {
            // A correction, not a log: same row, new values, same id.
            val num = Regex("(\\d+)").find(raw)?.groupValues?.get(1)?.toIntOrNull() ?: 0
            val bare = raw.replace(Regex("\\d+"), "").trim().ifEmpty { if (editing.source == "paisa") "Spend" else "Meal" }
            patch { copy(typed = "", editing = null) }
            push(Msgs.user("\"$raw\""))
            applyEdit(editing, bare.replaceFirstChar { it.uppercase() }, num)
            return Sent.Edit
        }
        // Everything else is the agent's.
        ask(raw, context)
        return Sent.Ask
    }

    /* ─── row-level edits ──────────────────────────────────────────────── */

    fun toggleRow(id: String) = patch { copy(openRow = if (openRow == id) null else id) }

    /**
     * Delete a ledger row, from any card. The id joins `deletedRows`, so every
     * card showing the row strikes it; the row leaves the deck's lists, and a
     * struck copy stays with the by-id rows, so a table can still draw what
     * went instead of losing the line.
     */
    fun deleteRow(source: String, id: String) {
        val st = s
        val kept: Any? = if (source == "paisa") st.tx.firstOrNull { it.id == id } ?: st.fixedTx.firstOrNull { it.id == id }
        else st.meals.firstOrNull { it.id == id }
        // A lending lives in `pending`, not `tx`; deleting one removes it there.
        val keptPending = if (source == "paisa") st.pending.firstOrNull { it.id == id } ?: st.borrowed.firstOrNull { it.id == id } else null
        patch {
            val marked = if (id in deletedRows) deletedRows else deletedRows + id
            if (source == "paisa") copy(
                tx = tx.filter { it.id != id }, fixedTx = fixedTx.filter { it.id != id },
                pending = pending.filter { it.id != id }, borrowed = borrowed.filter { it.id != id },
                fetchedTx = if (kept is Tx) fetchedTx.filter { it.id != id } + kept.copy(deleted = true) else fetchedTx,
                deletedRows = marked, openRow = null,
            ) else copy(
                meals = meals.filter { it.id != id },
                fetchedMeals = if (kept is Meal) fetchedMeals.filter { it.id != id } + kept.copy(deleted = true) else fetchedMeals,
                deletedRows = marked, openRow = null,
            )
        }
        // Refused: not deleted after all — the struck copy goes, the strike lifts.
        fun unmark() = patch {
            copy(
                deletedRows = deletedRows - id,
                fetchedTx = if (kept is Tx) fetchedTx.filter { it.id != id } else fetchedTx,
                fetchedMeals = if (kept is Meal) fetchedMeals.filter { it.id != id } else fetchedMeals,
            )
        }
        if (keptPending != null) {
            val same = thisMonth(keptPending.date)
            patch {
                copy(
                    lentMonth = if (keptPending.leg == "lent" && same) lentMonth - keptPending.amount else lentMonth,
                    borrowedMonth = if (keptPending.leg == "borrowed" && same) borrowedMonth - keptPending.amount else borrowedMonth,
                )
            }
        }
        launch {
            try {
                if (source == "paisa") Api.deleteTransaction(id) else Api.deleteMeal(id)
            } catch (_: Exception) {
                unmark()
                if (keptPending != null) {
                    // The server refused — a lending with repayments cannot be deleted.
                    val same = thisMonth(keptPending.date)
                    patch {
                        val lent = keptPending.leg == "lent"
                        copy(
                            lentMonth = if (lent && same) lentMonth + keptPending.amount else lentMonth,
                            borrowedMonth = if (!lent && same) borrowedMonth + keptPending.amount else borrowedMonth,
                            pending = if (lent) (pending + keptPending).sortedBy { it.date } else pending,
                            borrowed = if (!lent) (borrowed + keptPending).sortedBy { it.date } else borrowed,
                        )
                    }
                    push(Msgs.stub("Not deleted —", "${keptPending.label} has repayments. Undo them first."))
                    return@launch
                }
                when (kept) {
                    is Tx -> patch { if (kept.fixed) copy(fixedTx = fixedTx + kept.copy(failed = true)) else copy(tx = tx + kept.copy(failed = true)) }
                    is Meal -> patch { copy(meals = meals + kept.copy(failed = true)) }
                    // A row from outside the deck has nothing to come back to: say so.
                    else -> refuse("Not deleted — the server refused.")
                }
            }
        }
    }

    /** Restores in flight — a second tap on Undo waits for the first. */
    private val restoring = HashSet<String>()

    /**
     * Undo on a removed receipt: the row comes back through its own route.
     * Not optimistic — the strike lifts only once the server has the row live
     * again; a refusal is a toast, and the card stays as it was.
     */
    fun restoreRow(msg: ChatMsg.Confirm) {
        val id = msg.rowId ?: return
        if (msg.source != "paisa" && msg.source != "diet") return
        if (!restoring.add(id)) return
        launch {
            try {
                if (msg.source == "paisa") {
                    val row = Api.restoreTransaction(id)
                    patch { withRestoredTx(row) }
                } else {
                    val row = Api.restoreMeal(id)
                    patch { withRestoredMeal(row) }
                    launch { runCatching { loadPantry() } }
                }
                // The deck's numbers are the server's: they follow the row back.
                launch { runCatching { reloadDeck() } }
            } catch (e: Exception) {
                val code = e.status()
                if (code != 401) refuse(if (code != null) "Couldn't undo — the server refused." else "Couldn't undo — didn't reach the server.")
            } finally {
                restoring -= id
            }
        }
    }

    /** The restored row, back where the deck keeps its kind — this month's expenses — or with the by-id rows. */
    private fun AppState.withRestoredTx(row: Tx): AppState {
        val inDeck = row.kind == "expense" && (row.date ?: todayIso).take(7) == todayIso.take(7)
        return copy(
            tx = tx.filter { it.id != row.id } + listOfNotNull(row.takeIf { inDeck && !it.fixed }),
            fixedTx = fixedTx.filter { it.id != row.id } + listOfNotNull(row.takeIf { inDeck && it.fixed }),
            fetchedTx = fetchedTx.filter { it.id != row.id } + listOfNotNull(row.takeIf { !inDeck }),
            deletedRows = deletedRows - row.id,
        )
    }

    /** The deck holds every live meal, so a restored one goes straight back among them. */
    private fun AppState.withRestoredMeal(row: Meal) = copy(
        meals = meals.filter { it.id != row.id } + row,
        fetchedMeals = fetchedMeals.filter { it.id != row.id },
        deletedRows = deletedRows - row.id,
    )

    /**
     * The agent's delete cards, as they arrive: their rows are struck in every
     * card at once, and a struck copy is kept for the tables — the deck that
     * follows the turn no longer holds them.
     */
    private fun learnDeleted(cards: List<ChatMsg>) {
        val gone = cards.filterIsInstance<ChatMsg.Confirm>()
            .filter { it.state == "deleted" && (it.source == "paisa" || it.source == "diet") }
            .mapNotNull { it.rowId }
        if (gone.isEmpty()) return
        patch {
            val tx0 = (tx + fixedTx).filter { it.id in gone }
            val meals0 = meals.filter { it.id in gone }
            copy(
                deletedRows = (deletedRows + gone).distinct(),
                fetchedTx = fetchedTx.filter { f -> tx0.none { it.id == f.id } } + tx0.map { it.copy(deleted = true) },
                fetchedMeals = fetchedMeals.filter { f -> meals0.none { it.id == f.id } } + meals0.map { it.copy(deleted = true) },
            )
        }
    }

    fun deleteHabitLog(id: String) {
        val kept = s.habitLogs.firstOrNull { it.id == id }
        patch { copy(habitLogs = habitLogs.filter { it.id != id }) }
        launch {
            try {
                Api.deleteHabitLog(id)
            } catch (_: Exception) {
                if (kept != null) patch { copy(habitLogs = habitLogs + kept) }
            }
        }
    }

    /** A task's Undo, or a ⋮ Delete: gone from every list, struck on the card that added it. */
    fun deleteTask(id: String) {
        val kept = s.todos.firstOrNull { it.id == id }
        patch { copy(todos = todos.filter { it.id != id }, deletedRows = if (id in deletedRows) deletedRows else deletedRows + id) }
        launch {
            try {
                Api.deleteTask(id)
            } catch (_: Exception) {
                patch { copy(todos = if (kept != null) todos + kept else todos, deletedRows = deletedRows - id) }
                refuse("Not removed — the server refused.")
            }
        }
    }

    /** One ⋮ → Delete for every kind of row the report shows. */
    fun deleteAny(kind: String, id: String) = when (kind) {
        "habit" -> deleteHabitLog(id)
        "task" -> deleteTask(id)
        "repayment" -> undoRepayment(id)
        else -> deleteRow(kind, id)
    }

    /** ⋮ → Edit: the row's text goes into the composer AND the composer remembers the row. An edit replaces a context. */
    fun editRow(source: String, id: String, text: String) =
        patch { copy(typed = text, openRow = null, composing = true, context = null, editing = Editing(source, id, text), composeFocus = composeFocus + 1) }

    fun cancelEdit() = patch { copy(typed = "", editing = null) }

    fun toggleTodo(id: String) {
        val before = s.todos.firstOrNull { it.id == id } ?: return
        val done = !before.done
        patch {
            copy(todos = todos.map {
                // Stamping the day keeps a finished task on the card for today.
                // A tracker's task reminds the moment it is ticked.
                if (it.id == id) it.copy(done = done, doneOn = if (done) todayIso else null, awaitingMove = done && it.tracked) else it
            })
        }
        launch {
            try {
                Api.patchTask(id, done)
            } catch (_: Exception) {
                patch { copy(todos = todos.map { if (it.id == id) before else it }) }
            }
        }
    }

    /* ─── chat history ─────────────────────────────────────────────────── */

    private fun applyPage(page: ChatPage) = patch {
        copy(
            chat = Cards.toMessages(page.turns),
            chatOlder = page.turns.firstOrNull()?.seq,
            chatHasMore = page.hasMore,
            chatCleared = page.clearedThrough,
        )
    }

    suspend fun loadChat() = applyPage(Api.fetchChat())

    /** The page before what is on screen, prepended. */
    fun loadOlderChat(includeCleared: Boolean = false) {
        val s0 = s
        if (s0.chatLoadingOlder || s0.chatOlder == null) return
        if (!s0.chatHasMore && !includeCleared) return
        patch { copy(chatLoadingOlder = true) }
        launch {
            try {
                val page = Api.fetchChat(before = s0.chatOlder, includeCleared = includeCleared)
                patch {
                    copy(
                        chat = Cards.toMessages(page.turns) + chat,
                        chatOlder = page.turns.firstOrNull()?.seq ?: chatOlder,
                        chatHasMore = page.hasMore,
                        // Revealed once, revealed for the session.
                        chatCleared = if (includeCleared) 0 else chatCleared,
                        chatLoadingOlder = false,
                    )
                }
            } catch (_: Exception) {
                patch { copy(chatLoadingOlder = false) }
            }
        }
    }

    private var clearing = false

    /** Clear the screen without forgetting. A flag, set before anything else runs. */
    fun clearConversation() {
        if (clearing) return
        clearing = true
        patch { copy(chatClearing = true) }
        launch {
            try {
                applyPage(Api.clearChat())
                notify("Conversation cleared", "The agent kept the gist")
            } catch (_: Exception) {
                refuse("Couldn't clear — the server refused.")
            } finally {
                clearing = false
                patch { copy(chatClearing = false) }
            }
        }
    }

    private val requestedRows = HashSet<String>()

    /** Rows a card named that the deck's window does not hold — fetched once per id. */
    fun ensureRows(source: String, ids: List<String>) {
        val fresh = ids.filter { "$source:$it" !in requestedRows }
        if (fresh.isEmpty()) return
        fresh.forEach { requestedRows += "$source:$it" }
        launch {
            try {
                if (source == "paisa") {
                    val rows = Api.fetchTxByIds(fresh)
                    patch { copy(fetchedTx = fetchedTx.filter { h -> rows.none { it.id == h.id } } + rows) }
                } else {
                    val rows = Api.fetchMealsByIds(fresh)
                    patch { copy(fetchedMeals = fetchedMeals.filter { h -> rows.none { it.id == h.id } } + rows) }
                }
            } catch (_: Exception) {
                fresh.forEach { requestedRows -= "$source:$it" }
            }
        }
    }

    /** `Confirm` in a card's tray: the guess was right. Confidence goes to 1. */
    fun confirmRow(msg: ChatMsg.Confirm) {
        val id = msg.rowId ?: return
        if (msg.source != "paisa" && msg.source != "diet") return
        // A `proposed` card carries a guess the row does not yet hold.
        val fields = mutableMapOf<String, Any?>("confidence" to 1)
        if (msg.state == "proposed") {
            msg.fields.filter { it.guessed && (it.key == "category" || it.key == "description") }.forEach { fields[it.key] = it.value }
        }
        fun stampTx(t: Tx) = if (t.id != id) t else t.copy(
            confidence = 1.0,
            cat = (fields["category"] as String?) ?: t.cat,
            name = (fields["description"] as String?) ?: t.name,
        )
        patch {
            if (msg.source == "paisa") copy(tx = tx.map(::stampTx), fixedTx = fixedTx.map(::stampTx), fetchedTx = fetchedTx.map(::stampTx), openRow = null)
            else copy(
                meals = meals.map { if (it.id == id) it.copy(confidence = 1.0) else it },
                fetchedMeals = fetchedMeals.map { if (it.id == id) it.copy(confidence = 1.0) else it },
                openRow = null,
            )
        }
        launch {
            try {
                if (msg.source == "paisa") Api.patchTransaction(id, body(*fields.toList().toTypedArray()))
                else Api.patchMeal(id, body("confidence" to 1))
            } catch (_: Exception) {
                refuse("Not confirmed — the server refused.")
            }
        }
    }

    /** Delete from a confirm card: the route that owns the row, by source. */
    fun deleteConfirmRow(msg: ChatMsg.Confirm) {
        val id = msg.rowId ?: return
        patch { copy(deletedRows = if (id in deletedRows) deletedRows else deletedRows + id, openRow = null) }
        when (msg.source) {
            "paisa", "diet" -> deleteRow(msg.source, id)
            "pantry" -> launch {
                try {
                    Api.deletePantryMove(id)
                    loadPantry()
                } catch (_: Exception) {
                    // Not deleted: the card must not go on saying it was.
                    patch { copy(deletedRows = deletedRows - id) }
                    refuse("Not deleted — the server refused.")
                }
            }
            "memory" -> removeMemory(id)
            "places" -> removePlace(id)
            // A weight's card holds its weigh-in: the reading goes, and the day's copy with it.
            "body" -> if (msg.fields.any { it.key == "weight_kg" }) deleteWeighIn(id)
        }
    }

    /** Tap on a dish or exercise card: log it, now — no model between tap and row. */
    fun logSuggested(item: SuggestItem) {
        val s0 = s
        if (item.ref in s0.pendingLogs || s0.suggestLogged.containsKey(item.ref)) return
        patch { copy(pendingLogs = pendingLogs + item.ref, openRow = null) }
        launch {
            try {
                val day = s.todayIso
                val out = if (item.type == "exercise") {
                    Api.actChat("log_exercise", body("exercise_id" to item.ref, "local_day" to day))
                } else {
                    Api.actChat(
                        "log_meal",
                        body("dish_id" to item.ref, "text_said" to item.name, "meal_type" to (item.mealType ?: Day.mealTypeNow()), "local_day" to day),
                    )
                }
                val confirm = out.cards.mapIndexedNotNull { i, c -> Cards.toMsg(c, i, "act") }.filterIsInstance<ChatMsg.Confirm>().firstOrNull()
                val what = confirm?.fields?.firstOrNull { it.key == "dish" || it.key == "name" }?.value ?: item.name
                patch {
                    copy(
                        suggestLogged = suggestLogged + (item.ref to (confirm?.lede ?: "logged")),
                        pendingLogs = pendingLogs - item.ref,
                    )
                }
                notify("$what logged", confirm?.lede)
                launch { runCatching { reloadDeck() } }
                launch { runCatching { loadExercises() } }
            } catch (_: Exception) {
                patch { copy(pendingLogs = pendingLogs - item.ref) }
                refuse("Couldn't log it — the server refused.")
            }
        }
    }

    /** ★ in a dish card's tray — the library, through its route. */
    fun saveSuggested(msgId: String, item: SuggestItem) {
        if (item.type != "dish") return
        fun flip(saved: Boolean) = patch {
            copy(
                chat = chat.map { m ->
                    if (m is ChatMsg.Suggest && m.id == msgId) m.copy(items = m.items.map { if (it.ref == item.ref) it.copy(saved = saved) else it }) else m
                },
                openRow = null,
            )
        }
        flip(!item.saved)
        launch {
            try {
                if (item.saved) Api.unsaveDish(item.ref) else Api.saveDish(item.ref)
                loadDishes()
            } catch (_: Exception) {
                flip(item.saved)
                refuse("Not saved — the server refused.")
            }
        }
    }

    /** "Not this": the item goes, and the card with it when it was the last. */
    fun dismissSuggested(msgId: String, ref: String) = patch {
        copy(
            chat = chat.mapNotNull { m ->
                if (m !is ChatMsg.Suggest || m.id != msgId) m
                else m.items.filter { it.ref != ref }.takeIf { it.isNotEmpty() }?.let { m.copy(items = it) }
            },
            openRow = null,
        )
    }

    fun signOut(done: () -> Unit) = launch {
        runCatching { Api.signOut() }
        reset()
        done()
    }
}
