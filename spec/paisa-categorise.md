# Auto category & description engine

> Status: ready to build
> Surface: android (capture + signals) · backend (LLM batch) · frontend (inbox, review)
> Owner: s12k · 27 Aug 2026
> Depends on: notification capture — **not yet specified**, assume it delivers raw events

## Fits with

| Doc | What it settles that this spec assumes |
| --- | --- |
| **Substrate** note | Transactions are **ledger** rows: append-only, corrections are new entries |
| `spec/archive/commitments.md` | An insurance payment captured here can spawn a commitment via the one-question follow-up |
| `spec/capture.md` | The **Inbox** this spec fills is the same Inbox already in Your data |

**Three inconsistencies to settle before code** — each is small now and expensive later:

1. **`localDay` is missing from `Txn`.** The Substrate note requires the local
   day stored beside UTC, because India is UTC+5:30 and an 11:30pm payment lands
   on the wrong day otherwise. Every "aaj kitna kharch hua" in the app depends on
   it, and this engine's own `hourOfDay` / `dayOfWeek` signals do too.
2. **Confidence scale disagrees.** This spec uses `Int 0–100`; the vault and the
   Substrate envelope use `0–1`. Pick one. `0–1` is already in the running code.
3. **The Inbox threshold disagrees.** Your data currently holds anything under
   **70%**; this spec draws its lines at **85** and **50**. Three levels is the
   better design — so the existing 70% cut should move to match, not the reverse.

---

## 1. One-liner

Har payment ke saath jo metadata milta hai — amount, time, din, payee naam,
motion, location, history — usse **category aur ek insaani description** khud
generate karo. User sirf confirm kare.

## 2. Problem

Notification se yeh milta hai:

```
₹98.00 paid to MOHAN LAL
```

Isse kuch pata nahi chalta. 5 din baad khud ko bhi yaad nahi rehta. Isliye sab
kuch "Other" mein chala jaata hai.

**Asli data (1–27 Aug, 27 din):**

| | |
|---|---|
| "Other" category | ₹2,855 (18%) |
| Jinke payees ka pata hi nahi | 6 |
| Sabse bada ek payment jiska pata nahi | ₹1,100 |

**Aur proof ki yeh solvable hai:** manual analysis se pata chala ki MOHAN LAL =
paan shop, MOHD WASIM = chicken shop, GEETA = ande wali dukaan. **Yeh sab sirf
metadata pattern dekh ke nikla — koi model train nahi hua.**

## 3. Scope

### V1 mein

| # | Kya |
|---|---|
| 1 | 13 deterministic signals compute karna (on-device) |
| 2 | Known-payee dictionary — ek baar label, hamesha ke liye |
| 3 | LLM skill file se category + description generate |
| 4 | Confidence levels — auto / suggest / poocho |
| 5 | End-of-day review — batch confirm |
| 6 | Feedback loop — correction se seekhna |
| 7 | User-learned amount bands (per category) |
| 8 | Monthly reconciliation — "maine 10,000 kaha, aapke paas 8,000 hai, 2,000 kahan gaya?" |

### Baad ke liye

| # | Kya | Kyun ruka |
|---|---|---|
| 9 | Trained ML model | Pehle dekho skill file kitna kaam karta hai |
| 10 | Trip chain / sequence prediction | 2-3 mahine ka data chahiye |
| 11 | Routine-break detection | Same |
| 12 | Reciprocity tracking | v1 se bada scope |
| 13 | Location-based prediction | Permission friction; motion pehle try karo |

### Bilkul nahi

- Voice input / STT — user Whisper Flow use karta hai
- Bank balance API / Account Aggregator
- Bill splitting
- Global (cross-user) model

## 4. Product spec

### 4.1 Confidence levels

Yeh poore feature ka dil hai. **Galat prediction sahi se zyada khatarnak hai**,
kyunki user usko sach maan lega.

| Level | Kab | Behaviour | UI |
|---|---|---|---|
| **PAKKA** (≥85) | Known payee, ya bahut strong signal | Chup-chaap fill, notification nahi | Log mein dikhega, edit kar sakte ho |
| **SHAYAD** (50–84) | Signals se guess | Inbox mein card, ek tap confirm | Signals bhi dikhao |
| **PATA NAHI** (<50) | Naya payee, koi signal nahi | Inbox mein poochho | "Yeh kya tha?" + options |

**Rule:** jo bhi PAKKA se neeche hai, woh **hamesha suggestion ke roop mein**
dikhega — kabhi silently save nahi hoga.

### 4.2 End-of-day review

User ka asli behaviour: woh transaction ke waqt log nahi karta, **raat ko batch
mein review karta hai.** Design isi ke hisaab se.

```
Raat 9 baje ek notification:
"Aaj ke 6 payments — 2 confirm karne hain"
→ Inbox khulta hai
→ SHAYAD wale cards upar
→ Har card: ek tap Haan / Kuch aur
→ Inbox zero → din poora
```

**PAKKA wale cards inbox mein nahi aate.** Woh log mein seedhe chale jaate hain.
Warna inbox bhar jayega aur user chhod dega.

### 4.3 Labelling — ek baar, hamesha ke liye

Repeat payee ko user ek baar label kare, phir dobara kabhi na poochha jaye.

```
┌─────────────────────────────────┐
│  MOHAN LAL                    │
│  5 payments · ₹44–98            │
│                                 │
│  Isko kya naam doge?            │
│  [ chai aur samosa          ]    │
│                                 │
│  Category: [ Health/Diet   ▾]   │
│                                 │
│  ☑ Aage se aise hi maan lena    │
└─────────────────────────────────┘
```

Iske baad har MOHAN LAL payment apne aap "chai aur samosa" ban jaayega, PAKKA
confidence par.

**Edge case (asli):** 27 Aug ko user ne **gym fees ₹700 cash** di, Mohan Lal ki
dukaan par. Wahi payee, alag maqsad. Isliye known-payee override tabhi lagana jab
**amount bhi us payee ke seekhe hue band mein ho.** ₹700 band (44–98) se bahar hai
→ SHAYAD par gir jaana chahiye, PAKKA nahi.

### 4.4 Monthly reconciliation

**Bank balance kabhi nahi poochenge.** Sirf mahine ka hisaab.

```
Mahine ki shuruaat: user batata hai "is mahine 95,000 aaye"
                    fixed kharche minus
                    = kharche ke liye X

App track karta hai → "aapke paas 10,000 bache honge"
User: "nahi, mere paas 8,000 hain"
         ↓
App: "₹2,000 ka hisaab nahi mila. Yaad hai kahan gaya?"
     [ Cash tha ]  [ Koi bhool gaya ]  [ Pata nahi ]
         ↓
Cash tha → "Cash kharcha" entry ban jaati hai
Bhool gaya → user add karta hai
Pata nahi → "Anjaan" entry, par ledger sahi ho jaata hai
```

**Seekhna:** agar har baar gap "cash" nikalta hai, to app agle mahine se cash
buffer estimate karna shuru kare aur user ko pehle hi bataye.

### 4.5 Edge cases

| Case | Behaviour |
|---|---|
| Ek hi transaction do source se aayi | `txnId` hash se dedupe |
| Payee naam kata hua | `EXTRA_BIG_TEXT` se poora lo |
| Refund / reversal | Credit + wahi payee + 7 din ke andar → original se link |
| Ek session mein kai payments | 15 min window → session ID, context share |
| User ne galat confirm kiya | Log mein hamesha edit possible, correction se seekho |
| Same payee, alag maqsad | Amount band check (§4.3) |

## 5. Engineering spec

### 5.1 Data model

```kotlin
data class Txn(
  val txnId: String,           // hash(package + amount + payee + timestamp_minute)
  val occurredAt: Long,
  val localDay: String,        // "2026-08-27" — see Fits with, note 1
  val amount: Double,
  val direction: Direction,    // DEBIT | CREDIT
  val rawPayee: String,        // "MOHAN LAL"
  val rawText: String,         // poori notification
  val sourcePackage: String,

  // enrichment (capture ke waqt)
  val motionState: Motion?,    // IN_VEHICLE | WALKING | STILL | UNKNOWN
  val locationHash: String?,   // geohash, precise coords nahi
  val sessionId: String?,      // 15-min window

  // prediction
  var category: String?,
  var description: String?,
  var confidence: Double,      // 0–1, matching the Substrate envelope
  var predictedBy: Predictor,  // DICTIONARY | RULES | LLM | USER
  var confirmed: Boolean = false
)

data class PayeeProfile(
  val normalizedName: String,  // upper, trim, punctuation hata ke
  val userLabel: String?,      // "chai aur samosa"
  val category: String?,
  val txnCount: Int,
  val amountMin: Double,
  val amountMax: Double,
  val amountMedian: Double,
  val hasReceivedFrom: Boolean,   // bidirectional — udhaar spec ke liye bhi
  val inContacts: Boolean,
  val firstSeen: Long,
  val lastSeen: Long
)
```

### 5.2 Signals (13)

Sab **on-device**, sab LLM ko jaane se pehle compute.

| # | Signal | Kaise | Permission |
|---|---|---|---|
| 1 | `amount` | Notification | — |
| 2 | `amountBandMatch` | User ki category-wise bands se compare | — |
| 3 | `payeeName` | Notification | — |
| 4 | `payeeSeenCount` | Local DB | — |
| 5 | `payeeNameType` | Regex: business keywords (STORE, SWEETS, PVT, LTD) | — |
| 6 | `hasBidirectional` | Local DB — is payee se credit aaya kabhi? | — |
| 7 | `hourOfDay` | Clock | — |
| 8 | `dayOfWeek` + `isHoliday` | Clock | — |
| 9 | `inContacts` | Contacts API (haan/na, poori list nahi) | READ_CONTACTS |
| 10 | `motionBefore30min` | Activity Recognition Transition API | ACTIVITY_RECOGNITION |
| 11 | `locationCluster` | Geohash → "ghar" / "office" / "naya" | ACCESS_COARSE_LOCATION |
| 12 | `minsSinceLastTxn` | Local DB | — |
| 13 | `lastTxnCategory` | Local DB | — |

**1–8 aur 12–13 ko koi permission nahi chahiye.** Agar user permission na de, to
bhi 10 signals kaam karte hain.

> **Sabak (asli galti):** 23 Aug ko ₹150 ka payment aaya. Amount band (114–160) ne
> "Rapido commute" bola. **Galat tha — woh phal shop tha, apple.** Wajah: **Sunday
> tha, office nahi jaate.** Signal #8 use hi nahi hua.
>
> **Isliye:** commute prediction se pehle `dayOfWeek` gate lagana **mandatory** hai.

### 5.3 Amount bands khud seekhna

Har category ke liye user-specific bands nikaalo. Hardcode kuch nahi.

```kotlin
fun learnBands(category: String): List<Band> {
  val amounts = db.amountsFor(category).sorted()
  // 1-D clustering: consecutive gap > 40% of range → naya cluster
  return cluster(amounts, gapThreshold = 0.4)
}
```

**Asli misaal:** Transport = `40, 40, 60, 114, 114, 130, 130, 140, 160`
→ Band A: 40–60 (toto), Band B: 114–160 (Rapido). Beech mein 61–113 khaali.

**Minimum 5 transactions** chahiye kisi category mein band banane ke liye. Usse
pehle band signal off.

### 5.4 Prediction pipeline — tiered (cost control)

LLM har transaction par mat chalao. Chaar tier:

```
Tier 0 — DICTIONARY (0ms, ₹0)
  Known payee + amount band ke andar
  → PAKKA, seedha save

Tier 1 — RULES (0ms, ₹0)
  Deterministic scoring (§5.5)
  Score ≥85 → PAKKA
  → LLM ki zaroorat nahi

Tier 2 — LLM BATCH (raat ko ek call, sasta)
  Din ke saare uncertain transactions ek saath
  → SHAYAD / PATA NAHI

Tier 3 — USER
  Inbox mein poocho
```

**Cost estimate:** din ke ~6 transactions mein se 4-5 Tier 0/1 par nikal
jaayenge. Tier 2 mein 1-2 bachenge, aur woh bhi **ek hi batched call** mein.
Matlab **din mein ek LLM call.**

### 5.5 Deterministic rules (Tier 1)

```
score = 0

// payee history
if (payeeSeenCount >= 3 && amountInPayeeBand)   score += 50
if (payeeSeenCount >= 3 && !amountInPayeeBand)  score += 15   // dukaan hai par amount ajeeb

// amount band
if (amountInCategoryBand && bandIsUnique)       score += 30

// time + day gate
if (isCommuteWindow && isWorkingDay)            score += 20
if (isCommuteBand && !isWorkingDay)             score -= 30   // 23 Aug wali galti

// motion
if (motionBefore == IN_VEHICLE)                 score += 25   // ride
if (motionBefore == STILL && duration > 30min)  score += 15   // baithe the — restaurant

// sequence
if (minsSinceLastTxn < 15)                      score += 10   // same session

// naya payee
if (payeeSeenCount == 0)                        score -= 20
```

### 5.6 LLM skill file

V1 mein model train **nahi** karenge. Ek skill file likhenge jo LLM ko user ke
patterns batati hai.

**Skill file structure** (app ke saath ship hoti hai, user data se roz update
hoti hai):

```markdown
# User Spending Patterns

## Learned payees
| Payee | Label | Category | Amount range | Frequency |
|---|---|---|---|---|
| MOHAN LAL | chai aur samosa | Health/Diet | 44–98 | ~4/hafta |
| MOHD WASIM | chicken shop | Khana | 5–240 | ~2/hafta |
| GEETA | ande wali dukaan | Khana | 220 | ~1/hafta |

## Learned amount bands
| Category | Bands |
|---|---|
| Transport | 40–60 (toto), 114–160 (Rapido) |
| Khana | 5–36 (chhota), 100–320 (grocery) |

## Routines
- Weekday shaam 7–8 PM: office se ghar, Rapido 114–160
- Sunday: office nahi. Commute band par bharosa mat karo.
- Subah 8–9 AM: doodh 31–36

## Rules learned from corrections
- Sunday ka 150 = phal/grocery, commute NAHI
- Mohan Lal par ₹700 = gym fees cash, chai nahi
```

**Prompt structure:**

```
[SKILL FILE — upar wala]

## Aaj ke uncertain transactions
1. ₹98 → MOHAN LAL | Mon 7:42 PM | seen 5x | motion: WALKING | 12 min after last txn
2. ₹340 → ANITA KUMARI | Mon 1:15 PM | seen 0x | motion: STILL | in contacts: no

Har ek ke liye JSON do, aur kuch nahi:
[{ "id": 1, "category": "...", "description": "...", "confidence": 0-100, "why": "..." }]
```

**Output validation:**

- JSON parse fail → Tier 3 (user se poocho)
- Category list se bahar → reject
- `confidence` > 85 aur payee naya hai → 84 par cap karo (LLM overconfident hota hai)

### 5.7 Feedback loop

```
User correction
   ↓
1. PayeeProfile update (label, category)
2. Category ke amount bands dobara compute
3. Agar correction ne kisi rule ko toda → skill file ke "Rules learned" mein add
   e.g. "Sunday ka 150 = phal, commute nahi"
4. Skill file regenerate (roz ek baar, raat ko)
```

**Har correction ko store karo** — `(signals, predicted, actual)`. Yeh baad mein
model train karne ka dataset hai. Aaj se collect karo, chahe model kabhi banao ya
na banao.

### 5.8 Privacy

- Saara transaction data **on-device** (Room/SQLite)
- Contacts: sirf `haan/na` check, poori list kabhi mat padho, kabhi mat bhejo
- Location: geohash (~1km), precise coords kabhi nahi
- LLM call: payee naam **hash** karke bhejne ka option (skill file mein mapping
  local rahegi)
- Notification raw text kabhi server par nahi

## 6. Acceptance criteria

| # | Criteria | Target |
|---|---|---|
| A1 | Known payee auto-fill | 100% |
| A2 | Overall auto-categorised (bina poochhe) after 30 din | ≥70% |
| A3 | Prediction accuracy jab confidence ≥85 | ≥95% |
| A4 | "Other" category ka hissa | <10% |
| A5 | User ko roz kitne poochhne padte hain | ≤2 |
| A6 | LLM calls per day | ≤2 |
| A7 | End-of-day review time | <60 sec |

## 7. Test plan — abhi ho sakta hai

**Dataset already hai:** 1–27 Aug, ~70 transactions, sab labelled.

| Test | Kaise |
|---|---|
| T1 | Skill file bana ke LLM ko 27 din ke transactions do, accuracy naapo |
| T2 | Sirf pehle 14 din ka skill file do, baad ke 13 din predict karao — yeh asli test hai |
| T3 | Deterministic rules alone kitna nikaalte hain (LLM ke bina baseline) |
| T4 | Known edge cases: 23 Aug ka ₹150, 27 Aug ka ₹700 gym |

**Agar T2 mein accuracy <70% aaye, to skill-file approach kaafi nahi — tab model
training sochna.**

## 8. Open questions

- Skill file kitni badi ho sakti hai? 100+ payees ke baad context limit?
- LLM on-device (Gemini Nano) ya API? Cost vs privacy
- Skill file regenerate roz ho ya har 10 correction ke baad?
- Naye user ke liye seed skill file? (common Indian payees: Zepto, Blinkit,
  Swiggy, Rapido)
- **Notification capture ka spec abhi likha nahi gaya.** Yeh spec uspe khada hai,
  to woh pehle chahiye — kam se kam yeh tay karna ki raw event ki shakl kya hai.
