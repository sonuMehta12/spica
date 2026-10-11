import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ns } from '../brand';
import { loadDeck } from '../data/live';
import { BORROWED, BORROWED_MONTH, CARB_TARGET, DATA_MONTH, MONTH_DAYS, SAVINGS_TARGET, DATA_YEAR, DIET_TODAY, DIET_TODAY_ISO, HABIT_LOGS, KCAL_TARGET, LENT_MONTH, PAID_BACK_MONTH, PENDING, PROFILE, PROTEIN_TARGET, REPAID_MONTH, REPAYMENTS, SALARY, SALARY_TODAY, TODAY, TODAY_ISO, seedCommittedTx, seedMeals, seedTodos, seedTx, seedWorkouts, setProfile, setUdhaar } from '../data/live';
import { GROUP_OF, clearEdit, parseKg, parseProfileEdit, type FieldId, type GroupKey } from './profileEdit';
import { initialStack, sameEntry, useNav, type Screen } from './nav';
import {
  dietConfirm,
  paisaConfirm,
  stubMsg,
  todoMsg,
  userMsg,
} from '../agent/messages';
import { LISTEN_MS, SAVING_MS, THINKING_MS, VOICE_SCRIPT } from '../agent/script';
import { toChatMsg } from '../agent/wire';
import { MODES, WORK_NOTE, modeIndex, rangeFor } from '../modes';
import { heroTasks, openTasks, projectStats } from '../work/tasks';
import { weekChain, weekCount } from '../diet/workouts';
import type { ReportMode, ReportRange } from '../report/metrics';
import { LIBRARY, type SavedItem } from '../data/vault';
import type { Section } from '../vault/stats';
import { rupees } from '../lib/format';
import { mealChips, spendChips } from '../lib/chips';
import { addDays, diffDays, monthStart, weekIndex } from '../lib/day';
import { ulid } from '../lib/ulid';
import type { Edits as PersonEdits } from '../components/vault/PeopleSection';
import { rereadWeighIns } from '../components/messages/live';
import type {
  ComposerContext,
  ConfirmMsg,
  SuggestItem,
} from '../types';
import {
  actChat,
  createCommitment,
  createCounterparty,
  createExercise,
  createMeal,
  createMemory,
  createOpen,
  createPantryMove,
  createPlace,
  createRepayment,
  createTransaction,
  createWeighIn,
  deleteCommitment as deleteCommitmentApi,
  deleteHabitLog as deleteHabitLogApi,
  deleteMeal,
  deleteMemory,
  deletePantryMove,
  deletePlace,
  deleteTask as deleteTaskApi,
  deleteTransaction,
  deleteWeighIn,
  didExercise,
  errorStatus,
  fetchChat,
  fetchCommitments,
  fetchDishes,
  fetchExercises,
  CHAT_PAGE,
  clearChat,
  createHabit,
  deleteHabit,
  fetchHabits,
  fetchSchedules,
  fetchLimit,
  fetchPantry,
  fetchPantryMoves,
  fetchPeople,
  fetchPlaces,
  fetchRowsByIds,
  giftLending,
  isoDay,
  listMemories,
  listWeighIns,
  mealTypeNow,
  patchCommitment,
  patchCounterparty,
  patchHabit,
  patchSchedule,
  patchMeal,
  patchMemory,
  patchPantryItem,
  patchPlace,
  patchTask,
  patchTransaction,
  patchUser,
  restoreMeal,
  restoreTransaction,
  saveDish,
  sendChat,
  stopTracking,
  trackFood,
  type CommitmentChange,
  type CommitmentDraft,
  type CommitmentRow,
  type CommitmentsPage,
  type DishRow,
  type ExerciseRow,
  type HabitLogRow,
  type LimitInfo,
  type HabitRow,
  type ScheduleRow,
  type MemoryRow,
  type PantryMoveRow as PantryMove,
  type PantryRow,
  type PendingItem,
  type PersonRow,
  type PlaceRow,
  type Profile,
  type RepaymentItem,
  type WeighInRow,
  type WireTurn,
  unsaveDish,
} from '../data/api';
import { color } from '../theme';
import type {
  ChatMsg,
  HeroView,
  Meal,
  Mode,
  Range,
  Suggestion,
  Todo,
  Tx,
} from '../types';

interface State {
  mode: Mode;
  range: Range;
  listening: boolean;
  /**
   * What the agent is visibly doing, for the live row's mascot. `listening` is
   * separate because it also drives the waveform and the composer.
   */
  phase: 'idle' | 'thinking' | 'saving';
  /** Composer has focus, or the mic is running — the deck stands down. */
  composing: boolean;
  typed: string;
  /**
   * Bumped whenever something claims the composer for the user — a card's
   * Change, say. The composer focuses on the change; a counter rather than a
   * boolean so the same claim twice still focuses.
   */
  composeFocus: number;
  scriptIdx: number;
  /**
   * The screens open over Home, bottom first — the menu, the Report, Your
   * data, Profile, the commitment sheet. Empty is Home. Mirrored into
   * history.state (state/nav.ts), so a reload reopens the screen it left.
   */
  stack: Screen[];
  moreOpen: boolean;
  /** Id of the ledger row whose edit/delete tray is expanded, if any. */
  openRow: string | null;
  /** Rows chat cards named from outside the deck's window, fetched by id. */
  fetchedTx: Tx[];
  fetchedMeals: Meal[];
  /**
   * Ids deleted this session — by a delete card, an Undo or a ⋮ Delete —
   * struck wherever shown and out of every sum. Undo on a removed row (its
   * restore route) takes the id back out.
   */
  deletedRows: string[];
  /** Suggestion ref → the meal it was logged as, by a tap this session. */
  suggestLogged: Record<string, string>;
  /** Suggestion refs with a log in flight. */
  pendingLogs: string[];
  /** A receipt that flashes and goes — a tap's confirmation, a refused tray action. */
  toast: { id: number; text: string; sub?: string; failed?: boolean } | null;
  /** Paging the thread. `chatOlder` is the cursor for the next page back. */
  chatOlder: number | null;
  chatHasMore: boolean;
  chatLoadingOlder: boolean;
  /** What the user cleared from view; 0 if never. Offers *Show older*. */
  chatCleared: number;
  /** A clear is in flight. It folds the thread, which is a model call. */
  chatClearing: boolean;
  /**
   * The row the composer is correcting, if any. While set, send() PATCHes this
   * row instead of logging a new one — and the bar shows a chip saying so, so
   * a plain "chai 40" can never silently overwrite whatever was last opened.
   */
  editing: { source: 'paisa' | 'diet'; id: string; label: string } | null;
  /**
   * What a card's Change hung on the composer — drawn as a pill above the
   * text, never typed into it. The next send goes to the agent as the
   * context's words and then what was typed, and the context comes off.
   */
  context: ComposerContext | null;
  /** The report has its own mode and range, independent of the deck. */
  reportMode: ReportMode;
  reportRange: ReportRange;
  library: SavedItem[];
  usedSuggs: string[];
  todos: typeof seedTodos;
  workouts: typeof seedWorkouts;
  /** Every habit log, in state so a delete reflects on the strip and the report. */
  habitLogs: HabitLogRow[];
  chat: ChatMsg[];
  tx: Tx[];
  /** This month's payments that count toward a commitment, apart so the spend arithmetic never sees them. */
  committedTx: Tx[];
  meals: Meal[];
  /** The person. Targets come from here, never from a constant. */
  profile: Profile;
  memories: MemoryRow[];
  /** What you have decided to track. Ticks live on Day; this is the list. */
  habits: HabitRow[];
  /** What Spica does on its own, and when. */
  schedules: ScheduleRow[];
  weighIns: WeighInRow[];
  /** Udhaar, in state so Repaid / Gift / Undo reflect at once. Mirrors data/live. */
  /** Your data → Pantry: the tracked foods and the moves ledger behind them. */
  pantry: PantryRow[];
  pantryMoves: PantryMove[];
  /** Your dish library — saved or tried. The pool is searched, not held. */
  dishes: DishRow[];
  /** Everyone the ledger has a counterparty row for. Numbers are the server's. */
  people: PersonRow[];
  /** The exercise library — what exists to suggest from. No ledger: a workout
   * is a habit tick. */
  exercises: ExerciseRow[];
  /** Pins, with their payment counts already summed by the server. */
  places: PlaceRow[];
  /** The daily limit and what it is made of — computed on the server, never
   * here. Null until the first fetch lands; the card shows — until then. */
  limitInfo: LimitInfo | null;
  /** What is owed this month, line by line — the server's, like the limit.
   *  Null until the first read lands. */
  commitments: CommitmentsPage | null;
  pending: PendingItem[];
  borrowed: PendingItem[];
  repayments: RepaymentItem[];
  lentMonth: number;
  repaidMonth: number;
  borrowedMonth: number;
  paidBackMonth: number;
}

/**
 * The commitment sheet — a stack entry, opened from Your data, the Report's
 * Commits tab, a payment's tray or a chat card. `editing` is the line being
 * changed; otherwise it makes a new one — pre-filled from a payment when `payment` is set, which the
 * new line will then count.
 */
export interface CommitmentSheet {
  editing: CommitmentRow | null;
  payment: { id: string; name: string; category: string; amountPaise: number } | null;
}

/**
 * Built lazily, not as a module constant: the deck's rows arrive from the
 * server after this module loads, and a constant would capture the blanks that
 * exist before `loadDeck()` returns.
 */
const initialState = (): State => ({
  mode: 'paisa',
  range: 'aaj',
  listening: false,
  phase: 'idle',
  composing: false,
  typed: '',
  composeFocus: 0,
  scriptIdx: 0,
  stack: initialStack(),
  moreOpen: false,
  openRow: null,
  fetchedTx: [],
  fetchedMeals: [],
  deletedRows: [],
  suggestLogged: {},
  pendingLogs: [],
  toast: null,
  chatOlder: null,
  chatHasMore: false,
  chatLoadingOlder: false,
  chatCleared: 0,
  chatClearing: false,
  editing: null,
  context: null,
  profile: PROFILE,
  memories: [],
  habits: [],
  schedules: [],
  weighIns: [],
  pantry: [],
  pantryMoves: [],
  dishes: [],
  people: [],
  exercises: [],
  places: [],
  limitInfo: null,
  commitments: null,
  pending: PENDING,
  borrowed: BORROWED,
  repayments: REPAYMENTS,
  lentMonth: LENT_MONTH,
  repaidMonth: REPAID_MONTH,
  borrowedMonth: BORROWED_MONTH,
  paidBackMonth: PAID_BACK_MONTH,
  reportMode: 'paisa',
  // The month so far, not a rolling week: on the 7th that is 7 days, on the
  // 29th it is 29. A report answers "how am I doing" and the answer resets
  // with the month — the salary, the limit and the saving target all do.
  reportRange: 'mahina',
  library: LIBRARY,
  usedSuggs: [],
  todos: seedTodos,
  workouts: seedWorkouts,
  habitLogs: HABIT_LOGS,
  chat: [],
  tx: seedTx,
  committedTx: seedCommittedTx,
  meals: seedMeals,
});

/** A row into a list by id: replaced where it stands, or added at the end. */
const upsert = <T extends { id: string }>(list: T[], row: T): T[] =>
  list.some((x) => x.id === row.id) ? list.map((x) => (x.id === row.id ? row : x)) : [...list, row];

const withId = (ids: string[], id: string) => (ids.includes(id) ? ids : [...ids, id]);

/**
 * A payment or a meal gone from the ledger, as state: out of the deck's
 * lists, so no sum counts it; into the deleted set, so every card strikes
 * it; and a struck copy kept with the fetched rows, so a table or a receipt
 * can still say what it was.
 */
function struck(cur: State, source: 'paisa' | 'diet', id: string): Partial<State> {
  if (source === 'paisa') {
    const row =
      cur.tx.find((x) => x.id === id) ?? cur.committedTx.find((x) => x.id === id) ?? cur.fetchedTx.find((x) => x.id === id);
    return {
      tx: cur.tx.filter((x) => x.id !== id),
      committedTx: cur.committedTx.filter((x) => x.id !== id),
      fetchedTx: row ? upsert(cur.fetchedTx, { ...row, deleted: true }) : cur.fetchedTx,
      deletedRows: withId(cur.deletedRows, id),
    };
  }
  const row = cur.meals.find((x) => x.id === id) ?? cur.fetchedMeals.find((x) => x.id === id);
  return {
    meals: cur.meals.filter((x) => x.id !== id),
    fetchedMeals: row ? upsert(cur.fetchedMeals, { ...row, deleted: true }) : cur.fetchedMeals,
    deletedRows: withId(cur.deletedRows, id),
  };
}

/**
 * Spend allowance for the rest of the month, per day — pure ledger arithmetic.
 *
 *   (income − fixed − spent so far − goal shortfall) ÷ days left
 *
 * The transactions are trusted as the complete story; nothing outside the
 * ledger feeds this number. Two cleverer versions died here: a stored bank
 * constant went stale, and a roll-forward from a balance check couldn't see
 * cash. The stated bank balance still exists — but for the reconciliation
 * gap in the report, never for the limit.
 *
 * Money that left is gone, money that came is here: the pool counts a lending
 * out and a repayment in, and never counts what is still pending
 * (spec/in-progress/udhaar-repayment.md).
 */
const GREETED_KEY = ns('lockedGreetedOn');
const anchorKey = () => isoDay(DATA_YEAR, DATA_MONTH, TODAY);
function greetedToday(): boolean {
  try {
    return localStorage.getItem(GREETED_KEY) === anchorKey();
  } catch {
    return false;
  }
}
function markGreeted(): void {
  try {
    localStorage.setItem(GREETED_KEY, anchorKey());
  } catch {
    /* private mode: the line shows again tomorrow, which is fine */
  }
}


/** Everything the hero pages need, rolled up once per render. */
export interface Snapshot {
  tx: Tx[];
  /** Payments counted toward a commitment this month, and what is still locked. */
  committedTx: Tx[];
  fixedPaid: number;
  locked: number;
  /** Still out on loan. Leaves the pool, so it moves the limit, but it is
   *  not spending and never reaches the Total ring. */
  lentOut: number;
  spentToday: number;
  totalLogged: number;
  /** Keyed by ISO local day. A day-of-month key merges 13 Aug into 13 Sep. */
  dayP: Record<string, number>;
  dayK: Record<string, number>;
  dayC: Record<string, number>;
  /** Meals whose carbs are actually known — the denominator behind dayC. */
  knownC: number;
  todayP: number;
  todayK: number;
  todayC: number;
  dietDays: string[];
}

/** A row's ISO day. A row written optimistically has none until the server
 *  answers — it was written just now, so it is today's. */
const isoOf = (r: { date?: string }) => r.date ?? TODAY_ISO;

/** What the hero cards are computed from — the landing page supplies its own. */
export type DeckRows = Pick<State, 'meals' | 'tx' | 'committedTx' | 'limitInfo' | 'pending'>;

export function rollUp(s: DeckRows): Snapshot {
  const dayP: Record<string, number> = {};
  const dayK: Record<string, number> = {};
  const dayC: Record<string, number> = {};
  let knownC = 0;
  for (const m of s.meals) {
    const d = isoOf(m);
    dayP[d] = (dayP[d] ?? 0) + m.p;
    dayK[d] = (dayK[d] ?? 0) + m.k;
    if (m.c != null) {
      dayC[d] = (dayC[d] ?? 0) + m.c;
      knownC += 1;
    }
  }
  return {
    tx: s.tx,
    committedTx: s.committedTx,
    fixedPaid: s.committedTx.reduce((a, t) => a + t.amt, 0),
    // From the server, with the limit — the same computation the card and the
    // agent read. spec/agent-tools.md.
    locked: s.limitInfo?.locked ?? 0,
    // Money out on loan. It leaves the pool, so it moves the limit, but it is
    // not spending and never reaches the Total ring — so lending ₹10,000
    // changed nothing a person could see on the card.
    lentOut: s.pending.reduce((a, p) => a + p.remaining, 0),
    spentToday: s.tx.filter((t) => isoOf(t) === TODAY_ISO).reduce((a, t) => a + t.amt, 0),
    totalLogged: s.tx.reduce((a, t) => a + t.amt, 0),
    dayP,
    dayK,
    dayC,
    knownC,
    todayP: dayP[DIET_TODAY_ISO] ?? 0,
    todayK: dayK[DIET_TODAY_ISO] ?? 0,
    todayC: dayC[DIET_TODAY_ISO] ?? 0,
    dietDays: Object.keys(dayP).sort(),
  };
}

/**
 * The Work card's band: Open · Late · Done this week, counted from the live
 * todos at render time. Work tasks only — a gym fee is not work.
 */
function workStrip(todos: Todo[]): NonNullable<HeroView['strip']> {
  const work = todos.filter((t) => t.kind === 'work');
  const open = work.filter((t) => !t.done);
  const late = open.filter((t) => t.due != null && t.due < TODAY_ISO).length;
  const monday = addDays(TODAY_ISO, -weekIndex(TODAY_ISO));
  const doneWeek = work.filter((t) => t.done && t.doneOn != null && t.doneOn >= monday && t.doneOn <= TODAY_ISO).length;
  return [
    { key: 'open', label: 'Open', value: String(open.length) },
    { key: 'late', label: 'Late', value: String(late), tone: late ? 'red' : 'ink' },
    { key: 'done', label: 'Done this week', value: String(doneWeek) },
  ];
}

/**
 * One hero page: concentric arcs, outermost first. Computed for every mode, not
 * just the active one, so the whole deck can be on-screen mid-swipe.
 */
export function heroFor(
  mode: Mode,
  range: Range,
  snap: Snapshot,
  limit: number | null,
  pool: number,
  todos: Todo[],
  habitDays: { date: string; habit: string; amount?: number }[],
): HeroView {
  const def = MODES.find((m) => m.id === mode) ?? MODES[0];

  if (!def.live) {
    return { mode, label: def.label, live: false, rings: [], hasMacros: false, note: WORK_NOTE };
  }

  // The deck shares one range across all three cards, but they do not all offer
  // the same ones. Compute on what the dropdown is actually showing, or the
  // label and the numbers drift apart.
  const scoped = rangeFor(mode, range);

  if (mode === 'work') {
    return {
      mode,
      label: def.label,
      live: true,
      hasMacros: false,
      rings: [],
      projects: projectStats(todos, scoped),
      tasks: heroTasks(todos),
      openCount: openTasks(todos).length,
      // The same band as Paisa's, so all three cards share one anatomy. From
      // the live todos, whatever the range: what is open now, what of it is
      // late, and what got finished this calendar week.
      strip: workStrip(todos),
    };
  }


  if (mode === 'paisa') {
    const minDay =
      scoped === 'aaj'
        ? TODAY_ISO
        : scoped === '7din'
          ? addDays(TODAY_ISO, -6)
          : monthStart(TODAY_ISO);
    const rangeTotal = snap.tx.filter((t) => isoOf(t) >= minDay).reduce((a, t) => a + t.amt, 0);
    const rangeDays =
      scoped === 'aaj' ? 1 : scoped === '7din' ? 7 : diffDays(monthStart(TODAY_ISO), TODAY_ISO) + 1;
    const cur = scoped === 'aaj' ? snap.spentToday : rangeTotal / rangeDays;
    // Unknown is not zero: with no limit there is nothing to be over.
    const over = limit != null && cur > limit;
    const spentThisMonth = snap.fixedPaid + snap.totalLogged;
    // Pace is discretionary spending only: the fixed costs of the rest of the
    // month are already in `locked`, so counting them here would charge for
    // them twice.
    const pace = snap.totalLogged / Math.max(1, TODAY);
    const daysLeft = MONTH_DAYS - TODAY + 1;
    const projected = Math.round(pool - snap.locked - pace * daysLeft);
    // No explainer line: Total and Aaj carry the story, and the goal behind
    // the limit is a profile setting, not card copy. Tried twice, confused
    // twice, removed on the user's call.
    return {
      mode,
      label: def.label,
      live: true,
      hasMacros: false,
      // Where the month lands at three rates — the cricket projected score.
      // On the card, not the report: it answers "aage kya", which is the
      // question you have while looking at the arc.
      // Three numbers, three questions, two rows. What is safe to spend, what
      // is still owed, and what is with other people. The projected savings
      // rates that stood here answered none of them, and `committed` — the
      // number that explains a ₹0 limit — was reachable only through the ⋮
      // menu. spec/done/commitments.md § the card.
      strip: [
        // Where the month lands if the current pace holds, against the goal.
        // The daily limit is not repeated here — the Today ring already shows
        // it as its denominator, and one number in two places is how they
        // start disagreeing.
        {
          key: 'saves',
          // Not "saves" alone: read next to a ₹19,401 balance it looked like
          // the money in hand. "Expected" is the whole description — this is
          // where the month LANDS at the current pace, not what is left today.
          label: 'Expected saving',
          value: rupees(projected),
          // The goal is not printed beside it. It lives in the ⋮ menu, and on
          // a card this size a second number next to the first invites the
          // two to be read as one figure. Red still carries the comparison.
          tone: projected < SAVINGS_TARGET ? 'red' : 'ink',
        },
        { key: 'committed', label: 'Committed', value: rupees(snap.locked) },
        { key: 'lent', label: 'Lent out', value: rupees(snap.lentOut) },
      ],
      locked: snap.locked,
      rings: [
        {
          key: 'month',
          caption: 'This month',
          valueStr: rupees(spentThisMonth),
          // SALARY is 0 until the income row arrives (and stays 0 in a month
          // with none). No denominator → no arc, same rule as the diet
          // targets — never 0/0, which is NaN and an empty SVG attribute.
          totalStr: SALARY ? rupees(SALARY) : '',
          pct: SALARY ? spentThisMonth / SALARY : 0,
          // Fixed commitments are already spoken for — drawn as a paler stretch
          // of the same arc, with logged spending continuing in full strength.
          basePct: SALARY ? snap.fixedPaid / SALARY : 0,
          // The mode's hue, stepped: the month in soft, today in base — one
          // family, and the two legend dots still read apart.
          color: color.paisaSoft,
        },
        {
          key: 'today',
          caption: scoped === 'aaj' ? 'Today' : 'Average',
          valueStr: rupees(cur),
          // No denominator when there is no limit. "₹200 / ₹0" reads as a
          // broken ring; the limit being zero is a real state — everything
          // this month is already committed — and the strip below says so.
          // Unknown (no income yet) reads —; zero is nothing free; below zero is
          // past the line and says so with its minus.
          totalStr: limit == null ? '—' : limit === 0 ? 'nothing free' : rupees(limit),
          pct: limit == null ? 0 : limit > 0 ? cur / limit : 1,
          color: over ? color.red : color.paisa,
        },
      ],
    };
  }

  // Calendar windows, not "the last 7 days that have logs" — a window that
  // slides back to wherever data exists reports last month's average as this
  // week's, which is a flattering number, and flattering numbers are what the
  // honesty rule exists for.
  const winStart =
    scoped === 'aaj'
      ? DIET_TODAY_ISO
      : scoped === '7din'
        ? addDays(DIET_TODAY_ISO, -6)
        : monthStart(DIET_TODAY_ISO);
  const calDays = diffDays(winStart, DIET_TODAY_ISO) + 1;
  const days = snap.dietDays.filter((d) => d >= winStart && d <= DIET_TODAY_ISO);
  // Averages divide by LOGGED days: an unlogged day is missing data, not
  // fasting. The denominator is shown, not hidden — see `coverage`.
  const span = Math.max(1, days.length);
  const avgP = days.reduce((a, d) => a + (snap.dayP[d] ?? 0), 0) / span;
  const avgK = days.reduce((a, d) => a + (snap.dayK[d] ?? 0), 0) / span;
  const avgC = days.reduce((a, d) => a + (snap.dayC[d] ?? 0), 0) / span;
  const kNow = scoped === 'aaj' ? snap.todayK : Math.round(avgK);
  const coverage =
    scoped === 'aaj'
      ? days.length
        ? undefined
        : 'nothing logged yet today'
      : `${days.length}/${calDays} days logged`;
  // Always the current week, whatever the ring range is — the strip answers a
  // different question and a 30-day "week" is not a thing.
  const chain = weekChain(habitDays);
  return {
    mode,
    label: def.label,
    live: true,
    hasMacros: true,
    chain,
    chainCount: weekCount(chain),
    coverage,
    rings: [
      {
        key: 'kcal',
        caption: 'Calories',
        valueStr: kNow.toLocaleString('en-IN'),
        // No target → no denominator. The value stands alone rather than
        // against an invented 2,050.
        totalStr: KCAL_TARGET == null ? '' : KCAL_TARGET.toLocaleString('en-IN'),
        pct: KCAL_TARGET ? kNow / KCAL_TARGET : 0,
        // Diet's hue, stepped: calories in base, protein in ink, carbs soft.
        color: KCAL_TARGET != null && kNow > KCAL_TARGET ? color.red : color.diet,
      },
      {
        key: 'protein',
        caption: scoped === 'aaj' ? 'Protein' : 'Protein avg',
        valueStr: `${Math.round(avgP)}g`,
        totalStr: PROTEIN_TARGET == null ? '' : `${PROTEIN_TARGET}g`,
        pct: PROTEIN_TARGET ? avgP / PROTEIN_TARGET : 0,
        color: color.dietInk,
      },
      {
        key: 'carbs',
        caption: 'Carbs',
        // '—' when no meal in view carries carbs: a 0 would read as 'ate no
        // carbs', and unknown is not zero.
        valueStr: snap.knownC ? `${Math.round(scoped === 'aaj' ? snap.todayC : avgC)}g` : '—',
        totalStr: CARB_TARGET == null ? '' : `${CARB_TARGET}g`,
        pct: snap.knownC && CARB_TARGET ? (scoped === 'aaj' ? snap.todayC : avgC) / CARB_TARGET : 0,
        color: color.dietSoft,
      },
    ],
  };
}

export function usePersonaOS() {
  const [state, setState] = useState<State>(initialState);

  // Async callbacks (the mic timer) need the state as of when they fire, not
  // as of when they were scheduled.
  const beat = useRef<ReturnType<typeof setTimeout> | null>(null);
  const stateRef = useRef(state);
  stateRef.current = state;

  // `ask` is built far below — the chips above it only need it when tapped, so
  // they reach it through a ref rather than dragging its whole dependency
  // chain up here.
  const askRef = useRef<(raw: string) => void>(() => undefined);

  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);

  const patch = useCallback((p: Partial<State> | ((s: State) => Partial<State>)) => {
    setState((s) => ({ ...s, ...(typeof p === 'function' ? p(s) : p) }));
  }, []);

  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  /**
   * A receipt, not a message: it shows above the composer for a few seconds
   * and goes. The thread is for things that were said; the ledger keeps the
   * fact, and the tapped card reads its `✓ Logged` from the ledger.
   */
  const notify = useCallback(
    // `failed` draws a ✕ instead of the tick: a refusal must not look like a receipt.
    (text: string, sub?: string, failed = false) => {
      if (toastTimer.current) clearTimeout(toastTimer.current);
      patch({ toast: { id: Date.now(), text, sub, failed } });
      toastTimer.current = setTimeout(() => patch({ toast: null }), 3200);
    },
    [patch],
  );
  const dismissToast = useCallback(() => {
    if (toastTimer.current) clearTimeout(toastTimer.current);
    patch({ toast: null });
  }, [patch]);

  const push = useCallback(
    (msgs: ChatMsg | ChatMsg[], extra?: Partial<State>) => {
      patch((s) => ({ ...extra, chat: [...s.chat, ...(Array.isArray(msgs) ? msgs : [msgs])] }));
    },
    [patch],
  );

  // ── screens ─────────────────────────────────────────────────
  //
  // Every change of screen is a context switch: the deck comes back, and an
  // edit or a context hung on the composer goes with the screen whose
  // composer showed it — so Back can never spend a press clearing a pill
  // nobody can see. A sheet opening or closing over a screen is not a change
  // of screen: it covers the composer, whose edit is still there when it
  // closes (as on the phone, where the sheet is a window). Nor is a tab
  // changed in place.
  /** An ask sent from a page: once the stack is down, Home opens on the thread, the cursor in the composer. */
  const landInChat = useRef(false);
  const setStack = useCallback(
    (next: Screen[]) => {
      const toChat = next.length === 0 && landInChat.current;
      if (next.length === 0) landInChat.current = false;
      patch((s) => {
        if (next.length === s.stack.length && next.every((x, i) => x === s.stack[i])) return {};
        const places = (st: Screen[]) => st.filter((x) => x.kind !== 'sheet');
        const was = places(s.stack);
        const now = places(next);
        if (was.length === now.length && was.every((x, i) => sameEntry(x, now[i]))) return { stack: next };
        return {
          stack: next,
          composing: toChat,
          editing: null,
          context: null,
          typed: s.editing ? '' : s.typed,
        };
      });
    },
    [patch],
  );
  const screens = useNav(state.stack, setStack);
  const { push: openScreen, pop: popScreen, replace: replaceScreen } = screens;

  /**
   * The agent takes a beat before answering: think, then show the lock, then
   * speak. Today the delay is theatre over a synchronous stub — but the shape
   * is the real one, so wiring `/chat` in later is a swap rather than a
   * rewrite, and the mascot already narrates it.
   */
  const respond = useCallback(
    (run: () => void, extra?: Partial<State>) => {
      patch({ ...extra, phase: 'thinking' });
      if (beat.current) clearTimeout(beat.current);
      beat.current = setTimeout(() => {
        patch({ phase: 'saving' });
        beat.current = setTimeout(() => {
          run();
          patch({ phase: 'idle' });
        }, SAVING_MS);
      }, THINKING_MS);
    },
    [patch],
  );

  // The limit is the server's number — the same one the agent reads — and it
  // is refetched whenever the rows it is built from change, so logging a chai
  // still tightens it; one round-trip later rather than in the same render.
  const limit = state.limitInfo?.limit ?? null;
  const loadLimit = useCallback(async () => {
    try {
      patch({ limitInfo: await fetchLimit(isoDay(DATA_YEAR, DATA_MONTH, TODAY)) });
    } catch {
      /* quiet: the card shows — and the deck does not depend on it */
    }
  }, [patch]);
  // The commitments are the other half of the same sum: what is owed moves the
  // limit, so they are read whenever the limit is, and the page never shows a
  // number the card disagrees with.
  const loadCommitments = useCallback(async () => {
    try {
      patch({ commitments: await fetchCommitments() });
    } catch {
      /* quiet: the page says it did not load; the deck does not depend on it */
    }
  }, [patch]);
  // Boot patches tx, committedTx, borrowed, pending and profile one after another,
  // and each would refetch — five identical calls in 160ms. One per burst.
  useEffect(() => {
    const t = setTimeout(() => {
      void loadLimit();
      void loadCommitments();
    }, 150);
    return () => clearTimeout(t);
  }, [loadLimit, loadCommitments, state.tx, state.committedTx, state.borrowed, state.pending, state.profile]);

  // ── logging ────────────────────────────────────────────────
  //
  // Optimistic, but never silently: the row lands on the card at once, marked
  // pending, and the POST runs behind it. If the server refuses or never
  // answers, the row STAYS and turns 'unsaved' — someone said they spent ₹340,
  // and losing it to a blinked network is the app dropping data it was handed.
  // (spec/in-progress/ledger-writes.md)
  const localDay = isoDay(DATA_YEAR, DATA_MONTH, TODAY);

  const settle = useCallback(
    (kind: 'tx' | 'meals', id: string, failed: boolean) =>
      patch(
        (s) =>
          ({
            [kind]: (s[kind] as { id: string }[]).map((r) =>
              r.id === id ? { ...r, pending: false, failed } : r,
            ),
          }) as Partial<State>,
      ),
    [patch],
  );

  const logPaisa = useCallback(
    (name: string, cat: string, amt: number, said?: string) => {
      const s = stateRef.current;
      const confirm = paisaConfirm(s, limit, name, cat, amt);
      const row: Tx = { id: ulid(), day: TODAY, date: TODAY_ISO, name, cat, amt, pending: true };
      const said_ = said ? [userMsg(said)] : [];
      patch((cur) => ({
        tx: [...cur.tx, row],
        chat: [...cur.chat, ...said_, confirm],
      }));
      createTransaction(row, localDay).then(
        (saved) => {
          if (saved.commitment_id) {
            // The server counted it toward a commitment — a guess from the
            // category, marked as one. It was never spending: move it, and
            // say so where the row shows.
            patch((cur) => ({
              tx: cur.tx.filter((t) => t.id !== row.id),
              committedTx: [...cur.committedTx, {
                ...row, pending: false,
                commitmentId: saved.commitment_id, commitmentInferred: saved.commitment_inferred,
              }],
            }));
          } else settle('tx', row.id, false);
        },
        () => settle('tx', row.id, true),
      );
    },
    [limit, patch, localDay, settle],
  );

  const logDiet = useCallback(
    (name: string, p: number, k: number, said?: string) => {
      const s = stateRef.current;
      const confirm = dietConfirm(s, name, p, k);
      // Carbs and fat are not known when logging by hand — left undefined, not
      // zeroed. The agent fills them in when it parses a meal properly.
      const row: Meal = { id: ulid(), day: DIET_TODAY, date: DIET_TODAY_ISO, name, p, k, pending: true };
      const said_ = said ? [userMsg(said)] : [];
      patch((cur) => ({
        meals: [...cur.meals, row],
        chat: [...cur.chat, ...said_, confirm],
      }));
      createMeal(row, localDay).then(
        () => settle('meals', row.id, false),
        () => settle('meals', row.id, true),
      );
    },
    [patch, localDay, settle],
  );

  // ── derived ────────────────────────────────────────────────
  const view = useMemo(() => {
    const s = state;
    const snap = rollUp(s);
    const habitDays = s.habitLogs.map((l) => ({ date: l.date, habit: l.habit, amount: l.amount }));
    const heroes = MODES.map((m) => heroFor(m.id, s.range, snap, limit, s.limitInfo?.pool ?? 0, s.todos, habitDays));
    const index = modeIndex(s.mode);
    const hero = heroes[index];

    // Your own repeats, on the card you are on — spends on Paisa, meals on
    // Diet, none on Work. Worked out from the rows now, never stored.
    const picks =
      !hero.live || s.mode === 'work'
        ? []
        : (s.mode === 'paisa' ? spendChips(s.tx, TODAY_ISO) : mealChips(s.meals, DIET_TODAY_ISO))
            .filter((c) => !s.usedSuggs.includes(c.id));
    // The thread opens on nothing you did not ask for. A time-of-day greeting
    // came back after every clear and only restated the deck above it ("limit
    // ₹0"), so it read as a dummy message. The agent speaks first only when it
    // has something you do not know yet: that a card is not set up, and —
    // below — what salary day has locked. Who Spica is, the first run said.
    const greetBody = !hero.live
      ? 'Work is not set up yet. Swipe to Paisa or Diet — everything works there.'
      : '';

    // The day salary lands, say what is already spoken for — once. The
    // assumption is read before it shapes a single limit. Remembered on the
    // device: a viewing convenience, not a fact about the person.
    const monthKey = isoDay(DATA_YEAR, DATA_MONTH, 1).slice(0, 7);
    const lockedList = [
      // What is still owed on this month's own commitments, from the live
      // lines — a skipped one and a paid one owe nothing.
      ...(s.commitments?.items ?? [])
        .filter((c) => c.source === 'commitment' && !c.skipped && c.owedPaise > 0)
        .map((c) => ({ cat: c.name, amt: Math.round(c.owedPaise / 100) })),
      ...s.borrowed
        .filter((b) => b.date.slice(0, 7) < monthKey)
        .map((b) => ({ cat: `owed to ${b.label.replace(/\s+se liya$/i, '')}`, amt: b.remaining })),
    ];
    const salaryLine =
      SALARY_TODAY && lockedList.length && s.mode !== 'work' && !greetedToday()
        ? `Salary landed. Commitments — ${lockedList
            .map((r) => `${r.cat} ${rupees(r.amt)}`)
            .join(', ')} — ${rupees(lockedList.reduce((a, r) => a + r.amt, 0))} locked. `
        : '';

    return {
      heroes,
      hero,
      index,
      // Work takes typing too: a task said is a task added
      // (spec/done/projects.md). The chips below stay money and food.
      canLog: hero.live,
      /** What the composer invites on this card. */
      composerHint: s.mode === 'work' ? 'Add a task, or ask about work' : undefined,
      moreOpen: hero.hasMacros && s.moreOpen,
      greetBody: (salaryLine + greetBody).trim(),
      salaryLineShown: salaryLine !== '',
      /** The greeting's chips from your own ledger, already filtered for use. */
      picks,
      /** The deck's anchor day, ISO — what "today" means for every view. */
      anchorDay: isoDay(DATA_YEAR, DATA_MONTH, TODAY),
    };
  }, [state, limit]);

  // Mark the salary line as shown for today, so tomorrow's greeting is the plain one.
  useEffect(() => {
    if (view.salaryLineShown) markGreeted();
  }, [view.salaryLineShown]);

  // ── suggestion chips ───────────────────────────────────────
  const suggestions = useMemo<(Suggestion & { tap: () => void })[]>(() => {
    if (!view.canLog || state.mode === 'work') return [];
    // The chips are yours — your most repeated spends or meals — or there are
    // none. A tap sends the sentence to the agent, as every chip does.
    return view.picks.map((c) => ({
      id: c.id,
      name: c.name,
      tag: c.tag,
      tap: () => {
        patch((s) => ({ usedSuggs: [...s.usedSuggs, c.id] }));
        askRef.current(c.send);
      },
    }));
  }, [state.usedSuggs, state.mode, view.canLog, view.picks, patch]);

  // ── actions ────────────────────────────────────────────────
  const setModeByIndex = useCallback(
    (i: number) => {
      const next = MODES[Math.min(MODES.length - 1, Math.max(0, i))];
      patch({ mode: next.id, listening: false });
    },
    [patch],
  );

  /**
   * The Kaam card's "Sab kaam" — the To-do list, narrowed to work.
   */
  // ── the person ──────────────────────────────────────────────
  //
  // Edited in place on the Profile page: a row opens into a small editor and
  // Enter saves. No composer hop — the composer is for talking to the agent,
  // and a quick edit is not a conversation. Every save is optimistic; a
  // refusal puts the old value back and the editor says so.
  const loadProfileRows = useCallback(
    () =>
      Promise.all([listMemories(), listWeighIns()]).then(
        ([memories, weighIns]) => patch({ memories, weighIns }),
        () => push(stubMsg('Profile —', 'Memory and weigh-ins did not load. Is the server up?')),
      ),
    [patch, push],
  );
  /**
   * The grid, or — with a field — that field's group alone, its row open in
   * edit mode. A deep link pushes only the level it opens, so Back from Edit
   * goal returns to where it was tapped, not to a grid never seen.
   */
  const openProfile = useCallback(
    (focus: FieldId | null = null) => {
      openScreen({ kind: 'profile', group: focus ? GROUP_OF[focus] : null, focus });
      void loadProfileRows();
    },
    [openScreen, loadProfileRows],
  );
  /** A tile on the Profile grid: its group, as a page over the grid. */
  const openProfileGroup = useCallback(
    (group: GroupKey) => openScreen({ kind: 'profile', group, focus: null }),
    [openScreen],
  );
  /** Paisa ⋮ → Edit goal: the Profile page, opened on that row. */
  const editGoal = useCallback(() => openProfile('goal'), [openProfile]);
  /** Diet ⋮ → Edit targets: the Profile page, opened on the Health group. */
  const editTargets = useCallback(() => openProfile('kcal'), [openProfile]);

  const openCommitmentSheet = useCallback(
    (sheet: CommitmentSheet) => {
      patch({ openRow: null });
      openScreen({ kind: 'sheet', id: ulid(), sheet });
    },
    [patch, openScreen],
  );

  /**
   * One field. True when the server took it; false when it refused or nothing
   * usable was typed. An empty save clears the field — every one but the name
   * and the timezone (spec/done/onboarding-goals.md § Profile).
   */
  const saveField = useCallback(
    async (id: FieldId, raw: string): Promise<boolean> => {
      const edit = raw.trim() ? parseProfileEdit(id, `${id} ${raw}`) : clearEdit(id);
      if (!edit) return false;
      const before = stateRef.current.profile;
      const next = { ...before, ...edit.profile };
      setProfile(next);
      patch({ profile: next });
      try {
        const saved = await patchUser(edit.body);
        setProfile(saved);
        patch({ profile: saved });
        return true;
      } catch {
        setProfile(before);
        patch({ profile: before });
        return false;
      }
    },
    [patch],
  );
  const saveWeighIn = useCallback(
    async (raw: string): Promise<boolean> => {
      const kg = parseKg(raw);
      if (kg == null) return false;
      const row: WeighInRow = { id: ulid(), day: isoDay(DATA_YEAR, DATA_MONTH, TODAY), kg, estimated: false, pending: true };
      patch((cur) => ({ weighIns: [row, ...cur.weighIns.filter((w) => w.day !== row.day)] }));
      try {
        const saved = await createWeighIn(row.id, row.day, kg);
        patch((cur) => ({ weighIns: cur.weighIns.map((w) => (w.id === row.id ? saved : w)) }));
        // A reading the same day replaces that day's row, id and all: a chat
        // card holding it reads the new weight, and loses the dot.
        void rereadWeighIns();
        return true;
      } catch {
        patch((cur) => ({
          weighIns: cur.weighIns.map((w) => (w.id === row.id ? { ...w, pending: false, failed: true } : w)),
        }));
        return false;
      }
    },
    [patch],
  );
  /**
   * A reading deleted — on Profile, or by Undo on its card in the chat: the
   * next one back is the latest, and every card that showed it is struck now,
   * not one read later. The server takes that day's copy with it.
   */
  const removeWeighIn = useCallback(
    (id: string) => {
      const before = stateRef.current.weighIns;
      patch((cur) => ({ weighIns: cur.weighIns.filter((w) => w.id !== id), deletedRows: withId(cur.deletedRows, id) }));
      deleteWeighIn(id).then(
        () => void rereadWeighIns(),
        () => {
          patch((cur) => ({ weighIns: before, deletedRows: cur.deletedRows.filter((x) => x !== id) }));
          notify("Couldn't delete — the server refused.", undefined, true);
        },
      );
    },
    [patch, notify],
  );
  const saveMemory = useCallback(
    async (id: string, text: string): Promise<boolean> => {
      const before = stateRef.current.memories.find((m) => m.id === id);
      const clean = text.trim();
      if (!before || !clean) return false;
      patch((cur) => ({
        memories: cur.memories.map((m) => (m.id === id ? { ...m, text: clean, pending: true } : m)),
      }));
      try {
        const saved = await patchMemory(id, { text: clean });
        patch((cur) => ({ memories: cur.memories.map((m) => (m.id === id ? saved : m)) }));
        return true;
      } catch {
        patch((cur) => ({
          memories: cur.memories.map((m) => (m.id === id ? { ...before, failed: true } : m)),
        }));
        return false;
      }
    },
    [patch],
  );
  const addMemoryRow = useCallback(
    async (input: { slug: string; kind: string; text: string }): Promise<boolean> => {
      const slug = input.slug.trim().toLowerCase();
      const text = input.text.trim();
      if (!/^[a-z0-9][a-z0-9-]*$/.test(slug) || !text) return false;
      const row: MemoryRow = {
        id: ulid(),
        slug,
        kind: input.kind,
        text,
        source: 'user',
        confirmedAt: new Date().toISOString(),
        pending: true,
      };
      // Same slug → the server updates that row and returns its id.
      patch((cur) => ({ memories: [row, ...cur.memories.filter((m) => m.slug !== slug)] }));
      try {
        const saved = await createMemory({ id: row.id, slug, kind: input.kind, text });
        patch((cur) => ({ memories: cur.memories.map((m) => (m.id === row.id ? saved : m)) }));
        return true;
      } catch {
        patch((cur) => ({
          memories: cur.memories.map((m) => (m.id === row.id ? { ...m, pending: false, failed: true } : m)),
        }));
        return false;
      }
    },
    [patch],
  );
  const removeMemory = useCallback(
    (id: string) => {
      const before = stateRef.current.memories;
      patch({ memories: before.filter((m) => m.id !== id) });
      deleteMemory(id).catch(() => {
        patch({ memories: before });
        push(stubMsg('Not deleted —', 'Server refused. The memory is back.'));
      });
    },
    [patch, push],
  );

  // ── pantry ─────────────────────────────────────────────────
  //
  // Stock is never stored: every action writes a move (or a row) and the list
  // is refetched, so the number on screen is always the ledger's own sum.
  // spec/in-progress/pantry-view.md.
  const today = () => isoDay(DATA_YEAR, DATA_MONTH, TODAY);

  const loadSchedules = useCallback(
    async () => patch({ schedules: await fetchSchedules() }),
    [patch],
  );

  /**
   * Move a scheduled job, or turn it off. Optimistic, and reverted on refusal
   * — the row is the only place the time lives, so a silent failure would
   * leave the screen saying one thing and the dispatcher doing another.
   */
  const editSchedule = useCallback(
    async (id: string, p: { at?: string; enabled?: boolean }) => {
      const before = stateRef.current.schedules;
      patch({
        schedules: before.map((x) => (x.id === id ? { ...x, ...p, pending: true } : x)),
      });
      try {
        const saved = await patchSchedule(id, {
          ...(p.at !== undefined ? { at_local_time: p.at } : {}),
          ...(p.enabled !== undefined ? { enabled: p.enabled } : {}),
        });
        patch((cur) => ({ schedules: cur.schedules.map((x) => (x.id === id ? saved : x)) }));
        return true;
      } catch {
        patch({ schedules: before });
        notify("Couldn't save — the server refused.", undefined, true);
        return false;
      }
    },
    [patch, notify],
  );

  const loadHabits = useCallback(
    async () => patch({ habits: await fetchHabits() }),
    [patch],
  );

  /**
   * Start tracking something. Optimistic like every other library write in the
   * app: the row appears, and comes back marked if the server refuses — a
   * duplicate name is a 409, and that is the common refusal.
   */
  const addHabit = useCallback(
    async (row: { name: string; direction: 'build' | 'break'; unit: string | null }) => {
      try {
        const made = await createHabit(row);
        patch((cur) => ({ habits: [...cur.habits, made].sort((a, b) => a.name.localeCompare(b.name)) }));
        return true;
      } catch {
        notify(`Couldn't add ${row.name} — that name is probably already tracked.`, undefined, true);
        return false;
      }
    },
    [patch, notify],
  );

  const editHabit = useCallback(
    async (id: string, p: { name?: string; direction?: 'build' | 'break'; unit?: string | null }) => {
      const before = stateRef.current.habits;
      patch({ habits: before.map((h) => (h.id === id ? { ...h, ...p, pending: true } : h)) });
      try {
        const saved = await patchHabit(id, p);
        patch((cur) => ({ habits: cur.habits.map((h) => (h.id === id ? saved : h)) }));
        return true;
      } catch {
        patch({ habits: before });
        notify("Couldn't save — the server refused.", undefined, true);
        return false;
      }
    },
    [patch, notify],
  );

  /** Stop tracking it. The ticks stay: that you went in August is still true. */
  const removeHabit = useCallback(
    (id: string) => {
      const before = stateRef.current.habits;
      patch({ habits: before.filter((h) => h.id !== id) });
      deleteHabit(id).catch(() => {
        patch({ habits: before });
        notify("Couldn't stop tracking — the server refused.", undefined, true);
      });
    },
    [patch, notify],
  );

  const loadDishes = useCallback(
    async () => patch({ dishes: await fetchDishes(true) }),
    [patch],
  );
  /** Star or unstar, optimistically — the row moves in the list at once. */
  const toggleSaveDish = useCallback(
    (id: string) => {
      const before = stateRef.current.dishes;
      const row = before.find((d) => d.id === id);
      if (!row) return;
      patch({ dishes: before.map((d) => (d.id === id ? { ...d, saved: !d.saved } : d)) });
      (row.saved ? unsaveDish(id) : saveDish(id)).then(
        () => loadDishes(),
        () => {
          patch({ dishes: before });
          push(stubMsg('Not saved —', 'The server refused. Nothing changed.'));
        },
      );
    },
    [patch, push, loadDishes],
  );

  const loadPeople = useCallback(
    async () => patch({ people: await fetchPeople() }),
    [patch],
  );
  /**
   * File a row: what it is, or what you call them. Not optimistic — the server
   * sends the whole row back including the four derived numbers, and guessing
   * those on the client is how a screen starts disagreeing with the ledger.
   */
  const filePerson = useCallback(
    async (id: string, body: PersonEdits) => {
      try {
        const row = await patchCounterparty(id, body);
        patch({ people: stateRef.current.people.map((p) => (p.id === id ? row : p)) });
        return true;
      } catch {
        push(stubMsg('Not saved —', 'The server refused. Nothing changed.'));
        return false;
      }
    },
    [patch, push],
  );
  /**
   * Someone the ledger has never seen. A duplicate name is the server's 409 —
   * raw_name is the match key, so two rows for one name would leave the next
   * notification unable to say which it belongs to.
   */
  const addPerson = useCallback(
    async (name: string, body: PersonEdits) => {
      try {
        const row = await createCounterparty({ id: ulid(), raw_name: name, ...body });
        patch({ people: [...stateRef.current.people, row] });
        return true;
      } catch {
        push(stubMsg('Not added —', 'Either that name is already here, or the server refused.'));
        return false;
      }
    },
    [patch, push],
  );

  const loadExercises = useCallback(
    async () => patch({ exercises: await fetchExercises() }),
    [patch],
  );

  /**
   * One more time. The server increments and stamps the day in one write, and
   * sends the row back — the client never reads a counter and writes it back.
   */
  const didExerciseOnce = useCallback(
    (id: string) => {
      const before = stateRef.current.exercises;
      didExercise(id, isoDay(DATA_YEAR, DATA_MONTH, TODAY)).then(
        (row) => patch({ exercises: before.map((e) => (e.id === id ? row : e)) }),
        () => push(stubMsg('Not counted —', 'The server refused. Nothing changed.')),
      );
    },
    [patch, push],
  );

  /** Add one — typed here, or kept from something the agent found. */
  const addExercise = useCallback(
    async (row: { name: string; kind: string | null; muscle_group: string | null;
                  equipment: string | null; typical_minutes: number | null;
                  steps: string | null; source_url: string | null }) => {
      try {
        const made = await createExercise({ id: ulid(), source: 'manual', ...row });
        patch({ exercises: [...stateRef.current.exercises, made] });
        return true;
      } catch {
        push(stubMsg('Not added —', 'The server refused. Nothing changed.'));
        return false;
      }
    },
    [patch, push],
  );

  /** The thread, on boot. The user scrolls all of it; the model is given the
   *  last twenty turns and a summary. */
  /** One wire turn becomes one or more rendered messages. */
  const toMessages = useCallback((turns: WireTurn[]): ChatMsg[] => {
    const msgs: ChatMsg[] = [];
    for (const t2 of turns) {
      if (t2.role === 'user') {
        msgs.push({ kind: 'user', id: t2.id, text: t2.text });
        continue;
      }
      const cards = (t2.cards ?? [])
        .map((c, i) => toChatMsg(c, i, t2.id))
        .filter((m): m is ChatMsg => m !== null);
      msgs.push(...(cards.length ? cards : [stubMsg('', t2.text) as ChatMsg]));
    }
    return msgs;
  }, []);

  /**
   * The newest page. The thread is permanent and was already 172 messages
   * after two weeks, so it is never all fetched at once — older pages arrive
   * as the user scrolls back. spec/done/chat-history.md.
   */
  const loadChat = useCallback(async () => {
    const page = await fetchChat({ limit: CHAT_PAGE });
    patch({
      chat: toMessages(page.turns),
      chatOlder: page.turns.length ? page.turns[0].seq : null,
      chatHasMore: page.hasMore,
      chatCleared: page.clearedThrough,
    });
  }, [patch, toMessages]);

  /**
   * The page before what is on screen, prepended. `includeCleared` is the
   * *Show older* path: the user asking for what they hid.
   */
  const loadOlderChat = useCallback(
    async (includeCleared = false) => {
      const s0 = stateRef.current;
      if (s0.chatLoadingOlder || s0.chatOlder == null) return;
      if (!s0.chatHasMore && !includeCleared) return;
      patch({ chatLoadingOlder: true });
      try {
        const page = await fetchChat({
          limit: CHAT_PAGE, before: s0.chatOlder, includeCleared,
        });
        patch((cur) => ({
          chat: [...toMessages(page.turns), ...cur.chat],
          chatOlder: page.turns.length ? page.turns[0].seq : cur.chatOlder,
          chatHasMore: page.hasMore,
          // Revealed once, revealed for the session: the top row stops
          // offering *Show older* and goes back to plain paging.
          chatCleared: includeCleared ? 0 : cur.chatCleared,
          chatLoadingOlder: false,
        }));
      } catch {
        patch({ chatLoadingOlder: false });
      }
    },
    [patch, toMessages],
  );


  const loadPlaces = useCallback(
    async () => patch({ places: await fetchPlaces() }),
    [patch],
  );

  /**
   * A pin. Not optimistic: the server returns the row with its payment count
   * already summed, and guessing that on the client is how a screen starts
   * disagreeing with the ledger.
   */
  const addPlace = useCallback(
    async (row: { name: string; lat: number; lng: number; kind: string | null;
                  address: string | null; source: string }) => {
      try {
        const made = await createPlace({ id: ulid(), ...row });
        patch({ places: [...stateRef.current.places, made] });
        return true;
      } catch {
        push(stubMsg('Not added —', 'The server refused. Nothing changed.'));
        return false;
      }
    },
    [patch, push],
  );

  const editPlace = useCallback(
    async (id: string, body: Parameters<typeof patchPlace>[1]) => {
      try {
        const row = await patchPlace(id, body);
        patch({ places: stateRef.current.places.map((p) => (p.id === id ? row : p)) });
        return true;
      } catch {
        push(stubMsg('Not saved —', 'The server refused. Nothing changed.'));
        return false;
      }
    },
    [patch, push],
  );

  const removePlace = useCallback(
    (id: string) => {
      const before = stateRef.current.places;
      patch({ places: before.filter((p) => p.id !== id) });
      deletePlace(id).catch(() => {
        patch({ places: before });
        push(stubMsg('Not removed —', 'The server refused. Nothing changed.'));
      });
    },
    [patch, push],
  );

  const loadPantry = useCallback(
    async (foodId?: string) => {
      const [rows, moves] = await Promise.all([fetchPantry(today()), fetchPantryMoves(foodId)]);
      patch({ pantry: rows, pantryMoves: moves });
    },
    [patch],
  );
  // The pantry and recipes cards read these from state, so they load once at
  // boot rather than only when Your data opens. Quiet on failure: Your data
  // retries with its own message, and the deck does not depend on them.
  useEffect(() => {
    void Promise.all([
      loadPantry(),
      loadDishes(),
      loadHabits(),
      loadSchedules(),
      loadPeople(),
      loadExercises(),
      loadPlaces(),
      loadChat(),
    ]).catch(() => undefined);
  }, [loadPantry, loadDishes, loadPeople, loadExercises, loadPlaces, loadChat]);

  // A screen restored by a reload: the rows its opener would have read. Your
  // data's are the ones read at boot just above; Profile's are its own.
  useEffect(() => {
    if (stateRef.current.stack.some((sc) => sc.kind === 'profile')) void loadProfileRows();
  }, [loadProfileRows]);

  const openData = useCallback(
    (section: Section | null = null) => {
      openScreen({ kind: 'data', section });
      Promise.all([
        loadPantry(),
        loadDishes(),
        loadPeople(),
        loadExercises(),
        loadPlaces(),
        loadCommitments(),
      ]).catch(() => push(stubMsg('Your data —', 'It did not load. Is the server up?')));
    },
    [openScreen, push, loadPantry, loadDishes, loadPeople, loadExercises, loadPlaces, loadCommitments],
  );

  /** Bought (a purchase) or Have (a stock-take). False when the amount is unusable. */
  const addPantryMove = useCallback(
    async (foodId: string, grams: number, kind: 'purchase' | 'opening'): Promise<boolean> => {
      if (!Number.isFinite(grams) || grams <= 0) return false;
      try {
        await createPantryMove(ulid(), foodId, grams, kind, today());
        await loadPantry();
        return true;
      } catch {
        return false;
      }
    },
    [loadPantry],
  );
  /** Undo a move the user wrote. Consumption is refused by the server. */
  const undoPantryMove = useCallback(
    (id: string) => {
      deletePantryMove(id).then(
        () => loadPantry(),
        () => push(stubMsg('Not undone —', 'The server refused. That move stands.')),
      );
    },
    [loadPantry, push],
  );
  /** Start tracking a food. Grams, if given, land as an opening stock-take. */
  const addPantryFood = useCallback(
    async (name: string, quantity?: number, staple = false, unit = 'g'): Promise<boolean> => {
      const clean = name.trim();
      if (!clean) return false;
      try {
        const row = (await trackFood(ulid(), clean, staple, unit)) as { food_id: string };
        if (quantity && quantity > 0) {
          await createPantryMove(ulid(), row.food_id, quantity, 'opening', today());
        }
        await loadPantry();
        return true;
      } catch {
        return false;
      }
    },
    [loadPantry],
  );
  const savePantrySettings = useCallback(
    async (id: string, reorder: number | null, shelfLife: number | null): Promise<boolean> => {
      try {
        await patchPantryItem(id, { reorder_at_g: reorder, shelf_life_days: shelfLife });
        await loadPantry();
        return true;
      } catch {
        return false;
      }
    },
    [loadPantry],
  );
  /** Move a row between Stock and Staple — the user's declaration, so it is a patch. */
  const setStaple = useCallback(
    async (id: string, staple: boolean): Promise<boolean> => {
      try {
        await patchPantryItem(id, { staple });
        await loadPantry();
        return true;
      } catch {
        return false;
      }
    },
    [loadPantry],
  );
  const stopTrackingFood = useCallback(
    (id: string) => {
      const before = stateRef.current.pantry;
      patch({ pantry: before.filter((p) => p.id !== id) });
      stopTracking(id).then(
        () => loadPantry(),
        () => {
          patch({ pantry: before });
          push(stubMsg('Not removed —', 'The server refused. It is still tracked.'));
        },
      );
    },
    [patch, push, loadPantry],
  );

  // ── udhaar ─────────────────────────────────────────────────
  //
  // Repaid, Gift, Undo — each a row write, each optimistic. The live bindings
  // and the state move together so the limit (which reads the pool) and the
  // report (which reads state) cannot disagree.
  const putUdhaar = useCallback(
    (u: { pending: PendingItem[]; borrowed: PendingItem[]; repayments: RepaymentItem[]; lentMonth: number; repaidMonth: number; borrowedMonth: number; paidBackMonth: number }) => {
      setUdhaar(u);
      patch(u);
    },
    [patch],
  );
  const udhaarNow = () => {
    const s = stateRef.current;
    return {
      pending: s.pending, borrowed: s.borrowed, repayments: s.repayments,
      lentMonth: s.lentMonth, repaidMonth: s.repaidMonth, borrowedMonth: s.borrowedMonth, paidBackMonth: s.paidBackMonth,
    };
  };
  const thisMonth = (iso: string) => iso.slice(0, 7) === isoDay(DATA_YEAR, DATA_MONTH, 1).slice(0, 7);

  /**
   * "Wapas aaya" on a lending, "wapas de diya" on a borrowing. One repayment
   * row either way: yours coming back enters the pool; theirs going back
   * leaves it (and stops being locked). False when refused.
   */
  const markRepaid = useCallback(
    async (openId: string, amount: number): Promise<boolean> => {
      const before = udhaarNow();
      const open = before.pending.find((p) => p.id === openId) ?? before.borrowed.find((p) => p.id === openId);
      if (!open || !(amount > 0) || amount > open.remaining) return false;
      const day = isoDay(DATA_YEAR, DATA_MONTH, TODAY);
      const row: RepaymentItem = {
        id: ulid(), lendingId: openId, leg: open.leg, label: open.label, amount, date: day, day: TODAY,
        lentDate: open.date, lentAmount: open.amount, pending: true,
      };
      const shrink = (list: PendingItem[]) =>
        list.map((p) => (p.id === openId ? { ...p, remaining: p.remaining - amount } : p)).filter((p) => p.remaining > 0);
      putUdhaar({
        pending: open.leg === 'lent' ? shrink(before.pending) : before.pending,
        borrowed: open.leg === 'borrowed' ? shrink(before.borrowed) : before.borrowed,
        repayments: [row, ...before.repayments],
        lentMonth: before.lentMonth,
        borrowedMonth: before.borrowedMonth,
        repaidMonth: open.leg === 'lent' ? before.repaidMonth + amount : before.repaidMonth,
        paidBackMonth: open.leg === 'borrowed' ? before.paidBackMonth + amount : before.paidBackMonth,
      });
      try {
        await createRepayment(row.id, open, amount, day);
        patch((cur) => ({ repayments: cur.repayments.map((r) => (r.id === row.id ? { ...r, pending: false } : r)) }));
        return true;
      } catch {
        putUdhaar(before);
        return false;
      }
    },
    [patch, putUdhaar],
  );
  /** A lending or a borrowing typed on the report. Yours out lowers the pool; theirs in raises it. */
  const addOpen = useCallback(
    async (leg: 'lent' | 'borrowed', who: string, amount: number): Promise<boolean> => {
      const name = who.trim();
      if (!name || !(amount > 0)) return false;
      const before = udhaarNow();
      const day = isoDay(DATA_YEAR, DATA_MONTH, TODAY);
      const row: PendingItem = {
        id: ulid(), leg, label: leg === 'lent' ? `${name} ko diya` : `${name} se liya`,
        amount, remaining: amount, date: day, day: TODAY, pending: true,
      };
      putUdhaar({
        ...before,
        pending: leg === 'lent' ? [...before.pending, row] : before.pending,
        borrowed: leg === 'borrowed' ? [...before.borrowed, row] : before.borrowed,
        lentMonth: leg === 'lent' ? before.lentMonth + amount : before.lentMonth,
        borrowedMonth: leg === 'borrowed' ? before.borrowedMonth + amount : before.borrowedMonth,
      });
      try {
        await createOpen(row.id, leg, name, amount, day);
        patch((cur) => ({
          pending: cur.pending.map((p) => (p.id === row.id ? { ...p, pending: false } : p)),
          borrowed: cur.borrowed.map((p) => (p.id === row.id ? { ...p, pending: false } : p)),
        }));
        return true;
      } catch {
        putUdhaar(before);
        return false;
      }
    },
    [patch, putUdhaar],
  );
  /** Stop expecting it back. The lending becomes spend; the pool already lost it when it was lent. */
  const gift = useCallback(
    (lendingId: string) => {
      const before = udhaarNow();
      const lending = before.pending.find((p) => p.id === lendingId);
      if (!lending) return;
      putUdhaar({
        ...before,
        pending: before.pending.filter((p) => p.id !== lendingId),
        // Lent → expense: the month's lent leg shrinks and its spend grows by the same amount.
        lentMonth: thisMonth(lending.date) ? before.lentMonth - lending.amount : before.lentMonth,
      });
      if (thisMonth(lending.date)) {
        patch((cur) => ({
          tx: [...cur.tx, { id: lending.id, day: lending.day, name: lending.label, cat: 'Logon ko diya', amt: lending.amount }],
        }));
      }
      giftLending(lendingId).then(
        () => undefined,
        () => {
          putUdhaar(before);
          patch((cur) => ({ tx: cur.tx.filter((t) => t.id !== lendingId) }));
          push(stubMsg('Not saved —', `${lending.label} is still pending; the server refused.`));
        },
      );
    },
    [patch, push, putUdhaar],
  );
  /** Undo a repayment: the row is soft-deleted and the lending or borrowing is open again. */
  const undoRepayment = useCallback(
    (repaymentId: string) => {
      const before = udhaarNow();
      const rep = before.repayments.find((r) => r.id === repaymentId);
      if (!rep) return;
      const listKey = rep.leg === 'lent' ? 'pending' : 'borrowed';
      const list = before[listKey];
      const open = list.find((p) => p.id === rep.lendingId);
      const restored = open
        ? list.map((p) => (p.id === rep.lendingId ? { ...p, remaining: p.remaining + rep.amount } : p))
        : [
            ...list,
            // Fully repaid before this undo: rebuild the row from its own leg, date and size.
            { id: rep.lendingId, leg: rep.leg, label: rep.label, amount: rep.lentAmount, remaining: rep.amount, date: rep.lentDate, day: Number(rep.lentDate.slice(8, 10)) },
          ].sort((x, y) => x.date.localeCompare(y.date));
      putUdhaar({
        ...before,
        [listKey]: restored,
        repayments: before.repayments.filter((r) => r.id !== repaymentId),
        repaidMonth: rep.leg === 'lent' && thisMonth(rep.date) ? before.repaidMonth - rep.amount : before.repaidMonth,
        paidBackMonth: rep.leg === 'borrowed' && thisMonth(rep.date) ? before.paidBackMonth - rep.amount : before.paidBackMonth,
      });
      // The repayment is a ledger row like any other: a card showing it strikes it.
      patch((cur) => ({ deletedRows: withId(cur.deletedRows, repaymentId) }));
      deleteTransaction(repaymentId).catch(() => {
        putUdhaar(before);
        patch((cur) => ({ deletedRows: cur.deletedRows.filter((x) => x !== repaymentId) }));
        push(stubMsg('Not undone —', 'Server refused. The repayment stands.'));
      });
    },
    [patch, push, putUdhaar],
  );

  // ── counts toward a commitment ──────────────────────────────
  //
  // A payment's link is the commitment_id on the row. Linking moves the row
  // between the spend list and the committed list — the arithmetic reads the
  // lists, so nothing else has to know — and the server answers with the new
  // owed and the new limit, which are read again behind it. Optimistic,
  // reverted if the server refuses.
  const linkPayment = useCallback(
    (id: string, commitmentId: string | null) => {
      const s0 = stateRef.current;
      const row = s0.tx.find((t) => t.id === id) ?? s0.committedTx.find((t) => t.id === id);
      const before = row ?? s0.fetchedTx.find((t) => t.id === id);
      if (!before) return;
      const apply = (cur: State, cid: string | null, inferred: boolean): Partial<State> => {
        const inDeck = cur.tx.find((t) => t.id === id) ?? cur.committedTx.find((t) => t.id === id);
        const stamp = (t: Tx): Tx => ({ ...t, commitmentId: cid, commitmentInferred: inferred });
        const fetched = cur.fetchedTx.map((t) => (t.id === id ? stamp(t) : t));
        if (!inDeck) return { fetchedTx: fetched, openRow: null };
        const next = stamp(inDeck);
        return cid
          ? { tx: cur.tx.filter((t) => t.id !== id), committedTx: upsert(cur.committedTx, next), fetchedTx: fetched, openRow: null }
          : { committedTx: cur.committedTx.filter((t) => t.id !== id), tx: upsert(cur.tx, next), fetchedTx: fetched, openRow: null };
      };
      patch((cur) => apply(cur, commitmentId, false));
      patchTransaction(id, { commitment_id: commitmentId }).then(
        () => void Promise.all([loadLimit(), loadCommitments()]),
        () => {
          patch((cur) => apply(cur, before.commitmentId ?? null, Boolean(before.commitmentInferred)));
          notify('Not changed — the server refused.', undefined, true);
        },
      );
    },
    [patch, notify, loadLimit, loadCommitments],
  );

  const showWorkTasks = useCallback(
    () => push([userMsg('show all tasks'), todoMsg('work')], {}),
    [push],
  );

  const tapMic = useCallback(() => {
    if (stateRef.current.mode === 'work') return;
    patch({ listening: true, composing: true });
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      const s = stateRef.current;
      const line = VOICE_SCRIPT[s.scriptIdx % VOICE_SCRIPT.length];
      patch({ listening: false, composing: false, scriptIdx: s.scriptIdx + 1 });
      push(userMsg(line.u));
      respond(() =>
        line.type === 'paisa'
          ? logPaisa(line.name, line.cat, line.amt)
          : logDiet(line.name, line.p, line.k),
      );
    }, LISTEN_MS);
  }, [patch, push, respond, logPaisa, logDiet]);

  const pickMedia = useCallback(() => {
    const mode = stateRef.current.mode;
    if (mode === 'work') return;
    const isPaisa = mode === 'paisa';
    push(
      {
        ...stubMsg(
          isPaisa ? 'Send the payment screenshot —' : 'Send a photo of the food —',
          isPaisa
            ? 'Amount, payee, time, app — all read from the screenshot.'
            : 'Portion and macros estimated from the photo — faster than typing.',
        ),
        hl: 'I will read it',
      },
      {},
    );
  }, [push]);

  /**
   * A menu row pushes its page over the menu, so Back returns to the menu as
   * it was. A row marked Soon does nothing — it is not a door yet.
   */
  const openMenuRow = useCallback(
    (name: string) => {
      // On the tab it was last left on, as the phone opens it.
      if (name === 'Reports') openScreen({ kind: 'report', mode: stateRef.current.reportMode });
      else if (name === 'Your data') openData();
      else if (name === 'Profile') openProfile();
    },
    [openScreen, openProfile, openData],
  );

  /**
   * Fix a row in place. Optimistic — the new values show at once — but never
   * silently: if the server refuses, the OLD values come back and the row
   * reads 'unsaved'. The screen must not claim a number the server rejected.
   */
  const applyEdit = useCallback(
    (target: NonNullable<State['editing']>, label: string, num: number) => {
      const s = stateRef.current;
      if (target.source === 'paisa' && !s.tx.some((t) => t.id === target.id) && !s.committedTx.some((t) => t.id === target.id)) {
        // A lending or borrowing, edited from its tab.
        const k: 'pending' | 'borrowed' = s.pending.some((p) => p.id === target.id) ? 'pending' : 'borrowed';
        const open = s[k].find((p) => p.id === target.id);
        if (!open) return;
        const amt = num > 0 ? num : open.amount;
        const next = { ...open, label, amount: amt, remaining: Math.max(0, open.remaining + (amt - open.amount)) };
        putUdhaar({ ...udhaarNow(), [k]: s[k].map((p) => (p.id === target.id ? next : p)) });
        push(stubMsg('Updated —', `${label} · ${rupees(amt)}`));
        patchTransaction(target.id, { description: label, amount_paise: Math.round(amt * 100) }).catch(() =>
          putUdhaar({ ...udhaarNow(), [k]: stateRef.current[k].map((p) => (p.id === target.id ? open : p)) }),
        );
      } else if (target.source === 'paisa') {
        const list: 'tx' | 'committedTx' = s.tx.some((t) => t.id === target.id) ? 'tx' : 'committedTx';
        const before = s[list].find((t) => t.id === target.id);
        if (!before) return;
        const amt = num > 0 ? num : before.amt;
        patch((cur) => ({
          [list]: cur[list].map((t) => (t.id === target.id ? { ...t, name: label, amt, pending: true } : t)),
        }));
        push(stubMsg('Updated —', `${label} · ${rupees(amt)}`));
        patchTransaction(target.id, { description: label, amount_paise: Math.round(amt * 100) }).then(
          () => patch((cur) => ({ [list]: cur[list].map((t) => (t.id === target.id ? { ...t, pending: false } : t)) })),
          () => patch((cur) => ({
            [list]: cur[list].map((t) => (t.id === target.id ? { ...before, failed: true } : t)),
          })),
        );
      } else {
        const before = s.meals.find((m) => m.id === target.id);
        if (!before) return;
        const k = num > 40 ? num : before.k;
        patch((cur) => ({
          meals: cur.meals.map((m) => (m.id === target.id ? { ...m, name: label, k, pending: true } : m)),
        }));
        push(stubMsg('Updated —', `${label} · ${k} kcal`));
        patchMeal(target.id, { dish: label, kcal: k }).then(
          () => settle('meals', target.id, false),
          () => patch((cur) => ({
            meals: cur.meals.map((m) => (m.id === target.id ? { ...before, failed: true } : m)),
          })),
        );
      }
    },
    [patch, push, settle, putUdhaar],
  );

  /** Send whatever is in the composer: a `@tool`, or free text the agent parses. */
  /**
   * Refetch the deck and re-seed the state that was seeded from it.
   *
   * The hook's rows come from `data/live`'s module values at first render, so
   * a server-side write is invisible until both are refreshed. Every other
   * write in the app is optimistic and patches state itself; the agent's are
   * not, because only the server knows what its tools actually did.
   */
  const reloadDeck = useCallback(async () => {
    await loadDeck();
    setUdhaar({ pending: PENDING, borrowed: BORROWED, repayments: REPAYMENTS,
                lentMonth: LENT_MONTH, repaidMonth: REPAID_MONTH,
                borrowedMonth: BORROWED_MONTH, paidBackMonth: PAID_BACK_MONTH });
    patch({ tx: seedTx, committedTx: seedCommittedTx, meals: seedMeals, todos: seedTodos,
            workouts: seedWorkouts, habitLogs: HABIT_LOGS, pending: PENDING,
            borrowed: BORROWED, repayments: REPAYMENTS, lentMonth: LENT_MONTH,
            repaidMonth: REPAID_MONTH, borrowedMonth: BORROWED_MONTH,
            paidBackMonth: PAID_BACK_MONTH });
    // A payment that moved was counted toward a line, or not: what is owed follows.
    void loadCommitments();
  }, [patch, loadCommitments]);

  /**
   * Ask the agent. One turn, no streaming — the reply lands whole. Said about
   * a row (a context), the bubble keeps what was typed and the agent hears
   * the context's words first: "Change the category of the ₹80 Auto payment
   * on 1 Oct to transport".
   */
  const ask = useCallback(
    async (raw: string, ctx?: ComposerContext | null) => {
      const said = userMsg(raw, ctx);
      push(said, { typed: '', phase: 'thinking' });
      try {
        const out = await sendChat(ctx ? `${ctx.prefix} ${raw}` : raw, isoDay(DATA_YEAR, DATA_MONTH, TODAY));
        const cards = out.cards
          .map((c, i) => toChatMsg(c, i, `chat-${Date.now()}`))
          .filter((m): m is ChatMsg => m !== null);
        // A weight written: the weight cards read the weigh-ins again before
        // this one is drawn — a same-day correction keeps its row's id, and a
        // copy from before would show the old weight under the new card.
        if (cards.some((m) => m.kind === 'confirm' && m.source === 'body' && m.fields.some((f) => f.key === 'weight_kg'))) {
          void rereadWeighIns();
        }
        // No pause here: the reply row's own face runs the close-and-spark
        // (`done`) as it mounts, so the beat is on the message, not before it.
        push(cards.length ? cards : stubMsg('', out.reply || 'Nothing came back.'));
        // A delete the agent made strikes its row on every card now, not one
        // fetch later — and an Undo on any of them can bring it back.
        const gone = cards.filter(
          (m): m is ConfirmMsg =>
            m.kind === 'confirm' && m.state === 'deleted' && m.rowId != null && (m.source === 'paisa' || m.source === 'diet'),
        );
        if (gone.length) {
          patch((cur) => {
            let next = cur;
            for (const m of gone) next = { ...next, ...struck(next, m.source as 'paisa' | 'diet', m.rowId!) };
            return next;
          });
        }
        // A turn may have written something; the deck and the limit follow.
        void Promise.all([reloadDeck(), loadLimit(), loadPantry(), loadExercises()])
          .catch(() => undefined);
      } catch {
        // It was yours that did not go, so your own bubble says so — "Not
        // sent · Retry" — rather than an agent bubble speaking for the server.
        patch((s) => ({
          chat: s.chat.map((m) => (m.id === said.id && m.kind === 'user' ? { ...m, failed: true } : m)),
        }));
      } finally {
        patch({ phase: 'idle' });
      }
    },
    [push, patch, reloadDeck, loadLimit, loadPantry, loadExercises],
  );
  askRef.current = (raw: string) => void ask(raw);

  /**
   * A card's Change. The row and its field hang on the composer as a pill and
   * the cursor goes to the text box — nothing is typed for the user, nothing
   * already typed is lost, and no page opens. The agent already understands
   * sentences: what is typed next goes after the context's words, so a bare
   * "transport" arrives as a correction of that one row.
   */
  const setContext = useCallback(
    (context: ComposerContext) =>
      patch((s) => ({
        context,
        // A row edit and a context both claim the next send; the newer wins.
        editing: null,
        composing: true,
        composeFocus: s.composeFocus + 1,
      })),
    [patch],
  );
  const clearContext = useCallback(() => patch({ context: null }), [patch]);

  /**
   * What a send did: nothing (an empty field), a correction to a row in place,
   * or a question for the agent. Only an ask leaves a page — its answer is in
   * the thread; a correction stays where the row is.
   */
  const send = useCallback((): 'none' | 'edit' | 'ask' => {
    const raw = stateRef.current.typed.trim();
    if (!raw) return 'none';
    // The context belongs to this one sentence: once sent, it comes off.
    const ctx = stateRef.current.context;
    if (ctx) patch({ context: null });

    const editing = stateRef.current.editing;
    if (editing) {
      // A correction, not a log: same row, new values, same id. Still local —
      // the row is already on screen and the edit is unambiguous.
      const match = raw.match(/(\d+)/);
      const num = match ? parseInt(match[1], 10) : 0;
      const bare = raw.replace(/\d+/g, '').trim()
        || (editing.source === 'paisa' ? 'Spend' : 'Meal');
      patch({ typed: '', editing: null });
      push(userMsg(`"${raw}"`));
      applyEdit(editing, bare.charAt(0).toUpperCase() + bare.slice(1), num);
      return 'edit';
    }

    // Everything else is the agent's. It parses the sentence, calls the tools
    // and answers in cards — the keyword-and-number guesswork that used to
    // live here guessed 12g of protein for every meal.
    void ask(raw, ctx);
    return 'ask';
  }, [push, patch, applyEdit, ask]);

  // ── commitments: make, change, skip, repeat, delete ─────────
  //
  // Not optimistic: what is owed and the limit are the server's arithmetic, so
  // each write waits for its answer and then reads both again. A payment the
  // new line counts moves with it, so the deck is read too.
  const afterCommitmentWrite = useCallback(
    () => Promise.all([reloadDeck(), loadLimit(), loadCommitments()]).then(() => undefined, () => undefined),
    [reloadDeck, loadLimit, loadCommitments],
  );
  const refused = useCallback(
    (e: unknown, what: string) => {
      const code = errorStatus(e);
      if (code !== 401) {
        notify(
          code === null ? `${what} — didn't reach the server.` : `${what} — the server refused.`,
          undefined,
          true,
        );
      }
    },
    [notify],
  );

  /**
   * The sheet's Save. False when it did not go, so the sheet stays open. On
   * success it closes `from` — that sheet, and only if it is still on top.
   */
  const saveCommitment = useCallback(
    async (draft: CommitmentDraft, editing: CommitmentRow | null, paymentId?: string, from?: Screen): Promise<boolean> => {
      try {
        if (editing) {
          const change: CommitmentChange = {};
          if (draft.name !== editing.name) change.name = draft.name;
          if (draft.category !== editing.category) change.category = draft.category;
          // Only a changed amount is sent: sending the same one would turn a
          // carried figure into a stated one without the person saying it.
          if (draft.amountPaise !== editing.expectedPaise) change.amountPaise = draft.amountPaise;
          if (draft.dueDay !== editing.dueDay) change.dueDay = draft.dueDay;
          if (draft.repeats !== editing.repeats) change.repeats = draft.repeats;
          if (Object.keys(change).length) await patchCommitment(editing.id, change);
        } else {
          await createCommitment(ulid(), draft, paymentId ? [paymentId] : []);
        }
        if (from) popScreen(from);
        await afterCommitmentWrite();
        return true;
      } catch (e) {
        refused(e, "Couldn't save it");
        return false;
      }
    },
    [popScreen, afterCommitmentWrite, refused],
  );

  const skipCommitment = useCallback(
    async (id: string, skipped: boolean) => {
      try {
        await patchCommitment(id, { skipped });
        patch({ openRow: null });
        await afterCommitmentWrite();
      } catch (e) {
        refused(e, skipped ? "Couldn't skip it" : "Couldn't unskip it");
      }
    },
    [patch, afterCommitmentWrite, refused],
  );

  const repeatCommitment = useCallback(
    async (id: string, repeats: boolean) => {
      try {
        await patchCommitment(id, { repeats });
        patch({ openRow: null });
        await afterCommitmentWrite();
      } catch (e) {
        refused(e, "Couldn't change it");
      }
    },
    [patch, afterCommitmentWrite, refused],
  );

  /** Its payments become ordinary spending and the repeat ends. There is no undo. */
  const removeCommitment = useCallback(
    async (id: string) => {
      try {
        await deleteCommitmentApi(id);
        patch({ openRow: null });
        await afterCommitmentWrite();
      } catch (e) {
        refused(e, "Couldn't delete it");
      }
    },
    [patch, afterCommitmentWrite, refused],
  );

  // ── row-level edits ────────────────────────────────────────
  const toggleRow = useCallback(
    (id: string) => patch((s) => ({ openRow: s.openRow === id ? null : id })),
    [patch],
  );

  const deleteRow = useCallback(
    (source: 'paisa' | 'diet', id: string) => {
      // Optimistic removal; if the server disagrees the row comes back, marked.
      const s = stateRef.current;
      const kept =
        source === 'paisa'
          ? (s.tx.find((x) => x.id === id) ?? s.committedTx.find((x) => x.id === id))
          : s.meals.find((x) => x.id === id);
      // The copy a card fetched by id, as it was — put back if the delete is refused.
      const fetchedTx = s.fetchedTx.find((x) => x.id === id);
      const fetchedMeal = s.fetchedMeals.find((x) => x.id === id);
      // A lending lives in `pending`, not `tx`; deleting one removes it there.
      const keptPending = source === 'paisa' ? (s.pending.find((p) => p.id === id) ?? s.borrowed.find((p) => p.id === id)) : undefined;
      // Struck on every card that shows it — a table, a receipt, here or in
      // the report — and out of every sum.
      patch((cur) => ({
        ...struck(cur, source, id),
        ...(source === 'paisa'
          ? { pending: cur.pending.filter((p) => p.id !== id), borrowed: cur.borrowed.filter((p) => p.id !== id) }
          : {}),
        openRow: null,
      }));
      if (keptPending) {
        const now = udhaarNow();
        const same = thisMonth(keptPending.date);
        const legs = {
          lentMonth: keptPending.leg === 'lent' && same ? now.lentMonth - keptPending.amount : now.lentMonth,
          borrowedMonth: keptPending.leg === 'borrowed' && same ? now.borrowedMonth - keptPending.amount : now.borrowedMonth,
        };
        setUdhaar({ ...now, ...legs, pending: s.pending.filter((p) => p.id !== id), borrowed: s.borrowed.filter((p) => p.id !== id) });
        patch(legs);
      }
      (source === 'paisa' ? deleteTransaction(id) : deleteMeal(id)).catch(() => {
        // Refused: the row is not gone, so nothing strikes it.
        patch((cur) =>
          source === 'paisa'
            ? {
                deletedRows: cur.deletedRows.filter((x) => x !== id),
                fetchedTx: fetchedTx ? upsert(cur.fetchedTx, fetchedTx) : cur.fetchedTx.filter((x) => x.id !== id),
              }
            : {
                deletedRows: cur.deletedRows.filter((x) => x !== id),
                fetchedMeals: fetchedMeal ? upsert(cur.fetchedMeals, fetchedMeal) : cur.fetchedMeals.filter((x) => x.id !== id),
              },
        );
        if (keptPending) {
          // The server refused — a lending with repayments cannot be deleted.
          const k = keptPending.leg === 'lent' ? 'pending' : 'borrowed';
          const now = udhaarNow();
          const same = thisMonth(keptPending.date);
          const legs = {
            lentMonth: keptPending.leg === 'lent' && same ? now.lentMonth + keptPending.amount : now.lentMonth,
            borrowedMonth: keptPending.leg === 'borrowed' && same ? now.borrowedMonth + keptPending.amount : now.borrowedMonth,
          };
          setUdhaar({ ...now, ...legs, [k]: [...stateRef.current[k], keptPending] });
          patch((cur) => ({ ...legs, [k]: [...cur[k], keptPending].sort((x, y) => x.date.localeCompare(y.date)) }));
          push(stubMsg('Not deleted —', `${keptPending.label} has repayments. Undo them first.`));
          return;
        }
        if (!kept) return;
        patch((cur) =>
          source === 'paisa'
            ? (kept as Tx).commitmentId
              ? { committedTx: [...cur.committedTx, { ...(kept as Tx), failed: true }] }
              : { tx: [...cur.tx, { ...(kept as Tx), failed: true }] }
            : { meals: [...cur.meals, { ...(kept as Meal), failed: true }] },
        );
      });
    },
    [patch, push],
  );

  /** "Edit" drops the row back into the composer so it can be re-said. */
  /** Optimistic soft-delete of a habit log; the row returns if the server refuses. */
  const deleteHabitLog = useCallback(
    (id: string) => {
      const kept = stateRef.current.habitLogs.find((l) => l.id === id);
      patch((s) => ({ habitLogs: s.habitLogs.filter((l) => l.id !== id) }));
      deleteHabitLogApi(id).catch(() => {
        if (kept) patch((s) => ({ habitLogs: [...s.habitLogs, kept] }));
      });
    },
    [patch],
  );

  /**
   * Same for a task — the plugin will call the same endpoint; one API, two
   * callers. A card that showed it stays, struck: `Removed`.
   */
  const deleteTask = useCallback(
    (id: string) => {
      const kept = stateRef.current.todos.find((t) => t.id === id);
      patch((s) => ({ todos: s.todos.filter((t) => t.id !== id), deletedRows: withId(s.deletedRows, id) }));
      deleteTaskApi(id).catch(() => {
        patch((s) => ({
          todos: kept ? [...s.todos, kept] : s.todos,
          deletedRows: s.deletedRows.filter((x) => x !== id),
        }));
        notify('Not removed — the server refused.', undefined, true);
      });
    },
    [patch, notify],
  );

  /** One ⋮ → Delete for every kind of row the report shows. */
  const deleteAny = useCallback(
    (kind: 'paisa' | 'diet' | 'habit' | 'task' | 'repayment', id: string) => {
      if (kind === 'habit') deleteHabitLog(id);
      else if (kind === 'task') deleteTask(id);
      else if (kind === 'repayment') undoRepayment(id);
      else deleteRow(kind, id);
    },
    [deleteHabitLog, deleteTask, deleteRow, undoRepayment],
  );

  /** ⋮ → Edit: the row's text goes into the composer AND the composer remembers the row. */
  const editRow = useCallback(
    (source: 'paisa' | 'diet', id: string, text: string) =>
      patch({ typed: text, openRow: null, composing: true, editing: { source, id, label: text }, context: null }),
    [patch],
  );
  const cancelEdit = useCallback(() => patch({ typed: '', editing: null }), [patch]);

  const toggleTodo = useCallback(
    (id: string) => {
      const before = stateRef.current.todos.find((t) => t.id === id);
      if (!before) return;
      const done = !before.done;
      patch((s) => ({
        todos: s.todos.map((t) =>
          t.id === id
            ? // Stamping the day is what lets a finished task stay on the card
              // with a completed status instead of vanishing under your finger.
              // A tracker's task reminds the moment it is ticked: the server
              // agrees on the next load, and un-ticking takes it back.
              {
                ...t,
                done,
                doneOn: done ? TODAY_ISO : undefined,
                awaitingMove: done && Boolean(t.tracked),
              }
            : t,
        ),
      }));
      // A task is state, not an event — the one in-place update. Revert if the
      // server never took it, so the card never lies about what is saved.
      patchTask(id, done).catch(() =>
        patch((s) => ({ todos: s.todos.map((t) => (t.id === id ? before : t)) })),
      );
    },
    [patch],
  );


  // ── chat cards ─────────────────────────────────────────────────────────
  // spec/done/chat-cards.md. Cards name rows by id; these keep them live.


  /**
   * Clear the screen without forgetting. The server folds everything above the
   * newest message into the summary and hides it — nothing is deleted, and the
   * thread is still one thread.
   */
  // A ref, not the state flag. Three presses in one tick all read the same
  // `stateRef` and all got through — React had not re-rendered yet, so
  // `disabled` was not on the button either, and three summariser calls ran.
  // A ref is set before the next line executes.
  const clearing = useRef(false);
  const clearConversation = useCallback(async () => {
    if (clearing.current) return;
    clearing.current = true;
    patch({ chatClearing: true });
    try {
      const page = await clearChat();
      patch({
        chat: toMessages(page.turns),
        chatOlder: page.turns.length ? page.turns[0].seq : null,
        chatHasMore: page.hasMore,
        chatCleared: page.clearedThrough,
      });
      notify('Conversation cleared', 'The agent kept the gist');
    } catch {
      notify("Couldn't clear — the server refused.", undefined, true);
    } finally {
      clearing.current = false;
      patch({ chatClearing: false });
    }
  }, [patch, toMessages, notify]);

  const requestedRows = useRef<Set<string>>(new Set());
  /**
   * Rows a card named that the deck's window does not hold — fetched by id,
   * deleted ones included, so the card can strike them rather than lose them.
   * Asked for once per id: a row the server does not return would otherwise
   * be asked for on every render.
   */
  const ensureRows = useCallback(
    (source: 'paisa' | 'diet', ids: string[]) => {
      const fresh = ids.filter((id) => !requestedRows.current.has(`${source}:${id}`));
      if (!fresh.length) return;
      fresh.forEach((id) => requestedRows.current.add(`${source}:${id}`));
      const merge = <T extends { id: string }>(have: T[], got: T[]) =>
        [...have.filter((h) => !got.some((g) => g.id === h.id)), ...got];
      if (source === 'paisa') {
        fetchRowsByIds('paisa', fresh)
          .then((rows) => patch((cur) => ({ fetchedTx: merge(cur.fetchedTx, rows) })))
          .catch(() => fresh.forEach((id) => requestedRows.current.delete(`paisa:${id}`)));
      } else {
        fetchRowsByIds('diet', fresh)
          .then((rows) => patch((cur) => ({ fetchedMeals: merge(cur.fetchedMeals, rows) })))
          .catch(() => fresh.forEach((id) => requestedRows.current.delete(`diet:${id}`)));
      }
    },
    [patch],
  );

  /**
   * `Confirm` in a card's tray: the guess was right. The row's confidence goes
   * to 1, which is what the dot reads, so it clears — and stays cleared after
   * a reload, because the row carries it, not the card.
   */
  const confirmRow = useCallback(
    (msg: ConfirmMsg) => {
      const id = msg.rowId;
      if (!id || (msg.source !== 'paisa' && msg.source !== 'diet')) return;
      // A `proposed` card carries a guess the row does not yet hold — the
      // nightly batch would not write it. Confirm sends the guessed values
      // with the confidence, so "haan" makes the guess the row's fact.
      // (spec/in-progress/categorise.md § Review)
      const body: Record<string, unknown> = { confidence: 1 };
      if (msg.state === 'proposed') {
        for (const f of msg.fields) {
          if (f.guessed && (f.key === 'category' || f.key === 'description')) body[f.key] = f.value;
        }
      }
      const stamp = <T extends { id: string; confidence?: number }>(rows: T[]) =>
        rows.map((r) => (r.id === id ? { ...r, ...body } : r));
      patch((cur) =>
        msg.source === 'paisa'
          ? { tx: stamp(cur.tx), committedTx: stamp(cur.committedTx), fetchedTx: stamp(cur.fetchedTx), openRow: null }
          : { meals: stamp(cur.meals), fetchedMeals: stamp(cur.fetchedMeals), openRow: null },
      );
      (msg.source === 'paisa' ? patchTransaction(id, body) : patchMeal(id, { confidence: 1 }))
        .catch(() => notify('Not confirmed — the server refused.', undefined, true));
    },
    [patch, notify],
  );

  /** Delete from a confirm card: the route that owns the row, by source. */
  const deleteConfirmRow = useCallback(
    (msg: ConfirmMsg) => {
      const id = msg.rowId;
      if (!id) return;
      patch((cur) => ({ deletedRows: withId(cur.deletedRows, id), openRow: null }));
      switch (msg.source) {
        case 'paisa':
        case 'diet':
          deleteRow(msg.source, id);
          break;
        case 'work':
          // Only a task card offers it — the Undo on one just added.
          deleteTask(id);
          break;
        case 'pantry':
          deletePantryMove(id).then(
            () => loadPantry(),
            () => notify('Not deleted — the server refused.', undefined, true),
          );
          break;
        case 'memory':
          removeMemory(id);
          break;
        case 'places':
          removePlace(id);
          break;
        case 'body':
          // Only a weight's own card offers it, and only while its weigh-in
          // is live: the reading goes, by its own route.
          if (msg.fields.length === 1 && msg.fields[0].key === 'weight_kg') removeWeighIn(id);
          break;
        default:
          break;
      }
    },
    [patch, notify, deleteRow, deleteTask, loadPantry, removeMemory, removePlace, removeWeighIn],
  );

  /**
   * Undo on a removed payment or meal. Not optimistic: the row comes back
   * when the server says it has, and then everywhere at once — the deleted
   * set lets go of it, the row returns to the ledger, and every card that
   * showed it is live again (one born of a delete becomes a plain receipt).
   * Udhaar, the limit and the pantry are the server's arithmetic, so the
   * deck is read again behind it.
   */
  const restoring = useRef<Set<string>>(new Set());
  const restoreRow = useCallback(
    async (source: 'paisa' | 'diet', id: string) => {
      // One tap, one restore: a second would be refused, and say so falsely.
      if (restoring.current.has(id)) return;
      restoring.current.add(id);
      try {
        if (source === 'paisa') {
          const row = await restoreTransaction(id);
          // The deck holds this month's spending; any other row lives with the
          // fetched ones, and the live copy goes there either way, so a card
          // never loses it while the deck reloads.
          const deck = row.kind === 'expense' && (row.date ?? '').slice(0, 7) === TODAY_ISO.slice(0, 7);
          patch((cur) => ({
            deletedRows: cur.deletedRows.filter((x) => x !== id),
            tx: deck && !row.commitmentId ? upsert(cur.tx, row) : cur.tx,
            committedTx: deck && row.commitmentId ? upsert(cur.committedTx, row) : cur.committedTx,
            fetchedTx: upsert(cur.fetchedTx, row),
          }));
        } else {
          // The deck holds every live meal.
          const meal = await restoreMeal(id);
          patch((cur) => ({
            deletedRows: cur.deletedRows.filter((x) => x !== id),
            meals: upsert(cur.meals, meal),
            fetchedMeals: upsert(cur.fetchedMeals, meal),
          }));
        }
        void Promise.all([reloadDeck(), loadLimit(), ...(source === 'diet' ? [loadPantry()] : [])])
          .catch(() => undefined);
      } catch (e) {
        // A 401 signs out on its own; otherwise say which — refused, or never reached.
        const code = errorStatus(e);
        if (code !== 401) notify(code === null ? "Couldn't undo — didn't reach the server." : "Couldn't undo — the server refused.", undefined, true);
      } finally {
        restoring.current.delete(id);
      }
    },
    [patch, notify, reloadDeck, loadLimit, loadPantry],
  );

  /**
   * Tap on a dish or exercise card: log it, now. One tap has one meaning, so
   * no model sits between the tap and the row — `POST /chat/act` runs the
   * tool and hands back the same cards the agent would have built. Nothing
   * joins the thread: the confirmation is a receipt that flashes and goes,
   * and the card itself reads `✓ Logged` from the ledger from then on.
   */
  const logSuggested = useCallback(
    async (item: SuggestItem) => {
      const s0 = stateRef.current;
      if (s0.pendingLogs.includes(item.ref) || s0.suggestLogged[item.ref]) return;
      patch({ pendingLogs: [...s0.pendingLogs, item.ref], openRow: null });
      const localDay = isoDay(DATA_YEAR, DATA_MONTH, DIET_TODAY);
      try {
        const out = item.type === 'exercise'
          ? await actChat('log_exercise', { exercise_id: item.ref, local_day: localDay })
          : await actChat('log_meal', {
              dish_id: item.ref, text_said: item.name,
              meal_type: item.mealType ?? mealTypeNow(), local_day: localDay,
            });
        const confirm = out.cards.find((c) => c.kind === 'confirm') as
          { lede?: string; fields?: { key: string; value: string }[] } | undefined;
        const what = confirm?.fields?.find((f) => f.key === 'dish' || f.key === 'name')?.value ?? item.name;
        patch((cur) => ({
          suggestLogged: { ...cur.suggestLogged, [item.ref]: confirm?.lede ?? 'logged' },
          pendingLogs: cur.pendingLogs.filter((r) => r !== item.ref),
        }));
        notify(`${what} logged`, confirm?.lede);
        void Promise.all([reloadDeck(), loadExercises()]).catch(() => undefined);
      } catch {
        patch((cur) => ({ pendingLogs: cur.pendingLogs.filter((r) => r !== item.ref) }));
        notify("Couldn't log it — the server refused.", undefined, true);
      }
    },
    [patch, notify, reloadDeck, loadExercises],
  );

  /** ★ in a dish card's tray — the library, through its route. */
  const saveSuggested = useCallback(
    (msgId: string, item: SuggestItem) => {
      if (item.type !== 'dish') return;
      const flip = (saved: boolean) =>
        patch((cur) => ({
          chat: cur.chat.map((m) =>
            m.kind === 'suggest' && m.id === msgId
              ? { ...m, items: m.items.map((it) => (it.ref === item.ref ? { ...it, saved } : it)) }
              : m,
          ),
          openRow: null,
        }));
      flip(!item.saved);
      (item.saved ? unsaveDish(item.ref) : saveDish(item.ref)).then(
        () => loadDishes(),
        () => {
          flip(item.saved);
          notify('Not saved — the server refused.', undefined, true);
        },
      );
    },
    [patch, notify, loadDishes],
  );

  /** "Not this": the item goes, and the card with it when it was the last. */
  const dismissSuggested = useCallback(
    (msgId: string, ref: string) =>
      patch((cur) => ({
        chat: cur.chat.flatMap((m) => {
          if (m.kind !== 'suggest' || m.id !== msgId) return [m];
          const items = m.items.filter((it) => it.ref !== ref);
          return items.length ? [{ ...m, items }] : [];
        }),
        openRow: null,
      })),
    [patch],
  );


  return {
    state,
    view,
    suggestions,
    limit,
    actions: {
      reloadDeck,
      setModeByIndex,
      setRange: (range: Range) => patch({ range }),
      toggleMore: () => patch((s) => ({ moreOpen: !s.moreOpen })),
      /** The menu: a place, pushed like any page. Opening it lets the deck back in. */
      openMenu: () => openScreen({ kind: 'menu' }),
      setTyped: (typed: string) => patch({ typed }),
      /** Blur is ignored mid-dictation, so the deck doesn't flash back. */
      setComposing: (composing: boolean) =>
        patch((st) => (!composing && st.listening ? {} : { composing })),
      showWorkTasks,
      editGoal,
      editTargets,
      saveField,
      saveWeighIn,
      removeWeighIn,
      saveMemory,
      addMemoryRow,
      removeMemory,
      addHabit,
      editSchedule,
      editHabit,
      removeHabit,
      openProfile,
      openProfileGroup,
      tapMic,
      pickMedia,
      openMenuRow,
      /**
       * Opening from a card carries that card's mode across, so the report
       * lands on what you were looking at instead of wherever it was left.
       */
      openReport: (mode: Mode) => {
        const reportMode: ReportMode = mode === 'work' ? 'kaam' : mode;
        patch({ reportMode });
        openScreen({ kind: 'report', mode: reportMode });
      },
      /** The Report's tab: changed in place on its entry, so a reload reopens it on the same one. */
      setReportMode: (reportMode: ReportMode) => {
        patch({ reportMode });
        replaceScreen({ kind: 'report', mode: reportMode });
      },
      setReportRange: (reportRange: ReportRange) => patch({ reportRange }),
      /** A Your data tile: its section, as a page over the overview. */
      openDataSection: (section: Section) => openScreen({ kind: 'data', section }),
      addPantryMove,
      undoPantryMove,
      addPantryFood,
      savePantrySettings,
      setStaple,
      stopTrackingFood,
      toggleSaveDish,
      setContext,
      clearContext,
      answer: (text: string) => void ask(text),
      filePerson,
      addPerson,
      didExerciseOnce,
      addExercise,
      addPlace,
      editPlace,
      removePlace,
      loadPantryMoves: (foodId?: string) =>
        fetchPantryMoves(foodId).then((pantryMoves) => patch({ pantryMoves })),
      dropItem: (id: string) =>
        patch((st) => ({ library: st.library.filter((i) => i.id !== id) })),
      send,
      /**
       * A page's composer. An ask leaves every page — its answer is in the
       * thread — and lands on Home with the thread up and the cursor in the
       * composer, as the phone lands in Chat. A correction stays: the row it
       * fixes is on this page, and updates in place.
       */
      sendFromPage: () => {
        if (send() !== 'ask') return;
        landInChat.current = true;
        screens.closeAll();
      },
      toggleRow,
      deleteRow,
      deleteAny,
      linkPayment,
      openCommitmentSheet,
      saveCommitment,
      skipCommitment,
      repeatCommitment,
      removeCommitment,
      loadCommitments,
      markRepaid,
      addOpen,
      gift,
      undoRepayment,
      editRow,
      cancelEdit,
      toggleTodo,
      ensureRows,
      confirmRow,
      deleteConfirmRow,
      restoreRow,
      logSuggested,
      saveSuggested,
      dismissSuggested,
      /**
       * Resend a message that never went: it replaces the failed bubble, not
       * joins it — about the same row, if it was said about one.
       */
      retry: (text: string, failedId?: string, context?: ComposerContext) => {
        if (failedId) patch((s) => ({ chat: s.chat.filter((m) => m.id !== failedId) }));
        void ask(text, context);
      },
      notify,
      dismissToast,
      loadOlderChat,
      clearConversation,
      /** Open a screen over the top one. */
      push: screens.push,
      /** Back one screen; with `from`, only while that screen is on top. */
      pop: screens.pop,
      /** What Escape does: the innermost open thing, else pop. */
      back: screens.back,
      /** Every screen at once, back to Home. Only an ask does this. */
      closeAll: screens.closeAll,
    },
  };
}

export type PersonaOS = ReturnType<typeof usePersonaOS>;
