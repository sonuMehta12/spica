import type { CSSProperties } from 'react';
import { color } from '../theme';

/** `saving` is the one-shot beat; `done` is the same beat, then held at rest
 *  — the newest reply wears it until the next turn starts, so "this is the
 *  one I just finished" is visible without a word. */
export type MascotState = 'still' | 'idle' | 'thinking' | 'saving' | 'done' | 'listening';

/**
 * Below this, the diagonal dots land under a pixel and the mark turns to
 * speckle. Small sizes get their own build rather than a shrunk one — the same
 * way an app icon differs from its own marketing art.
 */
const COMPACT_BELOW = 24;

/** Below this, the full build's outer dots gain half a unit so they keep their weight. */
const HEAVY_BELOW = 48;

interface Props {
  size?: number;
  state?: MascotState;
  /** Force the reduced build regardless of size. */
  compact?: boolean;
}

/** One outer dot, in 96-unit space, with its turn in the thinking pulse (seconds). */
interface Dot {
  x: number;
  y: number;
  r: number;
  delay: number;
}

/**
 * Clockwise from the top. A mid dot every 0.3 s, and each diagonal 0.15 s
 * behind the mid dot before it: one wave round the ring, 1.2 s a lap.
 */
const ring = (mid: number, diagonal: number): Dot[] => [
  { x: 48, y: 20, r: mid, delay: 0 },
  { x: 68, y: 28, r: diagonal, delay: 0.15 },
  { x: 76, y: 48, r: mid, delay: 0.3 },
  { x: 68, y: 68, r: diagonal, delay: 0.45 },
  { x: 48, y: 76, r: mid, delay: 0.6 },
  { x: 28, y: 68, r: diagonal, delay: 0.75 },
  { x: 20, y: 48, r: mid, delay: 0.9 },
  { x: 28, y: 28, r: diagonal, delay: 1.05 },
];

/**
 * The full build, exported for anything that draws the mark out of its parts
 * — the door's film flies its dots into exactly these places, so the mark it
 * builds cannot drift from this one.
 */
export const FULL = ring(6, 3.5);
/** The full build's centre dot. */
export const CORE = { x: 48, y: 48, r: 10 } as const;
const HEAVY = ring(6.5, 4);

/** The compact build: no diagonals, and the four mid dots heavier and further out. */
const COMPACT: Dot[] = [
  { x: 48, y: 18, r: 8, delay: 0 },
  { x: 78, y: 48, r: 8, delay: 0.3 },
  { x: 48, y: 78, r: 8, delay: 0.6 },
  { x: 18, y: 48, r: 8, delay: 0.9 },
];

/**
 * Spica, as a constellation.
 *
 * Every dot is one colour, the brand. Motion moves dots, never resizes the
 * outer ones: each outer dot travels along its own spoke from the centre
 * (`--dx`, `--dy` are that spoke), so the mark keeps its shape whatever state
 * it is in.
 *
 * Animation lives in `global.css` under `.cx-mascot`, keyed off `data-state`,
 * so it runs on the compositor and costs nothing per frame here.
 *
 * `still` is a real state, not an absence of one: a mark beside a message from
 * ten minutes ago is a portrait. Exactly one mark animates at a time — a column
 * of pulsing avatars reads as a glitch, not as life.
 */
export default function Mascot({ size = 200, state = 'idle', compact }: Props) {
  const small = compact ?? size < COMPACT_BELOW;
  const dots = small ? COMPACT : size < HEAVY_BELOW ? HEAVY : FULL;

  return (
    <svg
      className="cx-mascot"
      data-state={state}
      data-build={small ? 'compact' : 'full'}
      width={size}
      height={size}
      viewBox="0 0 96 96"
      aria-hidden="true"
    >
      <g fill={color.brand}>
        {dots.map((d, i) => (
          <circle
            key={i}
            className="cx-dot"
            cx={d.x}
            cy={d.y}
            r={d.r}
            style={{ '--dx': `${d.x - 48}px`, '--dy': `${d.y - 48}px`, '--delay': `${d.delay}s` } as CSSProperties}
          />
        ))}
        <circle className="cx-core" cx={CORE.x} cy={CORE.y} r={small ? 12 : CORE.r} />
      </g>
    </svg>
  );
}
