import { ulid } from '../lib/ulid';
/**
 * The one file that knows both shapes.
 *
 * The server speaks the database's language — `local_day: "2026-08-22"`,
 * `amount_paise: 30900`, ULID ids. The web version speaks its own — `day: 22`,
 * `amt: 309`. Everything downstream (`metrics.ts`, `tasks.ts`, `workouts.ts`)
 * keeps working on the web version's types, unchanged, because the translation
 * stops here.
 *
 * That boundary is the point: Android will read the same endpoint and write
 * its own translator. Neither client's convenience leaks into the API.
 */

import { localDayOf } from '../lib/day';
import type { Meal, Project, Todo, Tx, Workout } from '../types';
import { getToken, setToken, signedOut } from './session';

export { getToken, setToken, onSignedOut } from './session';

// The API lives next to whoever served the page: on the laptop that is
// localhost, on a phone on the same Wi-Fi it is the laptop's LAN address. A
// hardcoded localhost would point the phone at itself.
const BASE = import.meta.env.VITE_API ?? `http://${window.location.hostname}:8001`;

/* ─── wire types: exactly what /deck sends ────────────────────────────── */

export interface WireTx {
  id: string;
  local_day: string;
  amount_paise: number;
  direction: string;
  confidence: number;
  kind: string;
  category: string;
  description: string;
  tags: string[];
  settles_id: string | null;
  /** The commitment this payment counts toward. Linked means committed, not discretionary. */
  commitment_id: string | null;
  /** The link was guessed from the category — an amber dot until moved or confirmed. */
  commitment_inferred: boolean;
}

interface WireMeal {
  id: string;
  local_day: string;
  meal_type: string;
  dish: string;
  kcal: number;
  /** NUMERIC arrives as a string so the decimal survives the trip. */
  protein_g: string;
  carbs_g: string | null;   // null = not known
  fat_g: string | null;
  confidence: number;
}

interface WireHabitLog {
  id: string;
  habit_id: string;
  local_day: string;
  amount: number | null;
  note: string | null;
}

interface WireTask {
  id: string;
  title: string;
  status: string;
  done_at: string | null;
  due: string | null;
  priority: number | null;
  labels: string[];
  project_id: string | null;
  /** The model chose the project — drawn with the amber dot. */
  project_guessed: boolean;
  source: string;
  source_ref: string | null;
  doc_ref: string | null;
  repo: string | null;
  path: string | null;
  line: number | null;
  /** A tracker's stage in the team's own word — "In Progress". */
  source_state: string | null;
  tracked: boolean;
  /** Done here, not yet moved in the tracker. Derived on the server. */
  awaiting_move: boolean;
  /** The meeting a task came from. */
  source_title: string | null;
}

interface WireProject {
  id: string;
  key: string;
  name: string;
  color: string;
  description: string | null;
  /** An emoji, or `icon:<name>` from the app's set. */
  icon: string | null;
  aliases: string[];
  is_default: boolean;
}

interface WireBalance {
  as_of: string;
  amount_paise: number;
}

interface Deck {
  from: string | null;
  to: string;
  profile: WireUser;
  paisa: { transactions: WireTx[]; balance_check: WireBalance | null };
  diet: {
    meals: WireMeal[];
    habits: { id: string; name: string }[];
    habit_logs: WireHabitLog[];
    days: { local_day: string; sleep_hours: number | null }[];
  };
  work: { projects: WireProject[]; tasks: WireTask[] };
  onboarding: WireOnboarding;
}

/**
 * Whether the first run is behind them — finished or skipped
 * (spec/done/onboarding-goals.md § Which flag). The server still sends an empty
 * `steps` beside it for older builds; nothing here reads it.
 */
export interface WireOnboarding {
  done_at: string | null;
}

/** The categories `users` holds, as the wire spells them. */
export type Gender = 'female' | 'male' | 'other';
export type Diet = 'veg' | 'nonveg' | 'eggetarian' | 'any';

/** The users row as served: NUMERICs arrive as strings. */
export interface WireUser {
  id: string;
  display_name: string;
  email: string | null;
  avatar_url: string | null;
  onboarding_done_at: string | null;
  dob: string | null;
  gender: Gender | null;
  height_cm: string | null;
  city: string | null;
  diet: Diet | null;
  timezone: string;
  savings_target_paise: number | null;
  kcal_target: number | null;
  protein_g_target: string | null;
  carbs_g_target: string | null;
  fat_g_target: string | null;
  fibre_g_target: string | null;
  weight_target_kg: string | null;
  sleep_target_min: number | null;
  step_target: number | null;
  updated_at: string;
}

export interface WireMemory {
  id: string;
  slug: string;
  kind: string;
  text: string;
  source: string;
  confirmed_at: string | null;
  updated_at: string;
}

export interface WireWeighIn {
  id: string;
  local_day: string;
  weight_kg: string;
  /** Said as a guess ("around 72"). An exact reading the same day clears it. */
  estimated: boolean;
  note: string | null;
}

/* ─── what the app gets back ──────────────────────────────────────────── */

/**
 * The person, as the app reads it. Every target is nullable: unset is unset,
 * and a ring with no target shows its value with no denominator rather than
 * an invented one. Money in rupees, macros in grams, sleep in minutes.
 */
export interface Profile {
  id: string;
  displayName: string;
  /** From Google, and shown in the Profile header: the only place that answers
   *  *which account am I signed in as*. */
  email: string | null;
  avatarUrl: string | null;
  onboardingDoneAt: string | null;
  /** An age said as "28" is 1 January of the birth year — shown as an age, never as the date. */
  dob: string | null;
  gender: Gender | null;
  heightCm: number | null;
  city: string | null;
  diet: Diet | null;
  timezone: string;
  savingsTarget: number | null;
  kcalTarget: number | null;
  proteinTarget: number | null;
  carbsTarget: number | null;
  fatTarget: number | null;
  fibreTarget: number | null;
  weightTargetKg: number | null;
  sleepTargetMin: number | null;
  stepTarget: number | null;
}

export interface MemoryRow {
  id: string;
  slug: string;
  kind: string;
  text: string;
  source: string;
  /** Null means nobody has said "still true" — shown as inferred. */
  confirmedAt: string | null;
  pending?: boolean;
  failed?: boolean;
}

export interface WeighInRow {
  id: string;
  day: string;
  kg: number;
  /** The amber dot, until an exact reading replaces it. */
  estimated: boolean;
  pending?: boolean;
  failed?: boolean;
}

const num = (v: string | number | null | undefined): number | null =>
  v == null ? null : Number(v);

export function toProfile(w: WireUser): Profile {
  return {
    id: w.id,
    displayName: w.display_name,
    email: w.email,
    avatarUrl: w.avatar_url,
    onboardingDoneAt: w.onboarding_done_at,
    dob: w.dob,
    gender: w.gender,
    heightCm: num(w.height_cm),
    city: w.city,
    diet: w.diet,
    timezone: w.timezone,
    savingsTarget: w.savings_target_paise == null ? null : paise(w.savings_target_paise),
    kcalTarget: w.kcal_target,
    proteinTarget: num(w.protein_g_target),
    carbsTarget: num(w.carbs_g_target),
    fatTarget: num(w.fat_g_target),
    fibreTarget: num(w.fibre_g_target),
    weightTargetKg: num(w.weight_target_kg),
    sleepTargetMin: w.sleep_target_min,
    stepTarget: w.step_target,
  };
}

export const toMemory = (w: WireMemory): MemoryRow => ({
  id: w.id,
  slug: w.slug,
  kind: w.kind,
  text: w.text,
  source: w.source,
  confirmedAt: w.confirmed_at,
});

export const toWeighIn = (w: WireWeighIn): WeighInRow => ({
  id: w.id,
  day: w.local_day,
  kg: Number(w.weight_kg),
  estimated: Boolean(w.estimated),
});

export interface HabitLogRow {
  id: string;
  day: number;
  /** ISO local day — the month a report row prints comes from here. */
  date: string;
  habit: string;
  amount?: number;
  note?: string;
}

export interface DeckData {
  today: number;
  /** The anchor as an ISO local day — the identity behind `today`, which is
   *  only its day-of-month and cannot tell two months apart. */
  todayISO: string;
  month: number;
  year: number;
  monthDays: number;
  /** This month's spendable expenses — what the limit and the categories are about. */
  tx: Tx[];
  /** This month's payments that count toward a commitment: paid, never spendable. The pale arc. */
  committedTx: Tx[];
  /** An income row landed on the anchor day — the day to say what is locked. */
  salaryToday: boolean;
  meals: Meal[];
  workouts: Workout[];
  /** Every habit log, with its id so the report can delete one. The strip
   *  derives its per-day stacks from these. */
  habitLogs: HabitLogRow[];
  /** Nights with a recorded sleep — the 3 real ones, nothing invented. */
  sleep: { day: number; date: string; hours: number }[];
  todos: Todo[];
  projects: Project[];
  /**
   * The last STATED balance, as stated. An observation, never a calculation:
   * rolling it forward from the ledger was tried and produced ₹1,984 against
   * a real balance above ₹10k, because the ledger cannot know which rows were
   * cash (method is blank on most) or what was never logged at all. A stale
   * true number beats a fresh fabricated one; the agent's job is to ask for a
   * new check when this one ages, not to invent movement.
   */
  bankBalance: number;
  profile: Profile;
  /** Committed money already paid this month, measured — never forecast. */
  fixedPaid: number;
  income: number;
  /** One row per lending still outstanding, oldest first. */
  pending: PendingItem[];
  /** One row per borrowing still owed, oldest first. */
  borrowed: PendingItem[];
  /** Every repayment, newest first — the Settled list, and each one's Undo. */
  repayments: RepaymentItem[];
  /**
   * Udhaar inside the anchor month, for the pool. Money that left is gone,
   * money that came is here: yours out (lent) and back (repaid), theirs in
   * (borrowed) and back out (paid back). spec/done/udhaar-borrowed.md.
   */
  lentMonth: number;
  repaidMonth: number;
  borrowedMonth: number;
  paidBackMonth: number;
  incomeSources: { label: string; amount: number }[];
  /** Whether the first run is behind them. While it is not, the gate shows it. */
  onboarding: WireOnboarding;
}

export interface PendingItem {
  id: string;
  /** Which way the money went: yours out to them, or theirs in to you. */
  leg: 'lent' | 'borrowed';
  label: string;
  /** What was lent. */
  amount: number;
  /** What is still out, after repayments. Always > 0 here. */
  remaining: number;
  /** ISO local day it was lent — age is counted from this, not a day number. */
  date: string;
  day: number;
  pending?: boolean;
  failed?: boolean;
}

export interface RepaymentItem {
  id: string;
  lendingId: string;
  /** The lending's description, so the settled row can say who. */
  label: string;
  amount: number;
  date: string;
  day: number;
  /** The lending's own leg, date and size — Undo rebuilds the open row from these, not from the repayment. */
  leg: 'lent' | 'borrowed';
  lentDate: string;
  lentAmount: number;
  pending?: boolean;
  failed?: boolean;
}

/** "2026-08-22" → 22. The card thinks in days of the month. */
const dayOf = (iso: string) => Number(iso.slice(8, 10));

const paise = (n: number) => Math.round(n / 100);

/**
 * Workout habit logs become Workout rows. Only logs of the workout habit —
 * cigarettes and alcohol are habits too, and they are not sessions.
 */
/**
 * A workout is a habit tick — yes or no, the same as a cigarette. The note is
 * whatever was said alongside it.
 *
 * A session ledger was built on 2026-09-06 and removed on the 7th: this user
 * does not record which exercises he did, so there was nothing to put in it.
 * The library (`/exercises`) is the half that was actually wanted.
 */
function toWorkouts(d: Deck): Workout[] {
  const workoutIds = new Set(
    d.diet.habits.filter((h) => /workout|gym|run/i.test(h.name)).map((h) => h.id),
  );
  return d.diet.habit_logs
    .filter((l) => workoutIds.has(l.habit_id))
    .map((l) => ({
      id: l.id,
      day: dayOf(l.local_day),
      // The note is what the log actually said — 'Workout B (back)'.
      kind: l.note ?? 'Workout',
      minutes: l.amount ?? undefined,
      source: 'manual' as const,
    }));
}

function toTodos(d: Deck): Todo[] {
  return d.work.tasks.map((t) => ({
    id: t.id,
    name: t.title,
    done: t.status === 'done',
    // A task is work unless a label says otherwise — the deck's other two
    // surfaces only ever showed chores that came from them.
    kind: t.labels.includes('diet')
      ? ('diet' as const)
      : t.labels.includes('paisa')
        ? ('paisa' as const)
        : ('work' as const),
    // Tasks keep the real date on both sides: `done_at` is an instant, so it
    // is read in the device's timezone; `due` is already a plain local day.
    doneOn: t.done_at ? localDayOf(t.done_at) : undefined,
    project: t.project_id ?? undefined,
    projectGuessed: t.project_guessed,
    due: t.due ?? undefined,
    priority: t.priority ?? undefined,
    src: t.path ? `${t.path}${t.line ? `:${t.line}` : ''}` : fromLabel(t),
    link: t.doc_ref?.startsWith('http') ? t.doc_ref : undefined,
    stage: t.source_state ?? undefined,
    tracked: t.tracked,
    origin: t.tracked ? sourceName(t.source) : undefined,
    awaitingMove: t.awaiting_move,
  }));
}

/**
 * Where a synced task came from, in the words the person knows it by:
 * `Linear · ENG-142`, or the meeting's title. Data, so it is never translated.
 */
function fromLabel(t: WireTask): string | undefined {
  if (t.source_title) return t.source_title;
  if (t.tracked && t.source_ref) return `${sourceName(t.source)} · ${t.source_ref}`;
  return undefined;
}

/** A source is free text on the wire; the known ones get their proper name. */
export const sourceName = (source: string) =>
  ({ linear: 'Linear', wispr: 'Wispr Flow' })[source] ?? source;

/** Outstanding udhaar: every `lent` row, less the repayments settling it. */
const toTx = (t: WireTx): Tx => ({
  id: t.id,
  day: dayOf(t.local_day),
  name: t.description,
  cat: t.category,
  amt: paise(t.amount_paise),
  commitmentId: t.commitment_id,
  commitmentInferred: t.commitment_inferred,
  confidence: t.confidence,
  // Carried so a card can name the month. A day number alone was printed with
  // a hardcoded "Aug", which read September rows as August ones.
  date: t.local_day,
  credit: t.direction === 'credit',
  kind: t.kind,
});

const toMeal = (m: WireMeal): Meal => ({
  id: m.id,
  day: dayOf(m.local_day),
  name: m.dish,
  type: m.meal_type,
  p: Number(m.protein_g),
  k: m.kcal,
  confidence: m.confidence,
  date: m.local_day,
  c: m.carbs_g == null ? undefined : Number(m.carbs_g),
  f: m.fat_g == null ? undefined : Number(m.fat_g),
});

/** What is still open on one leg, one row per lending or borrowing — per person, so the report can name who. */
export function toOpen(txns: WireTx[], leg: 'lent' | 'borrowed'): PendingItem[] {
  return txns
    .filter((t) => t.kind === leg)
    .map((t) => ({
      id: t.id,
      leg,
      label: t.description,
      amount: paise(t.amount_paise),
      remaining: paise(
        t.amount_paise -
          txns
            .filter((r) => r.kind === 'repayment' && r.settles_id === t.id)
            .reduce((sum, r) => sum + r.amount_paise, 0),
      ),
      date: t.local_day,
      day: dayOf(t.local_day),
    }))
    .filter((p) => p.remaining > 0)
    .sort((x, y) => x.date.localeCompare(y.date));
}

export function toRepayments(txns: WireTx[]): RepaymentItem[] {
  const lendings = new Map(txns.filter((t) => t.kind === 'lent' || t.kind === 'borrowed').map((t) => [t.id, t]));
  return txns
    .filter((t) => t.kind === 'repayment')
    .map((t) => ({
      id: t.id,
      lendingId: t.settles_id ?? '',
      label: (t.settles_id && lendings.get(t.settles_id)?.description) || t.description,
      amount: paise(t.amount_paise),
      date: t.local_day,
      day: dayOf(t.local_day),
      leg: ((t.settles_id && lendings.get(t.settles_id)?.kind) || (t.direction === 'debit' ? 'borrowed' : 'lent')) as 'lent' | 'borrowed',
      lentDate: (t.settles_id && lendings.get(t.settles_id)?.local_day) || t.local_day,
      lentAmount: paise((t.settles_id && lendings.get(t.settles_id)?.amount_paise) || t.amount_paise),
    }))
    .sort((x, y) => y.date.localeCompare(x.date));
}

/**
 * What day the app thinks it is: the device's, always.
 *
 * Dev used to anchor to the last day that had rows, so a frozen dataset kept
 * behaving like "today" instead of receding. Once the ledger started taking
 * live writes that stopped being scaffolding and became a lie: the anchor sat
 * on whatever was last logged, so on 13 September the agent was told it was
 * the 12th and said so. `VITE_ANCHOR` still time-travels on purpose.
 */
function anchorISO(d: Deck): string {
  const override = import.meta.env.DEV
    ? (import.meta.env.VITE_ANCHOR as string | undefined)
    : undefined;
  return override || d.to;
}

function adapt(d: Deck): DeckData {
  const anchor = new Date(`${anchorISO(d)}T00:00:00`);
  const txns = d.paisa.transactions;
  // The pool is the month: a June lending is pending in September, but June's
  // money is not September's pool.
  const month = anchorISO(d).slice(0, 7);
  const inMonth = (t: WireTx) => t.local_day.slice(0, 7) === month;
  const habitName = new Map(d.diet.habits.map((h) => [h.id, h.name]));

  return {
    today: anchor.getDate(),
    todayISO: anchorISO(d),
    month: anchor.getMonth(),
    year: anchor.getFullYear(),
    monthDays: new Date(anchor.getFullYear(), anchor.getMonth() + 1, 0).getDate(),

    // Only discretionary expenses reach the daily limit. A payment that
    // counts toward a commitment — rent, EMI, money sent home — is real
    // spending but not today's decision; the link is the commitment_id on the
    // row, never a flag. Both lists are the anchor month: the pool is the month.
    tx: txns.filter((t) => t.kind === 'expense' && !t.commitment_id && inMonth(t)).map(toTx),
    committedTx: txns.filter((t) => t.kind === 'expense' && t.commitment_id && inMonth(t)).map(toTx),
    salaryToday: txns.some((t) => t.kind === 'income' && t.local_day === anchorISO(d)),

    meals: d.diet.meals.map(toMeal),

    workouts: toWorkouts(d),
    habitLogs: d.diet.habit_logs.map((l) => ({
      id: l.id,
      day: dayOf(l.local_day),
      date: l.local_day,
      habit: habitName.get(l.habit_id) ?? '?',
      amount: l.amount ?? undefined,
      note: l.note ?? undefined,
    })),
    sleep: d.diet.days
      .filter((x) => x.sleep_hours != null)
      .map((x) => ({ day: dayOf(x.local_day), date: x.local_day, hours: x.sleep_hours as number })),
    todos: toTodos(d),
    projects: d.work.projects.map(toProject),

    bankBalance: paise(d.paisa.balance_check?.amount_paise ?? 0),
    profile: toProfile(d.profile),
    fixedPaid: paise(
      txns
        .filter((t) => t.kind === 'expense' && t.commitment_id && inMonth(t))
        .reduce((sum, t) => sum + t.amount_paise, 0),
    ),
    // Everything that ARRIVED this month, which is the inflow side of the
    // server's pool rule: `pool = income + repaid + borrowed − fixed − spent
    // − lent − paid_back` (spec/done/fixed-costs.md § the pool rule). Salary
    // alone was too narrow: a friend returning ₹2,000 is money you now have,
    // and the agent already counted it, so the arc and the agent disagreed.
    income: paise(
      txns
        .filter((t) => inMonth(t) && (
          t.kind === 'income'
          || t.kind === 'borrowed'
          || (t.kind === 'repayment' && t.direction === 'credit')))
        .reduce((sum, t) => sum + t.amount_paise, 0),
    ),

    pending: toOpen(txns, 'lent'),
    borrowed: toOpen(txns, 'borrowed'),
    repayments: toRepayments(txns),
    lentMonth: paise(
      txns.filter((t) => t.kind === 'lent' && inMonth(t)).reduce((s, t) => s + t.amount_paise, 0),
    ),
    repaidMonth: paise(
      txns
        .filter((t) => t.kind === 'repayment' && t.direction === 'credit' && inMonth(t))
        .reduce((s, t) => s + t.amount_paise, 0),
    ),
    borrowedMonth: paise(
      txns.filter((t) => t.kind === 'borrowed' && inMonth(t)).reduce((s, t) => s + t.amount_paise, 0),
    ),
    paidBackMonth: paise(
      txns
        .filter((t) => t.kind === 'repayment' && t.direction === 'debit' && inMonth(t))
        .reduce((s, t) => s + t.amount_paise, 0),
    ),

    incomeSources: txns
      .filter((t) => t.kind === 'income')
      .map((t) => ({ label: t.description, amount: paise(t.amount_paise) })),

    onboarding: { done_at: d.onboarding?.done_at ?? null },
  };
}

/* ─── the one client ──────────────────────────────────────────────────── */

/** An error that reached us from the server, carrying what it answered. */
export interface HttpError extends Error {
  status: number;
}

/**
 * Every request to our API goes through here.
 *
 * It is the only place that knows about the bearer header, so a token that
 * changes shape changes one function. It is also the only place that can tell
 * a 401 from a 500: `!res.ok` used to collapse both into the same
 * `label: status` string at twenty call sites, and the app had no way to ask
 * *am I signed out?*. The status now rides on the error, and a 401 drops the
 * token and rings the app on the way out.
 *
 * `label` keeps each call site's own error text — `deck: 404` still reads
 * `deck: 404`.
 */
async function call<T = unknown>(
  path: string,
  opts: { method?: string; body?: unknown; label: string; signal?: AbortSignal },
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  // Only a request that carries one describes its body.
  if (opts.body !== undefined) headers['Content-Type'] = 'application/json';

  const res = await fetch(`${BASE}${path}`, {
    method: opts.method ?? 'GET',
    headers,
    body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
    signal: opts.signal,
  });

  if (!res.ok) {
    // The token is dead whatever the caller decides to do about it.
    if (res.status === 401) signedOut();
    throw Object.assign(new Error(`${opts.label}: ${res.status}`), { status: res.status });
  }

  if (res.status === 204) return null as T;
  const text = await res.text();
  return (text ? JSON.parse(text) : null) as T;
}

/** The status an error carries, or `null` when it never reached the server. */
export const errorStatus = (e: unknown): number | null =>
  e instanceof Error && typeof (e as Partial<HttpError>).status === 'number'
    ? (e as HttpError).status
    : null;

/* ─── the door ────────────────────────────────────────────────────────── */

/**
 * Swap a Google ID token for a Spica session.
 *
 * The credential is read once, here, and never stored: what the app keeps is
 * the session token this returns. A 403 means the email is not invited, which
 * is a sentence for the user rather than a failure to retry.
 */
export async function signInWithGoogle(credential: string): Promise<Profile> {
  const out = await call<{ token: string; user: WireUser }>('/auth/google', {
    method: 'POST',
    body: { credential },
    label: 'sign in',
  });
  setToken(out.token);
  return toProfile(out.user);
}

/** This device only. The server drops the row; the phone keeps its own session. */
export async function signOut(): Promise<void> {
  try {
    await call('/auth/session', { method: 'DELETE', label: 'sign out' });
  } finally {
    // Whatever the server said, this device is signed out — a network failure
    // must not strand someone on a screen they asked to leave.
    setToken(null);
    // Google remembers who it picked last and will re-select them silently on
    // the next tap. Someone who just signed out is usually signing in as
    // somebody else, so the chooser has to come back.
    try {
      window.google?.accounts?.id.disableAutoSelect();
    } catch {
      /* the script may not be loaded on this screen; nothing to reset */
    }
  }
}

/* ─── writes ──────────────────────────────────────────────────────────── */

async function send(method: string, path: string, body?: unknown): Promise<any> {
  // A body-less write (DELETE, PUT .../save) sends no Content-Type, which the
  // server never read anyway.
  return call<any>(path, { method, body, label: `${method} ${path}` });
}

const pad = (n: number) => String(n).padStart(2, '0');

/** The app's idea of a day as the wire wants it. The device decides the day. */
export const isoDay = (year: number, month0: number, day: number) =>
  `${year}-${pad(month0 + 1)}-${pad(day)}`;

/** Now, on the given local day — the anchor may not be the real today in dev. */
/** The device's wall clock as HH:MM:SS. */
export const localTime = () => new Date().toTimeString().slice(0, 8);

const occurredAt = (localDay: string) => `${localDay}T${new Date().toISOString().slice(11)}`;

/** Resolves to the stored row — an expense may come back linked to a commitment, as a guess. */
export function createTransaction(row: Tx, localDay: string): Promise<WireTx> {
  return send('POST', '/transactions', {
    id: row.id,
    occurred_at: occurredAt(localDay),
    local_day: localDay,
    amount_paise: Math.round(row.amt * 100),
    direction: 'debit',
    kind: 'expense',
    category: row.cat,
    description: row.name,
    source: 'manual',
  });
}

/** Which meal it was, from the clock. Free text on the wire, so this is a
 *  default the user can correct, not a category the app enforces. */
const mealType = () => {
  const h = new Date().getHours();
  return h < 11 ? 'Breakfast' : h < 15 ? 'Lunch' : h < 19 ? 'Snack' : 'Dinner';
};

export function createMeal(row: Meal, localDay: string) {
  return send('POST', '/meals', {
    id: row.id,
    occurred_at: occurredAt(localDay),
    local_day: localDay,
    meal_type: mealType(),
    dish: row.name,
    kcal: row.k,
    protein_g: String(row.p),
    // Sent only when known. The composer knows kcal and protein for a chip,
    // not its fat or carbs — and neither did the portion sheet the chips came
    // from. Omitting them keeps the row honest: NULL, not a fabricated 0.
    ...(row.c != null ? { carbs_g: String(row.c) } : {}),
    ...(row.f != null ? { fat_g: String(row.f) } : {}),
    source: 'manual',
  });
}

export const patchTask = (id: string, done: boolean) =>
  send('PATCH', `/tasks/${id}`, { status: done ? 'done' : 'open' });

/* ─── an app asking to reach Spica (spec/work-sync.md § Auth) ─────────── */

export interface ConnectRequest {
  client_name: string;
  redirect_host: string;
  scopes: string[];
}

export const fetchConnectRequest = (request: string): Promise<ConnectRequest> =>
  send('GET', `/oauth/requests/${encodeURIComponent(request)}`);

/** The person's answer. Resolves to where the browser goes next — back to
 *  the app that asked, with a code or with a refusal. */
export const answerConnect = (request: string, allow: boolean): Promise<{ redirect: string }> =>
  send('POST', `/oauth/requests/${encodeURIComponent(request)}/${allow ? 'approve' : 'deny'}`);

/** What the composer can say about a money row: a description and an amount. */
export const patchTransaction = (
  id: string,
  body: {
    description?: string;
    amount_paise?: number;
    /** An id moves the payment to that commitment (and confirms it); null is "Not a commitment". */
    commitment_id?: string | null;
    confidence?: number;
  },
) =>
  send('PATCH', `/transactions/${id}`, body);

/** And about a meal: a dish and its kcal. Protein and the rest stay as they were. */
export const patchMeal = (id: string, body: { dish?: string; kcal?: number; confidence?: number }) =>
  send('PATCH', `/meals/${id}`, body);

export const deleteHabitLog = (id: string) => send('DELETE', `/habit-logs/${id}`);
export const deleteTask = (id: string) => send('DELETE', `/tasks/${id}`);

export const deleteTransaction = (id: string) => send('DELETE', `/transactions/${id}`);
export const deleteMeal = (id: string) => send('DELETE', `/meals/${id}`);

/**
 * Undo on a removed row: the soft delete is lifted and the row comes back
 * live. Refused (404) when the row is missing or was never deleted.
 */
export async function restoreTransaction(id: string): Promise<Tx> {
  return toTx((await send('POST', `/transactions/${id}/restore`)) as WireTx);
}

/** A meal comes back with the pantry moves it had made — the server puts both back. */
export async function restoreMeal(id: string): Promise<Meal> {
  const out = (await send('POST', `/meals/${id}/restore`)) as { meal: WireMeal; pantry_moves: unknown[] };
  return toMeal(out.meal);
}

const iso = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(
    d.getDate(),
  ).padStart(2, '0')}`;

/**
 * The dates are computed here, from the device's clock, because only the
 * device knows what day it is where the user is. A server deciding "today"
 * would put an 11:30pm chai on the wrong day.
 */
export async function fetchDeck(to: Date = new Date()): Promise<DeckData> {
  return adapt(await call<Deck>(`/deck?to=${iso(to)}`, { label: 'deck' }));
}

/* ─── the person ─────────────────────────────────────────────────────── */

/** Any subset of the editable columns; the server refuses anything else. */
export type UserPatch = Partial<
  Pick<
    WireUser,
    | 'display_name' | 'dob' | 'gender' | 'height_cm' | 'city' | 'diet' | 'timezone' | 'savings_target_paise'
    | 'kcal_target' | 'protein_g_target' | 'carbs_g_target' | 'fat_g_target'
    | 'fibre_g_target' | 'weight_target_kg' | 'sleep_target_min' | 'step_target'
    | 'onboarding_done_at'
  >
>;

export async function patchUser(body: UserPatch): Promise<Profile> {
  return toProfile((await send('PATCH', '/users/me', body)) as WireUser);
}

/** The person as they are now — the first run reads it after every answer. */
export async function fetchMe(): Promise<Profile> {
  return toProfile(await call<WireUser>('/users/me', { label: 'me' }));
}

export async function listMemories(): Promise<MemoryRow[]> {
  return (await call<WireMemory[]>('/memories', { label: 'memories' })).map(toMemory);
}

/** Same slug → the server updates that row instead of filing a second one. */
export async function createMemory(row: {
  id: string; slug: string; kind: string; text: string;
}): Promise<MemoryRow> {
  return toMemory((await send('POST', '/memories', { ...row, source: 'user' })) as WireMemory);
}

export async function patchMemory(id: string, patch: { text?: string; kind?: string }) {
  return toMemory((await send('PATCH', `/memories/${id}`, patch)) as WireMemory);
}

export const deleteMemory = (id: string) => send('DELETE', `/memories/${id}`);

export async function listWeighIns(): Promise<WeighInRow[]> {
  return (await call<WireWeighIn[]>('/weigh-ins', { label: 'weigh-ins' })).map(toWeighIn);
}

/**
 * A second reading on the same day replaces the first — the server dedupes on
 * the day. One typed on Profile is a reading, so it goes as exact and clears
 * an estimate.
 */
export async function createWeighIn(id: string, localDay: string, kg: number): Promise<WeighInRow> {
  return toWeighIn(
    (await send('POST', '/weigh-ins', { id, local_day: localDay, weight_kg: String(kg) })) as WireWeighIn,
  );
}

/** The reading goes, and that day's copy on `days` with it. */
export const deleteWeighIn = (id: string) => send('DELETE', `/weigh-ins/${id}`);

/* ─── udhaar ─────────────────────────────────────────────────────────── */

/** "<name> ko diya" → "<name> se wapas aaya"; "<name> se liya" → "<name> ko wapas diya". */
const settledLabel = (open: PendingItem) =>
  open.leg === 'lent'
    ? /\s+ko diya$/i.test(open.label)
      ? open.label.replace(/\s+ko diya$/i, ' se wapas aaya')
      : `${open.label} · wapas aaya`
    : /\s+se liya$/i.test(open.label)
      ? open.label.replace(/\s+se liya$/i, ' ko wapas diya')
      : `${open.label} · wapas diya`;

/**
 * A repayment against a lending (a credit: their money came back to you) or a
 * borrowing (a debit: you paid theirs back). The server fills the counterparty
 * from the open row and refuses more than what is out.
 */
export function createRepayment(id: string, open: PendingItem, amount: number, localDay: string) {
  return send('POST', '/transactions', {
    id,
    occurred_at: occurredAt(localDay),
    local_day: localDay,
    amount_paise: Math.round(amount * 100),
    direction: open.leg === 'lent' ? 'credit' : 'debit',
    kind: 'repayment',
    category: 'Udhaar',
    description: settledLabel(open),
    settles_id: open.id,
    source: 'manual',
  });
}

/**
 * A lending or a borrowing typed on the report: who, and how much. The server
 * resolves the name to a counterparty, creating the person if new.
 */
export function createOpen(
  id: string,
  leg: 'lent' | 'borrowed',
  who: string,
  amount: number,
  localDay: string,
) {
  return send('POST', '/transactions', {
    id,
    occurred_at: occurredAt(localDay),
    local_day: localDay,
    amount_paise: Math.round(amount * 100),
    direction: leg === 'lent' ? 'debit' : 'credit',
    kind: leg,
    category: 'Udhaar',
    description: leg === 'lent' ? `${who} ko diya` : `${who} se liya`,
    counterparty_name: who,
    source: 'manual',
  });
}

/** Stop expecting it back: the lending becomes an expense, in the category that already holds gifts. */
export function giftLending(id: string) {
  return send('PATCH', `/transactions/${id}`, { kind: 'expense', category: 'Logon ko diya' });
}

/* ─── pantry ─────────────────────────────────────────────────────────── */

interface WirePantryItem {
  id: string;
  food_id: string;
  name: string;
  stock_g: number;
  reorder_at_g: number | null;
  shelf_life_days: number | null;
  note: string | null;
  staple: boolean;
  unit: string;
  inbound: number;
  last_in: string | null;
  last_in_g: number | null;
}

interface WirePantryMove {
  id: string;
  food_id: string;
  name: string;
  local_day: string;
  quantity: number;
  unit: string;
  kind: string;
  note: string | null;
  dish: string | null;
}

/**
 * A tracked food. `status` is not on the wire — the server sends the numbers
 * that decide it and the client picks the word, because words are UI.
 */
export type PantryStatus = 'staple' | 'new' | 'out' | 'stale' | 'soon' | 'ok';

/**
 * "620 g", "600 ml", "18 pcs" — the food's own unit, never a converted one.
 * Display only: a stock run below zero reads "−15 g", with a true minus
 * (U+2212). A field's value is never built from this — it would not parse.
 */
export const inUnit = (n: number, unit: string) => {
  const v = (n < 0 ? '−' : '') + Math.abs(n);
  return unit === 'piece' ? `${v} pcs` : `${v} ${unit}`;
};

/** "1 dozen" is twelve pieces. A dozen is shorthand, not a unit. */
export function parseQuantity(raw: string, unit: string): number {
  const text = raw.trim().toLowerCase();
  const n = parseFloat(text.replace(/[^0-9.]/g, ''));
  if (!Number.isFinite(n)) return NaN;
  if (unit === 'piece' && /dozen|darjan/.test(text)) return Math.round(n * 12);
  return n;
}

export interface PantryRow {
  id: string;
  foodId: string;
  name: string;
  /** Sum of every live move. Meaningless when `inbound` is 0. */
  stockG: number;
  reorderAtG: number | null;
  shelfLifeDays: number | null;
  note: string | null;
  /** Always in the house — no arithmetic is attempted for it. */
  staple: boolean;
  /** What this food is counted in: 'g', 'ml' or 'piece'. */
  unit: string;
  /** How many purchases or stock-takes this food has ever had. */
  inbound: number;
  lastIn: string | null;
  /** The size of the last inbound move — the Bought prompt's default. */
  lastInG: number | null;
  status: PantryStatus;
  pending?: boolean;
  failed?: boolean;
}

export interface PantryMoveRow {
  id: string;
  foodId: string;
  name: string;
  day: string;
  quantity: number;
  unit: string;
  kind: string;
  /** The meal that caused a consumption. Those lines carry no Undo. */
  dish: string | null;
  pending?: boolean;
}

const daysBetween = (a: string, b: string) =>
  Math.round((Date.parse(`${b}T00:00:00Z`) - Date.parse(`${a}T00:00:00Z`)) / 86_400_000);

/**
 * The status ladder, in order.
 *
 * `staple` is first because it is a declaration, not a measurement: atta is in
 * the house and counting it is meaningless. `new` is second — a tracked food
 * with nothing ever logged in has no stock figure either, however negative its
 * consumption runs (eggs read −530 g, which is the ledger saying nobody records
 * eggs arriving, not that there are minus eggs). `stale` outranks `soon`
 * because 600 g of week-old tofu is not 600 g of tofu.
 */
export function statusOf(r: { staple: boolean; stockG: number; inbound: number; lastIn: string | null; shelfLifeDays: number | null; reorderAtG: number | null }, today: string): PantryStatus {
  if (r.staple) return 'staple';
  if (r.inbound === 0) return 'new';
  if (r.stockG <= 0) return 'out';
  if (r.shelfLifeDays && r.lastIn && daysBetween(r.lastIn, today) > r.shelfLifeDays) return 'stale';
  if (r.reorderAtG != null && r.stockG <= r.reorderAtG) return 'soon';
  return 'ok';
}

export async function fetchPantry(today: string): Promise<PantryRow[]> {
  return (await call<WirePantryItem[]>('/pantry', { label: 'pantry' })).map((w) => {
    const row = {
      id: w.id,
      foodId: w.food_id,
      name: w.name,
      stockG: w.stock_g,
      reorderAtG: w.reorder_at_g,
      shelfLifeDays: w.shelf_life_days,
      note: w.note,
      staple: w.staple,
      unit: w.unit,
      inbound: w.inbound,
      lastIn: w.last_in,
      lastInG: w.last_in_g,
    };
    return { ...row, status: statusOf(row, today) };
  });
}

export async function fetchPantryMoves(foodId?: string): Promise<PantryMoveRow[]> {
  const q = foodId ? `?food_id=${encodeURIComponent(foodId)}` : '';
  return (await call<WirePantryMove[]>(`/pantry-moves${q}`, { label: 'pantry-moves' })).map((w) => ({
    id: w.id,
    foodId: w.food_id,
    name: w.name,
    day: w.local_day,
    quantity: w.quantity,
    unit: w.unit,
    kind: w.kind,
    dish: w.dish,
  }));
}

/** Bought (a purchase) or Have (a stock-take). Stock only ever moves by a move. */
export function createPantryMove(
  id: string,
  foodId: string,
  quantity: number,
  kind: 'purchase' | 'opening' | 'correction',
  localDay: string,
) {
  return send('POST', '/pantry-moves', {
    id,
    food_id: foodId,
    local_day: localDay,
    occurred_at: occurredAt(localDay),
    quantity: Math.round(quantity),
    kind,
  });
}

export const deletePantryMove = (id: string) => send('DELETE', `/pantry-moves/${id}`);

/** Start tracking a food by name. The opening stock, if any, is a second call. */
export function trackFood(id: string, foodName: string, staple = false, unit = 'g') {
  return send('POST', '/pantry', { id, food_name: foodName, staple, unit });
}

export function patchPantryItem(
  id: string,
  patch: { reorder_at_g?: number | null; shelf_life_days?: number | null; staple?: boolean },
) {
  return send('PATCH', `/pantry/${id}`, patch);
}

export const stopTracking = (id: string) => send('DELETE', `/pantry/${id}`);

/* ─── dishes ─────────────────────────────────────────────────────────── */

interface WireDishItem {
  id: string;
  food_id: string | null;
  food_name: string | null;
  component_dish_id: string | null;
  quantity: number | null;
  unit: string;
  servings: string;
  note: string | null;
  from_dish: string | null;
}

interface WireDish {
  id: string;
  name: string;
  aliases: string[];
  meal_type: string | null;
  serving_label: string;
  kcal: number | null;
  protein_g: string;
  carbs_g: string | null;
  fat_g: string | null;
  fibre_g: string | null;
  minutes: number | null;
  needs_prep_ahead: boolean;
  steps: string | null;
  image_url: string | null;
  tags: string[];
  note: string | null;
  mine: boolean;
  saved: boolean;
  tried: number;
  last_tried: string | null;
  items: WireDishItem[];
}

export interface DishIngredient {
  foodId: string | null;
  name: string | null;
  quantity: number | null;
  unit: string;
  servings: number;
  note: string | null;
  /** Set when the line came from a component dish; grams are already scaled. */
  fromDish: string | null;
}

/**
 * A dish, with this user's relationship to it. `tried` is counted from the
 * ledger's meal lines at read time — there is no stored counter to drift.
 */
export interface DishRow {
  id: string;
  name: string;
  aliases: string[];
  mealType: string | null;
  serving: string;
  kcal: number | null;
  proteinG: number;
  carbsG: number | null;
  fatG: number | null;
  minutes: number | null;
  needsPrepAhead: boolean;
  imageUrl: string | null;
  tags: string[];
  note: string | null;
  mine: boolean;
  saved: boolean;
  tried: number;
  lastTried: string | null;
  items: DishIngredient[];
}

const toDish = (w: WireDish): DishRow => ({
  id: w.id,
  name: w.name,
  aliases: w.aliases,
  mealType: w.meal_type,
  serving: w.serving_label,
  kcal: w.kcal,
  proteinG: Number(w.protein_g),
  carbsG: w.carbs_g == null ? null : Number(w.carbs_g),
  fatG: w.fat_g == null ? null : Number(w.fat_g),
  minutes: w.minutes,
  needsPrepAhead: w.needs_prep_ahead,
  imageUrl: w.image_url,
  tags: w.tags,
  note: w.note,
  mine: w.mine,
  saved: w.saved,
  tried: w.tried,
  lastTried: w.last_tried,
  items: w.items.map((i) => ({
    foodId: i.food_id,
    name: i.food_name,
    quantity: i.quantity,
    unit: i.unit,
    servings: Number(i.servings),
    note: i.note,
    fromDish: i.from_dish,
  })),
});

/** `mine` is your library — saved or tried. Otherwise the whole pool. */
export async function fetchDishes(mine = true, q?: string): Promise<DishRow[]> {
  const params = new URLSearchParams({ mine: String(mine) });
  if (q) params.set('q', q);
  return (await call<WireDish[]>(`/dishes?${params}`, { label: 'dishes' })).map(toDish);
}

export const saveDish = (id: string) => send('PUT', `/dishes/${id}/save`);
export const unsaveDish = (id: string) => send('DELETE', `/dishes/${id}/save`);

/* ─── people. spec/in-progress/people.md ──────────────────────────────── */

interface WirePerson {
  id: string;
  raw_name: string;
  display_name: string | null;
  kind: string | null;
  relation: string | null;
  note: string | null;
  source: string | null;
  confirmed_at: string | null;
  is_peer: boolean;
  in_contacts: boolean;
  default_category: string | null;
  sent_paise: number;
  received_paise: number;
  still_out_paise: number;
  you_owe_paise: number;
  typical_days: number | null;
  tx_count: number;
  last_day: string | null;
}

export type PersonKind = 'person' | 'shop' | 'service';

/**
 * Someone the ledger has a row for. Only `kind`, `relation` and `note` are
 * stored about them — every number is arithmetic over the transactions, so a
 * deleted payment corrects all of them with nothing to update.
 */
export interface PersonRow {
  id: string;
  rawName: string;
  displayName: string | null;
  name: string;
  kind: PersonKind | null;
  relation: string | null;
  note: string | null;
  /** No confirmation means nobody has said this — the row shows · andaaza. */
  confirmed: boolean;
  source: string | null;
  isPeer: boolean;
  /** The bucket payments here usually land in. */
  defaultCategory: string | null;
  sent: number;
  received: number;
  /** What they owe you, in paise. */
  stillOut: number;
  /** What you owe them, in paise. */
  youOwe: number;
  /** Mean days from a lending to its first repayment. null = nothing back yet. */
  typicalDays: number | null;
  txCount: number;
  lastDay: string | null;
}

function toPerson(w: WirePerson): PersonRow {
  return {
    id: w.id,
    rawName: w.raw_name,
    displayName: w.display_name,
    name: w.display_name || w.raw_name,
    kind: w.kind as PersonKind | null,
    relation: w.relation,
    note: w.note,
    confirmed: w.confirmed_at != null,
    source: w.source,
    isPeer: w.is_peer,
    defaultCategory: w.default_category,
    sent: w.sent_paise,
    received: w.received_paise,
    stillOut: w.still_out_paise,
    youOwe: w.you_owe_paise,
    typicalDays: w.typical_days,
    txCount: w.tx_count,
    lastDay: w.last_day,
  };
}

export async function fetchPeople(): Promise<PersonRow[]> {
  return (await call<WirePerson[]>('/people', { label: 'people' })).map(toPerson);
}

export async function patchCounterparty(
  id: string,
  patch: {
    kind?: PersonKind | null;
    relation?: string | null;
    note?: string | null;
    display_name?: string | null;
    default_category?: string | null;
  },
): Promise<PersonRow> {
  return toPerson(
    await call<WirePerson>(`/counterparties/${id}`, {
      method: 'PATCH', body: patch, label: 'counterparty',
    }),
  );
}

export async function createCounterparty(row: {
  id: string;
  raw_name: string;
  display_name?: string | null;
  kind?: PersonKind | null;
  relation?: string | null;
  note?: string | null;
  default_category?: string | null;
}): Promise<PersonRow> {
  return toPerson(
    await call<WirePerson>('/counterparties', { method: 'POST', body: row, label: 'counterparty' }),
  );
}

/* ─── workouts. spec/in-progress/workouts.md ──────────────────────────── */

interface WireExercise {
  id: string;
  name: string;
  aliases: string[];
  kind: string | null;
  muscle_group: string | null;
  equipment: string | null;
  typical_minutes: number | null;
  steps: string | null;
  source_url: string | null;
  image_url: string | null;
  source: string;
  note: string | null;
  tried: number;
  last_tried: string | null;
}

/**
 * One library row — what exists to suggest from.
 *
 * `tried` is stored, not derived, and it is the only count in the app that is:
 * there is no ledger of exercises done, because a workout is a habit tick. So
 * "I have done this three times" is a declaration. 0 means bookmarked only.
 */
export interface ExerciseRow {
  id: string;
  name: string;
  aliases: string[];
  /** Separate from muscleGroup: cardio is not a muscle. */
  kind: string | null;
  muscleGroup: string | null;
  equipment: string | null;
  typicalMinutes: number | null;
  steps: string | null;
  sourceUrl: string | null;
  imageUrl: string | null;
  source: string;
  note: string | null;
  tried: number;
  lastTried: string | null;
}

const toExercise = (w: WireExercise): ExerciseRow => ({
  id: w.id,
  name: w.name,
  aliases: w.aliases,
  kind: w.kind,
  muscleGroup: w.muscle_group,
  equipment: w.equipment,
  typicalMinutes: w.typical_minutes,
  steps: w.steps,
  sourceUrl: w.source_url,
  imageUrl: w.image_url,
  source: w.source,
  note: w.note,
  tried: w.tried,
  lastTried: w.last_tried,
});

export async function fetchExercises(): Promise<ExerciseRow[]> {
  return (await call<WireExercise[]>('/exercises', { label: 'exercises' })).map(toExercise);
}

export async function createExercise(row: {
  id: string;
  name: string;
  kind?: string | null;
  muscle_group?: string | null;
  equipment?: string | null;
  typical_minutes?: number | null;
  steps?: string | null;
  source_url?: string | null;
  source?: string;
}): Promise<ExerciseRow> {
  return toExercise(
    await call<WireExercise>('/exercises', { method: 'POST', body: row, label: 'exercise' }),
  );
}

/** `tried += 1` and today's date, in one write. */
export async function didExercise(id: string, localDay: string): Promise<ExerciseRow> {
  return toExercise(
    await call<WireExercise>(`/exercises/${id}/did`, {
      method: 'POST', body: { local_day: localDay }, label: 'exercise',
    }),
  );
}

export async function patchExercise(
  id: string,
  patch: { tried?: number; last_tried?: string | null; steps?: string | null; note?: string | null },
): Promise<ExerciseRow> {
  return toExercise(
    await call<WireExercise>(`/exercises/${id}`, {
      method: 'PATCH', body: patch, label: 'exercise',
    }),
  );
}

/* ─── places. spec/in-progress/places.md ──────────────────────────────── */

interface WirePlace {
  id: string;
  name: string;
  kind: string | null;
  lat: number;
  lng: number;
  radius_m: number;
  address: string | null;
  category: string | null;
  counterparty_id: string | null;
  counterparty_name: string | null;
  note: string | null;
  source: string;
  confirmed_at: string | null;
  payments: number;
  spent_paise: number;
  last_seen: string | null;
}

/**
 * A pin, and what the ledger knows about it.
 *
 * `payments`, `spent` and `lastSeen` are counted server-side per request —
 * unlike the exercise library, a place *has* a ledger under it, so deleting a
 * payment corrects the pin with no write.
 */
export interface PlaceRow {
  id: string;
  name: string;
  kind: string | null;
  lat: number;
  lng: number;
  radiusM: number;
  address: string | null;
  category: string | null;
  counterpartyId: string | null;
  counterpartyName: string | null;
  note: string | null;
  source: string;
  /** False on a detected pin until you say so — that is what shows · andaaza. */
  confirmed: boolean;
  payments: number;
  spent: number;
  lastSeen: string | null;
}

const toPlace = (w: WirePlace): PlaceRow => ({
  id: w.id,
  name: w.name,
  kind: w.kind,
  lat: w.lat,
  lng: w.lng,
  radiusM: w.radius_m,
  address: w.address,
  category: w.category,
  counterpartyId: w.counterparty_id,
  counterpartyName: w.counterparty_name,
  note: w.note,
  source: w.source,
  confirmed: w.confirmed_at != null,
  payments: w.payments,
  spent: w.spent_paise,
  lastSeen: w.last_seen,
});

export async function fetchPlaces(): Promise<PlaceRow[]> {
  return (await call<WirePlace[]>('/places', { label: 'places' })).map(toPlace);
}

export async function createPlace(row: {
  id: string;
  name: string;
  lat: number;
  lng: number;
  kind?: string | null;
  radius_m?: number;
  address?: string | null;
  counterparty_id?: string | null;
  note?: string | null;
  source?: string;
}): Promise<PlaceRow> {
  return toPlace(await call<WirePlace>('/places', { method: 'POST', body: row, label: 'place' }));
}

export async function patchPlace(
  id: string,
  patch: {
    name?: string;
    kind?: string | null;
    radius_m?: number;
    counterparty_id?: string | null;
    note?: string | null;
    category?: string | null;
  },
): Promise<PlaceRow> {
  return toPlace(
    await call<WirePlace>(`/places/${id}`, { method: 'PATCH', body: patch, label: 'place' }),
  );
}

export async function deletePlace(id: string): Promise<void> {
  await call(`/places/${id}`, { method: 'DELETE', label: 'place' });
}

export interface Found {
  name: string;
  lat: number;
  lng: number;
  address: string;
}

/**
 * Nominatim — OpenStreetMap's own geocoder. Free and keyless, rate-limited to
 * about one request a second, which is fine for one person typing. Biased to
 * India because that is where the payments are.
 */
export async function searchPlaces(q: string): Promise<Found[]> {
  const url = new URL('https://nominatim.openstreetmap.org/search');
  url.searchParams.set('q', q);
  url.searchParams.set('format', 'jsonv2');
  url.searchParams.set('limit', '6');
  url.searchParams.set('countrycodes', 'in');
  // The one request that does not go through `call`: it is somebody else's
  // server, and our session token has no business travelling there.
  const res = await fetch(url, { headers: { Accept: 'application/json' } });
  if (!res.ok) throw new Error(`search: ${res.status}`);
  return ((await res.json()) as { display_name: string; lat: string; lon: string }[]).map((r) => ({
    name: r.display_name.split(',')[0],
    address: r.display_name,
    lat: Number(r.lat),
    lng: Number(r.lon),
  }));
}

/* ─── the month's numbers, computed once on the server ────────────────── */

/**
 * The Paisa card's limit and what it is made of. Until 2026-09-12 the hook
 * computed this itself; the agent needed the same figure, and two
 * computations of one number is how a screen and an agent start disagreeing.
 * `GET /paisa/summary` is one function with two callers — this, and the
 * agent's `paisa_report` tool. spec/agent-tools.md.
 */
export interface LimitInfo {
  /** Rupees, like everything else the hook holds. Null is unknown — no income
   *  yet this month — and never ₹0. Negative means past the line. */
  limit: number | null;
  spentToday: number;
  /** Null with the limit. */
  left: number | null;
  pool: number;
  locked: number;
  fixedPaid: number;
  daysLeft: number;
}

export async function fetchLimit(to: string): Promise<LimitInfo> {
  const L = (await call<{
    limit_today: {
      limit_paise?: number; spent_today_paise: number; left_paise?: number;
      pool_paise: number; locked_paise: number; fixed_paid_paise: number; days_left: number;
    };
  }>(`/paisa/summary?to=${to}&fields=limit_today`, { label: 'summary' })).limit_today;
  return {
    limit: L.limit_paise == null ? null : paise(L.limit_paise),
    spentToday: paise(L.spent_today_paise),
    left: L.left_paise == null ? null : paise(L.left_paise),
    pool: paise(L.pool_paise),
    locked: paise(L.locked_paise),
    fixedPaid: paise(L.fixed_paid_paise),
    daysLeft: L.days_left,
  };
}

/* ─── the agent. spec/agent.md ─────────────────────────────────────────── */

/** One card in a reply. The server's shapes, kept loose here on purpose —
 *  they are still moving, and a strict mirror would break on every tweak. */
export interface WireCard {
  kind: 'agent' | 'table' | 'confirm' | 'suggest' | 'ask' | 'todos' | 'commitments';
  [k: string]: unknown;
}

export interface ChatReply {
  reply: string;
  cards: WireCard[];
  tokens_in: number;
  tokens_out: number;
  model: string;
}

/**
 * A turn. No streaming: the reply lands whole, which is the right trade while
 * the card shapes are still moving. The local day is the client's to send —
 * only it knows what day it is where the user is.
 */
export async function sendChat(message: string, localDay: string): Promise<ChatReply> {
  return call<ChatReply>('/chat', {
    method: 'POST',
    // The clock goes with the day. Without it the agent cannot tell breakfast
    // from dinner and stamps everything it writes at midday.
    body: { message, local_day: localDay, local_time: localTime() },
    label: 'chat',
  });
}

/** One answer to one of the first run's questions. spec/done/onboarding-goals.md § A turn. */
export type OnboardingQuestion = 'about' | 'place' | 'health' | 'money' | 'habits';

export interface OnboardingTurn {
  /** The confirm cards for this answer's writes, one per write. */
  cards: WireCard[];
  /** A follow-up, or "Say that again?" — null once the question is done. */
  reply: string | null;
  /** The question is answered or skipped: ask the next one. */
  next: boolean;
}

/**
 * The onboarding agent reads one answer and writes it through the app's own
 * tools. Nothing joins the chat thread. `409` once the first run is over,
 * `429` past the day's cap, `502` when the model failed — nothing written.
 */
export async function sendOnboardingTurn(
  question: OnboardingQuestion,
  text: string,
  localDay: string,
  signal?: AbortSignal,
): Promise<OnboardingTurn> {
  return call<OnboardingTurn>('/onboarding/turn', {
    method: 'POST',
    body: { question, text, local_day: localDay },
    label: 'onboarding',
    signal,
  });
}

export interface WireTurn {
  id: string;
  seq: number;
  role: 'user' | 'agent';
  text: string;
  cards: WireCard[] | null;
}

/**
 * How much thread the client asks for at a time. Not the agent's `CHAT_WINDOW`
 * and deliberately not tied to it: that is a token budget, this is a DOM and
 * round-trip budget. Nor an env flag — the web version is not the client that
 * lasts, and the Android app will size its own list. spec/done/chat-history.md.
 */
export const CHAT_PAGE = 20;

export interface ChatPage {
  turns: WireTurn[];
  /** More sits before this page, within the same scope. */
  hasMore: boolean;
  /** What the user cleared from view; 0 if never. */
  clearedThrough: number;
}

/**
 * One page of the thread, oldest last. `before` is a message `seq`, not an
 * offset, so a new arrival or a soft delete cannot shift the page under
 * someone mid-scroll.
 */
export async function fetchChat(
  opts: { limit?: number; before?: number; includeCleared?: boolean } = {},
): Promise<ChatPage> {
  const q = new URLSearchParams({ limit: String(opts.limit ?? CHAT_PAGE) });
  if (opts.before != null) q.set('before', String(opts.before));
  if (opts.includeCleared) q.set('include_cleared', 'true');
  const body = await call<{
    messages: WireTurn[]; has_more: boolean; cleared_through_seq: number;
  }>(`/chat?${q}`, { label: 'chat' });
  return { turns: body.messages, hasMore: body.has_more,
           clearedThrough: body.cleared_through_seq };
}

/**
 * Clear the screen without forgetting. The server folds everything above the
 * newest message into the summary and hides it; nothing is deleted, and
 * *Show older* brings it back.
 */
export async function clearChat(): Promise<ChatPage> {
  const body = await call<{
    messages: WireTurn[]; has_more: boolean; cleared_through_seq: number;
  }>('/chat/clear', { method: 'POST', label: 'chat/clear' });
  return { turns: body.messages, hasMore: body.has_more,
           clearedThrough: body.cleared_through_seq };
}



/* ─── chat cards: rows by id, tap-to-log ─────────────────────────────────── */

interface WireRowTx extends WireTx {
  description: string;
  category: string;
  deleted_at: string | null;
}

interface WireRowMeal {
  id: string;
  local_day: string;
  meal_type: string;
  dish: string;
  kcal: number;
  protein_g: string;
  carbs_g: string | null;
  fat_g: string | null;
  confidence: number;
  deleted_at: string | null;
}

/**
 * Rows a chat card named that the deck's window does not hold. The one read
 * that returns deleted rows — with `deleted_at` set — so a card can strike a
 * row through instead of silently losing it. spec/chat-cards.md § ledger card.
 */
export async function fetchRowsByIds(source: 'paisa', ids: string[]): Promise<Tx[]>;
export async function fetchRowsByIds(source: 'diet', ids: string[]): Promise<Meal[]>;
export async function fetchRowsByIds(source: 'paisa' | 'diet', ids: string[]): Promise<Tx[] | Meal[]> {
  const path = source === 'paisa' ? '/transactions' : '/meals';
  const rows = await call<WireRowTx[] | WireRowMeal[]>(
    `${path}?ids=${encodeURIComponent(ids.slice(0, 50).join(','))}`,
    { label: path },
  );
  if (source === 'paisa') {
    return (rows as WireRowTx[]).map((t) => ({
      id: t.id,
      day: dayOf(t.local_day),
      date: t.local_day,
      name: t.description,
      cat: t.category,
      amt: paise(t.amount_paise),
      commitmentId: t.commitment_id,
      commitmentInferred: t.commitment_inferred,
      confidence: t.confidence,
      credit: t.direction === 'credit',
      kind: t.kind,
      deleted: t.deleted_at != null,
    }));
  }
  return (rows as WireRowMeal[]).map((m) => ({
    id: m.id,
    day: dayOf(m.local_day),
    date: m.local_day,
    name: m.dish,
    type: m.meal_type,
    p: Number(m.protein_g),
    k: m.kcal,
    ...(m.carbs_g != null ? { c: Number(m.carbs_g) } : {}),
    ...(m.fat_g != null ? { f: Number(m.fat_g) } : {}),
    confidence: m.confidence,
    deleted: m.deleted_at != null,
  }));
}

/**
 * A tap on a card: one tool, its arguments, no model. The server runs the tool
 * and returns its cards for the client to show as a receipt; the thread is
 * left alone unless `record` is set — a shortcut the user asked for belongs in
 * the scrollback, a tap's confirmation does not.
 */
export async function actChat(
  name: string,
  args: Record<string, unknown>,
  record = false,
): Promise<ChatReply> {
  return call<ChatReply>('/chat/act', {
    method: 'POST', body: { name, args, record }, label: 'chat/act',
  });
}

/** Breakfast / Lunch / Snack / Dinner by the clock, for a tap with no stated slot. */
export const mealTypeNow = () => mealType();


/* ─── habits ─────────────────────────────────────────────────────────────── */

interface WireHabit {
  id: string;
  name: string;
  direction: string;
  unit: string | null;
  days_this_week: number;
  logged_ever: number;
}

/**
 * A habit you have decided to track. `direction` has been on the row since the
 * first migration and never on a screen — it is what makes a long chain read as
 * progress on one habit and as a warning on another.
 */
export interface HabitRow {
  id: string;
  name: string;
  direction: 'build' | 'break';
  /** What a tick can carry an amount in. NULL where a tick is the whole fact. */
  unit: string | null;
  daysThisWeek: number;
  loggedEver: number;
  pending?: boolean;
  failed?: boolean;
}

const toHabit = (w: WireHabit): HabitRow => ({
  id: w.id,
  name: w.name,
  direction: w.direction === 'break' ? 'break' : 'build',
  unit: w.unit,
  daysThisWeek: w.days_this_week,
  loggedEver: w.logged_ever,
});

export async function fetchHabits(): Promise<HabitRow[]> {
  return (await call<WireHabit[]>('/habits', { label: 'habits' })).map(toHabit);
}

export async function createHabit(row: {
  name: string; direction: 'build' | 'break'; unit: string | null;
}): Promise<HabitRow> {
  return toHabit((await send('POST', '/habits', { id: ulid(), ...row })) as WireHabit);
}

export async function patchHabit(
  id: string,
  patch: { name?: string; direction?: 'build' | 'break'; unit?: string | null },
): Promise<HabitRow> {
  return toHabit((await send('PATCH', `/habits/${id}`, patch)) as WireHabit);
}

export const deleteHabit = (id: string) => send('DELETE', `/habits/${id}`);

/* ─── projects (spec/done/projects.md) ───────────────────────────── */

const toProject = (w: WireProject): Project => ({
  id: w.id,
  name: w.name,
  color: w.color,
  description: w.description ?? undefined,
  icon: w.icon ?? undefined,
  aliases: w.aliases ?? [],
  isDefault: w.is_default,
});

interface WireProjectRow extends WireProject {
  archived_at: string | null;
  open_tasks: number;
  moved_aliases: { alias: string; from: string }[];
}

export interface ProjectRow extends Project {
  archived: boolean;
  openTasks: number;
  /** Aliases the last write took from another project, so the page can say so. */
  movedAliases: { alias: string; from: string }[];
}

const toProjectRow = (w: WireProjectRow): ProjectRow => ({
  ...toProject(w),
  archived: w.archived_at != null,
  openTasks: w.open_tasks,
  movedAliases: w.moved_aliases ?? [],
});

export interface ProjectDraft {
  name?: string;
  description?: string | null;
  icon?: string | null;
  aliases?: string[];
  archived?: boolean;
  is_default?: boolean;
}

export async function fetchProjects(): Promise<ProjectRow[]> {
  return ((await send('GET', '/projects')) as WireProjectRow[]).map(toProjectRow);
}

export async function createProject(draft: ProjectDraft & { name: string }): Promise<ProjectRow> {
  return toProjectRow(await send('POST', '/projects', { id: ulid(), ...draft }));
}

export async function patchProject(id: string, draft: ProjectDraft): Promise<ProjectRow> {
  return toProjectRow(await send('PATCH', `/projects/${id}`, draft));
}

/** Soft; its tasks move to the default project. */
export const deleteProject = (id: string) => send('DELETE', `/projects/${id}`);

// ─── schedules ───────────────────────────────────────────────────────────────

interface WireSchedule {
  id: string;
  job: string;
  label: string;
  blurb: string;
  at_local_time: string;
  repeat: 'daily' | 'weekly' | 'once';
  days: number[];
  enabled: boolean;
  last_run_local_day: string | null;
  last_run_at: string | null;
  last_error: string | null;
  due_now: boolean;
}

/** One thing Spica does on its own. `label` and `blurb` come from the server's
 *  job registry, so the client never holds a list of what jobs exist. */
export interface ScheduleRow {
  id: string;
  job: string;
  label: string;
  blurb: string;
  /** `HH:MM`, the user's own clock. */
  at: string;
  repeat: 'daily' | 'weekly' | 'once';
  days: number[];
  enabled: boolean;
  lastRunDay: string | null;
  lastError: string | null;
  dueNow: boolean;
  pending?: boolean;
}

const toSchedule = (w: WireSchedule): ScheduleRow => ({
  id: w.id,
  job: w.job,
  label: w.label,
  blurb: w.blurb,
  at: w.at_local_time.slice(0, 5),
  repeat: w.repeat,
  days: w.days,
  enabled: w.enabled,
  lastRunDay: w.last_run_local_day,
  lastError: w.last_error,
  dueNow: w.due_now,
});

export async function fetchSchedules(): Promise<ScheduleRow[]> {
  return (await call<WireSchedule[]>('/schedules', { label: 'schedules' })).map(toSchedule);
}

export async function patchSchedule(
  id: string,
  patch: { at_local_time?: string; enabled?: boolean; repeat?: string; days?: number[] },
): Promise<ScheduleRow> {
  return toSchedule((await send('PATCH', `/schedules/${id}`, patch)) as WireSchedule);
}


/* ─── commitments. spec/done/commitments.md ─────────────────────── */

interface WireCommitment {
  id: string;
  name: string;
  source: 'commitment' | 'borrowing';
  origin: 'manual' | 'rolled' | 'carried' | 'borrowing';
  category: string;
  expected_paise: number;
  paid_paise: number;
  owed_paise: number;
  over_paise: number;
  settled: boolean;
  skipped: boolean;
  due_day: number | null;
  repeats: boolean;
  amount_source: 'stated' | 'rolled';
  inferred_links: number;
  carried_from_month: string | null;
}

interface WireCommitments {
  month: string;
  editable: boolean;
  owed_paise: number;
  pool_paise: number;
  savings_target_paise: number;
  limit_paise: number | null;
  days_left: number;
  paid_count: number;
  open_count: number;
  items: WireCommitment[];
}

/** One line of what is owed. Paise, because a commitment is the one amount the
 *  page lets you edit, and rounding it to rupees on the way in would change it. */
export interface CommitmentRow {
  id: string;
  name: string;
  /** A borrowing is read-only here: it lives in udhaar. */
  source: 'commitment' | 'borrowing';
  origin: 'manual' | 'rolled' | 'carried' | 'borrowing';
  category: string;
  expectedPaise: number;
  paidPaise: number;
  owedPaise: number;
  overPaise: number;
  settled: boolean;
  skipped: boolean;
  dueDay: number | null;
  repeats: boolean;
  /** The amount was carried from last month, not stated — the amber dot. */
  rolled: boolean;
  /** Payments counted toward it only by a guess. */
  inferredLinks: number;
  /** ISO first of the month this remainder was carried from. */
  carriedFrom: string | null;
}

export interface CommitmentsPage {
  /** ISO first of the month. */
  month: string;
  /** Only the current month can be changed. */
  editable: boolean;
  owedPaise: number;
  poolPaise: number;
  savingsTargetPaise: number;
  /** Null is unknown — no income yet — never zero. May be negative. */
  limitPaise: number | null;
  daysLeft: number;
  paidCount: number;
  openCount: number;
  items: CommitmentRow[];
}

const toCommitment = (w: WireCommitment): CommitmentRow => ({
  id: w.id,
  name: w.name,
  source: w.source,
  origin: w.origin,
  category: w.category,
  expectedPaise: w.expected_paise,
  paidPaise: w.paid_paise,
  owedPaise: w.owed_paise,
  overPaise: w.over_paise,
  settled: w.settled,
  skipped: w.skipped,
  dueDay: w.due_day,
  repeats: w.repeats,
  rolled: w.amount_source === 'rolled',
  inferredLinks: w.inferred_links,
  carriedFrom: w.carried_from_month,
});

/** The month's commitments. Without `month`, the current one — which the server rolls forward on first read. */
export async function fetchCommitments(month?: string): Promise<CommitmentsPage> {
  const w = await call<WireCommitments>(`/commitments${month ? `?month=${month}` : ''}`, { label: 'commitments' });
  return {
    month: w.month,
    editable: w.editable,
    owedPaise: w.owed_paise,
    poolPaise: w.pool_paise,
    savingsTargetPaise: w.savings_target_paise,
    limitPaise: w.limit_paise ?? null,
    daysLeft: w.days_left,
    paidCount: w.paid_count,
    openCount: w.open_count,
    items: w.items.map(toCommitment),
  };
}

export interface CommitmentDraft {
  name: string;
  category: string;
  amountPaise: number;
  dueDay: number | null;
  repeats: boolean;
}

/** `id` is the client's, like every write: the same id again is a replay. */
export async function createCommitment(
  id: string,
  d: CommitmentDraft,
  linkTransactionIds: string[] = [],
): Promise<CommitmentRow> {
  return toCommitment(await send('POST', '/commitments', {
    id,
    name: d.name,
    category: d.category,
    amount_paise: d.amountPaise,
    ...(d.dueDay != null ? { due_day: d.dueDay } : {}),
    repeats: d.repeats,
    ...(linkTransactionIds.length ? { link_transaction_ids: linkTransactionIds } : {}),
  }));
}

/** Any of these; `dueDay: null` clears the day. */
export interface CommitmentChange {
  name?: string;
  category?: string;
  amountPaise?: number;
  dueDay?: number | null;
  repeats?: boolean;
  skipped?: boolean;
}

export async function patchCommitment(id: string, c: CommitmentChange): Promise<CommitmentRow> {
  return toCommitment(await send('PATCH', `/commitments/${id}`, {
    ...(c.name !== undefined ? { name: c.name } : {}),
    ...(c.category !== undefined ? { category: c.category } : {}),
    ...(c.amountPaise !== undefined ? { amount_paise: c.amountPaise } : {}),
    ...(c.dueDay !== undefined ? { due_day: c.dueDay } : {}),
    ...(c.repeats !== undefined ? { repeats: c.repeats } : {}),
    ...(c.skipped !== undefined ? { skipped: c.skipped } : {}),
  }));
}

/** Soft. Its payments become ordinary spending and the repeat ends. There is no undo. */
export const deleteCommitment = (id: string) => send('DELETE', `/commitments/${id}`);
