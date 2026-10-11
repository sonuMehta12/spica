import type { ReactNode } from 'react';
import { ArrowCounterClockwise, BowlFood, CookingPot, Package, PushPin, Scales, X } from '@phosphor-icons/react';
import { DIET_TODAY_ISO } from '../../data/live';
import { inUnit } from '../../data/api';
import { color, font } from '../../theme';
import { agentCard } from './bubble';
import {
  SET_PROTEIN_TARGET,
  field,
  fieldContext,
  grams,
  ledeTitle,
  num,
  proteinContext,
  val,
  type ConfirmActions,
  type ConfirmData,
} from './confirmKit';
import { Removed } from './ConfirmMoney';
import Dot from './Dot';
import { certain } from './live';
import { Bar, Coin, Fig, GuessLine, Quiet, Receipt, Section, Stacked, TextBtn, cap, clamp, dayText, metaLine } from './parts';
import type { ConfirmMsg } from '../../types';

const dietCoin = <Coin icon={BowlFood} tint={color.dietTint} ink={color.dietInk} />;
const goneDietCoin = <Coin icon={BowlFood} tint={color.lineSoft} ink={color.grey} />;

/** One thing the plate held that is not in the total, on its own line. */
function GapLine({ mark, text, right }: { mark: ReactNode; text: string; right?: string }) {
  return (
    <Section>
      <span style={{ width: 16, display: 'inline-flex', justifyContent: 'center', flex: '0 0 auto' }}>{mark}</span>
      <span style={{ flex: 1, minWidth: 0, fontFamily: font.sans, fontSize: 14, lineHeight: '19px', color: color.ink, ...clamp(2) }}>
        {text}
      </span>
      {right && (
        <span style={{ fontFamily: font.sans, fontSize: 12, lineHeight: '16px', color: color.faint, whiteSpace: 'nowrap' }}>
          {right}
        </span>
      )}
    </Section>
  );
}

/**
 * A meal, as one line: the dish, its slot and day, protein over the rest of
 * what it held — kcal, and carbs and fat where the plate's foods know them.
 * The gaps are said once each, on their own lines — an item the agent could
 * not find, one it could not weigh, the portion it assumed — so what counted
 * is readable without decoding a form. Then the day's protein against the
 * target, from the live meals, so an edit or a delete moves it.
 */
export function MealCard({ msg, data, a }: { msg: ConfirmMsg; data: ConfirmData; a: ConfirmActions }) {
  const m = data.live.meal;
  const dish = m?.name ?? val(msg, 'dish') ?? ledeTitle(msg.lede);
  const slot = m?.type ?? val(msg, 'meal_type');
  const day = m?.date ?? val(msg, 'local_day') ?? null;
  const id = msg.rowId;

  if (data.live.deleted) {
    return <Removed coin={goneDietCoin} what={dish} day={day} onUndo={id ? () => a.onRestore('diet', id) : undefined} />;
  }

  // The server says "—" when nothing on the plate had nutrition on file: the
  // stored zero means nobody knows, not no calories. A later correction that
  // put real numbers on the row wins.
  const unknown = field(msg, 'kcal')?.value.trim() === '—' && (!m || (m.k === 0 && m.p === 0));
  const protein = m ? m.p : num(val(msg, 'protein_g'));
  const kcal = m ? m.k : num(val(msg, 'kcal'));
  // Carbs and fat only when known: a meal that never said them shows neither,
  // rather than a 0 g that reads as "none".
  const carbs = m?.c ?? num(val(msg, 'carbs_g'));
  const fat = m?.f ?? num(val(msg, 'fat_g'));
  const rest = [
    kcal != null && `${kcal.toLocaleString('en-IN')} kcal`,
    carbs != null && `${grams(carbs)} g carbs`,
    fat != null && `${grams(fat)} g fat`,
  ].filter((x): x is string => Boolean(x));
  const estimated =
    !certain(m) && Boolean(field(msg, 'kcal')?.guessed || field(msg, 'protein_g')?.guessed);
  const assumption = val(msg, 'assumption');
  const isToday = day === DIET_TODAY_ISO;

  const figure = unknown ? (
    <span style={{ fontFamily: font.sans, fontSize: 12.5, lineHeight: '17px', color: color.faint, whiteSpace: 'nowrap' }}>
      macros unknown
    </span>
  ) : protein != null ? (
    <Stacked
      top={
        <span style={{ display: 'inline-flex', alignItems: 'center' }}>
          {estimated && <Dot />}
          <Fig size={15}>{grams(protein)} g</Fig>
        </span>
      }
      parts={rest}
    />
  ) : undefined;

  // Protein today, against the target — only for a meal eaten today; under
  // an older one, today's total would be read as that day's.
  const target = data.rows.profile.proteinTarget;
  const todayP = data.meals
    .filter((x) => !x.deleted && x.date === DIET_TODAY_ISO)
    .reduce((s, x) => s + x.p, 0);

  return (
    <div style={agentCard('12px 14px')}>
      <Receipt coin={dietCoin} what={dish} meta={metaLine(slot, dayText(day, DIET_TODAY_ISO))} figure={figure} />

      {assumption && (
        <GapLine mark={!certain(m) ? <Dot /> : null} text={`Assumed: ${assumption}`} />
      )}
      {msg.needsQuantity.map((x) => (
        <GapLine key={`q-${x}`} mark={<Scales size={15} color={color.faint} />} text={`${cap(x)} — how much?`} right="not counted" />
      ))}
      {msg.unresolved.map((x) => (
        <GapLine key={`u-${x}`} mark={<X size={12} weight="bold" color={color.grey} />} text={`${cap(x)} — not found`} right="not counted" />
      ))}

      {estimated && protein != null && msg.rowId && (
        <GuessLine
          text={`${grams(protein)} g protein, I estimated`}
          onRight={() => a.onConfirm(msg)}
          onChange={() => a.onContext(proteinContext(dish, slot, day, DIET_TODAY_ISO))}
        />
      )}

      {isToday && !unknown && (
        <div style={{ marginTop: 12 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
            <span style={{ fontFamily: font.sans, fontSize: 12, lineHeight: '16px', color: color.faint, flex: 1 }}>Protein today</span>
            {target ? (
              <Fig size={12} tone={color.muted}>{`${grams(todayP)} of ${target} g`}</Fig>
            ) : (
              // No target, so no bar: the figure stands alone, and setting
              // one is a sentence away — the composer, not a settings page.
              <span style={{ display: 'inline-flex', alignItems: 'baseline', flex: '0 0 auto' }}>
                <Fig size={12} tone={color.muted}>{`${grams(todayP)} g · no target`}</Fig>
                <span aria-hidden="true" style={{ fontFamily: font.sans, fontSize: 12, color: color.muted, margin: '0 0.3em' }}>·</span>
                <TextBtn label="Set target" size={12} tone={color.brand} onClick={() => a.onContext(SET_PROTEIN_TARGET)} />
              </span>
            )}
          </div>
          {target ? (
            <div style={{ marginTop: 6 }}>
              <Bar pct={todayP / target} tone={color.diet} />
            </div>
          ) : null}
        </div>
      )}

      {msg.rowId && (
        <Quiet>
          <TextBtn label="Undo" icon={ArrowCounterClockwise} onClick={() => a.onDelete(msg)} />
          {unknown && (
            <TextBtn
              label="Add weight"
              // The row hangs on the composer and the sentence typed next goes
              // to the agent as a correction of it. No sentence is sent for
              // the user: an automatic one risks logging the meal twice
              // (spec/done/card-redesign.md § decided against).
              onClick={() => a.onContext(fieldContext(dish, 'weight'))}
            />
          )}
        </Quiet>
      )}
    </div>
  );
}

/** "700 g Paneer left" → "700 g"; "6 piece Eggs left" → "6 pcs". The level now, as the server worked it out. */
function levelOf(lede: string): string | null {
  const m = /^(-?[\d.]+) (\S+) .+ left$/.exec(lede);
  return m ? inUnit(Number(m[1]), m[2]) : null;
}

/** A pantry move: what moved and which way, and the level it left. */
export function PantryMoveCard({ msg, data, a }: { msg: ConfirmMsg; data: ConfirmData; a: ConfirmActions }) {
  const food = val(msg, 'food') ?? ledeTitle(msg.lede);
  const kind = val(msg, 'kind') ?? '';
  const q = /^(-?[\d.]+) (\S+)$/.exec(val(msg, 'quantity') ?? '');
  // The sign comes from the number, which the ledger stores signed — waste
  // and a downward correction arrive negative. Only a purchase adds a plus.
  const n = q ? Number(q[1]) : 0;
  const sign = n < 0 ? '−' : kind === 'bought' ? '+' : '';
  const moved = q ? `${sign}${inUnit(Math.abs(n), q[2])} ${kind}` : kind;
  const level = levelOf(msg.lede);

  if (data.live.deleted) {
    return <Removed coin={<Coin icon={Package} tint={color.lineSoft} ink={color.grey} />} what={food} day={data.day} />;
  }
  return (
    <div style={agentCard('12px 14px')}>
      <Receipt
        coin={<Coin icon={Package} tint={color.dietTint} ink={color.dietInk} />}
        what={food}
        meta={metaLine(moved, dayText(data.day))}
        figure={level ? <Fig>{level}</Fig> : undefined}
      />
      {msg.rowId && (
        <Quiet>
          <TextBtn label="Undo" icon={ArrowCounterClockwise} onClick={() => a.onDelete(msg)} />
        </Quiet>
      )}
    </div>
  );
}

/** A dish kept: drawn as suggestions draw it, from the live dish row, with the pin. */
export function DishSavedCard({ msg, data }: { msg: ConfirmMsg; data: ConfirmData }) {
  const dish = msg.rowId ? data.rows.dishes.find((d) => d.id === msg.rowId) : undefined;
  const name = dish?.name ?? val(msg, 'name') ?? ledeTitle(msg.lede).replace(/^Saved · /, '');
  const saved = dish ? dish.saved : true;
  return (
    <div style={agentCard('12px 14px')}>
      <Receipt
        coin={
          dish?.imageUrl ? (
            <img src={dish.imageUrl} alt="" style={{ width: 44, height: 44, borderRadius: '50%', objectFit: 'cover', flex: '0 0 auto' }} />
          ) : (
            <Coin icon={CookingPot} tint={color.dietTint} ink={color.dietInk} size={44} />
          )
        }
        what={name}
        meta={dish ? metaLine(dish.mealType, dish.minutes != null && `${dish.minutes} min`, dish.kcal != null && `${dish.kcal} kcal`) : null}
        figure={dish ? <Fig>{grams(dish.proteinG)} g</Fig> : undefined}
      />
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, margin: '10px 0 0 56px' }}>
        <PushPin size={14} weight={saved ? 'fill' : 'regular'} color={saved ? color.brand : color.faint} aria-hidden />
        <span style={{ fontFamily: font.sans, fontSize: 12.5, lineHeight: '17px', color: color.muted }}>
          {saved ? 'Saved' : 'No longer saved'}
        </span>
      </div>
    </div>
  );
}
