import { BRAND } from '../brand';
import { CORE, FULL } from '../components/Mascot';
import { color } from '../theme';

/**
 * The door's film, as data and one pure function. spec/done/onboarding-goals.md
 * § 1 · The door; the frozen contract is `spec/reference/onboarding-film.dc.html`.
 *
 * The approved prototype had no clock: a 500 ms tick set new targets and CSS
 * transitions did every frame in between. This is that, written down. A
 * per-beat target table says where everything should be on each beat, and
 * `frame(ms)` applies the browser's transition rules to it explicitly — each
 * channel eases from its *current* value whenever its target changes, keeps
 * running when it does not, and a fade reversed part-way takes only as long
 * as it had run (CSS Transitions § 3). So the film can be frozen at any
 * millisecond, and checked against the prototype number for number.
 *
 * The phone keeps the same table in `logic/FilmDots.kt`, with the same names
 * in the same order — the way `theme.ts` and `Tokens.kt` are kept. Colours are
 * token names, never hex: the two films are drawn from one palette.
 *
 * Nothing here is random. The scatter is arithmetic on the dot's index and the
 * jitter a keyframe with a per-dot delay, so it is ported as it was.
 */

/** A colour, by its token name in `theme.ts`. */
export type Token = keyof typeof color;

/** Dots on screen. */
export const N = 28;
/** One beat. */
export const BEAT_MS = 500;
/** Beats in a loop: 22 s. */
export const LOOP = 44;
export const LOOP_MS = LOOP * BEAT_MS;

/** The acts, by their first beat: mess 0–9, order 10–14, outcome 15–34, close 35–43. */
export const ORDER_FROM = 10;
export const OUTCOME_FROM = 15;
export const CLOSE_FROM = 35;
/** Beats in one outcome scene; its figure shows from the scene's second beat. */
export const SCENE_BEATS = 5;

/** The stage, in units: one unit is one px at full size, and never more. */
export const STAGE = { w: 390, h: 560 } as const;

/**
 * The mess: dot `i` takes `MESS[i % 8]`. Red was the sixth in the prototype;
 * red means *over* everywhere in the app, so it is `dietSoft` here.
 */
export const MESS: readonly Token[] = ['paisa', 'diet', 'work', 'dietInk', 'grey', 'dietSoft', 'paisaSoft', 'workSoft'];
/** The order: one colour per row of the month. */
export const ROWS: readonly Token[] = ['paisa', 'dietInk', 'diet', 'work'];
/** A missed day in an outcome scene: an empty track, not a judgement. */
export const MISSED: Token = 'ringIdle';
/** The mark, small and built. */
export const MARK_INK: Token = 'brand';

/**
 * The four outcomes, one person's month — the dots are days, the figure what
 * they added up to. Marketing, told as such; never written anywhere.
 */
export interface Win {
  figure: string;
  line: string;
  hue: Token;
  ink: Token;
  missed: readonly number[];
}
export const WINS: readonly Win[] = [
  { figure: '₹15,000', line: 'saved this month.', hue: 'paisa', ink: 'paisaInk', missed: [4, 13, 22] },
  { figure: '−2 kg', line: 'this month, and counting.', hue: 'diet', ink: 'dietInk', missed: [5, 6, 17, 26] },
  { figure: '6 hours', line: 'a week, back for you.', hue: 'work', ink: 'workInk', missed: [9, 23] },
  { figure: '4 weeks', line: 'at the gym. Started, and stuck.', hue: 'dietInk', ink: 'dietInk', missed: [] },
];

export const WEEKDAYS: readonly string[] = ['M', 'T', 'W', 'T', 'F', 'S', 'S'];

/** The three captions, each a list of lines. */
export const CAPTIONS: readonly (readonly string[])[] = [
  ['Money slipping. Time slipping.', 'Health slipping.'],
  [`${BRAND} puts it in order.`],
  ['Time for what matters.'],
];

/**
 * Where the text sits, in stage units, as the prototype laid it out: a block's
 * top and its line height (each line is centred in its own line box).
 */
export const LAYOUT = {
  /** The small mark: a 34-unit square, scaled about its centre. */
  mark: { x: 178, y: 22, size: 34 },
  /** The weekday row: seven 34-unit cells centred on the stage, 12-unit text. */
  days: { top: 112, cell: 34, size: 12, lineHeight: 16 },
  /** The figure (46 on 50, −1 tracking) and its serif line (18 on 25, 2 below). */
  figure: { top: 300, size: 46, lineHeight: 50, tracking: -1, lineTop: 352, lineSize: 18, lineLineHeight: 25 },
  /** The captions: mess, order, close. */
  captions: [
    { top: 474, size: 20, lineHeight: 27, weight: 400 },
    { top: 316, size: 20, lineHeight: 27, weight: 400 },
    { top: 352, size: 28, lineHeight: 34, weight: 500 },
  ],
} as const;

/**
 * The mark the close builds, in the prototype's order: the centre, the four
 * mid dots (top, right, bottom, left), then the diagonals (top-right,
 * bottom-right, bottom-left, top-left). Dot `i` flies to `MARK[i]`; dots 9–27
 * fly to the centre and fade. `FULL` runs clockwise from the top.
 */
export const MARK: readonly { x: number; y: number; r: number }[] = [
  CORE, FULL[0], FULL[2], FULL[4], FULL[6], FULL[1], FULL[3], FULL[5], FULL[7],
];
/** The close's mark: centred here, at twice the 96-unit grid. */
export const CLOSE = { cx: 195, cy: 236, scale: 2 } as const;

/** Reduced motion holds these beats, each until the next: every act's settled frame, one per outcome scene. */
export const HOLDS: readonly number[] = [9, 14, 19, 24, 29, 34, 43];

/* ── timing ─────────────────────────────────────────────────────────────── */

export type EaseName = 'settle' | 'ease' | 'easeInOut';

/** CSS's curves: `settle` is the prototype's cubic-bezier(.2,.75,.2,1). */
export const CURVES: Record<EaseName, readonly [number, number, number, number]> = {
  settle: [0.2, 0.75, 0.2, 1],
  ease: [0.25, 0.1, 0.25, 1],
  easeInOut: [0.42, 0, 0.58, 1],
};

interface Timing {
  ms: number;
  ease: EaseName;
}

/** Each channel's transition, as the prototype's stylesheet set it. */
export const TIMING = {
  /** A dot's left and top. */
  position: { ms: 1000, ease: 'settle' },
  /** A dot's width and height. */
  size: { ms: 700, ease: 'ease' },
  /** A dot's colour. */
  colour: { ms: 700, ease: 'ease' },
  /** A dot's opacity. */
  opacity: { ms: 600, ease: 'ease' },
  /** The small mark's opacity, and its scale about its centre (0.6 hidden, 1 shown). */
  markOpacity: { ms: 700, ease: 'ease' },
  markScale: { ms: 900, ease: 'settle' },
  /** The weekday row, the figure and the captions: opacity, and the figure's lift. */
  fade: { ms: 650, ease: 'ease' },
  lift: { ms: 750, ease: 'settle' },
} as const satisfies Record<string, Timing>;

/**
 * The mess's shake: a 700 ms keyframe, eased in and out between keys, offset
 * per dot by `(i × 113) mod 700` ms. It runs only in the mess and stops dead
 * at the order, as the prototype's class swap did.
 */
export const JITTER = {
  ms: 700,
  stagger: 113,
  ease: 'easeInOut' as EaseName,
  keys: [0, 0.2, 0.4, 0.6, 0.8, 1] as readonly number[],
  offsets: [[0, 0], [3, -2], [-2, 3], [2, 2], [-3, -1], [0, 0]] as readonly (readonly [number, number])[],
};

/* ── the table ──────────────────────────────────────────────────────────── */

/** Where one dot should be on a beat. `x`, `y` are its box's top-left corner. */
export interface DotTarget {
  x: number;
  y: number;
  size: number;
  opacity: number;
  fill: Token;
  /** Shaking: the mess only. */
  jitter: boolean;
}

export interface Targets {
  dots: DotTarget[];
  markOpacity: number;
  markScale: number;
  daysOpacity: number;
  figureOpacity: number;
  /** The figure block's drop below its place while hidden. */
  figureDrop: number;
  captions: [number, number, number];
}

const sceneOf = (beat: number) => Math.min(3, Math.floor((beat - OUTCOME_FROM) / SCENE_BEATS));

/** Every target on one beat (0–43). The prototype's `renderVals`, as data. */
export function targets(beat: number): Targets {
  const t = ((beat % LOOP) + LOOP) % LOOP;
  const mess = t < ORDER_FROM;
  const order = t >= ORDER_FROM && t < OUTCOME_FROM;
  const outcome = t >= OUTCOME_FROM && t < CLOSE_FROM;
  const close = t >= CLOSE_FROM;
  const win = WINS[outcome ? sceneOf(t) : 0];

  const dots: DotTarget[] = [];
  for (let i = 0; i < N; i++) {
    let x: number;
    let y: number;
    let size: number;
    let opacity = 1;
    let fill: Token;
    if (mess) {
      // Scattered, shaking and sliding down: the month slipping away.
      x = 18 + ((i * 97 + 31) % 340);
      y = 40 + ((i * 131 + 17) % 300) + t * (6 + (i % 5) * 3);
      size = 9 + (i % 4) * 3;
      fill = MESS[i % MESS.length];
      opacity = y > 470 ? 0 : 1;
    } else if (close) {
      const m = MARK[i < MARK.length ? i : 0];
      size = m.r * 4;
      x = CLOSE.cx + (m.x - 48) * CLOSE.scale - size / 2;
      y = CLOSE.cy + (m.y - 48) * CLOSE.scale - size / 2;
      opacity = i < MARK.length ? 1 : 0;
      fill = MARK_INK;
    } else {
      const col = i % 7;
      const row = Math.floor(i / 7);
      size = 16;
      x = 93 + col * 34 - size / 2;
      y = 150 + row * 34 - size / 2;
      fill = order ? ROWS[row] : win.missed.includes(i) ? MISSED : win.hue;
    }
    dots.push({ x: Math.round(x), y: Math.round(y), size, opacity, fill, jitter: mess });
  }

  const shown = shownOn(t);
  return {
    dots,
    markOpacity: order || outcome ? 1 : 0,
    markScale: order || outcome ? 1 : 0.6,
    daysOpacity: outcome ? 1 : 0,
    figureOpacity: shown ? 1 : 0,
    figureDrop: shown ? 0 : 10,
    captions: [mess && t >= 2 ? 1 : 0, order && t >= 11 ? 1 : 0, close && t >= 36 ? 1 : 0],
  };
}

/** An outcome scene's figure is showing on this beat: from the scene's second beat. */
const shownOn = (t: number) => t >= OUTCOME_FROM && t < CLOSE_FROM && (t - OUTCOME_FROM) % SCENE_BEATS >= 1;

/* ── the transition rules ───────────────────────────────────────────────── */

/** CSS's cubic-bezier: Newton's method, then bisection — the way browsers solve it. */
function bezier([x1, y1, x2, y2]: readonly [number, number, number, number]): (p: number) => number {
  const cx = 3 * x1;
  const bx = 3 * (x2 - x1) - cx;
  const ax = 1 - cx - bx;
  const cy = 3 * y1;
  const by = 3 * (y2 - y1) - cy;
  const ay = 1 - cy - by;
  const sampleX = (t: number) => ((ax * t + bx) * t + cx) * t;
  const sampleY = (t: number) => ((ay * t + by) * t + cy) * t;
  const slopeX = (t: number) => (3 * ax * t + 2 * bx) * t + cx;
  const solve = (x: number) => {
    let t = x;
    for (let i = 0; i < 8; i++) {
      const err = sampleX(t) - x;
      if (Math.abs(err) < 1e-7) return t;
      const d = slopeX(t);
      if (Math.abs(d) < 1e-6) break;
      t -= err / d;
    }
    let lo = 0;
    let hi = 1;
    t = x;
    while (hi - lo > 1e-7) {
      const v = sampleX(t);
      if (Math.abs(v - x) < 1e-7) return t;
      if (x > v) lo = t;
      else hi = t;
      t = (lo + hi) / 2;
    }
    return t;
  };
  return (p) => (p <= 0 ? 0 : p >= 1 ? 1 : sampleY(solve(p)));
}

const EASE: Record<EaseName, (p: number) => number> = {
  settle: bezier(CURVES.settle),
  ease: bezier(CURVES.ease),
  easeInOut: bezier(CURVES.easeInOut),
};

/** `#RRGGBB` → [r, g, b]. Colours blend in sRGB, channel by channel, as a browser does. */
const rgb = (token: Token): number[] => {
  const hex = color[token];
  return [1, 3, 5].map((k) => parseInt(hex.slice(k, k + 2), 16));
};

/**
 * One channel's transition: running from `from` at `start` to `to` over `ms`,
 * or finished and holding `to`. `back` is CSS's reversing-adjusted start value
 * and `shorten` its reversing shortening factor.
 */
interface Seg {
  from: number[];
  to: number[];
  start: number;
  ms: number;
  ease: EaseName;
  back: number[];
  shorten: number;
}

const progress = (seg: Seg, ms: number) =>
  seg.ms <= 0 ? 1 : EASE[seg.ease](Math.min(1, Math.max(0, (ms - seg.start) / seg.ms)));

const at = (seg: Seg, ms: number): number[] => {
  const p = progress(seg, ms);
  return seg.from.map((f, k) => f + (seg.to[k] - f) * p);
};

const same = (a: number[], b: number[]) => a.every((v, k) => v === b[k]);

const held = (v: number[], timing: Timing): Seg => ({ from: v, to: v, start: -Infinity, ms: 0, ease: timing.ease, back: v, shorten: 1 });

/** A style change at `ms`, for one channel: CSS Transitions § 3, as the browser runs it. */
function retarget(seg: Seg, to: number[], ms: number, timing: Timing): Seg {
  // The same end: a running transition carries on, a finished one holds.
  if (same(seg.to, to)) return seg;
  // Nothing running: from where it rests, the full length.
  if (ms >= seg.start + seg.ms) return { from: seg.to, to, start: ms, ms: timing.ms, ease: timing.ease, back: seg.to, shorten: 1 };
  const now = at(seg, ms);
  // Already there: the running one is cancelled and nothing starts.
  if (same(now, to)) return held(to, timing);
  // Back where the running one came from: shortened by how far it got.
  if (same(seg.back, to)) {
    const shorten = Math.min(1, Math.max(0, Math.abs(progress(seg, ms) * seg.shorten + 1 - seg.shorten)));
    return { from: now, to, start: ms, ms: timing.ms * shorten, ease: timing.ease, back: seg.to, shorten };
  }
  return { from: now, to, start: ms, ms: timing.ms, ease: timing.ease, back: now, shorten: 1 };
}

/** A channel: what it reads from a beat's targets, and how it moves. */
interface Channel {
  read: (tg: Targets) => number[];
  timing: Timing;
}

const CHANNELS: Channel[] = [
  ...Array.from({ length: N }, (_, i): Channel[] => [
    { read: (tg) => [tg.dots[i].x], timing: TIMING.position },
    { read: (tg) => [tg.dots[i].y], timing: TIMING.position },
    { read: (tg) => [tg.dots[i].size], timing: TIMING.size },
    { read: (tg) => [tg.dots[i].opacity], timing: TIMING.opacity },
    { read: (tg) => rgb(tg.dots[i].fill), timing: TIMING.colour },
  ]).flat(),
  { read: (tg) => [tg.markOpacity], timing: TIMING.markOpacity },
  { read: (tg) => [tg.markScale], timing: TIMING.markScale },
  { read: (tg) => [tg.daysOpacity], timing: TIMING.fade },
  { read: (tg) => [tg.figureOpacity], timing: TIMING.fade },
  { read: (tg) => [tg.figureDrop], timing: TIMING.lift },
  { read: (tg) => [tg.captions[0]], timing: TIMING.fade },
  { read: (tg) => [tg.captions[1]], timing: TIMING.fade },
  { read: (tg) => [tg.captions[2]], timing: TIMING.fade },
];
/** Where the shared channels start, after five per dot. */
const MARK_CH = N * 5;

const BEATS = Array.from({ length: LOOP }, (_, t) => targets(t));

/** One loop: each beat's transition per channel, and whose figure is on screen. */
interface Table {
  segs: Seg[][];
  /**
   * The outcome whose figure shows. The prototype swapped the words the
   * moment a scene changed, while the old figure was still fading out; here
   * they change as the next one fades in. The timing does not move, and the
   * ink goes with the words.
   */
  figure: number[];
}

/**
 * Each beat's running transitions, for one loop, from the state it starts
 * in. The very first loop starts still on beat 0, as the prototype did on
 * mount; every later one starts where the first ended — nothing still moves
 * by beat 43 — so each repeats exactly.
 */
function build(entering: Seg[], figureFrom: number): Table {
  let now = entering;
  let shown = figureFrom;
  const segs: Seg[][] = [];
  const figure: number[] = [];
  for (let beat = 0; beat < LOOP; beat++) {
    const ms = beat * BEAT_MS;
    now = now.map((seg, c) => retarget(seg, CHANNELS[c].read(BEATS[beat]), ms, CHANNELS[c].timing));
    if (shownOn(beat)) shown = sceneOf(beat);
    segs.push(now);
    figure.push(shown);
  }
  return { segs, figure };
}

const FIRST = build(CHANNELS.map((ch) => held(ch.read(BEATS[0]), ch.timing)), 0);
const LATER = build(
  FIRST.segs[LOOP - 1].map((seg) => ({ ...seg, start: seg.start - LOOP_MS })),
  FIRST.figure[LOOP - 1],
);

/* ── a frame ────────────────────────────────────────────────────────────── */

export interface DotFrame {
  /** The dot's box, top-left, and its side: the prototype's `left`, `top`, `width`. */
  x: number;
  y: number;
  size: number;
  /** The shake, applied to the drawn dot only. */
  jx: number;
  jy: number;
  /** A CSS colour, already blended. */
  fill: string;
  opacity: number;
}

export interface Frame {
  dots: DotFrame[];
  mark: { opacity: number; scale: number };
  days: { opacity: number };
  figure: { opacity: number; drop: number; text: string; line: string; ink: Token };
  captions: [number, number, number];
}

/** The beat a moment falls on, and its milliseconds into the loop. */
function place(ms: number): { first: boolean; local: number; beat: number } {
  const t = Math.max(0, ms);
  const first = t < LOOP_MS;
  const local = first ? t : (t - LOOP_MS) % LOOP_MS;
  return { first, local, beat: Math.min(LOOP - 1, Math.floor(local / BEAT_MS)) };
}

/** The shake of dot `i`, `local` ms into a loop. */
function jitter(i: number, local: number): [number, number] {
  const phase = ((local + ((i * JITTER.stagger) % JITTER.ms)) % JITTER.ms) / JITTER.ms;
  let k = 0;
  while (k < JITTER.keys.length - 2 && phase >= JITTER.keys[k + 1]) k++;
  const span = JITTER.keys[k + 1] - JITTER.keys[k];
  const p = EASE[JITTER.ease]((phase - JITTER.keys[k]) / span);
  const [ax, ay] = JITTER.offsets[k];
  const [bx, by] = JITTER.offsets[k + 1];
  return [ax + (bx - ax) * p, ay + (by - ay) * p];
}

const css = ([r, g, b]: number[]) => `rgb(${Math.round(r)}, ${Math.round(g)}, ${Math.round(b)})`;

/** A beat's targets with nothing moving: a held frame. */
function still(beat: number): Frame {
  const tg = BEATS[beat];
  const win = WINS[beat >= OUTCOME_FROM && beat < CLOSE_FROM ? sceneOf(beat) : 0];
  return {
    dots: tg.dots.map((d) => ({ x: d.x, y: d.y, size: d.size, jx: 0, jy: 0, fill: css(rgb(d.fill)), opacity: d.opacity })),
    mark: { opacity: tg.markOpacity, scale: tg.markScale },
    days: { opacity: tg.daysOpacity },
    figure: { opacity: tg.figureOpacity, drop: tg.figureDrop, text: win.figure, line: win.line, ink: win.ink },
    captions: [...tg.captions],
  };
}

/**
 * Everything on screen `ms` into the film, on the film's own clock.
 *
 * `reduced` is reduced motion: seven held frames — the mess settled, the
 * order, each outcome scene's last beat, the close — each for its own stretch
 * of the same clock, cut hard, no shake.
 */
export function frame(ms: number, reduced = false): Frame {
  const { first, local, beat } = place(ms);
  if (reduced) return still(HOLDS.find((h) => h >= beat) ?? LOOP - 1);

  const table = first ? FIRST : LATER;
  const segs = table.segs[beat];
  const value = (c: number) => at(segs[c], local);
  const win = WINS[table.figure[beat]];
  const dots: DotFrame[] = [];
  for (let i = 0; i < N; i++) {
    const c = i * 5;
    const [jx, jy] = BEATS[beat].dots[i].jitter ? jitter(i, local) : [0, 0];
    dots.push({
      x: value(c)[0],
      y: value(c + 1)[0],
      size: value(c + 2)[0],
      jx,
      jy,
      opacity: value(c + 3)[0],
      fill: css(value(c + 4)),
    });
  }
  return {
    dots,
    mark: { opacity: value(MARK_CH)[0], scale: value(MARK_CH + 1)[0] },
    days: { opacity: value(MARK_CH + 2)[0] },
    figure: {
      opacity: value(MARK_CH + 3)[0],
      drop: value(MARK_CH + 4)[0],
      text: win.figure,
      line: win.line,
      ink: win.ink,
    },
    captions: [value(MARK_CH + 5)[0], value(MARK_CH + 6)[0], value(MARK_CH + 7)[0]],
  };
}
