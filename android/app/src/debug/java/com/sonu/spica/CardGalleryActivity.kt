package com.sonu.spica

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.sonu.spica.data.ActivityDay
import com.sonu.spica.data.ChatMsg
import com.sonu.spica.data.ComposeContext
import com.sonu.spica.data.DietGlance
import com.sonu.spica.data.DishRow
import com.sonu.spica.data.ExerciseRow
import com.sonu.spica.data.HabitLine
import com.sonu.spica.data.HabitLogRow
import com.sonu.spica.data.HabitsGlance
import com.sonu.spica.data.HealthAccess
import com.sonu.spica.data.PaisaGlance
import com.sonu.spica.data.PlanExercise
import com.sonu.spica.data.PlanMeal
import com.sonu.spica.data.PlanWorkout
import com.sonu.spica.data.TodayPlan
import com.sonu.spica.data.LimitInfo
import com.sonu.spica.data.Meal
import com.sonu.spica.data.PantryRow
import com.sonu.spica.data.PantryStatus
import com.sonu.spica.data.PendingItem
import com.sonu.spica.data.Profile
import com.sonu.spica.data.HealthSession
import com.sonu.spica.data.Project
import com.sonu.spica.data.TaskKind
import com.sonu.spica.data.Todo
import com.sonu.spica.data.Tx
import com.sonu.spica.data.WeighInRow
import com.sonu.spica.lib.Day
import com.sonu.spica.logic.Chain
import com.sonu.spica.state.Cards
import com.sonu.spica.ui.chat.AgentBubble
import com.sonu.spica.ui.chat.AgentRow
import com.sonu.spica.ui.chat.AskCard
import com.sonu.spica.data.Commitment
import com.sonu.spica.data.CommitmentsPage
import com.sonu.spica.ui.commitments.CommitmentActions
import com.sonu.spica.ui.commitments.CommitmentsCard
import com.sonu.spica.ui.chat.CardWorld
import com.sonu.spica.ui.chat.ConfirmActions
import com.sonu.spica.ui.chat.ConfirmCard
import com.sonu.spica.ui.chat.FlowCard
import com.sonu.spica.ui.chat.PantryCard
import com.sonu.spica.ui.chat.ReviewCard
import com.sonu.spica.ui.chat.RowActions
import com.sonu.spica.ui.chat.SuggestActions
import com.sonu.spica.ui.chat.SuggestCard
import com.sonu.spica.ui.chat.TableCard
import com.sonu.spica.ui.chat.TodoCard
import com.sonu.spica.ui.chat.UserRow
import com.sonu.spica.ui.chat.categoryContext
import com.sonu.spica.ui.chat.liveFor
import com.sonu.spica.ui.chat.reviewContext
import com.sonu.spica.ui.chat.targetContext
import com.sonu.spica.ui.home.Composer
import com.sonu.spica.ui.home.ComposerActions
import com.sonu.spica.ui.home.DietWidget
import com.sonu.spica.ui.home.HabitsWidget
import com.sonu.spica.ui.home.MealsWidget
import com.sonu.spica.ui.home.WorkoutWidget
import com.sonu.spica.ui.home.ActivityWidget
import com.sonu.spica.ui.home.MoneyWidget
import com.sonu.spica.ui.home.TodayWidget
import com.sonu.spica.ui.theme.C
import com.sonu.spica.ui.theme.T
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

/**
 * Debug builds only: every card in the thread, drawn by the same code the
 * conversation uses, from real payloads (copied from the dev chat history)
 * and a few illustrative ones, against sample live rows. Nothing is written.
 *
 *     adb shell am start -n com.sonu.spica/.CardGalleryActivity
 *
 * The door alone: `--es section door`; its film frozen at a millisecond:
 * `--es section door --el film_ms 5250`.
 */
class CardGalleryActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val section = intent.getStringExtra("section")
        // `--el film_ms <ms>` with the door: its film frozen there, to set beside the web's at the same moment.
        val filmMs = if (intent.hasExtra("film_ms")) intent.getLongExtra("film_ms", 0L).toDouble() else null
        setContent { SpicaTheme { Gallery(section, filmMs) } }
    }
}

private val TODAY = Day.today()
private fun ago(n: Int) = Day.addDays(TODAY, -n)
private fun dom(iso: String) = Day.dayOfMonth(iso)

/** Payloads exactly as the server sends them. The ones with real ids are copied from the chat history. */
private val PAYLOADS = """
[
 {"g":"Payment logged — the guess asks in place","card":{"kind":"confirm","lede":"₹20 · Chai","state":"written","fields":[{"key":"amount_paise","label":"Amount","value":"₹20","guessed":false},{"key":"category","label":"Category","value":"food","guessed":true},{"key":"description","label":"What","value":"Chai","guessed":false},{"key":"local_day","label":"Day","value":"${ago(1)}","guessed":false}],"row_id":"01M2K6CQ9JA4DMDDAMMQSE6PFD","source":"paisa","unresolved":[],"needs_quantity":[]}},
 {"g":"Payment removed — a quiet Undo restores it","card":{"kind":"confirm","lede":"₹10,000 · EMI payment","state":"deleted","fields":[{"key":"amount_paise","label":"Amount","value":"₹10,000","guessed":false},{"key":"category","label":"Category","value":"EMI","guessed":false},{"key":"description","label":"What","value":"EMI payment","guessed":false},{"key":"local_day","label":"Day","value":"${ago(18)}","guessed":false}],"row_id":"01M2CHZV40RJ1NVB9W6QJ62CRZ","source":"paisa","unresolved":[],"needs_quantity":[]}},
 {"g":"Money in — read from the live row","card":{"kind":"confirm","lede":"₹40,000 · Salary","state":"written","fields":[{"key":"amount_paise","label":"Amount","value":"₹40,000","guessed":false},{"key":"category","label":"Category","value":"Salary","guessed":false},{"key":"description","label":"What","value":"Salary","guessed":false},{"key":"local_day","label":"Day","value":"$TODAY","guessed":false}],"row_id":"g-salary","source":"paisa","unresolved":[],"needs_quantity":[]}},
 {"g":"Udhaar given","card":{"kind":"confirm","lede":"₹4,000 · Amit ko udhaar","state":"written","fields":[{"key":"amount_paise","label":"Amount","value":"₹4,000","guessed":false},{"key":"category","label":"Category","value":"Logon ko diya","guessed":false},{"key":"description","label":"What","value":"Amit ko udhaar","guessed":false},{"key":"local_day","label":"Day","value":"$TODAY","guessed":false}],"row_id":"g-lent","source":"paisa","unresolved":[],"needs_quantity":[]}},
 {"g":"Udhaar at 0.6 confidence, category guessed — still no guess line","card":{"kind":"confirm","lede":"₹500 · Rohit ko diya","state":"written","fields":[{"key":"amount_paise","label":"Amount","value":"₹500","guessed":false},{"key":"category","label":"Category","value":"Logon ko diya","guessed":true},{"key":"description","label":"What","value":"Rohit ko diya","guessed":false},{"key":"local_day","label":"Day","value":"${ago(6)}","guessed":false}],"row_id":"g-lent2","source":"paisa","unresolved":[],"needs_quantity":[]}},
 {"g":"Udhaar from the new server — category Udhaar, row not held","card":{"kind":"confirm","lede":"₹300 · Amit ko wapas diya","state":"written","fields":[{"key":"amount_paise","label":"Amount","value":"₹300","guessed":false},{"key":"category","label":"Category","value":"Udhaar","guessed":false},{"key":"description","label":"What","value":"Amit ko wapas diya","guessed":false},{"key":"local_day","label":"Day","value":"$TODAY","guessed":false}],"row_id":"g-unheld","source":"paisa","unresolved":[],"needs_quantity":[]}},
 {"g":"Udhaar rows in a table — Lent, Borrowed, Repaid under the name, and out of the lead: ₹20 spent, not ₹4,520","card":{"kind":"table","source":"paisa","heading":"₹4,520 out, ₹3,500 in · 4 rows · 30 days","ids":["01M2K6CQ9JA4DMDDAMMQSE6PFD","g-lent","g-borrow","g-repaid"]}},
 {"g":"Loans alone in a table — no lead line at all, the rows say what they are","card":{"kind":"table","source":"paisa","heading":"₹500 out, ₹2,000 in · 2 rows · 30 days","ids":["g-lent2","g-borrow"]}},
 {"g":"The nightly review — three guesses, one at a time","cards":[
   {"kind":"confirm","lede":"₹40,000 · Ghar par diya (Papa ko) · 80% sure","state":"proposed","fields":[{"key":"category","label":"Category","value":"Logon ko diya","guessed":true},{"key":"why","label":"Why","value":"money given to Papa; round amount may be udhaar","guessed":false},{"key":"local_day","label":"Day","value":"${ago(4)}","guessed":false}],"row_id":"01M18NTA2TY8V2DBW19YY7MG50","source":"paisa","unresolved":[],"needs_quantity":[]},
   {"kind":"confirm","lede":"₹1,200 · Amazon · 60% sure","state":"proposed","fields":[{"key":"category","label":"Category","value":"Shopping","guessed":true},{"key":"why","label":"Why","value":"online order; could be household","guessed":false},{"key":"local_day","label":"Day","value":"${ago(2)}","guessed":false}],"row_id":"g-p2","source":"paisa","unresolved":[],"needs_quantity":[]},
   {"kind":"confirm","lede":"₹486 · Swiggy · 70% sure","state":"proposed","fields":[{"key":"category","label":"Category","value":"Food","guessed":true},{"key":"why","label":"Why","value":"food delivery app","guessed":false},{"key":"local_day","label":"Day","value":"${ago(2)}","guessed":false}],"row_id":"g-p3","source":"paisa","unresolved":[],"needs_quantity":[]}]},
 {"g":"Payments table","card":{"kind":"table","source":"paisa","heading":"₹345 out · 3 payments · 30 days","ids":["01M2K6CQ9JA4DMDDAMMQSE6PFD","g-r1","g-r2"]}},
 {"g":"Meal — macros unknown","card":{"kind":"confirm","lede":"Logged · macros unknown","state":"written","fields":[{"key":"dish","label":"What","value":"3 eggs","guessed":false},{"key":"meal_type","label":"When","value":"Breakfast","guessed":false},{"key":"kcal","label":"Calories","value":"—","guessed":false},{"key":"protein_g","label":"Protein","value":"—","guessed":false}],"row_id":"01M2T4S41H11BRRXMQNY3WCCA0","source":"diet","unresolved":[],"needs_quantity":[]}},
 {"g":"Meal with gaps — each thing said is its own line","card":{"kind":"confirm","lede":"96 g protein left","state":"written","fields":[{"key":"dish","label":"What","value":"2 roti, dal, achaar aur thoda salad","guessed":false},{"key":"meal_type","label":"When","value":"Lunch","guessed":false},{"key":"kcal","label":"Calories","value":"410","guessed":true},{"key":"protein_g","label":"Protein","value":"18 g","guessed":true},{"key":"assumption","label":"Assumed","value":"2 roti ~40g each","guessed":true}],"row_id":"g-m2","source":"diet","unresolved":["achaar"],"needs_quantity":["salad"]}},
 {"g":"Meal with carbs and fat — from the card, then from the live row","cards":[
   {"kind":"confirm","lede":"104 g protein left","state":"written","fields":[{"key":"dish","label":"What","value":"Rajma chawal","guessed":false},{"key":"meal_type","label":"When","value":"Lunch","guessed":false},{"key":"kcal","label":"Calories","value":"520","guessed":false},{"key":"protein_g","label":"Protein","value":"31 g","guessed":false},{"key":"carbs_g","label":"Carbs","value":"60 g","guessed":false},{"key":"fat_g","label":"Fat","value":"14 g","guessed":false}],"row_id":"g-m9","source":"diet","unresolved":[],"needs_quantity":[]},
   {"kind":"confirm","lede":"92 g protein left","state":"written","fields":[{"key":"dish","label":"What","value":"Oats + whey + banana + flaxseed","guessed":false},{"key":"meal_type","label":"When","value":"Breakfast","guessed":false},{"key":"kcal","label":"Calories","value":"560","guessed":false},{"key":"protein_g","label":"Protein","value":"43 g","guessed":false}],"row_id":"g-m1","source":"diet","unresolved":[],"needs_quantity":[]}]},
 {"g":"Meal removed — Undo restores it, then it is a plain receipt","card":{"kind":"confirm","lede":"4 eggs, 2 brown-bread slices aur 1 bowl dahi · deleted","state":"deleted","fields":[{"key":"dish","label":"What","value":"4 eggs, 2 brown-bread slices aur 1 bowl dahi","guessed":false},{"key":"meal_type","label":"When","value":"Breakfast","guessed":false},{"key":"local_day","label":"Day","value":"${ago(17)}","guessed":false}],"row_id":"01M2CCJF0BYS2A3KRYWE59SQTC","source":"diet","unresolved":[],"needs_quantity":[]}},
 {"g":"Diet table","card":{"kind":"table","source":"diet","heading":"61 g protein · 2 meals","ids":["g-m1","g-m2"]}},
 {"g":"Dish suggestions","card":{"kind":"suggest","items":[{"ref":"dish-soya-keema","why":"cookable now · had 1× · 16 days ago","kcal":380,"name":"Dhaba-style soya keema","type":"dish","saved":false,"tried":null,"minutes":20,"missing":[],"image_url":null,"meal_type":"Dinner","protein_g":33.0,"muscle_group":null,"exercise_kind":null},{"ref":"dish-paneer-bhurji","why":"missing capsicum · had 3×","kcal":320,"name":"Paneer bhurji","type":"dish","saved":true,"minutes":15,"missing":["capsicum"],"image_url":null,"meal_type":"Dinner","protein_g":24.0}]}},
 {"g":"Pantry stock","card":{"kind":"confirm","lede":"700 g Paneer left","state":"written","fields":[{"key":"food","label":"Food","value":"Paneer","guessed":false},{"key":"quantity","label":"Moved","value":"200 g","guessed":false},{"key":"kind","label":"Kind","value":"bought","guessed":false}],"row_id":"g-pm","source":"pantry","unresolved":[],"needs_quantity":[]}},
 {"g":"Dish saved","card":{"kind":"confirm","lede":"Saved · Paneer bhurji","state":"written","fields":[{"key":"name","label":"Dish","value":"Paneer bhurji","guessed":false}],"row_id":"dish-paneer-bhurji","source":"diet","unresolved":[],"needs_quantity":[]}},
 {"g":"Habit ticked — the count, not \"Ticked\"","card":{"kind":"confirm","lede":"1 habit ticked","state":"written","fields":[{"key":"habit:Cigarettes","label":"Cigarettes","value":"Ticked","guessed":false}],"row_id":null,"source":"body","unresolved":[],"needs_quantity":[]}},
 {"g":"Sleep and weight","card":{"kind":"confirm","lede":"6 h 30 m sleep · 71.2 kg","state":"written","fields":[{"key":"sleep_hours","label":"Sleep","value":"6 h 30 m","guessed":false},{"key":"weight_kg","label":"Weight","value":"71.2 kg","guessed":false}],"row_id":"g-day","source":"body","unresolved":[],"needs_quantity":[]}},
 {"g":"Habit started","card":{"kind":"confirm","lede":"Cigarettes · tracking break","state":"written","fields":[{"key":"name","label":"Habit","value":"Cigarettes","guessed":false},{"key":"direction","label":"Aim","value":"break","guessed":false}],"row_id":"g-h1","source":"body","unresolved":[],"needs_quantity":[]}},
 {"g":"Habit stopped","card":{"kind":"confirm","lede":"Daily habit · no longer tracked","state":"deleted","fields":[{"key":"name","label":"Habit","value":"Daily habit","guessed":false}],"row_id":"01M2JC3Y2RRPQ71EDS2SYK5AGA","source":"body","unresolved":[],"needs_quantity":[]}},
 {"g":"Exercise done","card":{"kind":"confirm","lede":"Goblet squat · 3×","state":"written","fields":[{"key":"name","label":"Exercise","value":"Goblet squat","guessed":false}],"row_id":"g-ex","source":"body","unresolved":[],"needs_quantity":[]}},
 {"g":"Workout suggestions","card":{"kind":"suggest","items":[{"type":"exercise","ref":"g-ex","name":"Goblet squat","why":"strength · legs · dumbbell · done 3×","minutes":10,"exercise_kind":"strength","muscle_group":"legs","tried":3,"saved":false,"image_url":null},{"type":"exercise","ref":"g-ex2","name":"Walking lunges","why":"strength · legs · not tried yet","minutes":8,"exercise_kind":"strength","muscle_group":"legs","tried":0,"saved":false,"image_url":null}]}},
 {"g":"Task added — the card is the task, and one tap takes it back","card":{"kind":"confirm","lede":"DB migration par kaam karna · added","state":"written","fields":[{"key":"project","label":"Project","value":"PersonaOS","guessed":true},{"key":"due","label":"Due","value":"${Day.addDays(TODAY, 1)}","guessed":false}],"row_id":"g-t1","source":"work","unresolved":[],"needs_quantity":[]}},
 {"g":"Already on the list — the task, no Undo","card":{"kind":"confirm","lede":"Finish the Render deploy spec · already on the list","state":"written","fields":[{"key":"project","label":"Project","value":"PersonaOS","guessed":false},{"key":"due","label":"Due","value":"$TODAY","guessed":false}],"row_id":"g-t5","source":"work","unresolved":[],"needs_quantity":[]}},
 {"g":"To-do from the agent — PersonaOS only, its reply is the text","cards":[
   {"kind":"agent","text":"Two open on PersonaOS — the deploy spec is due today, the migration tomorrow."},
   {"kind":"todos","scope":"all","project":"personaos"}]},
 {"g":"Task done — the one thing left, as its own line","card":{"kind":"confirm","lede":"By default we should show 3 recipes, currently we are showing 6 · done","state":"written","fields":[{"key":"project","label":"Project","value":"Kestrel","guessed":false},{"key":"move_in","label":"Next","value":"move ACM-119 forward in Linear","guessed":false}],"row_id":"g-t2","source":"work","unresolved":[],"needs_quantity":[]}},
 {"g":"Project created","card":{"kind":"confirm","lede":"Kestrel · created","state":"written","fields":[{"key":"name","label":"Project","value":"Kestrel","guessed":false}],"row_id":"g-proj","source":"work","unresolved":[],"needs_quantity":[]}},
 {"g":"Commitment made — Category guessed (amber), Change attaches it to the composer","card":{"kind":"confirm","lede":"Gym · ₹1,500 · every month","state":"written","fields":[{"key":"name","label":"Commitment","value":"Gym","guessed":false},{"key":"amount_paise","label":"Amount","value":"₹1,500","guessed":false},{"key":"category","label":"Category","value":"Subscriptions","guessed":true},{"key":"due_day","label":"Due","value":"the 5th","guessed":false},{"key":"repeats","label":"Repeats","value":"every month","guessed":false}],"row_id":"g-c1","source":"commitment","unresolved":[],"needs_quantity":[]}},
 {"g":"Commitment deleted — history, no tray","card":{"kind":"confirm","lede":"Gym · deleted","state":"deleted","fields":[{"key":"name","label":"Commitment","value":"Gym","guessed":false},{"key":"payments","label":"Payments","value":"1 payment now counts as spending","guessed":false}],"row_id":"g-c1","source":"commitment","unresolved":[],"needs_quantity":[]}},
 {"g":"Commitments — live, no rows on the wire","cards":[
   {"kind":"agent","text":"₹61,421 owed across 4 lines."},
   {"kind":"commitments"}]},
 {"g":"Memory saved","card":{"kind":"confirm","lede":"Remembered","state":"written","fields":[{"key":"text","label":"reference","value":"Money log delete nahi kar pa raha; wrong entries (jaise egg roll) directly delete nahi hoti.","guessed":false}],"row_id":"01M2BGN1WDE830DTEZ0S1N6KRW","source":"memory","unresolved":[],"needs_quantity":[]}},
 {"g":"Profile target","card":{"kind":"confirm","lede":"Savings target → ₹10,000","state":"written","fields":[{"key":"savings_target_paise","label":"Savings target","value":"₹10,000","guessed":false}],"row_id":null,"source":"profile","unresolved":[],"needs_quantity":[]}},
 {"g":"A person filed","card":{"kind":"confirm","lede":"Mohan Lal · friend","state":"written","fields":[{"key":"relation","label":"Relation","value":"friend","guessed":false},{"key":"kind","label":"Kind","value":"person","guessed":false}],"row_id":"g-per","source":"people","unresolved":[],"needs_quantity":[]}},
 {"g":"A place pinned","card":{"kind":"confirm","lede":"Blue Tokai · eat","state":"written","fields":[{"key":"kind","label":"Kind","value":"eat","guessed":false},{"key":"payments","label":"Payments","value":"6 payments","guessed":false},{"key":"spent","label":"Spent","value":"₹1,840","guessed":false}],"row_id":"g-pl","source":"places","unresolved":[],"needs_quantity":[]}},
 {"g":"A question back (the server never sends this yet)","card":{"kind":"ask","question":"₹500 to Rohit, yesterday. Is it coming back?","options":["Udhaar","Spent"],"pending_row_id":null}}
]
"""

private val WORLD = CardWorld(
    tx = listOf(
        Tx("01M2K6CQ9JA4DMDDAMMQSE6PFD", dom(ago(1)), "Chai", "food", 20, date = ago(1), confidence = 0.7),
        Tx("g-r1", dom(ago(3)), "Rapido ride", "Transport", 65, date = ago(3), confidence = 1.0),
        Tx("g-r2", dom(ago(5)), "Rapido", "Transport", 260, date = ago(5), confidence = 1.0),
        Tx("g-salary", dom(TODAY), "Salary", "Salary", 40000, credit = true, date = TODAY, confidence = 1.0, kind = "income"),
        Tx("g-lent", dom(TODAY), "Amit ko udhaar", "Logon ko diya", 4000, date = TODAY, confidence = 1.0, kind = "lent"),
        // Udhaar fetched by id: an old guess on the lending, a borrowing, a repayment.
        Tx("g-lent2", dom(ago(6)), "Rohit ko diya", "Logon ko diya", 500, date = ago(6), confidence = 0.6, kind = "lent"),
        Tx("g-borrow", dom(ago(8)), "Amit se liya", "Udhaar", 2000, credit = true, date = ago(8), confidence = 1.0, kind = "borrowed"),
        Tx("g-repaid", dom(ago(2)), "Amit se wapas aaya", "Udhaar", 1500, credit = true, date = ago(2), confidence = 1.0, kind = "repayment"),
        Tx("01M18NTA2TY8V2DBW19YY7MG50", dom(ago(4)), "Ghar par diya (Papa ko)", "Other", 40000, date = ago(4), confidence = 0.5),
        Tx("g-p2", dom(ago(2)), "Amazon", "Other", 1200, date = ago(2), confidence = 0.5),
        Tx("g-p3", dom(ago(2)), "Swiggy", "Other", 486, date = ago(2), confidence = 0.5),
    ),
    meals = listOf(
        Meal("01M2T4S41H11BRRXMQNY3WCCA0", dom(TODAY), "3 eggs", "Breakfast", 0.0, 0, date = TODAY, confidence = 1.0),
        Meal("g-m1", dom(TODAY), "Oats + whey + banana + flaxseed", "Breakfast", 43.0, 560, c = 72.0, f = 14.5, date = TODAY, confidence = 1.0),
        Meal("g-m2", dom(TODAY), "2 roti, dal, achaar aur thoda salad", "Lunch", 18.0, 410, date = TODAY, confidence = 0.6),
    ),
    todos = listOf(
        Todo("g-t1", "DB migration par kaam karna", false, TaskKind.Work, project = "p-os", projectGuessed = true, due = Day.addDays(TODAY, 1)),
        Todo("g-t2", "By default we should show 3 recipes, currently we are showing 6", true, TaskKind.Work, doneOn = TODAY, project = "p-kestrel", link = "https://linear.app", tracked = true, origin = "Linear", awaitingMove = true),
        Todo("g-t3", "Delete the ACM-223 test issue in Linear", false, TaskKind.Work, project = "p-bun", due = ago(3)),
        Todo("g-t4", "Fix the catalog sync bug", false, TaskKind.Work, project = "p-any", due = ago(2), priority = 1),
        Todo("g-t5", "Finish the Render deploy spec", false, TaskKind.Work, project = "p-os", due = TODAY),
        Todo("g-t6", "Replace the Google Sheet with the DB", false, TaskKind.Work, project = "p-any"),
    ),
    projects = listOf(
        Project(id = "p-os", name = "PersonaOS", color = "#418AD1"),
        Project(id = "p-kestrel", name = "Kestrel", color = "#C16E2D"),
        Project(id = "p-bun", name = "Acme", color = "#732F67"),
        Project(id = "p-any", name = "NovaCart-chan", color = "#239D6A"),
        Project(id = "g-proj", name = "Kestrel", color = "#C16E2D"),
    ),
    habitLogs = listOf(
        HabitLogRow("hl1", dom(TODAY), TODAY, "Cigarettes", 2.0),
        HabitLogRow("hl2", dom(ago(1)), ago(1), "Cigarettes", 3.0),
        HabitLogRow("hl3", dom(ago(2)), ago(2), "Cigarettes", 4.0),
    ),
    exercises = listOf(ExerciseRow("g-ex", "Goblet squat", emptyList(), "strength", "legs", "dumbbell", 10, null, null, null, "library", null, 3, TODAY)),
    dishes = listOf(
        DishRow("dish-paneer-bhurji", "Paneer bhurji", emptyList(), "Dinner", "1 bowl", 320, 24.0, null, null, 15, false, null, emptyList(), null, null, null, true, true, 3, ago(6), emptyList()),
    ),
    pending = listOf(PendingItem("g-lent", "lent", "Amit ko udhaar", 4000, 4000, TODAY, dom(TODAY))),
    weighIns = listOf(WeighInRow("w1", TODAY, 71.2), WeighInRow("w0", ago(3), 71.6)),
    profile = Profile(proteinTarget = 135.0, kcalTarget = 2000, sleepTargetMin = 450, savingsTarget = 10000),
    today = TODAY,
    deletedRows = emptyList(),
    weighInsLoaded = true,
)

/** Pantry rows in every state the card groups by. */
private val SAMPLE_PANTRY = listOf(
    PantryRow("pr1", "f1", "Bread", 200.0, null, 4, null, false, "g", 0, ago(6), 400.0, PantryStatus.Stale),
    PantryRow("pr2", "f2", "Dahi", 150.0, 200.0, 3, null, false, "g", 0, ago(2), 500.0, PantryStatus.Soon),
    PantryRow("pr3", "f3", "Eggs", 0.0, 4.0, null, null, false, "piece", 0, ago(5), 12.0, PantryStatus.Out),
    PantryRow("pr4", "f4", "Paneer", 700.0, 200.0, 7, null, false, "g", 0, TODAY, 200.0, PantryStatus.Ok),
    PantryRow("pr5", "f5", "Oats", 400.0, 100.0, null, null, false, "g", 0, ago(10), 1000.0, PantryStatus.Ok),
    PantryRow("pr6", "f6", "Salt", 0.0, null, null, null, true, "g", 0, null, null, PantryStatus.Staple),
)

private val NOOP_CONFIRM = ConfirmActions(
    onContext = {}, onConfirm = {}, onEdit = { _, _, _ -> }, onDelete = {}, onRestore = {}, onDeleteTask = {},
    onToggleTodo = {},
)
private val NOOP_ROWS = RowActions(null, {}, { _, _ -> }, { _, _, _ -> })
private val NOOP_COMMITMENTS = CommitmentActions({}, {}, {}, {}, {}, {})

/** The ledger's four rolled lines, one part-paid, one carried, one skipped, one borrowing — every state the card draws. */
private val SAMPLE_COMMITMENTS = CommitmentsPage(
    month = "${TODAY.take(7)}-01", editable = true, owed = 62471, pool = 69636, savingsTarget = 0, limit = -3799, daysLeft = 21, paidCount = 1, openCount = 5,
    items = listOf(
        Commitment("g-c1", "Ghar", "commitment", "rolled", "Ghar", 40000, 0, 40000, 0, false, false, 1, true, true, 0, null),
        Commitment("g-c2", "EMI", "commitment", "manual", "EMI", 10000, 0, 10000, 0, false, false, 5, true, false, 0, null),
        Commitment("g-c3", "Health/Diet", "commitment", "manual", "Health/Diet", 2000, 50, 1950, 0, false, false, null, true, false, 1, null),
        Commitment("g-c4", "Rent", "commitment", "carried", "Rent", 4000, 0, 4000, 0, false, false, null, false, false, 0, "${Day.addDays(TODAY, -40).take(7)}-01"),
        Commitment("g-c5", "Subscriptions", "commitment", "rolled", "Subscriptions", 3000, 3000, 0, 0, true, false, 7, true, true, 1, null),
        Commitment("g-b1", "Dost ka udhaar", "borrowing", "borrowing", "Udhaar", 6000, 0, 6000, 0, false, false, null, false, false, 0, null),
        Commitment("g-c6", "Gym", "commitment", "manual", "Subscriptions", 1500, 0, 0, 0, false, true, 3, true, false, 0, null),
    ),
)
private val NOOP_SUGGEST = SuggestActions(null, {}, {}, { _, _ -> }, { _, _ -> })
private val NOOP_COMPOSER = ComposerActions({}, {}, {}, {}, {}, {}, {})

/** One card from a payload, as the thread would build it. */
private fun card(json: String): ChatMsg = Cards.toMsg(Json.parseToJsonElement(json).jsonObject, 0, "local-${json.hashCode()}")!!

/** The Chai payment, deleted this session: in `deletedRows`, its row still live in the deck. */
private val CHAI_GONE = WORLD.copy(deletedRows = listOf("01M2K6CQ9JA4DMDDAMMQSE6PFD"))

/** The added task, taken back with its Undo: gone from the list, struck on its card. */
private val TASK_GONE = WORLD.copy(todos = WORLD.todos.filter { it.id != "g-t1" }, deletedRows = listOf("g-t1"))

/** Nobody has set a protein target yet. */
private val NO_TARGET = WORLD.copy(profile = WORLD.profile.copy(proteinTarget = null))

/** A week of habits on Home, named as the main account names them: two built by the day, two counted. */
private val HABIT_LOGS = listOf(
    HabitLogRow("w1", dom(ago(3)), ago(3), "Workout", null),
    HabitLogRow("w2", dom(ago(1)), ago(1), "Workout", null),
    HabitLogRow("w3", dom(TODAY), TODAY, "Workout", null),
    HabitLogRow("c1", dom(ago(3)), ago(3), "Cigarettes", 3.0),
    HabitLogRow("c2", dom(ago(2)), ago(2), "Cigarettes", 2.0),
    HabitLogRow("c3", dom(ago(1)), ago(1), "Cigarettes", 1.0),
    HabitLogRow("c4", dom(TODAY), TODAY, "Cigarettes", 2.0),
    HabitLogRow("m1", dom(ago(2)), ago(2), "Meditation", null),
    HabitLogRow("b1", dom(ago(2)), ago(2), "Alcohol", 2.0),
)
private val HABIT_LINES = listOf(
    HabitLine("Workout", counted = false), HabitLine("Cigarettes", counted = true),
    HabitLine("Meditation", counted = false), HabitLine("Alcohol", counted = true),
)

/** Today's plan as the server sends it, with real Commons pictures. */
private const val COMMONS = "https://thumb.wikimedia.org/wikipedia/commons/thumb"
private val PLAN = TodayPlan(
    available = true, done = false, proteinTarget = 120.0, kcalTarget = 2000,
    loggedProtein = 30.0, loggedKcal = 600, plannedProtein = 88.0, plannedKcal = 1290,
    meals = listOf(
        PlanMeal("Lunch", "dish-rajma", "Rajma chawal", 520, 22.0, 80.0, 11.0, "22 g protein; rajma is soaked and in", false,
            "$COMMONS/6/6e/Rajma_Chawal_Rajma_Rice.jpg/960px-Rajma_Chawal_Rajma_Rice.jpg", "Photo: Sayanilive, CC BY-SA 4.0 · Wikimedia Commons"),
        PlanMeal("Snack", null, "Whey shake with banana", 220, 26.0, 28.0, 3.0, "26 g protein in two minutes", true, null, null),
        PlanMeal("Dinner", null, "Paneer bhurji with two rotis", 550, 40.0, 42.0, 24.0, "40 g closes the day", true,
            "$COMMONS/f/fe/Homemade_Paneer_Bhurji_cooked_in_pan_India.jpg/960px-Homemade_Paneer_Bhurji_cooked_in_pan_India.jpg",
            "Photo: Status 401, CC BY-SA 4.0 · Wikimedia Commons"),
    ),
    workout = PlanWorkout(
        "gym", "Legs", 40, "Two runs this week, no legs since Monday",
        listOf(PlanExercise("ex-1", "Goblet squat", "3 × 10", false), PlanExercise("ex-2", "Walking lunges", "3 × 12", false),
            PlanExercise(null, "Romanian deadlift", "3 × 8", true)),
        false, null, null,
    ),
)
private val RUN = PlanWorkout(
    "run", "Easy run", 30, "Legs yesterday; something light", emptyList(), true,
    "$COMMONS/f/fb/Morning_jogging_session.jpg/960px-Morning_jogging_session.jpg", "Photo: Adewuyi Israel, CC BY-SA 4.0 · Wikimedia Commons",
)

/** The removed breakfast, after its Undo: the restore route handed the row back, live. */
private val RESTORED = WORLD.copy(
    meals = WORLD.meals + Meal("01M2CCJF0BYS2A3KRYWE59SQTC", dom(ago(17)), "4 eggs, 2 brown-bread slices aur 1 bowl dahi", "Breakfast", 41.0, 520, c = 38.0, f = 22.0, date = ago(17), confidence = 1.0),
)

private sealed interface Entry {
    val label: String
    data class Server(override val label: String, val msgs: List<ChatMsg>) : Entry
    data class Local(override val label: String, val draw: @Composable () -> Unit) : Entry
}

private fun entries(): List<Entry> {
    val parsed = Json.parseToJsonElement(PAYLOADS).jsonArray.mapIndexed { i, el ->
        val o = el.jsonObject
        val label = o["g"]!!.jsonPrimitive.content
        val cards = (o["cards"]?.jsonArray?.map { it.jsonObject } ?: listOf(o["card"]!!.jsonObject))
        Entry.Server(label, Cards.group(cards.mapIndexedNotNull { j, c -> Cards.toMsg(c as JsonObject, j, "g$i") }))
    }
    val chai = card("""{"kind":"confirm","lede":"₹20 · Chai","state":"written","fields":[{"key":"amount_paise","label":"Amount","value":"₹20","guessed":false},{"key":"category","label":"Category","value":"food","guessed":true},{"key":"description","label":"What","value":"Chai","guessed":false},{"key":"local_day","label":"Day","value":"${ago(1)}","guessed":false}],"row_id":"01M2K6CQ9JA4DMDDAMMQSE6PFD","source":"paisa"}""")
    val payments = card("""{"kind":"table","source":"paisa","heading":"₹345 out · 3 payments · 30 days","ids":["01M2K6CQ9JA4DMDDAMMQSE6PFD","g-r1","g-r2"]}""")
    val task = card("""{"kind":"confirm","lede":"DB migration par kaam karna · added","state":"written","fields":[{"key":"project","label":"Project","value":"PersonaOS","guessed":true},{"key":"due","label":"Due","value":"${Day.addDays(TODAY, 1)}","guessed":false}],"row_id":"g-t1","source":"work"}""")
    val removedMeal = card("""{"kind":"confirm","lede":"4 eggs, 2 brown-bread slices aur 1 bowl dahi · deleted","state":"deleted","fields":[{"key":"dish","label":"What","value":"4 eggs, 2 brown-bread slices aur 1 bowl dahi","guessed":false},{"key":"meal_type","label":"When","value":"Breakfast","guessed":false},{"key":"local_day","label":"Day","value":"${ago(17)}","guessed":false}],"row_id":"01M2CCJF0BYS2A3KRYWE59SQTC","source":"diet"}""")
    val yesterdayMeal = card("""{"kind":"confirm","lede":"18 g protein logged","state":"written","fields":[{"key":"dish","label":"What","value":"Dal ek katori","guessed":false},{"key":"meal_type","label":"When","value":"Lunch","guessed":false},{"key":"kcal","label":"Calories","value":"195","guessed":true},{"key":"protein_g","label":"Protein","value":"12 g","guessed":true},{"key":"local_day","label":"Day","value":"${ago(2)}","guessed":false}],"row_id":"g-m8","source":"diet"}""")
    val breakfast = card("""{"kind":"confirm","lede":"Logged","state":"written","fields":[{"key":"dish","label":"What","value":"Oats + whey + banana + flaxseed","guessed":false},{"key":"meal_type","label":"When","value":"Breakfast","guessed":false},{"key":"kcal","label":"Calories","value":"560","guessed":false},{"key":"protein_g","label":"Protein","value":"43 g","guessed":false}],"row_id":"g-m1","source":"diet"}""")
    val week = Chain.weekChain(HABIT_LOGS, TODAY)
    val home = listOf(
        Entry.Local("Home · Today — three tasks, the most pressing first") {
            TodayWidget(WORLD.todos, WORLD.projects, TODAY, {}, {}, {})
        },
        Entry.Local("Home · Today — nothing on the list") {
            TodayWidget(emptyList(), WORLD.projects, TODAY, {}, {}, {})
        },
        Entry.Local("Home · Money — within today's limit") {
            MoneyWidget(PaisaGlance(1470, 345, 90000, 46031, 12400, 10000, 8000, 4500, 2), {}, {})
        },
        Entry.Local("Home · Money — over today, out past in, saving under target") {
            MoneyWidget(PaisaGlance(600, 780, 40000, 43500, 6200, 10000, 0, 0, 0), {}, {})
        },
        Entry.Local("Home · Money — before the limit lands, nothing in yet, no target") {
            MoneyWidget(PaisaGlance(null, 120, 0, 3200, null, 0, null, 4000, 1), {}, {})
        },
        Entry.Local("Home · Diet — protein against its target") {
            DietWidget(DietGlance(61.0, 135.0, 1240.0, 2200, 160.0, 250.0, 38.0, 2), {}, {})
        },
        Entry.Local("Home · Diet — target met, calories over theirs") {
            DietWidget(DietGlance(142.0, 135.0, 2450.0, 2200, 210.0, null, 71.5, 4), {}, {})
        },
        Entry.Local("Home · Diet — no target yet, carbs and fat unknown") {
            DietWidget(DietGlance(18.0, null, 410.0, null, null, null, null, 1), {}, {})
        },
        Entry.Local("Home · Activity — connected, a week of runs and rides") {
            ActivityWidget(HealthAccess.Granted, ActivityDay(6240, 312.0, listOf(
                HealthSession("Running", 31, ago(3)), HealthSession("Running", 24, ago(1)), HealthSession("Cycling", 40, ago(2)), HealthSession("Strength", 45, TODAY),
            ))) {}
        },
        Entry.Local("Home · Activity — connected, nothing recorded today") {
            ActivityWidget(HealthAccess.Granted, ActivityDay(null, null, emptyList())) {}
        },
        Entry.Local("Home · Activity — not connected, and not on this phone") {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                ActivityWidget(HealthAccess.NotGranted, null) {}
                ActivityWidget(HealthAccess.Unavailable, null) {}
            }
        },
        Entry.Local("Home · Meals — the rest of today, a library dish and an idea") {
            MealsWidget(PLAN, false, emptyList(), {}, {}, {})
        },
        Entry.Local("Home · Meals — one logged, the idea saved; and planning, and could not") {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                MealsWidget(PLAN, true, listOf("meal:Lunch", "save:Dinner"), {}, {}, {})
                MealsWidget(null, true, emptyList(), {}, {}, {})
                MealsWidget(PLAN.copy(available = false, meals = emptyList(), workout = null), false, emptyList(), {}, {}, {})
            }
        },
        Entry.Local("Home · Meals — the day's meals are done") {
            MealsWidget(PLAN.copy(done = true, meals = emptyList(), loggedKcal = 1940, loggedProtein = 118.0), false, emptyList(), {}, {}, {})
        },
        Entry.Local("Home · Workout — a gym session from the library, and a run") {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                WorkoutWidget(PLAN, false, false, {}, {})
                WorkoutWidget(PLAN.copy(workout = RUN), false, true, {}, {})
                WorkoutWidget(PLAN.copy(workout = RUN.copy(kind = "rest", name = "Rest", minutes = null, why = "Three hard days in a row", imageUrl = null, imageCredit = null)), false, false, {}, {})
            }
        },
        Entry.Local("Home · Habits — built by the day, counted by the number") {
            HabitsWidget(HabitsGlance(HABIT_LINES, week)) {}
        },
        Entry.Local("Home · Habits — none tracked") {
            HabitsWidget(HabitsGlance(emptyList(), week)) {}
        },
    )
    val local = listOf(
        Entry.Local("Chai deleted this session — the receipt says Removed with an Undo; the table strikes it, out of the total") {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Draw(chai, CHAI_GONE)
                Draw(payments, CHAI_GONE)
            }
        },
        Entry.Local("Every row of a table deleted — struck, and the caption says no payments yet") {
            Draw(payments, WORLD.copy(deletedRows = listOf("01M2K6CQ9JA4DMDDAMMQSE6PFD", "g-r1", "g-r2")))
        },
        Entry.Local("Born deleted, then restored — the same card is a plain receipt again") { Draw(removedMeal, RESTORED) },
        Entry.Local("Task undone — the card is the task, struck: Removed") { Draw(task, TASK_GONE) },
        Entry.Local("Protein with no target yet — the line offers one") { Draw(breakfast, NO_TARGET) },
        Entry.Local("An estimate from another day — its Change names the day, not today") { Draw(yesterdayMeal, WORLD) },
        Entry.Local("Composer with a context — the pill above the input, inside the bar") {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Composer(
                    typed = "", focusKey = 0, composing = true, canLog = true, hint = null,
                    editing = null, a = NOOP_COMPOSER,
                    context = categoryContext("Auto", "₹80", TODAY),
                )
                Composer(
                    typed = "transport", focusKey = 0, composing = true, canLog = true, hint = null,
                    editing = null, a = NOOP_COMPOSER,
                    context = reviewContext("Ghar par diya (Papa ko)", "₹40,000", ago(4)),
                )
            }
        },
        Entry.Local("Your words, sent with a context — its label on a faint line above") {
            Column {
                UserRow("transport", context = categoryContext("Auto", "₹80", TODAY).label)
                UserRow("10,000", context = targetContext("Savings target", "₹10,000").label)
            }
        },
        Entry.Local("To-do (+ menu) — its line above the card") { TodoCard(WORLD.todos, "all", WORLD.projects, TODAY) {} },
        Entry.Local("Pantry (+ menu) — sample rows") { PantryCard(ChatMsg.Pantry("pn", "pantry"), SAMPLE_PANTRY, WORLD.dishes, TODAY) },
        Entry.Local("Recipes (+ menu)") { PantryCard(ChatMsg.Pantry("rc", "dishes"), SAMPLE_PANTRY, WORLD.dishes, TODAY) },
        Entry.Local("Cash flow (+ menu) — ₹40,000 in, ₹22,085 gone, ₹10,000 committed") {
            FlowCard(LimitInfo(264, 0, 7915, 17915, 10000, 22000, 30), 40000, WORLD.pending, TODAY)
        },
        Entry.Local("Empty + menu cards — only their line") {
            Column {
                PantryCard(ChatMsg.Pantry("pn0", "pantry"), emptyList(), emptyList(), TODAY)
                PantryCard(ChatMsg.Pantry("rc0", "dishes"), emptyList(), emptyList(), TODAY)
                FlowCard(LimitInfo(0, 0, 0, 0, 0, 0, 30), 0, emptyList(), TODAY)
            }
        },
        Entry.Local("A send that failed — marked on your own message") { UserRow("chai 20", failed = "Didn't reach the server.") {} },
        Entry.Local("The agent's text stands alone; the card below holds data") {
            Column {
                AgentBubble(ChatMsg.Agent("a", "", "", C.ink, "₹1,470 left for today."))
            }
        },
    )
    return home + parsed + local
}

@Composable
private fun Gallery(section: String?, filmMs: Double?) {
    // The door, alone — to see it without signing out. Its button is never pressed here.
    if (section == "door") {
        com.sonu.spica.ui.door.Door(onSignedIn = {}, filmAt = filmMs)
        return
    }
    val all = entries()
    val list = rememberLazyListState()
    // Each entry is a label row then its cards; the title is item 0.
    LaunchedEffect(section) {
        if (section == null) return@LaunchedEffect
        var index = 1
        for (e in all) {
            if (e.label.contains(section, ignoreCase = true)) break
            index += 1 + if (e is Entry.Server) e.msgs.size else 1
        }
        list.scrollToItem(index)
    }
    // A card's Change lands here as it would in the composer, with the
    // sentence the agent would be sent printed above it. Nothing is sent.
    var context by remember { mutableStateOf<ComposeContext?>(null) }
    val actions = remember { ConfirmActions(
        onContext = { context = it }, onConfirm = {}, onEdit = { _, _, _ -> }, onDelete = {}, onRestore = {}, onDeleteTask = {},
        onToggleTodo = {},
    ) }
    Box(Modifier.fillMaxSize().background(C.paper)) {
        CompositionLocalProvider(LocalActions provides actions) {
            LazyColumn(
                Modifier.fillMaxSize().statusBarsPadding(),
                state = list,
                contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 16.dp, bottom = 220.dp),
            ) {
                item { Text("Card gallery · debug", style = T.display.copy(fontSize = 22.sp), modifier = Modifier.padding(bottom = 16.dp)) }
                all.forEachIndexed { i, e ->
                    item(key = "label-$i") { Text(e.label, style = T.sans.copy(fontSize = 12.sp, color = C.faint), modifier = Modifier.padding(top = 18.dp, bottom = 8.dp)) }
                    when (e) {
                        is Entry.Local -> item(key = "card-$i") { AgentRow(gap = 4.dp) { e.draw() } }
                        is Entry.Server -> e.msgs.forEachIndexed { j, m ->
                            item(key = "card-$i-$j") { AgentRow(gap = 8.dp) { Draw(m, WORLD) } }
                        }
                    }
                }
            }
        }
        context?.let { c ->
            Column(Modifier.align(Alignment.BottomCenter).fillMaxWidth()) {
                Text(
                    "Sends: ${c.prefix} …",
                    style = T.sans.copy(fontSize = 12.sp, color = C.muted),
                    modifier = Modifier.fillMaxWidth().background(C.surface).padding(horizontal = 16.dp, vertical = 8.dp),
                )
                Composer(
                    typed = "", focusKey = 0, composing = true, canLog = true, hint = null,
                    editing = null,
                    a = ComposerActions({}, {}, {}, {}, {}, {}) { context = null }, context = c,
                )
            }
        }
    }
}

/** What the gallery's cards do when tapped — only a Change does anything, and nothing is written. */
private val LocalActions = staticCompositionLocalOf { NOOP_CONFIRM }

/** A message as the conversation draws it, against the given live rows. */
@Composable
private fun Draw(m: ChatMsg, w: CardWorld) {
    when (m) {
        is ChatMsg.Confirm -> ConfirmCard(m, liveFor(m, w.tx, w.meals, w.deletedRows), w, LocalActions.current)
        is ChatMsg.Review -> ReviewCard(m.items, { liveFor(it, w.tx, w.meals, w.deletedRows) }, w, LocalActions.current)
        is ChatMsg.Table -> TableCard(m, w.tx, w.meals, w.deletedRows, NOOP_ROWS, w.profile.proteinTarget) { _, _ -> }
        is ChatMsg.Todos -> TodoCard(w.todos, m.scope, w.projects, TODAY, m.project, m.line) {}
        is ChatMsg.Commitments -> CommitmentsCard(NOOP_COMMITMENTS, SAMPLE_COMMITMENTS)
        is ChatMsg.Suggest -> SuggestCard(m, emptySet(), emptyList(), NOOP_SUGGEST)
        is ChatMsg.Ask -> AskCard(m, null) {}
        is ChatMsg.Agent -> AgentBubble(m)
        else -> Text("(not drawn here: ${m::class.simpleName})", style = T.sans.copy(fontSize = 12.sp, color = C.red))
    }
}
