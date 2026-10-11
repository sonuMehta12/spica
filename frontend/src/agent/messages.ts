import { DIET_TODAY_ISO, PROTEIN_TARGET, TODAY_ISO } from '../data/live';
import { nextId, rupees } from '../lib/format';
import { color } from '../theme';
import type { AgentMsg, ComposerContext, Meal, TodoMsg, Tx, UserMsg } from '../types';

/** Everything the agent needs to reason about a log before it is committed. */
export interface Ledger {
  tx: Tx[];
  meals: Meal[];
}

export function userMsg(text: string, context?: ComposerContext | null): UserMsg {
  return { kind: 'user', id: nextId('u'), text, ...(context ? { context } : {}) };
}

/** What's left of today's spend allowance once `amt` lands. */
export function paisaConfirm(
  ledger: Ledger,
  limit: number | null,
  name: string,
  cat: string,
  amt: number,
): AgentMsg {
  const spent = ledger.tx.filter((t) => (t.date ?? TODAY_ISO) === TODAY_ISO).reduce((a, t) => a + t.amt, 0) + amt;
  // Unknown is not zero: with no limit yet (no income this month) there is
  // nothing to be left of, so the line says only what was logged.
  const rem = limit == null ? null : limit - spent;
  return {
    kind: 'agent',
    id: nextId('a'),
    title: 'Logged ✓',
    hl: `${name} ${rupees(amt)}`,
    hlColor: rem != null && rem < 0 ? color.red : color.paisaInk,
    body:
      rem == null
        ? `${cat}.`
        : `${cat}. Today ` +
          (rem < 0
            ? `${rupees(-rem)} over the limit — go easy tomorrow.`
            : `${rupees(rem)} left.`),
  };
}

/** How much protein is still owed today once this meal lands. */
export function dietConfirm(ledger: Ledger, name: string, p: number, k: number): AgentMsg {
  const cur = ledger.meals.filter((m) => (m.date ?? DIET_TODAY_ISO) === DIET_TODAY_ISO).reduce((a, m) => a + m.p, 0) + p;
  // No target set → no "still owed"; the number stands on its own.
  const remP = PROTEIN_TARGET == null ? null : Math.max(0, PROTEIN_TARGET - cur);
  return {
    kind: 'agent',
    id: nextId('a'),
    title: 'Logged ✓',
    hl: `${name} · ${p}g`,
    hlColor: color.dietInk,
    body:
      remP == null
        ? `${k} kcal. Protein now ${cur}g.`
        : `${k} kcal. Protein now ${cur}g — ` +
          (remP > 0
            ? `${remP}g more today. Soya keema tonight covers it.`
            : 'target met 🎯'),
  };
}

/** A plain "not built yet" card — used by the drawer rows and the Work mode. */
export function stubMsg(title: string, body: string): AgentMsg {
  return { kind: 'agent', id: nextId('a'), title, hl: '', hlColor: color.ink, body };
}

export function todoMsg(scope: TodoMsg['scope'] = 'all'): TodoMsg {
  return { kind: 'todo', id: nextId('td'), scope };
}

/** Shown when free text carries no amount the agent can hang a log on. */
export function unparsedMsg(): AgentMsg {
  return stubMsg('Say that again?', 'No amount found. Like "chai 20".');
}

