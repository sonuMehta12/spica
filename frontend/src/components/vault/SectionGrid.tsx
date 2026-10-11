import { color, font, radius } from '../../theme';
import { ToolIcon } from '../Icons';
import type { Section, SectionSummary } from '../../vault/stats';

interface Props {
  items: SectionSummary[];
  onOpen: (s: Section) => void;
}

/** The sections as tiles: white, a hairline, no lift — they sit in the page. */
export default function SectionGrid({ items, onOpen }: Props) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
      {items.map((s) => (
        <button
          key={s.key}
          type="button"
          onClick={() => onOpen(s.key)}
          className="hov-tint"
          style={{
            background: color.white,
            border: `1px solid ${color.line}`,
            borderRadius: radius.card,
            padding: 12,
            cursor: 'pointer',
            textAlign: 'left',
            fontFamily: font.sans,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <ToolIcon icon={s.icon} size={20} stroke={color.muted} />
            <span style={{ fontWeight: 500, fontSize: 20, lineHeight: '24px', color: color.ink }}>
              {s.count}
            </span>
          </div>
          <div style={{ fontWeight: 500, fontSize: 15, lineHeight: '20px', marginTop: 8, color: color.ink }}>
            {s.label}
          </div>
          <div
            style={{
              fontSize: 12,
              lineHeight: '16px',
              marginTop: 2,
              color: s.urgent ? color.ink : color.faint,
            }}
          >
            {s.hint}
          </div>
        </button>
      ))}
    </div>
  );
}
