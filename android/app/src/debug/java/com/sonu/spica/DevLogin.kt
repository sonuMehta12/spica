package com.sonu.spica

import android.content.Context
import java.io.File

/**
 * Debug builds only: a session minted on the laptop, handed over without a
 * Google round-trip.
 *
 * `backend/scripts/dev_session.py` writes a token to a file; the file is piped
 * into this app's private storage with `adb shell run-as`, so the token never
 * appears on a command line or in logcat. The app reads it once and deletes it.
 * Sign-in on a real phone is Google's; this exists so the emulator can be
 * driven while the Android OAuth client is not set up yet.
 *
 * The release source set has a stub that always returns null.
 */
object DevLogin {
    fun consume(context: Context): String? {
        val f = File(context.filesDir, "dev_token")
        if (!f.exists()) return null
        val token = f.readText().trim()
        f.delete()
        return token.ifEmpty { null }
    }
}
