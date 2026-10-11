/**
 * The loaded deck, readable as ordinary module values.
 *
 * These are `let` exports, which ES modules keep as live bindings: `loadDeck()`
 * reassigns them here and every importer sees the new value without changing a
 * line. `metrics.ts`, `tasks.ts` and `workouts.ts` therefore keep their
 * arithmetic byte-for-byte while the numbers underneath become real.
 *
 * `App` awaits `loadDeck()` before rendering, so nothing observes the blanks.
 */

import {
  fetchDeck,
  type DeckData,
  type HabitLogRow,
  type PendingItem,
  type Profile,
  type RepaymentItem,
} from './api';
import { localToday } from '../lib/day';
import type { Meal, Project, Todo, Tx, Workout } from '../types';

export interface NightSleep {
  date: string;
  startMin: number;
  endMin: number;
  source: 'confirmed' | 'estimated';
  confidence: number;
}

export interface DaySteps {
  date: string;
  steps: number;
}

const now = new Date();

/* Dates come from the device's clock. The seed pinned TODAY to 22 August and
   never moved; that lie ends here. */
export let TODAY = now.getDate();
/** Today as an ISO local day. `TODAY` is only a day-of-month: every bucket,
 *  window and "is this today" test reads this instead. */
export let TODAY_ISO = localToday();
export let MONTH_DAYS = new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate();
export let DATA_MONTH = now.getMonth();
export let DATA_YEAR = now.getFullYear();
/** The diet card reads the same day — they were only separate in the seed. */
export let DIET_TODAY = now.getDate();
export let DIET_TODAY_ISO = localToday();

export let seedTx: Tx[] = [];
/** This month's payments that count toward a commitment — paid, never spendable. */
export let seedCommittedTx: Tx[] = [];
export let seedMeals: Meal[] = [];
export let seedTodos: Todo[] = [];
export let seedWorkouts: Workout[] = [];
export let HABIT_DAYS: { date: string; habit: string; amount?: number }[] = [];
export let HABIT_LOGS: HabitLogRow[] = [];
/** Nights with a recorded sleep, in hours. Empty means unrecorded, never zero. */
export let SLEEP_HOURS: { day: number; date: string; hours: number }[] = [];
export let PROJECTS: Project[] = [];

export let BANK_BALANCE = 0;

/**
 * The person. Targets used to be constants in config.ts — the bank-balance
 * lesson applied: a client constant is quietly wrong the day it changes. They
 * come from the users row now, and `setProfile` is the one place they change,
 * so an edit on the deck and a fresh load walk the same path.
 */
export let PROFILE: Profile = {
  id: '',
  displayName: '',
  email: null,
  avatarUrl: null,
  onboardingDoneAt: null,
  dob: null,
  gender: null,
  heightCm: null,
  city: null,
  diet: null,
  timezone: 'Asia/Kolkata',
  savingsTarget: null,
  kcalTarget: null,
  proteinTarget: null,
  carbsTarget: null,
  fatTarget: null,
  fibreTarget: null,
  weightTargetKg: null,
  sleepTargetMin: null,
  stepTarget: null,
};
/**
 * Whether the first run is behind them — finished or skipped. Once set it
 * stays set; while it is null the gate shows the first run before the app.
 */
export let ONBOARDING_DONE_AT: string | null = null;

/** The limit needs a number: no goal set means nothing held back for one. */
export let SAVINGS_TARGET = 0;
/** Null = no target set. Rings then show the value with no denominator. */
export let PROTEIN_TARGET: number | null = null;
export let KCAL_TARGET: number | null = null;
export let CARB_TARGET: number | null = null;
export let SLEEP_TARGET_MIN: number | null = null;
export let STEP_TARGET: number | null = null;

export function setProfile(p: Profile): void {
  PROFILE = p;
  SAVINGS_TARGET = p.savingsTarget ?? 0;
  PROTEIN_TARGET = p.proteinTarget;
  KCAL_TARGET = p.kcalTarget;
  CARB_TARGET = p.carbsTarget;
  SLEEP_TARGET_MIN = p.sleepTargetMin;
  STEP_TARGET = p.stepTarget;
}
export let SALARY = 0;
/** An income row on the anchor day: the day the greeting says what is locked. */
export let SALARY_TODAY = false;

/**
 * Sleep and steps have no rows to draw. Sleep exists on `days` but was answered
 * 3 times in 24; steps need Health Connect, which is phase 6. Empty is the
 * honest value — the seed's invented weeks were the violation.
 */
export const SLEEP: NightSleep[] = [];
export const STEPS: DaySteps[] = [];

/** Money still out with people, one row per lending; and every repayment. */
export let PENDING: PendingItem[] = [];
/** What you still owe people, one row per borrowing. Never in the pool: not your money. */
export let BORROWED: PendingItem[] = [];
export let REPAYMENTS: RepaymentItem[] = [];
/** The month's two udhaar legs, for the pool. */
export let LENT_MONTH = 0;
export let REPAID_MONTH = 0;
export let BORROWED_MONTH = 0;
export let PAID_BACK_MONTH = 0;

export interface Udhaar {
  pending: PendingItem[];
  borrowed: PendingItem[];
  repayments: RepaymentItem[];
  lentMonth: number;
  repaidMonth: number;
  borrowedMonth: number;
  paidBackMonth: number;
}

/** One place these change — a fresh load and a repayment on the report walk the same path. */
export function setUdhaar(u: Udhaar): void {
  PENDING = u.pending;
  BORROWED = u.borrowed;
  REPAYMENTS = u.repayments;
  LENT_MONTH = u.lentMonth;
  REPAID_MONTH = u.repaidMonth;
  BORROWED_MONTH = u.borrowedMonth;
  PAID_BACK_MONTH = u.paidBackMonth;
}
export let INCOME_SOURCES: { label: string; amount: number }[] = [];

export async function loadDeck(): Promise<void> {
  applyDeck(await fetchDeck());
}

/**
 * Sets every binding from one deck. `loadDeck` is the server's copy; the
 * landing page hands it example rows, so the deck it shows is the app's own
 * code on data nobody owns (the landing page).
 */
export function applyDeck(d: DeckData): void {
  TODAY = d.today;
  TODAY_ISO = d.todayISO;
  MONTH_DAYS = d.monthDays;
  DATA_MONTH = d.month;
  DATA_YEAR = d.year;
  DIET_TODAY = d.today;
  DIET_TODAY_ISO = d.todayISO;

  seedTx = d.tx;
  seedCommittedTx = d.committedTx;
  SALARY_TODAY = d.salaryToday;
  seedMeals = d.meals;
  seedTodos = d.todos;
  seedWorkouts = d.workouts;
  HABIT_LOGS = d.habitLogs;
  HABIT_DAYS = d.habitLogs.map((l) => ({ date: l.date, habit: l.habit, amount: l.amount }));
  SLEEP_HOURS = d.sleep;
  PROJECTS = d.projects;

  BANK_BALANCE = d.bankBalance;
  ONBOARDING_DONE_AT = d.onboarding.done_at;
  setProfile(d.profile);
  SALARY = d.income;
  setUdhaar(d);
  INCOME_SOURCES = d.incomeSources;
}
