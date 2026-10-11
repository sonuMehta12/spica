import { TODAY_ISO } from '../data/live';
import { dueLabel, sortTasks } from '../work/tasks';
import { diffDays } from '../lib/day';
import { rupees } from '../lib/format';
import type { DishRow, PantryRow, PendingItem } from '../data/api';
import type { Todo } from '../types';

/**
 * The agent's line over a card the phone built — To-do, Pantry, Cash flow,
 * your dishes — where no reply exists to say it (spec/done/card-redesign.md).
 *
 * Two clauses: **what the data says**, then **what it means next**. A single
 * observation is a caption; the second half is what makes it worth reading.
 *
 * Worked out at render time from the live rows, never stored: delete a row or
 * tick a task and the sentence re-reads correctly. It is drawn above the card,
 * in the serif — never inside it. A server card (a table) gets no note at
 * all: the agent's own reply above it is the commentary.
 */

const n = (count: number, one: string, many: string) => `${count} ${count === 1 ? one : many}`;

/** "Bread", "Bread and dahi", "Bread, dahi and 2 more". Names stay as said. */
function list(names: string[]): string {
  if (names.length <= 2) return names.join(' and ');
  if (names.length === 3) return `${names[0]}, ${names[1]} and ${names[2]}`;
  return `${names[0]}, ${names[1]} and ${names.length - 2} more`;
}

export function todoNote(todos: Todo[]): string {
  const left = todos.filter((t) => !t.done);
  if (!left.length) {
    return 'All done — nothing left for today. Say if something for tomorrow needs remembering.';
  }

  const late = left.filter((t) => t.due != null && t.due < TODAY_ISO);
  const backlog = left.filter((t) => t.kind === 'work' && t.due == null);
  const dated = sortTasks(left.filter((t) => t.due != null))[0];

  // Late work outranks everything: it is the only thing here you are already
  // behind on, and saying it first is the whole point of the line.
  if (late.length) {
    const worst = sortTasks(late)[0];
    const days = worst.due == null ? 0 : diffDays(worst.due, TODAY_ISO);
    return `${n(late.length, 'task is', 'tasks are')} past ${late.length === 1 ? 'its' : 'their'} date — ${
      late.length === 1 ? '' : 'the oldest is '
    }“${worst.name}”, ${n(days, 'day', 'days')} now. Clear that one first.`;
  }

  if (dated) {
    const rest = backlog.length
      ? ` ${backlog.length} more sit undated — whenever there is room.`
      : ' Nothing else is on a deadline.';
    return `${n(left.length, 'task', 'tasks')} left, “${dated.name}” first — ${dueLabel(
      dated.due,
    ).toLowerCase()}.${rest}`;
  }

  return `${n(left.length, 'task', 'tasks')} left, none dated. Give the important ones a date, or this pile only grows.`;
}

export function pantryNote(rows: PantryRow[], today: string): string {
  if (!rows.length) return 'Nothing in the pantry is counted yet.';

  // Oldest first: the one that has sat longest is the one to use.
  const stale = rows
    .filter((r) => r.status === 'stale')
    .sort((a, b) => (a.lastIn ?? '').localeCompare(b.lastIn ?? ''));
  const out = rows.filter((r) => r.status === 'out').map((r) => r.name);
  const low = rows.filter((r) => r.status === 'soon').map((r) => r.name);
  // "Out of" and "running low on" read right for "Eggs" and "Paneer" alike —
  // a name's own number never has to agree with a verb.
  const buy = out.length && low.length
    ? `Out of ${list(out)}, and running low on ${list(low)}.`
    : out.length
      ? `Out of ${list(out)}.`
      : low.length
        ? `Running low on ${list(low)}.`
        : '';

  if (stale.length) {
    const first = stale[0];
    const age = first.lastIn ? diffDays(first.lastIn, today) : null;
    const lead = `Use the ${first.name} first${age != null ? ` — it came in ${n(age, 'day', 'days')} ago` : ''}.`;
    return buy ? `${lead} ${buy}` : lead;
  }
  if (buy) return `${buy.slice(0, -1)} — worth adding to the next shop.`;
  return 'Nothing to use up or buy. Stock drops as meals are logged.';
}

export function dishesNote(dishes: DishRow[]): string {
  if (!dishes.length) return 'No dishes yet — save one, or log a meal that matches one.';
  const tried = dishes.filter((d) => d.tried > 0).length;
  // The uncomfortable number: kept, and never cooked.
  const idle = dishes.filter((d) => d.saved && d.tried === 0).length;
  if (!tried) {
    const kept = idle === dishes.length ? (idle === 1 ? 'saved' : 'all saved') : `${idle} saved`;
    return `None eaten yet${idle ? ` — ${kept} and never cooked.` : '.'}`;
  }
  return `${tried} of ${dishes.length} eaten${idle ? ` — ${idle} saved and never cooked.` : '.'}`;
}

/**
 * The month, as the server counts it: what is left once the committed costs
 * go out (`pool − locked`, `GET /paisa/summary`). Null while it loads.
 *
 * The card leads with that figure, so the line never says it again — it says
 * what the card cannot: that lent money is missing from it on purpose, or
 * that nothing more is free.
 */
export function flowNote(f: { cameIn: number; left: number | null; locked: number | null; pending: PendingItem[] }): string {
  if (f.left == null || f.locked == null) return "This month's numbers are still loading.";
  const owed = f.pending.reduce((a, p) => a + p.remaining, 0);
  if (f.cameIn === 0 && f.left === 0 && f.locked === 0 && owed === 0) {
    return 'Nothing has come in or gone out this month yet — the first payment starts the count.';
  }
  // Below zero has three causes, and the line names the one that is true.
  const short =
    f.left >= 0
      ? ''
      : f.cameIn === 0
        ? 'Nothing has come in this month yet — until it does, what goes out shows below zero.'
        : f.left + f.locked < 0
          ? 'More has gone out than came in this month — nothing more is free to spend.'
          : 'The committed costs are more than this month has left — nothing more is free to spend.';
  const lent = owed > 0 ? `The ${rupees(owed)} lent out is not counted until it comes back.` : '';
  if (short || lent) return [short, lent].filter(Boolean).join(' ');
  return f.locked > 0
    ? 'The committed costs are already taken out — anything spent from here comes out of what stays.'
    : 'Nothing committed is left to pay — anything spent from here comes out of what stays.';
}
