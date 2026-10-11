import { dayLabel } from '../../lib/format';
import { color, font } from '../../theme';
import type { SavedItem } from '../../data/vault';

/** Only the freshest few are shown; the rest wait rather than becoming a wall. */
const VISIBLE = 3;

interface Props {
  items: SavedItem[];
  onConfirm: (id: string) => void;
  onDrop: (id: string) => void;
}

/**
 * Captures the agent filed but wasn't confident about. Passive capture means
 * wrong guesses, so the correction lives here rather than in the chat.
 */
export default function InboxCard({ items, onConfirm, onDrop }: Props) {
  return (
    <div
      style={{
        background: color.white,
        border: `1px solid ${color.line}`,
        borderRadius: 14,
        overflow: 'hidden',
      }}
    >
      {items.slice(0, VISIBLE).map((i, idx) => (
        <div
          key={i.id}
          style={{
            padding: '11px 13px',
            borderTop: idx ? `1px solid ${color.lineSoft}` : 'none',
          }}
        >
          <div style={{ fontSize: 13.5, fontWeight: 500, lineHeight: 1.35 }}>{i.title}</div>
          <div
            style={{
              fontFamily: font.sans,
              fontSize: 11,
              color: color.faint,
              marginTop: 3,
            }}
          >
            {i.source} · {dayLabel(i)} · {Math.round(i.confidence * 100)}% sure
          </div>
          <div style={{ display: 'flex', gap: 7, alignItems: 'center', marginTop: 8 }}>
            <button
              type="button"
              onClick={() => onConfirm(i.id)}
              style={{
                fontFamily: font.sans,
                fontSize: 12,
                fontWeight: 500,
                padding: '5px 12px',
                borderRadius: 999,
                border: 'none',
                background: color.brand,
                color: color.white,
                cursor: 'pointer',
              }}
            >
              {i.category} ✓
            </button>
            <button
              type="button"
              onClick={() => onDrop(i.id)}
              style={{
                fontFamily: font.sans,
                fontSize: 12,
                fontWeight: 500,
                padding: '5px 12px',
                borderRadius: 999,
                border: `1px solid ${color.redBorder}`,
                background: color.redSurface,
                color: color.red,
                cursor: 'pointer',
              }}
            >
              Remove
            </button>
          </div>
        </div>
      ))}
      {items.length > VISIBLE && (
        <div
          style={{
            padding: '9px 13px',
            borderTop: `1px solid ${color.lineSoft}`,
            fontFamily: font.sans,
            fontSize: 11,
            color: color.faint,
          }}
        >
          {items.length - VISIBLE} more in the inbox
        </div>
      )}
    </div>
  );
}
