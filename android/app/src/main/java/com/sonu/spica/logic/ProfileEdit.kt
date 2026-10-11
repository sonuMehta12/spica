package com.sonu.spica.logic

import com.sonu.spica.data.Profile
import com.sonu.spica.lib.Day
import com.sonu.spica.lib.Fmt
import kotlinx.serialization.json.JsonObject
import com.sonu.spica.data.toJson

/**
 * One table of fields drives the Profile page, the inline editor and the
 * parser that turns what was typed into a PATCH. Port of `state/profileEdit.ts`.
 */
enum class Kind { Text, Date, Rupees, Int, Grams, Kg, Cm, Sleep, Choice }

enum class FieldId(val id: String, val label: String, val wire: String, val kind: Kind, val aliases: List<String> = emptyList()) {
    Name("name", "Name", "display_name", Kind.Text),
    Gender("gender", "Gender", "gender", Kind.Choice),
    /** Stored as a date of birth, shown as an age — one said as "28" is 1 January of the year, and only the year means anything. */
    Dob("dob", "Age", "dob", Kind.Date, listOf("birthday")),
    Height("height", "Height", "height_cm", Kind.Cm),
    City("city", "City", "city", Kind.Text),
    Diet("diet", "Diet", "diet", Kind.Choice),
    Timezone("timezone", "Timezone", "timezone", Kind.Text, listOf("tz")),
    Goal("goal", "Saving goal", "savings_target_paise", Kind.Rupees, listOf("saving", "savings")),
    Kcal("kcal", "Calories", "kcal_target", Kind.Int, listOf("calories", "cal")),
    Protein("protein", "Protein", "protein_g_target", Kind.Grams),
    Carbs("carbs", "Carbs", "carbs_g_target", Kind.Grams, listOf("carb")),
    Fat("fat", "Fat", "fat_g_target", Kind.Grams),
    Fibre("fibre", "Fibre", "fibre_g_target", Kind.Grams, listOf("fiber")),
    Weight("weight", "Weight target", "weight_target_kg", Kind.Kg),
    Sleep("sleep", "Sleep", "sleep_target_min", Kind.Sleep),
    Steps("steps", "Steps", "step_target", Kind.Int, listOf("step"));

    /** Every field can be emptied but the name, which is changed, never removed, and the timezone, which every day is read in. */
    val clearable: Boolean get() = this != Name && this != Timezone

    companion object {
        fun byWord(word: String): FieldId? {
            val w = word.lowercase()
            return entries.firstOrNull { it.id == w || w in it.aliases }
        }
    }
}

object ProfileEdit {
    val FINANCE = listOf(FieldId.Goal)
    val HEALTH = listOf(FieldId.Kcal, FieldId.Protein, FieldId.Carbs, FieldId.Fat, FieldId.Fibre, FieldId.Sleep, FieldId.Steps)
    val WEIGHT = listOf(FieldId.Weight)
    val ABOUT = listOf(FieldId.Name, FieldId.Gender, FieldId.Dob, FieldId.Height, FieldId.City, FieldId.Diet, FieldId.Timezone)

    /** The columns' own values, and how each reads. A diet outside the four is the nearest of them plus a memory. */
    val GENDERS = listOf("female" to "Female", "male" to "Male", "other" to "Other")
    val DIETS = listOf("veg" to "Veg", "nonveg" to "Non-veg", "eggetarian" to "Eggetarian", "any" to "Anything")

    fun options(f: FieldId): List<Pair<String, String>> = when (f) {
        FieldId.Gender -> GENDERS
        FieldId.Diet -> DIETS
        else -> emptyList()
    }

    /** `nonveg` → `Non-veg`; a value this build does not know is shown as stored. */
    fun choiceLabel(f: FieldId, value: String?): String? = value?.let { v -> options(f).firstOrNull { it.first == v }?.second ?: v }

    /** Whole years lived by `today`. Null when there is no date of birth, or it will not parse. */
    fun age(dob: String?, today: String = Day.today()): Int? {
        if (dob == null) return null
        return runCatching { java.time.Period.between(java.time.LocalDate.parse(dob), java.time.LocalDate.parse(today)).years }.getOrNull()
    }

    val MEMORY_KINDS = listOf("identity", "preference", "style", "interest", "project", "reference")

    fun sleepLabel(min: Int): String {
        val h = min / 60
        val m = min % 60
        return if (m != 0) "${h}h ${m}m" else "${h}h"
    }

    fun raw(f: FieldId, p: Profile): Any? = when (f) {
        FieldId.Name -> p.displayName
        FieldId.Gender -> p.gender
        FieldId.Dob -> p.dob
        FieldId.Height -> p.heightCm
        FieldId.City -> p.city
        FieldId.Diet -> p.diet
        FieldId.Timezone -> p.timezone
        FieldId.Goal -> p.savingsTarget
        FieldId.Kcal -> p.kcalTarget
        FieldId.Protein -> p.proteinTarget
        FieldId.Carbs -> p.carbsTarget
        FieldId.Fat -> p.fatTarget
        FieldId.Fibre -> p.fibreTarget
        FieldId.Weight -> p.weightTargetKg
        FieldId.Sleep -> p.sleepTargetMin
        FieldId.Steps -> p.stepTarget
    }

    private fun show(v: Any): String = when (v) {
        is Double -> Fmt.num(v)
        else -> v.toString()
    }

    /** How the Profile page shows a value. Null = unset, shown as an honest dash. */
    fun formatValue(f: FieldId, p: Profile): String? {
        val v = raw(f, p) ?: return null
        if (v is String && v.isEmpty()) return null
        // A date of birth is never shown as the date: one worked out from an age would read as a birthday.
        if (f == FieldId.Dob) return age(v as String)?.let { "$it years" }
        return when (f.kind) {
            Kind.Rupees -> Fmt.rupees((v as Number).toDouble())
            Kind.Grams -> "${show(v)} g"
            Kind.Kg -> "${show(v)} kg"
            Kind.Cm -> "${show(v)} cm"
            Kind.Sleep -> sleepLabel((v as Number).toInt())
            Kind.Int -> Fmt.indian((v as Number).toLong())
            Kind.Choice -> choiceLabel(f, v as String)
            else -> v.toString()
        }
    }

    /**
     * What the inline editor opens with — sleep in hours, money in rupees, a
     * date of birth as the stored ISO date, as the web does. Every field opens
     * with its value, so a save left empty always means *clear it*.
     */
    fun draftValue(f: FieldId, p: Profile): String {
        val v = raw(f, p) ?: return ""
        if (f.kind == Kind.Sleep) return Fmt.num(Math.round((v as Number).toDouble() / 60 * 10) / 10.0)
        return show(v)
    }

    /**
     * A field's value as `PATCH /users/me` takes it — money in paise; grams,
     * kilograms and centimetres as text — read from the person as they were.
     * Null when it was unset, which clears it.
     */
    fun wireValue(f: FieldId, p: Profile): Any? {
        val v = raw(f, p) ?: return null
        return when (f.kind) {
            Kind.Rupees -> Math.round((v as Number).toDouble() * 100)
            Kind.Grams, Kind.Kg, Kind.Cm -> Fmt.num((v as Number).toDouble())
            else -> v
        }
    }

    data class Parsed(val body: Map<String, Any?>, val profile: Profile, val summary: String) {
        fun json(): JsonObject = JsonObject(body.mapValues { toJson(it.value) })
    }

    private fun apply(p: Profile, f: FieldId, v: Any?): Profile = when (f) {
        FieldId.Name -> p.copy(displayName = v as String)
        FieldId.Gender -> p.copy(gender = v as String?)
        FieldId.Dob -> p.copy(dob = v as String?)
        FieldId.Height -> p.copy(heightCm = v as Double?)
        FieldId.City -> p.copy(city = v as String?)
        FieldId.Diet -> p.copy(diet = v as String?)
        FieldId.Timezone -> p.copy(timezone = v as String)
        FieldId.Goal -> p.copy(savingsTarget = (v as Number?)?.toInt())
        FieldId.Kcal -> p.copy(kcalTarget = (v as Number?)?.toInt())
        FieldId.Protein -> p.copy(proteinTarget = v as Double?)
        FieldId.Carbs -> p.copy(carbsTarget = v as Double?)
        FieldId.Fat -> p.copy(fatTarget = v as Double?)
        FieldId.Fibre -> p.copy(fibreTarget = v as Double?)
        FieldId.Weight -> p.copy(weightTargetKg = v as Double?)
        FieldId.Sleep -> p.copy(sleepTargetMin = (v as Number?)?.toInt())
        FieldId.Steps -> p.copy(stepTarget = (v as Number?)?.toInt())
    }

    /** An empty save: null on the wire, which clears the column. Null for a field that cannot be emptied. */
    fun clear(f: FieldId, base: Profile): Parsed? =
        if (!f.clearable) null else Parsed(linkedMapOf(f.wire to null), apply(base, f, null), "${f.label} cleared")

    /**
     * Typed text → a PATCH. `field` is the row being edited, so a bare number
     * has somewhere to go; `raw` may carry the field word too ("goal 15000").
     * Null when nothing usable was typed — the caller shows a hint, never guesses.
     */
    fun parse(field: FieldId?, raw: String, base: Profile): Parsed? {
        val text = raw.trim()
        if (text.isEmpty()) return null
        val body = linkedMapOf<String, Any?>()
        var profile = base
        var summary = ""

        if (field != null && (field.kind == Kind.Text || field.kind == Kind.Date || field.kind == Kind.Choice)) {
            val value = text.replace(Regex("^${field.id}\\s+", RegexOption.IGNORE_CASE), "").trim()
            if (value.isEmpty()) return null
            if (field.kind == Kind.Date && !Regex("^\\d{4}-\\d{2}-\\d{2}$").matches(value)) return null
            if (field.kind == Kind.Choice && options(field).none { it.first == value }) return null
            body[field.wire] = value
            return Parsed(body, apply(profile, field, value), "${field.label} $value")
        }

        fun setNumber(f: FieldId, n: Double): Boolean {
            if (!(n > 0)) return false
            when (f.kind) {
                Kind.Rupees -> {
                    body[f.wire] = Math.round(n * 100)
                    profile = apply(profile, f, n)
                }
                Kind.Int -> {
                    body[f.wire] = Math.round(n)
                    profile = apply(profile, f, Math.round(n))
                }
                Kind.Sleep -> {
                    // "sleep 7.5" is hours; "sleep 450" is already minutes.
                    val min = if (n < 24) Math.round(n * 60) else Math.round(n)
                    body[f.wire] = min
                    profile = apply(profile, f, min)
                }
                // grams · kg · cm — NUMERIC on the wire, so a string.
                else -> {
                    body[f.wire] = Fmt.num(n)
                    profile = apply(profile, f, n)
                }
            }
            val shown = formatValue(f, profile) ?: Fmt.num(n)
            summary += (if (summary.isNotEmpty()) " · " else "") + "${f.label} $shown"
            return true
        }

        var any = false
        for (m in Regex("([a-z]+)\\s*(\\d+(?:\\.\\d+)?)", RegexOption.IGNORE_CASE).findAll(text)) {
            val f = FieldId.byWord(m.groupValues[1])
            if (f != null && f.kind != Kind.Text && f.kind != Kind.Date && f.kind != Kind.Choice) any = setNumber(f, m.groupValues[2].toDouble()) || any
        }
        if (!any && field != null) {
            Regex("^(\\d+(?:\\.\\d+)?)$").find(text)?.let { any = setNumber(field, it.groupValues[1].toDouble()) }
        }
        return if (any) Parsed(body, profile, summary) else null
    }

    data class InputSpec(val numeric: Boolean, val decimal: Boolean, val prefix: String? = null, val suffix: String? = null, val hint: String)

    fun inputFor(f: FieldId): InputSpec = when (f.kind) {
        Kind.Rupees -> InputSpec(true, false, prefix = "₹", hint = "A whole number of rupees.")
        Kind.Int -> InputSpec(true, false, hint = "A whole number.")
        Kind.Grams -> InputSpec(true, true, suffix = "g", hint = "Grams.")
        Kind.Kg -> InputSpec(true, true, suffix = "kg", hint = "Kilograms.")
        Kind.Cm -> InputSpec(true, true, suffix = "cm", hint = "Centimetres.")
        Kind.Sleep -> InputSpec(true, true, suffix = "h", hint = "Hours — 7.5 is fine.")
        Kind.Date -> InputSpec(false, false, hint = "Your date of birth — shown as an age.")
        else -> InputSpec(false, false, hint = "")
    }

    /** "78.4" or "weight 78.4" → kg. */
    fun parseKg(raw: String): Double? {
        val kg = Regex("(\\d+(?:\\.\\d+)?)").find(raw)?.groupValues?.get(1)?.toDoubleOrNull() ?: return null
        return if (kg > 20 && kg < 400) kg else null
    }
}
