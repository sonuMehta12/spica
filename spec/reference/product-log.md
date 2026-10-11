# Product Log — Paisa Tracker

Ek din is tracking ko product banana hai. Yeh file us safar ka log hai — ideas, observations, aur jo real use se seekha.

**Started:** 17 Aug 2026
**Last updated:** 21 Aug 2026
**Current stage:** Manual tracking (Excel + chat), 21 din ka data. Product abhi nahi bana.

---

## Next Actions — jo abhi karna hai

Priority order. Har ek ka faisla data se hoga, opinion se nahi.

| # | Kaam | Kyun | Time |
|---|---|---|---|
| 1 | **Lending scoring model apne 21-din data par test karo** | PRD ka sabse bada assumption. Agar accuracy <85% to notification listener banane ka matlab nahi. | 10 min |
| 2 | **Bank balance confirm karo** | Poora "gayab" number isi par tika hai. Abhi tak 14 Aug ke baad se calculated hai, verified nahi. | 2 min |
| 3 | **Travel payments ke saath TIME log karo** | Feature #7 (time of day) ke bina commute window nahi nikalti | Ongoing |
| 4 | **Splitkaro aur FairShare ek hafta use karo** | Idea #4 ka gap sach hai ya sirf lagta hai — pata karo | 1 hafta |
| 5 | **Tasker + AutoInput se bubble prototype** | Din mein kitni baar dabate ho, count karo. 10+ = alag product banao. 1-2 = share sheet kaafi tha. | 2 ghante |
| 6 | **Web Speech API Hinglish test** | v1 ka sabse bada technical risk | 30 min |

**#1 aur #2 aaj ho sakte hain.** Dono ke liye koi code, permission, ya infra nahi chahiye.

---

## Idea #1 — Auto-Description from Payment Metadata

**Date:** 17 Aug 2026
**Status:** Idea — not built
**Priority:** Core idea. Yehi product ka dil hai.

### Problem

UPI history mein sirf naam aur amount dikhta hai:

```
MOHAN LAL        ₹83
MOHD WASIM         ₹240
DSCSC CHILLA...    ₹570
```

Yeh dekh ke kuch pata nahi chalta. 5 din baad khud ko bhi yaad nahi rehta. Isliye har cheez "Other" category mein chali jaati hai — jo bekaar hai.

### Idea

Payment ke saath metadata capture karo, aur usse **apne aap description likh do.**

**Inputs:**
| Signal | Kya batata hai |
|---|---|
| Merchant/payee name | Sabse strong signal ("KRISHNA SWEETS" → mithai) |
| Time of day | 8am chai, 1pm lunch, 9pm dinner |
| Location (GPS) | Ghar ke paas / office / naya area |
| Amount | 20 = chai, 570 = group meal |
| Day of week | Weekend = dost, weekday = routine |
| Frequency | Roz wahi payee = daily habit |
| Payment app | Alag apps alag kaam ke liye |

**Output:** "Sunday raat 8:30, ghar se 2km door, ₹570 — dosto ke saath dinner"

### Kyun yeh kaam karega

Jo asli data 12–16 Aug mein aaya, usmein pattern saaf hai:

- **MOHAN LAL** — 15 Aug ko ₹83, 16 Aug ko ₹60 aur ₹44. Ek hi din mein do baar, chhote amounts. Yeh koi paas ki dukaan hai (kirana/chai/paan). Sirf frequency + amount se yeh guess ho jaata hai.
- **Mr SADANAND GUPTA** — ₹70 phir ₹280. Amounts alag-alag, repeat payee. Shayad auto/dhaba.
- **VINAY KUMAR** — note mein "rent" likha tha. Ek word ne poora context de diya.

Matlab: **repeat payees hi asli kharcha hain.** Ek baar unko label kar do, phir hamesha ke liye ho gaya.

### Learning loop

```
Naya payment
   ↓
Kya yeh payee pehle dekha hai?
   ├─ HAAN → pichhla label use karo (confidence: high)
   └─ NAHI → metadata se guess karo (confidence: low)
                ↓
         User se ek baar poochho
                ↓
         Yaad rakho — agli baar mat poochhna
```

Pehle mahine mein ~30 payees label ho jayenge. Uske baad shayad 70–80% payments apne aap categorize honge. User ko sirf naye payee par tap karna padega.

### Confidence levels — zaroori

Galat description sahi se zyada khatarnak hai, kyunki user usko sach maan lega. To teen level rakho:

| Level | Kab | UI |
|---|---|---|
| **Pakka** | Repeat payee, user ne pehle confirm kiya | Chup-chaap fill kar do |
| **Shayad** | Metadata se guess | Dikha do, edit karne do |
| **Pata nahi** | Naya payee, koi signal nahi | Poochho — ek tap mein |

---

## Reality Check — yeh banana kitna mushkil hai

Idea achha hai, par technically yeh sabse mushkil hissa hai. Honest rehna zaroori hai:

**Problem:** India mein UPI transaction data third-party app ko seedha nahi milta. GPay/PhonePe/Paytm apni history export nahi karne dete.

**Possible raaste:**

1. **SMS parsing** — Bank ke SMS padho. Sabse common tareeka (Walnut, Money View yehi karte the). Kaam karta hai, par SMS mein location nahi hota, aur merchant name adhoora hota hai.
2. **Account Aggregator (AA)** — RBI ka official framework. Bank data legally milta hai, user ki consent se. Sahi raasta, par licensing chahiye aur setup bhaari hai.
3. **Manual + smart** — User khud amount daale, baaki sab app khud bhar de (time, location, last payee). Sabse aasaan, aur 80% value de deta hai.

**Suggestion:** Option 3 se shuru karo. Location aur time to phone se free mein mil jaata hai. Agar wahi kaam kar gaya, tab SMS/AA ki tarah jao.

---

## Observations from Real Use (12–16 Aug 2026)

Yeh assumptions nahi hain — asli data se nikle hain. Product design inhi par bane.

### 1. Memory 9x tak galat hoti hai

| | Andaaza | Asli |
|---|---|---|
| 12 Aug ka kharcha | ₹270 | ₹2,566 |
| Sat + Sun (15–16) | ₹200 | ₹1,783 |

**Product implication:** Kabhi user se "kitna kharch hua" mat poochho. Woh jawab hamesha galat hoga. Sirf actual transactions dikhao.

### 2. Chhoti cheezein yaad rehti hain, badi nahi

12 Aug ko user ko nimbu (₹10), biscuit (₹5), doodh (₹31) yaad the. ₹1,100 aur ₹800 nahi the.

**Product implication:** Bade transactions par turant notification bhejo — "₹1,100 gaya, kya tha?" Chhoto ko baad ke liye chhod do.

### 3. Recurring bills sabse zyada bhoolte hain

Wi-Fi recharge (₹4,000) mahine ke beech mein yaad aaya, woh bhi ittefaq se. Rent (₹7,948) 5 din tak pata hi nahi chala.

**Product implication:** Recurring detection sabse pehle bano. Har mahine wahi payee + wahi amount = auto-flag.

### 4. Udhaar ko kharcha ginna sabse bada confusion tha

₹7,000 + ₹1,000 + ₹2,000 lent the. Kharche mein gin liye to lagा paisa gayab hai. Wapas aaye to samajh aaya.

**Product implication:** Lending ek alag mode ho, category nahi. "Yeh wapas aayega?" ek toggle. Aur wapas aane par reminder.

### 5. Pass-through payments hisaab bigaad dete hain

Papa ne ₹8,000 bheje → agle din rent ₹7,948 gaya. Agar ise income aur expense dono gino to numbers jhooth bolte hain.

**Product implication:** "Yeh mera paisa nahi tha" flag chahiye. In/out pair detect karke suggest karo.

### 6. "Other" category failure ka signal hai

Abhi tak: Other ₹4,077 — sabse bada category. Matlab tracking ho rahi hai par samajh nahi aa rahi.

**Product implication:** Health metric = "Other ka %". Jitna kam, utna achha. Ise dashboard par dikhao.

---

## Idea #2 — Full App Spec: "PaisaPulse AI"

**Date:** 17 Aug 2026
**Status:** Written as implementation plan by user. Not built.
**Stack proposed:** React + TypeScript + Vite. Dark/slate fintech UI, glassmorphic cards.

### Feature Inventory

**F1 — Voice-First Agentic Interface**
- Live mic (Web Speech API: `webkitSpeechRecognition`), text fallback bar if mic denied
- Natural language parsing for four intent types:
  - Log expense — *"Spent 350 for gas via cash"*
  - Log loan — *"Lent 5000 to Amit until next month"*
  - Query budget — *"How much can I spend today to meet my 15k savings target?"*
  - Query analysis — *"What are my unnecessary expenses this month?"*
- Agentic action cards streamed into a conversation feed (not just text replies)

**F2 — Cricket-Style Run-Rate Engine**
- **Target Score** = savings goal (e.g. ₹15,000 from ₹40,000)
- **CRR (Current Run Rate)** = daily spending average vs median
- **RRR (Required Run Rate)** = safe daily burn limit for remaining days
- **Match Projection** = predictive meter, projected month-end savings vs target, with min/max spend boundaries

**F3 — Peer Loan & IOU Ledger with Digital Handshake**
- Lent/borrowed tracking with due dates
- Shareable link → simulated borrower mobile screen → "Sign & Confirm Acceptance"
- Verifiable audit token / receipt stamp
- Purpose: solve disputes and forgetfulness with a recorded digital receipt

**F4 — EMI & Multi-Source Cashflow Matrix**
- Active loans, monthly EMIs, payment dates, interest rates
- Multiple income streams (salary, freelance, rental)
- Computes *True Disposable Daily Allowance* after locking EMIs + savings goal

**F5 — Expense Leakage Trimmer**
- Flags impulse spending, excessive food delivery, redundant recurring charges
- One-tap "Trim Expense" simulator — shows how cutting a habit recovers the target

**F6 — Demo Presets & Persistence**
- Presets: *"₹40k Salaried Aggressive Saver"*, *"Mid-Month Deficit Crisis"*, *"Fresh Blank Slate"*
- LocalStorage for logs, loans, EMIs, chats

---

## Assessment — kaunsa feature asli hai, kaunsa baad ke liye

Real usage data (12–16 Aug) ke against har feature ko checked:

| Feature | Real problem solve karta hai? | Verdict |
|---|---|---|
| **F2 Run-rate** | HAAN — yeh already manually ho raha hai. "₹349/din" hi RRR hai. CRR ₹892 tha weekend par. | **v1 mein rakho** |
| **F1 Voice logging** | HAAN — memory 9x galat hai. Turant log karna hi asli fix hai. Voice sabse kam friction. | **v1 mein rakho** |
| **Idea #1 auto-description** | HAAN — "Other" ₹4,077 hai. Yehi sabse bada dard. | **v1 mein rakho** |
| **F3 Peer loan tracking** | HAAN — ₹10,000 lent tha, poora hisaab bigad gaya tha | **v1 — bas simple version** |
| **F3 Digital sign-off** | Pata nahi — abhi tak koi dispute nahi hua. Dost ko link bhejke sign karwana **awkward** ho sakta hai. | **v2 — pehle test karo** |
| **F4 EMI matrix** | Aadha — EMI ek hi hai (₹10,000), fixed hai. Multi-income abhi nahi hai. | **v2** |
| **F5 Leakage trimmer** | Abhi nahi — categories hi nahi hain. "Other" 36% hai. Trimmer ko sahi categories chahiye pehle. | **v2 — Idea #1 ke baad** |
| **F6 Presets** | Nahi — yeh demo ke liye hai, khud ke use ke liye nahi | **Skip** |

### Sabse bada risk: scope

6 features, 20+ components, NLP engine, projection engine, voice — yeh 3–4 mahine ka kaam hai. Aur abhi **5 din ka data** hai.

Poora banake baad mein pata chala ki asli problem kuch aur thi — to woh 3 mahine gaye.

### Suggested v1 (2 hafte, 3 screens)

1. **Log screen** — voice ya ek tap. Amount + payee. Baaki app bhare (time, location, last category).
2. **Today screen** — ek bada number: *"Aaj ₹349 bache hain."* Aur bas. CRR vs RRR chhota sa neeche.
3. **Udhaar screen** — kisko kitna, kab tak. Sign-off nahi, sirf reminder.

Baaki sab v2. Agar ye teen screen 30 din chal gaye, tab baaki banao.

### Notes on specific features

**Cricket metaphor is genuinely strong.** RRR ka matlab hai "ab har over mein kitna chahiye" — yehi to daily limit hai. Aur cricket mein sabse zaroori baat: RRR badhta jaata hai agar aap slow khelte ho. Yeh feeling exactly wahi hai jo mid-month hoti hai. Isko UI mein saaf dikhana chahiye — **RRR kal 412 tha, aaj 349 hai, kyunki weekend mein zyada kharch hua.**

**Digital handshake — ek warning.** Idea technically achha hai, par social cost hai. Dost ko ₹500 udhaar dene ke baad "sign karo" link bhejna rishte mein ajeeb hai. Shayad yeh badi amounts (₹5,000+) ke liye optional feature ho, default nahi.

**Web Speech API — Hindi/Hinglish check karna.** Zyada tar payments Hinglish mein bole jayenge ("do sau ka momos"). Browser API English par accha hai, Hinglish par test karna padega. Yeh v1 ka sabse bada technical risk hai.

---

## Idea #3 — Contact Graph as Metadata (Lending Detection Without Sign-Off)

**Date:** 17 Aug 2026
**Status:** Idea — not built
**Replaces:** F3 ka digital sign-off wala hissa

### Kyun

Digital sign-off ka social cost hai. Dost ko "sign karo" link bhejna rishte mein ajeeb hai. Aur asli problem dispute nahi hai — **bhoolna** hai. Bhoolne ka ilaaj sign-off nahi, reminder hai.

To sawaal yeh hai: **bina poochhe kaise pata chale ki yeh payment udhaar tha, kharcha nahi?**

### Signal 1 — Contacts

Agar payee phone contacts mein hai, to woh insaan hai, dukaan nahi. Auto-suggest: *"Kya yeh udhaar tha?"*

**Problem:** Kaafi nahi hai. Landlord bhi contact mein hai. Kirana wala bhi. Contact hona sirf ek hint hai, jawab nahi.

### Signal 2 — Round Numbers (yeh sabse strong hai)

Real data 12–16 Aug se:

| Udhaar (round) | Kharcha (odd) |
|---|---|
| 7,000 | 83, 125, 20, 5, 240 |
| 1,000 | 40, 70, 60, 56 |
| 2,000 | 190, 570, 44, 280 |
| 4,000 | 129, 100, 330, 7,948 |

**100% clean separation.** Har udhaar round tha. Har kharcha odd tha (sirf ₹100 exception, aur woh chhota hai).

Logic yeh hai: dukaan par jo bill banta hai woh odd hota hai. Dost ko dete waqt aap round number bhejte ho — koi ₹4,287 udhaar nahi deta.

**Rule:** amount ≥ ₹500 **aur** 500 ka multiple **aur** payee ek insaan hai → 90% chance udhaar hai.

### Signal 3 — Bidirectional History (sabse pakka)

Dukaan sirf paisa **leti** hai. Dost ke saath paisa **dono taraf** jaata hai.

Data se:
- MOHD SAMEER → +7,000 aaya
- RAJESH → +1,000 aaya
- NAGENDRA KUMAR → +8,000 aaya (papa)
- KRISHNA SWEETS, DSCSC → sirf gaya, kabhi aaya nahi

**Rule:** agar is payee se kabhi paisa aaya hai, to woh peer hai, merchant nahi. Permanent tag.

### Signal 4 — Frequency Shape

| Pattern | Kaun |
|---|---|
| Bahut baar, chhote amounts (₹20–300) | Dukaan / auto / chai |
| Kabhi-kabhi, bade round amounts | Dost — udhaar |
| Mahine mein ek baar, wahi amount | Rent / EMI / bill |

MOHAN LAL: 3 payments 2 din mein, ₹44–83. Yeh clearly dukaan hai, chahe contacts mein ho ya na ho.

### Combined Scoring

```
lending_score = 0
+40  agar payee phone contacts mein hai
+30  agar amount round hai (≥500, multiple of 500)
+30  agar is payee se pehle paisa AAYA hai
-40  agar payee se 5+ transactions hain (dukaan pattern)
-30  agar payee ka naam business jaisa hai (SWEETS, STORE, ALL CAPS)

score ≥ 70  →  "Udhaar" mark karo, chup-chaap
score 40–69 →  ek tap poochho: "Udhaar tha?"
score < 40  →  normal kharcha
```

### Sign-off ka naya roop

Sign-off hatao nahi — **default se off karo.**

- **Default:** koi link nahi, koi awkwardness nahi. Bas aapko reminder — *"Amit ko ₹4,000 diye the, 7 din ho gaye."* Aap khud decide karo poochhna hai ya nahi.
- **Optional:** sirf badi amounts par (₹5,000+), aur wo bhi ek button ke peeche. User chahe to bheje.

Isse forgetfulness solve ho jaata hai (asli problem) bina trust todhe.

### Privacy note — zaroori

Contacts access bahut sensitive permission hai. Play Store / App Store dono justification maangte hain.

- Sab kuch **on-device** rakho. Contacts kabhi server par mat bhejo.
- Poora contact list mat padho — sirf check karo ki *"yeh ek number contacts mein hai ya nahi"* (haan/na).
- Agar permission na mile to bhi app chale — Signal 2, 3, 4 bina contacts ke bhi kaam karte hain.

### Fallback

Naya dost jo contacts mein nahi hai? Signal 2 aur 3 phir bhi pakad lenge. Aur ek baar user ne bata diya, to hamesha ke liye yaad rahega (Idea #1 ka learning loop).

---

## Technical Feasibility Assessment

**Date:** 17 Aug 2026
**Scope:** Sirf "ban sakta hai ya nahi". Privacy/security/compliance baad mein.

### Rating

| Capability | Rating | Kyun |
|---|---|---|
| Round-number detection | **GREEN** | Pure logic. Ek `if` statement. Zero dependency. |
| Bidirectional history | **GREEN** | Local DB query. Zero dependency. |
| Frequency shape | **GREEN** | Group by payee, count. Trivial. |
| Contacts lookup | **GREEN** | Standard API dono platform par. |
| Run-rate engine (F2) | **GREEN** | Simple arithmetic. Already Excel mein chal raha hai. |
| Manual/voice entry | **GREEN** | No dependency. |
| Notification capture (Android) | **AMBER** | Kaam karta hai, par Android-only |
| Location at txn time | **AMBER** | Trigger chahiye. Android par possible, iOS par nahi. |
| Voice in Hinglish | **AMBER** | Browser API weak. LLM chahiye — cost aata hai. |
| SMS parsing | **RED** | Play Store policy blocker (neeche) |
| Account Aggregator | **RED** | Licence chahiye. Solo dev ke liye band. |
| iOS auto-capture | **RED** | Koi raasta nahi. iOS = manual only. |

---

### Blocker 1 — Account Aggregator band hai

Yeh "sahi raasta" tha. Ab nahi hai.

- Sirf RBI/SEBI/IRDAI/PFRDA se regulated companies hi FIU ban sakti hain
- Bina NBFC ya investment-advisory licence ke, do hi option: licence lo, ya kisi regulated entity ke saath partner karo
- Subscription pricing lakhs per month se shuru hoti hai; per-pull bhi hai par tab bhi FIU status chahiye

**Verdict:** Solo developer ke liye ye raasta band hai. Roadmap se hata do. Company ban jaye, funding aa jaye, tab dekhna.

### Blocker 2 — SMS parsing Play Store par nahi chalega

Google ki current policy: jo app default SMS/Phone/Assistant handler nahi hai, woh manifest mein bhi yeh permission declare nahi kar sakta.

Matlab: SMS padhne ke liye aapko **default SMS app** banna padega. Ek expense tracker ke liye ye bekaar hai.

Kuch purane apps (MoneyView, Axio) ke paas legacy exception hai, par naye apps ke liye trend tight hota ja raha hai.

**Verdict:** Iske bharose plan mat banao.

### Jo actually kaam karta hai — Notification Listener

`NotificationListenerService` (Android). GPay/PhonePe/Paytm/bank ki notification padhta hai.

- Runtime permission nahi — user Settings mein jaake enable karta hai (special access)
- FinArt jaise apps ye already kar rahe hain, to precedent hai
- **Bonus:** ye ek *trigger* deta hai. Notification aayi → app jaga → `getLastKnownLocation()` call kar liya. Yahi location capture ka raasta hai.

**Limitations:**
- Android only
- Notification text bank/app ke format par depend karta hai — parser har app ke liye alag
- Notification miss ho gayi to transaction gaya
- User ne notification off kar di to kuch nahi milega

### iOS ka sach

iOS par notification listener nahi hai. SMS read nahi hai. AA ke liye licence chahiye.

**iOS = 100% manual entry.** Isko accept karo aur manual entry ko itna fast banao ki dard na ho (share sheet, widget, Siri shortcut).

---

### Sabse important PM insight

**Algorithm aur data pipeline ko alag karo.**

Jo cheez product ko special banati hai — round numbers, bidirectional history, auto-description, run-rate — woh **sab GREEN hai.** Unke liye kisi permission, licence, ya API ki zaroorat nahi.

Jo cheez RED hai, woh sirf *data andar laane ka pipe* hai.

To pehle algorithm banao aur manual data par test karo. Agar algorithm kaam nahi karta to pipe banane ka koi matlab nahi. Aur agar kaam karta hai, to pipe baad mein kabhi bhi lag sakta hai.

**Aaj hi test ho sakta hai:** 5 din ke UPI screenshots already hain. Un par scoring model chala ke dekho ki lending detection sahi nikalti hai ya nahi. Zero infrastructure, zero permission, zero cost.

### Suggested technical path

| Phase | Kya | Kitna time |
|---|---|---|
| **P0** | Detection logic + manual entry. Web app. Apne data par test. | 1–2 hafte |
| **P1** | Run-rate engine + Today screen | 1 hafta |
| **P2** | Android app + notification listener + location trigger | 3–4 hafte |
| **P3** | Voice (LLM-based, Hinglish) | 2 hafte |
| **Never** | SMS parsing, Account Aggregator | — |

---

## Idea #4 — Loan Recovery & Split Settlement

**Date:** 17 Aug 2026
**Status:** Researched. Problem statement + user stories below.
**Source:** User + friend brainstorm

---

### Research: kya yeh problem asli hai?

Haan. Aur documented hai.

**1. Awkwardness universal hai, culture-specific nahi**

Reddit, Mumsnet, forums — har jagah wahi kahani. Ek etiquette expert ka point: jis tarah se aap paisa maangte ho woh rishte ko nuksan pahucha sakta hai, aur maangne ka tareeka relationship, amount aur situation par depend karta hai.

Ek aur documented case: ek aurat ne dost ke dinner party ke liye khana banaya, ingredients ka paisa maanga — dost ne use "tacky" aur "nickel-and-diming" bola.

**Yehi asli dard hai.** Paisa nahi — *maangne par bura insaan lagne ka dar.*

**2. Amount ka ulta rule**

- **Chhoti amount (₹100–500):** maangna "petty" lagta hai. Log chhod dete hain.
- **Badi amount (₹5,000+):** maangna rishta kharab karta hai. Log der karte hain.

Dono taraf haar. Ek documented case mein loan wapas to mila, par kai missed deadlines ke baad — aur dosti hamesha ke liye kharab ho gayi.

**3. Splitwise exist karta hai, par gaps hain**

Documented limitations:
- Manual entry chahiye — time lagta hai, galtiyan hoti hain
- **Sabki honesty aur participation par depend karta hai**
- Payments ko reconcile nahi karta — settle karna aapka kaam
- Reminder bhejta hai, par kisi ko force nahi kar sakta

Users ki asli shikayat (feedback forum se): naye log jab pehli baar use karte hain to payments gadbad ho jaate hain, aur phir woh dobara app use hi nahi karte.

**Yehi Splitwise ka core problem hai: sabko install karna padta hai.** Ek dost ne mana kar diya, poora system bekaar.

**4. India ka naya blocker — bahut important**

**1 October 2025 se NPCI ne UPI P2P "collect request" band kar diya.** Fraud ki wajah se.

Pehle: dost ko payment request bhej sakte the, woh accept karke pay kar deta tha.
Ab: **aap request bhej hi nahi sakte.** Dost ko khud se push karna padega.

Matlab India mein yeh problem **2025 ke baad aur badh gayi hai.** Jo ek tap ka kaam tha, woh ab WhatsApp message aur yaad dilane ka kaam ban gaya.

**5. Jo already market mein hai**

| App | Kya karta hai |
|---|---|
| Splitwise | Standard. Manual, sabko install karna padta hai. |
| Splitkaro (India) | SMS fetch, Swiggy/Zomato/Blinkit se bill auto-fetch, reminders |
| FairShare (India) | Pre-filled UPI settlement link WhatsApp par bhejta hai |
| SplitMyExpenses | AI receipt itemization, debt simplification, UPI India |

Matlab space bhara hua hai. Differentiation sochna padega.

---

### Problem Statement

> Jab do dost paisa share karte hain — ek ne bill bhara, ya ek ne udhaar diya — to paisa wapas lene ki poori zimmedari **dene wale par** aa jaati hai. Usko yaad rakhna padta hai, amount yaad rakhni padti hai, aur phir khud maangna padta hai.
>
> Maangna emotionally mehnga hai. Chhoti amount par aap kanjoos lagte ho, badi par aap rishta risk karte ho. Isliye log maangte hi nahi — aur paisa chhod dete hain.
>
> Maujooda apps (Splitwise) tab kaam karte hain jab **sab** log app use karein. Asli zindagi mein ek dost hamesha mana kar deta hai, aur system toot jaata hai.
>
> India mein Oct 2025 se UPI collect request band hone ke baad, ab "request" bhejne ka koi seedha rasta bhi nahi bacha.

**Asli problem maangna nahi hai. Problem yeh hai ki maangna EK INSAAN ka kaam ban jaata hai.**

Agar system yaad rakhe aur system hi maange, to kisi ko bura banne ki zaroorat nahi.

---

### User Stories

**Epic 1 — Bina mehnat ke record**

> **US-1.1** — Ek dost ke roop mein jo bill bharta hai, main chahta hoon ki jab main kisi contact ko round amount bhejun to app khud poochhe *"udhaar tha?"*, taaki mujhe alag se entry na karni pade.
> *Accept:* Payment ke 30 second ke andar notification. Ek tap mein haan/na. Ignore karo to normal kharcha ban jaye.

> **US-1.2** — Ek group mein baithe insaan ke roop mein, main chahta hoon ki ek bill ko logon mein baant sakun aur app har ek ka hissa nikal de.
> *Accept:* Amount daalo, log chuno, equal ya custom split. 10 second se kam.

> **US-1.3** — Main chahta hoon ki jab paisa wapas aaye to app khud pehchan le aur udhaar band kar de.
> *Accept:* Usi insaan se wahi (ya usse zyada) amount aaya → auto-match, notification ke saath undo option.

**Epic 2 — Maangna aasaan banana**

> **US-2.1** — Ek insaan jisko maangne mein sharam aati hai, main chahta hoon ki app mere liye message likh de, taaki mujhe words na sochne padein.
> *Accept:* 2-3 tone options (halka / normal / seedha). Edit kar sakun. WhatsApp par share.

> **US-2.2** — Main chahta hoon ki message ke saath ek UPI link jaye jisme amount pehle se bhara ho, taaki dost ko sirf tap aur PIN karna pade.
> *Accept:* Link kisi bhi UPI app mein khule. Dost ko koi app install na karna pade. *(Note: collect request band hai, isliye link hi ekmatra rasta hai.)*

> **US-2.3** — Main chahta hoon ki app mujhe sahi waqt bataye kab maangna chahiye.
> *Accept:* Configurable — 3/7/14 din. Reminder mujhe aaye, dost ko nahi.

**Epic 3 — Dost ko install na karna pade**

> **US-3.1** — Ek insaan jiske dost naye app install nahi karte, main chahta hoon ki poora system sirf mere phone par chale.
> *Accept:* Koi bhi core feature dusre insaan ke signup par depend na kare.

> **US-3.2** — Main chahta hoon ki dost link se hisaab dekh sake bina account banaye.
> *Accept:* Web page — kya kharcha, kab, kitna hissa. Login nahi. Paise dene ka button.

**Epic 4 — Rishta bachana**

> **US-4.1** — Main chahta hoon ki chhoti amount ko app khud ignore karne ka option de, taaki main ₹40 ke liye kanjoos na lagun.
> *Accept:* Threshold set kar sakun. Usse chhoti amount silently track ho, reminder na aaye.

> **US-4.2** — Main chahta hoon ki app "yeh dost hamesha der karta hai" jaise pattern dikhaye, taaki main aage se soch samajh ke dun.
> *Accept:* Har contact par — kitni baar, kitne din mein wapas kiya, kitna abhi baaki.

> **US-4.3** — Main chahta hoon ki udhaar ko "gift" mein badal sakun, taaki ledger jhoot na bole aur mera dimaag saaf ho jaye.
> *Accept:* Ek tap. Amount savings target se hat jaye, "diya hua" mein chala jaye.

---

### Differentiation — kya alag hoga

Space bhara hua hai. Sirf teen cheezein alag ho sakti hain:

1. **Sirf ek insaan ko app chahiye.** Splitwise ki sabse badi kamzori yehi hai. Dost ko link milta hai, app nahi.
2. **Detection automatic hai.** Splitkaro SMS padhta hai. Hum notification padhenge — behtar quality (shop naam milta hai) aur round-number logic se udhaar khud pehchanenge.
3. **Yeh alag app nahi hai.** Yeh usi personal finance tracker ka hissa hai. Udhaar ka asar seedha savings target par dikhta hai — jo koi split app nahi dikhata.

Point 3 sabse strong hai. Splitwise batata hai ki kaun kitna deta hai. **Yeh batayega ki uski wajah se aapka mahina kaise bigda.**

### Open questions

- Chhoti amount ka threshold kya ho? (₹100? ₹500? user set kare?)
- Reminder ka default kitne din? Test karna padega.
- Kya sach mein log app-generated message bhejenge, ya khud likhenge?
- Splitkaro/FairShare use karke dekho — kya sach mein gap hai ya sirf lagta hai?

---

## Idea #5 — Feature Engineering for the Prediction Model

**Date:** 20 Aug 2026
**Status:** Analysis done on 19 din ke real data (37 transactions)

### Finding 1 — Amount clusters asli hain

Transport ke 9 transactions: `40, 40, 60, 114, 114, 130, 130, 140, 160`

| Band | Kya | n |
|---|---|---|
| 40–60 | Toto / chhoti hop | 3 |
| 114–160 | Rapido | 6 |

**61–113 ke beech ek bhi transaction nahi.** Gap saaf hai. Sirf amount se hi mode of transport alag ho jaata hai — is user ke data par 100%.

**Generalization:** band ki *value* user-specific hai (dusre sheher mein 60 ya 400 hoga). Jo generalize hota hai woh yeh hai ki **har user ka commute ek narrow band mein hota hai.** Model ko value hardcode nahi karni, band *khojna* hai.

### Finding 2 — Round-number rule kamzor hai (correction)

Idea #3 mein likha tha "100% clean separation". Zyada data par yeh **toot gaya**:

| Amount | Assumption | Asli |
|---|---|---|
| 1,000 / 2,000 / 4,000 (dost, mummy) | Udhaar | Udhaar ✓ |
| 2,000 (grocery) | Udhaar | **Kharcha ✗** |
| 4,000 (Wi-Fi) | Udhaar | **Kharcha ✗** |
| 800 (sister) | — | Udhaar, par 500 ka multiple nahi ✗ |

**Naya rule:**
```
round amount + payee INSAAN hai  → udhaar
round amount + payee DUKAAN hai  → kharcha
```
Amount akela signal nahi hai. Payee type ke saath hi kaam karta hai.

### Finding 3 — Repeat vs one-time payee

| Payee | Amounts | Inference |
|---|---|---|
| MOHAN LAL | 83, 60, 44 | Repeat + chhote + varied → **dukaan** |
| MOHD WASIM | 5, 240 | Repeat → jaan-pehchaan |
| DSCSC CHILLA | 190, 570 | Repeat → regular jagah |
| SURENDRA SINGH | 40 | One-time + toto band → **ride** |

**Rapido ka special case:** captain ka naam har baar alag hota hai. Repeat-payee logic yahan fail karta hai. Ulta signal chahiye —

> **"Pehli baar dikha payee"** hi Rapido ka sabse strong signal hai, kyunki dukaan hamesha repeat hoti hai.

### Feature list for the model

| # | Feature | Source | Cost |
|---|---|---|---|
| 1 | Amount | Notification / screenshot | Free |
| 2 | Amount band match (user-learned) | Local history | Free |
| 3 | Payee name | Notification text | Free |
| 4 | Payee seen before? (count) | Local DB | Free |
| 5 | Payee name type (person vs business) | Regex + learned | Free |
| 6 | Bidirectional history (paisa aaya kabhi?) | Local DB | Free |
| 7 | Time of day | System clock | Free |
| 8 | Day of week | System clock | Free |
| 9 | In contacts? | Contacts API | Permission |
| 10 | **Motion state before payment** | Activity Recognition API | Cheap |
| 11 | Location at payment | Location API (on trigger) | Permission |
| 12 | Gap since last transaction | Local DB | Free |

Features 1–8 aur 12 ko **koi permission nahi chahiye.** Model ka zyada tar kaam inhi se ho jayega.

### Activity Recognition > hourly location polling

User ka original idea: har ghante location lo, displacement dekho, commute detect karo.

**Problem:** battery bahut jayegi, aur payment ek pal ka event hai — ek ghante ka gap usse miss kar dega.

**Behtar:** Google Activity Recognition Transition API (`IN_VEHICLE` / `WALKING` / `ON_BICYCLE` / `STILL`). OS-managed, battery na ke barabar, precise location ki zaroorat nahi.

```
payment notification aayi
   ↓
pichhle 30 min ka motion history dekho
   ↓
IN_VEHICLE tha? → ride hai
STILL tha?      → dukaan/online hai
WALKING tha?    → paas ki dukaan hai
```

**Bonus:** location precise nahi chahiye → privacy better, permission halki. iOS par `CMMotionActivity` se same cheez milti hai.

Location tab lo jab **notification trigger** kare — polling ki zaroorat nahi.

### Multi-payment sessions

User ka observation: do payment paas-paas hue to shayad ek commute aur ek khana.

**Rule:** 15 minute ke andar ke transactions ko ek *session* maano. Session mein alag-alag category ho sakti hai, par context shared hota hai (wahi location, wahi trip).

Aaj ka example: ₹120 Rapido + ₹10 toto = ek hi journey ke do leg. Ek session, ek category.

### Training approach

Cold start problem hai — naye user ka koi data nahi.

| Phase | Kya |
|---|---|
| Hafta 1–2 | User categorize karta hai. App sirf dekh rahi hai. |
| Hafta 3–4 | App suggest karti hai, user confirm/correct karta hai |
| Hafta 5+ | Auto-categorize, sirf low-confidence par poochho |

Model **per-user** hona chahiye, global nahi. Ek generic model kabhi nahi jaan payega ki *is* user ka Rapido ₹114–160 hai.

---

## More Observations (17–21 Aug 2026)

### 7. Kharcha girna ≠ aadat badalna

17–20 Aug: kharcha 1,100/din se girkar 179/din ho gaya. Dikhne mein lagta hai user ne behaviour badla.

**Asli wajah:** chaar din se dost dinner treat de rahe the. User ne kuch nahi kaata — kharcha kisi aur ne utha liya.

Agar model isko seedha aage project kar deta, to jhoothi ummeed banti — aur jis din treat band hoti, target ek jhatke mein toot jaata.

**Product implication:**
- Run-rate ko andhadhund extrapolate mat karo. Poocho: *kaunsi category gayab hui?*
- Agar koi category (khana) achanak zero ho jaye jabki baaki chal rahi hain → yeh structural change nahi, circumstance hai. Flag karo, celebrate mat karo.
- Formula: `is category ka historical daily average` vs `pichhle 3-4 din` — bada gap = temporary
- Reciprocity debt bhi track karo: 4 log ne khilaya = ek group treat aana baaki hai (₹800–1,500). Yeh ek *pending liability* hai jo kisi ledger mein nahi dikhti.

**Broader lesson:** app ko "kitna kharch hua" ke saath "kyun kam hua" bhi samajhna hoga. Warna woh user ko galat waqt par shabaashi degi.

### Trip chains — transactions ko sequence mein dekho

**Confirmed example (user ne khud verify kiya):**

MOHAN LAL ke payments (83, 60, 44) ek paan ki dukaan ke the. Akela dekho to yeh sirf "₹60 kisi insaan ko" hai — kuch samajh nahi aata. Par poora chain dekho:

```
office se nikle
   ↓ IN_VEHICLE
Rapido payment (114–160, pehli baar dikha payee)
   ↓ ghar se PEHLE utar gaye — location ≠ ghar
WALKING / STILL, dost mile
   ↓
chhota payment, repeat payee (44–83) → paan shop
```

**Insight:** har step agla step predict karta hai. Rapido payment + "ghar nahi pahuncha" + chhota repeat payee = paan shop, lagbhag pakka.

Yeh Idea #5 ke 15-minute session se bada hai — **yeh ek routine hai jo hafte mein 3 baar repeat hoti hai.**

**Feature #13 — Sequence position.** Transaction se pehle kya hua, uska bhi feature banao:
- Pichhla transaction kitni der pehle tha
- Pichhle transaction ki category
- Beech mein motion state badla kya
- Location ghar/office se kitni door

**Aur ek use case:** routine break ho jaye to woh bhi signal hai. Agar hafte mein 3 baar chalne wali chain achanak ruk jaye, matlab aadat badal gayi — ya kuch aur hua. App ise pakad sakti hai.

**Real proof:** 16 Aug ko aakhri paan shop payment. 17–20 Aug: zero. Data se hi pata chal jaata hai ki user ne cigarette chhod di — bina bataye. Yeh ek behaviour-change detector hai jo kisi budget app mein nahi hai.

### 8. Reciprocity ek asli liability hai — aur predictable hai

**Prediction (19 Aug):** "4 logon ne khilaya = ek group treat aana baaki hai, ₹800–1,500."
**Kya hua (21 Aug):** ₹700 ki treat — beer + khana.

Prediction sahi nikli, 2 din ke andar.

**Product implication:** yeh ek *pending liability* hai jo kisi ledger mein nahi dikhti. Splitwise sirf paisa track karta hai. Yeh **ehsaan** track karega.

```
kisi ne aapko khilaya (aapne pay nahi kiya, par saath the)
   ↓
counter badhao
   ↓
counter 3-4 pahuncha → forecast mein ₹800-1,500 ka treat add karo
```

Detection: aap ek jagah the (location), payment kisi aur ne kiya (aapke paas koi transaction nahi), par aap `STILL` the restaurant ke paas 45 min. Yeh notification ke bina bhi pakda ja sakta hai.

**Yeh koi budget app nahi karta.**

### 9. Category substitution — ek girta hai, doosra chadhta hai

| Category | 1–19 Aug | 20–21 Aug |
|---|---|---|
| Cigarette | 187 | **0** |
| Transport | 928 | **390** |

Cigarette gaya (₹3,600/mahina bacha), par transport chupke se badh gaya. Do din mein 390 — poore pehle 19 din ka 42%.

**Product implication:** total kharcha dekhne se yeh chhup jaata hai. App ko **per-category trend** dekhna hoga:

> "Cigarette 0 ho gaya — badhiya. Par Transport pichhle hafte se 2x hai."

Ek category ka sudhar doosri ke bigadne ko chhupa sakta hai. Sirf ek total number dikhana yahan fail karta hai.

### 10. Target ko baar-baar ghatana pada — aur yeh normal hai

| Date | Target | Wajah |
|---|---|---|
| 12 Aug | 15,000 | Shuruaati umeed |
| 19 Aug | 13,000 | Gym + ₹2,000 dost ko |
| 21 Aug | 11,000 | Treat + transport |

Teen baar ghataya, 9 din mein. Aur har baar wajah asli thi — koi laaparwahi nahi.

**Product implication:** target miss hona **normal hai, failure nahi.** App ka sabse nazuk moment yahi hai — jab user target se peeche ho.

- ❌ "Aap peeche ho" (guilt → app delete)
- ✅ "Gym aur treat ki wajah se target 11,000 ban gaya. Woh abhi bhi aapki minimum se upar hai."

**Design rule:** jab target miss ho, app ko *wajah dikhani* chahiye, sirf gap nahi. Aur naya realistic target khud suggest karna chahiye — user ko haar maanne ka faisla na karna pade.

---

## Idea #6 — Envelope Budgeting (ek limit nahi, saat limits)

**Date:** 21 Aug 2026
**Status:** Idea. v1 daily-limit model ko replace/extend karta hai.

### Problem with a single daily limit

Abhi ka model: ek number, "aaj ₹351 bache hain".

Yeh awareness ke liye achha hai, par ek sawaal ka jawab nahi deta: **"kya yeh kharcha theek tha?"**

User ka apna sawaal: *"main balanced kharcha kar raha hoon ya fajool?"* Ek daily number isse nahi bata sakta. ₹700 ka dinner limit todta hai — par agar woh mahine ka pehla dinner hai, to woh bilkul theek hai.

### Idea — categories ko pehle se paisa do

Salary aane ke din hi baant do:

| Envelope | Mahina |
|---|---|
| Bills / Recharge | 4,000 |
| Transport | 4,500 |
| Khana / Grocery | 4,000 |
| Dosto ke saath | 3,000 |
| Logon ko dena | 2,500 |
| Gym | 700 |
| **Buffer (anjaan kharche)** | **5,000** |

**Buffer wali line sabse zaroori hai.** User ka ₹10,693 "gayab" koi galti nahi thi — woh zindagi thi. Wi-Fi recharge, kisi ka birthday, kuch toot gaya. Zyada tar budget isliye fail hote hain kyunki unme "anjaan" ki koi line hoti hi nahi.

Buffer ko naam de do → woh failure nahi rehta. Khaali reh gaya → extra bachat.

### Savings as a bill, not a leftover

Abhi: kharcha karo → jo bache woh bachat.
Badlo: salary ke din hi bachat alag account mein → bache hue mein jiyo.

Isse har kharcha guilt-free ho jaata hai, kyunki bachat pehle ho chuki hai.

### The one question

Har kharche se pehle:

> **"Yeh kis envelope se ja raha hai, aur usme kitna bacha hai?"**

- Jawab aa gaya → balanced hai
- Jawab nahi aaya → **yahi fajool kharch hai**

**Fajool kharch amount se tay nahi hota.** ₹700 ka dinner jo "Dost" envelope mein hai, theek hai. ₹200 ka kuch jo kisi envelope mein nahi, problem hai.

Yeh product ka core UX ban sakta hai — har transaction ke saath ek envelope tag, aur us envelope ka bacha hua paisa.

### Rhythm — daily awareness, weekly decisions

- **Roz:** limit dekho (5 second)
- **Hafte mein ek baar (Sunday, 5 min):** kaunsa envelope khatam ho raha hai, kahan se adjust karna hai, buffer mein kitna bacha

Roz faisle lene se user ek mahine mein thak jaata hai. Yeh 12 mahine chalna chahiye, 3 hafte nahi.

**v1 impact:** "Today screen" par ek number ki jagah — ek bada number (aaj ka limit) + saat chhoti envelope bars. Aur Sunday ko ek weekly review screen.

---

## Backlog — baad ke liye

- **Weekly review** — har Sunday: kya sahi gaya, kaunsa naya payee, agle hafte ka budget
- **Daily limit as one number** — poora dashboard nahi, sirf "aaj ₹349 bache hain"
- **Lending tracker with nudges** — 7 din baad "X se ₹4,000 abhi bhi baaki hai"
- **Repeat-payee leaderboard** — mahine ke top 5 payees. Asli leak yahi dikhta hai.
- **Cash gap tracker** — jo bank balance aur logged spend mein farak hai, woh cash hai. Usko explicitly dikhao.

---

## Open Questions

- Kya user roz app kholega? Ya notification hi kaafi hai?
- Location capture — privacy ka kya? Sab on-device rakhna padega.
- Naya payee poochhne ka sahi waqt kab hai — turant, ya raat ko ek saath?
- Ek user (khud) ke liye bana raha hoon ya sabke liye? Design bahut alag hoga.
- Web Speech API Hinglish samajhta hai? Test karna hai — v1 ka sabse bada risk.
- Digital sign-off dost ko bhejna kitna awkward hai? Ek dost par test karo pehle.
- Agar sirf teen screen banayein (log / today / udhaar) — kya woh kaafi hai?
- Kitna data chahiye product design ke liye? 30 din? 90 din?

---

*Yeh file badhti rahegi. Naya idea aaye to add karte jaana.*
