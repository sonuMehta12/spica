# Capture

> Status: draft
> Surface: frontend (bookmark) · android (share) · backend (enrichment)
> Related: `spec/../` Substrate design note — type · path · tag

## Superseded in part — read `spec/substrate.md` first

Two things this file assumes changed after it was written:

- **`article` and `video` are gone as types (2026-09-06).** This file's filing
  table maps a share onto one of five kinds; there are three — `recipe`,
  `place`, `workout`. The argument is the one already made below about `medium`,
  followed to its end: a reel showing a recipe is a **dish that arrived as a
  reel**, and `dishes.source_url` already holds the link. A thing that is only a
  link to read later is a read-later app, and this is not one. Every table below
  that names `article` or `video` as a destination is stale.

- **The always-on-top extension is gone; a Chrome extension is back (2026-09-04),
  but as a deliberate share button, not passive capture.** Nothing files itself.
  On the phone the share sheet is the door; in Chrome the extension's one action
  is. Sentences below that lean on the extension *watching* the page are stale.
- **Articles are out of scope entirely** — not "covered by the extension", which
  is the reason given below. There is no reading pile.

The share mechanics in §Door 2, the three bookmark states, the one-tap filing
rule and the enrichment honesty are all still correct. Door 1 (bookmark from
conversation) is secondary at best.

## The problem

The library is where recipes, workouts and places live, but almost nothing puts
things into it. The extension covers pages you visit in a browser. Two much more
common moments are uncovered:

1. **The agent suggests something good** — a recipe, a workout — and it vanishes
   when the conversation scrolls. It was never a thing, only a sentence.
2. **You are inside another app** — an Instagram reel, a YouTube video, a blog —
   and there is nowhere to put it except your own memory.

Both are the same gap: **a thing was in front of you and there was no way to
keep it.**

## Two doors

### Door 1 — bookmark, from inside the conversation

Anything the agent suggests as a *thing* can be kept with one tap. It lands in
the library, filed, without a follow-up question.

```
agent  Raat ko ye bana lo —
       ┌──────────────────────────────────┐
       │ Soya keema            39g  ☆     │   ← tap to keep
       │ 20 min · lobhia bhigo ke         │
       └──────────────────────────────────┘
       ┌──────────────────────────────────┐
       │ Paneer bhurji         24g  ★     │   ← already yours
       └──────────────────────────────────┘
```

**The thing being kept must be a typed object, not a sentence.** You cannot
bookmark prose. This is the constraint that shapes everything: when the agent
suggests things, its reply carries structured items with ids, and the prose sits
around them. A reply that is only text has nothing to keep.

Three states, and they are genuinely different:

| State | What tapping does |
| --- | --- |
| Suggested, not in the library | **Creates** the library item and files it |
| Already in the library | Nothing — the star is filled, and it is not a button |
| Came from the Inbox at low confidence | **Confirms** it, which clears the doubt without changing the item |

### Door 2 — share, from any other app

Spica appears in the Android share sheet. You share a reel, a video, a link, a
screenshot — it is stored and filed.

```
Instagram ──share──▶ Spica
                      └─ stored immediately, as a link
                         └─ enriched in the background
                            └─ filed, or dropped in the Inbox
```

The share lands in a **small sheet, not the whole app**. It confirms and closes:

```
┌─────────────────────────────┐
│ Save ho gaya · Recipes      │
│ instagram.com/reel/…        │
│                    [Kholo]  │
└─────────────────────────────┘
```

Booting the full app and dropping the user into a chat would cost them their
place in Instagram, which is the one thing a share must never do.

## The rule that makes both work

**One tap. The agent guesses where it goes. The Inbox catches mistakes.**

Filing is a `type` + `path` + `tags` decision, and asking the user for any of
them at capture time kills the habit — a bookmark that costs a form is a
bookmark nobody makes twice. So the agent decides, with a confidence score, and
anything under 70% goes to the **Inbox that already exists** in Your data rather
than being filed on a guess.

This is not a new mechanism. It is the same one the extension uses. Two doors,
one filing system.

## Where it lands

Per the Substrate note: `type` decides the shape, `path` is its one home, `tags`
carry everything else.

| Shared / suggested | type | path | tags from |
| --- | --- | --- | --- |
| A recipe reel | `recipe` | `Recipes/Dinner` | ingredients, time, `veg` |
| A workout video | `workout` | `Workouts/Push` | `gym`, duration |
| A restaurant link | `place` | `Places/Khana` | city, `jaana hai` |
| Anything unresolved | — | Inbox | whatever the URL gave up |

**Articles are out of v1**, deliberately. The extension already covers the case
where you are reading in a browser, and the sharing case brings the whole
read-later problem with it, which is its own spec.

## What actually arrives from a share — the honest part

This is the constraint most likely to be misjudged, so it goes here rather than
in the notes.

**A share gives you a link, not the content.**

| Source | What the intent carries | How well we can file it |
| --- | --- | --- |
| YouTube | URL + title | Good — title and description are fetchable |
| Blog / news | URL, sometimes title | Good — Open Graph tags are usually honest |
| Instagram | Usually **only** a URL | Poor. Scraping is actively blocked |
| Screenshot | An image | Depends entirely on OCR |
| Plain text | The text | Whatever the user typed |

So Instagram — the case that prompted this — is the **weakest** one. A reel URL
on its own does not say it is a paneer recipe.

Which forces the design:

- **The share always succeeds.** It stores the link and confirms, immediately,
  before anything is understood. A share that can fail is a share the user stops
  doing.
- **Enrichment is asynchronous and allowed to fail.** If it cannot tell what the
  thing is, the item sits in the Inbox as unresolved.
- **The user's own share text is a hint, not noise.** If they typed *"paneer
  recipe"* into the share sheet, that is better metadata than anything we could
  fetch.
- The agent may ask **once**, later, in conversation — *"ye reel kis baare mein
  thi?"* — and never again if ignored.

## Store the preference signal now

You said the "suggest from what the user liked" part comes later. It does — but
the signal for it has to be recorded **now**, because it cannot be backfilled.

Every capture stores:

```ts
keptAt: string;        // when it was bookmarked or shared
keptFrom: 'chat' | 'share' | 'extension';
suggestedBy?: string;  // the agent message it was kept from, if any
```

A bookmark is the strongest preference signal this app will ever get — the user
spent a tap on it. Six months of those is what makes later suggestions good, and
six months is exactly how long it takes to collect. Recording it costs three
fields today; not recording it costs half a year.

## How it is built

### Android — the share target

```xml
<activity android:name=".ShareActivity"
          android:theme="@style/Theme.Spica.BottomSheet"
          android:excludeFromRecents="true">
  <intent-filter>
    <action android:name="android.intent.action.SEND" />
    <category android:name="android.intent.category.DEFAULT" />
    <data android:mimeType="text/plain" />
    <data android:mimeType="image/*" />
  </intent-filter>
</activity>
```

- `EXTRA_TEXT` carries the URL, `EXTRA_SUBJECT` sometimes a title,
  `EXTRA_STREAM` an image
- A **bottom-sheet theme**, `excludeFromRecents` — this is a dialog, not a screen
- The write happens locally and synchronously; enrichment goes to WorkManager, so
  the sheet can close whether or not there is signal
- `shortcuts.xml` with a `<share-target>` puts Spica in the share sheet's
  **Direct Share** row rather than buried in the app list. Worth doing: the
  difference between one tap and three is the difference between a habit and not

### Frontend — what can be proven before Kotlin

The prototype cannot receive an Android intent, but it can prove the part that
actually carries risk:

- **Door 1 works fully in the web prototype.** Suggestion cards with typed items
  and a keep action, filing into the library, showing all three states
- **Door 2 is simulated** by pasting a URL into the composer — the same code path
  from "a URL arrived" onward, minus the intent plumbing

That ordering is on purpose. The filing logic and the three bookmark states are
where the design can be wrong; the intent filter is boilerplate that either works
or does not.

## Data

No new store. Library items gain the three `kept*` fields above, plus:

```ts
sourceUrl?: string;    // normalised, and the dedupe key
medium?: 'video' | 'page' | 'image' | 'text';
```

`medium` is how a thing reached you; type is what it is. *"Soya keema in 20
minutes"* used to be filed as a **video**, when it is plainly a recipe that
arrived as one — and following that all the way is what retired `article` and
`video` as types on 2026-09-06. What is left to record is the link, and the
thing it is a link *to* already has a column for it.

## Rules and edge cases

- **Sharing the same thing twice does not duplicate it.** Dedupe on the
  normalised URL — strip tracking parameters, trailing slashes, `m.` hosts.
  Second share surfaces the existing item instead of a new one.
- **Bookmarking is idempotent.** Tapping a filled star does nothing; it is not a
  toggle. Un-keeping happens where deleting happens, in Your data, deliberately.
- **Offline share still works.** It is a local write. Enrichment queues.
- **A share while the app has never been opened** must still work — no session,
  no onboarding, just store it.
- **Nothing is read that was not shared.** No clipboard, no browser history. The
  intent is the entire input.
- **Enrichment never overwrites the user.** If they typed a hint or corrected a
  category, a later fetch does not undo it.

## Testing

- Keeping a suggested recipe creates a filed library item, once
- The three bookmark states each render, and only the first is tappable
- Low-confidence filing lands in the Inbox, not in a folder
- The same URL shared twice yields one item
- A share with only a URL and no fetchable metadata still stores and confirms
- Enrichment failure leaves the item usable, in the Inbox
- A user-typed hint survives a later enrichment pass
- `keptAt` / `keptFrom` are populated on every path
- Airplane mode: share succeeds, enrichment queues, and runs on reconnect
- The share sheet closes in under a second on a cold start

## Definition of done

1. Suggestion cards carry typed items; each can be kept in one tap.
2. All three bookmark states are correct, and the "already yours" state is not a
   button.
3. Filing resolves type, path and tags without asking the user anything.
4. Anything under 70% confidence goes to the existing Inbox.
5. Spica appears in the Android share sheet for links and images, and in the
   Direct Share row.
6. A share stores and confirms before any network call, and succeeds offline.
7. Duplicate URLs collapse to one item.
8. `keptAt`, `keptFrom` and `suggestedBy` are recorded on every capture path,
   even though nothing reads them yet.
9. `medium` replaces `video`-as-a-type, and existing seed rows are migrated.
10. Web prototype proves Door 1 end to end and simulates Door 2 by paste.

## Decided against

| Option | Why not |
| --- | --- |
| Asking which folder at capture time | A bookmark that costs a form is one nobody makes twice. The agent guesses, the Inbox catches |
| Opening the full app on share | Costs the user their place in the app they shared from — the one thing a share must never do |
| Blocking the share until we understand the content | Instagram often gives only a URL. A share that can fail is a share that stops happening |
| Scraping Instagram properly | Actively blocked, breaks constantly, and the failure mode is a feature that silently rots |
| Bookmarking prose | You cannot keep a sentence. If the agent wants something kept, it has to emit a typed object |
| A star that toggles off | Deleting is a deliberate act and belongs where deleting lives. A toggle makes accidental loss one mistap away |
| Articles in v1 | The extension covers browser reading, and read-later is its own problem with its own spec |
| Waiting to add the preference fields | They cannot be backfilled. Three fields now, or start from zero later |

## Open

- **What counts as a suggestion worth keeping?** If every agent reply sprouts
  stars, the chat turns into a form. Probably only replies that name specific
  library-shaped things — needs a look once real conversations exist.
- OCR on shared screenshots: genuinely useful for a recipe photographed from a
  book, and a real dependency to take on. Later.
- The **suggestion bias** — using `keptAt` to weight what the agent proposes.
  Deferred by you, deliberately; this spec only guarantees the data exists.
- Should a shared **place** try to resolve to coordinates? Useful for
  *"paas mein kya hai"*, but it drags in a maps dependency.
