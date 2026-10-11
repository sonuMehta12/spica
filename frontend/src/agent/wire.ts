import { color } from '../theme';
import type { WireCard } from '../data/api';
import type { ChatMsg, ConfirmField, ConfirmMsg, SuggestItem } from '../types';

/**
 * The server's card into the shape `Conversation` draws. Unknown kinds fall
 * back to the agent bubble rather than vanishing — a card the client has not
 * learned yet should still show its text, not silently disappear.
 */
export function toChatMsg(c: WireCard, i: number, at: string): ChatMsg | null {
  const id = `${at}-${i}`;
  switch (c.kind) {
    case 'agent':
      return { kind: 'agent', id, title: '', hl: '', hlColor: color.ink,
               body: String(c.text ?? '') };
    case 'table':
      // Ids, not rows: the card resolves them against live data, and asks
      // for the ones the deck's window does not hold.
      return { kind: 'table', id, heading: String(c.heading ?? ''),
               source: (c.source as 'paisa' | 'diet') ?? 'paisa',
               ids: (c.ids as string[]) ?? [] };
    case 'confirm':
      return {
        kind: 'confirm', id,
        source: (c.source as ConfirmMsg['source']) ?? 'paisa',
        rowId: (c.row_id as string | null) ?? null,
        state: (c.state as ConfirmMsg['state']) ?? 'written',
        lede: String(c.lede ?? ''),
        fields: (c.fields as ConfirmField[]) ?? [],
        unresolved: (c.unresolved as string[]) ?? [],
        needsQuantity: (c.needs_quantity as string[]) ?? [],
      };
    case 'suggest': {
      type Wire = Record<string, unknown>;
      const items = ((c.items as Wire[]) ?? []).map((it): SuggestItem => ({
        type: (it.type as 'dish' | 'exercise') ?? 'dish',
        ref: String(it.ref ?? ''),
        name: String(it.name ?? ''),
        why: String(it.why ?? ''),
        saved: Boolean(it.saved),
        mealType: (it.meal_type as string | null) ?? null,
        minutes: (it.minutes as number | null) ?? null,
        proteinG: it.protein_g == null ? null : Number(it.protein_g),
        kcal: (it.kcal as number | null) ?? null,
        imageUrl: (it.image_url as string | null) ?? null,
        missing: (it.missing as string[]) ?? [],
        exerciseKind: (it.exercise_kind as string | null) ?? null,
        muscleGroup: (it.muscle_group as string | null) ?? null,
        tried: (it.tried as number | null) ?? null,
      }));
      return { kind: 'suggest', id, items };
    }
    case 'ask':
      return { kind: 'ask', id, question: String(c.question ?? ''),
               options: (c.options as string[]) ?? [],
               pendingRowId: (c.pending_row_id as string | null) ?? null };
    case 'todos':
      // A task question, answered with the live list — the + menu's card,
      // narrowed to the project the agent named. Its sentence is the card
      // before this one, so this one draws no line of its own.
      return { kind: 'todo', id, scope: c.scope === 'work' ? 'work' : 'all',
               project: typeof c.project === 'string' && c.project.trim() ? c.project : null,
               agent: true };
    case 'commitments':
      // The agent read what is owed. No rows travel: the card draws this
      // month's commitments from live state, so an edit or a delete anywhere
      // shows here.
      return { kind: 'commitments', id };
    default:
      return null;
  }
}
