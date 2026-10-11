import type { Mode, Range } from './types';

export interface ModeDef {
  id: Mode;
  /** The name above the deck — the words are the indicator. */
  label: string;
  /** Dormant modes have no data behind them — they render a placeholder page. */
  live: boolean;
}

/** Swipe order of the primary component, and the order of the names above it. */
export const MODES: ModeDef[] = [
  { id: 'paisa', label: 'Paisa', live: true },
  { id: 'diet', label: 'Diet', live: true },
  { id: 'work', label: 'Work', live: true },
];

/**
 * Which ranges each mode offers, and what they are called there.
 *
 * The label does the disambiguating: `7din` counts backwards for money and
 * forwards for work, because a spend is a thing that happened and a task is a
 * thing that has not. Work drops `aaj` — one day says nothing about a project —
 * and adds `sab`, the only window undated backlog appears in.
 */
export const RANGES: Record<Mode, { id: Range; label: string }[]> = {
  paisa: [
    { id: 'aaj', label: 'Today' },
    { id: '7din', label: '7 days' },
    { id: '30din', label: 'Month' },
  ],
  diet: [
    { id: 'aaj', label: 'Today' },
    { id: '7din', label: '7 days' },
    { id: '30din', label: 'Month' },
  ],
  work: [
    { id: '7din', label: 'This week' },
    { id: '30din', label: 'Month' },
    { id: 'sab', label: 'All' },
  ],
  // Same three as Paisa: attention is spent the way money is, and the windows
  // answer the same questions.
};

/**
 * The range to *show* for a mode, which is not always the one in state: the
 * deck keeps one range across all three cards, so swiping from Paisa on `Aaj`
 * to Work has to land somewhere Work actually offers.
 */
export function rangeFor(mode: Mode, range: Range): Range {
  const opts = RANGES[mode];
  return opts.some((o) => o.id === range) ? range : opts[0].id;
}

export const WORK_NOTE =
  'Project context, issue-wise memory, "where was I" — all of it lands here. Run Paisa and Diet for 30 days first.';

export function modeIndex(mode: Mode): number {
  const i = MODES.findIndex((m) => m.id === mode);
  return i < 0 ? 0 : i;
}
