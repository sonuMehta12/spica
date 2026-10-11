import { useEffect, useState, type KeyboardEvent } from 'react';
import { DotsThreeVertical, Plus } from '@phosphor-icons/react';
import { color, font } from '../../theme';
import {
  inUnit,
  parseQuantity,
  type PantryMoveRow,
  type PantryRow,
  type PantryStatus,
} from '../../data/api';
import { useBack } from '../../state/nav';
import { shortDay } from '../../lib/format';

/**
 * Your data → Pantry. spec/in-progress/pantry-view.md.
 *
 * Four tabs. **Buy** is the shopping list — what ran out, went off, or fell
 * below its reorder level. **Stock** is everything counted, with its status.
 * **Moves** is the ledger those numbers come from. **Staple** is what is always
 * in the house, where a quantity would be meaningless.
 *
 * Nothing here edits a quantity: a wrong number gets a correction, a drifted
 * one gets a stock-take. Staple is the user's declaration, not a derivation —
 * eggs cycle even when no purchase has been logged, and atta never will.
 */
interface Props {
  rows: PantryRow[];
  moves: PantryMoveRow[];
  /** The deck's anchor day, so "2 days left" counts from the same today. */
  today: string;
  onMove: (foodId: string, grams: number, kind: 'purchase' | 'opening') => Promise<boolean>;
  onUndoMove: (id: string) => void;
  onAdd: (name: string, quantity?: number, staple?: boolean, unit?: string) => Promise<boolean>;
  onSettings: (id: string, reorder: number | null, shelfLife: number | null) => Promise<boolean>;
  onSetStaple: (id: string, staple: boolean) => Promise<boolean>;
  onStopTracking: (id: string) => void;
  onLoadMoves: (foodId?: string) => void;
}

/** Buy is the shopping list: things that ran out or went off. No cadence. */
const BUY: PantryStatus[] = ['out', 'stale', 'soon'];

const WORD: Record<PantryStatus, string> = {
  staple: '',
  new: 'not counted',
  out: 'out',
  stale: 'stale',
  soon: 'soon',
  ok: 'ok',
};

/** Past its life or gone is red; running low is plain ink. Amber is only the estimate dot. */
const TONE: Record<PantryStatus, string> = {
  staple: color.faint,
  new: color.faint,
  out: color.red,
  stale: color.red,
  soon: color.ink,
  ok: color.muted,
};

const shell = {
  background: color.white,
  border: `1px solid ${color.line}`,
  borderRadius: 14,
  overflow: 'hidden' as const,
};

const trayBtn = {
  fontFamily: font.sans,
  fontSize: 12,
  fontWeight: 500,
  lineHeight: '16px',
  padding: '5px 12px',
  borderRadius: 999,
  border: `1px solid ${color.border}`,
  background: color.white,
  color: color.muted,
  cursor: 'pointer',
} as const;

const input = {
  fontFamily: font.sans,
  fontSize: 13,
  color: color.ink,
  background: color.white,
  border: `1px solid ${color.border}`,
  borderRadius: 8,
  padding: '6px 10px',
  outline: 'none',
  minWidth: 0,
};

/**
 * One number, in the food's own unit. Enter saves; a refusal keeps it open.
 * For a food counted in pieces it also understands "1 dozen".
 */
function QuantityPrompt({
  initial,
  unit,
  label,
  hint,
  onSave,
  onClose,
}: {
  initial: string;
  unit: string;
  label: string;
  hint: string;
  onSave: (quantity: number) => Promise<boolean>;
  onClose: () => void;
}) {
  const [draft, setDraft] = useState(initial);
  const [failed, setFailed] = useState(false);
  const save = async () => {
    const ok = await onSave(parseQuantity(draft, unit));
    if (ok) onClose();
    else setFailed(true);
  };
  const keys = (e: KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      void save();
    } else if (e.key === 'Escape') {
      e.preventDefault();
      onClose();
    }
  };
  return (
    <div style={{ padding: '0 13px 11px', animation: 'fadeup 0.2s' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <input
          autoFocus
          inputMode={unit === 'piece' ? 'text' : 'decimal'}
          value={draft}
          onChange={(e) => {
            setDraft(e.target.value);
            setFailed(false);
          }}
          onKeyDown={keys}
          onFocus={(e) => e.currentTarget.select()}
          style={{ ...input, width: 90 }}
        />
        <span style={{ fontFamily: font.sans, fontSize: 12.5, color: color.muted }}>
          {unit === 'piece' ? 'pcs' : unit}
        </span>
        <span style={{ flex: 1 }} />
        <button type="button" style={trayBtn} onClick={onClose}>
          Cancel
        </button>
        <button
          type="button"
          style={{ ...trayBtn, color: color.white, background: color.brand, borderColor: color.brand }}
          onClick={() => void save()}
        >
          {label}
        </button>
      </div>
      <div style={{ fontFamily: font.sans, fontSize: 11.5, marginTop: 6, color: failed ? color.red : color.muted }}>
        {failed ? 'Not saved — it must be a number above zero.' : hint}
      </div>
    </div>
  );
}

function Settings({
  row,
  onSave,
  onClose,
}: {
  row: PantryRow;
  onSave: (reorder: number | null, shelfLife: number | null) => Promise<boolean>;
  onClose: () => void;
}) {
  const [reorder, setReorder] = useState(row.reorderAtG?.toString() ?? '');
  const [life, setLife] = useState(row.shelfLifeDays?.toString() ?? '');
  const [failed, setFailed] = useState(false);
  const save = async () => {
    const ok = await onSave(reorder ? Number(reorder) : null, life ? Number(life) : null);
    if (ok) onClose();
    else setFailed(true);
  };
  return (
    <div style={{ padding: '0 13px 11px', animation: 'fadeup 0.2s' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <span style={{ fontFamily: font.sans, fontSize: 11.5, color: color.muted }}>buy below</span>
        <input inputMode="numeric" value={reorder} onChange={(e) => setReorder(e.target.value)} style={{ ...input, width: 70 }} />
        <span style={{ fontFamily: font.sans, fontSize: 12.5, color: color.muted }}>
          {row.unit === 'piece' ? 'pcs' : row.unit}
        </span>
        <span style={{ fontFamily: font.sans, fontSize: 11.5, color: color.muted, marginLeft: 6 }}>good for</span>
        <input inputMode="numeric" value={life} onChange={(e) => setLife(e.target.value)} style={{ ...input, width: 60 }} />
        <span style={{ fontFamily: font.sans, fontSize: 12.5, color: color.muted }}>days</span>
        <span style={{ flex: 1 }} />
        <button type="button" style={trayBtn} onClick={onClose}>
          Cancel
        </button>
        <button
          type="button"
          style={{ ...trayBtn, color: color.white, background: color.brand, borderColor: color.brand }}
          onClick={() => void save()}
        >
          Save
        </button>
      </div>
      <div style={{ fontFamily: font.sans, fontSize: 11.5, marginTop: 6, color: failed ? color.red : color.muted }}>
        {failed ? 'Not saved — the server refused.' : 'Blank means no rule. Neither is a quantity.'}
      </div>
    </div>
  );
}

type Tab = 'buy' | 'stock' | 'moves' | 'staple';

/** Whole days from a date to the deck's anchor day. */
const daysSinceFrom = (iso: string, today: string) =>
  Math.round((Date.parse(`${today}T00:00:00Z`) - Date.parse(`${iso}T00:00:00Z`)) / 86_400_000);

export default function PantrySection({
  rows,
  moves,
  today,
  onMove,
  onUndoMove,
  onAdd,
  onSettings,
  onSetStaple,
  onStopTracking,
  onLoadMoves,
}: Props) {
  const [view, setView] = useState<Tab>('buy');
  /** Which row's tray is open, and which prompt inside it. */
  const [open, setOpen] = useState<string | null>(null);
  const [prompt, setPrompt] = useState<{ row: string; kind: 'purchase' | 'opening' | 'settings' } | null>(null);
  const [adding, setAdding] = useState(false);
  const [newFood, setNewFood] = useState({ name: '', grams: '', staple: false, unit: 'g' });
  const [addFailed, setAddFailed] = useState(false);
  /** Moves filtered to one food, set by tapping it in Stock. */
  const [focus, setFocus] = useState<PantryRow | null>(null);

  useEffect(() => {
    onLoadMoves(focus?.foodId);
    // onLoadMoves is stable enough for this; refetching on focus is the point.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focus?.foodId]);

  const daysSince = (iso: string) => daysSinceFrom(iso, today);
  const buy = rows.filter((r) => BUY.includes(r.status));
  // Stock is the whole counted inventory, Buy the subset that needs action —
  // the same relationship the Paisa report's All and Pending have.
  const stock = rows.filter((r) => !r.staple);
  const staples = rows.filter((r) => r.staple);

  // Back closes what is open, innermost first — the amount being typed, the
  // row's tray, the new food — and then lifts the History filter, back to
  // Stock where it was set. Only what is on screen: the tray is shared
  // across tabs, and a press must never close something unseen.
  const tabRows = view === 'buy' ? buy : view === 'stock' ? stock : view === 'staple' ? staples : [];
  const onScreen = (id: string | null | undefined) => id != null && tabRows.some((r) => r.id === id);
  useBack(focus != null && view === 'moves', () => {
    setFocus(null);
    setView('stock');
  });
  useBack(adding && view === 'stock', () => setAdding(false));
  useBack(onScreen(open), () => {
    setOpen(null);
    setPrompt(null);
  });
  useBack(onScreen(prompt?.row), () => setPrompt(null));

  /**
   * When it came in, then what that means now: *11 Aug*, *22 Aug · 2d left*,
   * *22 Aug · 1d over*. The date answers "is this the one I bought last week";
   * the days answer "can I still eat it". A shelf-stable food that is fine
   * shows only its date.
   */
  const sub = (r: PantryRow) => {
    if (r.status === 'staple') return '';
    if (r.status === 'new') return 'not counted yet';
    const parts: string[] = [];
    if (r.lastIn) parts.push(shortDay(r.lastIn));
    if (r.status === 'out') parts.push('nothing left');
    else if (r.shelfLifeDays && r.lastIn) {
      const left = r.shelfLifeDays - daysSince(r.lastIn);
      parts.push(left < 0 ? `${-left}d over` : left === 0 ? 'today' : `${left}d left`);
    } else if (r.status === 'soon' && r.reorderAtG != null) {
      parts.push(`below ${inUnit(r.reorderAtG, r.unit)}`);
    }
    return parts.join(' · ');
  };

  const addFood = async () => {
    const ok = await onAdd(
      newFood.name,
      newFood.grams ? parseQuantity(newFood.grams, newFood.unit) : undefined,
      newFood.staple,
      newFood.unit,
    );
    if (ok) {
      setNewFood({ name: '', grams: '', staple: false, unit: 'g' });
      setAdding(false);
      setAddFailed(false);
    } else setAddFailed(true);
  };

  const Row = ({ r }: { r: PantryRow }) => (
    <div style={{ borderTop: `1px solid ${color.lineSoft}` }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, padding: '11px 6px 11px 13px' }}>
        <button
          type="button"
          className="hov-tint"
          // Opens the row where it stands. It used to jump to the Moves tab,
          // which read as the item having moved — and nothing moves except by
          // a purchase or a meal.
          onClick={() => {
            setOpen((o) => (o === r.id ? null : r.id));
            setPrompt(null);
          }}
          style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', textAlign: 'left', minWidth: 0, flex: 1 }}
        >
          <span style={{ fontSize: 13.5, fontWeight: 500, color: color.ink }}>{r.name}</span>
          {sub(r) && (
            <span style={{ fontFamily: font.sans, fontSize: 11, color: color.faint, marginLeft: 6 }}>{sub(r)}</span>
          )}
        </button>
        {/* No number for a staple or a food nothing has been logged into:
            there is no stock figure, and a negative consumption sum is not one. */}
        {r.status !== 'staple' && r.status !== 'new' && (
          <span
            style={{
              fontFamily: font.sans,
              fontSize: 12.5,
              fontWeight: 600,
              whiteSpace: 'nowrap',
              // Stale still shows the number, greyed: it is what the ledger
              // says, and the word beside it says why not to trust it.
              color: r.status === 'stale' ? color.faint : r.status === 'out' ? color.red : color.muted,
            }}
          >
            {inUnit(r.stockG, r.unit)}
          </span>
        )}
        {WORD[r.status] && (
          <span style={{ fontFamily: font.sans, fontSize: 11, color: TONE[r.status], whiteSpace: 'nowrap' }}>
            {WORD[r.status]}
          </span>
        )}
        <button
          type="button"
          onClick={() => {
            setOpen((o) => (o === r.id ? null : r.id));
            setPrompt(null);
          }}
          aria-label={`Options — ${r.name}`}
          aria-expanded={open === r.id}
          className="hov-tint"
          style={{
            width: 28,
            height: 28,
            borderRadius: '50%',
            background: open === r.id ? color.lineSoft : 'none',
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
          <DotsThreeVertical size={18} weight="bold" color={color.faint} aria-hidden />
        </button>
      </div>

      {open === r.id && !prompt && (
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', padding: '0 8px 10px', justifyContent: 'flex-end', animation: 'fadeup 0.2s' }}>
          <button
            type="button"
            style={{ ...trayBtn, color: color.brand, background: color.brandTint, borderColor: color.brandTint }}
            onClick={() => setPrompt({ row: r.id, kind: 'purchase' })}
          >
            Bought
          </button>
          <button type="button" style={trayBtn} onClick={() => setPrompt({ row: r.id, kind: 'opening' })}>
            Have
          </button>
          {!r.staple && (
            <button type="button" style={trayBtn} onClick={() => setPrompt({ row: r.id, kind: 'settings' })}>
              Settings
            </button>
          )}
          <button
            type="button"
            style={trayBtn}
            onClick={() => {
              void onSetStaple(r.id, !r.staple);
              setOpen(null);
            }}
          >
            {r.staple ? 'Count it' : 'Always here'}
          </button>
          <button
            type="button"
            style={trayBtn}
            onClick={() => {
              setFocus(r);
              setView('moves');
              setOpen(null);
            }}
          >
            History
          </button>
          <button
            type="button"
            style={{ ...trayBtn, color: color.red, borderColor: color.redBorder }}
            onClick={() => {
              onStopTracking(r.id);
              setOpen(null);
            }}
          >
            Stop tracking
          </button>
        </div>
      )}

      {prompt?.row === r.id && prompt.kind !== 'settings' && (
        <QuantityPrompt
          initial={prompt.kind === 'purchase' ? String(r.lastInG ?? '') : String(Math.max(0, r.stockG))}
          unit={r.unit}
          label={prompt.kind === 'purchase' ? 'Bought' : 'Have'}
          hint={
            prompt.kind === 'purchase'
              ? r.unit === 'piece'
                ? 'How many came in today — "1 dozen" works.'
                : 'How much came in today.'
              : 'What is actually on the shelf — a stock-take, counted from now.'
          }
          onSave={async (g) => {
            const ok = await onMove(r.foodId, g, prompt.kind as 'purchase' | 'opening');
            if (ok) setOpen(null);
            return ok;
          }}
          onClose={() => setPrompt(null)}
        />
      )}
      {prompt?.row === r.id && prompt.kind === 'settings' && (
        <Settings
          row={r}
          onSave={async (re, life) => {
            const ok = await onSettings(r.id, re, life);
            if (ok) setOpen(null);
            return ok;
          }}
          onClose={() => setPrompt(null)}
        />
      )}
    </div>
  );

  const tab = (id: Tab, label: string) => (
    <button
      key={id}
      type="button"
      onClick={() => {
        setView(id);
        if (id !== 'moves') setFocus(null);
      }}
      style={{
        fontFamily: font.sans,
        fontSize: 11.5,
        padding: '5px 12px',
        borderRadius: 14,
        border: `1px solid ${view === id ? color.brand : color.border}`,
        background: view === id ? color.brand : color.white,
        color: view === id ? color.white : color.muted,
        cursor: 'pointer',
      }}
    >
      {label}
    </button>
  );

  return (
    <>
      <div style={{ display: 'flex', gap: 7, marginBottom: 4, flexWrap: 'wrap' }}>
        {tab('buy', `Buy${buy.length ? ` · ${buy.length}` : ''}`)}
        {tab('stock', `Stock · ${stock.length}`)}
        {tab('moves', focus ? `Moves · ${focus.name}` : 'Moves')}
        {tab('staple', `Staple · ${staples.length}`)}
      </div>

      {view === 'buy' && (
        <div style={shell}>
            {buy.length === 0 && (
              <div style={{ padding: 14, fontSize: 13.5, color: color.muted }}>
                Nothing to buy — nothing is out, stale or running low.
              </div>
            )}
          {buy.map((r) => (
            <Row key={r.id} r={r} />
          ))}
        </div>
      )}

      {view === 'staple' && (
        // No quantities, by design: nobody weighs the family's atta.
        // 'Count it' moves a row over to Stock.
        <div style={shell}>
          {staples.map((r) => (
            <Row key={r.id} r={r} />
          ))}
        </div>
      )}

      {view === 'stock' ? (
        <>
          <div style={shell}>
            {stock.map((r) => (
              <Row key={r.id} r={r} />
            ))}
          </div>

          <div style={{ marginTop: 10 }}>
            {adding ? (
              <div style={{ ...shell, padding: '11px 13px', display: 'grid', gap: 8 }}>
                <div style={{ display: 'flex', gap: 8 }}>
                  <input
                    autoFocus
                    placeholder="What is it — soya chunks"
                    value={newFood.name}
                    onChange={(e) => setNewFood({ ...newFood, name: e.target.value })}
                    style={{ ...input, flex: 1, fontFamily: font.sans }}
                  />
                  <input
                    inputMode={newFood.unit === 'piece' ? 'text' : 'decimal'}
                    placeholder="how much"
                    disabled={newFood.staple}
                    value={newFood.staple ? '' : newFood.grams}
                    onChange={(e) => setNewFood({ ...newFood, grams: e.target.value })}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') void addFood();
                      if (e.key === 'Escape') {
                        e.preventDefault();
                        setAdding(false);
                      }
                    }}
                    style={{ ...input, width: 84 }}
                  />
                  {/* What it is counted in. Eggs by the piece, milk in ml. */}
                  <select
                    value={newFood.unit}
                    onChange={(e) => setNewFood({ ...newFood, unit: e.target.value })}
                    aria-label="Unit"
                    style={{ ...input, width: 68, fontFamily: font.sans }}
                  >
                    <option value="g">g</option>
                    <option value="ml">ml</option>
                    <option value="piece">pcs</option>
                  </select>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontFamily: font.sans, fontSize: 11.5, color: color.muted, cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={newFood.staple}
                      onChange={(e) => setNewFood({ ...newFood, staple: e.target.checked })}
                    />
                    always here
                  </label>
                  <span style={{ fontFamily: font.sans, fontSize: 11.5, color: addFailed ? color.red : color.muted, flex: 1 }}>
                    {addFailed ? 'Not saved — it may already be tracked.' : 'How much is optional.'}
                  </span>
                  <button type="button" style={trayBtn} onClick={() => setAdding(false)}>
                    Cancel
                  </button>
                  <button
                    type="button"
                    style={{ ...trayBtn, color: color.white, background: color.brand, borderColor: color.brand }}
                    onClick={() => void addFood()}
                  >
                    Save
                  </button>
                </div>
              </div>
            ) : (
              <button
                type="button"
                className="hov-tint"
                onClick={() => setAdding(true)}
                style={{
                  ...shell,
                  width: '100%',
                  padding: '11px 14px',
                  textAlign: 'left',
                  fontFamily: font.sans,
                  fontSize: 13.5,
                  fontWeight: 500,
                  color: color.brand,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                }}
              >
                <Plus size={15} aria-hidden />
                Add item
              </button>
            )}
          </div>
        </>
      ) : view === 'moves' ? (
        <div style={shell}>
          {moves.length === 0 && (
            <div style={{ padding: 14, fontSize: 13.5, color: color.muted }}>Nothing moved yet.</div>
          )}
          {moves.map((m, i) => (
            <div
              key={m.id}
              style={{
                display: 'flex',
                alignItems: 'baseline',
                gap: 10,
                padding: '10px 8px 10px 13px',
                borderTop: i ? `1px solid ${color.lineSoft}` : 'none',
              }}
            >
              <span style={{ fontFamily: font.sans, fontSize: 11, color: color.faint, width: 44, flex: '0 0 auto' }}>
                {shortDay(m.day)}
              </span>
              <span
                style={{
                  fontFamily: font.sans,
                  fontSize: 13.5,
                  fontWeight: 500,
                  width: 68,
                  flex: '0 0 auto',
                  // Food in is Diet's ink; food out is plain.
                  color: m.quantity > 0 ? color.dietInk : color.muted,
                }}
              >
                {m.quantity > 0 ? '+' : '−'}
                {inUnit(Math.abs(m.quantity), m.unit)}
              </span>
              <span style={{ minWidth: 0, flex: 1 }}>
                <span style={{ fontSize: 13.5, fontWeight: 500 }}>{m.name}</span>
                <span style={{ fontFamily: font.sans, fontSize: 11, color: color.faint, marginLeft: 6 }}>
                  {m.dish ?? m.kind}
                </span>
              </span>
              {/* Consumption belongs to its meal — undoing it there would
                  strand the meal, so only user-written moves offer it. */}
              {m.kind !== 'consumption' && (
                <button type="button" style={trayBtn} onClick={() => onUndoMove(m.id)}>
                  Undo
                </button>
              )}
            </div>
          ))}
        </div>
      ) : null}
    </>
  );
}
