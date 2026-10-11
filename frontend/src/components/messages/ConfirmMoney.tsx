import { useState, type ReactNode } from 'react';
import { ArrowCounterClockwise, CurrencyInr } from '@phosphor-icons/react';
import { LENT_MONTH, PAID_BACK_MONTH, SALARY, TODAY_ISO } from '../../data/live';
import { rupees, shortDate } from '../../lib/format';
import { color, font } from '../../theme';
import { agentCard } from './bubble';
import {
  UDHAAR,
  categoryContext,
  field,
  ledeTitle,
  initial,
  reviewContext,
  val,
  type ConfirmActions,
  type ConfirmData,
} from './confirmKit';
import Dot from './Dot';
import { PaymentLinkQuiet } from '../commitments/PaymentTray';
import { linkTargets } from '../commitments/kit';
import { certain } from './live';
import {
  Chip,
  Coin,
  FactLine,
  Fig,
  GuessLine,
  PillBtn,
  PrimaryBtn,
  Quiet,
  Receipt,
  Section,
  TextBtn,
  cap,
  metaLine,
} from './parts';
import type { ComposerContext, ConfirmMsg, Tx } from '../../types';

const paisaCoin = <Coin icon={CurrencyInr} tint={color.paisaTint} ink={color.paisaInk} />;
const goneCoin = <Coin icon={CurrencyInr} tint={color.lineSoft} ink={color.grey} />;

/**
 * A row that is gone keeps its line, struck and faint. A payment or a meal
 * has a restore route, so it offers a quiet Undo; the rest have none, and
 * offer nothing.
 */
export function Removed({
  coin = goneCoin,
  what,
  day,
  figure,
  onUndo,
}: {
  coin?: ReactNode;
  what: string;
  day?: string | null;
  figure?: string;
  onUndo?: () => void;
}) {
  return (
    <div style={agentCard('12px 14px')}>
      <Receipt
        coin={coin}
        what={what}
        struck
        meta={metaLine('Removed', day ? shortDate(day) : null)}
        figure={figure ? <Fig struck>{figure}</Fig> : undefined}
      />
      {onUndo && (
        <Quiet>
          <TextBtn label="Undo" icon={ArrowCounterClockwise} onClick={onUndo} />
        </Quiet>
      )}
    </div>
  );
}

/**
 * A payment, as one receipt line read from the live row: what, its category
 * and day, the amount. The row decides which kind of line it is — money in,
 * a lending still out, a borrowing still owed, or a spend — because the
 * payload cannot: it carries no direction.
 */
export function PaymentCard({ msg, data, a }: { msg: ConfirmMsg; data: ConfirmData; a: ConfirmActions }) {
  const { live, rows, deckTx } = data;
  const t: Tx | undefined = live.tx;
  const id = msg.rowId;
  const what = t?.name ?? val(msg, 'description') ?? ledeTitle(msg.lede).split(' · ').slice(1).join(' · ');
  const amount = t ? rupees(t.amt) : (val(msg, 'amount_paise') ?? '');
  const category = t?.cat ?? val(msg, 'category') ?? '';
  const day = t?.date ?? val(msg, 'local_day') ?? null;
  const dayStr = day ? shortDate(day) : null;

  if (live.deleted) {
    return <Removed what={what} day={day} figure={amount} onUndo={id ? () => a.onRestore('paisa', id) : undefined} />;
  }

  // Udhaar is read from the pending lists, never from the category: "Logon
  // ko diya" is a gift as often as a loan, and calling a gift "comes back"
  // inflates money you think is coming (spec/done/paisa-import.md).
  const lent = id ? rows.pending.find((p) => p.id === id) : undefined;
  const owed = id ? rows.borrowed.find((p) => p.id === id) : undefined;
  // A repayment names its loan's own leg, so a loan settled in full — gone
  // from the pending lists — is still known for what it was.
  const back = id ? rows.repayments.filter((r) => r.lendingId === id && r.leg === 'lent') : [];
  const paidBack = id ? rows.repayments.filter((r) => r.lendingId === id && r.leg === 'borrowed') : [];
  // A lending, a borrowing or a repayment is never asked a category: what it
  // is was said, not guessed, whatever confidence an older row carries.
  const udhaar =
    Boolean(t?.kind && UDHAAR[t.kind]) ||
    Boolean(lent || owed || back.length || paidBack.length) ||
    (id != null && rows.repayments.some((r) => r.id === id));

  // A guess stays dotted until the row itself says it is certain.
  const guessed = !udhaar && Boolean(field(msg, 'category')?.guessed) && !certain(t);
  const guess = guessed && id && (
    <GuessLine
      text={`${cap(category)}, I guessed`}
      onRight={() => a.onConfirm(msg)}
      onChange={() => a.onContext(categoryContext(what, amount, day))}
    />
  );
  const undo = (
    <TextBtn label="Undo" icon={ArrowCounterClockwise} onClick={() => a.onDelete(msg)} />
  );

  if (lent || back.length) {
    const backSum = back.reduce((s, r) => s + r.amount, 0);
    return (
      <div style={agentCard('12px 14px')}>
        <Receipt
          coin={<Coin tint={color.paisaTint} ink={color.paisaInk}>{initial(what)}</Coin>}
          what={what}
          meta={metaLine('Lent', lent ? 'comes back' : 'paid back', dayStr)}
          figure={<Fig>{amount}</Fig>}
        />
        {guess}
        {lent ? (
          <FactLine label="Still out" value={rupees(lent.remaining)} tone={color.ink} />
        ) : (
          <FactLine label="Came back" value={rupees(backSum)} />
        )}
        {/* A lending with a repayment against it cannot be deleted — the
            server refuses — so it offers no Undo. */}
        {id && !back.length && <Quiet>{undo}</Quiet>}
      </div>
    );
  }

  if (owed || paidBack.length) {
    return (
      <div style={agentCard('12px 14px')}>
        <Receipt
          coin={paisaCoin}
          what={what}
          meta={metaLine('Borrowed', owed ? 'goes back' : 'paid back', dayStr)}
          figure={<Fig tone={color.paisaInk}>+{amount}</Fig>}
        />
        {guess}
        {owed ? (
          <FactLine label="Still owed" value={rupees(owed.remaining)} tone={color.ink} />
        ) : (
          <FactLine label="Paid back" value={rupees(paidBack.reduce((s, r) => s + r.amount, 0))} />
        )}
        {id && !paidBack.length && <Quiet>{undo}</Quiet>}
      </div>
    );
  }

  if (t?.credit) {
    // The month's own figures — what came in and what went out, as the pool
    // counts them — only for a row in this month; any other month's rows
    // are not held.
    const thisMonth = day != null && day.slice(0, 7) === TODAY_ISO.slice(0, 7);
    const out = deckTx.reduce((s, x) => s + x.amt, 0) + LENT_MONTH + PAID_BACK_MONTH;
    return (
      <div style={agentCard('12px 14px')}>
        <Receipt
          coin={paisaCoin}
          what={what}
          meta={metaLine('Came in', dayStr)}
          figure={<Fig tone={color.paisaInk}>+{amount}</Fig>}
        />
        {guess}
        {thisMonth && <FactLine label="This month" value={`${rupees(SALARY)} in · ${rupees(out)} out`} />}
        {id && <Quiet>{undo}</Quiet>}
      </div>
    );
  }

  // Counting toward a commitment only works on a row the deck holds — this
  // month's spending.
  const held = id ? deckTx.find((x) => x.id === id) : undefined;
  return (
    <div style={agentCard('12px 14px')}>
      <Receipt
        coin={paisaCoin}
        what={what}
        // A guessed category is asked below rather than stated twice.
        meta={metaLine(guessed ? null : category, dayStr)}
        figure={<Fig>{amount}</Fig>}
      />
      {guess}
      {id &&
        (held ? (
          <PaymentLinkQuiet tx={held} targets={linkTargets(rows.commitments)} handlers={{ onLink: a.onLink, onMake: a.onMake }}>
            {undo}
          </PaymentLinkQuiet>
        ) : (
          <Quiet>{undo}</Quiet>
        ))}
    </div>
  );
}

/** "₹40,000 · Ghar par diya (Papa ko) · 80% sure" → amount and payee, the made-up percentage dropped. */
function splitLede(lede: string): { amount: string; payee: string } {
  const parts = lede.split(' · ');
  return {
    amount: parts[0] ?? '',
    payee: parts.slice(1).filter((p) => !/^\d+% sure$/.test(p.trim())).join(' · '),
  };
}

/**
 * The nightly second look's questions, one at a time. Proposals in one turn
 * stack into one card, "1 of N", with Skip — fourteen identical forms down
 * the thread read as a wall. A question is settled when its row says so
 * (confidence 1, or deleted), so an answer given anywhere clears it here.
 */
export function ProposalStack({
  msgs,
  tx,
  deletedRows,
  onConfirm,
  onContext,
  onRestore,
}: {
  msgs: ConfirmMsg[];
  tx: Tx[];
  deletedRows: string[];
  onConfirm: (msg: ConfirmMsg) => void;
  onContext: (ctx: ComposerContext) => void;
  onRestore: (source: 'paisa' | 'diet', id: string) => void;
}) {
  const [skipped, setSkipped] = useState<string[]>([]);
  const rowOf = (m: ConfirmMsg) => (m.rowId ? tx.find((x) => x.id === m.rowId) : undefined);
  const gone = (m: ConfirmMsg) => (m.rowId != null && deletedRows.includes(m.rowId)) || Boolean(rowOf(m)?.deleted);
  const settled = (m: ConfirmMsg) => gone(m) || certain(rowOf(m));
  const open = msgs.filter((m) => !settled(m));
  const current = open.find((m) => !skipped.includes(m.id)) ?? open[0];

  if (!current) {
    // Every question answered: the last one as the receipt it became.
    const last = msgs[msgs.length - 1];
    const t = rowOf(last);
    const { amount, payee } = splitLede(last.lede);
    const day = t?.date ?? val(last, 'local_day');
    const id = last.rowId;
    return (
      <div>
        {gone(last) ? (
          <Removed
            what={t?.name ?? payee}
            day={day}
            figure={t ? rupees(t.amt) : amount}
            onUndo={id ? () => onRestore('paisa', id) : undefined}
          />
        ) : (
          <div style={agentCard('12px 14px')}>
            <Receipt
              coin={paisaCoin}
              what={t?.name ?? payee}
              meta={metaLine(t?.cat ?? val(last, 'category'), day ? shortDate(day) : null)}
              figure={<Fig tone={t?.credit ? color.paisaInk : color.ink}>{t?.credit ? '+' : ''}{t ? rupees(t.amt) : amount}</Fig>}
            />
          </div>
        )}
        {msgs.length > 1 && <StackFoot>All {msgs.length} answered</StackFoot>}
      </div>
    );
  }

  const t = rowOf(current);
  const { amount, payee } = splitLede(current.lede);
  const guess = val(current, 'category') ?? '';
  const renamed = field(current, 'description')?.guessed ? val(current, 'description') : undefined;
  const why = val(current, 'why');
  const reasons = why ? why.split(';').map((s) => s.trim()).filter(Boolean) : [];
  const day = t?.date ?? val(current, 'local_day');
  const pos = msgs.indexOf(current) + 1;

  const skip = () => {
    // Round and round: once every open question has been skipped, the
    // first one comes back rather than the card going blank.
    const rest = open.filter((m) => m.id !== current.id && !skipped.includes(m.id));
    setSkipped(rest.length ? [...skipped, current.id] : [current.id]);
  };

  return (
    <div>
      <div style={agentCard('12px 14px')}>
        <Receipt
          coin={paisaCoin}
          what={t?.name ?? payee}
          meta={day ? shortDate(day) : null}
          figure={<Fig tone={t?.credit ? color.paisaInk : color.ink}>{t?.credit ? '+' : ''}{t ? rupees(t.amt) : amount}</Fig>}
        />
        <Section style={{ flexDirection: 'column', alignItems: 'stretch', gap: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center' }}>
            <Dot />
            <span style={{ fontFamily: font.sans, fontSize: 14, lineHeight: '19px', fontWeight: 500, color: color.ink }}>
              Category?
            </span>
          </div>
          {(reasons.length > 0 || renamed) && (
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 8 }}>
              {renamed && <Chip>as “{renamed}”</Chip>}
              {reasons.map((r) => (
                <Chip key={r}>{r}</Chip>
              ))}
            </div>
          )}
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', marginTop: 12 }}>
            <PrimaryBtn label={`Yes, ${guess}`} onClick={() => onConfirm(current)} />
            <PillBtn
              label="Change"
              onClick={() => onContext(reviewContext(t?.name ?? payee, t ? rupees(t.amt) : amount, day))}
            />
          </div>
        </Section>
      </div>
      {msgs.length > 1 && (
        <StackFoot>
          {pos} of {msgs.length}
          <span aria-hidden="true">·</span>
          <TextBtn label="Skip" size={12.5} tone={color.brand} onClick={skip} />
        </StackFoot>
      )}
    </div>
  );
}

function StackFoot({ children }: { children: ReactNode }) {
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        gap: 6,
        marginTop: 8,
        fontFamily: font.sans,
        fontSize: 12.5,
        lineHeight: '18px',
        color: color.faint,
      }}
    >
      {children}
    </div>
  );
}
