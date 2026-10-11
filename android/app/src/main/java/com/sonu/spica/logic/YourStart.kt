package com.sonu.spica.logic

import com.sonu.spica.data.HabitRow
import com.sonu.spica.data.MemoryRow
import com.sonu.spica.data.Profile
import com.sonu.spica.data.WeighInRow
import com.sonu.spica.lib.Fmt
import com.sonu.spica.state.isDietNote
import com.sonu.spica.state.isGoal

/**
 * The first run's screen 4, *You're all set* — where the person starts and
 * where they are headed. Worked out from live rows every time it is drawn,
 * never from the cards' copies: a value undone or changed is simply what the
 * rows say now. A field not given is left out — never a zero, never a default.
 * spec/done/onboarding-goals.md § 4.
 */
object YourStart {

    /** One tag on *About you*. `estimated`: the weight was said as a guess, and what is worked out from it. */
    data class Fact(val text: String, val estimated: Boolean = false)

    /** Which coin a goal wears: health, money, a habit — or a goal kept in their words. */
    enum class GoalKind { Weight, Words, Money, Habit }

    /** One piece of a goal's second line, dotted when it is the guessed weight. */
    data class Part(val text: String, val estimated: Boolean = false)

    data class Goal(val kind: GoalKind, val title: String, val titleEstimated: Boolean = false, val sub: List<Part> = emptyList())

    /** Adult BMI is wrong for a child: not shown when the date of birth makes them under 18. */
    private const val BMI_FROM_AGE = 18

    /** The BMI, a bare number to one decimal — worked out from the height as stored, never stored itself. */
    fun bmi(kg: Double, heightCm: Double): Double {
        val m = heightCm / 100
        return Math.round(kg / (m * m) * 10) / 10.0
    }

    /**
     * *About you*: gender, age, height, the weight, the BMI, the city, the diet
     * and what it rules out. The weight and the BMI carry the dot while the
     * weight is a guess. No category beside the BMI — the cut-offs are
     * contested, and it was not asked for.
     */
    fun about(p: Profile, latest: WeighInRow?, memories: List<MemoryRow>, today: String): List<Fact> = buildList {
        ProfileEdit.choiceLabel(FieldId.Gender, p.gender)?.let { add(Fact(it)) }
        val age = ProfileEdit.age(p.dob, today)
        age?.let { add(Fact("$it years")) }
        p.heightCm?.let { add(Fact("${Math.round(it)} cm")) }
        latest?.let { add(Fact("${Fmt.num(it.kg)} kg", it.estimated)) }
        val h = p.heightCm
        if (latest != null && h != null && h > 0 && (age == null || age >= BMI_FROM_AGE)) {
            // Always to one place — 23.0, not 23 — as the web shows it.
            add(Fact("BMI ${String.format(java.util.Locale.US, "%.1f", bmi(latest.kg, h))}", latest.estimated))
        }
        p.city?.takeIf { it.isNotBlank() }?.let { add(Fact(it)) }
        ProfileEdit.choiceLabel(FieldId.Diet, p.diet)?.let { add(Fact(it)) }
        // The diet's exceptions, in their words: the foods they never eat, and what a diet outside the four adds.
        memories.filter(::isDietNote).forEach { add(Fact(it.text)) }
    }

    /**
     * *Your goals*, one row each. A weight goal is said from the latest
     * weigh-in and the stored target, so it stays true as the weight moves;
     * while that weigh-in is a guess its figure and the change worked out
     * from it are dotted, the target is not. Habits keep no frequency, so
     * none is shown.
     */
    fun goals(p: Profile, latest: WeighInRow?, memories: List<MemoryRow>, habits: List<HabitRow>): List<Goal> = buildList {
        p.weightTargetKg?.let { target ->
            if (latest == null) add(Goal(GoalKind.Weight, "Reach ${Fmt.num(target)} kg"))
            else {
                val change = Math.round((latest.kg - target) * 10) / 10.0
                val title = when {
                    change > 0 -> "Lose ${Fmt.num(change)} kg"
                    change < 0 -> "Gain ${Fmt.num(-change)} kg"
                    else -> "Stay at ${Fmt.num(target)} kg"
                }
                // "Stay at 67 kg" is the stored target alone, so it is never dotted.
                add(Goal(GoalKind.Weight, title, latest.estimated && change != 0.0, listOf(Part("${Fmt.num(latest.kg)} kg", latest.estimated), Part(" → ${Fmt.num(target)} kg"))))
            }
        }
        memories.filter(::isGoal).forEach { add(Goal(GoalKind.Words, it.text)) }
        p.savingsTarget?.let { add(Goal(GoalKind.Money, "Save ${Fmt.rupees(it)}", sub = listOf(Part("every month")))) }
        habits.forEach { add(Goal(GoalKind.Habit, it.name, sub = listOf(Part(if (it.direction == "break") "a habit to break" else "a habit to build")))) }
    }
}
