import { useEffect, useState } from 'react';
import { CaretLeft, CaretRight, Plus } from '@phosphor-icons/react';
import { color, font, radius } from '../../theme';
import { monthLabel } from '../../lib/format';
import { fetchCommitments, type CommitmentsPage } from '../../data/api';
import CommitmentLines, { type LineHandlers } from './CommitmentLines';
import { inr } from './kit';

interface Props {
  /** The current month, live from state. Null until the first read lands. */
  page: CommitmentsPage | null;
  onAdd: () => void;
  handlers: LineHandlers;
}

/** The first of the month before `iso` (an ISO first of a month). */
function prevMonth(iso: string): string {
  const [y, m] = iso.split('-').map(Number);
  return m === 1 ? `${y - 1}-12-01` : `${y}-${String(m - 1).padStart(2, '0')}-01`;
}
function nextMonth(iso: string): string {
  const [y, m] = iso.split('-').map(Number);
  return m === 12 ? `${y + 1}-01-01` : `${y}-${String(m + 1).padStart(2, '0')}-01`;
}

/** Back as far as this many months: past months are read-only and the server keeps them, but nobody is asking for 2019. */
const MONTHS_BACK = 12;

const chip = (ink: string) => ({ fontFamily: font.sans, fontSize: 13, lineHeight: '18px', color: ink }) as const;

/**
 * Your data → Commitments. What is owed this month, line by line, and the sum
 * that turns it into a limit: *₹61,421 owed · ₹8,215 free · limit —*, so a
 * zero is never a mystery. The current month is live from state; ‹ › opens an
 * earlier month as it was recorded, read-only.
 */
export default function CommitmentsSection({ page: current, onAdd, handlers }: Props) {
  // Which month is showing, as an ISO first of the month; null is the current one.
  const [month, setMonth] = useState<string | null>(null);
  const [past, setPast] = useState<CommitmentsPage | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!month) return;
    let live = true;
    setPast(null);
    setFailed(false);
    fetchCommitments(month).then(
      (p) => live && setPast(p),
      () => live && setFailed(true),
    );
    return () => {
      live = false;
    };
  }, [month]);

  const viewingPast = month != null;
  const page = viewingPast ? past : current;
  const shown = viewingPast ? month : current?.month;

  const go = (dir: -1 | 1) => {
    if (!current || !shown) return;
    const to = dir < 0 ? prevMonth(shown) : nextMonth(shown);
    if (to >= current.month) setMonth(null);
    else setMonth(to);
  };
  const floor = (() => {
    if (!current) return '';
    let m = current.month;
    for (let i = 0; i < MONTHS_BACK; i++) m = prevMonth(m);
    return m;
  })();

  const nav = (
    <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 10 }}>
      <button
        type="button"
        aria-label="Earlier month"
        disabled={!shown || shown <= floor}
        onClick={() => go(-1)}
        className="hov-tint"
        style={navBtn(!shown || shown <= floor)}
      >
        <CaretLeft size={16} aria-hidden />
      </button>
      <span style={{ ...chip(color.ink), fontWeight: 500, minWidth: 84, textAlign: 'center' }}>
        {shown ? monthLabel(shown) : '—'}
      </span>
      <button
        type="button"
        aria-label="Later month"
        disabled={!viewingPast}
        onClick={() => go(1)}
        className="hov-tint"
        style={navBtn(!viewingPast)}
      >
        <CaretRight size={16} aria-hidden />
      </button>
    </div>
  );

  if (!page) {
    return (
      <>
        {nav}
        <div style={{ ...chip(color.faint), padding: '12px 0' }}>
          {failed ? 'It did not load. Is the server up?' : 'Loading…'}
        </div>
      </>
    );
  }

  const own = page.items.filter((c) => c.source === 'commitment');
  const free = page.poolPaise - page.owedPaise;
  const limit = page.limitPaise;
  const none = own.length === 0;

  return (
    <>
      {nav}
      <div
        style={{
          background: color.white,
          border: `1px solid ${color.line}`,
          borderRadius: radius.card,
          padding: '12px 14px',
        }}
      >
        {/* The chain from the pool to the limit, in one place. Unknown is a
            dash, never ₹0; past the line is red with its minus. */}
        <div
          data-chain
          style={{ ...chip(color.muted), fontFeatureSettings: "'tnum'", display: 'flex', gap: 6, flexWrap: 'wrap' }}
        >
          <span style={{ fontWeight: 600, color: color.ink }}>{inr(page.owedPaise)} owed</span>
          <span aria-hidden="true">·</span>
          <span style={{ color: free < 0 ? color.red : color.muted }}>{inr(free)} free</span>
          <span aria-hidden="true">·</span>
          <span style={{ color: limit != null && limit < 0 ? color.red : color.muted }}>
            limit {limit == null ? '—' : inr(limit)}
          </span>
        </div>
        {page.openCount > 0 && (
          <div style={{ ...chip(color.faint), fontSize: 12, marginTop: 3 }}>
            {page.paidCount} of {page.openCount} paid
          </div>
        )}

        {none && (
          <div style={{ ...chip(color.muted), padding: '16px 0 4px' }}>No commitments yet</div>
        )}
        {page.items.length > 0 && (
          <div style={{ marginTop: none ? 6 : 10 }}>
            <CommitmentLines items={page.items} editable={page.editable} handlers={handlers} />
          </div>
        )}
      </div>

      {page.editable && (
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
            lineHeight: '18px',
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
      {!page.editable && (
        <div style={{ ...chip(color.faint), fontSize: 12, marginTop: 10 }}>
          {monthLabel(page.month)} as it was recorded. Past months are read-only.
        </div>
      )}
      <div style={{ height: 18 }} />
    </>
  );
}

const navBtn = (off: boolean) =>
  ({
    width: 28,
    height: 28,
    borderRadius: '50%',
    background: 'none',
    border: 'none',
    cursor: off ? 'default' : 'pointer',
    opacity: off ? 0.35 : 1,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 0,
    color: color.muted,
  }) as const;

