import { Barbell, BookmarkSimple, Check, CookingPot } from '@phosphor-icons/react';
import { color, font } from '../../theme';
import { agentCard } from './bubble';
import { grams } from './confirmKit';
import { Chip, Coin, Fig, ListRow, PillBtn, PrimaryBtn, Stacked, TextBtn, clamp, metaLine } from './parts';
import type { SuggestItem, SuggestMsg } from '../../types';

/**
 * What the agent thinks you should eat or do next — each one tap from logged.
 *
 * A suggestion can only be kept if it is an **object**; that is the whole
 * reason replies are cards rather than prose. A tap logs it through the
 * route, no model in the loop: a tap on a suggestion can only mean *this one*.
 * The action is a real button now — when the whole card was the button,
 * nothing on it looked tappable.
 */
export default function SuggestCard({
  msg,
  loggedRefs,
  pendingRefs,
  onLog,
  onSave,
  onDismiss,
}: {
  msg: SuggestMsg;
  /** Refs already logged today — from the ledger, or from this session's taps. */
  loggedRefs: Set<string>;
  pendingRefs: string[];
  onLog: (item: SuggestItem) => void;
  onSave: (msgId: string, item: SuggestItem) => void;
  onDismiss: (msgId: string, ref: string) => void;
}) {
  const dishes = msg.items.filter((it) => it.type === 'dish');
  const moves = msg.items.filter((it) => it.type === 'exercise');
  return (
    <div style={{ display: 'grid', gap: 10, gridTemplateColumns: 'minmax(0, 1fr)' }}>
      {dishes.map((it) => (
        <Dish
          key={it.ref}
          it={it}
          logged={loggedRefs.has(it.ref)}
          pending={pendingRefs.includes(it.ref)}
          onLog={() => onLog(it)}
          onSave={() => onSave(msg.id, it)}
          onDismiss={() => onDismiss(msg.id, it.ref)}
        />
      ))}
      {moves.length > 0 && (
        <div style={agentCard('4px 14px')}>
          {moves.map((it, i) => (
            <Exercise key={it.ref} it={it} first={i === 0} logged={loggedRefs.has(it.ref)} pending={pendingRefs.includes(it.ref)} onLog={() => onLog(it)} />
          ))}
        </div>
      )}
    </div>
  );
}

/** "✓ Logged" — read from the ledger, so it survives a reload. */
function Done({ label }: { label: string }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontFamily: font.sans, fontSize: 13.5, lineHeight: '18px', fontWeight: 500, color: color.dietInk, whiteSpace: 'nowrap' }}>
      <Check size={14} weight="bold" aria-hidden />
      {label}
    </span>
  );
}

function Busy() {
  return <span style={{ fontFamily: font.sans, fontSize: 13.5, lineHeight: '18px', color: color.faint }}>Logging…</span>;
}

function Dish({
  it,
  logged,
  pending,
  onLog,
  onSave,
  onDismiss,
}: {
  it: SuggestItem;
  logged: boolean;
  pending: boolean;
  onLog: () => void;
  onSave: () => void;
  onDismiss: () => void;
}) {
  // The why, as the facts it was made of: "cookable now", "had 1×", "16 days ago".
  const reasons = it.why.split(' · ').map((s) => s.trim()).filter(Boolean);
  return (
    <div style={{ ...agentCard('12px 14px'), opacity: pending ? 0.7 : 1, minWidth: 0 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0 }}>
        {/* The dish's own photo or the coin — never a stock photo standing in
            for food it is not. */}
        {it.imageUrl ? (
          <img src={it.imageUrl} alt="" style={{ width: 44, height: 44, borderRadius: '50%', objectFit: 'cover', flex: '0 0 auto' }} />
        ) : (
          <Coin icon={CookingPot} tint={color.dietTint} ink={color.dietInk} size={44} />
        )}
        <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 2 }}>
          <span style={{ fontFamily: font.sans, fontSize: 15, lineHeight: '20px', fontWeight: 500, color: color.ink, ...clamp(2) }}>
            {it.name}
          </span>
          <span style={{ fontFamily: font.sans, fontSize: 12.5, lineHeight: '17px', color: color.faint }}>
            {metaLine(it.mealType, it.minutes != null && `${it.minutes} min`, it.kcal != null ? `${it.kcal} kcal` : 'kcal unknown')}
          </span>
        </div>
        {it.proteinG != null && <Fig>{grams(it.proteinG)} g</Fig>}
      </div>
      {reasons.length > 0 && (
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', margin: '10px 0 0 56px' }}>
          {reasons.map((r) => (
            <Chip key={r}>{r}</Chip>
          ))}
        </div>
      )}
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap', margin: '12px 0 0 56px' }}>
        {logged ? <Done label="Logged" /> : pending ? <Busy /> : <PrimaryBtn label="Log it" onClick={onLog} />}
        <TextBtn
          label={it.saved ? 'Saved' : 'Save'}
          icon={BookmarkSimple}
          iconWeight={it.saved ? 'fill' : 'regular'}
          tone={it.saved ? color.brand : color.muted}
          onClick={onSave}
        />
        {!logged && !pending && <TextBtn label="Not this" onClick={onDismiss} />}
      </div>
    </div>
  );
}

/**
 * "strength · legs · dumbbell · done 2×" → "dumbbell": the equipment is the
 * part of the why that is not the kind, the muscle or the count — the count is
 * the row's figure, and a figure is not repeated as a fact.
 */
function equipmentOf(it: SuggestItem): string | null {
  const skip = [it.exerciseKind, it.muscleGroup].filter(Boolean).map((s) => s!.toLowerCase());
  const rest = it.why
    .split(' · ')
    .map((s) => s.trim())
    .filter((s) => s && !skip.includes(s.toLowerCase()) && !/^done \d+×$/.test(s) && s !== 'not tried yet');
  return rest[0] ?? null;
}

function Exercise({
  it,
  first,
  logged,
  pending,
  onLog,
}: {
  it: SuggestItem;
  first: boolean;
  logged: boolean;
  pending: boolean;
  onLog: () => void;
}) {
  return (
    <ListRow first={first} pad="10px 0">
      <Coin icon={Barbell} weight="fill" tint={color.dietTint} ink={color.dietInk} size={40} />
      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 1 }}>
        <span style={{ fontFamily: font.sans, fontSize: 15, lineHeight: '20px', fontWeight: 500, color: color.ink, ...clamp(2) }}>
          {it.name}
        </span>
        <span style={{ fontFamily: font.sans, fontSize: 12.5, lineHeight: '17px', color: color.faint }}>
          {metaLine(it.muscleGroup ?? it.exerciseKind, it.minutes != null && `${it.minutes} min`, equipmentOf(it))}
        </span>
      </div>
      {it.tried ? <Stacked top={<Fig size={14}>{it.tried}×</Fig>} under="done" /> : <Fig size={14} tone={color.faint}>new</Fig>}
      {logged ? <Done label="Done" /> : pending ? <Busy /> : <PillBtn label="Done" onClick={onLog} />}
    </ListRow>
  );
}
