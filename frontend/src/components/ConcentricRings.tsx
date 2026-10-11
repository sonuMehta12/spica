import { color, font } from '../theme';
import type { RingSpec } from '../types';

/**
 * Concentric arcs, outermost first. Deliberately number-free — the figures live
 * in the legend beside it, keyed by colour, so nothing can collide or clip.
 */

const SIZE = 148;
const C = SIZE / 2;
const STROKE = 8;
/** Outermost first; a mode uses as many slots as it has rings. */
const RADII = [66, 52, 38];

export default function ConcentricRings({ rings }: { rings: RingSpec[] }) {
  return (
    <svg
      viewBox={`0 0 ${SIZE} ${SIZE}`}
      style={{ width: '100%', height: 'auto', display: 'block' }}
      role="img"
      aria-label={rings
        .map((r) => `${r.caption} ${r.valueStr}${r.totalStr ? ` of ${r.totalStr}` : ''}`)
        .join('. ')}
    >
      {/* rotated so every arc starts at twelve o'clock */}
      <g transform={`rotate(-90 ${C} ${C})`}>
        {rings.map((ring, i) => {
          const r = RADII[i] ?? RADII[RADII.length - 1];
          const len = 2 * Math.PI * r;
          // NaN sails straight through Math.min/Math.max and lands in the SVG
          // as an invalid attribute. A pct that is not a finite number means
          // "no denominator", and draws nothing.
          const pct = Number.isFinite(ring.pct) ? ring.pct : 0;
          const basePct = Number.isFinite(ring.basePct) ? (ring.basePct as number) : 0;
          const total = Math.min(1, Math.max(0, pct)) * len;
          const base = Math.min(total, Math.max(0, basePct) * len);
          const live = Math.max(0, total - base);
          return (
            <g key={ring.key}>
              <circle cx={C} cy={C} r={r} fill="none" stroke={color.ringIdle} strokeWidth={STROKE} />
              {/* Committed portion: same hue, dialled back — so the arc still
                  keys to this ring's legend dot instead of reading as a
                  separate grey series. */}
              {base > 0 && (
                <circle
                  cx={C}
                  cy={C}
                  r={r}
                  fill="none"
                  stroke={ring.color}
                  strokeOpacity={0.45}
                  strokeWidth={STROKE}
                  strokeDasharray={`${base} ${len - base}`}
                />
              )}
              <circle
                cx={C}
                cy={C}
                r={r}
                fill="none"
                stroke={ring.color}
                strokeWidth={STROKE}
                // A round cap would bleed back over the committed segment —
                // and on an empty arc it paints a lone dot at twelve o'clock,
                // where "no denominator" should draw nothing at all.
                strokeLinecap={base > 0 || live === 0 ? 'butt' : 'round'}
                strokeDasharray={`${live} ${len - live}`}
                strokeDashoffset={-base}
                style={{
                  transition: 'stroke-dasharray 0.6s cubic-bezier(0.4,0,0.2,1), stroke 0.4s',
                }}
              />
            </g>
          );
        })}
      </g>
    </svg>
  );
}

/** Same footprint as the arcs, for pages with no data behind them. */
export function DormantRing({ glyph }: { glyph: string }) {
  return (
    <div
      style={{
        width: 128,
        height: 128,
        flex: '0 0 auto',
        borderRadius: '50%',
        border: `2px dashed ${color.ringIdle}`,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontFamily: font.sans,
        fontWeight: 600,
        fontSize: 36,
        color: color.grey,
      }}
    >
      {glyph}
    </div>
  );
}
