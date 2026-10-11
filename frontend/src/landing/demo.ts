import type { DeckData, LimitInfo, Profile } from '../data/api';
import { applyDeck } from '../data/live';
import { addDays, dayOfMonth, localToday, weekIndex } from '../lib/day';
import { color } from '../theme';
import type { Meal, Project, Todo, Tx } from '../types';

/**
 * One ordinary month, invented — the rows the landing page's deck runs on.
 *
 * The hero shows the app's real cards (ModeDeck, HeroCard, the ring maths in
 * `heroFor`), not a picture of them, so they need a deck to read. This is one:
 * built relative to today, so the card's windows — today, 7 days, the month —
 * always have something in them whatever day it is opened. Round amounts,
 * ordinary names, nobody's ledger.
 */

const TODAY_ISO = localToday();
const TODAY = dayOfMonth(TODAY_ISO);
const now = new Date();
const MONTH_DAYS = new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate();

const SALARY = 85000;
const SAVINGS_TARGET = 15000;

/**
 * Each day's spends cycle through these; today gets its own. About ₹1,200 a
 * day — the pace that keeps the demo's daily limit near ₹1,000 whatever day of
 * the month the page is opened on.
 */
const DAILY: [string, string, number][][] = [
  [['Swiggy', 'Food', 349], ['Chai', 'Food', 20], ['Lunch', 'Food', 240], ['Metro', 'Transport', 60]],
  [['Rapido', 'Transport', 160], ['Blinkit', 'Groceries', 478], ['Chai', 'Food', 20], ['Lunch', 'Food', 220]],
  [['Zomato', 'Food', 412], ['Uber', 'Transport', 231], ['Chai', 'Food', 20]],
  [['Recharge', 'Bills', 299], ['Lunch', 'Food', 260], ['DMart', 'Groceries', 1120]],
  [['Amazon', 'Shopping', 1299], ['Chai', 'Food', 20], ['Rapido', 'Transport', 140]],
  [['Movie night', 'Fun', 640], ['Dinner out', 'Food', 980], ['Uber', 'Transport', 260]],
  [['Petrol', 'Transport', 500], ['Blinkit', 'Groceries', 386], ['Chai', 'Food', 20], ['Lunch', 'Food', 240]],
];

const iso = (day: number) => `${TODAY_ISO.slice(0, 8)}${String(day).padStart(2, '0')}`;

function spends(): Tx[] {
  const rows: Tx[] = [];
  for (let day = 1; day < TODAY; day++) {
    DAILY[day % DAILY.length].forEach(([name, cat, amt], i) =>
      rows.push({ id: `demo-tx-${day}-${i}`, day, date: iso(day), name, cat, amt }),
    );
  }
  rows.push({ id: 'demo-tx-today-0', day: TODAY, date: TODAY_ISO, name: 'Chai', cat: 'Food', amt: 20 });
  rows.push({ id: 'demo-tx-today-1', day: TODAY, date: TODAY_ISO, name: 'Swiggy', cat: 'Food', amt: 349 });
  return rows;
}

const FIXED: Tx[] = [
  { id: 'demo-fx-rent', day: 1, date: iso(1), name: 'Rent', cat: 'Rent', amt: 22000, commitmentId: 'demo-c-rent' },
  { id: 'demo-fx-emi', day: Math.min(5, TODAY), date: iso(Math.min(5, TODAY)), name: 'EMI', cat: 'EMI', amt: 9800, commitmentId: 'demo-c-emi' },
];

/** Three meals most days, a skipped one now and then — logged days, not every day. */
function meals(): Meal[] {
  const rows: Meal[] = [];
  const usual: [string, string, number, number, number][] = [
    ['Poha', 'Breakfast', 12, 290, 45],
    ['Office thali', 'Lunch', 24, 640, 82],
    ['Dal chawal', 'Dinner', 16, 480, 70],
    ['Sattu + kela', 'Breakfast', 21, 340, 52],
    ['Paneer roti', 'Dinner', 28, 560, 48],
  ];
  for (let back = 9; back >= 1; back--) {
    if (back === 4) continue; // a day nothing was logged — unlogged is not fasting
    const date = addDays(TODAY_ISO, -back);
    [0, 1, 2].forEach((slot) => {
      const [name, type, p, k, c] = usual[(back + slot * 2) % usual.length];
      rows.push({ id: `demo-meal-${back}-${slot}`, day: dayOfMonth(date), date, name, type, p, k, c });
    });
  }
  rows.push({ id: 'demo-meal-today-0', day: TODAY, date: TODAY_ISO, name: 'Poha', type: 'Breakfast', p: 12, k: 290, c: 45 });
  rows.push({ id: 'demo-meal-today-1', day: TODAY, date: TODAY_ISO, name: 'Office thali', type: 'Lunch', p: 24, k: 640, c: 82 });
  return rows;
}

/**
 * Projects take the work hue's family, stepping in lightness — base, then ink —
 * and the default one the grey that ends every palette. Never the brand, and
 * never amber: that is the estimate dot's alone.
 */
const PROJECTS: Project[] = [
  { id: 'demo-p-work', name: 'Checkout', color: color.work, icon: 'icon:cart' },
  { id: 'demo-p-side', name: 'Side project', color: color.workInk, icon: 'icon:rocket' },
  { id: 'demo-p-me', name: 'Personal', color: color.grey, isDefault: true },
];

function todos(): Todo[] {
  const t = (id: string, name: string, project: string, extra: Partial<Todo> = {}): Todo => ({
    id: `demo-task-${id}`,
    name,
    project,
    kind: 'work',
    done: false,
    ...extra,
  });
  return [
    t('checkout', 'Fix the checkout bug', 'demo-p-work', { due: TODAY_ISO, src: 'Linear · ENG-142', origin: 'Linear', tracked: true, stage: 'In Progress' }),
    t('pricing', 'Send the pricing sheet', 'demo-p-work', { due: TODAY_ISO, src: 'Standup' }),
    t('deck', 'Share the deck with Rohan', 'demo-p-side', { due: addDays(TODAY_ISO, 1) }),
    t('domain', 'Renew the domain', 'demo-p-me', { due: addDays(TODAY_ISO, 3) }),
    t('copy', 'Write the onboarding copy', 'demo-p-side'),
    t('review', 'Review the cart PR', 'demo-p-work', { done: true, doneOn: addDays(TODAY_ISO, -1), due: addDays(TODAY_ISO, -1) }),
    t('login', 'Fix the login redirect', 'demo-p-work', { done: true, doneOn: addDays(TODAY_ISO, -2), due: addDays(TODAY_ISO, -2) }),
    t('logo', 'Pick a logo', 'demo-p-side', { done: true, doneOn: addDays(TODAY_ISO, -3) }),
  ];
}

/**
 * The Diet card's week strip: habits being built and habits being broken,
 * side by side — gym, a run, yoga; cigarettes, a couple of beers — on this
 * week's real days, Monday to today. Counts ride on the coin: three
 * cigarettes is one cigarette reading 3.
 */
function habitWeek() {
  const WEEK: [string, number?][][] = [
    [['gym'], ['cigarette', 3]],
    [['run'], ['cigarette', 2]],
    [['yoga']],
    [['gym'], ['cigarette', 1]],
    [['beer', 2], ['cigarette', 2]],
    [['run'], ['yoga']],
    [['gym'], ['cigarette', 1]],
  ];
  const monday = addDays(TODAY_ISO, -weekIndex(TODAY_ISO));
  return WEEK.slice(0, weekIndex(TODAY_ISO) + 1).flatMap((day, i) => {
    const date = addDays(monday, i);
    return day.map(([habit, amount], j) => ({
      id: `demo-habit-${i}-${j}`,
      day: dayOfMonth(date),
      date,
      habit,
      amount,
    }));
  });
}

const PROFILE: Profile = {
  id: 'demo',
  displayName: 'You',
  email: null,
  avatarUrl: null,
  onboardingDoneAt: TODAY_ISO,
  dob: null,
  gender: null,
  heightCm: null,
  city: null,
  diet: null,
  timezone: 'Asia/Kolkata',
  savingsTarget: SAVINGS_TARGET,
  kcalTarget: 2000,
  proteinTarget: 90,
  carbsTarget: 250,
  fatTarget: null,
  fibreTarget: null,
  weightTargetKg: null,
  sleepTargetMin: null,
  stepTarget: null,
};

const tx = spends();
const committedTx = FIXED.filter((f) => f.day <= TODAY);
const fixedPaid = committedTx.reduce((a, t) => a + t.amt, 0);
const logged = tx.reduce((a, t) => a + t.amt, 0);
/** Internet and gym, not paid yet this month — held out of the pool. */
const LOCKED = 1800;
const daysLeft = MONTH_DAYS - TODAY + 1;
const pool = SALARY - fixedPaid - logged;
const spentToday = tx.filter((t) => t.date === TODAY_ISO).reduce((a, t) => a + t.amt, 0);
// The server's shape, not its code: what is free after the goal and the
// commitments, spread over the days left. Only ever a number on the demo card.
const limit = Math.max(0, Math.round((pool + spentToday - LOCKED - SAVINGS_TARGET) / daysLeft / 10) * 10);

export const DEMO_LIMIT: LimitInfo = {
  limit,
  spentToday,
  left: limit - spentToday,
  pool,
  locked: LOCKED,
  fixedPaid,
  daysLeft,
};

export const DEMO_DECK: DeckData = {
  today: TODAY,
  todayISO: TODAY_ISO,
  month: now.getMonth(),
  year: now.getFullYear(),
  monthDays: MONTH_DAYS,
  tx,
  committedTx,
  salaryToday: false,
  meals: meals(),
  workouts: [],
  habitLogs: habitWeek(),
  sleep: [],
  todos: todos(),
  projects: PROJECTS,
  bankBalance: 0,
  profile: PROFILE,
  fixedPaid,
  income: SALARY,
  pending: [
    { id: 'demo-lent-1', leg: 'lent', label: 'Rohit', amount: 1500, remaining: 1500, date: addDays(TODAY_ISO, -12), day: dayOfMonth(addDays(TODAY_ISO, -12)) },
  ],
  borrowed: [],
  repayments: [],
  lentMonth: 1500,
  repaidMonth: 0,
  borrowedMonth: 0,
  paidBackMonth: 0,
  incomeSources: [{ label: 'Salary', amount: SALARY }],
  onboarding: { done_at: TODAY_ISO },
};

/** What each hero demo's sentence adds, so the real card moves when it lands. */
export const DEMO_LOGGED = {
  paisa: { id: 'demo-tx-said', day: TODAY, date: TODAY_ISO, name: 'Rapido', cat: 'Transport', amt: 160, confidence: 0.8 } as Tx,
  diet: { id: 'demo-meal-said', day: TODAY, date: TODAY_ISO, name: '2 roti, dal, salad', type: 'Dinner', p: 18, k: 410, c: 58, confidence: 0.7 } as Meal,
  work: 'demo-task-pricing',
};

let applied = false;

/**
 * Writes the example month into the live bindings, once. The hero's deck and
 * the Work chapter's list both read them (a task row asks `projectOf`), and
 * whichever renders first does it. Only the lazy-loaded landing calls this.
 */
export function ensureDemoDeck(): void {
  if (applied) return;
  applyDeck(DEMO_DECK);
  applied = true;
}
