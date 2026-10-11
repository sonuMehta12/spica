import { mealTypeNow } from '../data/api';
import { addDays } from './day';
import { rupees } from './format';
import type { Meal, Tx } from '../types';

/**
 * The greeting's quick chips: your own most repeated entries, worked out from
 * the rows at render time and never stored. The Android app's `logic/Chips.kt`
 * is the same rule, line for line.
 */

/** How far back a habit is looked for. */
export const WINDOW_DAYS = 30;
/** One chai is not a habit. */
export const MIN_TIMES = 2;
export const TOP = 3;

/** A chip: what it shows, and the sentence a tap sends. */
export interface Pick {
  id: string;
  name: string;
  tag: string;
  send: string;
}

interface Seen {
  key: string;
  name: string;
  times: number;
  last: string;
  amount: number;
}

/** The name as said, case and spacing aside. */
const keyOf = (name: string) => name.trim().toLowerCase().replace(/\s+/g, ' ');

/**
 * Groups by the name as said, case and spacing aside. The newest row names
 * the chip; the most frequent amount is its usual one, ties to the newest.
 * Ranked by how often, then how recently.
 */
function rank<R>(
  rows: R[],
  today: string,
  name: (r: R) => string,
  day: (r: R) => string,
  amount: (r: R) => number,
): Seen[] {
  const from = addDays(today, -(WINDOW_DAYS - 1));
  const groups = new Map<string, R[]>();
  for (const r of rows) {
    const d = day(r);
    if (d < from || d > today || !name(r).trim()) continue;
    const k = keyOf(name(r));
    const g = groups.get(k);
    if (g) g.push(r);
    else groups.set(k, [r]);
  }
  const seen: Seen[] = [];
  for (const [key, group] of groups) {
    if (group.length < MIN_TIMES) continue;
    // Newest day first; a stable sort, as Kotlin's `sortedByDescending` is.
    const newestFirst = [...group].sort((a, b) => (day(a) < day(b) ? 1 : day(a) > day(b) ? -1 : 0));
    const counts = new Map<number, number>();
    for (const r of newestFirst) counts.set(amount(r), (counts.get(amount(r)) ?? 0) + 1);
    const top = Math.max(...counts.values());
    const usual = amount(newestFirst.find((r) => counts.get(amount(r)) === top)!);
    seen.push({ key, name: name(newestFirst[0]).trim(), times: group.length, last: day(newestFirst[0]), amount: usual });
  }
  return seen
    .sort((a, b) => b.times - a.times || (a.last < b.last ? 1 : a.last > b.last ? -1 : 0))
    .slice(0, TOP);
}

/** Paisa: "Chai ₹20". Money coming in is not a spend. */
export function spendChips(tx: Tx[], today: string): Pick[] {
  return rank(
    tx.filter((t) => !t.credit && !t.deleted && !t.failed),
    today,
    (t) => t.name,
    (t) => t.date ?? today,
    (t) => t.amt,
  ).map((s) => ({ id: `spend:${s.key}`, name: s.name, tag: rupees(s.amount), send: `${s.name} ${rupees(s.amount)}` }));
}

/** Diet: the dish, sent with the slot the clock says — "Lunch: dal chawal". */
export function mealChips(meals: Meal[], today: string, slot: string = mealTypeNow()): Pick[] {
  return rank(
    meals.filter((m) => !m.deleted && !m.failed),
    today,
    (m) => m.name,
    (m) => m.date ?? today,
    () => 0,
  ).map((s) => ({ id: `meal:${s.key}`, name: s.name, tag: '', send: `${slot}: ${s.name}` }));
}
