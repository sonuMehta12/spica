import { CalendarCheck } from '@phosphor-icons/react';
import { color, font } from '../../theme';
import { inr, ordinal } from '../commitments/kit';
import { agentCard } from './bubble';
import { field, val, type ConfirmActions, type ConfirmData } from './confirmKit';
import Dot from './Dot';
import { Coin, Fig, Quiet, Receipt, Section, TextBtn, cap, clamp, metaLine } from './parts';
import type { ConfirmMsg } from '../../types';

const coin = <Coin icon={CalendarCheck} tint={color.paisaTint} ink={color.paisaInk} />;
const goneCoin = <Coin icon={CalendarCheck} tint={color.lineSoft} ink={color.grey} />;

/**
 * A commitment made, changed, skipped, counted or deleted. Read from the live
 * line first — an edit anywhere shows here — and from the payload only for
 * what the line cannot say. A deleted one is a struck line with no tray: a
 * delete has no undo. Change hangs the commitment on the composer as a pill.
 */
export function CommitmentCard({ msg, data, a }: { msg: ConfirmMsg; data: ConfirmData; a: ConfirmActions }) {
  const live = msg.rowId ? data.rows.commitments?.items.find((c) => c.id === msg.rowId) : undefined;
  const name = live?.name ?? val(msg, 'name') ?? msg.lede.split(' · ')[0];

  if (msg.state === 'deleted') {
    return (
      <div style={agentCard('12px 14px')}>
        <Receipt coin={goneCoin} what={name} struck meta={metaLine('Removed', val(msg, 'payments'))} />
      </div>
    );
  }
  const category = live?.category ?? val(msg, 'category') ?? '';
  const amount = live ? inr(live.expectedPaise) : (val(msg, 'amount_paise') ?? '');
  const due = live ? (live.dueDay != null ? `due ${ordinal(live.dueDay)}` : null) : (val(msg, 'due_day') ?? null);
  const repeats = live ? (live.repeats ? 'every month' : 'this month only') : val(msg, 'repeats');
  // The dot is on the payload's guess; once the line's own category differs
  // from it, someone changed it, and it is a statement now.
  const guessed = Boolean(field(msg, 'category')?.guessed) && (!live || live.category === val(msg, 'category'));
  const change = () =>
    a.onContext({ label: `Commitment · ${name}`, prefix: `About my ${name} commitment —` });

  return (
    <div style={agentCard('12px 14px')}>
      <Receipt
        coin={coin}
        what={name}
        meta={metaLine(
          live?.skipped ? 'Skipped this month' : null,
          guessed ? null : category,
          due,
          repeats,
        )}
        figure={amount ? <Fig struck={live?.skipped}>{amount}</Fig> : undefined}
      />
      {guessed ? (
        <Section>
          <span style={{ flex: 1, minWidth: 0, display: 'flex', alignItems: 'center' }}>
            <Dot />
            <span style={{ fontFamily: font.sans, fontSize: 13, lineHeight: '18px', color: color.muted, ...clamp(2) }}>
              {cap(category)}, I guessed
            </span>
          </span>
          <TextBtn label="Change" onClick={change} />
        </Section>
      ) : (
        <Quiet>
          <TextBtn label="Change" onClick={change} />
        </Quiet>
      )}
    </div>
  );
}
