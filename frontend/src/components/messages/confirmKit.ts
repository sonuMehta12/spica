import { shortDay } from '../../lib/format';
import type { ComposerContext, ConfirmField, ConfirmMsg, Meal, Todo, Tx } from '../../types';
import type { CardRows, LiveRow } from './live';

/**
 * What a confirm card reads from its payload, and the actions it can take.
 * Every action is one that already existed behind the ⋮ tray, save Undo on a
 * removed row — that one has its own route, `POST /…/{id}/restore`.
 */
export interface ConfirmActions {
  /**
   * Change: the row and its field hang on the composer as a pill, and what is
   * typed next goes to the agent after the context's words. Nothing is
   * prefilled and nothing navigates.
   */
  onContext: (ctx: ComposerContext) => void;
  /** The guess was right: the row's confidence goes to 1 — Right, Yes. */
  onConfirm: (msg: ConfirmMsg) => void;
  /** The row's route deletes it — Undo, Forget. */
  onDelete: (msg: ConfirmMsg) => void;
  /** Undo on a removed payment or meal: the row comes back live, everywhere it shows. */
  onRestore: (source: 'paisa' | 'diet', id: string) => void;
  /** Count a payment toward a commitment (or `null`: Not a commitment). */
  onLink: (txId: string, commitmentId: string | null) => void;
  /** Open the commitment sheet pre-filled from a payment. */
  onMake: (tx: Tx) => void;
  onToggleTodo: (id: string) => void;
}

/** Everything a confirm card can read beyond its payload. */
export interface ConfirmData {
  live: LiveRow;
  rows: CardRows;
  /** This month's expense rows the deck holds — the only ones that can count toward a commitment. */
  deckTx: Tx[];
  /** Every meal the client holds, for protein today. */
  meals: Meal[];
  todos: Todo[];
  /** The local day the card was written, when its id can say. */
  day: string | null;
}

export const field = (msg: ConfirmMsg, key: string): ConfirmField | undefined =>
  msg.fields.find((f) => f.key === key);

/** A field's value, with the server's "—" read as absent — unknown is not a value. */
export const val = (msg: ConfirmMsg, key: string): string | undefined => {
  const v = field(msg, key)?.value?.trim();
  return v && v !== '—' ? v : undefined;
};

const STATES = /^(added|done|updated|archived|created|deleted|already on the list|already tracked|moved to .+|no longer tracked)$/;

/** "Fix the cart bug · done" → "Fix the cart bug": the lede without its state word. */
export function ledeTitle(lede: string): string {
  const i = lede.lastIndexOf(' · ');
  return i > 0 && STATES.test(lede.slice(i + 3)) ? lede.slice(0, i) : lede;
}

/** "Fix the cart bug · done" → "done". Empty when the lede carries none. */
export function ledeState(lede: string): string {
  const i = lede.lastIndexOf(' · ');
  const tail = i > 0 ? lede.slice(i + 3) : '';
  return STATES.test(tail) ? tail : '';
}

/** "18 g", "₹1,840", "6 payments" → the number in it, or null. */
export function num(s: string | undefined): number | null {
  if (!s) return null;
  const m = /-?[\d,]*\.?\d+/.exec(s);
  if (!m) return null;
  const n = Number(m[0].replace(/,/g, ''));
  return Number.isFinite(n) ? n : null;
}

/** Grams as a person reads them: 18, 18.5 — never 18.000000001. */
export const grams = (n: number) => `${Math.round(n * 10) / 10}`;

/** "Ghar par diya (Papa ko)" → "G". */
export const initial = (s: string) => (s.trim().charAt(0) || '?').toUpperCase();

/**
 * What Change hangs on the composer. Each names the row the way the data
 * does — amounts as rupees, days as "1 Oct" — so the sentence the agent gets
 * cannot be read as a new log. The prefix is completed by what is typed:
 * "Change the category of the ₹80 Auto payment on 1 Oct to" + "transport".
 */
const on = (day: string | null | undefined) => (day ? ` on ${shortDay(day)}` : '');

/** Any field without words of its own: "Dal · weight". */
export const fieldContext = (what: string, field: string): ComposerContext => ({
  label: `${what} · ${field}`,
  prefix: `Change the ${field} of ${what} to`,
});

/** A payment's guessed category. */
export const categoryContext = (what: string, amount: string, day: string | null | undefined): ComposerContext => ({
  label: `${what} · category`,
  prefix: `Change the category of the ${amount} ${what} payment${on(day)} to`,
});

/** The review's question, said as the statement its answer completes. */
export const reviewContext = (what: string, amount: string, day: string | null | undefined): ComposerContext => ({
  label: `${what} · category`,
  prefix: `The category of the ${amount} ${what} payment${on(day)} is`,
});

/** A meal's estimated protein: "The 3 eggs I had for breakfast today actually had" + "20 g". */
export const proteinContext = (
  dish: string,
  slot: string | null | undefined,
  day: string | null | undefined,
  today: string,
): ComposerContext => ({
  label: `${dish} · protein`,
  prefix: `The ${dish} I had${slot ? ` for ${slot.toLowerCase()}` : ''}${day === today ? ' today' : on(day)} actually had`,
});

/** A target, and what it is now: "Savings target · ₹10,000". */
export const targetContext = (label: string, value: string | null): ComposerContext => ({
  label: value ? `${label} · ${value}` : label,
  prefix: `Change my ${label.toLowerCase()} to`,
});

/** No protein target yet — the meal card offers to set one. */
export const SET_PROTEIN_TARGET: ComposerContext = {
  label: 'Protein target',
  prefix: 'Set my daily protein target to',
};

/** Udhaar's kinds, as a table names them in place of a category. */
export const UDHAAR: Record<string, string> = { lent: 'Lent', borrowed: 'Borrowed', repayment: 'Repaid' };
