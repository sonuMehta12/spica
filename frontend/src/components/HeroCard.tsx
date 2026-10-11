import { useEffect, useRef, useState } from 'react';
import ConcentricRings, { DormantRing } from './ConcentricRings';
import { KebabIcon } from './Icons';
import RingLegend from './RingLegend';
import ChainStrip from './ChainStrip';
import ProjectChart from './ProjectChart';
import TaskList from './TaskList';
import Dot from './messages/Dot';
import { DIET_TODAY_ISO, SAVINGS_TARGET, SLEEP, STEPS } from '../data/live';
import { duration } from '../lib/clock';
import { rupees } from '../lib/format';
import { color, font, radius, shadow } from '../theme';
import type { HeroView } from '../types';
import { useBack } from '../state/nav';

/**
 * Everything without a ring of its own, behind the card's overflow menu —
 * macros plus the two passively detected signals.
 */
function moreRows(): [string, string][] {
  const night = SLEEP.find((n) => n.date === DIET_TODAY_ISO);
  const walk = STEPS.find((d) => d.date === DIET_TODAY_ISO);
  return [
    ['Fat', '28g'],
    ['Fibre', '11g'],
    ['Sleep', night ? duration(night.endMin - night.startMin) : '—'],
    ['Steps', walk ? walk.steps.toLocaleString('en-IN') : '—'],
  ];
}

/** Movement and dwell past which a press is a swipe or a hold, not a tap. */
const TAP_SLOP = 8;
const TAP_MS = 500;

/**
 * Controls inside the card that own their own tap. A press landing on any of
 * these is theirs — ticking a task must never also open the report.
 */
const INTERACTIVE = 'button, select, a, input, [role="checkbox"], [role="menu"], [role="menuitem"]';

interface Props {
  hero: HeroView;
  /** Inactive pages stay rendered for the swipe, but out of the tab order. */
  active: boolean;
  moreOpen: boolean;
  onToggleMore: () => void;
  onEditGoal: () => void;
  onEditTargets: () => void;
  onToggleTask: (id: string) => void;
  onSeeAllTasks: () => void;
  /** Tapping the card's own space opens this mode's report. */
  onOpenReport: () => void;
}

interface MenuItem {
  key: string;
  label: string;
  run: () => void;
  /** Shown, not tappable. */
  info?: boolean;
  /** The value is an estimate: the dot says so. */
  dot?: boolean;
}

/**
 * One mode's card. All three share one anatomy: the figure on the left, its
 * legend (or, on Work, the next tasks) on the right, and a band along the
 * bottom. The card is white with a border, like every card — a tinted panel on
 * the white page read as one surface stacked on another — and has no shadow;
 * its menu sits top right, out of flow.
 */
export default function HeroCard({
  hero,
  active,
  moreOpen,
  onToggleMore,
  onEditGoal,
  onEditTargets,
  onToggleTask,
  onSeeAllTasks,
  onOpenReport,
}: Props) {
  const tab = active ? 0 : -1;
  const isWork = hero.mode === 'work';
  const press = useRef<{ x: number; y: number; t: number } | null>(null);

  const [menuOpen, setMenuOpen] = useState(false);
  const menuWrap = useRef<HTMLDivElement>(null);
  /** The ⋮ itself: a chosen item hands focus back to it, so a page it opens returns focus here, not to a gone item. */
  const trigger = useRef<HTMLButtonElement>(null);

  // Swiping away should not leave a menu hanging open on an off-screen card.
  useEffect(() => {
    if (!active) setMenuOpen(false);
  }, [active]);

  useEffect(() => {
    if (!menuOpen) return;
    const close = (e: Event) => {
      if (!menuWrap.current?.contains(e.target as Node)) setMenuOpen(false);
    };
    document.addEventListener('pointerdown', close);
    return () => document.removeEventListener('pointerdown', close);
  }, [menuOpen]);
  // Escape, and Back on the screen this sits on, close the ⋮ and nothing else.
  useBack(menuOpen, () => setMenuOpen(false));

  /** The card's overflow menu. Only rendered when it has something to hold. */
  const menuItems: MenuItem[] = isWork
    ? [{ key: 'all', label: 'All tasks', run: onSeeAllTasks }]
    : hero.hasMacros
      ? [
          { key: 'more', label: moreOpen ? 'Hide' : 'More', run: onToggleMore },
          // The rings' denominators. Same composer edit as the goal.
          { key: 'targets', label: 'Edit targets', run: onEditTargets },
        ]
      : [
          // The goal drives the daily limit but shows nowhere on the card —
          // an explainer line was tried and confused more than it explained.
          // The menu is where it lives instead: visible on demand, silent
          // otherwise.
          // No goal set reads as that, not as a ₹0 goal: unknown is not zero.
          {
            key: 'goal',
            label: SAVINGS_TARGET ? `Edit goal · ${rupees(SAVINGS_TARGET)}` : 'Set a goal',
            run: onEditGoal,
          },
          // Last month's repeating costs not yet paid — held out of the limit.
          // An estimate, so the dot says so; nothing to tap.
          ...(hero.locked
            ? [{ key: 'locked', label: `Locked · ${rupees(hero.locked)}`, info: true, dot: true, run: () => {} }]
            : []),
        ];

  return (
    <div
      // A press that barely moved, on the card's own space, opens the report.
      // `pointerdown` alone cannot be used — the deck's swipe starts with one
      // too, so this has to wait for the release and measure the distance.
      onPointerDown={(e) => {
        press.current = { x: e.clientX, y: e.clientY, t: e.timeStamp };
      }}
      onPointerUp={(e) => {
        const start = press.current;
        press.current = null;
        if (!active || !start) return;
        if (Math.hypot(e.clientX - start.x, e.clientY - start.y) > TAP_SLOP) return;
        if (e.timeStamp - start.t > TAP_MS) return;
        if (e.target instanceof Element && e.target.closest(INTERACTIVE)) return;
        onOpenReport();
      }}
      onPointerCancel={() => {
        press.current = null;
      }}
      style={{
        position: 'relative',
        background: color.white,
        border: `1px solid ${color.border}`,
        borderRadius: radius.deck,
        padding: 16,
        height: '100%',
        boxSizing: 'border-box',
        // A column, so the band can sit at the bottom of whatever height the
        // tallest card set — every mode's band lands on the same line.
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {hero.live ? (
        <>
          {menuItems.length > 0 && (
            <div ref={menuWrap} style={{ position: 'absolute', top: 8, right: 8, zIndex: 2 }}>
              <button
                ref={trigger}
                type="button"
                onClick={() => setMenuOpen((o) => !o)}
                tabIndex={tab}
                aria-label={`${hero.label} — more options`}
                aria-haspopup="menu"
                aria-expanded={menuOpen}
                className="hov-tint"
                style={{
                  width: 32,
                  height: 32,
                  borderRadius: '50%',
                  border: 'none',
                  background: menuOpen ? color.lineSoft : 'none',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                  padding: 0,
                }}
              >
                <KebabIcon size={18} stroke={color.muted} />
              </button>

              {menuOpen && (
                <div
                  role="menu"
                  style={{
                    position: 'absolute',
                    right: 0,
                    top: 36,
                    zIndex: 5,
                    background: color.white,
                    border: `1px solid ${color.line}`,
                    borderRadius: radius.card,
                    boxShadow: shadow.popover,
                    padding: 4,
                    minWidth: 168,
                    animation: 'fadeup 0.16s',
                  }}
                >
                  {menuItems.map((it) => (
                    <button
                      key={it.key}
                      type="button"
                      role="menuitem"
                      disabled={it.info}
                      onClick={() => {
                        // Focus first: a page this opens records what had it, and returns it there on Back.
                        trigger.current?.focus({ preventScroll: true });
                        setMenuOpen(false);
                        it.run();
                      }}
                      className={it.info ? undefined : 'hov-tint'}
                      style={{
                        display: 'block',
                        width: '100%',
                        background: 'none',
                        border: 'none',
                        borderRadius: 10,
                        padding: '10px 12px',
                        cursor: it.info ? 'default' : 'pointer',
                        fontFamily: font.sans,
                        fontSize: 14,
                        lineHeight: '18px',
                        color: it.info ? color.muted : color.ink,
                        textAlign: 'left',
                      }}
                    >
                      {it.dot && <Dot />}
                      {it.label}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: isWork ? 12 : 16,
              flex: 1,
              minHeight: 0,
            }}
          >
            {/* Work gives the figure less room: the list beside it is the
                answer, and the bars are only the context for it. */}
            <div
              style={{
                flex: isWork ? '0 0 34%' : '0 0 42%',
                maxWidth: isWork ? 118 : 148,
                minWidth: isWork ? 96 : 108,
              }}
            >
              {isWork ? (
                <ProjectChart projects={hero.projects ?? []} />
              ) : (
                <ConcentricRings rings={hero.rings} />
              )}
            </div>
            {isWork ? (
              <TaskList tasks={hero.tasks ?? []} onToggle={onToggleTask} tabIndex={tab} />
            ) : (
              <div style={{ minWidth: 0, paddingRight: 20 }}>
                <RingLegend rings={hero.rings} />

                {hero.coverage && (
                  <div
                    style={{
                      marginTop: 8,
                      fontFamily: font.sans,
                      fontSize: 11,
                      lineHeight: '14px',
                      color: color.faint,
                    }}
                  >
                    {hero.coverage}
                  </div>
                )}
              </div>
            )}
          </div>

          {hero.hasMacros && moreOpen && (
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-around',
                paddingTop: 12,
                marginTop: 12,
                borderTop: `1px solid ${color.border}`,
                animation: 'fadeup 0.25s',
              }}
            >
              {moreRows().map(([label, value]) => (
                <div key={label} style={{ textAlign: 'center' }}>
                  <div style={{ fontFamily: font.sans, fontSize: 11, lineHeight: '14px', color: color.faint }}>
                    {label}
                  </div>
                  <div
                    style={{ fontFamily: font.sans, fontWeight: 500, fontSize: 15, lineHeight: '20px', marginTop: 2, color: color.ink }}
                  >
                    {value}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* The band: one labelled figure per column, or the week's habits.
              In flow at the bottom — every card has one, so the deck is as
              tall as its tallest card and each band lands on the same line. */}
          {hero.strip && (
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: `repeat(${hero.strip.length}, 1fr)`,
                columnGap: 8,
                marginTop: 14,
                paddingTop: 10,
                borderTop: `1px solid ${color.border}`,
              }}
            >
              {hero.strip.map((c) => (
                <div key={c.key} style={{ minWidth: 0 }}>
                  <div
                    style={{
                      fontFamily: font.sans,
                      fontSize: 11,
                      lineHeight: '14px',
                      color: color.faint,
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}
                  >
                    {c.label}
                  </div>
                  <div
                    style={{
                      fontFamily: font.sans,
                      fontSize: 14,
                      lineHeight: '18px',
                      fontWeight: 500,
                      marginTop: 2,
                      color: c.tone === 'red' ? color.red : color.ink,
                    }}
                  >
                    {c.value}
                  </div>
                </div>
              ))}
            </div>
          )}

          {hero.chain && (
            <div style={{ marginTop: 14 }}>
              <ChainStrip chain={hero.chain} count={hero.chainCount ?? 0} />
            </div>
          )}
        </>
      ) : (
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, minHeight: 168 }}>
          <DormantRing glyph={hero.label.charAt(0)} />
          <div style={{ flex: 1 }}>
            <div style={{ fontFamily: font.sans, fontWeight: 500, fontSize: 15, marginBottom: 6 }}>
              {hero.label} is coming
            </div>
            <div style={{ fontFamily: font.sans, fontSize: 13, lineHeight: 1.5, color: color.muted }}>{hero.note}</div>
          </div>
        </div>
      )}
    </div>
  );
}
