import { color, font } from '../theme';
import type { RingSpec } from '../types';

/**
 * The numbers for each arc, keyed to it by a colour dot. This is where the
 * figures live — the rings themselves stay clean. Figures are the interface
 * face at medium weight, tabular: numbers are data, not the agent's voice.
 */
export default function RingLegend({ rings }: { rings: RingSpec[] }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, minWidth: 0 }}>
      {rings.map((ring) => (
        <div key={ring.key} style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
          <span
            aria-hidden="true"
            style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              background: ring.color,
              marginTop: 5,
              flex: '0 0 auto',
            }}
          />
          <div style={{ minWidth: 0 }}>
            <div
              style={{
                fontFamily: font.sans,
                fontSize: 12.5,
                lineHeight: '16px',
                color: color.muted,
              }}
            >
              {ring.caption}
            </div>
            <div
              style={{
                fontFamily: font.sans,
                fontWeight: 500,
                fontSize: 16,
                lineHeight: '20px',
                color: color.ink,
                marginTop: 1,
                whiteSpace: 'nowrap',
              }}
            >
              {ring.valueStr}
              {ring.totalStr && (
                <span style={{ fontWeight: 400, fontSize: 13, color: color.faint }}> / {ring.totalStr}</span>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
