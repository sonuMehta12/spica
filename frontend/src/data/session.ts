/**
 * The session token, and the one place that knows it is gone.
 *
 * The token is opaque to the app: it goes out on every request as a bearer
 * header and comes back only from sign-in. It is mirrored in memory as well as
 * `localStorage`, because private mode and blocked storage throw on every
 * access — a browser that refuses to remember the token must still be able to
 * use it until the tab closes, not crash on boot.
 */

import { ns } from '../brand';

const KEY = ns('session');

function stored(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

/** The in-memory copy is the truth for this tab; storage is how it survives a reload. */
let token: string | null = stored();

/** The current session token, or `null` when signed out. */
export function getToken(): string | null {
  return token;
}

/** Store a token, or clear it with `null`. */
export function setToken(t: string | null): void {
  token = t;
  try {
    if (t === null) localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, t);
  } catch {
    /* private mode: the token lives for this tab only */
  }
}

let listener: (() => void) | null = null;

/**
 * One subscriber slot, for the app layer: called after the token is cleared
 * because the server said 401. Pass `null` to unsubscribe. One slot, not a
 * list — there is exactly one thing to do about being signed out, and it is
 * to show the door.
 */
export function onSignedOut(cb: (() => void) | null): void {
  listener = cb;
}

/** Drop the token and tell the app. Called by the HTTP client on any 401. */
export function signedOut(): void {
  setToken(null);
  listener?.();
}
