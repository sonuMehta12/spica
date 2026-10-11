import { useCallback, useReducer, useRef } from 'react';
import { toChatMsg } from '../agent/wire';
import { field, ledeState, targetContext, val } from '../components/messages/confirmKit';
import {
  deleteHabit,
  deleteMemory,
  deleteTask,
  deleteWeighIn,
  errorStatus,
  patchUser,
  sendOnboardingTurn,
  type OnboardingQuestion,
  type OnboardingTurn,
  type Profile,
  type UserPatch,
} from '../data/api';
import { PROFILE } from '../data/live';
import { localToday } from '../lib/day';
import { FIELDS } from '../state/profileEdit';
import type { ComposerContext, ConfirmMsg } from '../types';
import { AGAIN, LINES, questionsFor, type PickId } from './copy';
import { answered, loadFacts, type Facts } from './facts';
import { useSpeech } from './speech';

/**
 * Screen 3's state: the questions, the thread, and every answer's round trip.
 * spec/done/onboarding-goals.md § 3 · A little about you.
 *
 * Each answer goes to `POST /onboarding/turn`, where the onboarding agent
 * writes it through the app's own tools; each write comes back as the app's
 * own confirm card. The server keeps no history of the turns, so what spans
 * them lives here: which questions are done, and a second "Say that again?"
 * on one question, which moves on as a skip.
 *
 * It lives above the screens, so Back to screen 2 keeps the thread and the
 * picks, and a pick added there appends its question.
 */

/** How an answer card's write is taken back — the route that already does it. */
export type Undo =
  | { kind: 'profile'; body: UserPatch }
  | { kind: 'delete'; run: () => Promise<unknown> };

export type Item =
  | { kind: 'ask'; id: string; q: OnboardingQuestion }
  | { kind: 'said'; id: string; text: string; context?: string }
  | {
      kind: 'card';
      id: string;
      q: OnboardingQuestion;
      msg: ConfirmMsg;
      /** The profile column it wrote, so a later write to the same one supersedes its Undo. */
      column: string | null;
      undo: Undo | null;
      edit: ComposerContext | null;
    }
  | { kind: 'reply'; id: string; text: string };

export type CardItem = Extract<Item, { kind: 'card' }>;

export interface AboutState {
  items: Item[];
  /** The question open now; null once there is none left. */
  current: OnboardingQuestion | null;
  /** The first question has been worked out — before that the screen waits. */
  started: boolean;
  /** Answered or skipped — never asked again. */
  closed: OnboardingQuestion[];
  /** "Say that again?" so far, per question. */
  misses: Partial<Record<OnboardingQuestion, number>>;
  typed: string;
  /** Bumped to put the cursor in the answer box. */
  focus: number;
  /** A card's Edit: its words go before what is typed next. */
  edit: { ctx: ComposerContext; q: OnboardingQuestion } | null;
  /** An answer is with the agent. */
  busy: boolean;
  /** A line about something that did not go through — gone at the next try. */
  failed: string | null;
  /** Answer cards taken back. */
  undone: string[];
  /**
   * The day's cap on answers was met: every answer after it would meet it
   * too, so the questions end, and the cap's own line is the last word.
   */
  capped: boolean;
  /** The rows, read after every answer: what is asked next, and what the cards read. */
  facts: Facts | null;
}

const INITIAL: AboutState = {
  items: [],
  current: null,
  started: false,
  closed: [],
  misses: {},
  typed: '',
  focus: 0,
  edit: null,
  busy: false,
  failed: null,
  undone: [],
  capped: false,
  facts: null,
};

let seq = 0;
const nid = () => `onb-${++seq}`;

/** A profile column's value as the wire takes it, from the person as they were. */
function wireValue(p: Profile, column: keyof UserPatch): UserPatch[keyof UserPatch] {
  const def = FIELDS.find((f) => f.wire === column);
  if (!def) return null;
  const v = p[def.key];
  if (v == null) return null;
  switch (def.kind) {
    case 'rupees':
      return Math.round(Number(v) * 100);
    case 'grams':
    case 'kg':
    case 'cm':
      return String(v);
    default:
      return v as UserPatch[keyof UserPatch];
  }
}

/** The column a profile card wrote. An age is the date of birth. */
const columnOf = (msg: ConfirmMsg): keyof UserPatch | null => {
  const key = msg.fields[0]?.key;
  if (msg.source !== 'profile' || !key) return null;
  const column = key === 'age' ? 'dob' : key;
  return FIELDS.some((f) => f.wire === column) ? (column as keyof UserPatch) : null;
};

/**
 * Undo, the way the app already takes each write back: a profile fact goes
 * back to what it was before this answer — empty, on a first run; a weigh-in,
 * a habit, a memory and a task are deleted by their own routes. The name is
 * changed, never removed: its Undo puts back the name it had — Google's, on a
 * first run — and with none to go back to there is no Undo. A habit or a task
 * that was already there before this answer has nothing to undo — deleting it
 * would take away what the person had.
 */
function undoFor(msg: ConfirmMsg, before: Profile): Undo | null {
  const id = msg.rowId;
  switch (msg.source) {
    case 'profile': {
      const column = columnOf(msg);
      if (!column) return null;
      if (column === 'display_name') {
        const was = before.displayName.trim();
        return was ? { kind: 'profile', body: { display_name: was } } : null;
      }
      return { kind: 'profile', body: { [column]: wireValue(before, column) } as UserPatch };
    }
    case 'body':
      if (!id) return null;
      if (msg.fields.length === 1 && field(msg, 'weight_kg')) return { kind: 'delete', run: () => deleteWeighIn(id) };
      if (field(msg, 'direction') && ledeState(msg.lede) !== 'already tracked') return { kind: 'delete', run: () => deleteHabit(id) };
      return null;
    case 'memory':
      return id ? { kind: 'delete', run: () => deleteMemory(id) } : null;
    case 'work':
      return id && ledeState(msg.lede) === 'added' ? { kind: 'delete', run: () => deleteTask(id) } : null;
    default:
      return null;
  }
}

/**
 * Edit hangs the card on the answer box, the way Change does in the chat: what
 * is typed next arrives as a correction of that one fact — "Change my height
 * to" + "180".
 */
function editFor(msg: ConfirmMsg): ComposerContext | null {
  const quote = (s: string) => `“${s}”`;
  switch (msg.source) {
    case 'profile': {
      const f = msg.fields[0];
      return f ? targetContext(f.label, f.value && f.value !== '—' ? f.value : null) : null;
    }
    case 'body': {
      const kg = val(msg, 'weight_kg');
      if (kg && msg.fields.length === 1) return { label: `Weight · ${kg}`, prefix: 'Change my weight to' };
      const habit = val(msg, 'name');
      return habit ? { label: `${habit} · habit`, prefix: `Change the habit ${habit} to` } : null;
    }
    case 'memory': {
      const fact = val(msg, 'text');
      return fact ? { label: fact, prefix: `Change what you remember, ${quote(fact)}, to` } : null;
    }
    case 'work': {
      const task = msg.lede.split(' · ')[0];
      return task ? { label: `${task} · task`, prefix: `Change the task ${quote(task)} to` } : null;
    }
    default:
      return null;
  }
}

export function useAboutYou(picks: ReadonlySet<PickId>, onOver: () => void) {
  // The state lives in a ref and a render is asked for on each change: an
  // answer's round trip reads what it just wrote, in the same tick.
  const st = useRef<AboutState>(INITIAL);
  const [, render] = useReducer((n: number) => n + 1, 0);
  const patch = useCallback((p: Partial<AboutState> | ((s: AboutState) => Partial<AboutState>)) => {
    st.current = { ...st.current, ...(typeof p === 'function' ? p(st.current) : p) };
    render();
  }, []);

  const picked = useRef(picks);
  picked.current = picks;
  const over = useRef(onOver);
  over.current = onOver;
  const inFlight = useRef<AbortController | null>(null);

  const refresh = useCallback(async () => {
    try {
      patch({ facts: await loadFacts() });
    } catch {
      /* the cards keep what they hold; the next answer reads again */
    }
  }, [patch]);

  /**
   * Ask the next question: the first the picks ask that is not done. One never
   * asked whose facts are already on the rows is passed over — coming back
   * mid-flow, or a fact given to an earlier question, is never asked again.
   * Past the day's cap there is none, a pick added on screen 2 included.
   */
  const askNext = useCallback(() => {
    const s = st.current;
    const asked = new Set(s.items.flatMap((i) => (i.kind === 'ask' ? [i.q] : [])));
    const passed: OnboardingQuestion[] = [];
    let next: OnboardingQuestion | null = null;
    for (const q of s.capped ? [] : questionsFor(picked.current)) {
      if (s.closed.includes(q.id)) continue;
      if (!asked.has(q.id) && s.facts && answered(q.id, s.facts)) {
        passed.push(q.id);
        continue;
      }
      next = q.id;
      break;
    }
    const lastAsk = [...s.items].reverse().find((i) => i.kind === 'ask');
    patch({
      closed: [...s.closed, ...passed],
      current: next,
      started: true,
      items: next && (lastAsk?.kind !== 'ask' || lastAsk.q !== next) ? [...s.items, { kind: 'ask', id: nid(), q: next }] : s.items,
    });
  }, [patch]);

  const moveOn = useCallback(
    (q: OnboardingQuestion) => {
      patch((s) => ({ closed: s.closed.includes(q) ? s.closed : [...s.closed, q] }));
      askNext();
    },
    [patch, askNext],
  );

  /** Screen 3 entered from screen 2: read the rows once, then keep the open question or ask the next. */
  const enter = useCallback(async () => {
    if (!st.current.facts) await refresh();
    const s = st.current;
    const open = s.current;
    if (open && !s.closed.includes(open) && questionsFor(picked.current).some((q) => q.id === open)) return;
    askNext();
  }, [refresh, askNext]);

  const speechBase = useRef('');
  const speech = useSpeech((heard) => {
    const base = speechBase.current;
    patch({ typed: base && heard ? `${base} ${heard}` : base || heard });
  });
  const hush = speech.cancel;

  const send = useCallback(async () => {
    const s = st.current;
    const raw = s.typed.trim();
    if (!raw || s.busy) return;
    const edit = s.edit;
    const q = edit ? edit.q : s.current;
    if (!q) return;
    hush();
    const said: Item = { kind: 'said', id: nid(), text: raw, context: edit?.ctx.label };
    const before = s.facts?.profile ?? PROFILE;
    patch({ items: [...s.items, said], typed: '', edit: null, busy: true, failed: null });

    const ctl = new AbortController();
    inFlight.current = ctl;
    let out: OnboardingTurn;
    try {
      out = await sendOnboardingTurn(q, edit ? `${edit.ctx.prefix} ${raw}` : raw, localToday(), ctl.signal);
    } catch (e) {
      inFlight.current = null;
      const code = errorStatus(e);
      // Back cancelled it, or it failed: either way the answer goes back in
      // the box, unsent, and nothing was written.
      const unsent = (failed: string | null) =>
        patch((cur) => ({ items: cur.items.filter((i) => i.id !== said.id), typed: raw, edit, busy: false, failed }));
      if (ctl.signal.aborted) return unsent(null);
      if (code === 401) return patch({ busy: false }); // the door takes over
      if (code === 409) {
        // Finished on another device: the questions are over.
        patch({ busy: false });
        over.current();
        return;
      }
      if (code === 429) {
        // The day's cap: every answer after this one would meet it too. One
        // line says the rest can wait, and the questions end on it.
        patch((cur) => ({
          items: [...cur.items, { kind: 'reply', id: nid(), text: LINES.capped }],
          capped: true,
          busy: false,
        }));
        askNext();
        return;
      }
      return unsent(LINES.failed);
    }
    inFlight.current = null;

    const at = `chat-${Date.now()}`;
    const cards: Item[] = out.cards
      .map((c, i) => toChatMsg(c, i, at))
      .filter((m): m is ConfirmMsg => m?.kind === 'confirm')
      .map((msg) => ({ kind: 'card', id: msg.id, q, msg, column: columnOf(msg), undo: undoFor(msg, before), edit: editFor(msg) }));
    // An Edit on an earlier question's card corrects that fact; it does not
    // answer the question open now.
    const own = !edit || edit.q === st.current.current;
    const missed = own && !out.next && out.reply?.trim() === AGAIN;
    const misses = (st.current.misses[q] ?? 0) + (missed ? 1 : 0);
    // A second "Say that again?" on one question moves on as a skip.
    const giveUp = missed && misses >= 2;
    const reply: Item[] = out.reply && !giveUp ? [{ kind: 'reply', id: nid(), text: out.reply }] : [];
    // The rows are read again before the cards are drawn: a weight card reads
    // its weigh-in from that read, and a same-day correction keeps the row's
    // id — drawn first, the corrected card would show the old weight.
    const reread = refresh();
    patch((cur) => ({ items: [...cur.items, ...cards, ...reply], misses: { ...cur.misses, [q]: misses } }));
    await reread;
    if (own && (out.next || giveUp)) moveOn(q);
    patch({ busy: false });
  }, [patch, refresh, askNext, moveOn, hush]);

  const undo = useCallback(
    async (item: CardItem) => {
      const s = st.current;
      if (!item.undo || s.undone.includes(item.id)) return;
      patch({
        undone: [...s.undone, item.id],
        failed: null,
        // An Edit on the card it took back has nothing left to change.
        edit: s.edit && s.edit.ctx === item.edit ? null : s.edit,
      });
      try {
        if (item.undo.kind === 'profile') await patchUser(item.undo.body);
        else await item.undo.run();
        await refresh();
      } catch (e) {
        if (errorStatus(e) === 401) return;
        patch((cur) => ({ undone: cur.undone.filter((x) => x !== item.id), failed: LINES.undoFailed }));
      }
    },
    [patch, refresh],
  );

  return {
    state: st.current,
    enter,
    send,
    undo,
    setTyped: (typed: string) => patch({ typed }),
    /** A chip adds its word after anything already typed, comma-separated. It never sends. */
    chip: (word: string) =>
      patch((s) => ({
        typed: s.typed.trim() ? `${s.typed.replace(/[\s,]+$/, '')}, ${word}` : word,
        focus: s.focus + 1,
      })),
    startEdit: (item: CardItem) => {
      if (!item.edit) return;
      patch((s) => ({ edit: { ctx: item.edit!, q: item.q }, focus: s.focus + 1, failed: null }));
    },
    clearEdit: () => patch({ edit: null }),
    mic: () => {
      if (speech.listening) {
        speech.stop();
        return;
      }
      speechBase.current = st.current.typed.trim();
      speech.start();
    },
    speech,
    /**
     * Back, on this screen: an Edit first, then a waiting answer. True when
     * one of them took it — false means the screen should change.
     */
    back: (): boolean => {
      if (st.current.edit) {
        patch({ edit: null });
        return true;
      }
      if (inFlight.current) {
        inFlight.current.abort();
        return true;
      }
      return false;
    },
    /** Leaving the screen: nothing keeps listening, nothing keeps waiting. */
    leave: () => {
      speech.cancel();
      inFlight.current?.abort();
    },
  };
}

export type AboutYou = ReturnType<typeof useAboutYou>;
