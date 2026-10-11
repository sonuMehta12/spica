/**
 * The product's name, in one place.
 *
 * The name had drifted into three spellings across components, a page title
 * and a `localStorage` key, so renaming the product meant grepping for it and
 * hoping. Everything that says the name — the Drawer, the door, the greeting —
 * reads it from here instead, and a rename costs this one file.
 *
 * `index.html` is the one exception: a static page title cannot import a
 * module, so it carries the literal.
 */

/** The product name, as it is written in a sentence. */
export const BRAND = 'Spica';

/** The name as a logo: lowercase, set in Anek Latin semibold beside the mark. */
export const WORDMARK = 'spica';

/** The door's headline: what it is for, said as two lines. */
export const PITCH = ['Less managing life.', 'More achieving it.'] as const;

/**
 * Everything the app stores in the browser sits under this prefix. It is the
 * old name, Cortex, and stays so on purpose: renaming the keys would sign every
 * browser out. CLAUDE.md says what keeps the old name.
 */
const PREFIX = 'cortex';

/** Namespaces a `localStorage` key: `ns('session')` → `'cortex.session'`. */
export const ns = (key: string): string => `${PREFIX}.${key}`;
