import { Barbell, CalendarCheck, CookingPot, MapPin, Package, Users, type Icon } from '@phosphor-icons/react';
import { CONFIRM_BELOW, LIBRARY, type ItemKind, type SavedItem } from '../data/vault';
import type { CommitmentsPage, PantryRow } from '../data/api';

export type Section = ItemKind | 'pantry' | 'people' | 'commitments';

export interface SectionSummary {
  key: Section;
  label: string;
  count: number;
  /** The one number worth reading at a glance. */
  hint: string;
  /** True when the hint is something to act on rather than just a stat. */
  urgent: boolean;
  /** The section's Phosphor glyph. */
  icon: Icon;
}

const ICONS: Record<Section, Icon> = {
  recipe: CookingPot,
  pantry: Package,
  place: MapPin,
  workout: Barbell,
  people: Users,
  commitments: CalendarCheck,
};

export function inbox(library: SavedItem[] = LIBRARY): SavedItem[] {
  return [...library]
    .filter((i) => i.confidence < CONFIRM_BELOW)
    .sort((a, b) => b.day - a.day);
}

export function itemsOf(kind: ItemKind, library: SavedItem[] = LIBRARY): SavedItem[] {
  return [...library].filter((i) => i.kind === kind).sort((a, b) => b.day - a.day);
}

/**
 * The tiles. `library` is no longer read — every section counts a real table
 * as of 2026-09-07 — but it stays in the signature because the seeded library
 * is what the capture extension will fill, and `Section` is still built from
 * its kinds.
 */
export function sections(
  _library: SavedItem[] = LIBRARY,
  pantry: PantryRow[] = [],
  dishes: { tried: number; saved: boolean }[] = [],
  people: { kind: string | null; stillOut: number; youOwe: number }[] = [],
  exercises: { tried: number }[] = [],
  places: { payments: number; spent: number }[] = [],
  commitments: CommitmentsPage | null = null,
): SectionSummary[] {

  const tried = dishes.filter((d) => d.tried > 0).length;
  // Buy is the shopping list: out, gone off, or below the reorder level.
  const toBuy = pantry.filter((p) => p.status === 'out' || p.status === 'stale' || p.status === 'soon').length;
  // Staples are in the house but not counted; they are not stock.
  const counted = pantry.filter((p) => !p.staple).length;

  // The hint says what is owed, not how many rows are unclassified: Unsorted
  // is a bucket, never a badge. spec/in-progress/people.md § Rules.
  const humans = people.filter((p) => p.kind === 'person').length;
  const known = exercises.filter((e) => e.tried > 0).length;
  const spentHere = places.reduce((n, p) => n + p.spent, 0);
  const owed = people.reduce((n, p) => n + p.stillOut + p.youOwe, 0);

  // What is owed, read from the live page: unknown until it loads, and a
  // month with nothing owed says so rather than printing ₹0.
  const lines = commitments?.items.filter((c) => c.source === 'commitment') ?? [];
  const owedNow = commitments?.owedPaise ?? 0;

  return [
    {
      key: 'commitments',
      label: 'Commitments',
      count: lines.filter((c) => !c.skipped).length,
      hint: !commitments
        ? ''
        : owedNow > 0
          ? `₹${Math.round(owedNow / 100).toLocaleString('en-IN')} owed`
          : lines.length
            ? 'nothing owed'
            : 'none yet',
      urgent: false,
      icon: ICONS.commitments,
    },
    {
      key: 'recipe',
      label: 'Dishes',
      count: dishes.length,
      hint: tried ? `${tried} you have eaten` : 'nothing tried yet',
      urgent: false,
      icon: ICONS.recipe,
    },
    {
      key: 'pantry',
      label: 'Pantry',
      count: counted,
      hint: toBuy ? `${toBuy} to buy` : 'all good',
      urgent: toBuy > 0,
      icon: ICONS.pantry,
    },
    {
      key: 'people',
      label: 'People',
      count: humans,
      hint: owed ? `₹${Math.round(owed / 100).toLocaleString('en-IN')} outstanding` : 'nothing owed',
      urgent: false,
      icon: ICONS.people,
    },
    {
      key: 'place',
      label: 'Places',
      count: places.length,
      // What was spent there, not how many were visited — a pin exists because
      // money moved. spec/in-progress/places.md.
      hint: spentHere
        ? `₹${Math.round(spentHere / 100).toLocaleString('en-IN')} spent`
        : 'nothing spent yet',
      urgent: false,
      icon: ICONS.place,
    },
    {
      key: 'workout',
      label: 'Workouts',
      count: exercises.length,
      // A library to suggest from, so the useful second number is how much of
      // it you have actually done — not how often you trained, which the habit
      // strip says.
      hint: known ? `${known} you have done` : 'none tried yet',
      urgent: false,
      icon: ICONS.workout,
    },
  ];
}

export interface SourceRow {
  source: string;
  count: number;
  share: number;
}

/** Where the capture extension has been picking things up from. */
export function sourceRows(library: SavedItem[] = LIBRARY): SourceRow[] {
  const tally = new Map<string, number>();
  for (const i of library) {
    const s = i.source === 'agent' || i.source === 'maps' ? i.source : i.source.replace(/^www\./, '');
    tally.set(s, (tally.get(s) ?? 0) + 1);
  }
  const total = library.length || 1;
  return [...tally.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([source, count]) => ({ source, count, share: count / total }));
}


export const SECTION_LABELS: Record<Section, string> = {
  recipe: 'Dishes',
  pantry: 'Pantry',
  place: 'Places',
  workout: 'Workouts',
  people: 'People',
  commitments: 'Commitments',
};
