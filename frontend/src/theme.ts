/**
 * Jamun — the design tokens. The Android app's `ui/theme/Tokens.kt` holds the
 * same values under the same names; the two move together.
 *
 * Every colour is an OKLCH decision, checked against WCAG contrast on white,
 * with the ratio beside it so the next colour added has a rule to follow.
 * Every colour and font in the app resolves through here — nothing else
 * hard-codes a hex. `global.css` reads these too, as custom properties set
 * from `cssVars()` at boot.
 */

const ink = '#1B171A';
const paper = '#FFFFFF';
const border = '#DEDBDE';
const jamun = '#732F67';
const jamunHover = '#611D55';
const jamunTint = '#F7EBF4';
const chipHover = '#F5E6F1';

export const color = {
  /* Neutrals — lean 0.5% toward jamun (C 0.005, H 335), so the greys and the
     brand read as one material rather than grey beside plum. */

  /** Text. 17.7 : 1. */
  ink,
  /** The page. */
  paper,
  /** A card or field that sits on the page. */
  white: '#FFFFFF',
  /** The deck card: a pale panel instead of a shadow. */
  surface: '#F8F4F7',

  /** Supporting text. 6.8 : 1. */
  muted: '#5D5A5C',
  /** Labels and metadata — AA on the page (4.97) and on the surface panel (4.56). */
  faint: '#726F71',
  /**
   * Decorative only — a future day, an idle mark, the last category. Never
   * text you must read. 2.7 : 1. Lighter than `faint`: the old theme had the
   * two the other way round.
   */
  grey: '#A09DA0',

  /** Hairlines: small card borders, dividers. */
  line: '#EDEAEC',
  lineSoft: '#F2EFF1',
  /** Fields, the composer, chips. */
  border,
  /** A ring's empty track. */
  ringIdle: '#E8E5E7',

  /* Jamun — the one brand colour, used sparingly: the mic and send, the
     agent's mark, the current selection, links. At least 80° of hue from
     every mode, so an action never reads as a number. White on it 9.0 : 1. */
  brand: jamun,
  brandHover: jamunHover,
  /** Your messages: a tint of the brand, ink on it. */
  brandTint: jamunTint,
  /** The mascot's arc. */
  brandSoft: '#CA8EBD',

  /** Chips are yours, not the brand's: white with a border, a brand wash on hover. */
  chip: '#FFFFFF',
  chipBorder: border,
  chipHover,

  /* One colour per mode at equal lightness and chroma (L 0.62, C 0.13). The
     hue says which mode; equal lightness means none reads more urgent than
     another. Data only — never chrome. A mode's rings step in lightness
     within its hue; `ink` is its text on `tint`. */
  paisa: '#239D6A',
  paisaSoft: '#9DD3B5',
  paisaInk: '#00613A',
  paisaTint: '#E6F9EE',

  diet: '#C16E2D',
  dietSoft: '#E9B999',
  dietInk: '#7C3C00',
  dietTint: '#FFF0E4',

  work: '#418AD1',
  workSoft: '#A2C8F0',
  workInk: '#125289',
  workTint: '#E7F5FF',

  /* The estimate dot, and nothing else. 3.1 : 1. */
  amber: '#C58500',
  amberDeep: '#734D00',
  amberTint: '#FEF2D9',

  /* Over — money out, over a limit, late. 5.5 : 1. */
  red: '#BD3933',
  redTint: '#FFEEEC',
  redSurface: '#FFF6F5',
  redBorder: '#FAC6BF',

  /* ── Aliases ────────────────────────────────────────────────────────────
     The old theme's names, kept compiling because `landing/` imports this
     file and is restyled on its own schedule. The app uses the names above;
     nothing new should reach for these. `green` was the brand, and the brand
     is not green any more. */
  green: jamun,
  greenHover: jamunHover,
  greenTint: jamunTint,
  greenChip: '#FFFFFF',
  greenChipBorder: border,
  greenChipHover: chipHover,
} as const;

/** A mode's four stops: `base` for marks, `soft` for a lighter ring, `ink` for text on `tint`. */
export interface ModeTone {
  base: string;
  soft: string;
  ink: string;
  tint: string;
}

export const modeTone: Record<'paisa' | 'diet' | 'work', ModeTone> = {
  paisa: { base: color.paisa, soft: color.paisaSoft, ink: color.paisaInk, tint: color.paisaTint },
  diet: { base: color.diet, soft: color.dietSoft, ink: color.dietInk, tint: color.dietTint },
  work: { base: color.work, soft: color.workSoft, ink: color.workInk, tint: color.workTint },
};

/**
 * Categories, in order: the mode hues at base, then soft, then grey — so a
 * palette never borrows amber (the estimate) or red (over).
 */
export const categoryPalette: readonly string[] = [
  color.paisa,
  color.diet,
  color.work,
  color.paisaSoft,
  color.dietSoft,
  color.workSoft,
  color.grey,
];

/**
 * Other companies' colours, for their marks only — never for anything of ours.
 * The landing page shows where Spica works (Claude, ChatGPT, WhatsApp), and a
 * mark in the wrong colour reads as a fake one.
 */
export const brand = {
  claude: '#D97757',
  whatsapp: '#25D366',
  chatgpt: '#000000',
  linear: '#5E6AD2',
  slack: '#4A154B',
  gmail: '#EA4335',
  keep: '#FFBB00',
  gemini: '#8E75B2',
  wispr: '#034F46',
  wisprInk: '#FFFFEB',
} as const;

const sans = "'Anek Latin', system-ui, sans-serif";

/**
 * Two faces with a job each, and no monospace anywhere.
 *
 * - **Newsreader** (`display`) — the agent's own words and the page's date.
 *   Serif is Spica speaking.
 * - **Anek Latin** (`sans`) — everything else: what you tap, every label and
 *   every number. Tabular figures are on globally (`global.css`), so ₹1,100
 *   and ₹8,880 are the same width.
 */
export const font = {
  display: "'Newsreader', Georgia, serif",
  sans,
  /** Alias — data is the same face in grey. Kept compiling for `landing/`. */
  mono: sans,
} as const;

/** Nothing that sits in the page casts a shadow. Only what floats lifts. */
const lift = '0 12px 30px rgba(27,23,26,0.16)';
export const shadow = {
  /** Menus and the toast — the only things that float. */
  popover: lift,
  /* Aliases, for `landing/`: each is now no shadow at all. */
  card: 'none',
  bubble: 'none',
  input: 'none',
  mic: 'none',
} as const;

/** Three radii, and full for pills. */
export const radius = {
  /** Small cards: chat cards, tiles, sections. */
  card: 14,
  /** The deck card. */
  deck: 18,
  /** Message bubbles. */
  bubble: 18,
  /** Pills and round buttons. */
  pill: 999,
} as const;

/** The 4px grid, as the jobs it does. */
export const space = {
  /** Page gutter. */
  gutter: 16,
  /** Header → mode tabs. */
  headerToTabs: 8,
  /** Mode tabs → the deck card. */
  tabsToDeck: 12,
  /** The deck → the thread. */
  deckToThread: 20,
  /** Between consecutive messages from the same speaker. */
  sameSpeaker: 8,
  /** Where the speaker changes. */
  newSpeaker: 20,
} as const;

/** Circumference of the r=50 hero ring — 2·π·50, rounded the way the canvas rounds it. */
export const RING_CIRCUMFERENCE = 314.2;

/** Safe-area aware insets. The canvas hard-coded 64px/42px for the iOS mock chrome. */
export const inset = {
  top: 'calc(env(safe-area-inset-top, 8px) + 16px)',
  bottom: 'calc(env(safe-area-inset-bottom, 8px) + 12px)',
} as const;

/**
 * The tokens as CSS custom properties — `--ink`, `--brand-tint`, `--f-sans` —
 * so `global.css` can use them without naming a hex. Set on `:root` at boot.
 */
export function cssVars(): Record<string, string> {
  const kebab = (k: string) => k.replace(/[A-Z]/g, (c) => `-${c.toLowerCase()}`);
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(color)) out[`--${kebab(k)}`] = v;
  out['--f-display'] = font.display;
  out['--f-sans'] = font.sans;
  out['--sh-pop'] = shadow.popover;
  return out;
}
