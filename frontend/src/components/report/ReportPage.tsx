import { memo, useEffect, useRef, useState, type ReactNode } from 'react';
import { CaretDown } from '@phosphor-icons/react';
import PageHeader from '../PageHeader';
import { DeckPages, DeckTabs, SETTLE_MS } from '../Deck';
import ConcentricRings from '../ConcentricRings';
import RingLegend from '../RingLegend';
import DonutChart from './DonutChart';
import ItemList, { type Item } from './ItemList';
import AddOpenRow from './AddOpenRow';
import ProjectChart from '../ProjectChart';
import { groupTasks, projectOf, projectStats, statusLabel } from '../../work/tasks';

import Scorecard from './Scorecard';
import { SLEEP_TARGET_MIN } from '../../data/live';
import { DATA_MONTH, DATA_YEAR, SLEEP_HOURS, TODAY, TODAY_ISO } from '../../data/live';
import type { CommitmentRow, CommitmentsPage, PendingItem, RepaymentItem } from '../../data/api';
import { canCount } from '../commitments/PaymentTray';
import CommitmentLines, { type LineHandlers } from '../commitments/CommitmentLines';
import { inr } from '../commitments/kit';
import { Plus } from '@phosphor-icons/react';
import type { HabitLogRow } from '../../data/api';
import { dayLabel, rupees, shortDay } from '../../lib/format';
import { RANGE_LABELS, buildReport, type ReportMode, type ReportRange } from '../../report/metrics';
import { color, font, inset, modeTone, radius, space } from '../../theme';
import { cardHeading } from '../messages/bubble';
import type { Meal, Todo, Tx } from '../../types';
import type { RowKind } from './ItemList';

const MODES: { id: ReportMode; label: string; tone: string }[] = [
  { id: 'kaam', label: 'Work', tone: modeTone.work.base },
  { id: 'paisa', label: 'Paisa', tone: modeTone.paisa.base },
  { id: 'diet', label: 'Diet', tone: modeTone.diet.base },
];

const RANGES: ReportRange[] = ['aaj', '7din', '14din', 'mahina'];

/** Sentinel for the non-category tab. */
const LENT_TAB = '__lent';
const BORROWED_TAB = '__borrowed';
const COMMITS_TAB = '__commits';
const MODE_TITLE: Record<ReportMode, string> = { paisa: 'Paisa', diet: 'Diet', kaam: 'Work' };

const ALL_TAB = '__all';
const MEALS_TAB = '__meals';
const HABITS_TAB = '__habits';
const SLEEP_TAB = '__sleep';

// Tabs follow the data the app holds, not the seed it was prototyped on: no
// Kadam until steps have a source, and Habits rather than Workout alone.
const TAB_LABELS: Record<string, string> = {
  [ALL_TAB]: 'All',
  [LENT_TAB]: 'Lent',
  [BORROWED_TAB]: 'Borrowed',
  [COMMITS_TAB]: 'Commits',
  [MEALS_TAB]: 'Meals',
  [HABITS_TAB]: 'Habits',
  [SLEEP_TAB]: 'Sleep',
};

interface Props {
  mode: ReportMode;
  range: ReportRange;
  tx: Tx[];
  /** This month's payments that count toward a commitment — listed with spend in All, never in the arithmetic. */
  committedTx: Tx[];
  meals: Meal[];
  todos: Todo[];
  /** From state, not the module store — so ⋮ → Delete reflects immediately. */
  habitLogs: HabitLogRow[];
  /** Udhaar, from state for the same reason: Repaid, Gift and Undo show at once. */
  pending: PendingItem[];
  borrowed: PendingItem[];
  repayments: RepaymentItem[];
  limit: number | null;
  onMode: (m: ReportMode) => void;
  onRange: (r: ReportRange) => void;
  /** What ← returns to — the menu, or Home when a card opened the report. */
  backTo: string;
  onBack: () => void;
  /** The same ⋮ actions the chat table has — one API, wherever the row shows. */
  onEdit: (kind: 'paisa' | 'diet', id: string, text: string) => void;
  onDelete: (kind: RowKind, id: string) => void;
  /** Lent / Borrowed tabs: a repayment for an amount; stop expecting it; take a repayment back; a new row. */
  onRepaid: (openId: string, amount: number) => Promise<boolean>;
  onGift: (lendingId: string) => void;
  onUndoRepayment: (repaymentId: string) => void;
  onAddOpen: (leg: 'lent' | 'borrowed', who: string, amount: number) => Promise<boolean>;
  /** This month's commitments, and what a payment can do about them. */
  commitments: CommitmentRow[];
  /** The month's page, for the Commits tab; its lines and add button. */
  commitmentsPage: CommitmentsPage | null;
  commitmentHandlers: LineHandlers;
  onAddCommitment: () => void;
  onLink: (txId: string, commitmentId: string | null) => void;
  onMake: (tx: Tx) => void;
  /** The same composer as the home screen, floating over this page while it is on top. */
  composer: ReactNode;
}

/** What one mode's page reads — everything but the page's own chrome, plus the shared filter. */
type BodyProps = Omit<Props, 'onMode' | 'onRange' | 'backTo' | 'onBack' | 'composer'> & {
  /** The page's filter, shared by the modes: a tab a mode does not have reads as All. */
  tab: string;
  onTab: (t: string) => void;
  /** The page on show. One that has slid away goes back to its top. */
  active: boolean;
};

const sectionTitle = {
  ...cardHeading,
  marginBottom: 8,
};

/**
 * A glance, not an analysis. Numbers, one ring, and a row of questions —
 * anything deeper is the agent's job, which is why the composer sits here too.
 *
 * The modes switch the way Home's deck does, with the same code: the names
 * are `DeckTabs` and each mode is a page of `DeckPages`. A tap slides the
 * page in; a swipe settles and sets the mode. As on the phone, the filter is
 * the page's, shared by the modes, and a mode left behind goes back to its top.
 */
export default function ReportPage(props: Props) {
  const { mode, range, onMode, onRange, backTo, onBack, composer, ...body } = props;
  const index = Math.max(0, MODES.findIndex((m) => m.id === mode));
  const go = (i: number) => onMode(MODES[i].id);
  const [tab, setTab] = useState<string>(ALL_TAB);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Report"
      tabIndex={-1}
      style={{
        position: 'absolute',
        inset: 0,
        zIndex: 80,
        background: color.paper,
        display: 'flex',
        flexDirection: 'column',
        padding: `${inset.top} 0 0`,
        animation: 'fadeup 0.28s cubic-bezier(0.3,0.7,0.3,1)',
        outline: 'none',
      }}
    >
      <div style={{ padding: `0 ${space.gutter}px 16px`, flex: '0 0 auto' }}>
        <PageHeader back={{ label: backTo, onClick: onBack }} eyebrow="Report" title={MODE_TITLE[mode]} />

        {/* The same row as the home deck's: the modes as words, the current
            one underlined in its colour, the period as words and a caret. */}
        <DeckTabs tabs={MODES} index={index} onIndex={go} label="Report mode" idPrefix="report" style={{ marginTop: 12 }}>
          <label
            style={{
              position: 'relative',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              padding: '4px 0 8px',
              fontFamily: font.sans,
              fontSize: 14,
              lineHeight: '20px',
              color: color.muted,
              cursor: 'pointer',
            }}
          >
            {RANGE_LABELS[range]}
            <CaretDown size={14} color="currentColor" aria-hidden />
            <select
              value={range}
              onChange={(e) => onRange(e.target.value as ReportRange)}
              aria-label="Period"
              style={{
                position: 'absolute',
                inset: 0,
                width: '100%',
                opacity: 0,
                cursor: 'pointer',
                border: 'none',
                fontSize: 16,
              }}
            >
              {RANGES.map((r) => (
                <option key={r} value={r}>
                  {RANGE_LABELS[r]}
                </option>
              ))}
            </select>
          </label>
        </DeckTabs>
      </div>

      <DeckPages ids={MODES.map((m) => m.id)} index={index} onIndex={go} idPrefix="report" fill>
        {(i, on) => <ModeReport {...body} mode={MODES[i].id} range={range} tab={tab} onTab={setTab} active={on} />}
      </DeckPages>

      {composer}
    </div>
  );
}

/**
 * One mode's page: its numbers, its ring, its tabs and its rows, scrolling on
 * its own. Memoised: a swipe redraws the deck on every move, and the pages'
 * props do not change while it does — only the deck's transforms.
 */
const ModeReport = memo(function ModeReport({
  mode,
  range,
  tab,
  onTab,
  active: shown,
  tx,
  committedTx,
  meals,
  todos,
  limit,
  onEdit,
  onDelete,
  habitLogs,
  pending,
  borrowed,
  repayments,
  onRepaid,
  onAddOpen,
  onGift,
  onUndoRepayment,
  commitments,
  commitmentsPage,
  commitmentHandlers,
  onAddCommitment,
  onLink,
  onMake,
}: BodyProps) {
  const data = buildReport(mode, range, tx, meals, limit, todos);
  /** A sentinel tab, or a category label. Each mode rests on its first tab. */
  const paisaTabs = (() => {
    const cats = data.charts[0]?.rows.map((r) => r.label) ?? [];
    // "Other" is the leftovers bucket, so it sits at the end rather than by size.
    return [ALL_TAB, LENT_TAB, BORROWED_TAB, COMMITS_TAB, ...cats.filter((c) => c !== 'Other'), ...cats.filter((c) => c === 'Other')];
  })();
  const kaamGroups = groupTasks(
    todos.filter((t) => t.kind === 'work'),
    'work',
  );
  const tabs =
    mode === 'paisa'
      ? paisaTabs
      : mode === 'kaam'
        ? [ALL_TAB, ...kaamGroups.map((g) => g.label)]
        : [ALL_TAB, MEALS_TAB, HABITS_TAB, SLEEP_TAB];
  const active = tabs.includes(tab) ? tab : tabs[0];

  // Each report opens at its top: a mode left behind goes back to it once it
  // has slid out of view, not while it is still leaving.
  const scroller = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (shown) return;
    const t = window.setTimeout(() => {
      if (scroller.current) scroller.current.scrollTop = 0;
    }, SETTLE_MS);
    return () => window.clearTimeout(t);
  }, [shown]);
  const focus = mode === 'paisa' && active !== LENT_TAB && active !== BORROWED_TAB && active !== COMMITS_TAB && active !== ALL_TAB ? active : null;

  /** A row's own day against the span. Day-of-month numbers cannot do this:
   *  the 13th of two months is one number, so August leaks into September. */
  const inSpan = (iso: string | undefined) => {
    const d = iso ?? TODAY_ISO;
    return d >= data.span.from && d <= data.span.to;
  };
  const isoOf = (r: { date?: string }) => r.date ?? TODAY_ISO;

  let items: Item[] = [];
  /** Whole days from a lending to the deck's anchor day — from dates, never day numbers. */
  const ageDays = (iso: string) =>
    Math.round((Date.UTC(DATA_YEAR, DATA_MONTH, TODAY) - Date.parse(`${iso}T00:00:00Z`)) / 86_400_000);

  const mealItem = (m: Meal): Item => ({
    id: m.id,
    label: m.name,
    sub: [m.type, dayLabel(m)].filter(Boolean).join(' · '),
    valueStr: `${m.k} kcal · ${Math.round(m.p)}g`,
    tone: 'muted',
    kind: 'diet',
    editText: m.name,
  });
  // A habit log carries its count in the label — 'Cigarettes ×2' — and nothing
  // on the right: it is a thing that happened, not a quantity against a target.
  const habitItem = (l: HabitLogRow): Item => ({
    id: l.id,
    label: `${l.habit}${l.amount ? ` ×${l.amount}` : ''}`,
    sub: [shortDay(l.date), l.note].filter(Boolean).join(' · '),
    valueStr: '',
    tone: 'muted',
    kind: 'habit',
  });
  const targets = commitments.filter((c) => c.source === 'commitment' && !c.skipped);
  const txItem = (t: Tx, withCat = false): Item => {
    const linked = Boolean(t.commitmentId);
    return {
      id: t.id,
      label: t.name,
      sub: withCat ? `${t.cat} · ${dayLabel(t)}` : dayLabel(t),
      // Which commitment it counts toward; amber while that was only a guess.
      link: linked
        ? { name: commitments.find((c) => c.id === t.commitmentId)?.name ?? 'Commitment', inferred: Boolean(t.commitmentInferred) }
        : undefined,
      valueStr: `−${rupees(t.amt)}`,
      tone: linked ? ('muted' as const) : ('bad' as const),
      kind: 'paisa',
      editText: `${t.name} ${t.amt}`,
      actions: canCount(t)
        ? [
            {
              label: 'Counts toward…',
              run: () => undefined,
              choices: targets
                .filter((c) => c.id !== t.commitmentId)
                .map((c) => ({ label: c.name, run: () => onLink(t.id, c.id) })),
            },
            ...(linked
              ? [
                  ...(t.commitmentInferred ? [{ label: 'Right', run: () => onLink(t.id, t.commitmentId ?? null) }] : []),
                  { label: 'Not a commitment', run: () => onLink(t.id, null) },
                ]
              : [{ label: 'Make this a commitment', run: () => onMake(t) }]),
          ]
        : [],
    };
  };

  if (active === LENT_TAB || active === BORROWED_TAB) {
    // What is open on this leg, oldest first — the one that has waited longest
    // is the one to ask about. Then what was settled, newest first, each with Undo.
    const leg: 'lent' | 'borrowed' = active === LENT_TAB ? 'lent' : 'borrowed';
    const openRows = leg === 'lent' ? pending : borrowed;
    const settleWord = leg === 'lent' ? 'Repaid' : 'Paid back';
    const open: Item[] = openRows.map((p) => ({
      id: p.id,
      label: p.label,
      sub: `${shortDay(p.date)} · ${ageDays(p.date)} days${p.remaining < p.amount ? ` · of ${rupees(p.amount)}` : ''}${p.pending ? ' · saving' : ''}`,
      valueStr: rupees(p.remaining),
      tone: leg === 'lent' ? ('good' as const) : ('bad' as const),
      // A lending or borrowing is a transaction; it edits and deletes like one.
      kind: 'paisa' as const,
      editText: `${p.label} ${p.amount}`,
      actions: [
        {
          label: settleWord,
          tone: 'good' as const,
          prompt: {
            initial: String(p.remaining),
            prefix: '₹',
            hint: `Enter saves · less than ${rupees(p.remaining)} is a partial`,
            refused: `More than the ${rupees(p.remaining)} still ${leg === 'lent' ? 'out' : 'owed'} — log the extra as ${leg === 'lent' ? 'income' : 'an expense'}.`,
          },
          run: (v?: string) => onRepaid(p.id, Number(v)),
        },
        ...(leg === 'lent' ? [{ label: 'Gift', run: () => onGift(p.id) }] : []),
      ],
    }));
    const settled: Item[] = repayments
      .filter((r) => r.leg === leg)
      .map((r) => ({
        id: r.id,
        label: r.label.replace(/\s+(ko diya|se liya)$/i, ''),
        sub: `${leg === 'lent' ? 'repaid' : 'paid back'} ${shortDay(r.date)}${r.pending ? ' · saving' : r.failed ? ' · unsaved' : ''}`,
        valueStr: rupees(r.amount),
        tone: 'muted' as const,
        kind: 'repayment' as const,
        actions: [{ label: 'Undo', run: () => onUndoRepayment(r.id) }],
      }));
    items = [...open, ...settled];
  } else if (mode === 'paisa' && active === ALL_TAB) {
    // Spend and fixed together, newest first — the month as it was paid.
    items = [...tx, ...committedTx]
      .filter((t) => inSpan(t.date))
      .sort((x, y) => y.day - x.day)
      .map((t) => txItem(t, true));
  } else if (mode === 'diet' && active === ALL_TAB) {
    // Meals and habits interleaved, newest first — the list reads like the day did.
    const ms = meals.filter((m) => inSpan(m.date)).map((m) => ({ d: isoOf(m), it: mealItem(m) }));
    const hs = habitLogs.filter((l) => inSpan(l.date)).map((l) => ({ d: l.date, it: habitItem(l) }));
    items = [...ms, ...hs].sort((a, b) => b.d.localeCompare(a.d)).map((x) => x.it);
  } else if (active === MEALS_TAB) {
    items = meals.filter((m) => inSpan(m.date)).reverse().map(mealItem);
  } else if (active === HABITS_TAB) {
    items = [...habitLogs]
      .filter((l) => inSpan(l.date))
      .sort((a, b) => b.date.localeCompare(a.date))
      .map(habitItem);
  } else if (active === SLEEP_TAB) {
    // Hours from `days`, the 3 real nights. No ⋮: days has no write path yet.
    items = SLEEP_HOURS.filter((n) => inSpan(n.date))
      .sort((a, b) => b.date.localeCompare(a.date))
      .map((n) => ({
        id: `s${n.date}`,
        label: shortDay(n.date),
        valueStr: `${n.hours} h`,
        tone:
          SLEEP_TARGET_MIN == null
            ? ('muted' as const)
            : n.hours * 60 >= SLEEP_TARGET_MIN
              ? ('good' as const)
              : ('warn' as const),
      }));
  } else if (mode === 'kaam') {
    const rows =
      active === ALL_TAB
        ? kaamGroups.flatMap((g) => g.tasks)
        : (kaamGroups.find((g) => g.label === active)?.tasks ?? []);
    items = rows.map((t) => ({
      id: t.id,
      label: t.name,
      // On the "All" tab a task has to say which project it belongs to; inside a
      // project tab that would just repeat the tab you are standing on.
      sub:
        active === ALL_TAB
          ? [projectOf(t.project)?.name, t.src].filter(Boolean).join(' · ')
          : (t.src ?? 'said aloud'),
      valueStr: statusLabel(t) || 'no date',
      tone: t.done
        ? ('muted' as const)
        : t.due == null
          ? ('muted' as const)
          : t.due < TODAY_ISO
            ? ('bad' as const)
            : t.due === TODAY_ISO
              ? ('warn' as const)
              : ('good' as const),
      // Delete only — a task's text is owned by the file it lives in.
      kind: 'task' as const,
    }));
  } else {
    items = tx
      .filter((t) => t.cat === active && inSpan(t.date))
      .reverse()
      .map((t) => txItem(t, false));
  }

  return (
    // Its own scroller, so each mode opens at its top. pan-y: the page scrolls,
    // and a sideways drag is the deck's.
    <div ref={scroller} className="scroll-y" style={{ height: '100%', padding: `0 ${space.gutter}px 116px`, touchAction: 'pan-y' }}>
      {/* Diet leads with two: protein and calories are one question asked
          twice, and demoting either would misstate how this user eats.
          Paisa and Work each have a single answer — spent, and open. */}
      <Scorecard
        tiles={data.tiles}
        hasPrev={data.hasPrev}
        extra={data.extraTiles}
        lead={mode === 'diet' ? 2 : 1}
      />

      {/* One container for every ring — two on Diet, one on Paisa. */}
      <div style={{ marginTop: 20 }}>
        <div style={sectionTitle}>{data.chartsTitle}</div>
        <div
          style={{
            background: color.white,
            border: `1px solid ${color.line}`,
            borderRadius: radius.card,
            padding: 16,
            display: 'flex',
            flexDirection: 'column',
            gap: 18,
          }}
        >
          {mode === 'kaam' ? (
            <div style={{ display: 'flex', justifyContent: 'center', padding: '4px 0' }}>
              <div style={{ maxWidth: 200, width: '100%' }}>
                <ProjectChart projects={projectStats(todos, 'sab')} />
              </div>
            </div>
          ) : data.rings ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <RingLegend rings={data.rings} />
              </div>
              <div style={{ flex: '0 0 44%', maxWidth: 140 }}>
                <ConcentricRings rings={data.rings} />
              </div>
            </div>
          ) : (
            data.charts.map((chart) =>
              chart.rows.length ? (
                <DonutChart
                  key={chart.key}
                  rows={chart.rows}
                  // Only the category ring answers to the tab strip.
                  selected={chart.key === 'cat' ? focus : null}
                  totalStr={chart.totalStr}
                  centreSub={chart.centreSub}
                  fill={chart.fill}
                />
              ) : (
                <div key={chart.key} style={{ fontSize: 13.5, color: color.muted }}>
                  Nothing in this period.
                </div>
              ),
            )
          )}
        </div>
      </div>

      {/* One strip, scrolling left to right inside the content width — it
          lines up with the cards rather than bleeding to the screen edge.
          Paisa lists categories, Diet lists meals, habits and sleep. The
          one you are on is a selection, so it takes the brand. */}
      <div className="strip-x" style={{ marginTop: 16 }}>
        {tabs.map((t) => {
          const on = active === t;
          return (
            <button
              key={t}
              type="button"
              aria-pressed={on}
              onClick={() => onTab(t)}
              style={{
                flex: '0 0 auto',
                background: on ? color.brand : color.chip,
                border: `1px solid ${on ? color.brand : color.chipBorder}`,
                borderRadius: radius.pill,
                padding: '7px 14px',
                cursor: 'pointer',
                fontFamily: font.sans,
                fontSize: 13,
                fontWeight: 500,
                lineHeight: '16px',
                color: on ? color.white : color.ink,
                whiteSpace: 'nowrap',
                transition: 'background 0.18s, border-color 0.18s, color 0.18s',
              }}
            >
              {TAB_LABELS[t] ?? t}
            </button>
          );
        })}
      </div>

      <div style={{ marginTop: 12 }}>
        {active === COMMITS_TAB ? (
          <CommitsPanel
            page={commitmentsPage}
            handlers={commitmentHandlers}
            onAdd={onAddCommitment}
            notThisMonth={range !== 'mahina'}
          />
        ) : (
          <ItemList items={items} onEdit={onEdit} onDelete={onDelete} />
        )}
        {(active === LENT_TAB || active === BORROWED_TAB) && (
          <AddOpenRow leg={active === LENT_TAB ? 'lent' : 'borrowed'} onAdd={onAddOpen} />
        )}
      </div>


      <div style={{ height: 18 }} />
    </div>
  );
});

/**
 * The Commits tab: this month's commitments, not the range's — they are
 * monthly, so the list ignores the range and says so when it is not the month.
 */
function CommitsPanel({
  page,
  handlers,
  onAdd,
  notThisMonth,
}: {
  page: CommitmentsPage | null;
  handlers: LineHandlers;
  onAdd: () => void;
  notThisMonth: boolean;
}) {
  const own = page?.items.filter((c) => c.source === 'commitment') ?? [];
  const note = { fontFamily: font.sans, fontSize: 12, lineHeight: '16px', color: color.faint } as const;
  return (
    <>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginBottom: 8 }}>
        <span style={sectionTitle}>Commitments</span>
        <span style={note}>{own.length}</span>
      </div>
      {notThisMonth && <div style={{ ...note, marginBottom: 8 }}>Shows this month, whatever range is picked.</div>}
      <div style={{ background: color.white, border: `1px solid ${color.line}`, borderRadius: radius.card, padding: '12px 14px' }}>
        {!page ? (
          <span style={note}>Loading…</span>
        ) : own.length === 0 ? (
          <span style={{ fontFamily: font.sans, fontSize: 13.5, color: color.muted }}>No commitments yet</span>
        ) : (
          <>
            <div style={{ fontFamily: font.sans, fontSize: 13, color: color.muted, fontFeatureSettings: "'tnum'" }}>
              <span style={{ fontWeight: 600, color: color.ink }}>{inr(page.owedPaise)} owed</span>
              {page.openCount > 0 && ` · ${page.paidCount} of ${page.openCount} paid`}
            </div>
            <div style={{ marginTop: 8 }}>
              <CommitmentLines items={own} editable={page.editable} handlers={handlers} compact />
            </div>
          </>
        )}
      </div>
      {page?.editable && (
        <button
          type="button"
          onClick={onAdd}
          className="hov-chip"
          style={{
            marginTop: 10,
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            fontFamily: font.sans,
            fontSize: 13.5,
            fontWeight: 500,
            padding: '8px 14px',
            borderRadius: radius.pill,
            border: `1px solid ${color.border}`,
            background: color.white,
            color: color.brand,
            cursor: 'pointer',
          }}
        >
          <Plus size={15} weight="bold" aria-hidden />
          Add commitment
        </button>
      )}
    </>
  );
}
