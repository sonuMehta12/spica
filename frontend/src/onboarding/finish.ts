import { ns } from '../brand';
import { patchUser } from '../data/api';

/**
 * The first run's one stored bit, `users.onboarding_done_at` — set by *Get
 * started*, *Skip* and *Skip for now*, and kept once set.
 *
 * If the PATCH does not land, Home opens anyway and the flag is sent again
 * on the next start: this browser remembers whose first run it finished
 * until the server has it. A convenience on one device, never the record —
 * the server's flag is what every other device reads.
 */
const KEY = ns('firstRunDone');

/** This browser finished `user`'s first run, and the server may not know yet. */
export function finishedHere(user: string): boolean {
  try {
    return Boolean(user) && localStorage.getItem(KEY) === user;
  } catch {
    return false;
  }
}

/** Tell the server the first run is behind `user`. Throws when it did not land. */
export async function sendFinish(user: string): Promise<void> {
  try {
    localStorage.setItem(KEY, user);
  } catch {
    /* storage blocked: the flag is only sent now */
  }
  await patchUser({ onboarding_done_at: new Date().toISOString() });
  forgetFinish();
}

/** The server has it. */
export function forgetFinish(): void {
  try {
    localStorage.removeItem(KEY);
  } catch {
    /* nothing kept */
  }
}
