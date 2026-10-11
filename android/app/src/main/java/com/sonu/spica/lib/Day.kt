package com.sonu.spica.lib

import java.time.Instant
import java.time.LocalDate
import java.time.LocalTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.time.temporal.ChronoUnit
import java.util.Locale

/**
 * ISO local days — `"2026-09-13"` — are the app's identity for a day.
 *
 * A day-of-month number is not one: the 13th of September and the 13th of
 * August are the same number, and bucketing by it merged two days a month
 * apart on the web (it read 13 August's meals as today's). ISO days sort
 * lexicographically in calendar order, so `>=` and `<=` on the strings are the
 * range checks. Port of `frontend/src/lib/day.ts`.
 */
object Day {
    private fun parse(iso: String): LocalDate = LocalDate.parse(iso.take(10))

    /** The device's current local day. Only the device knows what day it is here. */
    fun today(): String = LocalDate.now().toString()

    /**
     * An instant — a `done_at` timestamp — as the day it happened *here*.
     * Slicing the string would give the UTC day, a different date for anything
     * ticked before 5:30am in Delhi.
     */
    fun localDayOf(ts: String): String = try {
        Instant.parse(ts).atZone(ZoneId.systemDefault()).toLocalDate().toString()
    } catch (_: Exception) {
        try {
            java.time.OffsetDateTime.parse(ts).atZoneSameInstant(ZoneId.systemDefault()).toLocalDate().toString()
        } catch (_: Exception) {
            ts.take(10)
        }
    }

    fun addDays(iso: String, n: Int): String = parse(iso).plusDays(n.toLong()).toString()

    /** Whole days from `from` to `to`. Same day is 0. */
    fun diffDays(from: String, to: String): Int = ChronoUnit.DAYS.between(parse(from), parse(to)).toInt()

    fun eachDay(from: String, to: String): List<String> {
        val out = mutableListOf<String>()
        var d = from
        while (diffDays(d, to) >= 0) {
            out += d
            d = addDays(d, 1)
        }
        return out
    }

    fun monthStart(iso: String) = "${iso.take(7)}-01"

    fun maxDay(a: String, b: String) = if (a > b) a else b

    /** The day-of-month — for a label or an axis tick, never for identity. */
    fun dayOfMonth(iso: String) = iso.substring(8, 10).toInt()

    /** Monday-indexed weekday, 0–6. */
    fun weekIndex(iso: String) = parse(iso).dayOfWeek.value - 1

    fun monthDays(iso: String) = parse(iso).lengthOfMonth()

    /** The device's wall clock as HH:MM:SS — the agent needs breakfast apart from dinner. */
    fun localTime(): String = LocalTime.now().format(DateTimeFormatter.ofPattern("HH:mm:ss"))

    /** Now, on the given local day, as the wire's `occurred_at`. */
    fun occurredAt(localDay: String): String =
        "${localDay}T" + Instant.now().toString().substringAfter('T')

    fun hour(): Int = LocalTime.now().hour

    /** "3 Jul". Three letters for every month — en-IN spells September "Sept". */
    fun shortDay(iso: String): String {
        val d = parse(iso)
        return "${d.dayOfMonth} ${d.month.getDisplayName(java.time.format.TextStyle.SHORT, Locale.US)}"
    }

    /** "Wednesday, 30 September" — the page's heading. */
    fun longDay(iso: String): String {
        val d = parse(iso)
        val wd = d.dayOfWeek.getDisplayName(java.time.format.TextStyle.FULL, Locale.US)
        return "$wd, ${d.dayOfMonth} ${d.month.getDisplayName(java.time.format.TextStyle.FULL, Locale.US)}"
    }

    /** "Wed, 16 Sep" — a day on a card. ISO is for machines. */
    fun cardDay(iso: String): String {
        val d = parse(iso)
        return "${d.dayOfWeek.getDisplayName(java.time.format.TextStyle.SHORT, Locale.US)}, ${d.dayOfMonth} ${d.month.getDisplayName(java.time.format.TextStyle.SHORT, Locale.US)}"
    }

    /** "September". */
    fun monthName(iso: String): String =
        parse(iso).month.getDisplayName(java.time.format.TextStyle.FULL, Locale.US)

    /** Breakfast / Lunch / Snack / Dinner by the clock — a default, not a category. */
    fun mealTypeNow(): String {
        val h = hour()
        return if (h < 11) "Breakfast" else if (h < 15) "Lunch" else if (h < 19) "Snack" else "Dinner"
    }
}
