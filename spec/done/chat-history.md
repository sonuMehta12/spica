# Chat history: paging, and clearing the view

> Status: shipped 2026-09-13
> Surface: both

## The problem

`GET /chat` returns the last 200 messages and the client renders all of them.
That is already 195 messages after two weeks of use. At a year it is thousands,
every one of them mounted into the DOM on boot, on a phone.

And there is no way to clear the screen. The thread is deliberately permanent —
`_thread()` says *"the one thread; there is no 'new chat' and there will not be
one"* — but permanent-in-the-database and permanent-on-screen are different
promises, and only the first one was decided.

## What it does

### 1 · Paging

`GET /chat` gains a cursor:

```
GET /chat?limit=20              newest 20, plus the summary
GET /chat?limit=20&before=<seq> the 20 before that seq
```

`before` is a message `seq`, which is already a per-conversation counter and
already the sort key. No new column, no offset paging, no drift when a message
is soft-deleted mid-scroll.

The client loads the newest page on boot and asks for the previous one when the
user scrolls to the top. `HistoryOut` gains `has_more: bool` so the client knows
whether to keep offering.

**Scroll anchoring is the whole difficulty.** Prepending older messages grows
the scroll height above the viewport, so without correction the view jumps.
Record `scrollHeight` before the prepend and add the delta to `scrollTop`
after. Related: `Conversation.tsx` currently pins to the bottom whenever
`messages.length` changes, which would yank the user back down every time a
page loads. It has to pin only when a message is **appended**, keyed on the
last message's id rather than on the count.

**The page size is the client's, not the agent's.** `CHAT_WINDOW` is about
tokens and what the model can afford to read; a UI page is about DOM nodes and
one network round trip. Tying them together would mean a cost decision silently
changing a scroll experience. The client asks for what it wants and the server
caps it, which it already does.

### 2 · Clear the view

A second button in the header, immediately left of the menu, shown only when
there is more than one message. It leaves the newest message on screen and
hides everything above it.

**It is a marker, not a delete.** `conversations.cleared_through_seq`, one
migration, defaulting to 0. `GET /chat` returns messages after it. Nothing is
removed, and *"there is no new chat"* still holds: same thread, same summary,
same pointer.

**Nothing is unreachable.** At the top of a cleared thread the client shows one
line — *Older conversation hidden · Show* — which refetches from before the
marker. A clear you cannot undo is a delete wearing a friendlier word.

## The two decisions, settled

**Clearing also compacts.** It is what a person means by *"saaf kar do"* —
start fresh without the agent going stupid. Everything above the newest message
is folded into the summary on the press, so the gist survives and the words do
not. View-only was rejected: a clean screen beside an agent that still quotes
what you cleared reads as broken.

Hiding does not depend on the model. If the summariser errors, the clear is
logged and the marker is set anyway — the user asked for a clean screen, and
they get one.

**The page size is a client constant**, `CHAT_PAGE`, not an env flag. This
frontend is a prototype to be thrown away and the Android app will size its own
list widget. An env var here would be configuration for a surface that is going
to be rewritten.

## Rules and edge cases

- **Clearing an already-clear thread does nothing.** The button is hidden when
  one message or fewer sits above the marker.
- **A new turn after a clear is visible immediately.** The marker never moves
  forward on its own.
- **Paging never crosses the marker** unless the user asks for it with *Show*.
- **The summary survives a clear**, and is still sent to the model. That is the
  point of compacting rather than forgetting.
- **`limit` stays capped server-side.** A client asking for everything still
  gets at most 500.

## Decided against

- **Sharing `CHAT_WINDOW` with the UI page size.** See above: one is a token
  budget, the other is a DOM budget.
- **Offset paging (`?page=3`).** Soft deletes and new arrivals shift offsets
  under the reader. A `seq` cursor cannot drift.
- **Deleting messages on clear.** The ledger's own rule is per-item delete with
  soft deletes underneath; a bulk destroy behind a one-tap button is the
  opposite of that.
- **A "new chat" button.** Still refused, for the reason `agent.md` gives: one
  person, one continuous relationship. Clearing the view is not starting over.
- **Virtualised list instead of paging.** Solves the DOM cost and not the
  network cost, and adds a dependency to a throwaway prototype.

## Verified

`backend/tests/test_chat_history.py`, ten tests: a page is the newest N, oldest
first, and says whether more sits behind it; the cursor walks back with no gap
and no overlap; a page that covers its scope reports no more; `limit` is capped
server-side; clear hides everything but the last message and sets the marker
there; clear deletes nothing and *Show* returns every message; clear compacts,
so the model's own window is emptied and a summary is left behind; a turn after
a clear is visible; clearing twice does not move the marker; a failed
summariser still clears the screen.

Whole suite: 205 passing.

By hand in the browser, 2026-09-13:

| | |
|---|---|
| boot | one request, `GET /chat?limit=20`, 27 bubbles, pinned to the bottom |
| scroll to top | `GET /chat?limit=20&before=153`, 27 → 55 bubbles |
| anchoring | height grew 4150px, `scrollTop` moved 4112px, reader stayed put |
| clear | `POST /chat/clear`, down to one message, button hides itself |
| after reload | still one message, *Older conversation hidden · Show* offered |
| Show | `include_cleared=true`, back to 28 bubbles, row stops offering |

The clear's own summary was checked against the state that had produced a bad
one: 130 words, third person, no numbers, and the older concerns carried
forward. See `spec/done/prompt-layout.md` § *It reissues*.
