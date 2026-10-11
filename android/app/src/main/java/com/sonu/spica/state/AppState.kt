package com.sonu.spica.state

import com.sonu.spica.data.ActivityDay
import com.sonu.spica.data.ChatMsg
import com.sonu.spica.data.HealthAccess
import com.sonu.spica.data.ComposeContext
import com.sonu.spica.data.DishRow
import com.sonu.spica.data.ExerciseRow
import com.sonu.spica.data.HabitLogRow
import com.sonu.spica.data.HabitRow
import com.sonu.spica.data.CommitmentDraft
import com.sonu.spica.data.CommitmentsPage
import com.sonu.spica.data.LimitInfo
import com.sonu.spica.data.Meal
import com.sonu.spica.data.MemoryRow
import com.sonu.spica.data.NudgeRow
import com.sonu.spica.data.Onboarding
import com.sonu.spica.data.PantryMoveRow
import com.sonu.spica.data.PantryRow
import com.sonu.spica.data.PendingItem
import com.sonu.spica.data.PersonRow
import com.sonu.spica.data.PlaceRow
import com.sonu.spica.data.Profile
import com.sonu.spica.data.Project
import com.sonu.spica.data.RepaymentItem
import com.sonu.spica.data.ScheduleRow
import com.sonu.spica.data.Todo
import com.sonu.spica.data.TodayPlan
import com.sonu.spica.data.Tx
import com.sonu.spica.data.WeighInRow
import com.sonu.spica.data.Workout
import com.sonu.spica.lib.Day
import java.time.Instant

enum class Phase { Idle, Thinking, Saving }

enum class ReportMode(val id: String, val label: String) { Paisa("paisa", "Money"), Diet("diet", "Diet"), Kaam("kaam", "To-do") }

enum class ReportRange(val label: String) { Aaj("Today"), Din7("7 days"), Din14("14 days"), Mahina("Month") }

/** Your data's sections. The kinds name screens, not data. */
/** `icon` is a Phosphor name; the UI draws it. */
enum class Section(val label: String, val icon: String) {
    Recipe("Dishes", "cooking-pot"),
    Pantry("Pantry", "package"),
    People("People", "users"),
    Place("Places", "map-pin"),
    Workout("Workouts", "barbell"),
}

/**
 * Home's widgets you can add or take off, in the order they stand. Today is
 * not here: it is always first. Activity and Habits start off — added when
 * wanted, so Home opens on what everyone uses.
 */
enum class HomeWidget(val id: String, val label: String, val blurb: String) {
    Money("money", "Money", "Left today, the month in and out"),
    Diet("diet", "Diet", "Protein to go, calories, carbs and fat"),
    Meals("meals", "Meals", "The rest of today, planned to your targets"),
    Activity("activity", "Activity", "Steps, active calories, runs and rides"),
    Workout("workout", "Workout", "One workout for today, and why"),
    Habits("habits", "Habits", "Your habits, this week");

    companion object {
        val ids = entries.map { it.id }
        val DEFAULT = listOf(Money.id, Diet.id)
    }
}

/** The pages a nudge opens onto. `spec/in-progress/nudges.md` § The pages. */
enum class Landing { Day, Meals, Workout }

/** A nudge's page, open over Nudges. `nudgeId` is null when the page was reached from another page, not from a nudge. */
data class NudgePage(val landing: Landing, val nudgeId: String?)

/** Profile's groups. Each is a level of its own: a stack entry over the grid, or over whatever opened it. */
enum class ProfileGroup { Finance, Health, Projects, Runs, Weight, About, Memory }

/**
 * A screen over Home. Home — the Home | Chat pager — is the root and never on
 * the stack; everything opened over it is an entry, and so is each level
 * inside a page (a Your data section, a Profile group, a nudge's page).
 * Tabs, ranges, filters and month paging are not screens. THEME.md § Back.
 */
sealed interface Screen {
    data object Menu : Screen
    data object Report : Screen
    /** The overview when `section` is null. */
    data class Data(val section: Section? = null) : Screen
    /** The grid when `group` is null. */
    data class Profile(val group: ProfileGroup? = null) : Screen
    data object Commitments : Screen
    data object Nudges : Screen
    data class Nudge(val page: NudgePage) : Screen
}

/** Whether a list is the server's answer yet. Unknown is not zero: only Loaded may say there are none. */
enum class Load { Loading, Failed, Loaded }

/** `failed` draws a ✕ instead of the tick: a refusal must not look like a receipt. */
data class Toast(val id: Long, val text: String, val sub: String? = null, val failed: Boolean = false)

/** The row the composer is correcting. While set, send() PATCHes this row. */
data class Editing(val source: String, val id: String, val label: String)

/**
 * Everything the screen draws from — the prototype's `State`, field for field,
 * plus what the web keeps as `data/live` module values (the anchor day, the
 * projects, the month's income), since Kotlin has no live bindings.
 */
data class AppState(
    val booted: Boolean = false,
    val bootError: String? = null,

    val phase: Phase = Phase.Idle,
    /** Composer has focus — talking happens in Chat, so Home hands over to it. */
    val composing: Boolean = false,
    val typed: String = "",
    /** What a card's Change attached to the composer — drawn above the input, sent ahead of your words. */
    val context: ComposeContext? = null,
    /** Bumped when something fills the composer for the user — it takes focus. */
    val composeFocus: Int = 0,
    /**
     * The screens open over Home, the top one last. Opening one pushes it;
     * Back and ← pop exactly one, to whatever opened it. Only a send to the
     * agent, or a nudge's Ask, clears it.
     */
    val stack: List<Screen> = emptyList(),
    /** The ledger row whose edit/delete tray is expanded, if any. */
    val openRow: String? = null,
    val fetchedTx: List<Tx> = emptyList(),
    val fetchedMeals: List<Meal> = emptyList(),
    /**
     * Ids deleted this session — by a card's Undo, a ⋮ Delete, or the agent's
     * delete card — struck through wherever shown, until an Undo restores one.
     */
    val deletedRows: List<String> = emptyList(),
    /** Suggestion ref → the meal it was logged as, by a tap this session. */
    val suggestLogged: Map<String, String> = emptyMap(),
    val pendingLogs: List<String> = emptyList(),
    val toast: Toast? = null,
    val chatOlder: Int? = null,
    val chatHasMore: Boolean = false,
    val chatLoadingOlder: Boolean = false,
    val chatCleared: Int = 0,
    val chatClearing: Boolean = false,
    val editing: Editing? = null,
    val reportMode: ReportMode = ReportMode.Paisa,
    /** The tab the report opens on — Home's Habits widget opens Diet's Habits tab. Null is All. */
    val reportTab: String? = null,
    /** Bumped with every opener's `reportTab`, so the tab it asks for lands even when the Report is already open under it. */
    val reportAsk: Int = 0,
    // The month so far, not a rolling week: the answer resets with the month.
    val reportRange: ReportRange = ReportRange.Mahina,
    val usedSuggs: List<String> = emptyList(),
    val todos: List<Todo> = emptyList(),
    val workouts: List<Workout> = emptyList(),
    val habitLogs: List<HabitLogRow> = emptyList(),
    val chat: List<ChatMsg> = emptyList(),
    val tx: List<Tx> = emptyList(),
    /** This month's fixed expenses, apart so the spend arithmetic never sees them. */
    val fixedTx: List<Tx> = emptyList(),
    val meals: List<Meal> = emptyList(),
    val profile: Profile = Profile(),
    val onboarding: Onboarding = Onboarding(),
    /** Screens 2–4, shown after sign-in while `onboarding.doneAt` is null. */
    val firstRun: FirstRun = FirstRun(),
    val memories: List<MemoryRow> = emptyList(),
    val habits: List<HabitRow> = emptyList(),
    val schedules: List<ScheduleRow> = emptyList(),
    /** Newest first. */
    val weighIns: List<WeighInRow> = emptyList(),
    /** Whether the weigh-ins have been read: until then a weight card says nothing about the one before. */
    val weighInsLoad: Load = Load.Loading,
    val pantry: List<PantryRow> = emptyList(),
    val pantryMoves: List<PantryMoveRow> = emptyList(),
    val dishes: List<DishRow> = emptyList(),
    val people: List<PersonRow> = emptyList(),
    val exercises: List<ExerciseRow> = emptyList(),
    val places: List<PlaceRow> = emptyList(),
    /** The daily limit — computed on the server, never here. Null until it lands. */
    val limitInfo: LimitInfo? = null,
    /** What is owed this month, line by line — the server's, refetched after anything that moves it. Null until it lands. */
    val commitments: CommitmentsPage? = null,
    /** How many months back the page is showing; 0 is this month, the only one that can be changed. */
    val commitmentsBack: Int = 0,
    val commitmentsPast: CommitmentsPage? = null,
    val commitmentsPastLoad: Load = Load.Loading,
    /** The add/edit sheet, open when set — from the page, a payment's tray, anywhere. */
    val commitmentSheet: CommitmentDraft? = null,
    val pending: List<PendingItem> = emptyList(),
    val borrowed: List<PendingItem> = emptyList(),
    val repayments: List<RepaymentItem> = emptyList(),
    val lentMonth: Int = 0,
    val repaidMonth: Int = 0,
    val borrowedMonth: Int = 0,
    val paidBackMonth: Int = 0,

    /* What the web holds as `data/live` module values. */
    val today: Int = Day.dayOfMonth(Day.today()),
    val todayIso: String = Day.today(),
    val monthDays: Int = Day.monthDays(Day.today()),
    val projects: List<Project> = emptyList(),
    /** Everything that arrived this month — salary, repayments in, borrowings. */
    val salary: Int = 0,
    val salaryToday: Boolean = false,
    val incomeSources: List<Pair<String, Int>> = emptyList(),
    val bankBalance: Int = 0,
    val sleep: List<Triple<Int, String, Double>> = emptyList(),

    /* Read from the phone's Health Connect for Home's Activity widget — never sent anywhere. */
    /** Null until asked. */
    val healthAccess: HealthAccess? = null,
    val activity: ActivityDay? = null,
    /** The widgets on Home after Today, by `HomeWidget.id` — chosen on this phone. */
    val homeWidgets: List<String> = HomeWidget.DEFAULT,

    /** The server's plan for the rest of today — read, never stored. Null until asked. */
    val plan: TodayPlan? = null,
    val planLoading: Boolean = false,
    /** Plan items acted on this session — `meal:<slot>`, `save:<slot>`, `workout` — until the plan is read again. */
    val planDone: List<String> = emptyList(),

    /* Nudges — what Spica prepared without being asked. `spec/in-progress/nudges.md`. */
    /** The last seven days, newest first. Empty until read — and while the server has none to give. */
    val nudges: List<NudgeRow> = emptyList(),
    /** Whether `nudges` is the server's answer: until it is, the page does not say there are none. */
    val nudgesLoad: Load = Load.Loading,
    /** When the bell was last opened, kept on this phone: a nudge written after it puts the dot on the bell. */
    val bellOpenedAt: Instant? = null,
    /** Set to slide the pager to Chat once the stack is cleared; Home sets it back to 0 as it slides, so it never replays. */
    val toChat: Int = 0,
) {
    val savingsTarget: Int get() = profile.savingsTarget ?: 0

    /** The screen on top, or null on Home. */
    val top: Screen? get() = stack.lastOrNull()

    /** Where the composer is drawn: Home, or the top page when that page carries one (the Report, Profile). */
    val composerShown: Boolean get() = top.let { it == null || it == Screen.Report || it is Screen.Profile }

    /**
     * The bell's dot: a nudge written since the bell was last opened, and not
     * put away. One whose stamp did not parse counts while it is unopened.
     * Nothing read, nothing to mark.
     */
    val bellDot: Boolean get() = nudgesLoad == Load.Loaded && nudges.any { n ->
        val at = n.created
        !n.dismissed && if (at == null) !n.seen else bellOpenedAt == null || at.isAfter(bellOpenedAt)
    }
}
