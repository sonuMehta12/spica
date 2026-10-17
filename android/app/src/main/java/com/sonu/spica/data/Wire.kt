@file:OptIn(ExperimentalSerializationApi::class)

package com.sonu.spica.data

import kotlinx.serialization.ExperimentalSerializationApi
import kotlinx.serialization.KSerializer
import kotlinx.serialization.Serializable
import kotlinx.serialization.descriptors.PrimitiveKind
import kotlinx.serialization.descriptors.PrimitiveSerialDescriptor
import kotlinx.serialization.encoding.Decoder
import kotlinx.serialization.encoding.Encoder
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonDecoder
import kotlinx.serialization.json.JsonNamingStrategy
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.doubleOrNull

/**
 * Exactly what the server sends — the prototype's `Wire*` interfaces. Field
 * names are camelCase here and snake_case on the wire; the naming strategy
 * does the translation, so a field reads the same in both codebases.
 */
val WireJson = Json {
    ignoreUnknownKeys = true
    coerceInputValues = true
    explicitNulls = false
    isLenient = true
    namingStrategy = JsonNamingStrategy.SnakeCase
}

/**
 * A NUMERIC column arrives as a string so the decimal survives the trip —
 * `"12.5"`. Some endpoints send a plain number. This takes either.
 */
object FlexNum : KSerializer<Double?> {
    override val descriptor = PrimitiveSerialDescriptor("FlexNum", PrimitiveKind.DOUBLE)
    override fun deserialize(decoder: Decoder): Double? {
        val el = (decoder as JsonDecoder).decodeJsonElement()
        if (el is JsonNull) return null
        val p = el as? JsonPrimitive ?: return null
        return p.doubleOrNull ?: p.content.toDoubleOrNull()
    }
    override fun serialize(encoder: Encoder, value: Double?) {
        if (value == null) encoder.encodeNull() else encoder.encodeDouble(value)
    }
}

typealias Num = @Serializable(FlexNum::class) Double?

@Serializable
data class WireTx(
    val id: String,
    val localDay: String,
    val amountPaise: Long = 0,
    val direction: String = "debit",
    val confidence: Double = 1.0,
    val kind: String = "expense",
    val category: String = "",
    val description: String = "",
    val tags: List<String> = emptyList(),
    val settlesId: String? = null,
    val commitmentId: String? = null,
    val commitmentInferred: Boolean = false,
    val deletedAt: String? = null,
    /** When it happened — Home's day rail places the row there. */
    val occurredAt: String? = null,
)

@Serializable
data class WireMeal(
    val id: String,
    val localDay: String,
    val mealType: String = "",
    val dish: String = "",
    val kcal: Int? = null,
    val proteinG: Num = null,
    val carbsG: Num = null,
    val fatG: Num = null,
    val confidence: Double = 1.0,
    val deletedAt: String? = null,
    val occurredAt: String? = null,
)

/** A meal write's answer: the row, and the pantry moves it caused. */
@Serializable
data class WireMealWritten(val meal: WireMeal, val pantryMoves: List<WirePantryMove> = emptyList())

@Serializable
data class WireHabitLog(
    val id: String,
    val habitId: String,
    val localDay: String,
    val amount: Num = null,
    val note: String? = null,
    val occurredAt: String? = null,
)

@Serializable
data class WireTask(
    val id: String,
    val title: String,
    val status: String = "open",
    val doneAt: String? = null,
    val due: String? = null,
    val priority: Int? = null,
    val labels: List<String> = emptyList(),
    val projectId: String? = null,
    val projectGuessed: Boolean = false,
    val source: String = "",
    val sourceRef: String? = null,
    val docRef: String? = null,
    val repo: String? = null,
    val path: String? = null,
    val line: Int? = null,
    val sourceState: String? = null,
    val tracked: Boolean = false,
    val awaitingMove: Boolean = false,
    val sourceTitle: String? = null,
)

@Serializable
data class WireProject(
    val id: String,
    val key: String = "",
    val name: String,
    val color: String = "#7A8578",
    val description: String? = null,
    val icon: String? = null,
    val aliases: List<String> = emptyList(),
    val isDefault: Boolean = false,
    val archivedAt: String? = null,
    val openTasks: Int = 0,
    val movedAliases: List<MovedAlias> = emptyList(),
)

@Serializable
data class MovedAlias(val alias: String, val from: String)

@Serializable
data class WireBalance(val asOf: String? = null, val amountPaise: Long = 0)

@Serializable
data class WireUser(
    val id: String,
    val displayName: String = "",
    val email: String? = null,
    val avatarUrl: String? = null,
    val onboardingDoneAt: String? = null,
    val dob: String? = null,
    val gender: String? = null,
    val heightCm: Num = null,
    val city: String? = null,
    val diet: String? = null,
    val timezone: String = "Asia/Kolkata",
    val savingsTargetPaise: Long? = null,
    val kcalTarget: Int? = null,
    val proteinGTarget: Num = null,
    val carbsGTarget: Num = null,
    val fatGTarget: Num = null,
    val fibreGTarget: Num = null,
    val weightTargetKg: Num = null,
    val sleepTargetMin: Int? = null,
    val stepTarget: Int? = null,
)

/** `steps` still comes on the wire, always empty, for builds before the first run; nothing reads it. */
@Serializable
data class WireOnboarding(val doneAt: String? = null)

@Serializable
data class WireHabitName(val id: String, val name: String)

@Serializable
data class WireDayRow(val localDay: String, val sleepHours: Num = null)

@Serializable
data class WirePaisa(val transactions: List<WireTx> = emptyList(), val balanceCheck: WireBalance? = null)

@Serializable
data class WireDiet(
    val meals: List<WireMeal> = emptyList(),
    val habits: List<WireHabitName> = emptyList(),
    val habitLogs: List<WireHabitLog> = emptyList(),
    val days: List<WireDayRow> = emptyList(),
)

@Serializable
data class WireWork(val projects: List<WireProject> = emptyList(), val tasks: List<WireTask> = emptyList())

@Serializable
data class WireDeck(
    val from: String? = null,
    val to: String,
    val profile: WireUser,
    val paisa: WirePaisa = WirePaisa(),
    val diet: WireDiet = WireDiet(),
    val work: WireWork = WireWork(),
    val onboarding: WireOnboarding = WireOnboarding(),
)

@Serializable
data class WireMemory(
    val id: String,
    val slug: String = "",
    val kind: String = "",
    val text: String = "",
    val source: String = "",
    val confirmedAt: String? = null,
)

@Serializable
data class WireWeighIn(val id: String, val localDay: String, val weightKg: Num = null, val estimated: Boolean = false, val note: String? = null)

@Serializable
data class WirePantryItem(
    val id: String,
    val foodId: String,
    val name: String,
    val stockG: Double = 0.0,
    val reorderAtG: Double? = null,
    val shelfLifeDays: Int? = null,
    val note: String? = null,
    val staple: Boolean = false,
    val unit: String = "g",
    val inbound: Int = 0,
    val lastIn: String? = null,
    val lastInG: Double? = null,
)

@Serializable
data class WirePantryMove(
    val id: String,
    val foodId: String,
    val name: String = "",
    val localDay: String,
    val quantity: Double = 0.0,
    val unit: String = "g",
    val kind: String = "",
    val note: String? = null,
    val dish: String? = null,
)

@Serializable
data class WireDishItem(
    val id: String = "",
    val foodId: String? = null,
    val foodName: String? = null,
    val componentDishId: String? = null,
    val quantity: Double? = null,
    val unit: String = "g",
    val servings: Num = null,
    val note: String? = null,
    val fromDish: String? = null,
)

@Serializable
data class WireDish(
    val id: String,
    val name: String,
    val aliases: List<String> = emptyList(),
    val mealType: String? = null,
    val servingLabel: String = "",
    val kcal: Int? = null,
    val proteinG: Num = null,
    val carbsG: Num = null,
    val fatG: Num = null,
    val fibreG: Num = null,
    val minutes: Int? = null,
    val needsPrepAhead: Boolean = false,
    val steps: String? = null,
    val imageUrl: String? = null,
    val tags: List<String> = emptyList(),
    val note: String? = null,
    val mine: Boolean = false,
    val saved: Boolean = false,
    val tried: Int = 0,
    val lastTried: String? = null,
    val sourceUrl: String? = null,
    val items: List<WireDishItem> = emptyList(),
)

@Serializable
data class WirePerson(
    val id: String,
    val rawName: String,
    val displayName: String? = null,
    val kind: String? = null,
    val relation: String? = null,
    val note: String? = null,
    val source: String? = null,
    val confirmedAt: String? = null,
    val isPeer: Boolean = false,
    val inContacts: Boolean = false,
    val defaultCategory: String? = null,
    val sentPaise: Long = 0,
    val receivedPaise: Long = 0,
    val stillOutPaise: Long = 0,
    val youOwePaise: Long = 0,
    val typicalDays: Double? = null,
    val txCount: Int = 0,
    val lastDay: String? = null,
)

@Serializable
data class WireExercise(
    val id: String,
    val name: String,
    val aliases: List<String> = emptyList(),
    val kind: String? = null,
    val muscleGroup: String? = null,
    val equipment: String? = null,
    val typicalMinutes: Int? = null,
    val steps: String? = null,
    val sourceUrl: String? = null,
    val imageUrl: String? = null,
    val source: String = "",
    val note: String? = null,
    val tried: Int = 0,
    val lastTried: String? = null,
)

@Serializable
data class WirePlace(
    val id: String,
    val name: String,
    val kind: String? = null,
    val lat: Double = 0.0,
    val lng: Double = 0.0,
    val radiusM: Int = 80,
    val address: String? = null,
    val category: String? = null,
    val counterpartyId: String? = null,
    val counterpartyName: String? = null,
    val note: String? = null,
    val source: String = "",
    val confirmedAt: String? = null,
    val payments: Int = 0,
    val spentPaise: Long = 0,
    val lastSeen: String? = null,
)

@Serializable
data class WireLimit(
    /** Absent — not zero — when unknown; may be negative. */
    val limitPaise: Long? = null,
    val spentTodayPaise: Long = 0,
    val leftPaise: Long? = null,
    val poolPaise: Long = 0,
    val lockedPaise: Long = 0,
    val fixedPaidPaise: Long = 0,
    val daysLeft: Int = 0,
)

@Serializable
data class WireCommitment(
    val id: String,
    val name: String = "",
    val source: String = "commitment",
    val origin: String = "manual",
    val category: String = "",
    val expectedPaise: Long = 0,
    val paidPaise: Long = 0,
    val owedPaise: Long = 0,
    val overPaise: Long = 0,
    val settled: Boolean = false,
    val skipped: Boolean = false,
    val dueDay: Int? = null,
    val repeats: Boolean = false,
    val amountSource: String = "stated",
    val inferredLinks: Int = 0,
    val carriedFromMonth: String? = null,
)

@Serializable
data class WireCommitmentsPage(
    val month: String,
    val editable: Boolean = false,
    val owedPaise: Long = 0,
    val poolPaise: Long = 0,
    val savingsTargetPaise: Long = 0,
    val limitPaise: Long? = null,
    val daysLeft: Int = 0,
    val paidCount: Int = 0,
    val openCount: Int = 0,
    val items: List<WireCommitment> = emptyList(),
)

@Serializable
data class WireSummary(val limitToday: WireLimit = WireLimit())

@Serializable
data class ChatReply(
    val reply: String = "",
    val cards: List<JsonObject> = emptyList(),
    val tokensIn: Int = 0,
    val tokensOut: Int = 0,
    val model: String = "",
)

@Serializable
data class WireTurn(
    val id: String,
    val seq: Int,
    val role: String,
    val text: String = "",
    val cards: List<JsonObject>? = null,
)

@Serializable
data class WireChatPage(
    val messages: List<WireTurn> = emptyList(),
    val hasMore: Boolean = false,
    val clearedThroughSeq: Int = 0,
)

@Serializable
data class WireHabit(
    val id: String,
    val name: String,
    val direction: String = "build",
    val unit: String? = null,
    val daysThisWeek: Int = 0,
    val loggedEver: Int = 0,
)

@Serializable
data class WireSchedule(
    val id: String,
    val job: String,
    val label: String = "",
    val blurb: String = "",
    val atLocalTime: String = "00:00",
    val repeat: String = "daily",
    val days: List<Int> = emptyList(),
    val enabled: Boolean = true,
    val lastRunLocalDay: String? = null,
    val lastRunAt: String? = null,
    val lastError: String? = null,
    val dueNow: Boolean = false,
)

@Serializable
data class WireSignIn(val token: String, val user: WireUser)

/**
 * One answer on the first run's screen 3: the confirm cards for what the
 * agent wrote, its one line (a follow-up, or "Say that again?"), and whether
 * the question is done. spec/done/onboarding-goals.md § A turn.
 */
@Serializable
data class OnboardingReply(val cards: List<JsonObject> = emptyList(), val reply: String? = null, val next: Boolean = false)

/* ─── today's plan — spec/in-progress/today-plan.md ─────────────────────── */

@Serializable
data class WirePlanTotals(val proteinG: Num = null, val kcal: Num = null)

@Serializable
data class WirePlanMeal(
    val slot: String,
    val dishId: String? = null,
    val name: String,
    val kcal: Int = 0,
    val proteinG: Num = null,
    val carbsG: Num = null,
    val fatG: Num = null,
    val why: String = "",
    val idea: Boolean = false,
    val imageUrl: String? = null,
    val imageCredit: String? = null,
)

@Serializable
data class WirePlanExercise(val exerciseId: String? = null, val name: String, val detail: String = "", val idea: Boolean = false)

@Serializable
data class WirePlanWorkout(
    val kind: String,
    val name: String = "",
    val minutes: Int? = null,
    val why: String = "",
    val exercises: List<WirePlanExercise> = emptyList(),
    val idea: Boolean = false,
    val imageUrl: String? = null,
    val imageCredit: String? = null,
)

@Serializable
data class WirePlan(
    val localDay: String,
    val available: Boolean = false,
    val done: Boolean = false,
    val targets: WirePlanTotals = WirePlanTotals(),
    val logged: WirePlanTotals = WirePlanTotals(),
    val planned: WirePlanTotals = WirePlanTotals(),
    val meals: List<WirePlanMeal> = emptyList(),
    val workout: WirePlanWorkout? = null,
)

/* ─── nudges — spec/in-progress/nudges.md ───────────────────────────────── */

/**
 * What Spica prepared without being asked. `kind` is day · meals · workout ·
 * dinner · reminder · review; `line` is the sentence as it was said — history —
 * and may be null. `refs` holds live ids; its shape is the server's, and
 * nothing here reads it yet.
 */
@Serializable
data class WireNudge(
    val id: String,
    val kind: String,
    val title: String = "",
    val line: String? = null,
    val localDay: String = "",
    val createdAt: String? = null,
    val seenAt: String? = null,
    val doneAt: String? = null,
    val dismissedAt: String? = null,
    val scheduleId: String? = null,
    val refs: kotlinx.serialization.json.JsonElement? = null,
)
