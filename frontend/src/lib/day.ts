/**
 * ISO local days — `"2026-09-13"` — are the app's identity for a day.
 *
 * A day-of-month number is not one. The 13th of September and the 13th of
 * August are the same number, so bucketing or windowing by it silently merges
 * two days a month apart: the deck read 13 August's meals as today's and
 * showed 2,698 kcal against a real 560. Every ledger row carries its
 * `local_day`; this is the arithmetic the deck and the report need on top.
 *
 * ISO days sort lexicographically in calendar order, so `>=` and `<=` are the
 * range checks — nothing needs parsing to compare two of them.
 */

const pad = (n: number) => String(n).padStart(2, '0');

/** Parsed at local midnight, so the day never shifts under a timezone. */
const parse = (iso: string) => new Date(`${iso}T00:00:00`);

const format = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

/** The device's current local day. */
export const localToday = () => format(new Date());

/**
 * An instant — a `done_at` timestamp, say — as the day it happened *here*.
 * Slicing the string would give the day in UTC, which is a different date for
 * anything ticked before 5:30am in Delhi.
 */
export const localDayOf = (ts: string) => format(new Date(ts));

/** `n` days after `iso`; negative goes back. Month lengths are `Date`'s problem. */
export function addDays(iso: string, n: number): string {
  const d = parse(iso);
  d.setDate(d.getDate() + n);
  return format(d);
}

/** Whole days from `from` to `to`. Same day is 0; `to` before `from` is negative. */
export function diffDays(from: string, to: string): number {
  return Math.round((parse(to).getTime() - parse(from).getTime()) / 86_400_000);
}

/** Every day from `from` to `to`, inclusive. Empty when `to` is before `from`. */
export function eachDay(from: string, to: string): string[] {
  const out: string[] = [];
  for (let d = from; diffDays(d, to) >= 0; d = addDays(d, 1)) out.push(d);
  return out;
}

/** Whole years from a date of birth to `today` — an age, the way a person says it. */
export function ageOn(dob: string, today: string): number {
  const years = Number(today.slice(0, 4)) - Number(dob.slice(0, 4));
  return today.slice(5) < dob.slice(5) ? years - 1 : years;
}

/** The first of `iso`'s month. */
export const monthStart = (iso: string) => `${iso.slice(0, 7)}-01`;

/** The later of two ISO days. */
export const maxDay = (a: string, b: string) => (a > b ? a : b);

/** The day-of-month — for a label or an axis tick, never for identity. */
export const dayOfMonth = (iso: string) => Number(iso.slice(8, 10));

/** Monday-indexed weekday, 0–6. `getDay()` is Sunday-indexed, hence the shift. */
export const weekIndex = (iso: string) => (parse(iso).getDay() + 6) % 7;
