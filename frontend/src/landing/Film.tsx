import { CheckCircleIcon, PauseIcon, PlayIcon, SpeakerHighIcon, SpeakerSlashIcon } from '@phosphor-icons/react';
import { useCallback, useEffect, useLayoutEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react';
import Mascot from '../components/Mascot';
import Dot from '../components/messages/Dot';
import { brand, color, font } from '../theme';
import { ChatGPTMark, ClaudeMark, GeminiMark } from './marks';
import { clamp, ease, rupees, seg, useInView } from './parts';
import { FilmSound, type Sfx } from './sound';

/**
 * The film — seventy seconds, no voiceover.
 *
 * Drawn in code, not recorded: crisp at any size, nothing to download, and it
 * cannot drift from the product the way a screen recording does. One clock
 * drives nine scenes; each scene is a pure function of how far into it the
 * clock is, so the film can be paused, scrubbed and replayed and is the same
 * every time. Sizes come from the stage (`u` is 1% of its shorter side), so
 * the same film is right at 16:9 on a laptop, 4:5 on a phone and full-bleed
 * at /film for recording.
 *
 * Every amount is an illustration — round, ordinary, nobody's real ledger.
 *
 * Drawn in the app's own terms: the serif is the voice (the headlines, and
 * the agent's words, which have no bubble and no face); your words are a pill
 * in the brand's tint; a write is a white card with a hairline; nothing that
 * sits in a scene casts a shadow; mode colours are on data only.
 */

interface SceneProps {
  /** Seconds into this scene. */
  t: number;
  /** 1% of the stage's shorter side, in px. */
  u: number;
  /** Landscape enough to put words and pictures side by side. */
  wide: boolean;
}

/** A sound on a beat: seconds into the scene, and which one. */
type Cue = [number, Sfx];

interface Scene {
  key: string;
  label: string;
  /** Seconds of scene time; the film runs at SPEED, so it plays shorter. */
  dur: number;
  cues: Cue[];
  draw: (s: SceneProps) => ReactNode;
}

/* ─── small drawing helpers, all sized in u ─────────────────────────────── */

/** Fades and rises in from time `at`, over `len` seconds. */
function inAt(t: number, at: number, len = 0.55, rise = 1): CSSProperties {
  const k = ease(seg(t, at, at + len));
  return { opacity: k, transform: `translateY(${(1 - k) * rise * 2.4}em)` };
}

function Eyebrow({ u, children, style }: { u: number; children: ReactNode; style?: CSSProperties }) {
  return (
    <div
      style={{
        fontSize: Math.max(1.9 * u, 11),
        fontWeight: 500,
        color: color.faint,
        ...style,
      }}
    >
      {children}
    </div>
  );
}

function Headline({ u, size = 6, children, style }: { u: number; size?: number; children: ReactNode; style?: CSSProperties }) {
  return (
    <div
      style={{
        fontFamily: font.display,
        fontWeight: 400,
        fontSize: size * u,
        lineHeight: 1.05,
        letterSpacing: '-0.02em',
        color: color.ink,
        ...style,
      }}
    >
      {children}
    </div>
  );
}

/**
 * The phone, drawn at a height the stage can hold. On a tall stage — a phone
 * watching the film — a drawn phone would shrink its text past reading, so
 * the bezel goes and the screen itself fills the width. `u` here is the
 * screen's own unit, which the scene makes larger in that case.
 */
function FilmPhone({
  u,
  h,
  wide,
  children,
  style,
}: {
  u: number;
  h: number;
  wide: boolean;
  children: ReactNode;
  style?: CSSProperties;
}) {
  const screen: CSSProperties = {
    height: '100%',
    background: color.paper,
    overflow: 'hidden',
    display: 'flex',
    flexDirection: 'column',
    gap: 1.1 * u,
    fontSize: 1.55 * u,
    position: 'relative',
  };
  if (!wide) {
    return (
      <div
        style={{
          ...screen,
          width: '100%',
          height: h,
          borderRadius: 2.6 * u,
          padding: 1.6 * u,
          background: color.paper,
          border: `1px solid ${color.line}`,
          flex: '0 0 auto',
          ...style,
        }}
      >
        {children}
      </div>
    );
  }
  return (
    <div
      style={{
        width: h * 0.49,
        height: h,
        borderRadius: 5.2 * u,
        background: color.ink,
        padding: 1.1 * u,
        flex: '0 0 auto',
        ...style,
      }}
    >
      <div style={{ ...screen, borderRadius: 4.1 * u, padding: `${5.2 * u}px ${1.6 * u}px ${1.6 * u}px` }}>{children}</div>
    </div>
  );
}

/** Your words: a pill in the brand's tint, ink on it, the tail bottom right (18/18/4/18). */
function Bubble({ u, children, style }: { u: number; children: ReactNode; style?: CSSProperties }) {
  return (
    <div
      style={{
        alignSelf: 'flex-end',
        maxWidth: '84%',
        background: color.brandTint,
        color: color.ink,
        borderRadius: `${2 * u}px ${2 * u}px ${0.45 * u}px ${2 * u}px`,
        padding: `${0.9 * u}px ${1.8 * u}px`,
        fontSize: 1.55 * u,
        lineHeight: 1.4,
        ...style,
      }}
    >
      {children}
    </div>
  );
}

/** A write that happened: a small white card with a hairline, no lift. */
function LogBox({ u, children, style }: { u: number; children: ReactNode; style?: CSSProperties }) {
  return (
    <div
      style={{
        background: color.white,
        border: `1px solid ${color.line}`,
        borderRadius: 1.6 * u,
        padding: `${1.1 * u}px ${1.6 * u}px`,
        fontSize: 1.5 * u,
        lineHeight: 1.45,
        color: color.ink,
        ...style,
      }}
    >
      {children}
    </div>
  );
}

/** The agent's words: the serif, no bubble, no face. */
function AgentLine({ u, children, style }: { u: number; children: ReactNode; style?: CSSProperties }) {
  return (
    <div style={{ fontFamily: font.display, fontSize: 1.7 * u, lineHeight: 1.4, color: color.ink, ...style }}>
      {children}
    </div>
  );
}

function Rows({ u, heading, rows }: { u: number; heading: string; rows: [string, string, boolean?][] }) {
  return (
    <>
      <div style={{ fontSize: 1.3 * u, fontWeight: 500, color: color.faint, marginBottom: 0.4 * u }}>{heading}</div>
      {rows.map(([k, v, guessed]) => (
        <div key={k} style={{ display: 'flex', justifyContent: 'space-between', gap: 1.6 * u, padding: `${0.3 * u}px 0` }}>
          <span style={{ fontSize: 1.35 * u, color: color.faint }}>{k}</span>
          <span style={{ fontWeight: 500 }}>
            {guessed && <Dot />}
            {v}
          </span>
        </div>
      ))}
    </>
  );
}

function RingNum({ u, size, frac, big, small }: { u: number; size: number; frac: number; big: string; small: string }) {
  const r = 50;
  const c = 2 * Math.PI * r;
  return (
    <div style={{ position: 'relative', width: size, height: size, flex: '0 0 auto' }}>
      <svg viewBox="0 0 120 120" width={size} height={size}>
        <circle cx="60" cy="60" r={r} fill="none" stroke={color.ringIdle} strokeWidth="9" />
        <circle
          cx="60"
          cy="60"
          r={r}
          fill="none"
          stroke={color.paisa}
          strokeWidth="9"
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - clamp(frac))}
          transform="rotate(-90 60 60)"
        />
      </svg>
      <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ fontFamily: font.display, fontWeight: 500, fontSize: size * 0.2, letterSpacing: '-0.01em', color: color.ink }}>
          {big}
        </div>
        <div style={{ fontSize: size * 0.08, color: color.faint, marginTop: 0.2 * u }}>{small}</div>
      </div>
    </div>
  );
}

/** Words and a picture: side by side when wide, stacked when tall. */
function Split({ wide, u, words, picture }: { wide: boolean; u: number; words: ReactNode; picture: ReactNode }) {
  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: wide ? 'row' : 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: wide ? 7 * u : 3 * u,
        padding: wide ? `0 ${8 * u}px` : `${6 * u}px ${5 * u}px`,
      }}
    >
      <div style={{ flex: wide ? '1 1 0' : '0 0 auto', minWidth: 0, maxWidth: wide ? 70 * u : undefined, textAlign: wide ? 'left' : 'center' }}>
        {words}
      </div>
      <div style={{ flex: wide ? '0 0 auto' : '1 1 0', alignSelf: wide ? undefined : 'stretch', display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 0 }}>
        {picture}
      </div>
    </div>
  );
}

/* ─── the nine scenes ───────────────────────────────────────────────────── */

const SPENDS: [string, number][] = [
  ['Rent', 22000], ['Swiggy', 349], ['Rapido', 160], ['EMI', 9800], ['Amazon', 1299],
  ['Chai', 20], ['Zomato', 412], ['Blinkit', 278], ['Movie night', 640], ['Myntra', 1899],
  ['Uber', 231], ['Recharge', 299], ['Petrol', 1500], ['Chai', 20], ['Swiggy', 486],
];

const salary: Scene = {
  key: 'salary',
  label: 'Salary day',
  dur: 5,
  cues: [[0.6, 'rise'], [2.6, 'chime']],
  draw: ({ t, u }) => {
    const n = 85000 * ease(seg(t, 0.7, 2.6));
    const face = ease(seg(t, 2.6, 3.2));
    return (
      <div style={{ textAlign: 'center' }}>
        <div style={{ ...inAt(t, 2.6, 0.5), display: 'flex', justifyContent: 'center', marginBottom: 2.5 * u }}>
          <div style={{ transform: `scale(${0.6 + 0.4 * face})` }}>
            <Mascot size={15 * u} state="done" />
          </div>
        </div>
        <Eyebrow u={u} style={inAt(t, 0.2)}>The 1st of the month</Eyebrow>
        <Headline u={u} size={15} style={{ ...inAt(t, 0.5), color: color.paisaInk, marginTop: 1.4 * u, fontVariantNumeric: 'tabular-nums' }}>
          +{rupees(n)}
        </Headline>
        <div style={{ ...inAt(t, 1.8), fontSize: Math.max(2.8 * u, 12), color: color.muted, marginTop: 2 * u }}>
          Salary’s in. It feels like a lot.
        </div>
      </div>
    );
  },
};

const drain: Scene = {
  key: 'drain',
  label: 'Then it leaves',
  dur: 7.8,
  cues: SPENDS.map((_, i) => [0.6 + i * 0.44, 'drop'] as Cue),
  draw: ({ t, u, wide }) => {
    const left = 85000 - (85000 - 6240) * ease(seg(t, 0.9, 7.2) ** 0.9);
    const stream = (
      <div style={{ position: 'relative', width: wide ? 40 * u : 60 * u, height: wide ? 66 * u : 42 * u }}>
        {SPENDS.map(([name, amt], i) => {
          const start = 0.6 + i * 0.44;
          const k = seg(t, start, start + 3.2);
          if (k <= 0 || k >= 1) return null;
          const y = (1 - k) * 100;
          const fade = Math.min(1, k * 5, (1 - k) * 4);
          return (
            <div
              key={i}
              style={{
                position: 'absolute',
                left: `${(i % 3) * 8}%`,
                right: `${(2 - (i % 3)) * 8}%`,
                top: `${y - 10}%`,
                opacity: fade,
                display: 'flex',
                justifyContent: 'space-between',
                padding: `${1.1 * u}px ${1.6 * u}px`,
                borderRadius: 1.6 * u,
                background: color.white,
                border: `1px solid ${color.line}`,
                fontSize: Math.max(1.9 * u, 11),
              }}
            >
              <span style={{ fontWeight: 500 }}>{name}</span>
              <span style={{ color: color.red }}>−{rupees(amt)}</span>
            </div>
          );
        })}
      </div>
    );
    const words = (
      <>
        <Headline u={u} size={wide ? 7 : 6.5} style={inAt(t, 0.2)}>
          Then it leaves.
        </Headline>
        <div style={{ ...inAt(t, 0.8), fontSize: Math.max(2.6 * u, 11.5), color: color.muted, marginTop: 1.6 * u }}>A little at a time.</div>
        <div style={{ ...inAt(t, 1.2), marginTop: 4 * u }}>
          <Eyebrow u={u}>Balance</Eyebrow>
          <div
            style={{
              fontFamily: font.display,
              fontWeight: 400,
              fontSize: 8.5 * u,
              letterSpacing: '-0.02em',
              color: left < 20000 ? color.red : color.ink,
              fontVariantNumeric: 'tabular-nums',
              transition: 'color 0.4s',
            }}
          >
            {rupees(left)}
          </div>
        </div>
      </>
    );
    return <Split wide={wide} u={u} words={words} picture={stream} />;
  },
};

const day18: Scene = {
  key: 'day18',
  label: 'Day 18',
  dur: 5.5,
  cues: [[0.5, 'thud'], [2.3, 'tick'], [2.58, 'tick'], [2.86, 'tick'], [3.14, 'tick']],
  draw: ({ t, u }) => {
    const words = ['Where', 'did', 'it', 'go?'];
    return (
      <div style={{ textAlign: 'center', position: 'relative' }}>
        {['Food?', 'Travel?', 'Shopping?', 'Bills?', 'Chai?'].map((w, i) => {
          const k = seg(t, 2.2 + i * 0.25, 6.5);
          return (
            <span
              key={w}
              style={{
                position: 'absolute',
                left: `${[-40, 95, -25, 105, 30][i]}%`,
                top: `${[-35, -20, 95, 70, 120][i]}%`,
                fontFamily: font.display,
                fontStyle: 'italic',
                fontWeight: 400,
                fontSize: 3.2 * u,
                color: color.grey,
                opacity: Math.min(0.55, k * 3) * (1 - seg(t, 4.8, 5.5)),
                transform: `translateY(${-k * 4 * u}px)`,
                whiteSpace: 'nowrap',
              }}
            >
              {w}
            </span>
          );
        })}
        <Eyebrow u={u} style={inAt(t, 0.2)}>Day 18 · 12 days to go</Eyebrow>
        <Headline u={u} size={16} style={{ ...inAt(t, 0.5), color: color.red, marginTop: 1.4 * u }}>
          {rupees(6240)}
        </Headline>
        <div style={{ ...inAt(t, 1.1), fontSize: Math.max(2.8 * u, 11.5), color: color.muted, marginTop: 1 * u }}>left.</div>
        <div style={{ marginTop: 4 * u, display: 'flex', gap: 1.6 * u, justifyContent: 'center' }}>
          {words.map((w, i) => (
            <Headline key={w} u={u} size={6.5} style={inAt(t, 2.3 + i * 0.28, 0.4)}>
              {w}
            </Headline>
          ))}
        </div>
      </div>
    );
  },
};

const today: Scene = {
  key: 'today',
  label: 'One number',
  dur: 6,
  cues: [[0.3, 'whoosh'], [1.2, 'rise'], [3, 'pop'], [3.3, 'pop'], [3.6, 'pop']],
  draw: ({ t, u, wide }) => {
    const frac = 0.62 * ease(seg(t, 1.2, 2.8));
    const phoneH = wide ? 68 * u : 74 * u;
    // The screen's own unit: a size larger when the bezel is gone.
    const pu = wide ? u : u * 1.75;
    const words = (
      <>
        <Eyebrow u={u} style={inAt(t, 0.2)}>With Spica</Eyebrow>
        <Headline u={u} size={wide ? 6.4 : 5.6} style={{ ...inAt(t, 0.4), marginTop: 1.4 * u }}>
          Your month, as one number for today.
        </Headline>
        <div style={{ ...inAt(t, 3.2), fontSize: Math.max(2.3 * u, 11.5), color: color.muted, marginTop: 2 * u, lineHeight: 1.45 }}>
          It moves as you spend. You see it <b style={{ color: color.ink }}>before</b> you spend.
        </div>
      </>
    );
    const phone = (
      <FilmPhone u={pu} h={phoneH} wide={wide} style={inAt(t, 0.3, 0.9, 3)}>
        {/* The deck card: the surface panel — no shadow, no border. */}
        <div style={{ background: color.surface, borderRadius: 2 * pu, padding: 1.8 * pu, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1 * pu }}>
          <Eyebrow u={pu} style={{ fontSize: 1.3 * pu }}>Today</Eyebrow>
          <RingNum u={pu} size={phoneH * 0.3} frac={frac} big={rupees(1120)} small="left today" />
          <div style={{ fontSize: 1.3 * pu, color: color.faint }}>month · {rupees(14800)} left</div>
        </div>
        {/* One series, spend by category — one colour; the labels say which. */}
        {([['Food', 0.72], ['Travel', 0.38], ['Shopping', 0.55]] as [string, number][]).map(([name, f], i) => (
          <div key={name} style={{ ...inAt(t, 3 + i * 0.3), display: 'grid', gridTemplateColumns: '28% 1fr', alignItems: 'center', gap: 1 * pu }}>
            <span style={{ fontSize: 1.35 * pu }}>{name}</span>
            <span style={{ height: 1 * pu, borderRadius: pu, background: color.lineSoft, overflow: 'hidden' }}>
              <i style={{ display: 'block', height: '100%', width: `${f * 100 * ease(seg(t, 3.2 + i * 0.3, 4.4 + i * 0.3))}%`, background: color.paisa, borderRadius: pu }} />
            </span>
          </div>
        ))}
      </FilmPhone>
    );
    return <Split wide={wide} u={u} words={words} picture={phone} />;
  },
};

const sayIt: Scene = {
  key: 'say',
  label: 'Say it',
  dur: 7.2,
  cues: [[0.3, 'tap'], [2.3, 'pop'], [3.3, 'pop'], [4.4, 'done']],
  draw: ({ t, u, wide }) => {
    const spent = ease(seg(t, 4.4, 5.4));
    const leftToday = 1120 - 160 * spent;
    const phoneH = wide ? 68 * u : 74 * u;
    // The screen's own unit: a size larger when the bezel is gone.
    const pu = wide ? u : u * 1.75;
    const words = (
      <>
        <Headline u={u} size={wide ? 7 : 6} style={inAt(t, 0.2)}>
          Say it.
        </Headline>
        <Headline u={u} size={wide ? 7 : 6} style={{ ...inAt(t, 0.7), fontStyle: 'italic' }}>
          That’s the log.
        </Headline>
        <div style={{ ...inAt(t, 4.6), fontSize: Math.max(2.3 * u, 11.5), color: color.muted, marginTop: 2.2 * u, lineHeight: 1.45 }}>
          No form. No category picker. It works that out — and marks what it guessed.
        </div>
      </>
    );
    const phone = (
      <FilmPhone u={pu} h={phoneH} wide={wide} style={inAt(t, 0, 0.6, 2)}>
        <div style={{ background: color.surface, borderRadius: 2 * pu, padding: 1.4 * pu, display: 'flex', alignItems: 'center', gap: 1.4 * pu }}>
          <RingNum u={pu} size={phoneH * 0.17} frac={0.62 - 0.09 * spent} big="" small="" />
          <div>
            <Eyebrow u={pu} style={{ fontSize: 1.3 * pu }}>Today’s limit</Eyebrow>
            <div style={{ fontFamily: font.display, fontWeight: 500, fontSize: 3.4 * pu, letterSpacing: '-0.01em', fontVariantNumeric: 'tabular-nums' }}>
              {rupees(leftToday)}
            </div>
          </div>
        </div>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', gap: 1 * pu }}>
          {t > 2.3 && <Bubble u={pu} style={{ ...inAt(t, 2.3, 0.4), marginBottom: 0.8 * pu }}>Rapido home, one sixty</Bubble>}
          {t > 3.3 && (
            <LogBox u={pu} style={inAt(t, 3.3, 0.45)}>
              <Rows u={pu} heading="Logged · Paisa" rows={[['Amount', rupees(160)], ['Category', 'Transport', true]]} />
            </LogBox>
          )}
          {t > 5.5 && <AgentLine u={pu} style={inAt(t, 5.5, 0.4)}>{rupees(960)} left for today.</AgentLine>}
        </div>
        <div style={{ height: 5 * pu, borderRadius: 3 * pu, background: color.white, border: `1px solid ${color.border}`, display: 'flex', alignItems: 'center', padding: `0 ${0.6 * pu}px 0 ${1.8 * pu}px`, color: color.faint, fontSize: 1.4 * pu }}>
          {t < 2.3 ? 'Listening…' : 'Type… or speak'}
          <div style={{ marginLeft: 'auto', width: 3.8 * pu, height: 3.8 * pu, borderRadius: '50%', background: color.brand, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 0.3 * pu }}>
            {[0, 1, 2, 3].map((i) => (
              <i key={i} style={{ width: 0.3 * pu, borderRadius: u, background: color.white, height: t < 2.3 ? `${0.6 * pu + Math.abs(Math.sin(t * 9 + i * 1.4)) * 1.5 * pu}px` : 0.6 * pu }} />
            ))}
          </div>
        </div>
      </FilmPhone>
    );
    return <Split wide={wide} u={u} words={words} picture={phone} />;
  },
};

const food: Scene = {
  key: 'food',
  label: 'Food, no forms',
  dur: 8.3,
  cues: [[0.6, 'pop'], [1.6, 'pop'], [4.6, 'whoosh'], [6.2, 'tap'], [6.8, 'pop']],
  draw: ({ t, u, wide }) => {
    const later = t > 4.6;
    const phoneH = wide ? 68 * u : 74 * u;
    // The screen's own unit: a size larger when the bezel is gone.
    const pu = wide ? u : u * 1.75;
    const tapped = t > 6.2;
    const words = later ? (
      <div key="later">
        <Eyebrow u={u} style={inAt(t, 4.6)}>A week in</Eyebrow>
        <Headline u={u} size={wide ? 6.4 : 5.6} style={{ ...inAt(t, 4.8), marginTop: 1.4 * u }}>
          Your usual is already there.
        </Headline>
        <div style={{ ...inAt(t, 5.4), fontSize: Math.max(2.3 * u, 11.5), color: color.muted, marginTop: 2 * u, lineHeight: 1.45 }}>
          It learns your routine. The log is one tap.
        </div>
      </div>
    ) : (
      <div key="first">
        <Eyebrow u={u} style={inAt(t, 0.2)}>Not a diet app</Eyebrow>
        <Headline u={u} size={wide ? 6.4 : 5.6} style={{ ...inAt(t, 0.4), marginTop: 1.4 * u }}>
          Food, without the form.
        </Headline>
        <div style={{ ...inAt(t, 2), fontSize: Math.max(2.3 * u, 11.5), color: color.muted, marginTop: 2 * u, lineHeight: 1.45 }}>
          One sentence. The dot marks what it worked out — tap to fix.
        </div>
      </div>
    );
    const phone = (
      <FilmPhone u={pu} h={phoneH} wide={wide} style={inAt(t, 0, 0.6, 2)}>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', gap: 1 * pu, opacity: later ? 1 - seg(t, 4.4, 4.8) : 1 }}>
          {t > 0.6 && <Bubble u={pu} style={{ ...inAt(t, 0.6, 0.4), marginBottom: 0.8 * pu }}>2 roti, dal and a salad</Bubble>}
          {t > 1.6 && (
            <LogBox u={pu} style={inAt(t, 1.6, 0.45)}>
              <Rows u={pu} heading="Logged · Diet" rows={[['Protein', '18 g', true], ['Calories', '410 kcal', true]]} />
            </LogBox>
          )}
        </div>
        {later && (
          <div style={{ position: 'absolute', left: 1.6 * pu, right: 1.6 * pu, bottom: 8 * pu, top: (wide ? 5.2 : 1.6) * pu, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', gap: 1 * pu }}>
            {tapped && (
              <LogBox u={pu} style={inAt(t, 6.8, 0.45)}>
                <Rows u={pu} heading="Logged · Diet" rows={[['Meal', 'Sattu + kela'], ['Protein', '21 g']]} />
              </LogBox>
            )}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 0.7 * pu, ...inAt(t, 5, 0.5) }}>
              {[['Poha', '12g'], ['Sattu + kela', '21g'], ['Office thali', '24g']].map(([n, g], i) => {
                const on = tapped && i === 1;
                return (
                  <span
                    key={n}
                    style={{
                      display: 'inline-flex',
                      gap: 0.7 * pu,
                      alignItems: 'center',
                      height: 3.4 * pu,
                      padding: `0 ${1.3 * pu}px`,
                      borderRadius: 3 * pu,
                      fontSize: 1.35 * pu,
                      fontWeight: 500,
                      // Chips are yours: white and a border; the one tapped is the selection.
                      background: on ? color.brand : color.chip,
                      color: on ? color.white : color.ink,
                      border: `1px solid ${on ? color.brand : color.chipBorder}`,
                      transform: on ? `scale(${1 + 0.06 * (1 - seg(t, 6.2, 6.6))})` : 'none',
                    }}
                  >
                    {n}
                    <small style={{ color: on ? color.white : color.faint }}>{g}</small>
                  </span>
                );
              })}
            </div>
          </div>
        )}
        <div style={{ height: 5 * pu, borderRadius: 3 * pu, background: color.white, border: `1px solid ${color.border}`, marginTop: 'auto', display: 'flex', alignItems: 'center', padding: `0 ${1.8 * pu}px`, color: color.faint, fontSize: 1.4 * pu }}>
          Type… or speak
        </div>
      </FilmPhone>
    );
    return <Split wide={wide} u={u} words={words} picture={phone} />;
  },
};

// Linear and meetings arrive through Claude; the rest is what you said.
// Projects take the work hue's family, stepping in lightness: base, then ink.
const SOURCES: { from: string; text: string; tint: string; project: string }[] = [
  { from: 'Linear · ENG-142', text: 'Fix the checkout bug', tint: color.work, project: 'Work' },
  { from: 'Standup · meeting', text: 'Send the pricing sheet', tint: color.work, project: 'Work' },
  { from: 'You said · a WhatsApp', text: 'Share the deck with Rohan', tint: color.work, project: 'Work' },
  { from: 'You said', text: 'Renew the domain', tint: color.workInk, project: 'Personal' },
];

const work: Scene = {
  key: 'work',
  label: 'Work, one list',
  dur: 7.8,
  cues: [[0.8, 'pop'], [1.15, 'pop'], [1.5, 'pop'], [1.85, 'pop'], [3, 'whoosh'], [6.6, 'done']],
  draw: ({ t, u, wide }) => {
    const g = ease(seg(t, 3, 4.8));
    const boxW = wide ? 56 * u : 90 * u;
    const boxH = wide ? 62 * u : 76 * u;
    // The list's own unit: a size larger on a tall stage, where it has the width.
    const wu = wide ? u : u * 1.55;
    const scattered = [
      [4, 8, -7],
      [48, 2, 6],
      [8, 60, 5],
      [52, 66, -5],
    ];
    const ticked = t > 6.6;
    return (
      <div style={{ display: 'flex', flexDirection: wide ? 'row' : 'column', alignItems: 'center', gap: wide ? 6 * u : 3 * u, padding: wide ? `0 ${7 * u}px` : `${5 * u}px` }}>
        <div style={{ flex: wide ? '1 1 0' : '0 0 auto', textAlign: wide ? 'left' : 'center' }}>
          <Eyebrow u={u} style={inAt(t, 0.2)}>Linear · meetings · whatever you say</Eyebrow>
          <Headline u={u} size={wide ? 6.2 : 5.4} style={{ ...inAt(t, 0.4), marginTop: 1.4 * u }}>
            Your work, from everywhere, in one list.
          </Headline>
          <div style={{ ...inAt(t, 4.6), fontSize: Math.max(2.2 * u, 11.5), color: color.muted, marginTop: 2 * u, lineHeight: 1.45 }}>
            Linear and meetings arrive every morning. The rest, you say.
          </div>
        </div>
        <div style={{ position: 'relative', width: boxW, height: boxH, flex: '0 0 auto' }}>
          <div style={{ position: 'absolute', left: 0, right: 0, top: 0, opacity: g, fontSize: 1.4 * wu, fontWeight: 500, color: color.faint, display: 'flex', justifyContent: 'space-between' }}>
            <span>Today · {SOURCES.length} tasks</span>
            <span>One list</span>
          </div>
          {SOURCES.map((s, i) => {
            const [sx, sy, rot] = scattered[i];
            const lx = 0;
            const ly = 7 + i * 14;
            const x = sx + (lx - sx) * g;
            const y = sy + (ly - sy) * g;
            const r = rot * (1 - g);
            const w = 46 + (100 - 46) * g;
            const done = ticked && i === 1;
            return (
              <div
                key={s.text}
                style={{
                  ...inAt(t, 0.8 + i * 0.35, 0.45),
                  position: 'absolute',
                  left: `${x}%`,
                  top: `${y}%`,
                  width: `${w}%`,
                  transform: `${inAt(t, 0.8 + i * 0.35, 0.45).transform} rotate(${r}deg)`,
                  background: color.white,
                  border: `1px solid ${color.line}`,
                  borderRadius: 1.6 * wu,
                  padding: `${1.1 * wu}px ${1.5 * wu}px`,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 1.2 * wu,
                }}
              >
                <span style={{ width: 2.4 * wu, height: 2.4 * wu, flex: '0 0 auto', opacity: g, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  {done ? (
                    <CheckCircleIcon weight="fill" size={2.4 * wu} color={s.tint} aria-hidden="true" />
                  ) : (
                    <span style={{ width: 2 * wu, height: 2 * wu, borderRadius: '50%', border: `${0.2 * wu}px solid ${s.tint}` }} />
                  )}
                </span>
                <span style={{ minWidth: 0 }}>
                  <span style={{ display: 'block', fontSize: 1.25 * wu, color: color.faint }}>{s.from}</span>
                  <span style={{ display: 'block', fontSize: 1.65 * wu, color: done ? color.faint : color.ink, textDecoration: done ? 'line-through' : 'none' }}>
                    {s.text}
                  </span>
                </span>
                <span style={{ marginLeft: 'auto', fontSize: 1.25 * wu, color: color.faint, opacity: g }}>{s.project}</span>
              </div>
            );
          })}
        </div>
      </div>
    );
  },
};

const ask: Scene = {
  key: 'ask',
  label: 'Ask it',
  dur: 7.2,
  cues: [[0.6, 'pop'], [1.5, 'pop'], [3, 'pop'], [3.9, 'pop'], [5.2, 'pop'], [6.1, 'pop']],
  draw: ({ t, u, wide }) => {
    const qa: [number, string, string][] = [
      [0.6, 'kitna bacha hai?', `${rupees(4960)} left this month — ${rupees(960)} of it is today’s.`],
      [3, 'protein kitna hua?', '62 g to go.'],
      [5.2, 'aaj kya due hai?', 'Two: send the pricing sheet, fix checkout.'],
    ];
    return (
      <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: wide ? 'row' : 'column', alignItems: 'center', justifyContent: 'center', gap: wide ? 7 * u : 3 * u, padding: wide ? `0 ${8 * u}px` : `${6 * u}px ${5 * u}px` }}>
        <div style={{ flex: wide ? '1 1 0' : '0 0 auto', textAlign: wide ? 'left' : 'center' }}>
          <Eyebrow u={u} style={inAt(t, 0.2)}>One conversation</Eyebrow>
          <Headline u={u} size={wide ? 6.4 : 5.6} style={{ ...inAt(t, 0.4), marginTop: 1.4 * u }}>
            Ask it anything about your own numbers.
          </Headline>
        </div>
        <div style={{ width: wide ? 52 * u : 86 * u, display: 'flex', flexDirection: 'column', gap: 1.2 * u }}>
          {qa.map(([at, q, a]) => (
            <div key={q} style={{ display: 'flex', flexDirection: 'column', gap: 1 * u }}>
              {t > at && <Bubble u={u} style={{ ...inAt(t, at, 0.4), fontSize: (wide ? 1.9 : 2.8) * u }}>{q}</Bubble>}
              {t > at + 0.9 && (
                <AgentLine u={u} style={{ ...inAt(t, at + 0.9, 0.45), fontSize: (wide ? 2.1 : 3) * u }}>
                  {a}
                </AgentLine>
              )}
            </div>
          ))}
        </div>
      </div>
    );
  },
};

/**
 * Spica lives in the agent you already use: a sentence said in Claude, in
 * ChatGPT, in Gemini travels into Spica and lands as a row. Claude is built
 * (for work); the other two are not yet, so they carry *soon* and a dashed
 * line — the scene sells where it is going without claiming it is there.
 */
const AGENTS: {
  key: string;
  name: string;
  mark: (size: number) => ReactNode;
  said: string;
  logged: [string, string];
  soon: boolean;
  tint: string;
  /** Where the tile sits, as a fraction of the cluster. */
  x: number;
  y: number;
  /** Which side of the tile its sentence appears on. */
  side: 'left' | 'right';
}[] = [
  { key: 'claude', name: 'Claude', mark: (s) => <ClaudeMark size={s} />, said: 'add “send the deck” to Spica', logged: ['Work', 'Send the deck'], soon: false, tint: brand.claude, x: 0.14, y: 0.16, side: 'right' },
  { key: 'chatgpt', name: 'ChatGPT', mark: (s) => <ChatGPTMark size={s} />, said: 'lunch was 240', logged: ['Paisa', `${rupees(240)} · Food`], soon: true, tint: brand.chatgpt, x: 0.86, y: 0.3, side: 'left' },
  { key: 'gemini', name: 'Gemini', mark: (s) => <GeminiMark size={s} />, said: '2 eggs for breakfast', logged: ['Diet', '12 g protein'], soon: true, tint: brand.gemini, x: 0.2, y: 0.84, side: 'right' },
];

/** A tall stage puts the three in a row across the top instead. */
const AGENTS_TALL: { x: number; y: number }[] = [
  { x: 0.17, y: 0.1 },
  { x: 0.5, y: 0.1 },
  { x: 0.83, y: 0.1 },
];

/** When each agent's sentence leaves for Spica, and how long it travels. */
const SENDS = [2.3, 3.25, 4.2];
const HOP = 0.6;

const everywhere: Scene = {
  key: 'where',
  label: 'Everywhere',
  dur: 7.4,
  cues: [
    [0.9, 'pop'],
    [1.2, 'pop'],
    [1.5, 'pop'],
    [1.8, 'pop'],
    ...SENDS.flatMap((at) => [[at, 'tick'] as Cue, [at + HOP, 'pop'] as Cue]),
  ],
  draw: ({ t, u, wide }) => {
    const W = wide ? 64 * u : 84 * u;
    const H = wide ? 66 * u : 74 * u;
    const hub = wide ? { x: W * 0.55, y: H * 0.5 } : { x: W * 0.5, y: H * 0.62 };
    const at = (i: number) => (wide ? AGENTS[i] : AGENTS_TALL[i]);
    // Tall: one sentence at a time, in a slot under the row — side bubbles
    // would collide there.
    const speaking = SENDS.reduce((cur, s, i) => (t >= s - 0.7 && t < s + HOP + 1 ? i : cur), -1);
    const arrived = SENDS.filter((at) => t >= at + HOP).length;
    const flying = SENDS.some((at) => t >= at && t < at + HOP);
    const lastAt = arrived ? SENDS[arrived - 1] + HOP : -9;
    const pulse = 1 - seg(t, lastAt, lastAt + 0.5);
    const tile = 9 * u;

    const words = (
      <>
        <Eyebrow u={u} style={inAt(t, 0.2)}>
          Wherever you already are
        </Eyebrow>
        <Headline u={u} size={wide ? 6.4 : 5.6} style={{ ...inAt(t, 0.4), marginTop: 1.4 * u }}>
          It lives in your favourite agent.
        </Headline>
        <div style={{ ...inAt(t, 3), fontSize: Math.max(2.3 * u, 11.5), color: color.muted, marginTop: 2 * u, lineHeight: 1.45 }}>
          You don’t leave the app you love to log anything.
        </div>
      </>
    );

    const picture = (
      <div style={{ position: 'relative', width: W, height: H, flex: '0 0 auto' }}>
        <svg width={W} height={H} style={{ position: 'absolute', inset: 0, overflow: 'visible' }} aria-hidden="true">
          {AGENTS.map((a, i) => {
            const k = ease(seg(t, 1.2 + i * 0.3, 1.8 + i * 0.3));
            if (k <= 0) return null;
            const x = at(i).x * W;
            const y = at(i).y * H;
            return (
              <line
                key={a.key}
                x1={x}
                y1={y}
                x2={x + (hub.x - x) * k}
                y2={y + (hub.y - y) * k}
                stroke={color.border}
                strokeWidth={Math.max(1, 0.22 * u)}
                strokeDasharray={a.soon ? `${0.9 * u} ${0.9 * u}` : undefined}
              />
            );
          })}
          {AGENTS.map((a, i) => {
            const p = seg(t, SENDS[i], SENDS[i] + HOP);
            if (p <= 0 || p >= 1) return null;
            const e = ease(p);
            const x = at(i).x * W + (hub.x - at(i).x * W) * e;
            const y = at(i).y * H + (hub.y - at(i).y * H) * e;
            return <circle key={a.key} cx={x} cy={y} r={1.1 * u} fill={a.tint} stroke={color.white} strokeWidth={0.35 * u} />;
          })}
        </svg>

        {AGENTS.map((a, i) => {
          const x = at(i).x * W;
          const y = at(i).y * H;
          const bubble = wide
            ? seg(t, SENDS[i] - 0.7, SENDS[i] - 0.3) * (1 - seg(t, SENDS[i] + HOP + 0.9, SENDS[i] + HOP + 1.3))
            : 0;
          return (
            <div key={a.key}>
              <div
                style={{
                  ...inAt(t, 1.2 + i * 0.3, 0.45),
                  position: 'absolute',
                  left: x - tile / 2,
                  top: y - tile / 2,
                  width: tile,
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: 0.6 * u,
                }}
              >
                <div
                  style={{
                    width: tile,
                    height: tile,
                    borderRadius: 1.6 * u,
                    background: color.white,
                    border: `1px solid ${color.line}`,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  {a.mark(5 * u)}
                </div>
                <div style={{ fontSize: Math.max(1.5 * u, 10), fontWeight: 500, whiteSpace: 'nowrap' }}>{a.name}</div>
                {/* Built in ink on the surface; coming quieter, only outlined. */}
                <div
                  style={{
                    fontSize: Math.max(1.2 * u, 9),
                    fontWeight: 500,
                    padding: `${0.15 * u}px ${0.9 * u}px`,
                    borderRadius: 3 * u,
                    border: `1px solid ${a.soon ? color.border : 'transparent'}`,
                    background: a.soon ? 'transparent' : color.surface,
                    color: a.soon ? color.faint : color.ink,
                  }}
                >
                  {a.soon ? 'Soon' : 'Now'}
                </div>
              </div>
              {bubble > 0 && (
                <div
                  style={{
                    position: 'absolute',
                    top: y - 2.2 * u,
                    ...(a.side === 'right' ? { left: x + tile / 2 + 1.4 * u } : { right: W - x + tile / 2 + 1.4 * u }),
                    opacity: bubble,
                    transform: `translateY(${(1 - bubble) * 1.2 * u}px)`,
                    // Your words, said in another app: your pill, its tail
                    // toward the app it was said in.
                    background: color.brandTint,
                    color: color.ink,
                    borderRadius: a.side === 'right' ? `${2 * u}px ${2 * u}px ${2 * u}px ${0.45 * u}px` : `${2 * u}px ${2 * u}px ${0.45 * u}px ${2 * u}px`,
                    padding: `${0.9 * u}px ${1.6 * u}px`,
                    fontSize: Math.max(1.55 * u, 10.5),
                    whiteSpace: 'nowrap',
                  }}
                >
                  {a.said}
                </div>
              )}
            </div>
          );
        })}

        {!wide && speaking >= 0 && (
          <div
            key={`said-${speaking}`}
            style={{
              ...inAt(t, SENDS[speaking] - 0.7, 0.35),
              position: 'absolute',
              left: 0,
              right: 0,
              top: H * 0.33,
              display: 'flex',
              justifyContent: 'center',
            }}
          >
            <div
              style={{
                background: color.brandTint,
                color: color.ink,
                borderRadius: `${2 * u}px ${2 * u}px ${0.45 * u}px ${2 * u}px`,
                padding: `${0.9 * u}px ${1.6 * u}px`,
                fontSize: Math.max(1.7 * u, 11),
                whiteSpace: 'nowrap',
              }}
            >
              <span style={{ color: color.faint, marginRight: 0.8 * u }}>{AGENTS[speaking].name} ·</span>
              {AGENTS[speaking].said}
            </div>
          </div>
        )}

        <div
          style={{
            ...inAt(t, 0.8, 0.5),
            position: 'absolute',
            left: hub.x - 7.5 * u,
            top: hub.y - 7.5 * u,
            width: 15 * u,
            height: 15 * u,
            borderRadius: '50%',
            background: color.white,
            border: `1px solid ${color.line}`,
            // A ring of the brand's tint as a sentence lands — an outline, not a lift.
            boxShadow: `0 0 0 ${1.6 * u * pulse}px ${color.brandTint}`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            transform: `${inAt(t, 0.8, 0.5).transform} scale(${1 + 0.08 * pulse})`,
          }}
        >
          <Mascot size={10 * u} state={flying ? 'thinking' : arrived ? 'done' : 'idle'} compact />
        </div>

        {arrived > 0 && (
          <div
            key={`logged-${arrived}`}
            style={{
              ...inAt(t, lastAt, 0.35),
              position: 'absolute',
              left: hub.x,
              top: hub.y + 9.5 * u,
              transform: `translateX(-50%) ${inAt(t, lastAt, 0.35).transform}`,
            }}
          >
            <LogBox u={u} style={{ whiteSpace: 'nowrap', padding: `${0.9 * u}px ${1.6 * u}px` }}>
              <span style={{ fontSize: Math.max(1.3 * u, 10), fontWeight: 500, color: color.faint, marginRight: 1.2 * u }}>
                Logged · {AGENTS[arrived - 1].logged[0]}
              </span>
              <span style={{ fontSize: Math.max(1.6 * u, 11), fontWeight: 500 }}>{AGENTS[arrived - 1].logged[1]}</span>
            </LogBox>
          </div>
        )}
      </div>
    );

    return <Split wide={wide} u={u} words={words} picture={picture} />;
  },
};

const close: Scene = {
  key: 'close',
  label: 'Less time',
  dur: 6.5,
  cues: [[0.3, 'thud'], [1.1, 'thud'], [1.9, 'thud'], [3.8, 'whoosh'], [4.6, 'chime']],
  draw: ({ t, u }) => {
    const lockup = seg(t, 3.8, 4.6);
    return (
      <div style={{ textAlign: 'center', position: 'relative' }}>
        <div style={{ opacity: 1 - lockup, transform: `scale(${1 - 0.08 * lockup})` }}>
          <Headline u={u} size={11} style={inAt(t, 0.3, 0.5)}>Less time.</Headline>
          <Headline u={u} size={11} style={inAt(t, 1.1, 0.5)}>Less effort.</Headline>
          <Headline u={u} size={11} style={{ ...inAt(t, 1.9, 0.5), fontStyle: 'italic' }}>More kept.</Headline>
        </div>
        <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', opacity: lockup, transform: `scale(${0.94 + 0.06 * lockup})` }}>
          <Mascot size={16 * u} state={t > 4.6 ? 'idle' : 'still'} />
          {/* The wordmark: lowercase, Anek Latin semibold — THEME.md § Type. */}
          <Headline u={u} size={10} style={{ marginTop: 2 * u, fontFamily: font.sans, fontWeight: 600 }}>spica</Headline>
          <div style={{ fontSize: Math.max(2.6 * u, 11.5), color: color.muted, marginTop: 1.2 * u }}>Money, food, work. One conversation.</div>
        </div>
      </div>
    );
  },
};

export const SCENES: Scene[] = [salary, drain, day18, today, sayIt, food, work, ask, everywhere, close];
const STARTS = SCENES.reduce<number[]>((acc, _s, i) => [...acc, i ? acc[i - 1] + SCENES[i - 1].dur : 0], []);
export const TOTAL = SCENES.reduce((a, s) => a + s.dur, 0);
/**
 * Scene time runs this much faster than the wall clock. The choreography was
 * set at a readable pace; played a third faster it keeps every beat and loses
 * the wait — about 45 seconds end to end.
 */
const SPEED = 1.35;
/** Seconds the film takes to watch. */
export const RUNTIME = TOTAL / SPEED;
const FADE = 0.45;

/* ─── the player ────────────────────────────────────────────────────────── */

/** Every cue on the film's own clock, in order. */
const CUES = SCENES.flatMap((s, i) => s.cues.filter(([at]) => at < s.dur).map(([at, name]) => ({ at: STARTS[i] + at, name })));

/** Which scene scene-time `t` falls in. */
const sceneAt = (t: number) =>
  t >= TOTAL ? SCENES.length - 1 : Math.max(0, STARTS.findIndex((s, i) => t >= s && t < s + SCENES[i].dur));

export default function Film({ bleed = false, loop = false }: { bleed?: boolean; loop?: boolean }) {
  const stage = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 1280, h: 720 });
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);
  /** The viewer's choice — on by default. */
  const [soundOn, setSoundOn] = useState(true);
  /** Wanted, but the browser is still holding it for a tap or click. */
  const [soundLocked, setSoundLocked] = useState(true);
  const [holderRef, inView] = useInView<HTMLDivElement>(0.5, false);
  const userPaused = useRef(false);
  const sound = useRef<FilmSound | null>(null);
  const reduced = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

  useLayoutEffect(() => {
    const el = stage.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setSize({ w: e.contentRect.width, h: e.contentRect.height }));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Plays when half of it is on screen, pauses when it leaves — unless the
  // viewer paused it, which is theirs to undo. Full-bleed plays at once.
  useEffect(() => {
    if (reduced && !bleed) return;
    if (bleed) {
      setPlaying(true);
      return;
    }
    if (inView && !userPaused.current) setPlaying(true);
    if (!inView) setPlaying(false);
  }, [inView, bleed, reduced]);

  // The clock lives in a ref so the frame loop never reads a stale time; the
  // state copy is only what the scenes render from.
  const clock = useRef(0);
  const setClock = useCallback((v: number) => {
    clock.current = v;
    setT(v);
  }, []);

  useEffect(() => {
    if (!playing) {
      sound.current?.hush();
      return;
    }
    let raf = 0;
    let last = performance.now();
    const tick = (now: number) => {
      const dt = Math.min(0.1, (now - last) / 1000) * SPEED;
      last = now;
      const prev = clock.current;
      const next = prev + dt;
      // A cue sounds when the clock crosses it while playing — a seek jumps
      // over the ones in between rather than firing them all at once.
      const sfx = sound.current;
      if (sfx?.on) {
        for (const c of CUES) if (c.at > prev && c.at <= next) sfx.play(c.name);
        sfx.bed(sceneAt(Math.min(next, TOTAL - 0.001)));
      }
      if (next >= TOTAL && !(loop || bleed)) {
        setClock(TOTAL);
        setPlaying(false);
        return;
      }
      setClock(next >= TOTAL ? 0 : next);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, loop, bleed, setClock]);

  // Sound is on by default: asked for now, heard as soon as the browser
  // allows — at once where it already does, else at the page's first tap.
  useEffect(() => {
    const sfx = (sound.current ??= new FilmSound());
    const off = sfx.subscribe(() => {
      setSoundOn(sfx.wanted);
      setSoundLocked(sfx.locked);
    });
    sfx.want();
    return () => {
      off();
      sfx.dispose();
    };
  }, []);

  const toggle = () => {
    if (playing) {
      userPaused.current = true;
      setPlaying(false);
      return;
    }
    userPaused.current = false;
    if (clock.current >= TOTAL) setClock(0);
    setPlaying(true);
  };

  // Called from a click or a key, which is what lets a browser make sound.
  // While the browser is still holding it, the press means "yes, sound" —
  // it unlocks rather than turning off what the viewer never heard.
  const toggleSound = () => {
    const sfx = sound.current;
    if (!sfx) return;
    if (sfx.locked) {
      sfx.unlock();
      if (!playing) toggle();
      return;
    }
    if (sfx.wanted) {
      sfx.unwant();
      return;
    }
    sfx.want();
    sfx.unlock();
    if (!playing) toggle();
  };

  // A tap on the film while sound is held unlocks it; it does not pause.
  const onStage = () => {
    if (sound.current?.locked && playing) {
      sound.current.unlock();
      return;
    }
    toggle();
  };

  const seek = (i: number) => {
    setClock(STARTS[i] + 0.01);
    userPaused.current = false;
    setPlaying(true);
  };

  // At /film, for recording: space plays and pauses, S is sound, R restarts.
  const keys = useRef({ toggle, toggleSound, seek });
  keys.current = { toggle, toggleSound, seek };
  useEffect(() => {
    if (!bleed) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === ' ') keys.current.toggle();
      else if (e.key.toLowerCase() === 's') keys.current.toggleSound();
      else if (e.key.toLowerCase() === 'r') keys.current.seek(0);
      else return;
      e.preventDefault();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [bleed]);

  const wide = size.w / size.h > 1.2;
  // Landscape has width to spare, so everything is drawn a size larger.
  const u = (Math.min(size.w, size.h) / 100) * (wide ? 1.22 : 1);
  const current = sceneAt(t);

  return (
    <div ref={holderRef} style={bleed ? { height: '100%' } : undefined}>
      <div ref={stage} className={`lp-film ${bleed ? 'bleed' : ''}`} onClick={onStage} role="img" aria-label="A short film: where a month's money goes, and how Spica keeps money, food and work in one conversation">
        {SCENES.map((s, i) => {
          const local = t - STARTS[i];
          // The scene on now, and a neighbour only while they cross-fade.
          if (i !== current && !(local > -FADE && local < s.dur + FADE)) return null;
          const fadeIn = i === 0 ? 1 : clamp((local + FADE) / (2 * FADE));
          const fadeOut = i === SCENES.length - 1 ? 1 : clamp((s.dur + FADE - local) / (2 * FADE));
          const o = Math.min(fadeIn, fadeOut);
          if (o <= 0) return null;
          return (
            <div key={s.key} className="lp-scene" style={{ opacity: o }}>
              {s.draw({ t: clamp(local, 0, s.dur), u, wide })}
            </div>
          );
        })}
        {playing && soundOn && soundLocked && !bleed && (
          <button type="button" className="lp-film-unmute" onClick={(e) => (e.stopPropagation(), sound.current?.unlock())}>
            <SpeakerGlyph on={false} />
            Tap for sound
          </button>
        )}
        {!playing && !bleed && (
          <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', background: `color-mix(in srgb, ${color.paper} 35%, transparent)`, cursor: 'pointer' }}>
            <span style={{ width: 11 * u, height: 11 * u, borderRadius: '50%', background: color.ink, color: color.paper, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <PlayIcon weight="fill" size={4.6 * u} style={{ marginLeft: 0.4 * u }} aria-hidden="true" />
            </span>
          </div>
        )}
      </div>
      {!bleed && (
        <div className="lp-film-bar">
          <button type="button" className="lp-film-toggle" onClick={toggle} aria-label={playing ? 'Pause the film' : 'Play the film'}>
            {playing ? <PauseIcon weight="fill" size={18} aria-hidden="true" /> : <PlayIcon weight="fill" size={18} aria-hidden="true" />}
          </button>
          <div className="lp-film-track">
            {SCENES.map((s, i) => (
              <button
                key={s.key}
                type="button"
                className="lp-film-seg"
                style={{ '--w': s.dur } as CSSProperties}
                onClick={() => seek(i)}
                aria-label={`Jump to: ${s.label}`}
                title={s.label}
              >
                <i style={{ transform: `scaleX(${clamp((t - STARTS[i]) / s.dur)})` }} />
              </button>
            ))}
          </div>
          <span className="lp-film-label">{SCENES[current].label}</span>
          <button
            type="button"
            className={`lp-film-sound ${soundOn && !soundLocked ? 'on' : ''}`}
            onClick={toggleSound}
            aria-pressed={soundOn && !soundLocked}
            aria-label={soundOn ? (soundLocked ? 'Turn the sound on — tap to allow it' : 'Turn the sound off') : 'Turn the sound on'}
          >
            <SpeakerGlyph on={soundOn && !soundLocked} />
            <span>{soundOn ? (soundLocked ? 'Tap for sound' : 'Sound on') : 'Sound off'}</span>
          </button>
        </div>
      )}
    </div>
  );
}

function SpeakerGlyph({ on }: { on: boolean }) {
  return on ? <SpeakerHighIcon size={20} aria-hidden="true" /> : <SpeakerSlashIcon size={20} aria-hidden="true" />;
}
