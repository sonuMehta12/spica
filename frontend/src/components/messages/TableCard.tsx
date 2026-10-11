import { useEffect, type ReactNode } from 'react';
import { dayLabel, rupees } from '../../lib/format';
import { color, font } from '../../theme';
import { agentCard } from './bubble';
import { UDHAAR, grams } from './confirmKit';
import { Bar, Fig, Lead, LeadWord } from './parts';
import Dot from './Dot';
import { TrayActions, TrayToggle, type TrayAction } from './Tray';
import PaymentTray, { type LinkHandlers } from '../commitments/PaymentTray';
import type { CommitmentRow } from '../../data/api';
import type { Meal, TableMsg, Tx } from '../../types';

interface Row {
  id: string;
  dateStr: string;
  name: string;
  /** The line under the name — category, or slot and kcal. */
  sub: string;
  /** The figure, as printed: "₹20", "+₹40,000", "18 g", "—". */
  figure: string;
  /** Money in is Paisa's ink; every other figure is ink. Red never means spent. */
  figureTone: string;
  /** What "Edit" drops back into the composer. */
  editText: string;
  /** The payment itself, for the commitment actions. Paisa rows only. */
  tx?: Tx;
  /** The commitment it counts toward, by name — `· Rent`. Null when linked to one not on this month's page. */
  commitment?: { name: string | null; inferred: boolean };
  /** Known to be gone: struck, "Removed", no tray. */
  struck?: boolean;
  /** A meal logged with nothing in it — the name greyed, "nothing recorded". */
  empty?: boolean;
}

interface Props {
  msg: TableMsg;
  tx: Tx[];
  meals: Meal[];
  /** Ids deleted this session — a delete card, an Undo, a ⋮ Delete. Struck here too. */
  deletedRows: string[];
  /** The day's protein target, for the diet table's lead. Null when unset. */
  proteinTarget: number | null;
  openRow: string | null;
  onToggleRow: (id: string) => void;
  onDelete: (source: 'paisa' | 'diet', id: string) => void;
  onEdit: (source: 'paisa' | 'diet', id: string, text: string) => void;
  /** This month's commitments: what a payment counts toward, and what its line names. */
  commitments: CommitmentRow[];
  /** Paisa rows: count toward a commitment, not, or make one of it. */
  link: LinkHandlers;
  /** Ids the client does not hold — fetched live, deleted ones included. */
  onNeedRows?: (source: 'paisa' | 'diet', ids: string[]) => void;
}

const status = (r: { failed?: boolean; pending?: boolean }) => (r.failed ? 'unsaved' : r.pending ? 'saving' : null);
const join = (...xs: (string | null | undefined | false)[]) => xs.filter(Boolean).join(' · ');

/**
 * Resolves the message's stored row ids against live ledger data, so a row
 * deleted here is struck in every other table on screen too.
 */
function resolve(
  msg: TableMsg,
  tx: Tx[],
  meals: Meal[],
  deleted: Set<string>,
  commitments: CommitmentRow[],
): Row[] {
  if (msg.source === 'paisa') {
    const byId = new Map(tx.map((t) => [t.id, t]));
    return msg.ids
      .map((id) => byId.get(id))
      .filter((t): t is Tx => Boolean(t))
      .map((t) => ({
        id: t.id,
        dateStr: dayLabel(t),
        name: t.name,
        // A lending, a borrowing or a repayment says what it is, not a
        // category: it was never a guess.
        sub: join((t.kind && UDHAAR[t.kind]) || t.cat, status(t)),
        // A credit ARRIVED: "+", in Paisa's ink. A spend is a plain figure —
        // it was red, and spending is not an error.
        figure: `${t.credit ? '+' : ''}${rupees(t.amt)}`,
        figureTone: t.credit ? color.paisaInk : color.ink,
        editText: `${t.name} ${t.amt}`,
        tx: t,
        commitment: t.commitmentId
          ? { name: commitments.find((c) => c.id === t.commitmentId)?.name ?? null, inferred: Boolean(t.commitmentInferred) }
          : undefined,
        struck: Boolean(t.deleted) || deleted.has(t.id),
      }));
  }
  const byId = new Map(meals.map((m) => [m.id, m]));
  return msg.ids
    .map((id) => byId.get(id))
    .filter((m): m is Meal => Boolean(m))
    .map((m) => {
      // Nothing known: a slot logged with no food in it ("breakfast") is a
      // gap to fill, and a dish with no nutrition on file is unknown — a 0 g
      // meal is neither.
      const blank = m.p === 0 && m.k === 0;
      const empty = blank && (!m.name.trim() || m.name.trim().toLowerCase() === (m.type ?? '').trim().toLowerCase());
      return {
        id: m.id,
        dateStr: dayLabel(m),
        name: m.name,
        sub: empty
          ? 'nothing recorded'
          : join(m.type, blank ? 'macros unknown' : `${m.k.toLocaleString('en-IN')} kcal`, status(m)),
        figure: blank ? '—' : `${grams(m.p)} g`,
        figureTone: color.ink,
        editText: m.name,
        struck: Boolean(m.deleted) || deleted.has(m.id),
        empty,
      };
    });
}

/**
 * A ledger table, as the agent answered with it. The number the rows add up to
 * leads; the rows keep their anatomy — date, name with its category, the
 * figure, ⋮. No note under it: the agent's reply above is the commentary, and
 * two sentences would say the same thing (spec/done/card-redesign.md).
 */
export default function TableCard({
  msg,
  tx,
  meals,
  deletedRows,
  proteinTarget,
  openRow,
  onToggleRow,
  onDelete,
  onEdit,
  commitments,
  link,
  onNeedRows,
}: Props) {
  const deleted = new Set(deletedRows);
  const rows = resolve(msg, tx, meals, deleted, commitments);
  const targets = commitments.filter((c) => c.source === 'commitment' && !c.skipped);
  // A struck row is history: it stays on the card but in none of its sums.
  const counts = (r: { id: string; deleted?: boolean }) => msg.ids.includes(r.id) && !r.deleted && !deleted.has(r.id);

  // The deck is one window; a card can name a row from before it. Ask for
  // what is missing once — the hook remembers what it already asked for.
  const held = new Set(rows.map((r) => r.id));
  const missing = msg.ids.filter((id) => !held.has(id));
  const missingKey = missing.join(',');
  useEffect(() => {
    if (missingKey && onNeedRows) onNeedRows(msg.source, missingKey.split(','));
  }, [missingKey, msg.source, onNeedRows]);

  const loading = missing.length > 0;
  let lead: ReactNode = null;
  let rule = true;
  if (msg.source === 'paisa') {
    const live = tx.filter(counts);
    // A loan is neither spending nor income: lent, borrowed and repaid rows
    // stay on the card, named for what they are, but out of its sums — a
    // ₹4,000 lending was read as ₹4,000 spent.
    const money = live.filter((t) => !(t.kind && UDHAAR[t.kind]));
    const spends = money.filter((t) => !t.credit);
    const came = money.filter((t) => t.credit);
    const spent = spends.reduce((s, t) => s + t.amt, 0);
    const cameIn = came.reduce((s, t) => s + t.amt, 0);
    const n = (c: number, one: string) => `${c} ${c === 1 ? one : `${one}s`}`;
    if (spends.length) {
      lead = (
        <Lead>
          <Fig size={26}>{rupees(spent)}</Fig>
          <LeadWord>spent · {n(spends.length, 'payment')}{cameIn ? ` · +${rupees(cameIn)} in` : ''}</LeadWord>
        </Lead>
      );
    } else if (came.length) {
      lead = (
        <Lead>
          <Fig size={26} tone={color.paisaInk}>+{rupees(cameIn)}</Fig>
          <LeadWord>came in · {n(came.length, 'payment')}</LeadWord>
        </Lead>
      );
    } else if (!loading && !live.length) {
      // Nothing left in it: the caption says so, and no divider is drawn.
      lead = <LeadWord>no payments yet</LeadWord>;
      rule = false;
    }
    // Only loans left: no lead at all. The rows say what each one is, and
    // "no payments yet" over rows that are there would be false.
  } else {
    const live = meals.filter(counts);
    const p = live.reduce((s, m) => s + m.p, 0);
    const k = live.reduce((s, m) => s + m.k, 0);
    // A daily target only means something against one day's meals.
    const oneDay = new Set(live.map((m) => m.date ?? String(m.day))).size === 1;
    if (live.length) {
      lead = (
        <>
          <Lead>
            <Fig size={26}>{grams(p)} g</Fig>
            <LeadWord>
              {oneDay && proteinTarget ? `of ${proteinTarget} g protein` : `protein · ${live.length} ${live.length === 1 ? 'meal' : 'meals'}`}
            </LeadWord>
            <span style={{ flex: 1 }} />
            <Fig size={13} tone={color.faint}>{k.toLocaleString('en-IN')} kcal</Fig>
          </Lead>
          {oneDay && proteinTarget ? (
            <div style={{ marginTop: 10 }}>
              <Bar pct={p / proteinTarget} tone={color.diet} />
            </div>
          ) : null}
        </>
      );
    } else if (!loading) {
      lead = <LeadWord>no meals yet</LeadWord>;
      rule = false;
    }
  }

  return (
    <div style={agentCard('12px 14px 6px')}>
      {lead}
      {lead && rule && rows.length > 0 && <div style={{ height: 1, background: color.line, marginTop: 12 }} />}
      {rows.map((r, i) => {
        const open = openRow === r.id;
        const actions: TrayAction[] = [];
        actions.push({ label: 'Edit', onClick: () => onEdit(msg.source, r.id, r.editText) });
        actions.push({ label: 'Delete', tone: 'danger', onClick: () => onDelete(msg.source, r.id) });
        return (
          <div key={r.id} style={{ borderTop: i === 0 ? undefined : `1px solid ${color.lineSoft}` }}>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', padding: '8px 0' }}>
              <div style={{ flex: '0 0 44px', fontFamily: font.sans, fontSize: 11.5, lineHeight: '15px', color: color.muted }}>
                {r.dateStr}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div
                  style={{
                    fontFamily: font.sans,
                    fontSize: 14,
                    lineHeight: '19px',
                    fontWeight: 500,
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    textDecoration: r.struck ? 'line-through' : undefined,
                    color: r.struck || r.empty ? color.faint : color.ink,
                  }}
                >
                  {r.name}
                </div>
                <div
                  style={{
                    fontFamily: font.sans,
                    fontSize: 11.5,
                    lineHeight: '15px',
                    color: color.faint,
                    marginTop: 1,
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}
                >
                  {r.struck ? 'Removed' : r.sub}
                  {/* Which commitment it counts toward; amber when that was only a guess. */}
                  {!r.struck && r.commitment && (
                    <>
                      {' · '}
                      {r.commitment.inferred && <Dot />}
                      {r.commitment.name ?? 'Commitment'}
                    </>
                  )}
                </div>
              </div>
              <Fig size={14} weight={600} tone={r.figureTone} struck={r.struck}>
                {r.figure}
              </Fig>
              {r.struck ? (
                <div style={{ width: 28, flex: '0 0 auto' }} />
              ) : (
                <TrayToggle open={open} onToggle={() => onToggleRow(r.id)} label={r.name} />
              )}
            </div>
            {open && !r.struck && (r.tx ? (
              <PaymentTray tx={r.tx} targets={targets} handlers={link} rest={actions} />
            ) : (
              <TrayActions actions={actions} pad="0 0 9px" />
            ))}
          </div>
        );
      })}
      {loading && (
        <div style={{ fontFamily: font.sans, fontSize: 11.5, color: color.faint, padding: '6px 0' }}>
          {rows.length === 0 ? 'Loading rows…' : `${missing.length} more loading…`}
        </div>
      )}
    </div>
  );
}
