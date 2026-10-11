# Udhaar detection

> Status: **half shipped.** The manual half is built and tested —
> `spec/done/udhaar-repayment.md` and `spec/done/udhaar-borrowed.md`.
> What is left here is **detection**, and it cannot be built yet.
> Surface: android (signals) · backend (matching) · frontend (inbox, budget)
> Owner: s12k · 27 Aug 2026
> Depends on: `spec/paisa-categorise.md` — signals are shared

## What is built, and what this file still owes

Everything a person can do by hand exists: lending and borrowing rows, partial
repayments in both directions, *Gift*, Undo, per-person `is_peer`, and the
budget treatment in §7 — which was rewritten during that build and is the
version below.

| Section | State |
|---|---|
| §3 items 1–2 — detection, both directions | **Owed.** Needs payment capture (Android) and the agent |
| §3 item 3 — repayment auto-match | **Owed.** The manual match is built; automatic needs a captured credit |
| §3 items 4–5 — budget treatment, Gift | **Shipped** |
| §3 item 6–7 — reminders, threshold | **Owed.** Needs Android push |
| §3 item 8 — per-person history | **Partly.** `is_peer` is live; the counts and averages have no home yet |
| §4 signals, §5 incoming, §6 matching | **Owed.** All agent or Android |
| §9 data model | **Superseded.** It sits on `transactions` with `kind` and `settles_id`, not a `Commitment` table — commitments were archived (`spec/notes.md`) |

So this file is now a **phase 3 and 6 document**. Nothing in it blocks the
plugin, and nothing in it can be built before the agent exists.

## Fits with — one thing to settle first

**`Udhaar` and `Commitment` are the same entity wearing two names.**

`spec/archive/commitments.md` defines a commitment as *anything with a future date and a
consequence*, with `kind: 'money' | 'person' | …`, a direction, an amount, a
status, and a reminder schedule. An udhaar is exactly that: money owed, in a
direction, to a person, sometimes with a date.

Building both means two tables tracking money owed, two reminder engines, two
"close it" flows, and two places for the same bug.

**Proposed resolution:** udhaar is a **specialisation of commitment**, not a
sibling.

| Commitment field | Udhaar uses it as |
| --- | --- |
| `kind` | `'person'` |
| `direction` | `LENT` / `BORROWED` |
| `amount` | `principal` |
| `dueOn` | `expectedBy` (optional — most udhaar has no date) |
| `closedAt` / `status` | same, plus `GIFTED` |

What udhaar adds that a generic commitment does not have: **detection** (§4),
**repayment matching** (§6), and **per-person history** (§7). Those are real and
belong here. The storage and reminder machinery should not be duplicated.

Everything below is the detection and treatment logic, which stands either way.

---

## 1. One-liner

Jab paisa kisi **insaan** ko jaata hai (kharcha nahi, udhaar), usko khud
pehchano — aur jab wapas aaye, khud match karo. Dono direction: **maine diya**
aur **maine liya**.

## 2. Problem

Udhaar aur kharcha bilkul ek jaise dikhte hain. Dono mein paisa jaata hai, dono
UPI hai, dono ka notification ek jaisa aata hai.

**Par ek budget todta hai, doosra nahi.**

**Asli data (1–27 Aug):**

| Kahan gaya | Amount |
|---|---|
| Dost ko udhaar (7,000 + 1,000 + 4,000) | 12,000 |
| Sister ko | 2,800 |
| Mummy ko | 1,000 |
| Dost ko diya (wapas nahi aayega) | 2,000 |
| **Logon ko kul** | **17,800** |
| **Apne upar kul kharcha** | **~18,700** |

**User apne upar jitna kharch karta hai, lagbhag utna doosron ko deta hai.** Aur
woh kisi budget category mein nahi tha — isliye har mahine lagta tha "paisa
gayab ho gaya."

Aur jab 10,000 wapas aaya (14 Aug), poora hisaab ek jhatke mein badal gaya —
daily limit ₹349 se ₹700 ho gaya.

## 3. Scope

### V1 mein

| # | Kya |
|---|---|
| 1 | Outgoing udhaar detection (maine diya) |
| 2 | Incoming udhaar detection (maine liya — mujhpe udhaar) |
| 3 | Repayment auto-match, dono direction |
| 4 | Udhaar ko budget se bahar rakhna, receivable ki tarah |
| 5 | "Gift bana do" — ek tap mein udhaar → kharcha |
| 6 | Reminder **user ko** (dost ko nahi) |
| 7 | Chhoti amount threshold — usse kam par reminder nahi |
| 8 | Per-person history — kaun kitne din mein wapas karta hai |

### Baad ke liye

| # | Kya | Kyun ruka |
|---|---|---|
| 9 | WhatsApp reminder draft + UPI link | Pehle dekho user khud maangta hai ya nahi |
| 10 | Partial repayment tracking | Abhi tak ek bhi partial nahi hua |
| 11 | Reciprocity / ehsaan counter | Alag feature, v2 |

### Bilkul nahi

- **Bill splitting** — Splitwise wala jhamela nahi chahiye
- **Digital sign-off / IOU link** — dost ko sign karwana rishte mein ajeeb hai
- Dost ke app install karne par depend karne wala koi feature
- Interest calculation, due-date penalty

## 4. Signals

### 4.1 Signal 1 — round amount

**Asli data:**

| Round (udhaar) | Odd (kharcha) |
|---|---|
| 7,000 · 1,000 · 2,000 · 4,000 | 83 · 125 · 240 · 570 · 129 · 44 |

Wajah: dukaan ka bill odd banta hai. Dost ko dete waqt round bhejte ho. **Koi
₹4,287 udhaar nahi deta.**

**Correction (zaroori):** yeh akela **kaafi nahi hai.** Grocery ₹2,000 aur Wi-Fi
₹4,000 bhi round the, par kharcha the. Aur sister ka ₹800 udhaar tha par 500 ka
multiple nahi.

```
round + payee INSAAN hai  → udhaar
round + payee DUKAAN hai  → kharcha
```

### 4.2 Signal 2 — bidirectional history (sabse pakka)

**Dukaan sirf paisa leti hai. Dost ke saath paisa dono taraf jaata hai.**

| Payee | Paisa aaya? | Kya nikla |
|---|---|---|
| MOHD SAMEER | +7,000 | Dost |
| RAJESH | +1,000 | Dost |
| NAGENDRA KUMAR | +8,000 | Papa |
| KRISHNA SWEETS | Kabhi nahi | Dukaan |
| DSCSC CHILLA | Kabhi nahi | Dukaan |

**Rule:** ek baar kisi payee se credit aa gaya → woh permanently `isPeer = true`.
Yeh flag kabhi ulta nahi hota.

### 4.3 Signal 3 — contacts

Payee ka number phone contacts mein hai → insaan hai.

**India-specific problem:** naam se insaan/dukaan pehchanna **kaam nahi karta.**

| Naam | Asli mein |
|---|---|
| MOHAN LAL | paan shop |
| MOHD WASIM | chicken shop |
| GEETA | ande wali dukaan |
| SADANAND GUPTA | ? (dukaan lagti hai) |

India mein har kirana/paan/chicken dukaan proprietor ke naam se UPI par hai.
**Isliye `payeeNameType` signal ko bahut kam weight do.** Contacts zyada
bharosemand hai, par woh bhi pakka nahi — landlord aur kirana wala bhi contacts
mein ho sakte hain.

### 4.4 Signal 4 — frequency shape

| Pattern | Kaun |
|---|---|
| Bahut baar, chhote amounts (₹20–300) | Dukaan |
| Kabhi-kabhi, bade round amounts | Dost — udhaar |
| Mahine mein ek baar, wahi amount | Rent / EMI / bill |

### 4.5 Scoring

```
lendingScore = 0

// pakka signals
if (hasReceivedFromPayee)                    += 40    // bidirectional
if (inContacts)                              += 25

// amount
if (amount >= 500 && amount % 500 == 0)      += 25
else if (amount >= 500 && amount % 100 == 0) += 10    // 800 wala case

// dukaan ke ulte signals
if (payeeTxnCount >= 5)                      -= 40
if (payeeMedianAmount < 300)                 -= 25
if (businessKeywordInName)                   -= 30    // STORE, SWEETS, PVT, LTD
if (amountInKnownSpendBand)                  -= 20

// context
if (motionBefore == STILL && atHome)         += 10
```

| Score | Behaviour |
|---|---|
| ≥70 | Auto-mark udhaar, notification: "Udhaar mark kiya — badalna hai?" |
| 40–69 | Inbox mein poocho: "Yeh udhaar tha?" [Haan] [Nahi, kharcha] |
| <40 | Normal kharcha |

## 5. Incoming udhaar (mujhpe udhaar)

Yeh dono direction ka feature hai — abhi tak sirf outgoing socha gaya tha.

**Jab paisa AAYE (CREDIT):**

```
credit aaya
   ↓
kya yeh mere pichhle udhaar ka repayment hai?
   → haan: auto-match, udhaar band karo (§6)
   ↓
   → nahi: naya credit hai
        ↓
   kya yeh salary/known income hai? → income
        ↓
   kya payee insaan hai (contacts/bidirectional)?
        ↓
   → "Kya yeh udhaar hai jo aapko wapas karna hai?"
      [ Haan, wapas karna hai ]  [ Nahi, gift/income ]
```

**Asli misaal:** 13 Aug ko papa se ₹8,000 aaye, agle din rent ₹7,948 gaya. Yeh
**pass-through** tha — na income, na udhaar. Uske liye teesra option chahiye:

```
[ Wapas karna hai ]  [ Gift/income ]  [ Kisi aur ko dene ke liye tha ]
```

Teesra chuna → woh credit aur uska matching debit dono budget se bahar ho jaate
hain.

## 6. Repayment matching

```
Naya CREDIT aaya
   ↓
Us payee ka koi khula udhaar hai?
   ↓
amount == baaki amount        → 100% match, auto-close
amount >  baaki amount        → close + extra ko naya credit maano
amount <  baaki amount        → partial (v2), abhi user se poocho
   ↓
Notification: "Amit ne ₹4,000 wapas kiye. Udhaar band. [Undo]"
```

**Undo hamesha 24 ghante tak available rahe.**

**Asli test case:** 14 Aug ko ek hi din mein 7,000 (Sameer) + 1,000 (Rajesh) +
2,000 (sister) aaye. Teeno alag payees, teeno exact match. **Model ko teeno
alag-alag close karne chahiye.**

## 7. Budget treatment

**Yeh feature ka asli maqsad hai.** Decided 2026-09-04 (`spec/in-progress/udhaar-repayment.md`):

```
Udhaar diya    → paisa gaya. Us mahine ka pool ghata, daily limit ghati.
Wapas aaya     → paisa aaya. Jis mahine aaya us mahine ka pool badha, limit badhi —
                 agle hafte aaye ya teen mahine baad.
Gift diya      → kharcha hai, "Logon ko diya". Limit par ab asar nahi —
                 paisa to dene ke din hi gaya tha; bas ab wapas ki ummeed nahi.
Pending        → goal mein kabhi nahi ginta. Dost ka waada bachat nahi hai.
```

Pehle yahan likha tha ki udhaar ka limit par asar nahi hona chahiye, aur
receivable ko track record dekh kar spendable maana jaaye. Woh hata diya:
jo paisa haath mein nahi, woh ginta nahi — na spend ke liye, na goal ke liye.
Per-person history (kitne din mein wapas, kitni baar) reminders aur agent ki
detection ke liye rehti hai, arithmetic ke liye nahi.

## 8. Reminders

**Reminder user ko jaata hai, dost ko nahi.**

```
"Dost 2 ko ₹4,000 diye the, 27 din ho gaye.
 Aapke is mahine ke target ka 42% isi par tika hai."
```

| Setting | Default |
|---|---|
| Pehla reminder | 7 din |
| Uske baad | Har 7 din |
| Chhoti amount threshold | ₹500 — usse kam par kabhi reminder nahi |
| Snooze | Haan |
| "Bhool jao" | Gift bana do |

**Kyun threshold:** ₹100–500 maangna "petty" lagta hai. Log usse chhod dete hain.
To app ko bhi nahi kurednachahiye — bas chup-chaap track karta rahe.

## 9. Data model

Per **Fits with** above, this should sit on the `Commitment` table rather than a
new one. Kept here as the shape udhaar needs from it:

```kotlin
data class Udhaar(
  val id: String,
  val counterparty: String,        // normalized payee
  val direction: Direction,        // LENT | BORROWED
  val principal: Double,
  val repaid: Double = 0.0,
  val givenAt: Long,
  val expectedBy: Long?,           // optional
  val closedAt: Long?,
  val status: Status,              // OPEN | CLOSED | GIFTED
  val linkedTxnIds: List<String>
)

data class CounterpartyStats(
  val name: String,
  val isPeer: Boolean,             // kabhi paisa aaya? permanent flag
  val inContacts: Boolean,
  val timesLent: Int,
  val timesRepaid: Int,
  val avgDaysToRepay: Double?,
  val currentlyOwed: Double
)
```

`CounterpartyStats` overlaps `PayeeProfile` in `spec/paisa-categorise.md` —
`isPeer` is that spec's `hasReceivedFrom`, and `inContacts` is identical. One
table, not two.

## 10. Acceptance criteria

| # | Criteria | Target |
|---|---|---|
| B1 | Lending detection accuracy (27-din data par) | ≥85% |
| B2 | Repayment auto-match | ≥90% |
| B3 | Galti se kharche ko udhaar maanna (false positive) | <5% |
| B4 | Koi feature dost ke app install par depend kare | 0 |
| B5 | Udhaar ka daily limit par galat asar | 0 |

## 11. Test plan — abhi ho sakta hai

27 din ka labelled data maujood hai.

| Test | Expected |
|---|---|
| T1 | 7,000 / 1,000 / 2,000 / 4,000 → udhaar detect | 4/4 |
| T2 | Grocery 2,000 aur Wi-Fi 4,000 → udhaar NAHI | 2/2 |
| T3 | Sister ka 800 → udhaar (500 multiple nahi) | pass |
| T4 | 14 Aug ke teen repayments → teeno auto-close | 3/3 |
| T5 | Papa ka 8,000 + rent 7,948 → pass-through detect | pass |
| T6 | Mummy ka 1,000, dost ka 2,000 → gift, udhaar nahi | 2/2 |

**T2 aur T3 sabse zaroori hain** — wahin purana round-number rule toota tha.

## 12. Open questions

- Chhoti amount threshold ₹500 sahi hai ya user set kare?
- Agar user kabhi reminder par action na le, to kya app poochhe "yeh gift maan
  lein?"
- Family (mummy, sister) ko alag treat karein? Unse wapas nahi maangte, par 2,000
  wapas aaya tha
- Ek hi insaan ko baar-baar udhaar — alag entries ya ek running balance?
- **Udhaar vs Commitment** — the merge proposed at the top of this file. Needs a
  yes or no before either is built.
