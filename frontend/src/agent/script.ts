/**
 * Canned voice-capture demo. Holding the mic replays these in order, alternating
 * money and food, so the whole confirm-card vocabulary is reachable without a
 * speech backend wired up. Swap `VOICE_SCRIPT` for real ASR output when there is one.
 */

export interface PaisaLine {
  type: 'paisa';
  u: string;
  name: string;
  cat: string;
  amt: number;
}

export interface DietLine {
  type: 'diet';
  u: string;
  name: string;
  p: number;
  k: number;
}

export type VoiceLine = PaisaLine | DietLine;

const PAISA: PaisaLine[] = [
  {
    type: 'paisa',
    u: '"Rapido se aaya, ek sau saath ka"',
    name: 'Rapido',
    cat: 'Transport',
    amt: 160,
  },
  {
    type: 'paisa',
    u: '"Paani ki bottle, dus rupaye"',
    name: 'Paani',
    cat: 'Khana/Grocery',
    amt: 10,
  },
  {
    type: 'paisa',
    u: '"Mummy ko paanch sau diye"',
    name: 'Mummy ko diya',
    cat: 'Logon ko diya',
    amt: 500,
  },
];

const DIET: DietLine[] = [
  {
    type: 'diet',
    u: '"Dopahar ko chawal dal aur aloo ki sabzi khai"',
    name: 'Chawal dal + aloo',
    p: 15,
    k: 690,
  },
  {
    type: 'diet',
    u: '"Shaam ko sprouts khaye dahi ke saath"',
    name: 'Dahi + sprouts',
    p: 19,
    k: 270,
  },
  {
    type: 'diet',
    u: '"Raat ko soya keema, do roti"',
    name: 'Soya keema + 2 roti',
    p: 39,
    k: 540,
  },
];

export const VOICE_SCRIPT: VoiceLine[] = [PAISA[0], DIET[0], PAISA[1], DIET[1], PAISA[2], DIET[2]];

/** How long the waveform runs before the transcript lands. */
export const LISTEN_MS = 1700;

/** How long the agent visibly thinks before it answers. */
export const THINKING_MS = 750;
/** The lock beat, after thinking and before the reply lands. */
export const SAVING_MS = 480;
