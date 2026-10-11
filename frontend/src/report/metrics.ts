import { BORROWED, DIET_TODAY_ISO, KCAL_TARGET, PENDING, PROTEIN_TARGET, SALARY, SLEEP_TARGET_MIN, STEP_TARGET, TODAY_ISO } from '../data/live';
import { PROJECTS, SLEEP, STEPS } from '../data/live';
import { addDays, dayOfMonth, diffDays, eachDay, maxDay, monthStart } from '../lib/day';
import { duration } from '../lib/clock';
import { rupees } from '../lib/format';
import { categoryPalette, color } from '../theme';
import type { Meal, RingSpec, Todo, Tx } from '../types';

/** "1 day", "7 days" — the report can span a single day, so this cannot be a template. */
const days = (n: number) => `${n} day${n === 1 ? '' : 's'}`;

/** A tile's footnote when there is no earlier period: the target, or the honest absence of one. */
const targetSub = (t: number | null, show: (n: number) => string) =>
  t == null ? 'no target set' : `target ${show(t)}`;

export type ReportMode = 'paisa' | 'diet' | 'kaam';
export type ReportRange = 'aaj' | '7din' | '14din' | 'mahina';

export const RANGE_LABELS: Record<ReportRange, string> = {
  aaj: 'Today',
  '7din': '7 days',
  '14din': '14 days',
  mahina: 'Month',
};

/** An inclusive span of ISO local days. */
export interface Span {
  from: string;
  to: string;
  days: number;
}

/** A row's ISO day; a row written optimistically has none yet — it is today's. */
const isoOf = (r: { date?: string }) => r.date ?? TODAY_ISO;

/** Which way is "better" — decides whether a delta reads green or red. */
export type Good = 'up' | 'down' | 'none';

export interface Tile {
  key: string;
  label: string;
  value: string;
  /**
   * Quiet context under the number. Where a comparison exists this is the
   * previous period's own figure — a number you can weigh against the one
   * above it, rather than a restatement of it.
   */
  sub?: string;
  /** Some figures have no previous-period equivalent — don't show a placeholder. */
  noDelta?: boolean;
  /** Fractional change vs the previous span; null when there is nothing to compare. */
  delta: number | null;
  deltaLabel: string | null;
  good: Good;
}

export interface TrendPoint {
  day: number;
  value: number;
  /** Same slot in the previous span, or null if that span had no data. */
  prev: number | null;
}

export interface BreakdownRow {
  label: string;
  valueStr: string;
  share: number;
  delta: number | null;
  color: string;
}


/** One donut with its legend. Paisa has a single chart; Diet has two. */
export interface ChartSection {
  key: string;
  title: string;
  rows: BreakdownRow[];
  /** Centre figure when no slice is selected. */
  totalStr: string;
  /** The line under it. */
  centreSub: string;
  /**
   * How much of the ring the segments occupy — the circle's 100% is the money
   * that came in. null when the segments are the whole ring.
   */
  fill: { share: number; capStr: string } | null;
}

export interface ReportData {
  span: Span;
  prevSpan: Span;
  hasPrev: boolean;
  tiles: Tile[];
  trend: { points: TrendPoint[]; target: number; targetLabel: string };
  charts: ChartSection[];
  /**
   * Diet answers with nested arcs instead of a donut — two distributions cost
   * twice the height, and the useful question is only "how often in band?".
   */
  rings: RingSpec[] | null;
  /** Heading over the chart card. */
  chartsTitle: string;
  /** Secondary figures, behind the card's "More" menu. */
  extraTiles: Tile[];
  coverage: string;
}

/** The most recent day each mode has data for. */
const anchorFor = (mode: ReportMode) => (mode === 'diet' ? DIET_TODAY_ISO : TODAY_ISO);

export function spanFor(mode: ReportMode, range: ReportRange): Span {
  const to = anchorFor(mode);
  if (range === 'mahina') {
    const from = monthStart(to);
    return { from, to, days: diffDays(from, to) + 1 };
  }
  // Today compares against yesterday — `previous` needs no special case.
  const days = range === 'aaj' ? 1 : range === '7din' ? 7 : 14;
  return { from: addDays(to, -(days - 1)), to, days };
};

/**
 * The span immediately before this one, still clamped to the start of the
 * month so a comparison stays inside one month. A clamped span can be shorter,
 * or empty when the current span already starts on the 1st.
 */
const previous = (s: Span): Span => {
  const to = addDays(s.from, -1);
  const from = maxDay(monthStart(s.from), addDays(to, -(s.days - 1)));
  return { from, to, days: Math.max(0, diffDays(from, to) + 1) };
};

const inSpan = (iso: string, s: Span) => iso >= s.from && iso <= s.to;

function pct(cur: number, prev: number): number | null {
  if (!prev) return null;
  return (cur - prev) / prev;
}

const signed = (n: number, unit = '') =>
  `${n > 0 ? '+' : n < 0 ? '−' : ''}${Math.abs(n)}${unit}`;

const pctLabel = (d: number | null) =>
  d === null ? null : `${d > 0 ? '+' : d < 0 ? '−' : ''}${Math.abs(Math.round(d * 100))}%`;

/** Totals per day, plus the handful of aggregates every tile is built from. */
function rollPaisa(tx: Tx[], s: Span) {
  const rows = tx.filter((t) => inSpan(isoOf(t), s));
  const byDay = new Map<string, number>();
  for (const t of rows) byDay.set(isoOf(t), (byDay.get(isoOf(t)) ?? 0) + t.amt);
  const total = rows.reduce((a, t) => a + t.amt, 0);
  const other = rows.filter((t) => t.cat === 'Other').reduce((a, t) => a + t.amt, 0);
  return {
    rows,
    byDay,
    total,
    other,
    activeDays: byDay.size,
    txCount: rows.length,
  };
}

function rollDiet(meals: Meal[], s: Span) {
  const rows = meals.filter((m) => inSpan(isoOf(m), s));
  const p = new Map<string, number>();
  const k = new Map<string, number>();
  for (const m of rows) {
    p.set(isoOf(m), (p.get(isoOf(m)) ?? 0) + m.p);
    k.set(isoOf(m), (k.get(isoOf(m)) ?? 0) + m.k);
  }
  const days = [...p.keys()];
  const sumP = days.reduce((a, d) => a + (p.get(d) ?? 0), 0);
  const sumK = days.reduce((a, d) => a + (k.get(d) ?? 0), 0);
  return {
    rows,
    p,
    k,
    loggedDays: days.length,
    avgP: days.length ? sumP / days.length : 0,
    avgK: days.length ? sumK / days.length : 0,
    hitDays: PROTEIN_TARGET == null ? 0 : days.filter((d) => (p.get(d) ?? 0) >= PROTEIN_TARGET!).length,
    density: sumP ? sumK / sumP : 0,
  };
}


/**
 * Spend categories: the mode hues at base, then soft, then grey. Never amber
 * (the estimate) and never red (over) — a category is not a warning.
 */
const CAT_COLORS = categoryPalette;

function paisaReport(tx: Tx[], span: Span, limit: number | null): ReportData {
  const prevSpan = previous(span);
  const cur = rollPaisa(tx, span);
  const prev = rollPaisa(tx, prevSpan);
  const hasPrev = prevSpan.days > 0 && prev.txCount > 0;

  /**
   * How many transactions landed while that day was still inside the limit.
   * Running total per day, in log order — the honest reading of "limit ke andar
   * kitne transactions hue".
   */
  const withinLimit = (rows: Tx[]) => {
    const running = new Map<string, number>();
    let ok = 0;
    for (const t of rows) {
      const before = running.get(isoOf(t)) ?? 0;
      if (limit != null && before + t.amt <= limit) ok += 1;
      running.set(isoOf(t), before + t.amt);
    }
    return ok;
  };
  const withinCur = withinLimit(cur.rows);
  const withinPrev = withinLimit(prev.rows);
  const rateCur = cur.txCount ? withinCur / cur.txCount : 0;
  const ratePrev = prev.txCount ? withinPrev / prev.txCount : 0;

  const avgDayCur = cur.total / span.days;
  const avgDayPrev = prev.total / prevSpan.days;

  const tiles: Tile[] = [
    {
      key: 'total',
      label: span.days === 1 ? 'Spent today' : 'Total spend',
      value: rupees(cur.total),
      sub: hasPrev ? `${rupees(prev.total)} before` : undefined,
      delta: hasPrev ? pct(cur.total, prev.total) : null,
      deltaLabel: hasPrev ? pctLabel(pct(cur.total, prev.total)) : null,
      good: 'down',
    },
    // Over a single day this is the headline again, to the rupee. A row that
    // restates the number above it is not context, it is noise.
    ...(span.days === 1
      ? []
      : [
          {
            key: 'perday',
            label: 'Daily average',
            value: rupees(avgDayCur),
            sub: hasPrev ? `${rupees(avgDayPrev)} before` : undefined,
            delta: hasPrev ? pct(avgDayCur, avgDayPrev) : null,
            deltaLabel: hasPrev ? pctLabel(pct(avgDayCur, avgDayPrev)) : null,
            good: 'down' as const,
          },
        ]),
    {
      key: 'within',
      // Payments, not days. `31/38` read as "31 of 38 days" to the one person
      // who uses this, which is what a cryptic ratio buys you.
      label: 'Payments within limit',
      // No limit (no income yet) means nothing to be within — unknown, not 0.
      value: limit == null ? '—' : `${withinCur} of ${cur.txCount}`,
      sub: limit == null ? 'no limit yet' : `limit ${rupees(limit)}`,
      delta: limit != null && hasPrev ? rateCur - ratePrev : null,
      // The previous ratio itself, rather than a change in percentage points —
      // "5/20 se" needs no explaining.
      deltaLabel: limit != null && hasPrev ? `from ${withinPrev}/${prev.txCount}` : null,
      good: 'up',
    },
    (() => {
      // Informational only: the pool counts neither a friend's promise nor a
      // friend's money. Out is yours with them; owe is theirs with you.
      const out = PENDING.reduce((a, p) => a + p.remaining, 0);
      const owe = BORROWED.reduce((a, p) => a + p.remaining, 0);
      return {
        key: 'udhaar',
        label: 'Udhaar',
        value: `out ${rupees(out)}`,
        sub: owe ? `owe ${rupees(owe)}` : PENDING.length ? `${PENDING.length} lending${PENDING.length > 1 ? 's' : ''} open` : 'nothing out, nothing owed',
        delta: null,
        deltaLabel: null,
        good: 'none' as const,
      };
    })(),
  ];

  const prevDays = eachDay(prevSpan.from, prevSpan.to);
  const points: TrendPoint[] = eachDay(span.from, span.to).map((d, i) => {
    const prevDay = prevDays[i];
    return {
      day: dayOfMonth(d),
      value: cur.byDay.get(d) ?? 0,
      prev: hasPrev && prevDay ? (prev.byDay.get(prevDay) ?? 0) : null,
    };
  });

  const catCur = new Map<string, number>();
  const catPrev = new Map<string, number>();
  for (const t of cur.rows) catCur.set(t.cat, (catCur.get(t.cat) ?? 0) + t.amt);
  for (const t of prev.rows) catPrev.set(t.cat, (catPrev.get(t.cat) ?? 0) + t.amt);
  const rows: BreakdownRow[] = [...catCur.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([label, v], i) => ({
      label,
      valueStr: rupees(v),
      share: cur.total ? v / cur.total : 0,
      delta: hasPrev ? pct(v, catPrev.get(label) ?? 0) : null,
      // Past the six hues every category is grey: a seventh colour would
      // have to borrow amber or red, which mean something else.
      color: CAT_COLORS[Math.min(i, CAT_COLORS.length - 1)],
    }));

  return {
    span,
    prevSpan,
    hasPrev,
    tiles,
    trend: { points, target: limit ?? 0, targetLabel: limit == null ? '' : `Limit ${rupees(limit)}` },
    extraTiles: [],
    rings: null,
    chartsTitle: 'Where it went',
    charts: [
      {
        key: 'cat',
        title: 'Where it went',
        rows,
        totalStr: rupees(cur.total),
        centreSub: 'total',
        fill: { share: SALARY ? cur.total / SALARY : 0, capStr: rupees(SALARY) },
      },
    ],
    coverage: `${cur.activeDays} of ${span.days} days logged`,
  };
}

/** Calories cut both ways — over the band is as much a miss as under it. */
const KCAL_SLACK = 200;

function dietReport(meals: Meal[], span: Span): ReportData {
  const prevSpan = previous(span);
  const cur = rollDiet(meals, span);
  const prev = rollDiet(meals, prevSpan);
  const hasPrev = prevSpan.days > 0 && prev.loggedDays > 0;

  const rateCur = cur.loggedDays ? cur.hitDays / cur.loggedDays : 0;
  const ratePrev = prev.loggedDays ? prev.hitDays / prev.loggedDays : 0;

  // "In band" is the point of the rings: protein at Theek or better, calories
  // inside the slack either side of target.
  const proteinInBand = [...cur.p.values()].filter((v) => v >= 90).length;
  const kcalInBand =
    KCAL_TARGET == null
      ? 0
      : [...cur.k.values()].filter((v) => Math.abs(v - KCAL_TARGET!) <= KCAL_SLACK).length;

  const meanOf = (xs: number[]) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 0);
  const sleepIn = (sp: Span) =>
    meanOf(
      SLEEP.filter((n) => inSpan(n.date, sp)).map((n) => n.endMin - n.startMin),
    );
  const stepsIn = (sp: Span) =>
    meanOf(STEPS.filter((d) => inSpan(d.date, sp)).map((d) => d.steps));
  const sleepCur = sleepIn(span);
  const sleepPrev = sleepIn(prevSpan);
  const stepsCur = stepsIn(span);
  const stepsPrev = stepsIn(prevSpan);

  const tiles: Tile[] = [
    {
      key: 'protein',
      label: span.days === 1 ? 'Protein today' : 'Protein a day',
      value: `${Math.round(cur.avgP)}g`,
      sub: hasPrev ? `${Math.round(prev.avgP)}g before` : targetSub(PROTEIN_TARGET, (t) => `${t}g`),
      delta: hasPrev ? pct(cur.avgP, prev.avgP) : null,
      deltaLabel: hasPrev ? signed(Math.round(cur.avgP - prev.avgP), 'g') : null,
      good: 'up',
    },
    {
      key: 'kcal',
      label: span.days === 1 ? 'Calories today' : 'Calories a day',
      value: Math.round(cur.avgK).toLocaleString('en-IN'),
      sub: hasPrev
        ? `${Math.round(prev.avgK).toLocaleString('en-IN')} before`
        : targetSub(KCAL_TARGET, (t) => t.toLocaleString('en-IN')),
      delta: hasPrev ? pct(cur.avgK, prev.avgK) : null,
      deltaLabel: hasPrev ? pctLabel(pct(cur.avgK, prev.avgK)) : null,
      good: 'none',
    },
    {
      key: 'sleep',
      label: span.days === 1 ? 'Sleep' : 'Sleep a day',
      value: sleepCur ? duration(sleepCur) : '—',
      sub: sleepPrev ? `${duration(sleepPrev)} before` : targetSub(SLEEP_TARGET_MIN, duration),
      delta: sleepPrev ? pct(sleepCur, sleepPrev) : null,
      deltaLabel: sleepPrev ? signed(Math.round(sleepCur - sleepPrev), 'm') : null,
      good: 'up',
    },
    {
      key: 'steps',
      label: span.days === 1 ? 'Steps' : 'Steps a day',
      value: stepsCur ? Math.round(stepsCur).toLocaleString('en-IN') : '—',
      sub: stepsPrev
        ? `${Math.round(stepsPrev).toLocaleString('en-IN')} before`
        : targetSub(STEP_TARGET, (t) => t.toLocaleString('en-IN')),
      delta: stepsPrev ? pct(stepsCur, stepsPrev) : null,
      deltaLabel: stepsPrev ? pctLabel(pct(stepsCur, stepsPrev)) : null,
      good: 'up',
    },
  ];

  /** Still true, just not the first thing you need each morning. */
  const extraTiles: Tile[] = [
    {
      key: 'hit',
      label: 'Target hit',
      value: `${cur.hitDays}/${cur.loggedDays}`,
      sub: targetSub(PROTEIN_TARGET, (t) => `${t}g`),
      delta: hasPrev ? rateCur - ratePrev : null,
      deltaLabel: hasPrev ? `from ${prev.hitDays}/${prev.loggedDays}` : null,
      good: 'up',
    },
    {
      key: 'logged',
      label: 'Days logged',
      value: `${cur.loggedDays}/${span.days}`,
      sub: hasPrev ? `${prev.loggedDays}/${prevSpan.days} before` : undefined,
      delta: hasPrev ? pct(cur.loggedDays, prev.loggedDays) : null,
      deltaLabel: hasPrev ? signed(cur.loggedDays - prev.loggedDays, ' days') : null,
      good: 'up',
    },
  ];

  const prevDays = eachDay(prevSpan.from, prevSpan.to);
  const points: TrendPoint[] = eachDay(span.from, span.to).map((d, i) => {
    const prevDay = prevDays[i];
    return {
      day: dayOfMonth(d),
      value: cur.p.get(d) ?? 0,
      prev: hasPrev && prevDay ? (prev.p.get(prevDay) ?? 0) : null,
    };
  });

  return {
    span,
    prevSpan,
    hasPrev,
    tiles,
    trend: {
      points,
      target: PROTEIN_TARGET ?? 0,
      targetLabel: PROTEIN_TARGET == null ? '' : `Target ${PROTEIN_TARGET}g`,
    },
    extraTiles,
    chartsTitle: 'How often in band',
    charts: [],
    rings: [
      {
        key: 'kcal',
        caption: 'Calories',
        valueStr: String(kcalInBand),
        totalStr: days(cur.loggedDays),
        pct: cur.loggedDays ? kcalInBand / cur.loggedDays : 0,
        // Diet's hue, stepped like the home card: calories base, protein ink.
        color: color.diet,
      },
      {
        key: 'protein',
        caption: 'Protein',
        valueStr: String(proteinInBand),
        totalStr: days(cur.loggedDays),
        pct: cur.loggedDays ? proteinInBand / cur.loggedDays : 0,
        color: color.dietInk,
      },
    ],
    coverage: `${cur.loggedDays} of ${days(span.days)} logged`,
  };
}

/**
 * Kaam has no trend and no distribution — a task is done or it is not, and
 * plotting that per day says less than simply listing what is late. The page
 * renders the project bars in place of a chart, so `charts` and `rings` stay
 * empty rather than being filled with something that looks like analysis.
 */
function kaamReport(todos: Todo[], span: Span): ReportData {
  const work = todos.filter((t) => t.kind === 'work');
  const open = work.filter((t) => !t.done);
  const late = open.filter((t) => t.due != null && t.due < TODAY_ISO);
  const backlog = open.filter((t) => t.due == null);
  const doneInSpan = work.filter((t) => t.done && t.doneOn != null && inSpan(t.doneOn, span));

  return {
    span,
    prevSpan: previous(span),
    hasPrev: false,
    tiles: [
      { key: 'open', label: 'Open', value: String(open.length), noDelta: true, delta: null, deltaLabel: '', good: 'none' },
      {
        key: 'done',
        label: 'Done',
        value: String(doneInSpan.length),
        // The only tile the range actually moves — say so, or the dropdown
        // looks like it does nothing.
        sub: span.days === 1 ? 'today' : `in ${days(span.days)}`,
        noDelta: true,
        delta: null,
        deltaLabel: '',
        good: 'none',
      },
      {
        key: 'late',
        label: 'Past date',
        value: String(late.length),
        noDelta: true,
        delta: null,
        deltaLabel: '',
        good: 'none',
      },
      {
        key: 'backlog',
        label: 'No date',
        value: String(backlog.length),
        noDelta: true,
        delta: null,
        deltaLabel: '',
        good: 'none',
      },
    ],
    trend: { points: [], target: 0, targetLabel: '' },
    charts: [],
    rings: null,
    chartsTitle: 'Project',
    extraTiles: [],
    coverage: `${work.length} tasks, ${PROJECTS.length} projects`,
  };
}

export function buildReport(
  mode: ReportMode,
  range: ReportRange,
  tx: Tx[],
  meals: Meal[],
  limit: number | null,
  todos: Todo[],
): ReportData {
  const span = spanFor(mode, range);
  if (mode === 'kaam') return kaamReport(todos, span);
  return mode === 'paisa' ? paisaReport(tx, span, limit) : dietReport(meals, span);
}

/* ─── Projected saving — the cricket card ─────────────────────────────── */

