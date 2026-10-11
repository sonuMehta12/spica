/**
 * The profile edited through the composer. spec/in-progress/users-profile.md
 * § The settings surface: not a screen — a target is a row, and the composer
 * already edits rows. `goal 15000`, `protein 140 kcal 2100`, `name Sonu`.
 *
 * One table of fields drives the Profile page, the seed text that lands in the
 * composer, and the parser that turns what was typed into a PATCH.
 */

import type { Profile, UserPatch } from '../data/api';
import { ageOn, localToday } from '../lib/day';
import { rupees } from '../lib/format';

export type FieldId =
  | 'name' | 'gender' | 'dob' | 'height' | 'city' | 'diet' | 'timezone'
  | 'goal' | 'kcal' | 'protein' | 'carbs' | 'fat' | 'fibre' | 'weight' | 'sleep' | 'steps';

type Kind = 'text' | 'date' | 'choice' | 'rupees' | 'int' | 'grams' | 'kg' | 'cm' | 'sleep';

export interface FieldDef {
  id: FieldId;
  label: string;
  key: keyof Profile;
  wire: keyof UserPatch;
  kind: Kind;
  /** Other words the user might type for it. */
  aliases: string[];
  /** A choice's values, as the wire spells them, and their words. */
  options?: readonly (readonly [string, string])[];
}

/** The categories `users` holds, in the words a person reads. */
export const GENDERS = [['female', 'Female'], ['male', 'Male'], ['other', 'Other']] as const;
export const DIETS = [['veg', 'Veg'], ['nonveg', 'Non-veg'], ['eggetarian', 'Eggetarian'], ['any', 'Anything']] as const;

/** A choice's word for its stored value; the value itself if it is one this build does not know. */
export const optionLabel = (options: readonly (readonly [string, string])[], v: string): string =>
  options.find(([value]) => value === v)?.[1] ?? v;

/**
 * A date of birth is shown as an age, never as the date: an age said as "28"
 * is stored as 1 January of the birth year, and only its year means anything.
 */
export const ageText = (dob: string, today = localToday()) => `${ageOn(dob, today)} years`;

export const FIELDS: FieldDef[] = [
  { id: 'name', label: 'Name', key: 'displayName', wire: 'display_name', kind: 'text', aliases: [] },
  { id: 'gender', label: 'Gender', key: 'gender', wire: 'gender', kind: 'choice', aliases: [], options: GENDERS },
  { id: 'dob', label: 'Age', key: 'dob', wire: 'dob', kind: 'date', aliases: ['birthday'] },
  { id: 'height', label: 'Height', key: 'heightCm', wire: 'height_cm', kind: 'cm', aliases: [] },
  { id: 'city', label: 'City', key: 'city', wire: 'city', kind: 'text', aliases: [] },
  { id: 'diet', label: 'Diet', key: 'diet', wire: 'diet', kind: 'choice', aliases: [], options: DIETS },
  { id: 'timezone', label: 'Timezone', key: 'timezone', wire: 'timezone', kind: 'text', aliases: ['tz'] },
  { id: 'goal', label: 'Saving goal', key: 'savingsTarget', wire: 'savings_target_paise', kind: 'rupees', aliases: ['saving', 'savings'] },
  { id: 'kcal', label: 'Calories', key: 'kcalTarget', wire: 'kcal_target', kind: 'int', aliases: ['calories', 'cal'] },
  { id: 'protein', label: 'Protein', key: 'proteinTarget', wire: 'protein_g_target', kind: 'grams', aliases: [] },
  { id: 'carbs', label: 'Carbs', key: 'carbsTarget', wire: 'carbs_g_target', kind: 'grams', aliases: ['carb'] },
  { id: 'fat', label: 'Fat', key: 'fatTarget', wire: 'fat_g_target', kind: 'grams', aliases: [] },
  { id: 'fibre', label: 'Fibre', key: 'fibreTarget', wire: 'fibre_g_target', kind: 'grams', aliases: ['fiber'] },
  { id: 'weight', label: 'Weight target', key: 'weightTargetKg', wire: 'weight_target_kg', kind: 'kg', aliases: [] },
  { id: 'sleep', label: 'Sleep', key: 'sleepTargetMin', wire: 'sleep_target_min', kind: 'sleep', aliases: [] },
  { id: 'steps', label: 'Steps', key: 'stepTarget', wire: 'step_target', kind: 'int', aliases: ['step'] },
];

const pick = (ids: FieldId[]) => ids.map((id) => FIELDS.find((f) => f.id === id)!);
/**
 * The Profile page's groups. One long list of targets read as clutter; these
 * are the shelves a person actually thinks in. Finance holds only the goal for
 * now — income sources and fixed costs are ledger rows, and would join it here
 * as views, not settings.
 */
export const FINANCE_FIELDS = pick(['goal']);
export const HEALTH_FIELDS = pick(['kcal', 'protein', 'carbs', 'fat', 'fibre', 'sleep', 'steps']);
export const WEIGHT_FIELDS = pick(['weight']);
export const ABOUT_FIELDS = pick(['name', 'gender', 'dob', 'height', 'city', 'diet', 'timezone']);
export const fieldById = (id: string): FieldDef | undefined => FIELDS.find((f) => f.id === id);

const byWord = (word: string): FieldDef | undefined => {
  const w = word.toLowerCase();
  return FIELDS.find((f) => f.id === w || f.aliases.includes(w));
};

export function sleepLabel(min: number): string {
  const h = Math.floor(min / 60);
  const m = min % 60;
  return m ? `${h}h ${m}m` : `${h}h`;
}

/** How the Profile page shows a value. Null = unset, shown as an honest dash. */
export function formatValue(f: FieldDef, p: Profile): string | null {
  const v = p[f.key];
  if (v == null || v === '') return null;
  switch (f.kind) {
    case 'rupees': return rupees(v as number);
    case 'grams': return `${v} g`;
    case 'kg': return `${v} kg`;
    // Stored at the column's precision (175.3), shown whole; the editor keeps it exact.
    case 'cm': return `${Math.round(v as number)} cm`;
    case 'sleep': return sleepLabel(v as number);
    case 'int': return (v as number).toLocaleString('en-IN');
    case 'date': return ageText(String(v));
    case 'choice': return optionLabel(f.options ?? [], String(v));
    default: return String(v);
  }
}

/**
 * Two fields cannot be emptied: the name can be changed, not removed, and the
 * timezone is what decides every day the app counts. Everything else clears.
 */
export const clearable = (f: FieldDef) => f.id !== 'name' && f.id !== 'timezone';

/** What the inline editor opens with — sleep in hours, money in rupees, dates as ISO. */
export function draftValue(f: FieldDef, p: Profile): string {
  const v = p[f.key];
  if (v == null) return '';
  if (f.kind === 'sleep') return String(Math.round(((v as number) / 60) * 10) / 10);
  return String(v);
}

interface Parsed {
  body: UserPatch;
  profile: Partial<Profile>;
  summary: string;
}

function setNumber(f: FieldDef, n: number, out: Parsed): boolean {
  if (!(n > 0)) return false;
  switch (f.kind) {
    case 'rupees':
      out.body.savings_target_paise = Math.round(n * 100);
      out.profile.savingsTarget = n;
      break;
    case 'int':
      (out.body as Record<string, unknown>)[f.wire] = Math.round(n);
      (out.profile as Record<string, unknown>)[f.key] = Math.round(n);
      break;
    case 'sleep': {
      // "sleep 7.5" is hours; "sleep 450" is already minutes.
      const min = n < 24 ? Math.round(n * 60) : Math.round(n);
      out.body.sleep_target_min = min;
      out.profile.sleepTargetMin = min;
      break;
    }
    default: // grams · kg · cm — NUMERIC on the wire, so a string
      (out.body as Record<string, unknown>)[f.wire] = String(n);
      (out.profile as Record<string, unknown>)[f.key] = n;
  }
  const shown = formatValue(f, { ...EMPTY, ...out.profile } as Profile) ?? String(n);
  out.summary += (out.summary ? ' · ' : '') + `${f.label} ${shown}`;
  return true;
}

const EMPTY: Profile = {
  id: '', displayName: '', email: null, avatarUrl: null, onboardingDoneAt: null,
  dob: null, gender: null, heightCm: null, city: null, diet: null, timezone: '',
  savingsTarget: null, kcalTarget: null, proteinTarget: null, carbsTarget: null,
  fatTarget: null, fibreTarget: null, weightTargetKg: null, sleepTargetMin: null, stepTarget: null,
};

/**
 * Turn typed text into a PATCH. `field` is the row being edited, so a bare
 * number has somewhere to go; `raw` may carry the field word too ("goal 15000").
 * Returns null when nothing usable was typed — the caller shows a hint, never
 * guesses.
 */
export function parseProfileEdit(field: string, raw: string): Parsed | null {
  const text = raw.trim();
  if (!text) return null;
  const out: Parsed = { body: {}, profile: {}, summary: '' };
  const tapped = fieldById(field);

  if (tapped && (tapped.kind === 'text' || tapped.kind === 'date' || tapped.kind === 'choice')) {
    const value = text.replace(new RegExp(`^${tapped.id}\\s+`, 'i'), '').trim();
    if (!value) return null;
    if (tapped.kind === 'date' && !/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
    if (tapped.kind === 'choice' && !tapped.options?.some(([v]) => v === value)) return null;
    (out.body as Record<string, unknown>)[tapped.wire] = value;
    (out.profile as Record<string, unknown>)[tapped.key] = value;
    out.summary = `${tapped.label} ${value}`;
    return out;
  }

  let any = false;
  for (const m of text.matchAll(/([a-z]+)\s*(\d+(?:\.\d+)?)/gi)) {
    const f = byWord(m[1]);
    if (f && f.kind !== 'text' && f.kind !== 'date' && f.kind !== 'choice') any = setNumber(f, parseFloat(m[2]), out) || any;
  }
  if (!any && tapped) {
    // Just a number, for the field that was tapped.
    const lone = text.match(/^(\d+(?:\.\d+)?)$/);
    if (lone) any = setNumber(tapped, parseFloat(lone[1]), out);
  }
  return any ? out : null;
}

/** An empty save on a field that can be cleared: null, which unsets it. */
export function clearEdit(id: FieldId): Parsed | null {
  const f = fieldById(id);
  if (!f || !clearable(f)) return null;
  return {
    body: { [f.wire]: null } as UserPatch,
    profile: { [f.key]: null } as Partial<Profile>,
    summary: `${f.label} cleared`,
  };
}

/** How the inline editor asks for the field: keyboard, prefix, suffix. */
export function inputFor(f: FieldDef): {
  type: 'text' | 'date';
  inputMode: 'decimal' | 'numeric' | 'text';
  prefix?: string;
  suffix?: string;
  hint: string;
} {
  switch (f.kind) {
    case 'rupees': return { type: 'text', inputMode: 'numeric', prefix: '₹', hint: 'A whole number of rupees.' };
    case 'int': return { type: 'text', inputMode: 'numeric', hint: 'A whole number.' };
    case 'grams': return { type: 'text', inputMode: 'decimal', suffix: 'g', hint: 'Grams.' };
    case 'kg': return { type: 'text', inputMode: 'decimal', suffix: 'kg', hint: 'Kilograms.' };
    case 'cm': return { type: 'text', inputMode: 'decimal', suffix: 'cm', hint: 'Centimetres.' };
    case 'sleep': return { type: 'text', inputMode: 'decimal', suffix: 'h', hint: 'Hours — 7.5 is fine.' };
    case 'date': return { type: 'date', inputMode: 'text', hint: 'Your date of birth — shown as an age.' };
    default: return { type: 'text', inputMode: 'text', hint: '' };
  }
}

/** "78.4" or "weight 78.4" → kg. */
export function parseKg(raw: string): number | null {
  const m = raw.match(/(\d+(?:\.\d+)?)/);
  const kg = m ? parseFloat(m[1]) : NaN;
  return kg > 20 && kg < 400 ? kg : null;
}

export const MEMORY_KINDS = ['identity', 'preference', 'style', 'interest', 'project', 'reference'] as const;

/**
 * The Profile page's groups, as places: each opens as its own page over the
 * grid, and a field's group is where Edit goal and Edit targets land.
 */
export type GroupKey = 'finance' | 'health' | 'projects' | 'runs' | 'weight' | 'about' | 'memory';

export const GROUP_TITLES: Record<GroupKey, string> = {
  finance: 'Finance',
  health: 'Health',
  projects: 'Projects',
  runs: 'Daily runs',
  weight: 'Weight',
  about: 'About you',
  memory: 'Memory',
};

export const GROUP_OF: Record<FieldId, GroupKey> = {
  goal: 'finance',
  kcal: 'health', protein: 'health', carbs: 'health', fat: 'health', fibre: 'health', sleep: 'health', steps: 'health',
  weight: 'weight',
  name: 'about', gender: 'about', dob: 'about', height: 'about', city: 'about', diet: 'about', timezone: 'about',
};
