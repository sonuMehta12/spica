import { useState } from 'react';
import { Check, Star } from '@phosphor-icons/react';
import { color, font } from '../../theme';
import { shortDate } from '../../lib/format';
import { filterPill } from '../messages/bubble';
import { inUnit, type DishRow, type PantryRow } from '../../data/api';
import { useBack } from '../../state/nav';

/**
 * Your data → Dishes. spec/in-progress/dishes.md.
 *
 * Your library, not the pool: a dish is here because you **tried** it (counted
 * from the ledger's meal lines) or **saved** it (a bookmark row). Both marks
 * can be on one dish.
 *
 * Three tabs. **Cook now** is the only computed one — a dish qualifies when
 * every ingredient it needs is in the pantry, and staples count as present
 * because they always are. Dishes with no ingredients (Office thali) can never
 * qualify, and that is correct: nobody cooks a thali.
 *
 * No suggestion here. Ranking is the agent's job and the agent is phase 3.
 */
interface Props {
  dishes: DishRow[];
  pantry: PantryRow[];
  onToggleSave: (id: string) => void;
}

type Tab = 'all' | 'cook' | 'saved';

const shell = {
  background: color.white,
  border: `1px solid ${color.line}`,
  borderRadius: 14,
  overflow: 'hidden' as const,
};

/**
 * Can this be cooked from what is in the house right now?
 *
 * The server sends the ingredients already flattened — a component dish's
 * foods arrive as ordinary lines with their grams scaled — so nesting is
 * checked, not skipped.
 *
 * `missing` blocks the dish; `iffy` does not. A staple is always present, and
 * an untracked food is unknowable rather than absent: nagging about eggs
 * nobody logged would be the confident wrong answer this app avoids. Stale is
 * a warning, never a block — you are the one who can look in the fridge, and
 * the pantry refuses to declare food spoiled on its own.
 */
function checkStock(dish: DishRow, pantry: PantryRow[]): { missing: string[]; iffy: string[] } {
  const byId = new Map(pantry.map((p) => [p.foodId, p]));
  const missing: string[] = [];
  const iffy: string[] = [];
  for (const it of dish.items) {
    if (!it.foodId) continue;
    const row = byId.get(it.foodId);
    if (!row || row.status === 'staple' || row.status === 'new') continue;
    if (row.status === 'out' || (it.quantity != null && row.stockG < it.quantity)) missing.push(row.name);
    else if (row.status === 'stale') iffy.push(row.name);
  }
  return { missing, iffy };
}

export default function DishesSection({ dishes, pantry, onToggleSave }: Props) {
  const [view, setView] = useState<Tab>('all');
  const [open, setOpen] = useState<string | null>(null);

  const cookable = dishes.filter(
    (d) => d.items.length > 0 && checkStock(d, pantry).missing.length === 0,
  );
  const saved = dishes.filter((d) => d.saved);
  const shown = view === 'cook' ? cookable : view === 'saved' ? saved : dishes;
  // An open dish closes on Back — only while the filter still shows it.
  useBack(open != null && shown.some((d) => d.id === open), () => setOpen(null));

  const tab = (id: Tab, label: string) => (
    <button
      key={id}
      type="button"
      onClick={() => setView(id)}
      style={filterPill(view === id)}
    >
      {label}
    </button>
  );

  return (
    <>
      <div style={{ display: 'flex', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
        {tab('all', `All · ${dishes.length}`)}
        {tab('cook', `Cook now · ${cookable.length}`)}
        {tab('saved', `Saved · ${saved.length}`)}
      </div>

      <div style={shell}>
        {shown.length === 0 && (
          <div style={{ padding: 14, fontSize: 13.5, color: color.muted }}>
            {view === 'cook'
              ? 'Nothing can be cooked from what is in the house right now.'
              : view === 'saved'
                ? 'Nothing saved yet. Star a dish to try it later.'
                : 'No dishes yet.'}
          </div>
        )}
        {shown.map((d, i) => {
          const { missing, iffy } = checkStock(d, pantry);
          const ready = d.items.length > 0 && missing.length === 0;
          return (
            <div key={d.id} style={{ borderTop: i ? `1px solid ${color.lineSoft}` : 'none' }}>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, padding: '10px 6px 10px 14px' }}>
                <button
                  type="button"
                  className="hov-tint"
                  onClick={() => setOpen((o) => (o === d.id ? null : d.id))}
                  aria-expanded={open === d.id}
                  style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', textAlign: 'left', minWidth: 0, flex: 1 }}
                >
                  <span style={{ fontSize: 13.5, fontWeight: 500, color: color.ink }}>{d.name}</span>
                  <span style={{ fontFamily: font.sans, fontSize: 11, color: color.faint, marginLeft: 6 }}>
                    {d.serving}
                    {d.minutes != null && ` · ${d.minutes}m`}
                    {d.needsPrepAhead && ' · prep ahead'}
                  </span>
                  {/* Two marks, and a dish can carry both. */}
                  <span style={{ display: 'block', fontFamily: font.sans, fontSize: 11, marginTop: 3 }}>
                    {/* A mark is a Phosphor glyph, never a character. The tick
                        has no word beside it, so it is named; the star's
                        word says it. Baseline-aligned so the line's text stays
                        on one baseline, the glyph centred on it. */}
                    {d.tried > 0 && (
                      <span style={{ display: 'inline-flex', alignItems: 'baseline', gap: 3, color: color.dietInk }}>
                        <Check size={11} weight="bold" color={color.dietInk} role="img" aria-label="Tried" style={{ alignSelf: 'center' }} />
                        {d.tried}× {d.lastTried && `· ${shortDate(d.lastTried)}`}
                      </span>
                    )}
                    {d.tried > 0 && (d.saved || missing.length > 0 || iffy.length > 0) && (
                      <span style={{ color: color.faint }}>{'  ·  '}</span>
                    )}
                    {d.saved && (
                      <span style={{ display: 'inline-flex', alignItems: 'baseline', gap: 3, color: color.brand }}>
                        <Star size={11} weight="fill" color={color.brand} aria-hidden style={{ alignSelf: 'center' }} />
                        saved
                      </span>
                    )}
                    {d.saved && (missing.length > 0 || iffy.length > 0) && (
                      <span style={{ color: color.faint }}>{'  ·  '}</span>
                    )}
                    {missing.length > 0 ? (
                      <span style={{ color: color.faint }}>
                        need {missing.slice(0, 2).join(', ')}
                        {missing.length > 2 && ` +${missing.length - 2}`}
                      </span>
                    ) : (
                      // Cookable, but something in it is past its life. Said,
                      // not enforced — the fridge is yours to look in.
                      iffy.length > 0 && (
                        <span style={{ color: color.red }}>{iffy.join(', ')} is stale</span>
                      )
                    )}
                    {ready && iffy.length === 0 && d.tried === 0 && !d.saved && (
                      <span style={{ color: color.dietInk }}>can cook now</span>
                    )}
                  </span>
                </button>

                <span style={{ fontFamily: font.sans, fontSize: 13.5, fontWeight: 500, whiteSpace: 'nowrap', color: color.ink }}>
                  {d.proteinG}g
                </span>
                <span style={{ fontFamily: font.sans, fontSize: 11, color: color.faint, whiteSpace: 'nowrap' }}>
                  {d.kcal ?? '—'} kcal
                </span>
                <button
                  type="button"
                  onClick={() => onToggleSave(d.id)}
                  aria-label={d.saved ? `Unsave ${d.name}` : `Save ${d.name}`}
                  aria-pressed={d.saved}
                  className="hov-tint"
                  style={{
                    width: 28,
                    height: 28,
                    borderRadius: '50%',
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    padding: 0,
                    alignSelf: 'center',
                    flex: '0 0 auto',
                  }}
                >
                  <Star size={16} weight={d.saved ? 'fill' : 'regular'} color={d.saved ? color.brand : color.faint} aria-hidden />
                </button>
              </div>

              {open === d.id && (
                <div style={{ padding: '0 14px 12px', animation: 'fadeup 0.2s' }}>
                  {d.items.length > 0 ? (
                    <div style={{ fontFamily: font.sans, fontSize: 11.5, color: color.muted, lineHeight: 1.7 }}>
                      {d.items.map((it, n) => (
                        <span key={n} style={{ color: it.fromDish ? color.faint : color.muted }}>
                          {n > 0 && ' · '}
                          {it.name ?? 'a dish'}{' '}
                          {it.quantity != null ? inUnit(it.quantity, it.unit) : `×${it.servings}`}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <div style={{ fontFamily: font.sans, fontSize: 11.5, color: color.muted }}>
                      No ingredients — it cannot be broken into grams, so it never appears in Cook now.
                    </div>
                  )}
                  {d.note && (
                    <div style={{ fontFamily: font.sans, fontSize: 11.5, color: color.muted, marginTop: 6 }}>
                      {d.note}
                    </div>
                  )}
                  <div style={{ fontFamily: font.sans, fontSize: 11, color: color.faint, marginTop: 6 }}>
                    {[d.mealType, ...d.tags].filter(Boolean).join(' · ')}
                    {d.mine ? ' · yours' : ''}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </>
  );
}
