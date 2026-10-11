import { dayLabel } from '../../lib/format';
import { X } from '@phosphor-icons/react';
import { color, font } from '../../theme';
import type { SavedItem } from '../../data/vault';

const row = {
  padding: '10px 8px 10px 14px',
  display: 'flex',
  gap: 10,
  alignItems: 'flex-start',
  justifyContent: 'space-between',
};

interface Props {
  items: SavedItem[];
  onDrop: (id: string) => void;
}

export default function SectionList({ items, onDrop }: Props) {
  const shell = {
    background: color.white,
    border: `1px solid ${color.line}`,
    borderRadius: 14,
    overflow: 'hidden' as const,
  };

  // Pantry and Dishes have their own components: they read the live ledger.

  return (
    <div style={shell}>
      {items.map((it, i) => (
        <div key={it.id} style={{ ...row, borderTop: i ? `1px solid ${color.lineSoft}` : 'none' }}>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 13.5, fontWeight: 500, lineHeight: 1.35 }}>{it.title}</div>
            <div
              style={{ fontFamily: font.sans, fontSize: 11, color: color.faint, marginTop: 3 }}
            >
              {it.source} · {dayLabel(it)}
              {!it.used && ' · not opened yet'}
            </div>
            {it.link && (
              <div style={{ fontFamily: font.sans, fontSize: 11, color: color.brand, marginTop: 2 }}>
                ↳ {it.link}
              </div>
            )}
          </div>
          <button
            type="button"
            onClick={() => onDrop(it.id)}
            aria-label={`Remove — ${it.title}`}
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
              flex: '0 0 auto',
            }}
          >
            <X size={16} color={color.faint} aria-hidden />
          </button>
        </div>
      ))}
    </div>
  );
}
