import type { CommitmentRow, CommitmentsPage } from '../../data/api';
import { monthLabel } from '../../lib/format';

/** 1 → "1st", 22 → "22nd", 13 → "13th". */
export function ordinal(n: number): string {
  const tail = n % 100;
  const suffix = tail >= 11 && tail <= 13 ? 'th' : ({ 1: 'st', 2: 'nd', 3: 'rd' } as Record<number, string>)[n % 10] ?? 'th';
  return `${n}${suffix}`;
}

/** Paise as the page prints them: whole rupees, Indian grouping, a true minus. */
export function inr(paise: number): string {
  const r = Math.round(paise / 100);
  return `${r < 0 ? '−' : ''}₹${Math.abs(r).toLocaleString('en-IN')}`;
}

/** What the line says about its own month: "from September" for a carried remainder. */
export const carriedLabel = (c: CommitmentRow) =>
  c.carriedFrom ? `from ${monthLabel(c.carriedFrom)}` : null;

/**
 * This month's commitments a payment can count toward: the ones the person
 * made (a borrowing lives in udhaar), not skipped, the unpaid ones first.
 * Skipped lines owe nothing and a payment linked to one would not clear it.
 */
export function linkTargets(page: CommitmentsPage | null): CommitmentRow[] {
  if (!page?.editable) return [];
  return page.items
    .filter((c) => c.source === 'commitment' && !c.skipped)
    .sort((a, b) => Number(a.settled) - Number(b.settled));
}

/**
 * Offered beside the ledger's own categories, so a new commitment can be filed
 * before anything has been. The same names the server's prompt offers.
 */
const DEFAULT_CATEGORIES = [
  'Rent', 'EMI', 'Ghar', 'Subscriptions', 'Bills/Recharge', 'Health/Diet',
  'Transport', 'Khana/Grocery', 'Dost & Bahar', 'Shopping', 'Other',
];

/** The categories this ledger uses, then the defaults it has not used yet. */
export function categoryChoices(used: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const c of [...used, ...DEFAULT_CATEGORIES]) {
    const k = c.trim().toLowerCase();
    if (!k || seen.has(k)) continue;
    seen.add(k);
    out.push(c.trim());
  }
  return out;
}
