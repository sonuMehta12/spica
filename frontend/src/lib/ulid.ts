/**
 * A ULID, made on the device — 48 bits of time then 80 bits of randomness,
 * Crockford base32, 26 chars. The client owns the id so an optimistic row is
 * born with its permanent identity and a retried POST is a replay, never a
 * duplicate (spec/in-progress/ledger-writes.md). No dependency: the whole
 * spec is these twenty lines.
 */
const ENC = '0123456789ABCDEFGHJKMNPQRSTVWXYZ';

export function ulid(now = Date.now()): string {
  let t = now;
  let time = '';
  for (let i = 0; i < 10; i++) {
    time = ENC[t % 32] + time;
    t = Math.floor(t / 32);
  }
  const r = new Uint8Array(16);
  crypto.getRandomValues(r);
  let rand = '';
  for (let i = 0; i < 16; i++) rand += ENC[r[i] & 31];
  return time + rand;
}
