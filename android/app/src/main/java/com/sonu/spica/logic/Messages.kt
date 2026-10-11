package com.sonu.spica.logic

import com.sonu.spica.data.ChatMsg
import com.sonu.spica.data.ComposeContext
import com.sonu.spica.data.DishRow
import com.sonu.spica.data.Meal
import com.sonu.spica.data.PantryRow
import com.sonu.spica.data.Tx
import com.sonu.spica.lib.Fmt
import com.sonu.spica.ui.theme.C

/**
 * What the agent needs to reason about a log before it is committed, and to
 * build the cards the `+` tray answers with. Port of `agent/messages.ts`.
 */
data class Ledger(
    val tx: List<Tx>,
    val meals: List<Meal>,
    val pantry: List<PantryRow>,
    val dishes: List<DishRow>,
    val today: String,
    val proteinTarget: Double?,
)

object Msgs {
    fun user(text: String, context: ComposeContext? = null) = ChatMsg.User(Fmt.nextId("u"), text, context = context)

    /** A plain agent line — the drawer's stubs, the failure bubble. */
    fun stub(title: String, body: String) = ChatMsg.Agent(Fmt.nextId("a"), title, "", C.brand, body)

    fun paisaHistory(l: Ledger): ChatMsg.Table {
        val rows = l.tx.reversed().take(10)
        return ChatMsg.Table(Fmt.nextId("tb"), "Money · last ${rows.size}", "paisa", rows.map { it.id })
    }

    fun dietLog(l: Ledger): ChatMsg.Table {
        val rows = l.meals.reversed().take(10)
        return ChatMsg.Table(Fmt.nextId("tb"), "Diet log · last ${rows.size}", "diet", rows.map { it.id })
    }

    fun todo(scope: String = "all") = ChatMsg.Todos(Fmt.nextId("td"), scope)

    /** The month from the + menu — the card reads the live figures; nothing is stored on it. */
    fun flow(l: Ledger) = ChatMsg.Flow(Fmt.nextId("fl"))

    /** What is at home — the card reads the same live rows Your data → Pantry shows. */
    fun pantry(l: Ledger) = ChatMsg.Pantry(Fmt.nextId("pn"), "pantry")

    /** Your dishes — tried or saved — read live. */
    fun recipes(l: Ledger) = ChatMsg.Pantry(Fmt.nextId("rc"), "dishes")
}
