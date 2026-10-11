import { useEffect, useReducer, useState } from 'react';
import {
  listWeighIns,
  type CommitmentsPage,
  type DishRow,
  type ExerciseRow,
  type HabitLogRow,
  type HabitRow,
  type LimitInfo,
  type PantryRow,
  type PendingItem,
  type PersonRow,
  type PlaceRow,
  type Profile,
  type RepaymentItem,
  type WeighInRow,
} from '../../data/api';
import { localDayOf } from '../../lib/day';
import type { ConfirmMsg, Meal, Tx } from '../../types';

/**
 * The rows a card reads live, beyond the ledger lists the thread already
 * holds. Every one is loaded at boot and kept current by the hook, so a card
 * that names a pin, a habit or a dish shows what is true now — a deleted row,
 * a renamed habit, a pin's new spend — not what was true when it was written.
 */
export interface CardRows {
  pantry: PantryRow[];
  dishes: DishRow[];
  habits: HabitRow[];
  habitLogs: HabitLogRow[];
  people: PersonRow[];
  exercises: ExerciseRow[];
  places: PlaceRow[];
  limitInfo: LimitInfo | null;
  /** This month's commitments — what a payment counts toward, and what a chat card names. */
  commitments: CommitmentsPage | null;
  pending: PendingItem[];
  borrowed: PendingItem[];
  repayments: RepaymentItem[];
  profile: Profile;
}

/**
 * What the client knows about the ledger row a confirm card points at. The
 * live row wins over the payload for every value it carries; until it
 * arrives, the card draws from the payload.
 */
export interface LiveRow {
  /** Known to be gone: struck, faint, "Removed". */
  deleted: boolean;
  tx?: Tx;
  meal?: Meal;
}

export function liveFor(msg: ConfirmMsg, tx: Tx[], meals: Meal[], deletedRows: string[]): LiveRow {
  const id = msg.rowId;
  // Built by a delete in the first place: struck until the row itself says
  // otherwise. An Undo — on this card or any other — brings the row back, and
  // the card becomes the plain receipt it was before.
  const born = msg.state === 'deleted';
  if (!id) return { deleted: born };
  const gone = deletedRows.includes(id);
  if (msg.source === 'paisa') {
    const t = tx.find((x) => x.id === id);
    return { deleted: gone || (t ? Boolean(t.deleted) : born), tx: t };
  }
  if (msg.source === 'diet') {
    const m = meals.find((x) => x.id === id);
    return { deleted: gone || (m ? Boolean(m.deleted) : born), meal: m };
  }
  return { deleted: gone || born };
}

/** The row itself says it is certain: a guess on it was confirmed. */
export const certain = (row: { confidence?: number } | undefined) =>
  row?.confidence != null && row.confidence >= 1;

const ULID = '0123456789ABCDEFGHJKMNPQRSTVWXYZ';

/**
 * When a message was written, from its own id. A card carries no date of its
 * own, but its turn's id does: a server turn's is a ULID, whose first ten
 * characters are the millisecond it was made; a reply this session built is
 * `chat-<epoch ms>-<n>`. Without it, an old card would claim today's numbers —
 * "Cigarette · 0 today" under a day you logged two.
 */
export function msgTime(id: string): number | null {
  const local = /^chat-(\d{12,})-/.exec(id);
  if (local) return Number(local[1]);
  const head = id.slice(0, 10).toUpperCase();
  if (!/^[0-9A-HJKMNP-TV-Z]{10}$/.test(head)) return null;
  let t = 0;
  for (const ch of head) t = t * 32 + ULID.indexOf(ch);
  // 2020 → 2100: anything else is not a timestamp that happens to decode.
  return t > 1.57e12 && t < 4.1e12 ? t : null;
}

/** The local day a message was written, or null when its id cannot say. */
export function msgDay(id: string): string | null {
  const t = msgTime(id);
  return t == null ? null : localDayOf(new Date(t).toISOString());
}

/**
 * Weigh-ins, as the weight cards read them — they are not on the deck, and
 * only those cards ask. Read when one first needs them, and read again
 * whenever a weigh-in is written or deleted: a same-day correction keeps its
 * row's id, so a copy kept from before would put the old weight, and its dot,
 * under the corrected card. A failed read is retried on the next mount rather
 * than cached as "none": an empty list would let a card say "no earlier
 * weigh-in", which would be false.
 */
let weighIns: Promise<WeighInRow[]> | null = null;
const readers = new Set<() => void>();

/**
 * Read the weigh-ins again, now, and hand every weight card on screen the new
 * rows. Called once a weigh-in may have been written or deleted — before the
 * cards that show the write are drawn, so none of them draws the old copy.
 */
export function rereadWeighIns(): Promise<WeighInRow[]> {
  const read = listWeighIns();
  weighIns = read;
  read.catch(() => {
    if (weighIns === read) weighIns = null;
  });
  readers.forEach((r) => r());
  return read;
}

export function useWeighIns(enabled: boolean): WeighInRow[] | null {
  const [rows, setRows] = useState<WeighInRow[] | null>(null);
  const [round, again] = useReducer((n: number) => n + 1, 0);
  useEffect(() => {
    if (!enabled) return;
    readers.add(again);
    return () => {
      readers.delete(again);
    };
  }, [enabled]);
  useEffect(() => {
    if (!enabled) return;
    let live = true;
    const read = (weighIns ??= listWeighIns());
    read.then(
      (r) => live && setRows(r),
      () => {
        if (weighIns === read) weighIns = null;
      },
    );
    return () => {
      live = false;
    };
  }, [enabled, round]);
  return rows;
}
