import { useEffect, useRef, useState, type CSSProperties, type ReactNode, type RefObject } from 'react';
import Dot from '../components/messages/Dot';
import { color, cssVars as tokenVars } from '../theme';

/**
 * The pieces the landing page and the film draw the app with.
 *
 * They are the app's own styles — your words in a pill of the brand's tint,
 * the agent's in the serif with no bubble and no face, a write as a small
 * white card with a hairline, the amber dot before a value it worked out. The
 * page shows the product the way the product looks, so it cannot drift from
 * it the week a card changes.
 */

/**
 * Every token in `theme.ts` as a CSS variable — `--ink`, `--brand-tint`,
 * `--f-display` — the same names the app's `global.css` reads. Set on `.lp`,
 * so the page and `/film` carry them whatever the boot did; the stylesheet
 * names no colour of its own.
 */
export const cssVars = tokenVars() as CSSProperties;

/** ₹85,000 — the Indian grouping the app uses everywhere. */
export const rupees = (n: number) => `₹${Math.round(n).toLocaleString('en-IN')}`;

export const clamp = (x: number, lo = 0, hi = 1) => Math.min(hi, Math.max(lo, x));
/** Where `p` sits between `a` and `b`, as 0..1. */
export const seg = (p: number, a: number, b: number) => clamp((p - a) / (b - a));
/** Out-cubic: fast in, soft landing — the motion every entrance uses. */
export const ease = (x: number) => 1 - Math.pow(1 - clamp(x), 3);

/**
 * True once the element has been on screen. With `once` off it follows the
 * element in and out — the film uses that to pause when scrolled away.
 */
export function useInView<T extends Element>(
  threshold = 0.25,
  once = true,
): [RefObject<T | null>, boolean] {
  const ref = useRef<T>(null);
  const [seen, setSeen] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      ([e]) => {
        if (e.isIntersecting) {
          setSeen(true);
          if (once) io.disconnect();
        } else if (!once) {
          setSeen(false);
        }
      },
      { threshold },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [threshold, once]);
  return [ref, seen];
}

/** Rises into place the first time it is seen. `delay` staggers siblings. */
export function Reveal({
  children,
  delay = 0,
  className = '',
  as: Tag = 'div',
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
  as?: 'div' | 'section' | 'li' | 'p' | 'h2' | 'h3';
}) {
  const [ref, seen] = useInView<HTMLElement>(0.18);
  return (
    <Tag
      ref={ref as RefObject<never>}
      className={`rv ${seen ? 'in' : ''} ${className}`}
      style={{ transitionDelay: `${delay}s` }}
    >
      {children}
    </Tag>
  );
}

/** A phone, drawn — the app is a phone app and the page should say so. */
export function Phone({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <div className={`lp-phone ${className}`}>
      <div className="lp-phone-notch" aria-hidden="true" />
      <div className="lp-phone-screen">{children}</div>
    </div>
  );
}

/** What the person said — the brand's tint, ink on it, the tail bottom right. */
export function Said({ children, style }: { children: ReactNode; style?: CSSProperties }) {
  return (
    <div className="lp-said" style={style}>
      {children}
    </div>
  );
}

/** What the agent said: the serif, across the thread — no bubble, no face. */
export function AgentSays({ children, style }: { children: ReactNode; style?: CSSProperties }) {
  return (
    <div className="lp-agent-says" style={style}>
      {children}
    </div>
  );
}

export interface Row {
  label: string;
  value: string;
  /** Worked out rather than told — the amber dot. */
  guessed?: boolean;
}

/**
 * A write that happened: the confirm card, with its guessed values marked,
 * then the agent's line about it — outside the card, in its own voice.
 */
export function LogCard({
  heading,
  rows,
  note,
  style,
}: {
  heading: string;
  rows: Row[];
  note?: string;
  style?: CSSProperties;
}) {
  return (
    <div className="lp-turn" style={style}>
      <div className="lp-log">
        <div className="lp-log-h">{heading}</div>
        {rows.map((r) => (
          <div key={r.label} className="lp-log-row">
            <span className="lp-log-k">{r.label}</span>
            <span className="lp-log-v">
              {r.guessed && <Dot />}
              {r.value}
            </span>
          </div>
        ))}
      </div>
      {note && <AgentSays>{note}</AgentSays>}
    </div>
  );
}

/**
 * The day's limit as a ring, in Paisa's colour: the arc is what is left. `frac` is 0..1; `ease`
 * off means a caller animates it frame by frame (the film), on means the
 * stylesheet eases each change (the page's demos).
 */
export function Ring({
  frac,
  size,
  stroke = 9,
  tint = color.paisa,
  eased = true,
  children,
}: {
  frac: number;
  size: number;
  stroke?: number;
  tint?: string;
  eased?: boolean;
  children?: ReactNode;
}) {
  const r = 50;
  const c = 2 * Math.PI * r;
  return (
    <div className="lp-ring" style={{ width: size, height: size }}>
      <svg viewBox="0 0 120 120" width={size} height={size} aria-hidden="true">
        <circle cx="60" cy="60" r={r} fill="none" stroke={color.ringIdle} strokeWidth={stroke} />
        <circle
          cx="60"
          cy="60"
          r={r}
          fill="none"
          stroke={tint}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - clamp(frac))}
          transform="rotate(-90 60 60)"
          style={{ transition: eased ? 'stroke-dashoffset 1.1s cubic-bezier(.2,.7,.2,1)' : 'none' }}
        />
      </svg>
      <div className="lp-ring-in">{children}</div>
    </div>
  );
}

/** Voice, drawn: bars whose height follows `level` 0..1, or a CSS loop. */
export function Wave({ bars = 7, level, height = 26 }: { bars?: number; level?: number; height?: number }) {
  return (
    <div className="lp-wave" style={{ height }} aria-hidden="true">
      {Array.from({ length: bars }, (_, i) => {
        const h =
          level == null
            ? undefined
            : Math.max(0.18, Math.abs(Math.sin(level * 9 + i * 1.3)) * (0.35 + 0.65 * Math.sin(i * 0.7 + 1)));
        return (
          <i
            key={i}
            style={
              level == null
                ? { animationDelay: `${(i % 4) * 0.13}s` }
                : { height: `${Math.round(h! * 100)}%`, animation: 'none' }
            }
          />
        );
      })}
    </div>
  );
}
