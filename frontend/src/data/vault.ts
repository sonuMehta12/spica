/**
 * The knowledge base behind "Your data".
 *
 * `library` is what the always-on-top capture extension files automatically —
 * articles, videos, places, workouts — each with the agent's category guess and
 * how sure it was. Pantry and dishes used to be seeded here too; both now come
 * from the server.
 *
 * NOTE: unlike the ledger in `seed.ts` (real August figures from the workbook),
 * everything here is invented placeholder content. Swap it for real capture
 * output; nothing downstream assumes these particular rows.
 */

/**
 * A saved thing is a *thing*, never the medium it arrived in. A reel showing a
 * recipe is a dish with a `source_url`, not a video — `spec/capture.md` § medium
 * reached the same conclusion about `video`-as-a-type, and the same argument
 * retires `article`.
 */
/**
 * **No seeded rows left.** Dishes, Pantry, People, Workouts and Places all
 * render real tables now; the last five `place` rows went when Places shipped
 * on 2026-09-07. The union survives only because `Section` is built from it —
 * the kinds name screens, not data. spec/notes.md.
 */
export type ItemKind = 'recipe' | 'place' | 'workout';

export interface SavedItem {
  id: string;
  kind: ItemKind;
  title: string;
  /** Domain or app it was captured from. */
  source: string;
  /** Day of the month it was captured. */
  day: number;
  /** ISO local day it was captured — where the printed month comes from. */
  date?: string;
  /** The agent's filing decision. */
  category: string;
  /** 0–1. Below `CONFIRM_BELOW` it waits in the inbox for you to confirm. */
  confidence: number;
  /** Whether you ever actually opened, cooked or used it. */
  used: boolean;
  /** Cross-link into a mode, shown under the title. */
  link?: string;
}

/** Captures the agent wasn't sure enough about to file silently. */
export const CONFIRM_BELOW = 0.7;

export const LIBRARY: SavedItem[] = [

];
