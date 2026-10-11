import { useEffect, useLayoutEffect, useRef } from 'react';

/** How far a finger may travel and still count as a tap rather than a scroll. */
const TAP_SLOP = 8;
/** And how long it may rest — beyond this it is a long-press, not a tap. */
const TAP_MS = 500;
import AgentCard from './messages/AgentCard';
import AskCard from './messages/AskCard';
import CommitmentsCard from './messages/CommitmentsCard';
import ConfirmCard from './messages/ConfirmCard';
import type { LineHandlers } from './commitments/CommitmentLines';
import { ProposalStack } from './messages/ConfirmMoney';
import FlowCard from './messages/FlowCard';
import PantryCard from './messages/PantryCard';
import SuggestCard from './messages/SuggestCard';
import TableCard from './messages/TableCard';
import TodoCard from './messages/TodoCard';
import UserBubble from './messages/UserBubble';
import Greeting from './Greeting';
import { liveFor, msgDay, type CardRows } from './messages/live';
import { field, type ConfirmActions } from './messages/confirmKit';
import { rupees } from '../lib/format';
import { DIET_TODAY_ISO, TODAY_ISO } from '../data/live';
import { color, font, radius, space } from '../theme';
import ListeningWave from './ListeningWave';
import AgentAvatar from './Avatar';
import MessageRow, { type Side } from './messages/MessageRow';
import type { ChatMsg, ComposerContext, ConfirmMsg, Meal, Suggestion, SuggestItem, Todo, Tx } from '../types';

/** Only what you typed or said sits on the right; every card is the agent's. */
const sideOf = (m: ChatMsg): Side => (m.kind === 'user' ? 'user' : 'agent');

/** The turn a message came in — every card of one reply shares it. */
const turnOf = (id: string) => id.slice(0, id.lastIndexOf('-'));

const isProposal = (m: ChatMsg): m is ConfirmMsg =>
  m.kind === 'confirm' && m.state === 'proposed' && m.source === 'paisa';

/** One row of the thread: a message, or one turn's proposals stacked into a card. */
type Item = { kind: 'msg'; m: ChatMsg } | { kind: 'stack'; ms: ConfirmMsg[] };

/** fetchRowsByIds reads at most this many ids per request. */
const ID_BATCH = 50;

interface Props {
  messages: ChatMsg[];
  greetBody: string;
  suggestions: (Suggestion & { tap: () => void })[];
  listening: boolean;
  /** What the agent is visibly doing — drives the live row's face. */
  phase: 'idle' | 'thinking' | 'saving';
  tx: Tx[];
  meals: Meal[];
  todos: Todo[];
  /** The rest of the live rows the cards read: habits and their logs, pins, people, the pantry, the month. */
  cardRows: CardRows;
  openRow: string | null;
  onToggleRow: (id: string) => void;
  onDelete: (source: 'paisa' | 'diet', id: string) => void;
  onEdit: (source: 'paisa' | 'diet', id: string, text: string) => void;
  /** A payment counts toward a commitment (an id), or not (null). */
  onLinkPayment: (txId: string, commitmentId: string | null) => void;
  /** Make a commitment from a payment: opens the sheet pre-filled. */
  onMakeCommitment: (tx: Tx) => void;
  /** The ⋮ on a line of the commitments card. */
  commitmentHandlers: LineHandlers;
  onToggleTodo: (id: string) => void;
  /** Change on a card: the row and its field hang on the composer as a pill. */
  onContext: (ctx: ComposerContext) => void;
  /** Undo on a removed payment or meal: its restore route. */
  onRestore: (source: 'paisa' | 'diet', id: string) => void;
  /** Tapping an option on an ask card answers it as the next thing said. */
  onAnswer: (text: string) => void;
  /** Tapping empty space leaves compose mode and brings the deck back. */
  onDismissCompose: () => void;
  /** Rows chat cards named from outside the deck's window. */
  fetchedTx: Tx[];
  fetchedMeals: Meal[];
  deletedRows: string[];
  suggestLogged: Record<string, string>;
  pendingLogs: string[];
  onConfirmRow: (msg: ConfirmMsg) => void;
  onDeleteConfirm: (msg: ConfirmMsg) => void;
  onLogSuggested: (item: SuggestItem) => void;
  onSaveSuggested: (msgId: string, item: SuggestItem) => void;
  onDismissSuggested: (msgId: string, ref: string) => void;
  onNeedRows: (source: 'paisa' | 'diet', ids: string[]) => void;
  /** Resend a message that never reached the server, in place of it — about the same row, if any. */
  onRetry: (text: string, id: string, context?: ComposerContext) => void;
  /** Older pages of the thread; `chatCleared` offers what the user hid. */
  chatHasMore: boolean;
  chatLoadingOlder: boolean;
  chatCleared: number;
  onLoadOlder: (includeCleared?: boolean) => void;
}

export default function Conversation({
  messages,
  greetBody,
  suggestions,
  listening,
  phase,
  tx,
  meals,
  todos,
  cardRows,
  openRow,
  onToggleRow,
  onDelete,
  onEdit,
  onLinkPayment,
  onMakeCommitment,
  commitmentHandlers,
  onToggleTodo,
  onContext,
  onRestore,
  onAnswer,
  onDismissCompose,
  fetchedTx,
  fetchedMeals,
  deletedRows,
  suggestLogged,
  pendingLogs,
  onConfirmRow,
  onDeleteConfirm,
  onLogSuggested,
  onSaveSuggested,
  onDismissSuggested,
  onNeedRows,
  onRetry,
  chatHasMore,
  chatLoadingOlder,
  chatCleared,
  onLoadOlder,
}: Props) {
  // The deck's rows first; fetched rows fill in what the window does not hold.
  const allTx = [...tx, ...fetchedTx.filter((f) => !tx.some((t) => t.id === f.id))];
  const allMeals = [...meals, ...fetchedMeals.filter((f) => !meals.some((m) => m.id === f.id))];
  // "Logged" on a dish card is read from the ledger — a meal today by that
  // name — so it survives a reload without the card storing a claim.
  const loggedRefs = (items: SuggestItem[]) =>
    new Set(items
      .filter((it) => suggestLogged[it.ref]
        || (it.type === 'dish' && allMeals.some((m) => (m.date ?? DIET_TODAY_ISO) === DIET_TODAY_ISO && !m.deleted && m.name === it.name)))
      .map((it) => it.ref));
  const ledeOf = (rowId: string | null) => {
    if (!rowId) return null;
    const t = allTx.find((x) => x.id === rowId);
    if (t) return `${rupees(t.amt)} · ${t.name}`;
    const m = allMeals.find((x) => x.id === rowId);
    return m ? `${m.name} · ${m.p} g protein` : null;
  };
  const confirmActions: ConfirmActions = {
    onContext,
    onConfirm: onConfirmRow,
    onDelete: onDeleteConfirm,
    onRestore,
    onLink: onLinkPayment,
    onMake: onMakeCommitment,
    onToggleTodo,
  };

  // A confirm card reads its live row, and a row from outside the deck's
  // window is asked for by id, as a table's are — until it arrives the card
  // draws from its payload. A dish save names a dish, not a meal. A card
  // built by a delete asks too: its row may have been put back since.
  const wanted = (source: 'paisa' | 'diet') =>
    messages
      .filter((m): m is ConfirmMsg => m.kind === 'confirm' && m.source === source && m.rowId != null)
      .filter((m) => source === 'paisa' || !field(m, 'name'))
      .map((m) => m.rowId!)
      .filter((id) => !(source === 'paisa' ? allTx : allMeals).some((r) => r.id === id));
  const wantTx = [...new Set(wanted('paisa'))].join(',');
  const wantMeals = [...new Set(wanted('diet'))].join(',');
  useEffect(() => {
    for (const [source, key] of [['paisa', wantTx], ['diet', wantMeals]] as const) {
      const ids = key ? key.split(',') : [];
      for (let i = 0; i < ids.length; i += ID_BATCH) onNeedRows(source, ids.slice(i, i + ID_BATCH));
    }
  }, [wantTx, wantMeals, onNeedRows]);

  // One turn's proposals stack into one card: fourteen questions are asked
  // one at a time, "1 of 14", not as a wall of forms.
  const items: Item[] = [];
  for (const m of messages) {
    const last = items[items.length - 1];
    if (isProposal(m) && last?.kind === 'stack' && turnOf(last.ms[0].id) === turnOf(m.id)) last.ms.push(m);
    else if (isProposal(m)) items.push({ kind: 'stack', ms: [m] });
    else items.push({ kind: 'msg', m });
  }

  const body = useRef<HTMLDivElement>(null);
  const touch = useRef<{ x: number; y: number; t: number } | null>(null);
  const newest = messages.length ? messages[messages.length - 1].id : '';

  // Pin to the newest message when one ARRIVES — keyed on the last message's
  // id, not on the count. On the count, prepending an older page would read as
  // "something new" and yank the reader straight back to the bottom.
  useEffect(() => {
    const el = body.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [newest]);

  // Prepending grows the scroll height above the viewport, so without this the
  // view jumps by exactly the height of the page that just arrived. Measure
  // before, restore after.
  const anchor = useRef<number | null>(null);
  const oldest = messages.length ? messages[0].id : '';
  useLayoutEffect(() => {
    const el = body.current;
    if (el && anchor.current != null) {
      el.scrollTop += el.scrollHeight - anchor.current;
      anchor.current = null;
    }
  }, [oldest]);

  const askForOlder = (includeCleared = false) => {
    const el = body.current;
    anchor.current = el ? el.scrollHeight : null;
    onLoadOlder(includeCleared);
  };

  // The mascot is only ever on this row: the agent's replies have no face
  // beside them, so the one face on screen is always the working one.
  const liveRow = listening || phase !== 'idle';

  const render = (m: ChatMsg) => {
    switch (m.kind) {
      case 'user':
        return (
          <UserBubble
            text={m.text}
            context={m.context?.label}
            failed={m.failed}
            onRetry={() => onRetry(m.text, m.id, m.context)}
          />
        );
      case 'agent':
        return <AgentCard msg={m} />;
      case 'table':
        return (
          <TableCard
            msg={m}
            tx={allTx}
            meals={allMeals}
            deletedRows={deletedRows}
            proteinTarget={cardRows.profile.proteinTarget}
            openRow={openRow}
            onToggleRow={onToggleRow}
            onDelete={onDelete}
            onEdit={onEdit}
            commitments={cardRows.commitments?.items ?? []}
            link={{ onLink: onLinkPayment, onMake: onMakeCommitment }}
            onNeedRows={onNeedRows}
          />
        );
      case 'flow':
        return <FlowCard limit={cardRows.limitInfo} pending={cardRows.pending} />;
      case 'todo':
        return <TodoCard todos={todos} scope={m.scope} project={m.project} agent={m.agent} onToggle={onToggleTodo} />;
      case 'commitments':
        return <CommitmentsCard page={cardRows.commitments} handlers={commitmentHandlers} />;
      case 'pantry':
        return <PantryCard msg={m} pantry={cardRows.pantry} dishes={cardRows.dishes} today={TODAY_ISO} />;
      case 'confirm':
        return (
          <ConfirmCard
            msg={m}
            data={{
              live: liveFor(m, allTx, allMeals, deletedRows),
              rows: cardRows,
              deckTx: tx,
              meals: allMeals,
              todos,
              day: msgDay(m.id),
            }}
            actions={confirmActions}
          />
        );
      case 'suggest':
        return (
          <SuggestCard
            msg={m}
            loggedRefs={loggedRefs(m.items)}
            pendingRefs={pendingLogs}
            onLog={onLogSuggested}
            onSave={onSaveSuggested}
            onDismiss={onDismissSuggested}
          />
        );
      case 'ask':
        return <AskCard msg={m} pending={ledeOf(m.pendingRowId)} onAnswer={onAnswer} />;
    }
  };

  return (
    <div
      ref={body}
      className="scroll-y"
      // Tapping empty space leaves compose mode. `pointerdown` alone cannot be
      // used: on a phone every scroll starts with one, which is why this only
      // fires after a press that barely moved. Taps inside a bubble are left
      // alone — they may be hitting a button or selecting text to copy.
      onPointerDown={(e) => {
        touch.current = { x: e.clientX, y: e.clientY, t: e.timeStamp };
      }}
      onPointerUp={(e) => {
        const start = touch.current;
        touch.current = null;
        if (!start) return;
        const moved = Math.hypot(e.clientX - start.x, e.clientY - start.y);
        if (moved > TAP_SLOP || e.timeStamp - start.t > TAP_MS) return;
        if (e.target instanceof Element && e.target.closest('[data-bubble]')) return;
        const el = document.activeElement;
        if (el instanceof HTMLElement) el.blur();
        onDismissCompose();
      }}
      onPointerCancel={() => {
        touch.current = null;
      }}
      onScroll={(e) => {
        // Near the top and there is more: fetch the previous page. A sentinel
        // observer would do the same job and add a dependency to the web version.
        if (e.currentTarget.scrollTop < 80 && chatHasMore && !chatLoadingOlder) {
          askForOlder(false);
        }
      }}
      // The thread fades in over its top 24px rather than being cut flat at the
      // deck's edge — a sliced line read as the card lying on the text.
      style={{
        flex: 1,
        padding: `0 ${space.gutter}px 118px`,
        WebkitMaskImage: 'linear-gradient(to bottom, transparent, black 24px)',
        maskImage: 'linear-gradient(to bottom, transparent, black 24px)',
      }}
    >
      {/* What sits above the top of the thread. Paging is automatic; revealing
          what the user chose to hide is not — that takes a tap. */}
      {(chatLoadingOlder || (!chatHasMore && chatCleared > 0)) && (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '6px 0 10px' }}>
          {chatLoadingOlder ? (
            <span style={{ fontFamily: font.sans, fontSize: 11, color: color.faint }}>
              Loading older…
            </span>
          ) : (
            <button
              type="button"
              onClick={() => askForOlder(true)}
              style={{
                fontFamily: font.sans,
                fontSize: 12,
                padding: '5px 12px',
                borderRadius: radius.pill,
                border: `1px solid ${color.border}`,
                background: color.white,
                color: color.muted,
                cursor: 'pointer',
              }}
            >
              Older conversation hidden · Show
            </button>
          )}
        </div>
      )}

      <Greeting body={greetBody} suggestions={suggestions} />

      {items.map((it, i) => {
        // The greeting above is the agent's, so a run can already be in progress
        // at i === 0.
        const head = it.kind === 'msg' ? it.m : it.ms[0];
        const side = sideOf(head);
        const prev = items[i - 1];
        const prevSide = !prev ? 'agent' : sideOf(prev.kind === 'msg' ? prev.m : prev.ms[0]);
        return (
          <MessageRow key={head.id} side={side} newSpeaker={side !== prevSide}>
            {it.kind === 'stack' ? (
              <ProposalStack
                msgs={it.ms}
                tx={allTx}
                deletedRows={deletedRows}
                onConfirm={onConfirmRow}
                onContext={onContext}
                onRestore={onRestore}
              />
            ) : (
              render(it.m)
            )}
          </MessageRow>
        );
      })}

      {/* One live row at the end of the transcript carries the whole sequence —
          listening, then thinking, then the lock — and disappears when the
          reply lands. Faces above it stay idle: an avatar next to a message
          from ten minutes ago is a portrait, not a working agent. */}
      {liveRow && (
        <div
          style={{
            display: 'flex',
            gap: 10,
            alignItems: 'center',
            marginTop: messages.length && sideOf(messages[messages.length - 1]) === 'agent' ? space.sameSpeaker : space.newSpeaker,
          }}
        >
          <AgentAvatar state={listening ? 'listening' : phase} />
          {listening && <ListeningWave />}
          {/* A word, because a spinning arc alone does not say the agent is
              reading. Finishing needs no word: the reply row's face closes its
              ring and holds the sparks. `role=status` so a screen reader hears
              the change without the row being focused. */}
          {!listening && phase === 'thinking' && (
            <span
              role="status"
              aria-live="polite"
              style={{ fontFamily: font.sans, fontSize: 12.5, color: color.muted }}
            >
              Thinking…
            </span>
          )}
        </div>
      )}
    </div>
  );
}
