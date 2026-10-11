import { CaretDown } from '@phosphor-icons/react';
import HeroCard from './HeroCard';
import { DeckPages, DeckTabs } from './Deck';
import { MODES, RANGES, rangeFor } from '../modes';
import { color, font, modeTone, space } from '../theme';
import type { HeroView, Range } from '../types';

interface Props {
  heroes: HeroView[];
  index: number;
  onIndex: (i: number) => void;
  range: Range;
  onRange: (r: Range) => void;
  moreOpen: boolean;
  onToggleMore: () => void;
  onToggleTask: (id: string) => void;
  onSeeAllTasks: () => void;
  onEditGoal: () => void;
  onEditTargets: () => void;
  onOpenReport: (mode: HeroView['mode']) => void;
}

/**
 * The primary component: the three modes named above one card per mode, on a
 * ring. Swipe either way and the deck goes round — past Work is Paisa again —
 * or tap a name, or arrow-key along the names.
 *
 * The names are the indicator. The current one is ink with a short underline
 * in its mode's colour — the one place a mode colour touches chrome, and only
 * as a key to the card below it. The range sits at the right of the same row
 * as plain words and a caret: a native select laid over them, so a phone
 * still gets its own picker.
 *
 * The names and the ring are `DeckTabs` and `DeckPages` (`Deck.tsx`), shared
 * with the Report so its modes switch the same way. The cards share one grid
 * cell, so the deck is as tall as its tallest card.
 */
export default function ModeDeck({
  heroes,
  index,
  onIndex,
  range,
  onRange,
  moreOpen,
  onToggleMore,
  onToggleTask,
  onSeeAllTasks,
  onEditGoal,
  onEditTargets,
  onOpenReport,
}: Props) {
  const current = MODES[index] ?? MODES[0];
  const shown = rangeFor(current.id, range);
  const rangeLabel = RANGES[current.id].find((r) => r.id === shown)?.label ?? '';

  return (
    <div>
      <DeckTabs
        tabs={MODES.map((m) => ({ id: m.id, label: m.label, tone: modeTone[m.id].base }))}
        index={index}
        onIndex={onIndex}
        label="Modes"
        idPrefix="mode"
        style={{ marginBottom: space.tabsToDeck }}
      >
        {current.live && (
          <label
            style={{
              position: 'relative',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              padding: '4px 0 8px',
              fontFamily: font.sans,
              fontSize: 14,
              lineHeight: '20px',
              color: color.muted,
              cursor: 'pointer',
            }}
          >
            {rangeLabel}
            <CaretDown size={14} color="currentColor" aria-hidden />
            <select
              value={shown}
              onChange={(e) => onRange(e.target.value as Range)}
              aria-label="Time range"
              style={{
                position: 'absolute',
                inset: 0,
                width: '100%',
                opacity: 0,
                cursor: 'pointer',
                border: 'none',
                fontSize: 16,
              }}
            >
              {RANGES[current.id].map((r) => (
                <option key={r.id} value={r.id}>
                  {r.label}
                </option>
              ))}
            </select>
          </label>
        )}
      </DeckTabs>

      <DeckPages ids={heroes.map((h) => h.mode)} index={index} onIndex={onIndex} idPrefix="mode">
        {(i, active) => {
          const hero = heroes[i];
          return (
            <HeroCard
              hero={hero}
              active={active}
              moreOpen={moreOpen}
              onToggleMore={onToggleMore}
              onToggleTask={onToggleTask}
              onSeeAllTasks={onSeeAllTasks}
              onEditGoal={onEditGoal}
              onEditTargets={onEditTargets}
              onOpenReport={() => onOpenReport(hero.mode)}
            />
          );
        }}
      </DeckPages>
    </div>
  );
}
