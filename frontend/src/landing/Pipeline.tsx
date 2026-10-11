import { useEffect, useLayoutEffect, useMemo, useRef, useState, type CSSProperties, type ReactNode } from 'react';
import Mascot from '../components/Mascot';
import TaskList from '../components/TaskList';
import { TODAY_ISO } from '../data/live';
import { addDays } from '../lib/day';
import { brand } from '../theme';
import type { Todo } from '../types';
import { ensureDemoDeck } from './demo';
import { GmailMark, KeepMark, LinearMark, SlackMark, WhatsAppMark, WisprMark } from './marks';
import { ease, seg, useInView } from './parts';

/**
 * Work, as a pipeline: tasks leave the places they were born — Linear, a
 * meeting, a chat, a note — travel down a pipe into Spica, and come out as
 * one list in the app's own task rows.
 *
 * Honest about how each gets there. Linear and Wispr Flow arrive on their own
 * (the Claude routine, spec/work-sync.md); a WhatsApp ask or a note arrives
 * when you say it to Spica; Gmail and Slack are not built, so their pipes are
 * dashed and carry nothing.
 */

type Way = 'auto' | 'say' | 'soon';

interface Source {
  key: string;
  name: string;
  mark: ReactNode;
  way: Way;
  tint: string;
}

const SOURCES: Source[] = [
  { key: 'linear', name: 'Linear', mark: <LinearMark size={22} />, way: 'auto', tint: brand.linear },
  { key: 'wispr', name: 'Wispr Flow', mark: <WisprMark size={26} />, way: 'auto', tint: brand.wispr },
  { key: 'whatsapp', name: 'WhatsApp', mark: <WhatsAppMark size={22} />, way: 'say', tint: brand.whatsapp },
  { key: 'notes', name: 'Notes', mark: <KeepMark size={22} />, way: 'say', tint: brand.keep },
  { key: 'gmail', name: 'Gmail', mark: <GmailMark size={22} />, way: 'soon', tint: brand.gmail },
  { key: 'slack', name: 'Slack', mark: <SlackMark size={21} />, way: 'soon', tint: brand.slack },
];

/** Seconds a task takes down its pipe; the loop's length. */
const TRAVEL = 1.15;
const LOOP = 10.5;

/** Which source, when it leaves, and the task it becomes. */
function packets(): { from: number; at: number; task: Todo }[] {
  const t = (id: string, name: string, project: string, extra: Partial<Todo>): Todo => ({
    id: `pipe-${id}`,
    name,
    project,
    kind: 'work',
    done: false,
    ...extra,
  });
  return [
    { from: 0, at: 0.4, task: t('checkout', 'Fix the checkout bug', 'demo-p-work', { due: TODAY_ISO, src: 'Linear · ENG-142' }) },
    { from: 1, at: 1.4, task: t('pricing', 'Send the pricing sheet', 'demo-p-work', { due: TODAY_ISO, src: 'Standup' }) },
    { from: 2, at: 2.4, task: t('deck', 'Share the deck with Rohan', 'demo-p-side', { due: addDays(TODAY_ISO, 1) }) },
    { from: 3, at: 3.4, task: t('domain', 'Renew the domain', 'demo-p-me', { due: addDays(TODAY_ISO, 3) }) },
    { from: 0, at: 4.4, task: t('review', 'Review the cart PR', 'demo-p-work', { src: 'Linear · ENG-150' }) },
  ];
}

type Pt = { x: number; y: number };
const lerp = (a: Pt, b: Pt, s: number): Pt => ({ x: a.x + (b.x - a.x) * s, y: a.y + (b.y - a.y) * s });

/** The pipe from a tile down to the hub, as a cubic's four points. */
function pipe(from: Pt, hub: Pt): [Pt, Pt, Pt, Pt] {
  const dy = hub.y - from.y;
  return [from, { x: from.x, y: from.y + dy * 0.62 }, { x: hub.x, y: hub.y - dy * 0.5 }, hub];
}

const d = ([a, b, c, e]: Pt[]) => `M${a.x},${a.y} C${b.x},${b.y} ${c.x},${c.y} ${e.x},${e.y}`;

/** The first `s` of the pipe, split by de Casteljau — its end is exactly where the packet is. */
function head(p: [Pt, Pt, Pt, Pt], s: number): [Pt, Pt, Pt, Pt] {
  const a = lerp(p[0], p[1], s);
  const b = lerp(p[1], p[2], s);
  const c = lerp(p[2], p[3], s);
  const e = lerp(a, b, s);
  const f = lerp(b, c, s);
  return [p[0], a, e, lerp(e, f, s)];
}

export default function Pipeline() {
  useState(ensureDemoDeck);
  const list = useMemo(packets, []);
  const reduced = useMemo(() => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false, []);

  const [ref, inView] = useInView<HTMLDivElement>(0.3, false);
  const [t, setT] = useState(reduced ? LOOP - 2 : 0);
  useEffect(() => {
    if (!inView || reduced) return;
    let raf = 0;
    let last = performance.now();
    const tick = (now: number) => {
      const dt = Math.min(0.1, (now - last) / 1000);
      last = now;
      setT((x) => (x + dt) % LOOP);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [inView, reduced]);

  // Pipes are drawn between the tiles and the hub as laid out, so they stay
  // attached at any width.
  const box = useRef<HTMLDivElement>(null);
  const tiles = useRef<(HTMLDivElement | null)[]>([]);
  const hubRef = useRef<HTMLDivElement>(null);
  const [geo, setGeo] = useState<{ w: number; h: number; from: Pt[]; hub: Pt } | null>(null);
  useLayoutEffect(() => {
    const el = box.current;
    if (!el) return;
    const measure = () => {
      const b = el.getBoundingClientRect();
      const hub = hubRef.current?.getBoundingClientRect();
      if (!hub) return;
      // Every pipe leaves from the bottom of the row, so a name that wraps
      // to two lines does not drop its pipe below the others.
      const rects = tiles.current.map((tile) => tile!.getBoundingClientRect());
      const bottom = Math.max(...rects.map((r) => r.bottom)) - b.top;
      setGeo({
        w: b.width,
        h: b.height,
        from: rects.map((r) => ({ x: r.left - b.left + r.width / 2, y: bottom })),
        hub: { x: hub.left - b.left + hub.width / 2, y: hub.top - b.top + hub.height / 2 },
      });
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const [ticked, setTicked] = useState<Set<string>>(new Set());
  const arrived = list.filter((p) => t >= p.at + TRAVEL);
  const flying = list.filter((p) => t >= p.at && t < p.at + TRAVEL);
  const lastArrival = arrived.length ? arrived[arrived.length - 1].at + TRAVEL : -9;
  const pulse = 1 - seg(t, lastArrival, lastArrival + 0.5);
  const fade = 1 - seg(t, LOOP - 0.7, LOOP);

  return (
    <div ref={ref}>
      <div className="lp-panel lp-pipe-panel">
        <div ref={box} className="lp-pipe">
          {geo && (
            <svg className="lp-pipe-svg" width={geo.w} height={geo.h} aria-hidden="true">
              {SOURCES.map((s, i) => {
                const p = pipe(geo.from[i], geo.hub);
                return <path key={s.key} d={d(p)} className={`lp-pipe-line ${s.way}`} />;
              })}
              {list.map((pk, i) => {
                const k = seg(t, pk.at, pk.at + TRAVEL);
                const glow = t < pk.at ? 0 : 1 - seg(t, pk.at + TRAVEL, pk.at + TRAVEL + 0.7);
                if (glow <= 0) return null;
                const p = pipe(geo.from[pk.from], geo.hub);
                const lit = head(p, ease(k));
                const tint = SOURCES[pk.from].tint;
                return (
                  <g key={i} opacity={glow}>
                    <path d={d(lit)} fill="none" stroke={tint} strokeWidth={2.6} strokeLinecap="round" />
                    {k < 1 && <circle cx={lit[3].x} cy={lit[3].y} r={5.5} fill={tint} className="lp-pipe-packet" />}
                  </g>
                );
              })}
            </svg>
          )}

          <div className="lp-pipe-sources">
            {SOURCES.map((s, i) => {
              const emitting = list.some((p) => p.from === i && t >= p.at - 0.15 && t < p.at + 0.45);
              return (
                <div
                  key={s.key}
                  ref={(el) => void (tiles.current[i] = el)}
                  className={`lp-pipe-src ${s.way} ${emitting ? 'emit' : ''}`}
                  style={{ '--tint': s.tint } as CSSProperties}
                >
                  <div className="lp-pipe-logo">{s.mark}</div>
                  <b>{s.name}</b>
                </div>
              );
            })}
          </div>

          <div className="lp-pipe-hubrow">
            <div
              ref={hubRef}
              className="lp-pipe-hub"
              // A ring of the brand's tint as a task lands — an outline, not a lift.
              style={{ transform: `scale(${1 + 0.1 * pulse})`, boxShadow: `0 0 0 ${10 * pulse}px var(--brand-tint)` }}
            >
              <Mascot size={46} state={flying.length ? 'thinking' : arrived.length ? 'done' : 'idle'} compact />
            </div>
            <div className="lp-pipe-hublabel">Spica sorts it into projects</div>
          </div>

          <div className="lp-pipe-list" style={{ opacity: fade }}>
            <div className="lp-pipe-list-h">
              <span>Your list · today</span>
              <span>
                {arrived.length} {arrived.length === 1 ? 'task' : 'tasks'}
              </span>
            </div>
            {arrived.length === 0 && <div className="lp-pipe-empty">Waiting for the morning run…</div>}
            {arrived.map((pk) => {
              const task = ticked.has(pk.task.id) ? { ...pk.task, done: true, doneOn: TODAY_ISO } : pk.task;
              return (
                <div key={pk.task.id} className="lp-pipe-row lp-demo-step">
                  <span className="lp-pipe-row-mark" title={SOURCES[pk.from].name}>
                    {SOURCES[pk.from].mark}
                  </span>
                  <TaskList
                    tasks={[task]}
                    tabIndex={0}
                    onToggle={(id) =>
                      setTicked((s) => {
                        const next = new Set(s);
                        if (next.has(id)) next.delete(id);
                        else next.add(id);
                        return next;
                      })
                    }
                  />
                </div>
              );
            })}
          </div>
        </div>

      </div>
    </div>
  );
}
