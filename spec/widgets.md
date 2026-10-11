# Home screen widgets

> Status: draft
> Surface: android — **not** frontend or backend
> Blocked on: the Android app existing at all

## Sequencing — read this first

This spec is written now because the decisions it records affect the data layer,
which is being built now. **It is not buildable yet.** The build order in
`CLAUDE.md` holds: web prototype → backend → Android app → this.

Two things in here matter before then, though:

- A widget must read data **without launching the app**. That is another argument
  for local-first SQLite, already decided in the Substrate note.
- `localDay` has to exist on ledger rows, or the widget cannot roll over at
  midnight without doing timezone maths in the launcher process.

## The problem

Every glance at Spica currently costs an app launch. Money and food are checked
several times a day and the answer is usually one number — *"aaj kitna bacha
hai"*, *"protein kitna aur"*. Launching a whole app to read one number is the
kind of friction that ends with the app not being opened at all.

Work is worse than a glance problem: ticking a finished task also costs a launch,
so tasks stay ticked-in-your-head and the card slowly stops matching reality.

## What it does

Four widgets. The user places whichever they care about.

### 1 · Kaam — the one that earns its place

The only widget where something can be **done**, not just read. Everything else
here is a number; this one takes a tick.

| Size | Shows |
| --- | --- |
| 2×2 | The next task, its project and due chip, plus `+N aur` |
| 4×2 | Three tasks with working checkboxes. No chart — no room |
| 4×3 | The project bars, then three tasks with checkboxes |

- Tapping a **checkbox** toggles the task and re-renders in place. The row stays,
  struck through, reading `nipta` — same rule as the card
- Tapping a **task name** opens the app on Kaam
- Empty state: *"Sab nipat gaya — aaj ke liye kuch baaki nahi."*

### 2 · Paisa

| Size | Shows |
| --- | --- |
| 2×2 | `Aaj ₹0 / ₹351` with a horizontal bar underneath |
| 4×2 | Adds the month figure and the last two transactions |

### 3 · Diet

| Size | Shows |
| --- | --- |
| 2×2 | Protein remaining — `87g aur chahiye` |
| 4×2 | Adds calories and carbs as three stacked bars |

### 4 · Bol do

One cell. A mic glyph, nothing else. Tap opens the app with the mic already
running.

This is the smallest widget and probably the most-used one, because it is the
only one that matches the actual premise — *agent hi app hai*. A number you read
is a dashboard; a mic you tap is the product.

## How it is built

**Jetpack Glance.** Compose-like syntax that compiles down to `RemoteViews`. That
last part is the whole story: the widget renders in the **launcher's** process,
not the app's, and every limitation below follows from it.

```
GlanceAppWidgetReceiver          manifest entry, one per widget
  └── GlanceAppWidget
        └── provideGlance()      runs in OUR process — Room access is fine here
              └── provideContent { ... }   restricted composable set
```

**Layout** uses `SizeMode.Responsive` with the size buckets in the tables above,
so each bucket is a real layout rather than one layout squashed.

**The bars work.** Glance has no `Canvas` and no arbitrary drawing, so the
concentric arcs would have needed rendering to a bitmap and shipping as an
`Image` — a bad road. Bars are `Box` with a background and a height, which Glance
does natively.

> Worth noting: the bars replaced the arcs for a perception reason — arc length
> scales with radius, so three projects could not be compared. That change
> happens to be what makes this widget buildable at all.

**Updates are pushed, never polled.** `updatePeriodMillis` has a 30-minute floor
and would burn battery for no reason. Instead `updateAll()` fires on:

| Trigger | Why |
| --- | --- |
| Any ledger write | The number the widget shows just changed |
| Any task toggle | From the app or from the widget itself |
| **Local midnight** | `Aaj` means something different now — a one-shot alarm at the next local midnight, rescheduled each time it fires |
| Boot completed | Launcher restores widgets with whatever it cached; refresh once |

The midnight one is easy to forget and the most visible when missed: a widget
reading `Aaj ₹340 kharch` at 9am the next morning is worse than no widget.

## Data

Reads only. No widget writes anything except a task toggle, which goes through
the same path the app uses — never a direct DB write from widget code.

| Widget | Reads |
| --- | --- |
| Kaam | `todos` where `kind = work`, plus project stats for the current week |
| Paisa | Today's transactions, the daily limit, the month total |
| Diet | Today's meals rolled up to protein / calories / carbs |
| Bol do | Nothing |

## Rules and edge cases

- **Never show a stale `Aaj`.** If the widget's data is from an earlier local day
  and the midnight refresh was missed, show the label without a number rather
  than yesterday's figure. A wrong number is worse than a missing one.
- **Empty and first-run states are real states.** A freshly installed app has no
  data; the widget says so plainly instead of rendering `0 / 0`.
- **No animation.** `RemoteViews` cannot animate — bars snap to their new height.
  Do not try to work around this.
- **Toggle is optimistic.** The checkbox flips immediately, then the write lands.
  If it fails, the next render corrects it.
- **Colours come from our tokens, not Material You.** Spica has an identity;
  dynamic colour would dissolve it into the wallpaper. Use `GlanceTheme` with our
  own palette. Android 12+ rounded corners are enforced and that is fine.

## Testing

**Automated — what can actually be covered.** `androidx.glance:glance-testing`
runs the composable and asserts on the tree, so the parts worth unit-testing are
the ones with logic in them:

- The task list picks the right three, in the right order, at each size bucket
- A ticked task stays in place and reads `nipta`
- Empty, first-run and stale-day states each render their intended copy
- Number formatting matches the app — `₹1,000`, not `₹1000`

**Manual — everything else.** Widgets fail in the launcher, and launchers differ
more than anything else on Android. At minimum: **Pixel launcher and Samsung One
UI**, since One UI resizes and pads differently enough to break layouts that look
fine on a Pixel.

| Check | Passes when |
| --- | --- |
| Resize through every bucket | Each layout is intentional, nothing clipped or stretched |
| Light and dark | Both legible; our palette, not the wallpaper's |
| Tick from the widget | Toggles, re-renders, and the app agrees when opened |
| Tick in the app | Widget reflects it without being touched |
| Cross local midnight | `Aaj` resets; verified by moving the device clock, not by waiting |
| Reboot | Widget returns with correct data, not a blank box |
| Force-stop the app | Widget still renders; tapping recovers cleanly |
| Battery, 24h idle | No periodic wakeups attributable to widget updates |
| Long text | A long task name truncates rather than pushing the checkbox off |

## Definition of done

Not done until **all** of these are true:

1. All four widgets install, place and render on Pixel and One UI, in light and
   dark, at every declared size.
2. Ticking a task from the Kaam widget updates the database, the widget and the
   app — and ticking in the app updates the widget.
3. The full manual table above passes on both launchers.
4. `Aaj` rolls over at local midnight, verified by clock change on a device that
   was idle across the boundary.
5. Battery report over 24 idle hours shows no widget-attributable wakeups.
6. Unit tests cover selection, ordering, and the three non-happy states.
7. Every number shown matches what the app shows for the same moment — checked by
   opening the app immediately after reading the widget.
8. No hardcoded colours or sizes; everything resolves through the shared tokens.
9. `frontend/README.md`'s conventions still hold for any copy added here — the
   Hinglish register does not get more formal because it is on a home screen.

## Decided against

| Option | Why not |
| --- | --- |
| **One widget, swipe between modes** | Widgets get taps, not gestures. There is no swipe to have |
| **One widget, tap to cycle modes** | Technically possible, but every tap is a full re-render round trip through the launcher. It feels sluggish, and a widget you have to operate is not a glance |
| **One combined summary widget** | Fits three numbers and no actions. Loses the only genuinely valuable thing here, which is ticking a task |
| **Material You dynamic colour** | Would make Spica look like everyone else's home screen. The identity is the point |
| **Periodic auto-update** | 30-minute floor, battery cost, and the data only changes when the app writes. Push on change instead |
| **Composer input in the widget** | No text entry in `RemoteViews`. The `Bol do` widget covers the intent properly |

## Open

- **Custom fonts are the real unknown.** Bricolage Grotesque and IBM Plex carry
  the entire visual identity, and typeface support in `RemoteViews` is
  constrained. Needs a spike before any layout work: if custom faces do not
  render reliably, the choice is system fonts on the home screen — an acceptable
  but deliberate break — or bitmap-rendered text, which is worse than it sounds.
  **Do not design these layouts until this is answered.**
- Does the Kaam widget follow the card's range (`Is hafte`), or is it always the
  week? A widget has no dropdown, so it needs one fixed answer.
- Lock screen: Android 12 removed lock screen widgets, and what replaced them
  differs by OEM. Worth a look only after the home screen ones ship.
- A Quick Settings tile for `Bol do` — same intent, one swipe from anywhere. Very
  likely worth it, but it is a separate spec.
