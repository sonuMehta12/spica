package com.sonu.spica.data

import com.sonu.spica.lib.Day
import com.sonu.spica.lib.Fmt
import com.sonu.spica.lib.Ulid
import kotlinx.serialization.json.JsonObject
import java.net.URLEncoder

/**
 * The one file that knows both shapes — port of `frontend/src/data/api.ts`.
 *
 * The server speaks the database's language (`local_day: "2026-08-22"`,
 * `amount_paise: 30900`); the app speaks its own (`day: 22`, `amt: 309`). The
 * translation stops here, and neither client's convenience leaks into the API.
 */
object Api {
    private fun enc(s: String) = URLEncoder.encode(s, "UTF-8")

    /** Paise → rupees, rounded as the web rounds. */
    fun paise(n: Long): Int = Fmt.jsRound(n / 100.0).toInt()

    private fun dayOf(iso: String) = iso.substring(8, 10).toInt()

    /* ─── the deck ─────────────────────────────────────────────────────── */

    suspend fun fetchDeck(to: String = Day.today()): DeckData = adapt(Http.get<WireDeck>("/deck?to=$to", "deck"))

    fun toProfile(w: WireUser) = Profile(
        id = w.id,
        displayName = w.displayName,
        email = w.email,
        avatarUrl = w.avatarUrl,
        onboardingDoneAt = w.onboardingDoneAt,
        dob = w.dob,
        gender = w.gender,
        heightCm = w.heightCm,
        city = w.city,
        diet = w.diet,
        timezone = w.timezone,
        savingsTarget = w.savingsTargetPaise?.let(::paise),
        kcalTarget = w.kcalTarget,
        proteinTarget = w.proteinGTarget,
        carbsTarget = w.carbsGTarget,
        fatTarget = w.fatGTarget,
        fibreTarget = w.fibreGTarget,
        weightTargetKg = w.weightTargetKg,
        sleepTargetMin = w.sleepTargetMin,
        stepTarget = w.stepTarget,
    )

    fun toProject(w: WireProject) = Project(
        id = w.id,
        name = w.name,
        color = w.color,
        description = w.description,
        icon = w.icon,
        aliases = w.aliases,
        isDefault = w.isDefault,
    )

    private fun toTx(t: WireTx) = Tx(
        id = t.id,
        day = dayOf(t.localDay),
        name = t.description,
        cat = t.category,
        amt = paise(t.amountPaise),
        commitmentId = t.commitmentId,
        commitmentInferred = t.commitmentInferred,
        confidence = t.confidence,
        date = t.localDay,
        credit = t.direction == "credit",
        deleted = t.deletedAt != null,
        kind = t.kind,
        at = instantOf(t.occurredAt),
    )

    private fun toMeal(m: WireMeal) = Meal(
        id = m.id,
        day = dayOf(m.localDay),
        name = m.dish,
        type = m.mealType,
        p = m.proteinG ?: 0.0,
        k = m.kcal ?: 0,
        c = m.carbsG,
        f = m.fatG,
        confidence = m.confidence,
        date = m.localDay,
        deleted = m.deletedAt != null,
        at = instantOf(m.occurredAt),
    )

    /** A source is free text on the wire; the known ones get their proper name. */
    fun sourceName(source: String) = when (source) {
        "linear" -> "Linear"
        "wispr" -> "Wispr Flow"
        else -> source
    }

    /** Where a synced task came from, in the words the person knows it by. */
    private fun fromLabel(t: WireTask): String? = when {
        t.sourceTitle != null -> t.sourceTitle
        t.tracked && t.sourceRef != null -> "${sourceName(t.source)} · ${t.sourceRef}"
        else -> null
    }

    private fun toTodos(d: WireDeck): List<Todo> = d.work.tasks.map { t ->
        Todo(
            id = t.id,
            name = t.title,
            done = t.status == "done",
            // A task is work unless a label says otherwise.
            kind = when {
                "diet" in t.labels -> TaskKind.Diet
                "paisa" in t.labels -> TaskKind.Paisa
                else -> TaskKind.Work
            },
            // `done_at` is an instant, read in the device's timezone; `due` is
            // already a plain local day.
            doneOn = t.doneAt?.let(Day::localDayOf),
            doneAt = instantOf(t.doneAt),
            project = t.projectId,
            projectGuessed = t.projectGuessed,
            due = t.due,
            priority = t.priority,
            src = if (t.path != null) "${t.path}${if (t.line != null) ":${t.line}" else ""}" else fromLabel(t),
            link = t.docRef?.takeIf { it.startsWith("http") },
            stage = t.sourceState,
            tracked = t.tracked,
            origin = if (t.tracked) sourceName(t.source) else null,
            awaitingMove = t.awaitingMove,
        )
    }

    /** A workout is a habit tick; only the workout habit's logs are sessions. */
    private fun toWorkouts(d: WireDeck): List<Workout> {
        val re = Regex("workout|gym|run", RegexOption.IGNORE_CASE)
        val ids = d.diet.habits.filter { re.containsMatchIn(it.name) }.map { it.id }.toSet()
        return d.diet.habitLogs.filter { it.habitId in ids }.map {
            Workout(id = it.id, day = dayOf(it.localDay), kind = it.note ?: "Workout", minutes = it.amount)
        }
    }

    /** What is still open on one leg, one row per lending or borrowing. */
    fun toOpen(txns: List<WireTx>, leg: String): List<PendingItem> = txns
        .filter { it.kind == leg }
        .map { t ->
            PendingItem(
                id = t.id,
                leg = leg,
                label = t.description,
                amount = paise(t.amountPaise),
                remaining = paise(t.amountPaise - txns.filter { it.kind == "repayment" && it.settlesId == t.id }.sumOf { it.amountPaise }),
                date = t.localDay,
                day = dayOf(t.localDay),
            )
        }
        .filter { it.remaining > 0 }
        .sortedBy { it.date }

    fun toRepayments(txns: List<WireTx>): List<RepaymentItem> {
        val lendings = txns.filter { it.kind == "lent" || it.kind == "borrowed" }.associateBy { it.id }
        return txns.filter { it.kind == "repayment" }.map { t ->
            val l = t.settlesId?.let(lendings::get)
            RepaymentItem(
                id = t.id,
                lendingId = t.settlesId ?: "",
                label = l?.description?.takeIf { it.isNotEmpty() } ?: t.description,
                amount = paise(t.amountPaise),
                date = t.localDay,
                day = dayOf(t.localDay),
                leg = l?.kind ?: if (t.direction == "debit") "borrowed" else "lent",
                lentDate = l?.localDay ?: t.localDay,
                lentAmount = paise(l?.amountPaise?.takeIf { it != 0L } ?: t.amountPaise),
            )
        }.sortedByDescending { it.date }
    }

    fun adapt(d: WireDeck): DeckData {
        // What day the app thinks it is: the device's, always — sent as `to`.
        val anchor = d.to
        val txns = d.paisa.transactions
        // The pool is the month: a June lending is pending in September, but
        // June's money is not September's pool.
        val month = anchor.take(7)
        fun inMonth(t: WireTx) = t.localDay.take(7) == month
        val habitName = d.diet.habits.associate { it.id to it.name }
        fun sum(pred: (WireTx) -> Boolean) = paise(txns.filter(pred).sumOf { it.amountPaise })

        return DeckData(
            today = dayOf(anchor),
            todayIso = anchor,
            monthDays = Day.monthDays(anchor),
            // Only spendable expenses reach the daily limit. A payment that
            // settles a commitment is committed money — the link says so, not a flag.
            tx = txns.filter { it.kind == "expense" && it.commitmentId == null && inMonth(it) }.map(::toTx),
            fixedTx = txns.filter { it.kind == "expense" && it.commitmentId != null && inMonth(it) }.map(::toTx),
            salaryToday = txns.any { it.kind == "income" && it.localDay == anchor },
            meals = d.diet.meals.map(::toMeal),
            workouts = toWorkouts(d),
            habitLogs = d.diet.habitLogs.map {
                HabitLogRow(
                    id = it.id, day = dayOf(it.localDay), date = it.localDay,
                    habit = habitName[it.habitId] ?: "?", amount = it.amount, note = it.note,
                    at = instantOf(it.occurredAt),
                )
            },
            sleep = d.diet.days.filter { it.sleepHours != null }.map { Triple(dayOf(it.localDay), it.localDay, it.sleepHours!!) },
            todos = toTodos(d),
            projects = d.work.projects.map(::toProject),
            bankBalance = paise(d.paisa.balanceCheck?.amountPaise ?: 0),
            profile = toProfile(d.profile),
            fixedPaid = sum { it.kind == "expense" && it.commitmentId != null && inMonth(it) },
            // Everything that ARRIVED this month — the inflow side of the
            // server's pool rule (spec/done/fixed-costs.md § the pool rule).
            income = sum {
                inMonth(it) && (it.kind == "income" || it.kind == "borrowed" ||
                    (it.kind == "repayment" && it.direction == "credit"))
            },
            pending = toOpen(txns, "lent"),
            borrowed = toOpen(txns, "borrowed"),
            repayments = toRepayments(txns),
            lentMonth = sum { it.kind == "lent" && inMonth(it) },
            repaidMonth = sum { it.kind == "repayment" && it.direction == "credit" && inMonth(it) },
            borrowedMonth = sum { it.kind == "borrowed" && inMonth(it) },
            paidBackMonth = sum { it.kind == "repayment" && it.direction == "debit" && inMonth(it) },
            incomeSources = txns.filter { it.kind == "income" }.map { it.description to paise(it.amountPaise) },
            onboarding = Onboarding(d.onboarding.doneAt),
        )
    }

    /* ─── the door ─────────────────────────────────────────────────────── */

    /**
     * Swap a Google ID token for a Spica session. The credential is read
     * once, here, and never stored: what the app keeps is the session token.
     */
    suspend fun signInWithGoogle(credential: String): Profile {
        val out = Http.send<WireSignIn>("POST", "/auth/google", body("credential" to credential))
        Session.set(out.token)
        return toProfile(out.user)
    }

    /** This device only. Whatever the server says, this device is signed out. */
    suspend fun signOut() {
        try {
            Http.fire("DELETE", "/auth/session")
        } finally {
            Session.set(null)
        }
    }

    /* ─── writes ───────────────────────────────────────────────────────── */

    /** Resolves to the stored row — an expense may come back linked to the one commitment it settles, as a guess. */
    suspend fun createTransaction(row: Tx, localDay: String): WireTx = Http.send(
        "POST", "/transactions",
        body(
            "id" to row.id,
            "occurred_at" to Day.occurredAt(localDay),
            "local_day" to localDay,
            "amount_paise" to row.amt * 100L,
            "direction" to "debit",
            "kind" to "expense",
            "category" to row.cat,
            "description" to row.name,
            "source" to "manual",
        ),
    )

    suspend fun createMeal(row: Meal, localDay: String) {
        val pairs = mutableListOf<Pair<String, Any?>>(
            "id" to row.id,
            "occurred_at" to Day.occurredAt(localDay),
            "local_day" to localDay,
            "meal_type" to Day.mealTypeNow(),
            "dish" to row.name,
            "kcal" to row.k,
            "protein_g" to Fmt.num(row.p),
            "source" to "manual",
        )
        // Sent only when known — NULL, not a fabricated 0.
        row.c?.let { pairs += "carbs_g" to Fmt.num(it) }
        row.f?.let { pairs += "fat_g" to Fmt.num(it) }
        Http.fire("POST", "/meals", body(*pairs.toTypedArray()))
    }

    suspend fun patchTask(id: String, done: Boolean) =
        Http.fire("PATCH", "/tasks/$id", body("status" to if (done) "done" else "open"))

    suspend fun patchTransaction(id: String, b: JsonObject) = Http.fire("PATCH", "/transactions/$id", b)

    suspend fun patchMeal(id: String, b: JsonObject) = Http.fire("PATCH", "/meals/$id", b)

    suspend fun deleteHabitLog(id: String) = Http.fire("DELETE", "/habit-logs/$id")
    suspend fun deleteTask(id: String) = Http.fire("DELETE", "/tasks/$id")
    suspend fun deleteTransaction(id: String) = Http.fire("DELETE", "/transactions/$id")
    suspend fun deleteMeal(id: String) = Http.fire("DELETE", "/meals/$id")

    /** A soft delete taken back: the row, live again. 404 when it is missing or was never deleted. */
    suspend fun restoreTransaction(id: String): Tx = toTx(Http.send<WireTx>("POST", "/transactions/$id/restore"))

    /** The meal, live again — its food goes back off the shelf, as the pantry moves it returns. */
    suspend fun restoreMeal(id: String): Meal = toMeal(Http.send<WireMealWritten>("POST", "/meals/$id/restore").meal)

    /* ─── the person ───────────────────────────────────────────────────── */

    suspend fun fetchMe(): Profile = toProfile(Http.get<WireUser>("/users/me"))

    suspend fun patchUser(b: JsonObject): Profile = toProfile(Http.send("PATCH", "/users/me", b))

    private fun toMemory(w: WireMemory) = MemoryRow(w.id, w.slug, w.kind, w.text, w.source, w.confirmedAt)

    suspend fun listMemories(): List<MemoryRow> = Http.get<List<WireMemory>>("/memories").map(::toMemory)

    /** Same slug → the server updates that row instead of filing a second one. */
    suspend fun createMemory(id: String, slug: String, kind: String, text: String): MemoryRow =
        toMemory(Http.send("POST", "/memories", body("id" to id, "slug" to slug, "kind" to kind, "text" to text, "source" to "user")))

    suspend fun patchMemory(id: String, text: String): MemoryRow =
        toMemory(Http.send("PATCH", "/memories/$id", body("text" to text)))

    suspend fun deleteMemory(id: String) = Http.fire("DELETE", "/memories/$id")

    private fun toWeighIn(w: WireWeighIn) = WeighInRow(w.id, w.localDay, w.weightKg ?: 0.0, w.estimated)

    suspend fun listWeighIns(): List<WeighInRow> = Http.get<List<WireWeighIn>>("/weigh-ins").map(::toWeighIn)

    /** A second reading on the same day replaces the first — and, read off a scale, clears its estimate. */
    suspend fun createWeighIn(id: String, localDay: String, kg: Double): WeighInRow =
        toWeighIn(Http.send("POST", "/weigh-ins", body("id" to id, "local_day" to localDay, "weight_kg" to Fmt.num(kg))))

    /** The reading goes, and the day's copy of it with it. */
    suspend fun deleteWeighIn(id: String) = Http.fire("DELETE", "/weigh-ins/$id")

    /* ─── udhaar ───────────────────────────────────────────────────────── */

    /** "<name> ko diya" → "<name> se wapas aaya"; "<name> se liya" → "<name> ko wapas diya". */
    private fun settledLabel(open: PendingItem): String {
        val koDiya = Regex("\\s+ko diya$", RegexOption.IGNORE_CASE)
        val seLiya = Regex("\\s+se liya$", RegexOption.IGNORE_CASE)
        return if (open.leg == "lent") {
            if (koDiya.containsMatchIn(open.label)) open.label.replace(koDiya, " se wapas aaya") else "${open.label} · wapas aaya"
        } else {
            if (seLiya.containsMatchIn(open.label)) open.label.replace(seLiya, " ko wapas diya") else "${open.label} · wapas diya"
        }
    }

    suspend fun createRepayment(id: String, open: PendingItem, amount: Int, localDay: String) = Http.fire(
        "POST", "/transactions",
        body(
            "id" to id,
            "occurred_at" to Day.occurredAt(localDay),
            "local_day" to localDay,
            "amount_paise" to amount * 100L,
            "direction" to if (open.leg == "lent") "credit" else "debit",
            "kind" to "repayment",
            "category" to "Udhaar",
            "description" to settledLabel(open),
            "settles_id" to open.id,
            "source" to "manual",
        ),
    )

    suspend fun createOpen(id: String, leg: String, who: String, amount: Int, localDay: String) = Http.fire(
        "POST", "/transactions",
        body(
            "id" to id,
            "occurred_at" to Day.occurredAt(localDay),
            "local_day" to localDay,
            "amount_paise" to amount * 100L,
            "direction" to if (leg == "lent") "debit" else "credit",
            "kind" to leg,
            "category" to "Udhaar",
            "description" to if (leg == "lent") "$who ko diya" else "$who se liya",
            "counterparty_name" to who,
            "source" to "manual",
        ),
    )

    /** Stop expecting it back: the lending becomes an expense, among the gifts. */
    suspend fun giftLending(id: String) =
        Http.fire("PATCH", "/transactions/$id", body("kind" to "expense", "category" to "Logon ko diya"))

    /* ─── pantry ───────────────────────────────────────────────────────── */

    /**
     * "620 g", "600 ml", "18 pcs" — the food's own unit, never a converted one.
     * Display only: a negative reads with a true minus, `−15 g`. A field is
     * prefilled with `Fmt.num`, which a parse can read back.
     */
    fun inUnit(n: Double, unit: String): String {
        val v = if (n < 0) "−" + Fmt.num(-n) else Fmt.num(n)
        return if (unit == "piece") "$v pcs" else "$v $unit"
    }

    /** "1 dozen" is twelve pieces. A dozen is shorthand, not a unit. */
    fun parseQuantity(raw: String, unit: String): Double {
        val text = raw.trim().lowercase()
        val n = text.replace(Regex("[^0-9.]"), "").toDoubleOrNull() ?: return Double.NaN
        if (unit == "piece" && Regex("dozen|darjan").containsMatchIn(text)) return Math.round(n * 12).toDouble()
        return n
    }

    /**
     * The status ladder, in order. `staple` is a declaration, not a
     * measurement; `new` has no stock figure however negative consumption
     * runs; `stale` outranks `soon` — week-old tofu is not tofu.
     */
    fun statusOf(staple: Boolean, stockG: Double, inbound: Int, lastIn: String?, shelfLifeDays: Int?, reorderAtG: Double?, today: String): PantryStatus = when {
        staple -> PantryStatus.Staple
        inbound == 0 -> PantryStatus.New
        stockG <= 0 -> PantryStatus.Out
        shelfLifeDays != null && shelfLifeDays > 0 && lastIn != null && Day.diffDays(lastIn, today) > shelfLifeDays -> PantryStatus.Stale
        reorderAtG != null && stockG <= reorderAtG -> PantryStatus.Soon
        else -> PantryStatus.Ok
    }

    suspend fun fetchPantry(today: String): List<PantryRow> = Http.get<List<WirePantryItem>>("/pantry").map { w ->
        PantryRow(
            id = w.id, foodId = w.foodId, name = w.name, stockG = w.stockG, reorderAtG = w.reorderAtG,
            shelfLifeDays = w.shelfLifeDays, note = w.note, staple = w.staple, unit = w.unit,
            inbound = w.inbound, lastIn = w.lastIn, lastInG = w.lastInG,
            status = statusOf(w.staple, w.stockG, w.inbound, w.lastIn, w.shelfLifeDays, w.reorderAtG, today),
        )
    }

    suspend fun fetchPantryMoves(foodId: String? = null): List<PantryMoveRow> {
        val q = if (foodId != null) "?food_id=${enc(foodId)}" else ""
        return Http.get<List<WirePantryMove>>("/pantry-moves$q").map {
            PantryMoveRow(it.id, it.foodId, it.name, it.localDay, it.quantity, it.unit, it.kind, it.dish)
        }
    }

    suspend fun createPantryMove(id: String, foodId: String, quantity: Double, kind: String, localDay: String) = Http.fire(
        "POST", "/pantry-moves",
        body(
            "id" to id, "food_id" to foodId, "local_day" to localDay,
            "occurred_at" to Day.occurredAt(localDay), "quantity" to Math.round(quantity), "kind" to kind,
        ),
    )

    suspend fun deletePantryMove(id: String) = Http.fire("DELETE", "/pantry-moves/$id")

    /** Start tracking a food by name. The opening stock, if any, is a second call. */
    suspend fun trackFood(id: String, foodName: String, staple: Boolean, unit: String): String {
        val out = Http.raw("/pantry", "POST", body("id" to id, "food_name" to foodName, "staple" to staple, "unit" to unit))
        return (out as JsonObject)["food_id"].toString().trim('"')
    }

    suspend fun patchPantryItem(id: String, b: JsonObject) = Http.fire("PATCH", "/pantry/$id", b)

    suspend fun stopTracking(id: String) = Http.fire("DELETE", "/pantry/$id")

    /* ─── dishes ───────────────────────────────────────────────────────── */

    private fun toDish(w: WireDish) = DishRow(
        id = w.id, name = w.name, aliases = w.aliases, mealType = w.mealType, serving = w.servingLabel,
        kcal = w.kcal, proteinG = w.proteinG ?: 0.0, carbsG = w.carbsG, fatG = w.fatG, minutes = w.minutes,
        needsPrepAhead = w.needsPrepAhead, imageUrl = w.imageUrl, tags = w.tags, note = w.note,
        steps = w.steps, sourceUrl = w.sourceUrl, mine = w.mine, saved = w.saved, tried = w.tried,
        lastTried = w.lastTried,
        items = w.items.map {
            DishIngredient(it.foodId, it.foodName, it.quantity, it.unit, it.servings ?: 1.0, it.note, it.fromDish)
        },
    )

    /** `mine` is your library — saved or tried. Otherwise the whole pool. */
    suspend fun fetchDishes(mine: Boolean = true, q: String? = null): List<DishRow> {
        val query = "mine=$mine" + (q?.let { "&q=${enc(it)}" } ?: "")
        return Http.get<List<WireDish>>("/dishes?$query").map(::toDish)
    }

    suspend fun saveDish(id: String) = Http.fire("PUT", "/dishes/$id/save")
    suspend fun unsaveDish(id: String) = Http.fire("DELETE", "/dishes/$id/save")

    /* ─── people ───────────────────────────────────────────────────────── */

    private fun toPerson(w: WirePerson) = PersonRow(
        id = w.id, rawName = w.rawName, displayName = w.displayName,
        name = w.displayName?.takeIf { it.isNotEmpty() } ?: w.rawName,
        kind = w.kind, relation = w.relation, note = w.note, confirmed = w.confirmedAt != null,
        source = w.source, isPeer = w.isPeer, defaultCategory = w.defaultCategory,
        sent = w.sentPaise, received = w.receivedPaise, stillOut = w.stillOutPaise, youOwe = w.youOwePaise,
        typicalDays = w.typicalDays, txCount = w.txCount, lastDay = w.lastDay,
    )

    suspend fun fetchPeople(): List<PersonRow> = Http.get<List<WirePerson>>("/people").map(::toPerson)

    suspend fun patchCounterparty(id: String, b: JsonObject): PersonRow = toPerson(Http.send("PATCH", "/counterparties/$id", b))

    suspend fun createCounterparty(b: JsonObject): PersonRow = toPerson(Http.send("POST", "/counterparties", b))

    /* ─── exercises ────────────────────────────────────────────────────── */

    private fun toExercise(w: WireExercise) = ExerciseRow(
        w.id, w.name, w.aliases, w.kind, w.muscleGroup, w.equipment, w.typicalMinutes, w.steps,
        w.sourceUrl, w.imageUrl, w.source, w.note, w.tried, w.lastTried,
    )

    /* ─── today's plan ─────────────────────────────────────────────────── */

    /** The rest of today's meals and one workout; `localTime` (`HH:mm`) says which slots are still ahead. */
    suspend fun fetchPlan(localDay: String, localTime: String): TodayPlan {
        val w = Http.get<WirePlan>("/plan/today?local_day=$localDay&local_time=$localTime", "plan")
        return TodayPlan(
            available = w.available, done = w.done,
            proteinTarget = w.targets.proteinG, kcalTarget = w.targets.kcal?.toInt(),
            loggedProtein = w.logged.proteinG ?: 0.0, loggedKcal = (w.logged.kcal ?: 0.0).toInt(),
            plannedProtein = w.planned.proteinG ?: 0.0, plannedKcal = (w.planned.kcal ?: 0.0).toInt(),
            meals = w.meals.map {
                PlanMeal(it.slot, it.dishId, it.name, it.kcal, it.proteinG ?: 0.0, it.carbsG, it.fatG, it.why,
                    it.idea, it.imageUrl, it.imageCredit)
            },
            workout = w.workout?.let { k ->
                PlanWorkout(k.kind, k.name, k.minutes, k.why,
                    k.exercises.map { PlanExercise(it.exerciseId, it.name, it.detail, it.idea) },
                    k.idea, k.imageUrl, k.imageCredit)
            },
        )
    }

    suspend fun fetchExercises(): List<ExerciseRow> = Http.get<List<WireExercise>>("/exercises").map(::toExercise)

    suspend fun createExercise(b: JsonObject): ExerciseRow = toExercise(Http.send("POST", "/exercises", b))

    /** `tried += 1` and today's date, in one write. */
    suspend fun didExercise(id: String, localDay: String): ExerciseRow =
        toExercise(Http.send("POST", "/exercises/$id/did", body("local_day" to localDay)))

    suspend fun patchExercise(id: String, b: JsonObject): ExerciseRow = toExercise(Http.send("PATCH", "/exercises/$id", b))

    /* ─── places ───────────────────────────────────────────────────────── */

    private fun toPlace(w: WirePlace) = PlaceRow(
        w.id, w.name, w.kind, w.lat, w.lng, w.radiusM, w.address, w.category, w.counterpartyId,
        w.counterpartyName, w.note, w.source, w.confirmedAt != null, w.payments, w.spentPaise, w.lastSeen,
    )

    suspend fun fetchPlaces(): List<PlaceRow> = Http.get<List<WirePlace>>("/places").map(::toPlace)

    suspend fun createPlace(b: JsonObject): PlaceRow = toPlace(Http.send("POST", "/places", b))

    suspend fun patchPlace(id: String, b: JsonObject): PlaceRow = toPlace(Http.send("PATCH", "/places/$id", b))

    suspend fun deletePlace(id: String) = Http.fire("DELETE", "/places/$id")

    /**
     * Nominatim — OpenStreetMap's own geocoder. Free and keyless, about one
     * request a second, biased to India because that is where the payments
     * are. The one request that does not go through `Http.raw`: it is somebody
     * else's server, and our session token has no business travelling there.
     */
    suspend fun searchPlaces(q: String): List<Found> = kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) {
        val url = "https://nominatim.openstreetmap.org/search?q=${enc(q)}&format=jsonv2&limit=6&countrycodes=in"
        val req = okhttp3.Request.Builder().url(url)
            .header("Accept", "application/json")
            // Nominatim's usage policy asks every client to name itself.
            .header("User-Agent", "Spica-Android/0.1 (personal use)")
            .build()
        Http.client.newCall(req).execute().use { res ->
            if (!res.isSuccessful) throw HttpError(res.code, "search: ${res.code}")
            val arr = WireJson.parseToJsonElement(res.body.string()) as kotlinx.serialization.json.JsonArray
            arr.mapNotNull { el ->
                val o = el as? JsonObject ?: return@mapNotNull null
                fun str(k: String) = (o[k] as? kotlinx.serialization.json.JsonPrimitive)?.content ?: ""
                val display = str("display_name")
                Found(display.substringBefore(','), str("lat").toDoubleOrNull() ?: 0.0, str("lon").toDoubleOrNull() ?: 0.0, display)
            }
        }
    }

    /* ─── the month's numbers ──────────────────────────────────────────── */

    suspend fun fetchLimit(to: String): LimitInfo {
        val l = Http.get<WireSummary>("/paisa/summary?to=$to&fields=limit_today", "summary").limitToday
        return LimitInfo(
            limit = l.limitPaise?.let(::paise), spentToday = paise(l.spentTodayPaise), left = l.leftPaise?.let(::paise),
            pool = paise(l.poolPaise), locked = paise(l.lockedPaise), fixedPaid = paise(l.fixedPaidPaise),
            daysLeft = l.daysLeft,
        )
    }

    /* ─── commitments ──────────────────────────────────────────────────── */

    private fun toCommitment(w: WireCommitment) = Commitment(
        id = w.id, name = w.name, source = w.source, origin = w.origin, category = w.category,
        expected = paise(w.expectedPaise), paid = paise(w.paidPaise), owed = paise(w.owedPaise), over = paise(w.overPaise),
        settled = w.settled, skipped = w.skipped, dueDay = w.dueDay, repeats = w.repeats,
        rolled = w.amountSource == "rolled", inferredLinks = w.inferredLinks, carriedFrom = w.carriedFromMonth,
    )

    private fun toCommitmentsPage(w: WireCommitmentsPage) = CommitmentsPage(
        month = w.month, editable = w.editable, owed = paise(w.owedPaise), pool = paise(w.poolPaise),
        savingsTarget = paise(w.savingsTargetPaise), limit = w.limitPaise?.let(::paise), daysLeft = w.daysLeft,
        paidCount = w.paidCount, openCount = w.openCount, items = w.items.map(::toCommitment),
    )

    /** The current month when `month` is null — rolled forward on first read. Any other is read-only. */
    suspend fun fetchCommitments(month: String? = null): CommitmentsPage =
        toCommitmentsPage(Http.get<WireCommitmentsPage>("/commitments" + (month?.let { "?month=$it" } ?: ""), "commitments"))

    suspend fun createCommitment(d: CommitmentDraft, id: String): Commitment {
        val pairs = mutableListOf<Pair<String, Any?>>(
            "id" to id, "name" to d.name.trim(), "category" to d.category.trim(),
            "amount_paise" to (d.amount ?: 0) * 100L, "repeats" to d.repeats,
        )
        d.dueDay?.let { pairs += "due_day" to it }
        d.linkTx?.let { pairs += "link_transaction_ids" to listOf(it) }
        return toCommitment(Http.send("POST", "/commitments", body(*pairs.toTypedArray())))
    }

    suspend fun patchCommitment(id: String, b: JsonObject): Commitment = toCommitment(Http.send("PATCH", "/commitments/$id", b))

    suspend fun deleteCommitment(id: String) = Http.fire("DELETE", "/commitments/$id")

    /* ─── the agent ────────────────────────────────────────────────────── */

    const val CHAT_PAGE = 20

    /** A turn. No streaming: the reply lands whole. The day and clock are the client's. */
    suspend fun sendChat(message: String, localDay: String): ChatReply =
        Http.send("POST", "/chat", body("message" to message, "local_day" to localDay, "local_time" to Day.localTime()))

    suspend fun fetchChat(limit: Int = CHAT_PAGE, before: Int? = null, includeCleared: Boolean = false): ChatPage {
        var q = "limit=$limit"
        if (before != null) q += "&before=$before"
        if (includeCleared) q += "&include_cleared=true"
        val p = Http.get<WireChatPage>("/chat?$q", "chat")
        return ChatPage(p.messages, p.hasMore, p.clearedThroughSeq)
    }

    /** Clear the screen without forgetting: the server folds the thread into the summary. */
    suspend fun clearChat(): ChatPage {
        val p = Http.send<WireChatPage>("POST", "/chat/clear")
        return ChatPage(p.messages, p.hasMore, p.clearedThroughSeq)
    }

    /** Rows a card named that the deck's window does not hold — deleted ones included. */
    suspend fun fetchTxByIds(ids: List<String>): List<Tx> =
        Http.get<List<WireTx>>("/transactions?ids=${enc(ids.take(50).joinToString(","))}").map(::toTx)

    suspend fun fetchMealsByIds(ids: List<String>): List<Meal> =
        Http.get<List<WireMeal>>("/meals?ids=${enc(ids.take(50).joinToString(","))}").map(::toMeal)

    /**
     * One answer to one of the first run's questions. 409 once the first run is
     * finished, 429 past the day's cap, 502 when the model failed — and then
     * nothing was written.
     */
    suspend fun onboardingTurn(question: String, text: String, localDay: String): OnboardingReply =
        Http.send("POST", "/onboarding/turn", body("question" to question, "text" to text, "local_day" to localDay))

    /** A tap on a card: one tool, its arguments, no model. */
    suspend fun actChat(name: String, args: JsonObject, record: Boolean = false): ChatReply =
        Http.send("POST", "/chat/act", body("name" to name, "args" to args, "record" to record))

    /* ─── habits ───────────────────────────────────────────────────────── */

    private fun toHabit(w: WireHabit) = HabitRow(
        w.id, w.name, if (w.direction == "break") "break" else "build", w.unit, w.daysThisWeek, w.loggedEver,
    )

    suspend fun fetchHabits(): List<HabitRow> = Http.get<List<WireHabit>>("/habits").map(::toHabit)

    suspend fun createHabit(name: String, direction: String, unit: String?): HabitRow =
        toHabit(Http.send("POST", "/habits", body("id" to Ulid.next(), "name" to name, "direction" to direction, "unit" to unit)))

    suspend fun patchHabit(id: String, b: JsonObject): HabitRow = toHabit(Http.send("PATCH", "/habits/$id", b))

    suspend fun deleteHabit(id: String) = Http.fire("DELETE", "/habits/$id")

    /* ─── projects ─────────────────────────────────────────────────────── */

    private fun toProjectRow(w: WireProject) = ProjectRow(toProject(w), w.archivedAt != null, w.openTasks, w.movedAliases)

    suspend fun fetchProjects(): List<ProjectRow> = Http.get<List<WireProject>>("/projects").map(::toProjectRow)

    suspend fun createProject(b: JsonObject): ProjectRow {
        val withId = JsonObject(b + ("id" to toJson(Ulid.next())))
        return toProjectRow(Http.send("POST", "/projects", withId))
    }

    suspend fun patchProject(id: String, b: JsonObject): ProjectRow = toProjectRow(Http.send("PATCH", "/projects/$id", b))

    /** Soft; its tasks move to the default project. */
    suspend fun deleteProject(id: String) = Http.fire("DELETE", "/projects/$id")

    /* ─── schedules ────────────────────────────────────────────────────── */

    private fun toSchedule(w: WireSchedule) = ScheduleRow(
        w.id, w.job, w.label, w.blurb, w.atLocalTime.take(5), w.repeat, w.days, w.enabled,
        w.lastRunLocalDay, w.lastError, w.dueNow,
    )

    suspend fun fetchSchedules(): List<ScheduleRow> = Http.get<List<WireSchedule>>("/schedules").map(::toSchedule)

    suspend fun patchSchedule(id: String, b: JsonObject): ScheduleRow = toSchedule(Http.send("PATCH", "/schedules/$id", b))

    /* ─── nudges ───────────────────────────────────────────────────────── */

    /** A server timestamp — `…Z` or `…+05:30` — as an instant; a naive one is read as UTC. Null when it will not parse. */
    fun instantOf(ts: String?): java.time.Instant? {
        if (ts.isNullOrBlank()) return null
        return runCatching { java.time.OffsetDateTime.parse(ts).toInstant() }.getOrNull()
            ?: runCatching { java.time.Instant.parse(ts) }.getOrNull()
            ?: runCatching { java.time.LocalDateTime.parse(ts).toInstant(java.time.ZoneOffset.UTC) }.getOrNull()
    }

    private fun toNudge(w: WireNudge) = NudgeRow(
        id = w.id, kind = w.kind, title = w.title, line = w.line?.takeIf { it.isNotBlank() },
        day = w.localDay, created = instantOf(w.createdAt),
        seenAt = w.seenAt, doneAt = w.doneAt, dismissedAt = w.dismissedAt, scheduleId = w.scheduleId,
        commitmentIds = ((w.refs as? JsonObject)?.get("commitment_ids") as? kotlinx.serialization.json.JsonArray)
            ?.mapNotNull { (it as? kotlinx.serialization.json.JsonPrimitive)?.content }.orEmpty(),
    )

    /** Today and the days before it, newest first. */
    suspend fun fetchNudges(days: Int = 7): List<NudgeRow> = Http.get<List<WireNudge>>("/nudges?days=$days", "nudges").map(::toNudge)

    /** Opened, acted on, or put away. Only the states named are sent. */
    suspend fun patchNudge(id: String, seen: Boolean? = null, done: Boolean? = null, dismissed: Boolean? = null): NudgeRow {
        val pairs = listOfNotNull(seen?.let { "seen" to it }, done?.let { "done" to it }, dismissed?.let { "dismissed" to it })
        return toNudge(Http.send("PATCH", "/nudges/$id", body(*pairs.toTypedArray())))
    }
}
