/** `435` → `7h 15m`. */
export function duration(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = Math.round(minutes % 60);
  return m ? `${h}h ${m}m` : `${h}h`;
}

/**
 * Minutes-from-midnight → a wall clock. Negative means the evening before, so
 * `-35` reads `11:25pm`.
 */
export function clock(minutes: number): string {
  const wrapped = ((minutes % 1440) + 1440) % 1440;
  const h24 = Math.floor(wrapped / 60);
  const m = wrapped % 60;
  const suffix = h24 < 12 ? 'am' : 'pm';
  const h = h24 % 12 === 0 ? 12 : h24 % 12;
  return `${h}:${String(m).padStart(2, '0')}${suffix}`;
}
