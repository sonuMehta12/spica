package com.sonu.spica.ui.common

import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Intent
import android.speech.RecognizerIntent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState

/**
 * The mic, handed over to the phone's own speech recogniser — Google's, the
 * one every keyboard uses. en-IN because the person speaks Hinglish, and
 * Indian English writes it in the Latin script the agent already reads.
 *
 * What it heard comes back to `onResult`, null when nothing was said or the
 * sheet was closed. It is never sent from here: speech gets numbers wrong
 * ("one sixty" as 116, "five nine"), so it fills a bar the person sends.
 * No RECORD_AUDIO: the recogniser owns the mic.
 */
@Composable
fun rememberListen(prompt: String, onResult: (String?) -> Unit, onUnavailable: () -> Unit): () -> Unit {
    val result by rememberUpdatedState(onResult)
    val unavailable by rememberUpdatedState(onUnavailable)
    val launcher = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { r ->
        val said = r.data?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)?.firstOrNull()
        result(if (r.resultCode == Activity.RESULT_OK && !said.isNullOrBlank()) said else null)
    }
    return remember(launcher, prompt) {
        {
            val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
                .putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                .putExtra(RecognizerIntent.EXTRA_LANGUAGE, "en-IN")
                .putExtra(RecognizerIntent.EXTRA_PROMPT, prompt)
            try {
                launcher.launch(intent)
            } catch (_: ActivityNotFoundException) {
                unavailable()
            }
        }
    }
}
