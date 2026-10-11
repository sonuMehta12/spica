package com.sonu.spica

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.isImeVisible
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.sonu.spica.data.Session
import com.sonu.spica.state.SpicaViewModel
import com.sonu.spica.ui.common.TrayAction
import com.sonu.spica.ui.common.TrayActions
import com.sonu.spica.ui.door.Door
import com.sonu.spica.ui.home.Home
import com.sonu.spica.ui.onboarding.FirstRun
import com.sonu.spica.ui.theme.C
import com.sonu.spica.ui.theme.T

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        Session.init(applicationContext)
        // Debug builds only: a session handed over from the laptop.
        DevLogin.consume(applicationContext)?.let(Session::set)
        enableEdgeToEdge()
        setContent { SpicaTheme { Gate() } }
    }
}

/** Material underneath only for ripples and popups; every visible colour is ours. */
@Composable
fun SpicaTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = lightColorScheme(
            primary = C.brand, onPrimary = C.white, background = C.paper, onBackground = C.ink,
            surface = C.white, onSurface = C.ink, surfaceVariant = C.lineSoft, outline = C.border,
        ),
        content = content,
    )
}

/**
 * Signed in and loaded, or the door. Rendering first and filling in later
 * would flash zeros — a number the server did not send — so the deck waits
 * for the deck. A 401 mid-session drops the token and the door comes back.
 * Loaded, an account whose first run is not finished or skipped meets it
 * before Home, and Home is not composed under it. Port of `Boot.tsx`.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun Gate() {
    val vm: SpicaViewModel = viewModel()
    val token by Session.token.collectAsState()
    val s by vm.state.collectAsState()

    LaunchedEffect(token) {
        if (token == null) vm.reset() else if (!s.booted) vm.boot()
    }

    when {
        token == null -> Door(onSignedIn = { })
        s.booted && s.onboarding.doneAt == null -> FirstRun(vm, s)
        s.booted -> Home(vm, s, onSignedOut = { })
        else -> Column(
            Modifier.fillMaxSize().background(C.paper).safeDrawingPadding().padding(24.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp, androidx.compose.ui.Alignment.CenterVertically),
        ) {
            if (s.bootError == null) {
                Text("Loading…", style = T.agentVoice.copy(color = C.grey))
            } else {
                // Say what broke rather than an empty deck that looks like a day with nothing in it.
                Text("Couldn't reach the server.", style = T.agentVoice)
                Text(s.bootError ?: "", style = T.mono.copy(fontSize = 11.sp, color = C.grey))
                TrayActions(listOf(TrayAction("Retry") { vm.boot() }))
            }
        }
    }

    // The keyboard is Back's first step, everywhere: one press hides it and
    // does nothing else (THEME.md § Back). The pages' handlers would otherwise
    // see the same press. Composed when the keyboard appears and again when
    // the stack moves, so it is always the newest handler and outranks theirs.
    val ime = WindowInsets.isImeVisible
    val keyboard = LocalSoftwareKeyboardController.current
    val focus = LocalFocusManager.current
    key(ime, s.stack.size, s.onboarding.doneAt) {
        if (ime) BackHandler { keyboard?.hide(); focus.clearFocus() }
    }
}
