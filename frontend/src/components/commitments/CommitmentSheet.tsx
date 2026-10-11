import { useState, type CSSProperties, type ReactNode } from 'react';
import { X } from '@phosphor-icons/react';
import { color, font, radius, shadow } from '../../theme';
import { primaryBtn } from '../messages/bubble';
import { trayBtn } from '../messages/Tray';
import { categoryChoices } from './kit';
import type { CommitmentDraft, CommitmentRow } from '../../data/api';
import type { CommitmentSheet as SheetState } from '../../state/usePersonaOS';

interface Props {
  sheet: SheetState;
  /** Categories the ledger already uses, most-used first. */
  usedCategories: string[];
  /** Closes this sheet on success; false keeps it open with what was typed. */
  onSave: (draft: CommitmentDraft, editing: CommitmentRow | null, paymentId?: string) => Promise<boolean>;
  /** X, the scrim, Cancel — and Back and Escape, which pop the sheet like any screen. */
  onClose: () => void;
}

const field: CSSProperties = {
  width: '100%',
  boxSizing: 'border-box',
  fontFamily: font.sans,
  fontSize: 15,
  lineHeight: '20px',
  padding: '9px 12px',
  borderRadius: 10,
  border: `1px solid ${color.border}`,
  background: color.paper,
  color: color.ink,
  outline: 'none',
  fontFeatureSettings: "'tnum'",
};

function Labelled({ name, hint, children }: { name: string; hint?: string; children: ReactNode }) {
  return (
    <label style={{ display: 'block', marginTop: 14 }}>
      <span style={{ display: 'block', fontFamily: font.sans, fontSize: 12.5, color: color.muted, marginBottom: 5 }}>
        {name}
        {hint && <span style={{ color: color.faint }}>{'  '}{hint}</span>}
      </span>
      {children}
    </label>
  );
}

/**
 * The commitment sheet: name, amount, category, an optional due day, and
 * whether it repeats. Add and Edit are the same fields. Opened from a
 * payment's tray it arrives pre-filled from the payment, and saving counts
 * that payment toward the new line.
 *
 * A screen on the stack: Back and Escape close it, and Escape inside a field
 * only leaves the field. The draft lives here, never in history.
 */
export default function CommitmentSheet({ sheet, usedCategories, onSave, onClose }: Props) {
  const { editing, payment } = sheet;
  const seed = editing
    ? { name: editing.name, amount: String(editing.expectedPaise / 100), category: editing.category, due: editing.dueDay, repeats: editing.repeats }
    : payment
      ? { name: payment.name, amount: String(payment.amountPaise / 100), category: payment.category, due: null, repeats: true }
      : { name: '', amount: '', category: '', due: null as number | null, repeats: true };

  const [name, setName] = useState(seed.name);
  const [amount, setAmount] = useState(seed.amount);
  const [category, setCategory] = useState(seed.category);
  const [due, setDue] = useState(seed.due != null ? String(seed.due) : '');
  const [repeats, setRepeats] = useState(seed.repeats);
  const [busy, setBusy] = useState(false);

  const categories = categoryChoices([...(category ? [category] : []), ...usedCategories]);
  const amountPaise = Math.round(Number(amount.replace(/,/g, '')) * 100);
  const dueDay = due.trim() === '' ? null : Number(due);
  const dueOk = dueDay === null || (Number.isInteger(dueDay) && dueDay >= 1 && dueDay <= 31);
  const ok = name.trim() !== '' && category !== '' && Number.isFinite(amountPaise) && amountPaise > 0 && dueOk;

  const save = async () => {
    if (!ok || busy) return;
    setBusy(true);
    const saved = await onSave(
      { name: name.trim(), category, amountPaise, dueDay, repeats },
      editing,
      payment?.id,
    );
    // A refusal keeps the sheet open with what was typed; the toast says why.
    if (!saved) setBusy(false);
  };

  const title = editing ? 'Edit commitment' : 'Add commitment';

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={title}
      tabIndex={-1}
      style={{ position: 'absolute', inset: 0, zIndex: 120, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', outline: 'none' }}
    >
      <div
        onClick={onClose}
        aria-hidden="true"
        style={{ position: 'absolute', inset: 0, background: color.ink, opacity: 0.28 }}
      />
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void save();
        }}
        style={{
          position: 'relative',
          background: color.white,
          borderRadius: `${radius.deck}px ${radius.deck}px 0 0`,
          boxShadow: shadow.popover,
          padding: '16px 16px calc(env(safe-area-inset-bottom, 8px) + 16px)',
          maxHeight: '92%',
          overflowY: 'auto',
          animation: 'fadeup 0.25s',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <h2 style={{ margin: 0, fontFamily: font.sans, fontWeight: 600, fontSize: 18, lineHeight: '24px', color: color.ink }}>
            {title}
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="hov-tint"
            style={{ width: 32, height: 32, borderRadius: '50%', background: 'none', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 0 }}
          >
            <X size={18} color={color.muted} aria-hidden />
          </button>
        </div>
        {payment && !editing && (
          <div style={{ fontFamily: font.sans, fontSize: 12.5, color: color.faint, marginTop: 4 }}>
            This payment will count toward it.
          </div>
        )}

        <Labelled name="Name">
          <input
            autoFocus={!payment}
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Rent, EMI, Gym…"
            aria-label="Name"
            style={field}
          />
        </Labelled>
        <Labelled name="Amount" hint="each month">
          <input
            inputMode="decimal"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="₹"
            aria-label="Amount"
            style={field}
          />
        </Labelled>
        <Labelled name="Category" hint="payments in it count toward this">
          <select value={category} onChange={(e) => setCategory(e.target.value)} aria-label="Category" style={field}>
            <option value="" disabled>
              Pick one
            </option>
            {categories.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </Labelled>
        <Labelled name="Due day" hint="optional, 1 to 31">
          <input
            inputMode="numeric"
            value={due}
            onChange={(e) => setDue(e.target.value.replace(/\D/g, '').slice(0, 2))}
            placeholder="Not dated"
            aria-label="Due day"
            style={{ ...field, borderColor: dueOk ? color.border : color.red }}
          />
        </Labelled>

        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 16 }}>
          <span style={{ flex: 1, fontFamily: font.sans, fontSize: 14.5, color: color.ink }}>Repeats every month</span>
          <button
            type="button"
            role="switch"
            aria-checked={repeats}
            aria-label="Repeats every month"
            onClick={() => setRepeats(!repeats)}
            style={{
              width: 44,
              height: 26,
              borderRadius: radius.pill,
              border: 'none',
              padding: 3,
              cursor: 'pointer',
              background: repeats ? color.brand : color.ringIdle,
              display: 'flex',
              justifyContent: repeats ? 'flex-end' : 'flex-start',
              transition: 'background 0.15s',
            }}
          >
            <span style={{ width: 20, height: 20, borderRadius: '50%', background: color.white }} />
          </button>
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 20 }}>
          <button type="button" onClick={onClose} style={{ ...trayBtn, fontSize: 13, padding: '7px 14px' }}>
            Cancel
          </button>
          <button
            type="submit"
            disabled={!ok || busy}
            className="hov-brand"
            style={{ ...primaryBtn, opacity: ok && !busy ? 1 : 0.5, cursor: ok && !busy ? 'pointer' : 'default' }}
          >
            {editing ? 'Save' : 'Add'}
          </button>
        </div>
      </form>
    </div>
  );
}
