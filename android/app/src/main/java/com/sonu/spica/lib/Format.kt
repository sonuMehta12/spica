package com.sonu.spica.lib

import kotlin.math.abs
import kotlin.math.roundToLong

/** Port of `frontend/src/lib/format.ts` and `lib/clock.ts`. */
object Fmt {
    /**
     * Indian digit grouping — `1,00,000`, not `100,000`. Done by hand: the JVM's
     * en-IN locale groups in threes on some Android versions.
     */
    fun indian(n: Long): String {
        val neg = n < 0
        val s = abs(n).toString()
        if (s.length <= 3) return (if (neg) "−" else "") + s
        val last3 = s.takeLast(3)
        var rest = s.dropLast(3)
        val parts = mutableListOf<String>()
        while (rest.length > 2) {
            parts.add(0, rest.takeLast(2))
            rest = rest.dropLast(2)
        }
        if (rest.isNotEmpty()) parts.add(0, rest)
        return (if (neg) "−" else "") + parts.joinToString(",") + "," + last3
    }

    fun indian(n: Double): String = indian(jsRound(n))
    fun indian(n: Int): String = indian(n.toLong())

    /** `Math.round` as JavaScript does it: halves go up, including negatives. */
    fun jsRound(n: Double): Long = kotlin.math.floor(n + 0.5).toLong()

    /** Indian-format rupees, no paise — `₹1,100`; a negative reads `₹-23`, as on the web. */
    fun rupees(n: Double): String = jsRound(n).let { if (it < 0) "−₹" + indian(-it) else "₹" + indian(it) }

    fun rupees(n: Int): String = rupees(n.toDouble())
    fun rupees(n: Long): String = rupees(n.toDouble())

    fun grams(n: Double) = "${jsRound(n)}g"

    fun kcal(n: Double) = "${indian(jsRound(n))} kcal"

    /** `435` → `7h 15m`. */
    fun duration(minutes: Double): String {
        val h = (minutes / 60).toInt()
        val m = (minutes % 60).roundToLong()
        return if (m != 0L) "${h}h ${m}m" else "${h}h"
    }

    /** Minutes-from-midnight → a wall clock. Negative is the evening before. */
    fun clock(minutes: Int): String {
        val w = ((minutes % 1440) + 1440) % 1440
        val h24 = w / 60
        val m = w % 60
        val suffix = if (h24 < 12) "am" else "pm"
        val h = if (h24 % 12 == 0) 12 else h24 % 12
        return "$h:${m.toString().padStart(2, '0')}$suffix"
    }

    /** A number as the web prints it: no trailing `.0`. */
    fun num(n: Double): String =
        if (n == kotlin.math.floor(n) && !n.isInfinite()) n.toLong().toString() else n.toString()

    private var seq = 0

    /** Monotonic local id — chat messages the client makes itself. */
    fun nextId(prefix: String): String {
        seq += 1
        return "$prefix$seq"
    }
}
