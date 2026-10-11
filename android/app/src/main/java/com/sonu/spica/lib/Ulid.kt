package com.sonu.spica.lib

import java.security.SecureRandom

/**
 * A ULID, made on the device — 48 bits of time then 80 bits of randomness,
 * Crockford base32, 26 chars. The client owns the id, so an optimistic row is
 * born with its permanent identity and a retried POST is a replay, never a
 * duplicate. Same twenty lines as `frontend/src/lib/ulid.ts`.
 */
object Ulid {
    private const val ENC = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
    private val random = SecureRandom()

    fun next(now: Long = System.currentTimeMillis()): String {
        val time = CharArray(10)
        var t = now
        for (i in 9 downTo 0) {
            time[i] = ENC[(t % 32).toInt()]
            t /= 32
        }
        val r = ByteArray(16).also(random::nextBytes)
        val rand = CharArray(16) { ENC[r[it].toInt() and 31] }
        return String(time) + String(rand)
    }
}
