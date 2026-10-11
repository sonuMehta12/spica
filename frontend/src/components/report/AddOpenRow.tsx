import { useState, type KeyboardEvent } from 'react';
import { Plus } from '@phosphor-icons/react';
import { color, font } from '../../theme';
import { useBack } from '../../state/nav';

/**
 * "+ Lent" / "+ Borrowed": who, and how much. Two fields, because nothing else
 * can create a lending or a borrowing until the agent does — the same
 * allowance the Profile and Pantry pages have. spec/in-progress/udhaar-borrowed.md.
 */
interface Props {
  leg: 'lent' | 'borrowed';
  onAdd: (leg: 'lent' | 'borrowed', who: string, amount: number) => Promise<boolean>;
}

const field = {
  fontFamily: font.sans,
  fontSize: 14,
  color: color.ink,
  background: color.white,
  border: `1px solid ${color.border}`,
  borderRadius: 10,
  padding: '7px 10px',
  outline: 'none',
  minWidth: 0,
};

export default function AddOpenRow({ leg, onAdd }: Props) {
  const [open, setOpen] = useState(false);
  const [who, setWho] = useState('');
  const [amt, setAmt] = useState('');
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);

  const reset = () => {
    setOpen(false);
    setWho('');
    setAmt('');
    setFailed(false);
  };
  // Back closes the form before it leaves the Report.
  useBack(open, reset);
  const save = async () => {
    if (busy) return;
    setBusy(true);
    const ok = await onAdd(leg, who, Number(amt));
    setBusy(false);
    if (ok) reset();
    else setFailed(true);
  };
  const keys = (e: KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      void save();
    } else if (e.key === 'Escape') {
      e.preventDefault();
      reset();
    }
  };

  if (!open) {
    return (
      <button
        type="button"
        className="hov-tint"
        onClick={() => setOpen(true)}
        style={{
          width: '100%',
          marginTop: 10,
          background: 'none',
          border: 'none',
          padding: '10px 14px',
          textAlign: 'left',
          fontFamily: font.sans,
          fontSize: 14,
          fontWeight: 500,
          color: color.brand,
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          gap: 6,
        }}
      >
        <Plus size={15} aria-hidden />
        {leg === 'lent' ? 'Lent' : 'Borrowed'}
      </button>
    );
  }

  return (
    <div
      style={{
        marginTop: 10,
        background: color.white,
        border: `1px solid ${color.line}`,
        borderRadius: 14,
        padding: '12px 13px',
        display: 'grid',
        gap: 8,
      }}
    >
      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        <input
          autoFocus
          placeholder={leg === 'lent' ? 'who you gave it to' : 'who you took it from'}
          value={who}
          onChange={(e) => setWho(e.target.value)}
          onKeyDown={keys}
          style={{ ...field, flex: 1, fontFamily: font.sans }}
        />
        <span style={{ fontFamily: font.sans, fontSize: 12.5, color: color.muted }}>₹</span>
        <input
          inputMode="numeric"
          placeholder="0"
          value={amt}
          onChange={(e) => setAmt(e.target.value)}
          onKeyDown={keys}
          style={{ ...field, width: 96 }}
        />
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ fontFamily: font.sans, fontSize: 11.5, color: failed ? color.red : color.muted, flex: 1 }}>
          {failed ? 'Not saved — a name and an amount above zero.' : 'Today. Enter saves.'}
        </span>
        <button
          type="button"
          onClick={reset}
          style={{ fontFamily: font.sans, fontSize: 12, color: color.muted, background: 'none', border: 'none', cursor: 'pointer', padding: '7px 6px' }}
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={() => void save()}
          disabled={busy}
          className="hov-brand"
          style={{ fontFamily: font.sans, fontSize: 13, fontWeight: 500, color: color.white, background: color.brand, border: 'none', borderRadius: 999, padding: '7px 14px', cursor: 'pointer', opacity: busy ? 0.6 : 1 }}
        >
          {busy ? 'Saving…' : 'Save'}
        </button>
      </div>
    </div>
  );
}
