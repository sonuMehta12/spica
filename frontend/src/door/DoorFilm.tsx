import { useEffect, useRef, useState } from 'react';
import { color, font } from '../theme';
import { CAPTIONS, LAYOUT, MARK, MARK_INK, STAGE, WEEKDAYS, frame } from './filmDots';

/**
 * The door's film: a life slipping out of hand, put in order, becoming
 * results — told only in dots. spec/done/onboarding-goals.md § 1 · The door.
 *
 * One clock and one SVG. The clock is film time, not wall time: each frame
 * adds at most 100 ms, so a tab that was hidden resumes where it was rather
 * than jumping. Everything drawn is `frame(ms)` — nothing here decides where a
 * dot goes. No sound, no controls, no labels.
 *
 * Reduced motion is followed live: the film holds its seven settled frames,
 * each for its own stretch of the same clock.
 */

const LABEL =
  'A short film in dots: a life slipping out of hand is put in order, and becomes results.';

/** The longest step one frame may take, so a hidden tab does not leap ahead. */
const MAX_STEP = 100;

/**
 * A debugging hold: `?filmMs=12500` on the door freezes the film at that
 * millisecond, for checking it against the prototype. Dev builds only.
 */
function frozenAt(): number | null {
  if (!import.meta.env.DEV) return null;
  const raw = new URLSearchParams(window.location.search).get('filmMs');
  const ms = raw == null ? NaN : Number(raw);
  return Number.isFinite(ms) && ms >= 0 ? ms : null;
}

const REDUCE = '(prefers-reduced-motion: reduce)';

function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(() => window.matchMedia?.(REDUCE).matches ?? false);
  useEffect(() => {
    const mq = window.matchMedia?.(REDUCE);
    if (!mq) return;
    const change = () => setReduced(mq.matches);
    mq.addEventListener('change', change);
    return () => mq.removeEventListener('change', change);
  }, []);
  return reduced;
}

/** The film's clock, in ms. The first loop starts still at beat 0. */
function useFilmClock(frozen: number | null): number {
  const [ms, setMs] = useState(frozen ?? 0);
  useEffect(() => {
    if (frozen != null) return;
    let last: number | null = null;
    let raf = 0;
    const tick = (now: number) => {
      const step = last == null ? 0 : Math.min(MAX_STEP, Math.max(0, now - last));
      last = now;
      if (step) setMs((m) => m + step);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [frozen]);
  return ms;
}

/** The stage's scale in its slot: whole, centred, and never past one unit to one px. */
function useFit(): [React.RefObject<HTMLDivElement | null>, number] {
  const box = useRef<HTMLDivElement>(null);
  const [k, setK] = useState(0);
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const fit = () => setK(Math.min(1, el.clientWidth / STAGE.w, el.clientHeight / STAGE.h));
    fit();
    const ro = new ResizeObserver(fit);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [box, k];
}

/** Lines of text centred in their own line boxes, from a block's top. */
function Lines({
  lines,
  top,
  lineHeight,
  style,
}: {
  lines: readonly string[];
  top: number;
  lineHeight: number;
  style: React.CSSProperties;
}) {
  return (
    <text textAnchor="middle" dominantBaseline="central" style={style}>
      {lines.map((line, n) => (
        <tspan key={n} x={STAGE.w / 2} y={top + lineHeight * n + lineHeight / 2}>
          {line}
        </tspan>
      ))}
    </text>
  );
}

export default function DoorFilm() {
  const reduced = useReducedMotion();
  const ms = useFilmClock(frozenAt());
  const [box, k] = useFit();
  const f = frame(ms, reduced);

  const { mark, days, figure, captions } = LAYOUT;
  const markCx = mark.x + mark.size / 2;
  const markCy = mark.y + mark.size / 2;
  const serif = { fontFamily: font.display, fill: color.ink };

  return (
    <div
      ref={box}
      style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
    >
      {k > 0 && (
        <svg
          role="img"
          aria-label={LABEL}
          width={STAGE.w * k}
          height={STAGE.h * k}
          viewBox={`0 0 ${STAGE.w} ${STAGE.h}`}
          style={{ display: 'block', flex: '0 0 auto' }}
        >
          {/* The small mark: arrives with the order, scaled about its centre. */}
          <g
            opacity={f.mark.opacity}
            transform={`translate(${markCx} ${markCy}) scale(${f.mark.scale}) translate(${-mark.size / 2} ${-mark.size / 2}) scale(${mark.size / 96})`}
            fill={color[MARK_INK]}
          >
            {MARK.map((m, i) => (
              <circle key={i} cx={m.x} cy={m.y} r={m.r} />
            ))}
          </g>

          <g opacity={f.days.opacity} style={{ fontFamily: font.sans, fontSize: days.size, fill: color.faint }}>
            {WEEKDAYS.map((d, i) => (
              <text
                key={i}
                x={STAGE.w / 2 + (i - (WEEKDAYS.length - 1) / 2) * days.cell}
                y={days.top + days.lineHeight / 2}
                textAnchor="middle"
                dominantBaseline="central"
              >
                {d}
              </text>
            ))}
          </g>

          {f.dots.map((d, i) => (
            <circle
              key={i}
              cx={d.x + d.size / 2 + d.jx}
              cy={d.y + d.size / 2 + d.jy}
              r={d.size / 2}
              fill={d.fill}
              opacity={d.opacity}
            />
          ))}

          {/* The outcome: a figure, in the scene's ink, over the agent's line. */}
          <g opacity={f.figure.opacity} transform={`translate(0 ${f.figure.drop})`}>
            <Lines
              lines={[f.figure.text]}
              top={figure.top}
              lineHeight={figure.lineHeight}
              style={{
                fontFamily: font.sans,
                fontSize: figure.size,
                fontWeight: 500,
                letterSpacing: figure.tracking,
                fill: color[f.figure.ink],
              }}
            />
            <Lines
              lines={[f.figure.line]}
              top={figure.lineTop}
              lineHeight={figure.lineLineHeight}
              style={{ ...serif, fontSize: figure.lineSize }}
            />
          </g>

          {CAPTIONS.map((lines, n) => (
            <g key={n} opacity={f.captions[n]}>
              <Lines
                lines={lines}
                top={captions[n].top}
                lineHeight={captions[n].lineHeight}
                style={{ ...serif, fontSize: captions[n].size, fontWeight: captions[n].weight }}
              />
            </g>
          ))}
        </svg>
      )}
    </div>
  );
}
