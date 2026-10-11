import { color, font } from '../../theme';
import type { BreakdownRow } from '../../report/metrics';

const SIZE = 128;
const C = SIZE / 2;
const R = 48;
const STROKE = 20;
const LEN = 2 * Math.PI * R;

interface Props {
  rows: BreakdownRow[];
  /** null = everything. Otherwise the row whose slice is in focus. */
  selected: string | null;
  totalStr: string;
  /** The line under the centre figure when nothing is selected. */
  centreSub: string;
  /**
   * How much of the ring the segments occupy. The full circle is the money that
   * came in, so a period's spend fills only its share — the rest stays track.
   * null when the ring has no such cap and the segments are the whole of it.
   */
  fill: { share: number; capStr: string } | null;
}

/**
 * One ring, one legend. Selecting a category dims the rest and puts that slice's
 * figure in the middle, so the tab strip has somewhere to land — no callouts to
 * collide, nothing to clip.
 */
export default function DonutChart({ rows, selected, totalStr, centreSub, fill }: Props) {
  let offset = 0;
  const scale = fill ? Math.min(1, Math.max(0, fill.share)) : 1;
  const focus = selected ? rows.find((r) => r.label === selected) : null;

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 7, minWidth: 0 }}>
        {rows.map((r) => {
          const dim = focus ? r.label !== focus.label : false;
          return (
            <div
              key={r.label}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                opacity: dim ? 0.35 : 1,
                transition: 'opacity 0.2s',
              }}
            >
              <span
                aria-hidden="true"
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  background: r.color,
                  flex: '0 0 auto',
                }}
              />
              <span
                style={{
                  flex: 1,
                  fontSize: 13,
                  minWidth: 0,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {r.label}
              </span>
              <span
                style={{
                  fontFamily: font.sans,
                  fontSize: 11.5,
                  color: color.faint,
                  whiteSpace: 'nowrap',
                }}
              >
                {Math.round(r.share * 100)}%
              </span>
            </div>
          );
        })}
      </div>

      <div style={{ position: 'relative', flex: '0 0 auto', width: SIZE, height: SIZE }}>
        <svg
          width={SIZE}
          height={SIZE}
          viewBox={`0 0 ${SIZE} ${SIZE}`}
          style={{ transform: 'rotate(-90deg)' }}
          role="img"
          aria-label={rows.map((r) => `${r.label} ${Math.round(r.share * 100)}%`).join(', ')}
        >
          <circle cx={C} cy={C} r={R} fill="none" stroke={color.ringIdle} strokeWidth={STROKE} />
          {rows.map((r) => {
            const seg = r.share * scale * LEN;
            const dim = focus ? r.label !== focus.label : false;
            const arc = (
              <circle
                key={r.label}
                cx={C}
                cy={C}
                r={R}
                fill="none"
                stroke={r.color}
                strokeWidth={STROKE}
                strokeDasharray={`${seg} ${LEN - seg}`}
                strokeDashoffset={-offset}
                opacity={dim ? 0.22 : 1}
                style={{ transition: 'opacity 0.2s' }}
              />
            );
            offset += seg;
            return arc;
          })}
        </svg>

        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            pointerEvents: 'none',
          }}
        >
          <span
            style={{
              fontFamily: font.sans,
              fontWeight: 500,
              fontSize: focus ? 15 : 16,
              lineHeight: 1,
              // Ink, not the slice's colour: a soft hue as text is unreadable,
              // and the dimmed slices already say which one this is.
              color: color.ink,
            }}
          >
            {focus ? focus.valueStr : totalStr}
          </span>
          <span
            style={{
              fontFamily: font.sans,
              fontSize: 11,
              color: color.faint,
              marginTop: 4,
              textAlign: 'center',
              lineHeight: 1.4,
            }}
          >
            {focus
              ? `${Math.round(focus.share * 100)}% of spend`
              : fill
                ? `${Math.round(fill.share * 100)}% of ${fill.capStr}`
                : centreSub}
          </span>
        </div>
      </div>
    </div>
  );
}
