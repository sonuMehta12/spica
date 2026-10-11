import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import Header from '../components/Header';
import ModeDeck from '../components/ModeDeck';
import { TODAY_ISO } from '../data/live';
import { MODES } from '../modes';
import { heroFor, rollUp } from '../state/usePersonaOS';
import { font, space } from '../theme';
import type { Mode, Range } from '../types';
import { DEMO_DECK, DEMO_LIMIT, DEMO_LOGGED, ensureDemoDeck } from './demo';
import { LogCard, Said, Wave, type Row } from './parts';

/**
 * The app's own home screen — the real ModeDeck and HeroCard, on the example
 * month in `demo.ts` — running a loop: the deck turns to a mode, a sentence is
 * said, it lands as a row, and the card above moves because the row is now in
 * what it computes from. Swipe it, change its range, tick a task: it is the
 * deck, not a picture of it.
 *
 * Laid out at a phone's width and zoomed to fit the drawn phone, so the card
 * is exactly the one in the app rather than a squeezed cousin of it.
 */

/** The width the app is designed at. */
const APP_W = 390;

interface Line {
  said: string;
  heading: string;
  rows: Row[];
  note: string;
}

const LINES: Record<Mode, Line> = {
  paisa: {
    said: 'Rapido home, one sixty',
    heading: 'Logged · Paisa',
    rows: [
      { label: 'Amount', value: '₹160' },
      { label: 'Category', value: 'Transport', guessed: true },
    ],
    note: 'Today’s ring moved.',
  },
  diet: {
    said: '2 roti, dal and a salad',
    heading: 'Logged · Diet',
    rows: [
      { label: 'Protein', value: '18 g', guessed: true },
      { label: 'Calories', value: '410 kcal', guessed: true },
    ],
    note: 'Protein is up on the card.',
  },
  work: {
    said: 'pricing sheet bhej diya',
    heading: 'Done · Work',
    rows: [{ label: 'Task', value: 'Send the pricing sheet' }],
    note: 'Ticked. One fewer open.',
  },
};

// listening → said → logged, per mode
const STEP_MS = [1600, 1100, 3900];

export default function RealDeck() {
  // The live module's bindings become the example month. Only this page ever
  // renders this, and a real load overwrites every binding it sets.
  useState(ensureDemoDeck);

  const [index, setIndex] = useState(0);
  const [phase, setPhase] = useState(0);
  const [range, setRange] = useState<Range>('aaj');
  const [moreOpen, setMoreOpen] = useState(false);
  const [ticked, setTicked] = useState<Set<string>>(new Set());
  const reduced = useMemo(() => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false, []);

  useEffect(() => {
    if (reduced) return;
    const id = window.setTimeout(() => {
      if (phase < 2) setPhase(phase + 1);
      else {
        setPhase(0);
        setIndex((i) => (i + 1) % MODES.length);
      }
    }, STEP_MS[phase]);
    return () => window.clearTimeout(id);
  }, [phase, index, reduced]);

  const mode = MODES[index].id;
  const logged = reduced || phase === 2;

  const heroes = useMemo(() => {
    const tx = mode === 'paisa' && logged ? [...DEMO_DECK.tx, DEMO_LOGGED.paisa] : DEMO_DECK.tx;
    const meals = mode === 'diet' && logged ? [...DEMO_DECK.meals, DEMO_LOGGED.diet] : DEMO_DECK.meals;
    // A task flips if the loop's sentence ticked it or the visitor did — not both.
    const todos = DEMO_DECK.todos.map((t) => {
      const bySentence = mode === 'work' && logged && t.id === DEMO_LOGGED.work;
      if (bySentence === ticked.has(t.id)) return t;
      const done = !t.done;
      return { ...t, done, doneOn: done ? TODAY_ISO : undefined };
    });
    const snap = rollUp({ tx, meals, committedTx: DEMO_DECK.committedTx, limitInfo: DEMO_LIMIT, pending: DEMO_DECK.pending });
    const habitDays = DEMO_DECK.habitLogs.map((l) => ({ date: l.date, habit: l.habit, amount: l.amount }));
    return MODES.map((m) => heroFor(m.id, range, snap, DEMO_LIMIT.limit, DEMO_LIMIT.pool, todos, habitDays));
  }, [mode, logged, range, ticked]);

  // Zoom the phone-width layout to whatever the drawn phone's screen is.
  const outer = useRef<HTMLDivElement>(null);
  const [box, setBox] = useState({ w: 308, h: 640 });
  useLayoutEffect(() => {
    const el = outer.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setBox({ w: e.contentRect.width, h: e.contentRect.height }));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const k = box.w / APP_W;

  const line = LINES[mode];
  const noop = () => {};

  return (
    <div ref={outer} style={{ position: 'absolute', inset: 0, overflow: 'hidden' }}>
      <div
        style={{
          width: APP_W,
          height: box.h / k,
          zoom: k,
          display: 'flex',
          flexDirection: 'column',
          paddingTop: 44,
          fontFamily: font.sans,
        }}
      >
        <div style={{ padding: `0 ${space.gutter}px` }}>
          <Header onMenu={noop} onClear={noop} canClear={false} clearing={false} />
        </div>
        <div style={{ padding: `0 ${space.gutter}px ${space.deckToThread}px` }}>
          <ModeDeck
            heroes={heroes}
            index={index}
            onIndex={(i) => {
              setIndex(i);
              setPhase(0);
            }}
            range={range}
            onRange={setRange}
            moreOpen={moreOpen}
            onToggleMore={() => setMoreOpen((o) => !o)}
            onToggleTask={(id) =>
              setTicked((s) => {
                const next = new Set(s);
                if (next.has(id)) next.delete(id);
                else next.add(id);
                return next;
              })
            }
            onSeeAllTasks={noop}
            onEditGoal={noop}
            onEditTargets={noop}
            onOpenReport={noop}
          />
        </div>

        {/* The speaker changes between the two, so the app's wider gap. */}
        <div className="lp-demo-thread" style={{ padding: `0 ${space.gutter}px`, gap: space.newSpeaker }}>
          {phase >= 1 && !reduced && (
            <Said key={`${mode}-said`} style={{ animation: 'lp-pop 0.5s cubic-bezier(.2,.8,.2,1.2) both' }}>
              {line.said}
            </Said>
          )}
          {logged && (
            <div key={`${mode}-log`} className="lp-demo-step">
              <LogCard heading={line.heading} rows={line.rows} note={line.note} />
            </div>
          )}
        </div>

        <div style={{ padding: `12px ${space.gutter}px 16px` }}>
          <div className="lp-demo-composer">
            {phase === 0 && !reduced ? 'Listening…' : 'Say it or type it'}
            <span className="lp-demo-mic" style={{ width: 40, height: 40 }}>
              {phase === 0 && !reduced ? <Wave bars={4} height={16} /> : <Wave bars={4} level={0} height={16} />}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
