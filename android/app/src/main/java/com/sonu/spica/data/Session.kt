package com.sonu.spica.data

import android.content.Context
import android.content.SharedPreferences
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

/**
 * The session token, and the one place that knows it is gone.
 *
 * Opaque to the app: it goes out on every request as a bearer header and comes
 * back only from sign-in. Kept in the app's private preferences — sandboxed
 * per app, and `allowBackup` is off so it never leaves the phone in a backup.
 * Port of `frontend/src/data/session.ts`.
 */
object Session {
    private const val KEY = "spica.session"
    private lateinit var prefs: SharedPreferences

    private val _token = MutableStateFlow<String?>(null)

    /** Null while signed out. The app shows the door whenever this is null. */
    val token: StateFlow<String?> = _token

    fun init(context: Context) {
        prefs = context.getSharedPreferences("spica", Context.MODE_PRIVATE)
        _token.value = prefs.getString(KEY, null)
    }

    fun set(t: String?) {
        _token.value = t
        prefs.edit().apply { if (t == null) remove(KEY) else putString(KEY, t) }.apply()
    }

    /** Drop the token. Called by the HTTP client on any 401 — the door comes back. */
    fun signedOut() = set(null)
}
