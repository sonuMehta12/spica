import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useRef } from 'react';
import { PROFILE } from '../data/live';
import type { ReportMode } from '../report/metrics';
import { SECTION_LABELS, type Section } from '../vault/stats';
import { GROUP_TITLES, type FieldId, type GroupKey } from './profileEdit';
import type { CommitmentSheet } from './usePersonaOS';

/**
 * Where you are, as a back stack (THEME.md § Back). Home is the root and is
 * never on it; everything opened over Home is an entry — the menu, the
 * Report, Your data and each of its sections, Profile and each of its groups,
 * the commitment sheet. Opening pushes, Back pops exactly one, to whatever
 * opened it. Tabs, ranges, filters and popovers are not places and never push.
 *
 * Every push is a history entry carrying the stack, so the in-app ←, the
 * browser's back and forward, the phone's back gesture, Escape and a reload
 * all agree. ← calls `history.back()` and popstate sets the stack.
 *
 * An entry is only ever added on a tap. Chrome skips back over entries a page
 * adds with no input behind it — and over every entry of the same page with
 * them — so one entry pushed from inside a popstate left Back unable to reach
 * the menu or Home. When Back only closes something on the page, the app
 * steps forward onto the entry it just left, which adds nothing.
 */
export type Screen =
  | { kind: 'menu' }
  /** `mode` is the Report's tab: changed in place, kept so a reload reopens it as it was left. */
  | { kind: 'report'; mode: ReportMode }
  | { kind: 'data'; section: Section | null }
  /**
   * `focus` opens that row's editor on arrival. History keeps the group
   * alone, so a reload or a Forward brings the page back without reopening
   * an editor the person had closed.
   */
  | { kind: 'profile'; group: GroupKey | null; focus: FieldId | null }
  /** The draft it opens on stays in memory: history keeps only the id. */
  | { kind: 'sheet'; id: string; sheet: CommitmentSheet };

/** What a history entry keeps of a screen. A sheet's payment never reaches session history. */
type Kept = Exclude<Screen, { kind: 'sheet' }> | { kind: 'sheet'; id: string };

/** history.state for a non-root entry. The account, so a stack never opens for someone else. */
interface Entry {
  spica: Kept[];
  account: string;
}

const keep = (sc: Screen): Kept =>
  sc.kind === 'sheet'
    ? { kind: 'sheet', id: sc.id }
    : sc.kind === 'profile'
      ? { kind: 'profile', group: sc.group, focus: null }
      : sc;

/** Home is `null`, as the entry the page loaded on. */
const entryOf = (stack: Screen[]): Entry | null =>
  stack.length ? { spica: stack.map(keep), account: PROFILE.id } : null;

const MODES: readonly ReportMode[] = ['paisa', 'diet', 'kaam'];

/** An entry written before a field existed reads with its default, never as a hole. */
const normal = (k: Kept): Kept =>
  k.kind === 'report' && !MODES.includes(k.mode) ? { kind: 'report', mode: 'paisa' } : k;

/** The stack an entry holds — this account's only; anything else reads as Home. */
function read(state: unknown): Kept[] {
  const e = state as Partial<Entry> | null;
  return e && Array.isArray(e.spica) && e.account === PROFILE.id ? e.spica.map(normal) : [];
}

/**
 * How far above the app's first entry an entry sits, whoever's it is: a
 * stack's length, or 1 for the first run's one entry.
 */
function depthOf(state: unknown): number {
  const e = state as { spica?: unknown; firstRun?: unknown } | null;
  if (e && Array.isArray(e.spica)) return e.spica.length;
  return e?.firstRun ? 1 : 0;
}

/** One place: the same kind, and the same section, group or sheet. */
export function sameEntry(a: Screen | Kept, b: Screen | Kept): boolean {
  if (a.kind === 'data' && b.kind === 'data') return a.section === b.section;
  if (a.kind === 'profile' && b.kind === 'profile') return a.group === b.group;
  if (a.kind === 'sheet' && b.kind === 'sheet') return a.id === b.id;
  return a.kind === b.kind;
}

export const keyOf = (sc: Screen): string =>
  sc.kind === 'data'
    ? `data:${sc.section ?? ''}`
    : sc.kind === 'profile'
      ? `profile:${sc.group ?? ''}`
      : sc.kind === 'sheet'
        ? `sheet:${sc.id}`
        : sc.kind;

/** A screen's name, as the ← on the screen above it says it. No screen under → Home. */
export function titleOf(sc: Screen | undefined): string {
  if (!sc) return 'Home';
  switch (sc.kind) {
    case 'menu':
      return 'Menu';
    case 'report':
      return 'Report';
    case 'data':
      return sc.section ? SECTION_LABELS[sc.section] : 'Your data';
    case 'profile':
      return sc.group ? GROUP_TITLES[sc.group] : 'Profile';
    case 'sheet':
      return sc.sheet.editing ? 'Edit commitment' : 'Add commitment';
  }
}

/** The stack to open on: a reload reopens the screen it left — never a sheet, whose draft is gone. */
export function initialStack(): Screen[] {
  const kept = read(window.history.state);
  const sheet = kept.findIndex((k) => k.kind === 'sheet');
  return (sheet < 0 ? kept : kept.slice(0, sheet)) as Screen[];
}

/**
 * An entry's stack, with the screens still in memory kept as they are (a
 * sheet's draft, a deep link's focus). A sheet that is not in memory any more
 * is dead: its entry outlived it.
 */
function merge(kept: Kept[], cur: Screen[]): { next: Screen[]; dead: boolean } {
  const next: Screen[] = [];
  for (let i = 0; i < kept.length; i++) {
    const k = kept[i];
    if (cur[i] && sameEntry(cur[i], k)) next.push(cur[i]);
    else if (k.kind === 'sheet') return { next, dead: true };
    else next.push(k);
  }
  return { next, dead: false };
}

// ── traversals the app starts ────────────────────────────────────────────
//
// ← , X, a sheet's save, a send, and the step forward after Back closed
// something all move through history, and the popstate that comes back must
// not be mistaken for the person's own back. Each one records the stack
// length it will land on; only a popstate that lands elsewhere is the
// person's. A second ← while one is in flight is ignored, so a double tap
// cannot skip a level — and the mark clears itself, so ← can never stick.
const nav = {
  expect: null as number | null,
  timer: undefined as ReturnType<typeof setTimeout> | undefined,
  /** A close-all asked for while a traversal was in flight, run when it lands. */
  then: null as (() => void) | null,
  /** A close-all (a send): the answer is in the thread, so focus does not jump back to the menu. */
  quiet: false,
  /** Signed out, and on the way back to the app's first entry: nothing else answers a popstate. */
  leaving: false,
};

function traverse(land: number, delta: number) {
  nav.expect = land;
  clearTimeout(nav.timer);
  nav.timer = setTimeout(() => {
    nav.expect = null;
    nav.then = null;
  }, 1000);
  window.history.go(delta);
}

/** True while `leaveStack` is stepping back: the first run's own back listener stands aside. */
export const leavingStack = () => nav.leaving;

/**
 * Signed out — by the menu, or by a 401 mid-session. The entries above the
 * app's first one are this session's screens, and Back must never open them
 * again, for this account or the next. This steps back to that first entry
 * (a traversal, which adds nothing) and wipes it. Called again on its way —
 * several requests can fail at once — it does nothing more.
 */
export function leaveStack(): void {
  if (nav.leaving) return;
  // A traversal the app started is still on its way: wait for where it lands.
  const inFlight = nav.expect !== null;
  const depth = depthOf(window.history.state);
  if (!inFlight && depth === 0) {
    window.history.replaceState(null, '');
    return;
  }
  nav.leaving = true;
  const done = () => {
    window.removeEventListener('popstate', land);
    clearTimeout(timer);
    window.history.replaceState(null, '');
    nav.leaving = false;
  };
  const land = (e: PopStateEvent) => {
    nav.expect = null;
    nav.then = null;
    clearTimeout(nav.timer);
    const d = depthOf(e.state);
    if (d > 0) window.history.go(-d);
    else done();
  };
  // No landing (the entries below were never there): wipe where it stands.
  const timer = setTimeout(done, 1500);
  window.addEventListener('popstate', land);
  if (!inFlight) window.history.go(-depth);
}

// ── what Back closes first ───────────────────────────────────────────────

/** Which layer a component is drawn in: 0 is Home, 1 the first screen over it. */
export const LayerDepth = createContext(0);

interface Step {
  depth: number;
  order: number;
  run: () => void;
}
const steps = new Map<number, Step>();
let seq = 0;

/**
 * The web's BackHandler. While `enabled`, Back — Escape, or the browser's
 * back — runs `onBack` instead of leaving the screen: a popover, an inline
 * editor, a form, a filter closes first. Only steps on the top layer count,
 * and the one opened last wins, so Back closes things innermost first. The
 * on-screen ← is not Back: it leaves the page.
 *
 * Enable it only while its subject is on screen: a row's tray left open on a
 * tab that is not showing must not take a press.
 */
export function useBack(enabled: boolean, onBack: () => void): void {
  const depth = useContext(LayerDepth);
  const run = useRef(onBack);
  useLayoutEffect(() => {
    run.current = onBack;
  });
  useEffect(() => {
    if (!enabled) return;
    const id = ++seq;
    steps.set(id, { depth, order: id, run: () => run.current() });
    return () => {
      steps.delete(id);
    };
  }, [enabled, depth]);
}

/**
 * When what had focus leaves the page — an editor or form closed by Back,
 * Escape, Cancel or Save — focus goes back to the most recent thing focused
 * before it on the same layer: the row or button that opened it, not the page
 * body (THEME.md § Back). Only within a layer that is still there: a layer
 * that closes returns focus through its own opener (useNav), and a send that
 * clears the stack leaves focus where the answer is.
 *
 * Watching removals rather than blur: a browser does not reliably fire blur
 * when the focused element is taken out of the page.
 */
export function useFocusReturn(): void {
  useEffect(() => {
    const layerOf = (el: Element) => el.closest('[data-layer]')?.getAttribute('data-layer') ?? 'base';
    const recent: { el: HTMLElement; layer: string }[] = [];
    const onIn = (e: FocusEvent) => {
      if (!(e.target instanceof HTMLElement)) return;
      const el = e.target;
      const at = recent.findIndex((r) => r.el === el);
      if (at >= 0) recent.splice(at, 1);
      recent.push({ el, layer: layerOf(el) });
      if (recent.length > 16) recent.shift();
    };
    const watch = new MutationObserver(() => {
      const last = recent[recent.length - 1];
      if (!last || last.el.isConnected) return;
      const now = document.activeElement;
      if (now && now !== document.body) return;
      for (let i = recent.length - 2; i >= 0; i--) {
        const { el, layer } = recent[i];
        if (layer !== last.layer || !el.isConnected || el.closest('[inert]')) continue;
        el.focus({ preventScroll: true });
        if (document.activeElement === el) return;
      }
    });
    document.addEventListener('focusin', onIn);
    watch.observe(document.body, { childList: true, subtree: true });
    return () => {
      document.removeEventListener('focusin', onIn);
      watch.disconnect();
    };
  }, []);
}

function innermost(depth: number): Step | null {
  let best: Step | null = null;
  for (const s of steps.values()) if (s.depth === depth && (!best || s.order > best.order)) best = s;
  return best;
}

const TEXTLESS = new Set(['checkbox', 'radio', 'button', 'submit', 'reset', 'range', 'color', 'file']);
const isField = (el: HTMLElement) =>
  el instanceof HTMLTextAreaElement ||
  el instanceof HTMLSelectElement ||
  (el instanceof HTMLInputElement && !TEXTLESS.has(el.type)) ||
  el.isContentEditable;

/**
 * The stack's moves. `apply` sets the stack in state; nothing else may.
 *
 * - push: a history entry, then the screen. Only ever from a tap.
 * - pop(from): back one, through history. With `from`, only if that screen is
 *   still on top.
 * - replace: the top screen changed in place (the Report's tab) — no entry.
 * - back: what Escape does — the innermost open thing on the top layer, else pop.
 * - closeAll: back to Home in one traversal. Only an ask does this.
 */
export function useNav(stack: Screen[], apply: (next: Screen[]) => void) {
  const now = useRef(stack);
  useLayoutEffect(() => {
    now.current = stack;
  }, [stack]);
  /** What had focus when each layer opened, by the layer's index — where focus returns on close. */
  const openers = useRef<(Element | null)[]>([]);

  const settle = useCallback(
    (next: Screen[]) => {
      now.current = next;
      apply(next);
    },
    [apply],
  );

  /** History's entry holds the stack on screen. When it does not, ← must still work. */
  const agrees = (cur: Screen[]) => read(window.history.state).length === cur.length;

  const push = useCallback(
    (sc: Screen) => {
      const cur = now.current;
      openers.current[cur.length] = document.activeElement;
      const next = [...cur, sc];
      window.history.pushState(entryOf(next), '');
      settle(next);
    },
    [settle],
  );

  const pop = useCallback(
    (from?: Screen) => {
      const cur = now.current;
      if (!cur.length || nav.expect !== null || nav.leaving) return;
      if (from && !sameEntry(cur[cur.length - 1], from)) return;
      const next = cur.slice(0, -1);
      if (!agrees(cur)) {
        window.history.replaceState(entryOf(next), '');
        settle(next);
        return;
      }
      traverse(next.length, -1);
    },
    [settle],
  );

  const replace = useCallback(
    (sc: Screen) => {
      const cur = now.current;
      if (!cur.length || !sameEntry(cur[cur.length - 1], sc)) return;
      const next = [...cur.slice(0, -1), sc];
      if (agrees(cur)) window.history.replaceState(entryOf(next), '');
      settle(next);
    },
    [settle],
  );

  const closeAll = useCallback(() => {
    const cur = now.current;
    if (!cur.length || nav.leaving) return;
    if (nav.expect !== null) {
      nav.then = closeAll;
      return;
    }
    nav.quiet = true;
    if (!agrees(cur)) {
      window.history.replaceState(null, '');
      settle([]);
      return;
    }
    // go(0) would reload the page; the length check above keeps it from ever being 0.
    traverse(0, -cur.length);
  }, [settle]);

  const back = useCallback(() => {
    const step = innermost(now.current.length);
    if (step) step.run();
    else pop();
  }, [pop]);

  useEffect(() => {
    const onPop = (e: PopStateEvent) => {
      if (nav.leaving) return;
      const cur = now.current;
      const kept = read(e.state);
      const ours = nav.expect !== null && kept.length === nav.expect;
      if (nav.expect !== null) {
        nav.expect = null;
        clearTimeout(nav.timer);
      }
      // The person's own one step back while something is open on the page:
      // that closes instead, and the app steps forward onto the entry just
      // left. Never a push here — there is no tap behind it (see the top).
      if (!ours && cur.length > 0 && kept.length === cur.length - 1) {
        const step = innermost(cur.length);
        if (step) {
          step.run();
          traverse(cur.length, 1);
          return;
        }
      }
      const { next, dead } = merge(kept, cur);
      settle(next);
      // A sheet's entry, reached by Forward after the sheet closed: step off
      // it, onto the screen it was opened from.
      if (dead) traverse(kept.length - 1, -1);
      else if (ours && nav.then) {
        const then = nav.then;
        nav.then = null;
        then();
      }
    };
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, [settle]);

  // Opening on an entry that is not a place is stepped off, silently, so the
  // first Back here is a real one: a sheet's, after a reload (its draft is
  // gone), or the first run's, left under Home when it was finished on
  // another device or in another tab.
  useEffect(() => {
    nav.quiet = false;
    if (nav.expect !== null || nav.leaving) return;
    const state = window.history.state as { firstRun?: boolean } | null;
    if (state?.firstRun) {
      traverse(0, -1);
      return;
    }
    const kept = read(state);
    const cur = now.current;
    if (kept.length > cur.length) traverse(cur.length, cur.length - kept.length);
  }, []);

  // Escape is Back. A text field keeps its own Escape (an editor cancels
  // itself, the composer drops its edit); one that does not handle it is left.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape' || e.defaultPrevented || e.isComposing) return;
      const t = e.target;
      if (t instanceof HTMLElement && isField(t)) {
        t.blur();
        return;
      }
      e.preventDefault();
      back();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [back]);

  // Closing a layer returns focus to what opened it: the Menu button, the row
  // that was tapped, Add commitment. One that has gone since (a popover's
  // item) leaves focus on the screen now on top, not lost on the page.
  const was = useRef(stack.length);
  useEffect(() => {
    const before = was.current;
    was.current = stack.length;
    if (stack.length >= before) return;
    const el = openers.current[stack.length];
    openers.current.length = stack.length;
    if (nav.quiet) {
      nav.quiet = false;
      return;
    }
    if (el instanceof HTMLElement && el.isConnected) el.focus({ preventScroll: true });
    else if (stack.length)
      document
        .querySelector<HTMLElement>(`[data-layer="${stack.length}"] [role="dialog"]`)
        ?.focus({ preventScroll: true });
  }, [stack.length]);

  return { push, pop, replace, back, closeAll };
}
