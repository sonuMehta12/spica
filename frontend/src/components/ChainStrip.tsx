import HabitIcon, { habitTone } from './HabitIcon';
import { shortDay } from '../lib/format';
import { color, font } from '../theme';
import type { ChainDay } from '../types';

/**
 * The week's habits, as seven marks — every habit, not just workouts.
 *
 * A day's habits stack as overlapping icon coins, the avatar-stack pattern.
 * The stack itself is fixed; what adapts is the room each day is given, so a
 * heavy day never crowds the days beside it:
 * one habit is one coin however many times it happened, a heavy day is visibly
 * denser, an empty day is a hollow mark. The count rides on the coin as a small
 * badge, so two cigarettes stay one cigarette rather than becoming two marks.
 *
 * Colour comes from the habit's nature (`HabitIcon`), which is the strip's one
 * opinion: it still shows no target, no streak and no judgement of a day.
 *
 * Day letters sit in a small row above the marks. It is the Diet card's band —
 * the row Paisa and Work give to their three figures.
 */
const MARK = 15;
const MAX_ICONS = 3;

/** How much of a coin the one stacked on top of it covers — the avatar-stack
 *  overlap. A day's own coins sit exactly as they always have. */
const OVERLAP = Math.round(MARK / 3);
/** So each coin after the first advances by this much. */
const STEP = MARK - OVERLAP;

/** The room a day needs: its first coin, the advance of each one stacked on
 *  top, and a little more when the stack overflows into `+N`. */
const slotFor = (d: ChainDay) =>
  MARK +
  Math.max(0, Math.min(d.habits.length, MAX_ICONS) - 1) * STEP +
  (d.habits.length > MAX_ICONS ? 10 : 0);

export default function ChainStrip({ chain, count }: { chain: ChainDay[]; count: number }) {
  return (
    <div
      role="img"
      aria-label={`Something logged on ${count} day${count === 1 ? '' : 's'} this week`}
      style={{
        display: 'flex',
        gap: 6,
        alignItems: 'flex-end',
        paddingTop: 10,
        borderTop: `1px solid ${color.border}`,
      }}
    >
      {/* A label on the marks' own line, like the figures' labels on the
          other two cards: it says what the marks count. */}
      <div
        style={{
          fontFamily: font.sans,
          fontSize: 11,
          lineHeight: `${MARK}px`,
          color: color.faint,
          flex: '0 0 auto',
          marginRight: 6,
        }}
      >
        Habits
      </div>

      {chain.map((d, i) => (
        <div
          key={i}
          title={`${shortDay(d.date)}${
            d.habits.length
              ? ` — ${d.habits.map((h) => (h.count > 1 ? `${h.habit} ×${h.count}` : h.habit)).join(', ')}`
              : ''
          }`}
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 2,
            // Each day takes exactly the room its own stack needs, so a heavy
            // day widens its own slot rather than spilling over the days
            // either side of it — the spacing between days is what gives, not
            // the stack. Letters stay centred over their own marks.
            width: slotFor(d),
          }}
        >
          <span
            style={{
              fontFamily: font.sans,
              fontSize: 9,
              lineHeight: '10px',
              color: d.isToday ? color.ink : d.future ? color.grey : color.faint,
              fontWeight: d.isToday ? 600 : 400,
            }}
          >
            {d.letter}
          </span>

          {d.habits.length === 0 ? (
            <span
              style={{
                width: MARK,
                height: MARK,
                borderRadius: '50%',
                border: `1.4px solid ${d.future ? color.line : color.ringIdle}`,
                // Today is marked by a ring in the card's own hue — an outline,
                // not a lift.
                boxShadow: d.isToday ? `0 0 0 1.5px ${color.dietSoft}` : 'none',
              }}
            />
          ) : (
            <span style={{ display: 'flex', height: MARK, alignItems: 'center' }}>
              {d.habits.slice(0, MAX_ICONS).map((h, j) => (
                <span
                  key={h.habit}
                  style={{
                    position: 'relative',
                    display: 'flex',
                    // Coins overlap from the right, so each one's left edge
                    // stays clear — which is where the count badge sits.
                    marginLeft: j === 0 ? 0 : -OVERLAP,
                  }}
                >
                  <HabitIcon habit={h.habit} size={MARK} />
                  {h.count > 1 && (
                    <span
                      style={{
                        position: 'absolute',
                        left: -3,
                        bottom: -3,
                        minWidth: 9,
                        height: 9,
                        padding: '0 1.5px',
                        borderRadius: 5,
                        background: habitTone(h.habit).ink,
                        color: color.white,
                        fontFamily: font.sans,
                        fontSize: 7,
                        lineHeight: '9px',
                        fontWeight: 600,
                        textAlign: 'center',
                      }}
                    >
                      {Math.round(h.count * 10) / 10}
                    </span>
                  )}
                </span>
              ))}
              {d.habits.length > MAX_ICONS && (
                <span
                  style={{
                    marginLeft: 1,
                    fontFamily: font.sans,
                    fontSize: 9,
                    color: color.faint,
                  }}
                >
                  +{d.habits.length - MAX_ICONS}
                </span>
              )}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}
