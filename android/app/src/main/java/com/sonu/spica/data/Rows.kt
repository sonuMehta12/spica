package com.sonu.spica.data

/**
 * What the app gets back from the library endpoints — `PantryRow`, `DishRow`,
 * `PersonRow` and the rest of `api.ts`. Money in rupees or paise exactly where
 * the prototype has it, so arithmetic ported from there needs no rethinking.
 */

data class Profile(
    val id: String = "",
    val displayName: String = "",
    val email: String? = null,
    val avatarUrl: String? = null,
    val onboardingDoneAt: String? = null,
    /** A date of birth — shown as an age. One worked out from an age is 1 January of the year. */
    val dob: String? = null,
    /** `female` · `male` · `other`. Null is not said, never a default. */
    val gender: String? = null,
    val heightCm: Double? = null,
    val city: String? = null,
    /** `veg` · `nonveg` · `eggetarian` · `any`. Null is not said — never *Anything*. */
    val diet: String? = null,
    val timezone: String = "Asia/Kolkata",
    /** Rupees. Null = no goal set. */
    val savingsTarget: Int? = null,
    val kcalTarget: Int? = null,
    val proteinTarget: Double? = null,
    val carbsTarget: Double? = null,
    val fatTarget: Double? = null,
    val fibreTarget: Double? = null,
    val weightTargetKg: Double? = null,
    val sleepTargetMin: Int? = null,
    val stepTarget: Int? = null,
)

data class MemoryRow(
    val id: String,
    val slug: String,
    val kind: String,
    val text: String,
    val source: String,
    /** Null means nobody has said "still true" — shown as inferred. */
    val confirmedAt: String?,
    val pending: Boolean = false,
    val failed: Boolean = false,
)

/** `estimated`: said as a guess ("around 72") — the amber dot, until an exact reading replaces it. */
data class WeighInRow(
    val id: String,
    val day: String,
    val kg: Double,
    val estimated: Boolean = false,
    val pending: Boolean = false,
    val failed: Boolean = false,
)

data class HabitLogRow(
    val id: String,
    val day: Int,
    val date: String,
    val habit: String,
    val amount: Double? = null,
    val note: String? = null,
    /** When it happened, if the server said. */
    val at: java.time.Instant? = null,
)

data class PendingItem(
    val id: String,
    /** "lent" — yours out to them; "borrowed" — theirs in to you. */
    val leg: String,
    val label: String,
    /** What was lent. */
    val amount: Int,
    /** What is still out, after repayments. Always > 0 here. */
    val remaining: Int,
    val date: String,
    val day: Int,
    val pending: Boolean = false,
    val failed: Boolean = false,
)

data class RepaymentItem(
    val id: String,
    val lendingId: String,
    val label: String,
    val amount: Int,
    val date: String,
    val day: Int,
    val leg: String,
    val lentDate: String,
    val lentAmount: Int,
    val pending: Boolean = false,
    val failed: Boolean = false,
)

/** Whether the first run is finished or skipped. Null: the apps show it after sign-in. */
data class Onboarding(val doneAt: String? = null)

/** The loaded deck — what `data/live.ts` holds as module values on the web. */
data class DeckData(
    val today: Int,
    val todayIso: String,
    val monthDays: Int,
    val tx: List<Tx>,
    val fixedTx: List<Tx>,
    val salaryToday: Boolean,
    val meals: List<Meal>,
    val workouts: List<Workout>,
    val habitLogs: List<HabitLogRow>,
    val sleep: List<Triple<Int, String, Double>>,
    val todos: List<Todo>,
    val projects: List<Project>,
    val bankBalance: Int,
    val profile: Profile,
    val fixedPaid: Int,
    val income: Int,
    val pending: List<PendingItem>,
    val borrowed: List<PendingItem>,
    val repayments: List<RepaymentItem>,
    val lentMonth: Int,
    val repaidMonth: Int,
    val borrowedMonth: Int,
    val paidBackMonth: Int,
    val incomeSources: List<Pair<String, Int>>,
    val onboarding: Onboarding,
)

enum class PantryStatus { Staple, New, Out, Stale, Soon, Ok }

data class PantryRow(
    val id: String,
    val foodId: String,
    val name: String,
    val stockG: Double,
    val reorderAtG: Double?,
    val shelfLifeDays: Int?,
    val note: String?,
    val staple: Boolean,
    val unit: String,
    val inbound: Int,
    val lastIn: String?,
    val lastInG: Double?,
    val status: PantryStatus,
)

data class PantryMoveRow(
    val id: String,
    val foodId: String,
    val name: String,
    val day: String,
    val quantity: Double,
    val unit: String,
    val kind: String,
    /** The meal that caused a consumption. Those lines carry no Undo. */
    val dish: String?,
)

data class DishIngredient(
    val foodId: String?,
    val name: String?,
    val quantity: Double?,
    val unit: String,
    val servings: Double,
    val note: String?,
    val fromDish: String?,
)

data class DishRow(
    val id: String,
    val name: String,
    val aliases: List<String>,
    val mealType: String?,
    val serving: String,
    val kcal: Int?,
    val proteinG: Double,
    val carbsG: Double?,
    val fatG: Double?,
    val minutes: Int?,
    val needsPrepAhead: Boolean,
    val imageUrl: String?,
    val tags: List<String>,
    val note: String?,
    val steps: String?,
    val sourceUrl: String?,
    val mine: Boolean,
    val saved: Boolean,
    val tried: Int,
    val lastTried: String?,
    val items: List<DishIngredient>,
)

data class PersonRow(
    val id: String,
    val rawName: String,
    val displayName: String?,
    val name: String,
    /** person · shop · service. */
    val kind: String?,
    val relation: String?,
    val note: String?,
    /** No confirmation means nobody has said this — the amber dot. */
    val confirmed: Boolean,
    val source: String?,
    val isPeer: Boolean,
    val defaultCategory: String?,
    /** Paise, as the server sends them. */
    val sent: Long,
    val received: Long,
    val stillOut: Long,
    val youOwe: Long,
    val typicalDays: Double?,
    val txCount: Int,
    val lastDay: String?,
)

data class ExerciseRow(
    val id: String,
    val name: String,
    val aliases: List<String>,
    val kind: String?,
    val muscleGroup: String?,
    val equipment: String?,
    val typicalMinutes: Int?,
    val steps: String?,
    val sourceUrl: String?,
    val imageUrl: String?,
    val source: String,
    val note: String?,
    val tried: Int,
    val lastTried: String?,
)

data class PlaceRow(
    val id: String,
    val name: String,
    val kind: String?,
    val lat: Double,
    val lng: Double,
    val radiusM: Int,
    val address: String?,
    val category: String?,
    val counterpartyId: String?,
    val counterpartyName: String?,
    val note: String?,
    val source: String,
    /** False on a detected pin until you say so — the amber dot. */
    val confirmed: Boolean,
    val payments: Int,
    /** Paise. */
    val spent: Long,
    val lastSeen: String?,
)

data class Found(val name: String, val lat: Double, val lng: Double, val address: String)

/** The Paisa card's limit and what it is made of — the server's one computation. */
data class LimitInfo(
    /** Null — the server has none yet (no income this month). May be negative: past the line. */
    val limit: Int?,
    val spentToday: Int,
    val left: Int?,
    val pool: Int,
    val locked: Int,
    val fixedPaid: Int,
    val daysLeft: Int,
)

data class HabitRow(
    val id: String,
    val name: String,
    /** build · break. */
    val direction: String,
    val unit: String?,
    val daysThisWeek: Int,
    val loggedEver: Int,
    val pending: Boolean = false,
)

data class ScheduleRow(
    val id: String,
    val job: String,
    val label: String,
    val blurb: String,
    /** `HH:MM`, the user's own clock. */
    val at: String,
    val repeat: String,
    val days: List<Int>,
    val enabled: Boolean,
    val lastRunDay: String?,
    val lastError: String?,
    val dueNow: Boolean,
    val pending: Boolean = false,
)

data class ProjectRow(
    val project: Project,
    val archived: Boolean,
    val openTasks: Int,
    /** Aliases the last write took from another project, so the page can say so. */
    val movedAliases: List<MovedAlias>,
)

data class ChatPage(val turns: List<WireTurn>, val hasMore: Boolean, val clearedThrough: Int)

/**
 * A nudge — `spec/in-progress/nudges.md`. `created` is the instant it was
 * written (null when the server's stamp does not parse); `day` the local day
 * it belongs to. Seen, done and dismissed are instants, as the server keeps them.
 */
data class NudgeRow(
    val id: String,
    val kind: String,
    val title: String,
    val line: String?,
    val day: String,
    val created: java.time.Instant?,
    val seenAt: String?,
    val doneAt: String?,
    val dismissedAt: String?,
    val scheduleId: String?,
    /** `refs.commitment_ids` — present only when something is due within three days. Live ids, drawn from the commitments. */
    val commitmentIds: List<String> = emptyList(),
) {
    val seen get() = seenAt != null
    val done get() = doneAt != null
    val dismissed get() = dismissedAt != null
}
