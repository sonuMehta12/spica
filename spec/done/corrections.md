# Corrections — editing a row from the deck

> Built and verified in the browser on real rows: ⋮ → Edit → "Commute 150" →
> same id, ₹150, no duplicate, survived a reload; ✕ left the row untouched.
> The UI half of `spec/done/ledger-writes.md`.

## The problem

Tap ⋮ on a ledger row, choose *Edit*, and today the row's text is dropped back
into the composer so you can re-say it. Re-saying **creates a new row**. The
wrong one is still there. That is a re-log wearing an Edit label — and the
whole point of `PATCH` was that a person can fix a wrong number in place.

## What it does

The composer **remembers which row it is editing**, and on send it patches
that row instead of logging a new one.

```
⋮ → Edit          composer fills with "Commute 130", enters EDIT mode
                  a chip IN the bar, beside the input, reads  ✎ Commute 130  ✕
you type          "Commute 150"
send              → the row changes in place, same id, marked pending
                  → PATCH /transactions/{id} { description, amount_paise }
                  → 200: pending cleared      · failure: row reverts, reads "unsaved"
✕ or Esc          leaves the row untouched, clears the composer
```

Money edits: **description and amount**. Meal edits: **dish and kcal**.
Category, protein, tags stay as they were — the composer's parser cannot
express them, and guessing a category from a reworded description would be
the app changing a field the user did not touch. Those fields get their own
controls later, with the agent.

## Rules

- **Same id, in place.** An edit never creates a row and never touches
  `source` or `created_at` — those are facts about the row's origin.
- **Optimistic, but never silently.** The row shows the new value at once;
  if the server refuses, the *old* value comes back and the row reads
  `· unsaved`. A failed edit must not leave the screen claiming a number the
  server never accepted.
- **Edit mode is visible.** A composer that silently patches instead of
  logging would turn a normal "chai 40" into an overwrite of whatever was last
  opened. The chip is the guard; leaving edit mode always requires either a
  send or an explicit cancel.
- **One row at a time.** Opening Edit on a second row replaces the first
  target; nothing is queued.
- **Parsing is the composer's existing rule** — the first number is the
  amount (money) or kcal (meal), the rest is the description. Same code path
  as logging, so the two cannot drift.

## Decided against

| Option | Why not |
|---|---|
| An inline edit form on the row | A form. The premise is one conversation, no forms |
| Editing every field from the composer | Category and protein need structured input the composer does not have; guessing them from prose is the app editing what the user did not |
| Keeping the re-log behaviour and deleting the old row automatically | Two writes to fix one number, and a moment where both exist — the correction that ledgers were invented to avoid |

## Definition of done

| Check | Expected |
|---|---|
| Edit "Commute 130" → "Commute 150", send | same row, ₹150, one row in the table, `PATCH` returned 200 |
| Reload | still ₹150 |
| Edit and press ✕ | row untouched, composer empty, chip gone |
| Edit with the backend stopped | row reverts to ₹130, reads `· unsaved` |
| Edit a meal's kcal | same row, new kcal, protein unchanged |
| Type a normal log while not editing | a new row, as before — edit mode did not leak |
