/**
 * Settings and static UI text — everything that is a choice rather than data.
 *
 * Targets are NOT here any more: they live on the users row and arrive with
 * the deck (see data/live.ts § PROFILE). Nothing in this file comes out of the
 * ledger, and nothing in it is about the person.
 */

/**
 * The menu's rows, in the phone's three groups: what is yours, how the app
 * reaches you, and help. Profile is the name card above them, not a row.
 */
export const MENU_GROUPS = [
  ['Reports', 'Your data'],
  ['Notifications', 'Permissions', 'Billing'],
  ['Help & feedback'],
] as const;

/** The rows that open a page today; the rest say Soon and do nothing. */
export const BUILT: ReadonlySet<string> = new Set(['Reports', 'Your data']);
