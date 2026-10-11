import { DIET_TODAY_ISO } from '../data/live';
import { addDays, dayOfMonth, weekIndex } from '../lib/day';
import type { ChainDay, HabitMark, Workout } from '../types';

/** Monday first — the strip's letters have to read in the order people say them. */
export const DAY_LETTERS = ['M', 'T', 'W', 'T', 'F', 'S', 'S'];

/**
 * The calendar week containing `anchor`, Monday to Sunday.
 *
 * Deliberately not a rolling seven days ending today: rolling would leave the
 * letters in a scrambled order (`T W T F S S M`), and the only reason to label
 * marks with letters is that they read normally.
 *
 * Days are bucketed by ISO date, never by day-of-month — a week that starts in
 * the previous month is an ordinary week, and 13 August is not 13 September.
 */
export function weekChain(
  logs: { date: string; habit: string; amount?: number }[],
  anchor = DIET_TODAY_ISO,
): ChainDay[] {
  const monday = addDays(anchor, -weekIndex(anchor));
  const byDay = new Map<string, HabitMark[]>();
  for (const l of logs) {
    const list = byDay.get(l.date) ?? [];
    const seen = list.find((h) => h.habit === l.habit);
    // One coin per habit whatever the count: two cigarettes is one cigarette
    // icon reading 2, not two icons. A log with no amount counts as one.
    if (seen) seen.count += l.amount ?? 1;
    else list.push({ habit: l.habit, count: l.amount ?? 1 });
    byDay.set(l.date, list);
  }

  return DAY_LETTERS.map((letter, i) => {
    const date = addDays(monday, i);
    const habits = byDay.get(date) ?? [];
    return {
      day: dayOfMonth(date),
      date,
      letter,
      habits,
      done: habits.length > 0,
      isToday: date === anchor,
      future: date > anchor,
    };
  });
}

export function sessionsIn(workouts: Workout[], from: number, to: number): Workout[] {
  return workouts.filter((w) => w.day >= from && w.day <= to).sort((a, b) => b.day - a.day);
}

/** Days with at least one habit logged. Plain count, never a streak. */
export function weekCount(chain: ChainDay[]): number {
  return chain.filter((d) => d.done).length;
}
