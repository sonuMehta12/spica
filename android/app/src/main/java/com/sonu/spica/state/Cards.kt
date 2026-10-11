package com.sonu.spica.state

import com.sonu.spica.data.ChatMsg
import com.sonu.spica.data.ConfirmField
import com.sonu.spica.data.SuggestItem
import com.sonu.spica.data.WireTurn
import com.sonu.spica.logic.Msgs
import com.sonu.spica.ui.theme.C
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.doubleOrNull
import kotlinx.serialization.json.intOrNull

/**
 * The server's cards into the shapes the conversation draws. The wire shapes
 * are kept loose on purpose — they are still moving, and a strict mirror
 * would break on every tweak. Port of `toChatMsg` / `toMessages`.
 */
object Cards {
    private fun JsonObject.str(k: String): String? = (this[k] as? JsonPrimitive)?.takeIf { it !is JsonNull }?.contentOrNull
    private fun JsonObject.num(k: String): Double? = (this[k] as? JsonPrimitive)?.let { it.doubleOrNull ?: it.contentOrNull?.toDoubleOrNull() }
    private fun JsonObject.int(k: String): Int? = (this[k] as? JsonPrimitive)?.let { it.intOrNull ?: it.doubleOrNull?.toInt() }
    private fun JsonObject.bool(k: String): Boolean = (this[k] as? JsonPrimitive)?.booleanOrNull ?: false
    private fun JsonObject.strings(k: String): List<String> =
        (this[k] as? JsonArray)?.mapNotNull { (it as? JsonPrimitive)?.contentOrNull } ?: emptyList()
    private fun JsonObject.objects(k: String): List<JsonObject> = (this[k] as? JsonArray)?.mapNotNull { it as? JsonObject } ?: emptyList()

    /** Unknown kinds return null — the turn then falls back to its text. */
    fun toMsg(c: JsonObject, i: Int, at: String): ChatMsg? {
        val id = "$at-$i"
        return when (c.str("kind")) {
            "agent" -> ChatMsg.Agent(id, "", "", C.ink, c.str("text") ?: "")
            // Ids, not rows: the card resolves them against live data.
            "table" -> ChatMsg.Table(id, c.str("heading") ?: "", c.str("source") ?: "paisa", c.strings("ids"))
            "confirm" -> ChatMsg.Confirm(
                id = id,
                source = c.str("source") ?: "paisa",
                rowId = c.str("row_id"),
                state = c.str("state") ?: "written",
                lede = c.str("lede") ?: "",
                fields = c.objects("fields").map {
                    ConfirmField(it.str("key") ?: "", it.str("label") ?: "", it.str("value") ?: "", it.bool("guessed"))
                },
                unresolved = c.strings("unresolved"),
                needsQuantity = c.strings("needs_quantity"),
            )
            "suggest" -> ChatMsg.Suggest(
                id,
                c.objects("items").map {
                    SuggestItem(
                        type = it.str("type") ?: "dish",
                        ref = it.str("ref") ?: "",
                        name = it.str("name") ?: "",
                        why = it.str("why") ?: "",
                        saved = it.bool("saved"),
                        mealType = it.str("meal_type"),
                        minutes = it.int("minutes"),
                        proteinG = it.num("protein_g"),
                        kcal = it.int("kcal"),
                        imageUrl = it.str("image_url"),
                        missing = it.strings("missing"),
                        exerciseKind = it.str("exercise_kind"),
                        muscleGroup = it.str("muscle_group"),
                        tried = it.int("tried"),
                    )
                },
            )
            "ask" -> ChatMsg.Ask(id, c.str("question") ?: "", c.strings("options"), c.str("pending_row_id"))
            // The live To-do card, as the + menu draws it — minus its own line:
            // the agent's reply above is the text.
            // Live too: no rows ride on it — the card reads the month's commitments from state.
            "commitments" -> ChatMsg.Commitments(id)
            "todos" -> ChatMsg.Todos(id, c.str("scope") ?: "all", c.str("project"), line = false)
            else -> null
        }
    }

    /** Consecutive proposals in one turn become one card that asks them one at a time. */
    fun group(msgs: List<ChatMsg>): List<ChatMsg> = buildList {
        var run = mutableListOf<ChatMsg.Confirm>()
        fun flush() {
            if (run.size >= 2) add(ChatMsg.Review("${run.first().id}-review", run.toList())) else addAll(run)
            run = mutableListOf()
        }
        for (m in msgs) {
            if (m is ChatMsg.Confirm && m.state == "proposed") run += m else {
                flush()
                add(m)
            }
        }
        flush()
    }

    /** One wire turn becomes one or more rendered messages. */
    fun toMessages(turns: List<WireTurn>): List<ChatMsg> = buildList {
        for (t in turns) {
            if (t.role == "user") {
                add(ChatMsg.User(t.id, t.text))
                continue
            }
            val cards = group((t.cards ?: emptyList()).mapIndexedNotNull { i, c -> toMsg(c, i, t.id) })
            // The turn's own id, so the thread can read its day off it.
            if (cards.isNotEmpty()) addAll(cards) else add(Msgs.stub("", t.text).copy(id = t.id))
        }
    }

    fun field(o: JsonObject, k: String): JsonElement? = o[k]
}
