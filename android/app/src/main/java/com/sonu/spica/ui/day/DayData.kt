package com.sonu.spica.ui.day

import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import kotlin.coroutines.cancellation.CancellationException
import com.sonu.spica.data.Api
import com.sonu.spica.data.DeckData
import com.sonu.spica.logic.DaySheet
import com.sonu.spica.state.AppState

/**
 * A sheet open over Home: which one, the day it shows, the row that opened
 * it (picked out on the sheet) and, for a habit row, which habit. Kept as one
 * string so the open layer survives a rotation.
 */
data class SheetOpen(val sheet: DaySheet, val day: String, val key: String? = null, val habit: String? = null) {
    fun encode() = listOf(sheet.name, day, key.orEmpty(), habit.orEmpty()).joinToString(SEP)

    companion object {
        private const val SEP = "\u001F"

        fun decode(raw: String): SheetOpen? {
            val p = raw.split(SEP)
            val sheet = DaySheet.entries.firstOrNull { it.name == p.getOrNull(0) } ?: return null
            return SheetOpen(sheet, p.getOrNull(1).orEmpty(), p.getOrNull(2)?.ifEmpty { null }, p.getOrNull(3)?.ifEmpty { null })
        }
    }
}

/** The rows a day is drawn from: the phone's own, or an earlier month's read for it. */
sealed interface DaySource {
    data class Ready(val s: AppState) : DaySource
    data object Loading : DaySource
    data class Failed(val retry: () -> Unit) : DaySource
}

private sealed interface MonthLoad {
    data object Loading : MonthLoad
    data object Failed : MonthLoad
    data class Loaded(val deck: DeckData) : MonthLoad
}

/**
 * Meals, habit logs and tasks are on the phone for every day; spends only for
 * this month. A day in an earlier month reads the deck once for that day —
 * the server widens it to the day's month — and keeps it for the session.
 * Everything else about the day is the live state, so a delete or a tick
 * still shows on it.
 */
@Composable
fun rememberDaySource(s: AppState, day: String): DaySource {
    val months = remember { mutableStateMapOf<String, MonthLoad>() }
    var attempt by remember { mutableIntStateOf(0) }
    val month = day.take(7)
    val needsRead = month != s.todayIso.take(7)
    // Keyed on the month and the attempt only: keying on its own state would
    // cancel the read the moment it marks itself loading.
    LaunchedEffect(month, needsRead, attempt) {
        if (needsRead && months[month] !is MonthLoad.Loaded) {
            months[month] = MonthLoad.Loading
            months[month] = try {
                MonthLoad.Loaded(Api.fetchDeckDay(day))
            } catch (e: CancellationException) {
                months.remove(month)
                throw e
            } catch (_: Exception) {
                MonthLoad.Failed
            }
        }
    }
    if (!needsRead) return DaySource.Ready(s)
    return when (val m = months[month]) {
        is MonthLoad.Loaded -> DaySource.Ready(s.copy(tx = m.deck.tx, fixedTx = m.deck.fixedTx))
        MonthLoad.Failed -> DaySource.Failed { attempt++ }
        else -> DaySource.Loading
    }
}
