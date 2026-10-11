import {
  Barbell,
  BeerStein,
  Cigarette,
  FlowerLotus,
  Moon,
  SneakerMove,
  type Icon,
} from '@phosphor-icons/react';
import { color, font } from '../theme';

/**
 * A habit's icon and colour, chosen by name in the frontend — the backend
 * stores no iconography. Habit names are free text, so the lookup is fuzzy and
 * the fallback (the habit's first letter, in neutral grey) is the contract,
 * not an edge case.
 *
 * Phosphor's Fill weight, not strokes: at 9px a stroked dumbbell reads as a
 * capital H.
 */

/**
 * What kind of thing the habit is. This is the one place the app has an
 * opinion about a habit, and it is worth being plain about: the strip used to
 * be deliberately colourless so it only recorded what happened. Colour was
 * asked for, so building things take Diet's hue — the card they sit on — and
 * harmful ones red; the strip still shows no target and no streak.
 */
type Nature = 'build' | 'harm' | 'ease' | 'neutral';

const TONE: Record<Nature, { ink: string; bg: string; line: string }> = {
  build: { ink: color.dietInk, bg: color.dietTint, line: color.dietSoft },
  harm: { ink: color.red, bg: color.redTint, line: color.redBorder },
  ease: { ink: color.muted, bg: color.lineSoft, line: color.border },
  neutral: { ink: color.muted, bg: color.white, line: color.border },
};

const GLYPHS: [RegExp, Icon, Nature][] = [
  [/workout|gym|lift/i, Barbell, 'build'],
  [/smok|cigg?|sutta/i, Cigarette, 'harm'],
  [/beer|alcohol|drink|daru/i, BeerStein, 'ease'],
  [/run|daud/i, SneakerMove, 'build'],
  [/meditat|dhyan|yoga/i, FlowerLotus, 'build'],
  [/fast|vrat/i, Moon, 'build'],
];

const match = (habit: string) => GLYPHS.find(([re]) => re.test(habit));

/** The habit's colours, so a caller can tint a badge to match its coin. */
export function habitTone(habit: string) {
  const hit = match(habit);
  return TONE[hit ? hit[2] : 'neutral'];
}

/** The habit's glyph, for a caller drawing its own coin. Undefined: draw the letter. */
export function habitGlyph(habit: string): Icon | undefined {
  return match(habit)?.[1];
}

export default function HabitIcon({ habit, size = 15 }: { habit: string; size?: number }) {
  const hit = match(habit);
  const tone = habitTone(habit);
  const Glyph = hit?.[1];
  return (
    <span
      title={habit}
      style={{
        width: size,
        height: size,
        borderRadius: '50%',
        flex: '0 0 auto',
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        // A tinted disc with a border, so stacked icons read as separate coins.
        background: tone.bg,
        border: `1.2px solid ${tone.line}`,
        fontFamily: font.sans,
        fontWeight: 600,
        fontSize: Math.max(8, size * 0.5),
        lineHeight: 1,
        color: tone.ink,
      }}
    >
      {Glyph ? (
        <Glyph size={size - 5} weight="fill" color={tone.ink} aria-label={habit} />
      ) : (
        habit.charAt(0).toUpperCase()
      )}
    </span>
  );
}
