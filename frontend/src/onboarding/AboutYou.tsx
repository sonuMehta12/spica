import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { ArrowCounterClockwise, PencilSimple } from '@phosphor-icons/react';
import AgentAvatar from '../components/Avatar';
import InputBar from '../components/InputBar';
import ConfirmCard from '../components/messages/ConfirmCard';
import type { ConfirmActions } from '../components/messages/confirmKit';
import { msgDay, type CardRows } from '../components/messages/live';
import MessageRow from '../components/messages/MessageRow';
import UserBubble from '../components/messages/UserBubble';
import { agentVoice } from '../components/messages/bubble';
import { TextBtn } from '../components/messages/parts';
import { HABIT_LOGS, PROFILE, seedTodos } from '../data/live';
import { color, font, inset, radius, space } from '../theme';
import { LINES, LISTENING, PLACEHOLDER, question } from './copy';
import { BigButton, Screen, TopBar } from './parts';
import type { AboutYou as About, CardItem, Item } from './useAboutYou';

/**
 * Screen 3 · A little about you. The app's own chat parts on a screen of their
 * own: the agent's serif, your tint pill, the composer, and every write shown
 * back as the app's own confirm card with Edit and Undo under it.
 * spec/done/onboarding-goals.md § 3.
 */

/** The cards here act only through Edit and Undo; their own quiet actions are not drawn. */
const IDLE: ConfirmActions = {
  onContext: () => undefined,
  onConfirm: () => undefined,
  onDelete: () => undefined,
  onRestore: () => undefined,
  onLink: () => undefined,
  onMake: () => undefined,
  onToggleTodo: () => undefined,
};

/**
 * The composer's band before it is first measured — one line, no chips — and
 * the room kept clear above it, past its fade, so the newest line is never
 * under it.
 */
const BAND = 82;
const CLEAR = 36;

const sideOf = (it: Item) => (it.kind === 'said' ? 'user' : 'agent');

/** Two cards holding the same row — a weigh-in corrected the same day keeps its id. */
const sameRow = (a: CardItem, b: CardItem) =>
  a.msg.rowId != null && a.msg.rowId === b.msg.rowId && a.msg.source === b.msg.source;

export default function AboutYou({
  about,
  onBack,
  onSkip,
  onContinue,
}: {
  about: About;
  /** The ←: what the browser's back does here — an Edit cleared, else screen 2. */
  onBack: () => void;
  onSkip: () => void;
  onContinue: () => void;
}) {
  const s = about.state;
  const done = s.started && s.current == null;
  const composing = !done || s.edit != null;
  const chips = !s.edit && s.current ? question(s.current).chips : [];
  // Nothing given at all, though something was asked: the facts can come later.
  const gaveNothing = !s.items.some((i) => i.kind === 'card') && s.items.some((i) => i.kind === 'ask');

  // No composer, no listening: the recogniser would go on filling a box that
  // is not on screen, and the person would come back to words they never saw.
  const hush = about.speech.cancel;
  useEffect(() => {
    if (!composing) hush();
  }, [composing, hush]);

  // Room under the thread for the composer's band, as tall as it really is:
  // the chips wrap to two rows on a phone, an Edit adds its pill, a long
  // answer grows the field. A fixed guess hides the newest line under any of them.
  const [band, setBand] = useState(BAND);
  const measure = useCallback((el: HTMLDivElement | null) => {
    if (!el) return;
    const ro = new ResizeObserver(() => setBand(el.offsetHeight));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // The newest line in view: an answer, its cards, the next question.
  const thread = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = thread.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [s.items.length, s.busy, s.failed, done, band]);

  // What the cards read live: the person and their habits, as of the last answer.
  const rows: CardRows = {
    pantry: [],
    dishes: [],
    habits: s.facts?.habits ?? [],
    habitLogs: HABIT_LOGS,
    people: [],
    exercises: [],
    places: [],
    limitInfo: null,
    commitments: null,
    pending: [],
    borrowed: [],
    repayments: [],
    profile: s.facts?.profile ?? PROFILE,
  };

  const cards = s.items.filter((x): x is CardItem => x.kind === 'card');
  const card = (it: CardItem, index: number) => {
    // Taken back: this card, or another holding the same row whose Undo
    // deleted it — the row is gone from under both.
    const gone =
      s.undone.includes(it.id) ||
      cards.some((x) => x.undo?.kind === 'delete' && s.undone.includes(x.id) && sameRow(x, it));
    // A later write holds the value now — to the same profile column, or to
    // the same row with an Undo of its own: undoing this one would quietly
    // overwrite it, or delete the correction from under the later card.
    const superseded = s.items
      .slice(index + 1)
      .some(
        (x) =>
          x.kind === 'card' &&
          !s.undone.includes(x.id) &&
          ((it.column != null && x.column === it.column) || (x.undo != null && sameRow(x, it))),
      );
    const canUndo = it.undo != null && !superseded;
    // Past the day's cap a correction would only meet it again.
    const canEdit = it.edit != null && !s.capped;
    const quiet: ReactNode =
      gone || (!canEdit && !canUndo) ? null : (
        <>
          {canEdit && <TextBtn label="Edit" icon={PencilSimple} onClick={() => about.startEdit(it)} />}
          {canUndo && <TextBtn label="Undo" icon={ArrowCounterClockwise} onClick={() => void about.undo(it)} />}
        </>
      );
    return (
      <ConfirmCard
        msg={it.msg}
        data={{ live: { deleted: gone }, rows, deckTx: [], meals: [], todos: seedTodos, day: msgDay(it.msg.id) }}
        actions={IDLE}
        quiet={quiet}
      />
    );
  };

  const line = (text: string) => <div style={agentVoice}>{text}</div>;

  const rendered: { key: string; side: 'agent' | 'user'; node: ReactNode }[] = [];
  s.items.forEach((it, index) => {
    const side = sideOf(it);
    switch (it.kind) {
      case 'ask':
        question(it.q).says.forEach((text, n) => rendered.push({ key: `${it.id}-${n}`, side, node: line(text) }));
        break;
      case 'said':
        rendered.push({ key: it.id, side, node: <UserBubble text={it.text} context={it.context} /> });
        break;
      case 'card':
        rendered.push({ key: it.id, side, node: card(it, index) });
        break;
      case 'reply':
        rendered.push({ key: it.id, side, node: line(it.text) });
        break;
    }
  });
  // Lines worked out now, never kept: a failure until the next try, and the
  // end — unless the day's cap ended it, whose own line already said so.
  if (s.failed) rendered.push({ key: 'failed', side: 'agent', node: line(s.failed) });
  if (done && !s.busy && !s.capped) {
    rendered.push({ key: 'done', side: 'agent', node: line(gaveNothing ? LINES.nothing : LINES.done) });
  }

  const chipRow =
    chips.length > 0 ? (
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, padding: '0 4px 10px' }}>
        {chips.map((c) => (
          <button
            key={c}
            type="button"
            onClick={() => about.chip(c)}
            className="hov-chip"
            style={{
              height: 34,
              padding: '0 14px',
              borderRadius: radius.pill,
              border: `1px solid ${color.chipBorder}`,
              background: color.chip,
              color: color.ink,
              fontFamily: font.sans,
              fontSize: 14,
              cursor: 'pointer',
              transition: 'background 0.15s, border-color 0.15s',
            }}
          >
            {c}
          </button>
        ))}
      </div>
    ) : undefined;

  const last = rendered[rendered.length - 1];

  return (
    <Screen>
      <TopBar onBack={onBack} onSkip={onSkip} />
      <div
        ref={thread}
        className="scroll-y"
        style={{
          flex: '1 1 auto',
          minHeight: 0,
          padding: `8px ${space.gutter + 4}px ${composing ? band + CLEAR : 16}px`,
          WebkitMaskImage: 'linear-gradient(to bottom, transparent, black 24px)',
          maskImage: 'linear-gradient(to bottom, transparent, black 24px)',
        }}
      >
        {/* Pushed to the bottom while short, like a conversation. */}
        <div style={{ minHeight: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', paddingTop: 16 }}>
          {rendered.map((r, i) => (
            <MessageRow key={r.key} side={r.side} first={i === 0} newSpeaker={i > 0 && rendered[i - 1].side !== r.side}>
              {r.node}
            </MessageRow>
          ))}
          {/* The mark beside the thread, thinking, while the agent reads. */}
          {s.busy && (
            <div
              style={{
                display: 'flex',
                gap: 10,
                alignItems: 'center',
                marginTop: last && last.side === 'agent' ? space.sameSpeaker : space.newSpeaker,
              }}
            >
              <AgentAvatar state="thinking" />
              <span role="status" aria-live="polite" style={{ fontFamily: font.sans, fontSize: 12.5, color: color.muted }}>
                Thinking…
              </span>
            </div>
          )}
        </div>
      </div>

      {composing ? (
        <InputBar
          typed={s.typed}
          focusKey={s.focus}
          onType={about.setTyped}
          onSend={() => void about.send()}
          onMic={about.speech.supported ? about.mic : undefined}
          listening={about.speech.listening}
          waiting={s.busy || !s.started}
          label="Your answer"
          micLabel="Answer by voice"
          canLog
          hint={about.speech.listening ? LISTENING : PLACEHOLDER}
          onComposing={() => undefined}
          context={s.edit?.ctx ?? null}
          onClearContext={about.clearEdit}
          above={chipRow}
          bandRef={measure}
        />
      ) : (
        <div style={{ flex: '0 0 auto', padding: `12px ${space.gutter}px ${inset.bottom}` }}>
          <BigButton label="Continue" onClick={onContinue} />
        </div>
      )}
    </Screen>
  );
}
