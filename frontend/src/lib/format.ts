/**
 * Indian-format rupees, no paise — `₹1,100`. A negative reads `−₹21`, with a
 * true minus (U+2212) before the sign: `₹-21` is how a spreadsheet says it.
 */
export function rupees(n: number): string {
  const r = Math.round(n);
  return (r < 0 ? '−' : '') + '₹' + Math.abs(r).toLocaleString('en-IN');
}

export function grams(n: number): string {
  return `${Math.round(n)}g`;
}

export function kcal(n: number): string {
  return `${Math.round(n).toLocaleString('en-IN')} kcal`;
}


let seq = 0;
/** Monotonic local id — chat messages and freshly logged rows. */
export function nextId(prefix: string): string {
  seq += 1;
  return `${prefix}${seq}`;
}

/** An ISO local day as "3 Jul" — for rows from outside the deck's month. */
export function shortDay(iso: string): string {
  const d = new Date(`${iso}T00:00:00`);
  // en-IN renders September as "Sept" and every other month at three letters.
  // The date column is 44px and the rest of the app spells it "Sep", so the
  // month name comes from en-US, which keeps all twelve at three; the
  // day-first order is ours.
  return `${d.getDate()} ${d.toLocaleDateString('en-US', { month: 'short' })}`;
}

/** An ISO local day as "Wed, 16 Sep" — how a date reads wherever it is data. */
export function shortDate(iso: string): string {
  const d = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  // en-US for the names, which keeps every month at three letters ("Sep",
  // never en-IN's "Sept"); the day-first order is ours.
  const wd = d.toLocaleDateString('en-US', { weekday: 'short' });
  return `${wd}, ${d.getDate()} ${d.toLocaleDateString('en-US', { month: 'short' })}`;
}

/** An ISO local day in full — "Wednesday, 30 September" — the page's heading. */
export function longDay(iso: string): string {
  const d = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  const wd = d.toLocaleDateString('en-US', { weekday: 'long' });
  return `${wd}, ${d.getDate()} ${d.toLocaleDateString('en-US', { month: 'long' })}`;
}

/** The deck's month, spelled out — "September". */
export function monthName(year: number, month0: number): string {
  return new Date(year, month0, 1).toLocaleDateString('en-IN', { month: 'long' });
}

/**
 * A ledger row's day, with its month. Every row fetched from the server
 * carries `date`; the bare day-number fallback is for a row written
 * optimistically, before the server has answered with one.
 */
export function dayLabel(r: { day: number; date?: string }): string {
  return r.date ? shortDay(r.date) : `${r.day}`;
}

/** An ISO local day's month, spelled out — "September". */
export function monthLabel(iso: string): string {
  const d = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('en-US', { month: 'long' });
}
