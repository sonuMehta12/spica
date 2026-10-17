Design the Home screen of Spica, a personal life app for one person. Spica tracks money, food and health, work tasks, habits and mood, and the user logs things by talking to it. Home shows the user's whole day as one vertical rail: what already happened above, a highlighted "So far today" card at the current moment, and what is still coming below.

FRAME
- Android phone, 390 × 844 pt, one vertically scrolling page.
- The page opens already scrolled so the "Now" point sits near the top; the earlier part of the day is one swipe up.
- A composer floats at the bottom over the content.

LAYOUT, TOP TO BOTTOM

1. App bar
- Left: round menu button (list icon).
- Centre: a Home / Chat switch; Home is selected.
- Right: round nudges bell; shows a small dot when something new is waiting.
- No date, no week strip.

2. The day rail (straight on the white page, no panel around it)
- A thin vertical line connects every moment of the day.
- Each row has three columns: time (52 pt, right-aligned), an icon node sitting on the line (36 pt), then the title on the left and one figure on the right.
- Row height about 46 pt. One line per row, no second line.

3. Past rows (everything already done today, above Now)
- Icon node is filled: a circle in the domain's tint with the icon in the domain's ink.
- Title and figure are in muted grey, so the past reads quieter than the future.
- A logged feeling uses the mood face as its node instead of an icon.

4. Now marker
- A row at the current time: the time in bold, a solid dark dot on the rail, a dark line running across, and the word "Now".

5. So far today card (the highlight of the screen)
- Sits right under the Now marker and spans the width of the rail.
- White card with a hairline border (#EDEAEC) and a soft lifted shadow, so it floats above the page and reads as "you are here". No tinted background.
- Header: "So far today" plus a small line saying the time range and how many things were logged ("08:40 to 12:40 · 9 things logged").
- Mood face in the top-right corner, with the mood's name under it and a small "+" badge. Tapping it opens a row of five faces (Heavy, Uneasy, Okay, Calm, Bright) under "How are you now?". Picking one logs that mood at the current time: the corner face changes, a new mood row joins the rail at Now, and a line appears: "Logged · Calm at 12:40 · Add a word". "Add a word" opens Chat.
- Two circles, side by side:
  - Spent: a ring on a light money-tint track, filled to the share of today's spending limit already used. Centre: "₹260" and "spent". Under the ring: "₹640 left of ₹900" in the money colour. If spending passes the limit, the ring turns red and the line says how much over.
  - Protein: a ring on a light food-tint track, filled to the share of the protein target eaten. Centre: "78 g" and "protein". Under the ring: "62 g to go" in the food colour.
- Optional quiet line under the circles, separated by a hairline: five small icon + number pairs with a one-word unit under each: 1,240 kcal · 6,420 steps · 5h 10m sleep · 2 smoked · 1/4 tasks.

6. Up next card (the first upcoming item)
- On the rail at its time, with an outlined icon node.
- Food-tint card: a small "Up next" tag, the title "Lunch · Rajma chawal", the figure "22 g" on the right, one supporting line "Gets you to 100 of 140 g protein", then a primary "Log it" button and a "Something else" link.

7. First task card
- On the rail at its time, with an outlined task icon node.
- Work-tint card: a small "First task" tag, the title "catalog sync ka bug fix karna", the line "AnyMall-chan · 2 days late" with "2 days late" in red, the line "15:00 to 16:30, a free slot Spica found", then a primary "Done" button and a "Move" link.
- An amber dot before its time, because Spica suggested the slot and the user hasn't confirmed it.

8. The rest of today
- Every remaining item, one line each, in time order, with outlined icon nodes and normal-weight dark text.
- Items with no time come last, labelled "Any time".

9. Composer
- A floating pill at the bottom: a "+" button, the placeholder "Say what happened…", and a round brand-coloured mic button.

EXAMPLE DATA (Thursday, 12:40)
Past:
- 08:40 · food · Poha · 14 g
- 09:15 · money · Chai · −₹20
- 09:40 · money · Metro · −₹40
- 10:30 · money · Phone cover · −₹200
- 10:50 · habit · Cigarette · Terrace
- 11:05 · work · Reply on the AnyMall PR · Done
- 11:42 · mood · Felt uneasy (mood face node)
- 12:10 · health · Breathing, 3 min · Better
- 12:20 · habit · Cigarette · Terrace
Now: 12:40
So far: ₹260 spent of ₹900 (₹640 left) · 78 of 140 g protein (62 g to go) · 1,240 of 2,100 kcal · 6,420 steps · 5h 10m sleep · 2 smoked · 1 of 4 tasks done · mood Uneasy
Up next: 13:00 · Lunch · Rajma chawal · 22 g
First task: 15:00 (suggested) · catalog sync ka bug fix karna · AnyMall-chan · 2 days late
Rest of today:
- 16:30 (suggested) · work · Task source links · Today
- 18:30 · health · Gym · Workout B · 45 min
- 19:30 · health · Check in
- 20:30 (suggested) · food · Dinner idea · Paneer · 34 g
- 21:00 · reminder · Plan tomorrow's meals
- Any time · work · Study agentcall.dev app · Personal

INTERACTIONS
- Tap the mood face: open the five-face picker; pick one to log it; "Add a word" goes to Chat.
- Log it, Done, Move and Something else act on that item right where it is.
- Tap any row to open that item.
- Scroll up to see the earlier part of the day; the page always opens at Now.

STATES AND RULES
- Done items have filled icon nodes; planned items have outlined ones.
- Red means only "over the limit" or "late". Never use it for decoration or emphasis.
- An amber dot means only "suggested or estimated by Spica, not confirmed". Nothing else is amber.
- A value that is unknown shows a dash, never zero.
- The mood face is what the user logged, never a score Spica works out. Nothing on the screen grades the day.
- No streaks, no badges, no "great job".

VISUAL SYSTEM (current "Day" theme)
Colours:
- Page background pure white #FFFFFF. No tinted or pinkish backgrounds anywhere; cards are white too and separate by hairlines (#EDEAEC) and soft shadows. Only the Up next and First task cards carry their domain tint.
- Text #1B171A, muted #5D5A5C, faint #726F71, hairlines #EDEAEC.
- Brand (Jamun) #732F67 is only for primary buttons, the mic, the selected switch, links and selection. Never as a background.
- Money: #239D6A base, #00613A ink, #E6F9EE tint.
- Food and health: #C16E2D base, #7C3C00 ink, #FFF0E4 tint.
- Work: #418AD1 base, #125289 ink, #E7F5FF tint.
- Habits: ink #1B171A on #F2EFF1.
- Amber #C58500 (suggested only). Red #BD3933 (over or late only).
Type:
- Anek Latin for everything on this screen, with tabular figures so numbers line up.
- A serif (Newsreader) is reserved for sentences the assistant itself says; this screen has none.
- Labels in sentence case, never all caps.
Icons:
- Phosphor, regular weight: bowl (food), coffee, train, shopping bag, cigarette, check-square (task), barbell (workout), bell (reminder and check-in), wind (breathing), fire (calories), walking person (steps), bed (sleep), wallet (money), list, plus, microphone.
Mood face:
- A soft rounded blob in the food and health tint (#E9B999) with dark-brown features.
- Five expressions: Heavy (closed down-turned eyes, frown), Uneasy (worried brows, wavy mouth), Okay (dot eyes, flat mouth), Calm (closed smiling eyes, small smile, cheeks), Bright (dot eyes, open smile, cheeks).
- A dashed empty outline means "not logged yet".
- The colour never changes with the mood; only the expression does.
Shape and space:
- Side gutter 16. Cards 18–22 radius. Pills and buttons fully round. Icon nodes 30 pt circles.
- Soft shadows in ink at low opacity (0 1px 2px rgba(27,23,26,.05), 0 6px 18px rgba(27,23,26,.06)), never black.

KEEP FIXED IN EVERY VARIATION
- The order: past → Now → So far today → Up next → First task → rest of today → composer.
- The rail metaphor: one connecting line, one row per moment, time on the left.
- Spent and Protein as the two hero numbers, both with what is left.
- The mood face in the So far card, tappable to log a mood.
- The states and rules above.

FREE TO EXPLORE
- Theme: light, dark, bold or editorial, warm paper, glass, high contrast.
- How the two numbers are drawn: rings, circles that fill like liquid, segmented arcs, big numerals with thin gauges, dot matrices.
- Card style: tinted, outlined, floating or flat; corner radii; tags.
- Icon nodes: circles, rounded squares, outlined or filled, sizes.
- Typography scale and weight; density and row height.
- How the past is shown: full rows, a collapsible "8 done" stack, or faded.
- Motion: a breathing Now dot, the rings filling on open, a slow wave inside liquid circles. Respect reduced-motion settings.

Produce 3–4 distinct variations of this screen, each a full phone frame using the example data. Give each one a short name and a one-line description of its idea.
