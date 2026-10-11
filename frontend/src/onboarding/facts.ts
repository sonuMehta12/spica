import { rereadWeighIns } from '../components/messages/live';
import {
  fetchHabits,
  fetchMe,
  listMemories,
  type HabitRow,
  type MemoryRow,
  type OnboardingQuestion,
  type Profile,
  type WeighInRow,
} from '../data/api';
import { ageOn } from '../lib/day';
import { rupees } from '../lib/format';
import { DIETS, GENDERS, optionLabel } from '../state/profileEdit';

/**
 * What the person has told Spica, read from their rows — never from the
 * cards' copies. Screen 3 asks only what is not here yet; screen 4 is drawn
 * from it on entry. spec/done/onboarding-goals.md § 3 · Coming back, § 4.
 */
export interface Facts {
  profile: Profile;
  /** Newest first. */
  weighIns: WeighInRow[];
  memories: MemoryRow[];
  habits: HabitRow[];
}

/**
 * The rows, read now. The weigh-ins go through the weight cards' own read, so
 * a card drawn after an answer shows the weigh-in as this read found it — a
 * same-day correction keeps its row's id.
 */
export async function loadFacts(): Promise<Facts> {
  const [profile, weighIns, memories, habits] = await Promise.all([
    fetchMe(),
    rereadWeighIns(),
    listMemories(),
    fetchHabits(),
  ]);
  return { profile, weighIns: [...weighIns].sort((a, b) => b.day.localeCompare(a.day)), memories, habits };
}

export const latestWeighIn = (f: Facts): WeighInRow | undefined => f.weighIns[0];

/** A goal said in words, as the onboarding agent keeps one. */
const isGoal = (m: MemoryRow) => m.kind === 'project' && m.slug.startsWith('goal-');
/** What a diet leaves out, as the agent keeps it: "Never eats beef", "Vegan — never eats dairy". */
const isDietNote = (m: MemoryRow) =>
  m.kind === 'preference' && (m.slug.startsWith('never-eats-') || m.slug.startsWith('diet-'));

/**
 * Whether a question's facts are already on the rows — then coming back
 * mid-flow does not ask it again. The name does not count: sign-in fills it
 * from Google before anything is asked.
 */
export function answered(q: OnboardingQuestion, f: Facts): boolean {
  const p = f.profile;
  switch (q) {
    case 'about':
      return p.gender != null || p.dob != null || p.heightCm != null || f.weighIns.length > 0;
    case 'place':
      return p.city != null || p.diet != null || f.memories.some(isDietNote);
    case 'health':
      return p.weightTargetKg != null || f.memories.some(isGoal);
    case 'money':
      return p.savingsTarget != null;
    case 'habits':
      return f.habits.length > 0;
  }
}

/**
 * Body mass index from the latest weigh-in and the height as stored, to one
 * place — 72 kg at 175.3 cm is 23.4. A bare number: no category, no colour.
 * Null when either is missing, and for a child, whom adult BMI does not fit.
 */
export function bmi(kg: number | null | undefined, cm: number | null, age: number | null): number | null {
  if (kg == null || cm == null || cm <= 0) return null;
  if (age != null && age < 18) return null;
  const m = cm / 100;
  return Math.round((kg / (m * m)) * 10) / 10;
}

/** A fact on screen 4's About you card. `estimated` draws the dot before it. */
export interface Tag {
  text: string;
  estimated?: boolean;
}

/** Whole kilograms, or one place when it has one: 72, 71.5. */
const kgText = (kg: number) => `${Math.round(kg * 10) / 10} kg`;

/** Gender, age, height, weight, BMI, city, diet and what it leaves out — what is set, nothing else. */
export function aboutTags(f: Facts, today: string): Tag[] {
  const p = f.profile;
  const w = latestWeighIn(f);
  const age = p.dob ? ageOn(p.dob, today) : null;
  const index = bmi(w?.kg, p.heightCm, age);
  const tags: Tag[] = [];
  if (p.gender) tags.push({ text: optionLabel(GENDERS, p.gender) });
  if (age != null) tags.push({ text: `${age} years` });
  // Stored at the column's precision (175.3), shown whole.
  if (p.heightCm != null) tags.push({ text: `${Math.round(p.heightCm)} cm` });
  if (w) tags.push({ text: kgText(w.kg), estimated: w.estimated });
  // The BMI is worked out from that weight, so it carries the weight's dot.
  if (index != null) tags.push({ text: `BMI ${index.toFixed(1)}`, estimated: w?.estimated });
  if (p.city) tags.push({ text: p.city });
  if (p.diet) tags.push({ text: optionLabel(DIETS, p.diet) });
  // Data is data: what the diet leaves out, as it was kept.
  for (const m of f.memories.filter(isDietNote)) tags.push({ text: m.text });
  return tags;
}

/** One row of Your goals. `estimated` dots the parts worked out from a guessed weight. */
export interface Goal {
  key: string;
  domain: 'health' | 'money' | 'habit';
  title: string;
  titleEstimated?: boolean;
  /** The line under it, in parts — each may carry the dot on its own. */
  sub?: { text: string; estimated?: boolean }[];
  /** A habit's name, for its own glyph. */
  habit?: string;
}

/**
 * The goals, worked out at render from the rows: "Lose 5 kg — 72 kg → 67 kg"
 * is the latest weigh-in against the stored target, so it stays true as the
 * weight moves. While that weigh-in is a guess, its weight and the change
 * worked out from it carry the dot; the stored target does not.
 */
export function goals(f: Facts): Goal[] {
  const p = f.profile;
  const w = latestWeighIn(f);
  const out: Goal[] = [];
  if (p.weightTargetKg != null) {
    const target = p.weightTargetKg;
    if (w) {
      const diff = Math.round((w.kg - target) * 10) / 10;
      out.push({
        key: 'weight',
        domain: 'health',
        title: diff > 0 ? `Lose ${kgText(diff)}` : diff < 0 ? `Gain ${kgText(-diff)}` : `Stay at ${kgText(target)}`,
        titleEstimated: w.estimated && diff !== 0,
        sub: [{ text: kgText(w.kg), estimated: w.estimated }, { text: `→ ${kgText(target)}` }],
      });
    } else {
      // No weigh-in to count from: the target, as stored, and no change invented.
      out.push({ key: 'weight', domain: 'health', title: `Reach ${kgText(target)}` });
    }
  }
  for (const m of f.memories.filter(isGoal)) out.push({ key: m.id, domain: 'health', title: m.text });
  if (p.savingsTarget != null) {
    out.push({ key: 'save', domain: 'money', title: `Save ${rupees(p.savingsTarget)}`, sub: [{ text: 'every month' }] });
  }
  for (const h of f.habits) {
    out.push({
      key: h.id,
      domain: 'habit',
      title: h.name,
      sub: [{ text: h.direction === 'build' ? 'a habit to build' : 'a habit to break' }],
      habit: h.name,
    });
  }
  return out;
}
