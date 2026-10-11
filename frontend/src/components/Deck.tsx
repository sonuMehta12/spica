import { useContext, useLayoutEffect, useRef, type CSSProperties, type KeyboardEvent, type PointerEvent, type ReactNode } from 'react';
import { useSwipe } from '../lib/useSwipe';
import { LayerDepth } from '../state/nav';
import { color, font } from '../theme';

/** Gutter between pages, only ever seen mid-swipe. */
const GAP = 12;

/**
 * How a page settles: quick out of the gesture, long and soft into place —
 * the CSS stand-in for the spring Android uses.
 */
export const SETTLE_MS = 420;
export const SETTLE = `${SETTLE_MS / 1000}s cubic-bezier(0.22, 1, 0.36, 1)`;

/** `k` steps, folded onto the ring: the shortest way round, −n/2 … n/2. */
function ringStep(k: number, n: number): number {
  const m = ((k % n) + n) % n;
  return m > n / 2 ? m - n : m;
}

export interface DeckTab {
  id: string;
  label: string;
  /** The mode's colour, for the underline under the current name. */
  tone: string;
}

interface TabsProps {
  tabs: DeckTab[];
  index: number;
  onIndex: (i: number) => void;
  /** What a screen reader calls the row. */
  label: string;
  /** Ties each name to its page. Unique per screen: a layer under the top stays drawn. */
  idPrefix: string;
  style?: CSSProperties;
  /** What sits at the right end of the row — the range. */
  children?: ReactNode;
}

/**
 * The names above a deck — Home's modes, the Report's — and the one switch
 * both use. The names are the indicator: the current one is ink with a short
 * underline in its mode's colour, which grows into the new name as the old one
 * shrinks, in time with the page sliding in below. Tap a name, or arrow-key
 * along them, the way a tablist does.
 */
export function DeckTabs({ tabs, index, onIndex, label, idPrefix, style, children }: TabsProps) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);

  // Arrow keys move along the names, round the ring like the pages.
  const onKey = (e: KeyboardEvent) => {
    const step = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0;
    if (!step) return;
    e.preventDefault();
    const next = (index + step + tabs.length) % tabs.length;
    onIndex(next);
    refs.current[next]?.focus();
  };

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 12,
        ...style,
      }}
    >
      <div role="tablist" aria-label={label} onKeyDown={onKey} style={{ display: 'flex', gap: 18 }}>
        {tabs.map((t, i) => {
          const on = i === index;
          return (
            <button
              key={t.id}
              ref={(el) => {
                refs.current[i] = el;
              }}
              type="button"
              role="tab"
              id={`${idPrefix}-tab-${t.id}`}
              aria-selected={on}
              aria-controls={`${idPrefix}-panel-${t.id}`}
              tabIndex={on ? 0 : -1}
              onClick={() => onIndex(i)}
              style={{
                position: 'relative',
                background: 'none',
                border: 'none',
                padding: '4px 0 8px',
                cursor: 'pointer',
                fontFamily: font.sans,
                fontSize: 15,
                fontWeight: 500,
                lineHeight: '20px',
                color: on ? color.ink : color.faint,
                transition: 'color 0.2s',
              }}
            >
              {t.label}
              {/* Grows into the new name as the old one shrinks, in time with the page. */}
              <span
                aria-hidden="true"
                style={{
                  position: 'absolute',
                  left: '50%',
                  bottom: 0,
                  width: 16,
                  height: 2,
                  marginLeft: -8,
                  borderRadius: 1,
                  background: t.tone,
                  transform: on ? 'scaleX(1)' : 'scaleX(0)',
                  transition: `transform ${SETTLE}`,
                }}
              />
            </button>
          );
        })}
      </div>
      {children}
    </div>
  );
}

interface PagesProps {
  /** One per page, in the names' order — the same ids `DeckTabs` was given. */
  ids: string[];
  index: number;
  onIndex: (i: number) => void;
  idPrefix: string;
  /**
   * Fill the parent's height, each page scrolling on its own (the Report).
   * Without it the deck is as tall as its tallest page (Home).
   */
  fill?: boolean;
  children: (i: number, active: boolean) => ReactNode;
}

/**
 * The pages under `DeckTabs`, on a ring. Swipe either way and the deck goes
 * round — past the last is the first again — or tap a name: either way the
 * page slides to its place on the same settle, and the name's underline with
 * it.
 *
 * The pages share one grid cell, so the deck never changes height mid-swipe;
 * each is placed by its step from the current one. A page leaving the centre
 * recedes a little, so a swipe reads as turning the ring rather than sliding a
 * strip to its end.
 *
 * A page that is not showing stays drawn for the swipe, but is inert and
 * takes no Back step: an editor left open on it must not take a press
 * (THEME.md § Back).
 */
export function DeckPages({ ids, index, onIndex, idPrefix, fill = false, children }: PagesProps) {
  const n = ids.length;
  const { drag, dragging, width, handlers } = useSwipe({ index, count: n, onIndex });
  const depth = useContext(LayerDepth);

  // Where each page sat on the last committed render. A page that wraps from
  // one side to the other (the last → the first's far side) must jump, not
  // glide across the deck — it is off-screen at both ends of the jump.
  const slots = ids.map((_, i) => ringStep(i - index, n));
  const before = useRef<number[]>(slots);
  useLayoutEffect(() => {
    before.current = slots;
  });

  // A press in a field is for the field — selecting its text, not turning the page.
  const swipe = {
    ...handlers,
    onPointerDown: (e: PointerEvent<HTMLDivElement>) => {
      if (e.target instanceof Element && e.target.closest('input, textarea, select')) return;
      handlers.onPointerDown(e);
    },
  };

  return (
    <div className="deck" style={fill ? { overflow: 'hidden', flex: 1, minHeight: 0 } : { overflow: 'hidden' }} {...swipe}>
      <div style={fill ? { display: 'grid', height: '100%', gridTemplateRows: 'minmax(0, 1fr)' } : { display: 'grid' }}>
        {ids.map((id, i) => {
          const slot = slots[i];
          const wrapped = Math.abs(slot - (before.current[i] ?? slot)) > 1;
          // How far this page is from the centre, in pages: 0 at rest, 1 a full step out.
          const away = Math.min(1, Math.abs(slot + drag / (width + GAP)));
          const on = i === index;
          return (
            <div
              key={id}
              role="tabpanel"
              id={`${idPrefix}-panel-${id}`}
              aria-labelledby={`${idPrefix}-tab-${id}`}
              aria-hidden={!on}
              inert={!on}
              style={{
                gridArea: '1 / 1',
                minWidth: 0,
                transform: `translateX(calc(${slot * 100}% + ${slot * GAP + drag}px)) scale(${1 - 0.05 * away})`,
                opacity: 1 - 0.35 * away,
                transition: dragging || wrapped ? 'none' : `transform ${SETTLE}, opacity ${SETTLE}`,
                willChange: 'transform',
              }}
            >
              <LayerDepth.Provider value={on ? depth : -1}>{children(i, on)}</LayerDepth.Provider>
            </div>
          );
        })}
      </div>
    </div>
  );
}
