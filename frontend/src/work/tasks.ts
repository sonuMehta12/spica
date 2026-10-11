import { PROJECTS, TODAY_ISO } from '../data/live';
import { addDays, diffDays, weekIndex } from '../lib/day';
import { color } from '../theme';
import type { Project, ProjectStat, Range, Todo } from '../types';

/** How many rows the Work card shows before you have to ask for the rest. */
const HERO_TASKS = 3;

/** Sorts after every real date, so an undated task lands at the bottom. */
const NO_DATE = '9999-12-31';

export function projectOf(id: string | undefined): Project | undefined {
  return id ? PROJECTS.find((p) => p.id === id) : undefined;
}

/**
 * The window an arc counts over.
 *
 * `aaj` never reaches Work — a single day is too short to say anything about a
 * project — so it is folded into the week.
 */
/**
 * Work windows look FORWARD — whole calendar week, whole month — where paisa
 * and diet look back. A ledger's future is empty by definition; a task due
 * tomorrow belongs to this week today.
 *
 * The window is a range of ISO days, so next month's 5th no longer counts as
 * this month's.
 */
function inWindow(task: Todo, range: Range): boolean {
  if (range === 'sab') return true;
  const [start, end] = bounds(range);
  const within = (d: string | undefined) => d != null && d >= start && d <= end;
  // Finished: it belongs to the window it was finished in, or was due in.
  if (task.done) return within(task.doneOn) || within(task.due);
  // Still open: on the plate now if it is undated, due in the window, or
  // already late. Hiding the undated ones left the card at 0/0 while seven
  // tasks sat open (2026-09-27) — tasks said in chat and pulled from Linear
  // rarely carry a date. A late one dropping out of the week flattered too.
  return task.due == null || task.due <= end;
}

/** The window's first and last ISO day: the calendar week or month. */
function bounds(range: Range): [string, string] {
  if (range === '30din') {
    const [y, m] = TODAY_ISO.split('-').map(Number);
    // Day 0 of next month is the last of this one.
    const last = new Date(Date.UTC(y, m, 0)).getUTCDate();
    return [`${TODAY_ISO.slice(0, 7)}-01`, `${TODAY_ISO.slice(0, 7)}-${String(last).padStart(2, '0')}`];
  }
  const monday = addDays(TODAY_ISO, -weekIndex(TODAY_ISO));
  return [monday, addDays(monday, 6)];
}

/** `2 days late` · `Today` · `Tomorrow` · `4 days`. */
export function dueLabel(due: string | undefined): string {
  if (due == null) return 'no date';
  const d = diffDays(TODAY_ISO, due);
  if (d === 0) return 'Today';
  if (d === 1) return 'Tomorrow';
  if (d < 0) return `${-d} days late`;
  return `${d} days`;
}

/**
 * What the status column says. A finished task reports that it is finished —
 * carrying on about the date it was due would be false, since it was met.
 */
export function statusLabel(task: Todo): string {
  if (task.done) return 'done';
  return task.due == null ? '' : dueLabel(task.due);
}

/** Late is red; due today is plain ink — amber is only ever the estimate dot. */
export function dueTone(task: Todo): string {
  if (task.done) return color.faint;
  if (task.due == null) return color.faint;
  const d = diffDays(TODAY_ISO, task.due);
  if (d < 0) return color.red;
  if (d === 0) return color.ink;
  return color.muted;
}

/**
 * Overdue first, then by date, then by priority within the same day.
 * Deliberately blind to `done` — a task you tick keeps its place instead of
 * jumping out from under your finger.
 */
export function sortTasks(list: Todo[]): Todo[] {
  return [...list].sort((a, b) => {
    const ad = a.due ?? NO_DATE;
    const bd = b.due ?? NO_DATE;
    // ISO days sort lexicographically in calendar order — no parsing needed.
    if (ad !== bd) return ad < bd ? -1 : 1;
    return (a.priority ?? 9) - (b.priority ?? 9);
  });
}

/**
 * What the Work card shows: the next few tasks across every project — late
 * first, then by date, then the undated ones (`sortTasks` puts them last).
 *
 * Undated tasks are listed: they are most of what chat and Linear produce, and
 * a card that listed only dated work stood empty over seven open tasks.
 * Work finished on an earlier day is dropped — it is already counted in the
 * bars, and leaving it here would spend the card's three slots on things you
 * cannot act on. Anything ticked *today* stays, with its completed status.
 */
export function heroTasks(todos: Todo[], n = HERO_TASKS): Todo[] {
  const live = todos.filter(
    (t) => t.kind === 'work' && !(t.done && t.doneOn !== TODAY_ISO),
  );
  return sortTasks(live).slice(0, n);
}

/**
 * One bar per project.
 *
 * Deliberately not concentric arcs: nested rings read as a hierarchy these
 * three do not have, and an arc's length depends on its radius, so 50% on the
 * outer ring is physically longer than 50% on the inner one — which defeats
 * the only reason to show three projects together. Bars share a baseline.
 */
export function projectStats(todos: Todo[], range: Range): ProjectStat[] {
  return PROJECTS.map((proj) => {
    const rows = todos.filter((t) => t.project === proj.id && inWindow(t, range));
    return {
      id: proj.id,
      name: proj.name,
      color: proj.color,
      done: rows.filter((t) => t.done).length,
      total: rows.length,
      late: rows.filter((t) => !t.done && t.due != null && t.due < TODAY_ISO).length,
    };
  });
}

const KIND_LABEL: Record<Todo['kind'], string> = {
  work: 'Work',
  paisa: 'Paisa',
  diet: 'Diet',
};

export interface TaskGroup {
  key: string;
  label: string;
  color: string;
  tasks: Todo[];
}

/**
 * Tasks gathered into blocks rather than one flat date-sorted run.
 *
 * A flat list interleaves a cart bug, a gym fee and a soaking bowl by date
 * alone, and the eye has to re-orient at every row. Grouping puts like with
 * like — every project's work in one block, projects adjacent so all of work
 * reads as one region, chores after. Dates still order rows *within* a group,
 * so nothing late gets buried.
 */
export function groupTasks(todos: Todo[], scope: 'all' | 'work'): TaskGroup[] {
  // Every task has a project now — chores land in the default one — so when
  // the money and food blocks are shown below, a project block takes only
  // work, or a chore would be listed twice.
  const groups: TaskGroup[] = PROJECTS.map((proj) => ({
    key: proj.id,
    label: proj.name,
    color: proj.color,
    tasks: sortTasks(todos.filter((t) =>
      t.project === proj.id && (scope === 'work' || t.kind === 'work'))),
  }));

  // Work that never got filed under a project still has to land somewhere.
  const loose = todos.filter((t) => t.kind === 'work' && !projectOf(t.project));
  if (loose.length) {
    groups.push({ key: 'work', label: KIND_LABEL.work, color: color.work, tasks: sortTasks(loose) });
  }

  if (scope === 'all') {
    for (const kind of ['paisa', 'diet'] as const) {
      groups.push({
        key: kind,
        label: KIND_LABEL[kind],
        color: kind === 'paisa' ? color.paisa : color.diet,
        tasks: sortTasks(todos.filter((t) => t.kind === kind)),
      });
    }
  }

  return groups.filter((g) => g.tasks.length);
}

/** Everything still open, across all three surfaces. */
export function openTasks(todos: Todo[]): Todo[] {
  return todos.filter((t) => !t.done);
}
