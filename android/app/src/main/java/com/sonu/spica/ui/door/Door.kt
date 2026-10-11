package com.sonu.spica.ui.door

import android.app.Activity
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.credentials.CredentialManager
import androidx.credentials.CustomCredential
import androidx.credentials.GetCredentialRequest
import androidx.credentials.exceptions.GetCredentialCancellationException
import androidx.credentials.exceptions.GetCredentialException
import com.google.android.libraries.identity.googleid.GetSignInWithGoogleOption
import com.google.android.libraries.identity.googleid.GoogleIdTokenCredential
import com.sonu.spica.BuildConfig
import com.sonu.spica.data.Api
import com.sonu.spica.data.status
import com.sonu.spica.ui.common.Glyph
import com.sonu.spica.ui.common.Ground
import com.sonu.spica.ui.common.Ph
import com.sonu.spica.ui.common.Wordmark
import com.sonu.spica.ui.common.tap
import com.sonu.spica.ui.theme.C
import com.sonu.spica.ui.theme.S
import com.sonu.spica.ui.theme.T
import kotlinx.coroutines.launch

/**
 * The door: the one screen before sign-in, and the whole pitch. The wordmark,
 * the film in dots, the line it is all for, and Google's button — no
 * subheading, no controls on the film. Port of `Door.tsx`;
 * spec/done/onboarding-goals.md § 1.
 *
 * `filmAt` freezes the film at that millisecond; only the debug gallery
 * passes it.
 */
@Composable
fun Door(onSignedIn: () -> Unit, filmAt: Double? = null) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var problem by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }

    fun signIn() {
        if (busy) return
        if (BuildConfig.GOOGLE_CLIENT_ID.isEmpty()) {
            problem = "Sign-in is not configured. spica.googleClientId is unset."
            return
        }
        busy = true
        problem = ""
        scope.launch {
            try {
                val option = GetSignInWithGoogleOption.Builder(serverClientId = BuildConfig.GOOGLE_CLIENT_ID).build()
                val req = GetCredentialRequest.Builder().addCredentialOption(option).build()
                val result = CredentialManager.create(context).getCredential(context as Activity, req)
                val cred = result.credential
                if (cred is CustomCredential && cred.type == GoogleIdTokenCredential.TYPE_GOOGLE_ID_TOKEN_CREDENTIAL) {
                    val idToken = GoogleIdTokenCredential.createFrom(cred.data).idToken
                    Api.signInWithGoogle(idToken)
                    onSignedIn()
                } else {
                    problem = "That did not go through. Try again."
                }
            } catch (_: GetCredentialCancellationException) {
                /* they closed the sheet — nothing to say */
            } catch (e: GetCredentialException) {
                problem = "Google sign-in is not available on this phone yet."
            } catch (e: Exception) {
                // 403 is a sentence for the user, not a failure to retry.
                problem = if (e.status() == 403) "Spica is invite-only right now." else "That did not go through. Try again."
            } finally {
                busy = false
            }
        }
    }

    // The film bleeds to the screen's edges, as on the prototype; the words
    // and the button keep the page's gutter. It takes what the rest leaves,
    // so the door never scrolls.
    Column(
        Modifier.fillMaxSize().background(Ground).safeDrawingPadding().padding(top = 24.dp, bottom = 26.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Wordmark(20.sp)
        DotFilm(Modifier.padding(top = 6.dp).weight(1f).fillMaxWidth(), filmAt)
        Text(
            "Less managing life.\nMore achieving it.",
            style = T.display.copy(fontSize = 25.sp, lineHeight = 31.sp, textAlign = TextAlign.Center),
            modifier = Modifier.padding(top = 6.dp, start = 20.dp, end = 20.dp),
        )
        Column(
            Modifier.padding(top = 24.dp, start = 20.dp, end = 20.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            GoogleButton(busy, ::signIn)
            if (problem.isNotEmpty()) Text(problem, style = T.agentVoice.copy(color = C.red, textAlign = TextAlign.Center))
            // No export, no sale, delete anything — never a claim that it stays on the phone.
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                Glyph(Ph.lock, 14.dp, C.faint)
                Text("Your data stays yours", style = T.sans.copy(fontSize = 13.sp, color = C.faint))
            }
        }
    }
}

/** Google's own outline pill, drawn in the app's hand since the SDK draws none. */
@Composable
private fun GoogleButton(busy: Boolean, onClick: () -> Unit) {
    // A white pill floating on the ground, Google's mark in ink — no letter standing in for a logo.
    val shape = RoundedCornerShape(50)
    Row(
        Modifier
            .alpha(if (busy) 0.5f else 1f)
            .height(52.dp)
            .fillMaxWidth()
            .widthIn(max = 380.dp)
            .then(S.widget(shape))
            .clip(shape)
            .background(C.white)
            .tap(enabled = !busy, onClick = onClick)
            .padding(horizontal = 22.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(10.dp, Alignment.CenterHorizontally),
    ) {
        Glyph(Ph.googleLogo, 18.dp, C.ink)
        Text(if (busy) "Signing in…" else "Continue with Google", style = T.sans.copy(fontSize = 16.sp, lineHeight = 20.sp, fontWeight = FontWeight.Medium))
    }
}
