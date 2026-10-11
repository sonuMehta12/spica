import { useState } from 'react';
import { CaretDown, CookingPot } from '@phosphor-icons/react';
import { inUnit, type DishRow, type PantryRow } from '../../data/api';
import { diffDays } from '../../lib/day';
import { color, font } from '../../theme';
import { agentCard } from './bubble';
import { grams } from './confirmKit';
import { AgentLine, Coin, Fig, GroupLabel, Lead, LeadWord, ListRow, clamp, metaLine } from './parts';
import { dishesNote, pantryNote } from '../../agent/notes';
import type { PantryMsg } from '../../types';

/** A name with its small print under it. */
function Name({ name, sub }: { name: string; sub?: string | null }) {
  return (
    <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
      <span style={{ fontFamily: font.sans, fontSize: 14.5, lineHeight: '20px', color: color.ink, ...clamp(1) }}>{name}</span>
      {sub && <span style={{ fontFamily: font.sans, fontSize: 12, lineHeight: '16px', color: color.faint }}>{sub}</span>}
    </div>
  );
}

const days = (n: number) => `${n} ${n === 1 ? 'day' : 'days'}`;

const stock = (r: PantryRow) =>
  r.staple ? 'always' : r.status === 'new' ? 'not counted' : inUnit(r.stockG, r.unit);

/**
 * What is at home, grouped by what to do about it: use soon, running low,
 * and the rest folded. The status is derived every render from the live
 * rows, and so is the agent's line above the card.
 */
function Pantry({ rows, today }: { rows: PantryRow[]; today: string }) {
  const [unfold, setUnfold] = useState(false);
  const note = <AgentLine>{pantryNote(rows, today)}</AgentLine>;
  // Nothing tracked: the line alone, never an empty box under it.
  if (!rows.length) return note;

  // Past its shelf life, oldest first: the one that has sat longest goes first.
  const useSoon = rows
    .filter((r) => r.status === 'stale')
    .sort((a, b) => (a.lastIn ?? '').localeCompare(b.lastIn ?? ''));
  const low = rows.filter((r) => r.status === 'soon' || r.status === 'out');
  const stocked = rows.filter((r) => r.status === 'ok' || r.status === 'staple' || r.status === 'new');
  const inKitchen = rows.filter((r) => r.status !== 'out').length;

  return (
    <div>
      {note}
      <div style={agentCard('12px 14px')}>
        <Lead>
          <Fig size={20}>{inKitchen}</Fig>
          <LeadWord>in the kitchen</LeadWord>
        </Lead>
        {useSoon.length > 0 && (
          <>
            <GroupLabel tone={color.red}>Use soon</GroupLabel>
            {useSoon.map((r, i) => (
              <ListRow key={r.id} first={i === 0} pad="8px 0">
                <Name name={r.name} sub={stock(r)} />
                <Fig size={13.5} tone={color.muted}>
                  {r.lastIn ? days(diffDays(r.lastIn, today)) : '—'}
                </Fig>
              </ListRow>
            ))}
          </>
        )}
        {low.length > 0 && (
          <>
            <GroupLabel tone={color.ink}>Running low</GroupLabel>
            {low.map((r, i) => (
              <ListRow key={r.id} first={i === 0} pad="8px 0">
                <Name name={r.name} />
                <Fig size={13.5} tone={r.status === 'out' ? color.red : color.muted}>
                  {r.status === 'out' ? 'out' : `${inUnit(r.stockG, r.unit)} left`}
                </Fig>
              </ListRow>
            ))}
          </>
        )}
        {stocked.length > 0 && (
          <>
            <button
              type="button"
              aria-expanded={unfold}
              onClick={() => setUnfold((v) => !v)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                width: '100%',
                marginTop: 14,
                padding: 0,
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                fontFamily: font.sans,
                fontSize: 12,
                lineHeight: '16px',
                fontWeight: 500,
                color: color.faint,
                textAlign: 'left',
              }}
            >
              <span style={{ flex: 1 }}>Stocked · {stocked.length}</span>
              <CaretDown
                size={12}
                weight="bold"
                aria-hidden
                style={{ transform: unfold ? 'rotate(180deg)' : undefined, transition: 'transform 0.15s' }}
              />
            </button>
            {unfold &&
              stocked.map((r, i) => (
                <ListRow key={r.id} first={i === 0} pad="8px 0">
                  <Name name={r.name} />
                  <Fig size={13.5} tone={color.muted}>{stock(r)}</Fig>
                </ListRow>
              ))}
          </>
        )}
      </div>
    </div>
  );
}

/** Your dishes — tried or saved — as suggestions draw them. */
function Dishes({ dishes }: { dishes: DishRow[] }) {
  const note = <AgentLine>{dishesNote(dishes)}</AgentLine>;
  if (!dishes.length) return note;
  const tried = dishes.filter((d) => d.tried > 0).length;
  return (
    <div>
      {note}
      <div style={agentCard('4px 14px')}>
        <div style={{ padding: '8px 0 2px' }}>
          <Lead>
            <Fig size={20}>{dishes.length}</Fig>
            <LeadWord>
              {dishes.length === 1 ? 'dish' : 'dishes'} · {tried} eaten
            </LeadWord>
          </Lead>
        </div>
        {dishes.map((d) => (
          <ListRow key={d.id} first={false} pad="9px 0">
            <Coin icon={CookingPot} tint={color.dietTint} ink={color.dietInk} size={32} />
            <Name
              name={d.name}
              sub={metaLine(d.mealType, d.minutes != null && `${d.minutes} min`, d.kcal != null && `${d.kcal} kcal`)}
            />
            <Fig size={14}>{grams(d.proteinG)} g</Fig>
            <span style={{ fontFamily: font.sans, fontSize: 12, lineHeight: '16px', color: d.tried ? color.dietInk : color.faint, width: 40, textAlign: 'right' }}>
              {d.tried > 0 ? `${d.tried}×` : d.saved ? 'saved' : 'new'}
            </span>
          </ListRow>
        ))}
      </div>
    </div>
  );
}

/** Shared by the pantry and recipes cards — which list, read live; nothing stored on the message. */
export default function PantryCard({
  msg,
  pantry,
  dishes,
  today,
}: {
  msg: PantryMsg;
  pantry: PantryRow[];
  dishes: DishRow[];
  today: string;
}) {
  return msg.list === 'dishes' ? <Dishes dishes={dishes} /> : <Pantry rows={pantry} today={today} />;
}
