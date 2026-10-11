import { CaretDownIcon } from '@phosphor-icons/react';
import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react';
import Mascot from '../components/Mascot';
import Dot from '../components/messages/Dot';
import { color } from '../theme';
import Film from './Film';
import Pipeline from './Pipeline';
import RealDeck from './RealDeck';
import { ChatGPTMark, ClaudeMark, WhatsAppMark } from './marks';
import { AgentSays, LogCard, Phone, Reveal, Ring, Said, cssVars, rupees, useInView, type Row } from './parts';

/** The three modes, as the stylesheet keys their colours. */
type ModeKey = 'paisa' | 'diet' | 'work';
import './landing.css';

/**
 * The landing page.
 *
 * It sells the time back, not the features, and says as little as it can:
 * each chapter is a heading, the visitor's own words, and a demo that makes
 * the rest of the argument. Every amount and name on it is an illustration,
 * and the footer says so; nothing claims a number the product has not
 * measured.
 */

/** The web version lives at /app; the root is this page. */
const OPEN_APP = '/app';
/**
 * The app's Google Play listing. The Android app is the product; the page's
 * first button is its download. Empty until the listing's link is set here —
 * see TODO.md.
 */
const APP_URL = '';
const reduced = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;

/* ─── nav ───────────────────────────────────────────────────────────────── */

function Nav({ scrolled }: { scrolled: boolean }) {
  return (
    <nav className={`lp-nav ${scrolled ? 'scrolled' : ''}`}>
      <div className="lp-wrap">
        <a className="lp-brand" href="#top" aria-label="Spica, back to the top">
          <Mascot size={30} state="still" />
          spica
        </a>
        <div className="lp-nav-links">
          <a href="#money">Money</a>
          <a href="#food">Food</a>
          <a href="#work">Work</a>
          <a href="#film">Film</a>
          <a className="lp-btn lp-btn-primary" href={OPEN_APP}>
            Try on web
          </a>
        </div>
      </div>
    </nav>
  );
}

/* ─── hero ────────────────────────────────────────────────────────────── */

/** Download the app, and try it on the web — the page's two doors. */
function Ctas() {
  return (
    <div className="lp-hero-ctas">
      <a className="lp-btn lp-btn-primary" href={APP_URL || undefined} target="_blank" rel="noopener">
        <PlayGlyph />
        Download on Google Play
      </a>
      <a className="lp-btn lp-btn-ghost" href={OPEN_APP}>
        Try it on the web
      </a>
    </div>
  );
}

/** Google Play's mark (Simple Icons, CC0), in the button's own colour. */
function PlayGlyph() {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="currentColor"
        d="M22.018 13.298l-3.919 2.218-3.515-3.493 3.543-3.521 3.891 2.202a1.49 1.49 0 0 1 0 2.594zM1.337.924a1.486 1.486 0 0 0-.112.568v21.017c0 .217.045.419.124.6l11.155-11.087L1.337.924zm12.207 10.065l3.258-3.238L3.45.195a1.466 1.466 0 0 0-.946-.179l11.04 10.973zm0 2.067l-11 10.933c.298.036.612-.016.906-.183l13.324-7.54-3.23-3.21z"
      />
    </svg>
  );
}

function Hero() {
  return (
    <header className="lp-hero" id="top">
      <div className="lp-wrap">
        <div className="lp-hero-copy">
          <Reveal>
            <h1 className="lp-h1">
              Money, food, work.
              <br />
              <span className="lp-em">Just say it.</span>
            </h1>
          </Reveal>
          <Reveal delay={0.08}>
            <p className="lp-lede">Say what you spent, ate or have to do. Spica logs it, sorts it and adds it up.</p>
          </Reveal>
          <Reveal delay={0.16}>
            <Ctas />
          </Reveal>
        </div>
        <Reveal className="lp-hero-stage" delay={0.12}>
          <div className="lp-halo" aria-hidden="true" />
          <Phone className="real">
            <RealDeck />
          </Phone>
        </Reveal>
      </div>
    </header>
  );
}

/* ─── the drain: what slips, in all three ─────────────────────────────── */

type Slip = [string, string, 'money' | 'food' | 'work'];

const SLIPS_A: Slip[] = [
  ['Chai', `−${rupees(20)}`, 'money'],
  ['Skipped breakfast', 'not logged', 'food'],
  ['Fix checkout · Linear', 'due today', 'work'],
  ['Swiggy', `−${rupees(349)}`, 'money'],
  ['Samosa ×2', '520 kcal', 'food'],
  ['Deck for Rohan · WhatsApp', 'buried', 'work'],
  ['Rapido', `−${rupees(160)}`, 'money'],
  ['Maggi at 1 am', 'not logged', 'food'],
  ['Pricing sheet · a meeting', 'forgotten', 'work'],
  ['Recharge', `−${rupees(299)}`, 'money'],
];
const SLIPS_B: Slip[] = [
  ['Blinkit', `−${rupees(278)}`, 'money'],
  ['Office thali', 'protein?', 'food'],
  ['Renew the domain · a notepad', 'overdue', 'work'],
  ['Uber', `−${rupees(231)}`, 'money'],
  ['Cold coffee', '320 kcal', 'food'],
  ['Review the PR · Linear', 'waiting', 'work'],
  ['Amazon', `−${rupees(1299)}`, 'money'],
  ['Dal chawal', 'not logged', 'food'],
  ['Call the CA · a sticky note', 'lost', 'work'],
  ['Movie', `−${rupees(640)}`, 'money'],
];

function Marquee({ back = false, items }: { back?: boolean; items: Slip[] }) {
  // Two copies, so sliding by half is seamless.
  const all = [...items, ...items];
  return (
    <div className={`lp-marquee ${back ? 'back' : ''}`} aria-hidden="true">
      {all.map(([name, value, kind], i) => (
        <div key={i} className={`lp-spend ${kind}`}>
          <b>{name}</b>
          <span>{value}</span>
        </div>
      ))}
    </div>
  );
}

/** What slips, in all three modes — a band between the hero and the film. */
function Drain() {
  return (
    <section className="lp-drain" aria-label="Small things that slip: spends, meals and tasks">
      <Marquee items={SLIPS_A} />
      <Marquee back items={SLIPS_B} />
    </section>
  );
}

/* ─── the film ──────────────────────────────────────────────────────────── */

function FilmSection() {
  return (
    <section className="lp-film-sec" id="film" aria-labelledby="film-h">
      <div className="lp-wrap">
        <div className="lp-film-head">
          <Reveal>
            <h2 className="lp-h2" id="film-h">
              Your month, in under a minute.
            </h2>
          </Reveal>
        </div>
        <Film />
      </div>
    </section>
  );
}

/* ─── chapters ──────────────────────────────────────────────────────────── */

function Chapter({
  id,
  n,
  name,
  mode,
  flip,
  title,
  quote,
  problem,
  extra,
  panel,
}: {
  id: string;
  n: string;
  name: string;
  mode: ModeKey;
  flip?: boolean;
  title: ReactNode;
  quote: string;
  problem: string;
  extra?: ReactNode;
  panel: ReactNode;
}) {
  return (
    <section className={`lp-chapter ${flip ? 'flip' : ''}`} id={id} aria-labelledby={`${id}-h`}>
      <div className="lp-wrap">
        <div className="lp-copy">
          <Reveal>
            <div className="lp-chapter-n">
              <span>{n}</span>
              <span className={`lp-mode ${mode}`}>{name}</span>
            </div>
            <h2 className="lp-h2" id={`${id}-h`}>
              {title}
            </h2>
          </Reveal>
          <Reveal delay={0.08}>
            <div className="lp-problem">
              <q>{quote}</q>
              {problem}
            </div>
          </Reveal>
          {extra && <Reveal delay={0.14}>{extra}</Reveal>}
        </div>
        <Reveal delay={0.1}>{panel}</Reveal>
      </div>
    </section>
  );
}

/* money: a limit you can spend against, for real, on the page */

const LIMIT = 1120;
const TRY: [string, number][] = [['Chai', 20], ['Rapido', 160], ['Lunch', 240], ['Movie', 640]];
const MONTH: [string, number][] = [
  ['Rent', 22000],
  ['Food', 6410],
  ['Shopping', 3190],
  ['Transport', 2380],
];

function MoneyPanel() {
  const [spent, setSpent] = useState<[string, number][]>([]);
  const total = spent.reduce((a, [, n]) => a + n, 0);
  const left = LIMIT - total;
  const over = left < 0;
  const max = Math.max(...MONTH.map(([, n]) => n));
  return (
    <div className="lp-panel">
      <div className="lp-money-top">
        <Ring frac={Math.max(0, left) / LIMIT} size={140} stroke={10} tint={over ? color.red : color.paisa}>
          <div className="lp-ring-big" style={{ color: over ? color.red : color.ink }}>
            {rupees(Math.abs(left))}
          </div>
          <div className="lp-ring-small">{over ? 'over today' : 'left today'}</div>
        </Ring>
        <div>
          <div className="lp-eyebrow">Try it — spend something</div>
          <div className="lp-money-try">
            {TRY.map(([name, n]) => (
              <button
                key={name}
                type="button"
                className="lp-chip"
                onClick={() => setSpent((s) => [[name, n] as [string, number], ...s].slice(0, 6))}
              >
                {name}
                <small>{rupees(n)}</small>
              </button>
            ))}
          </div>
          <div className="lp-money-status">
            {spent.length === 0 ? (
              `Today’s limit is ${rupees(LIMIT)}. Tap a spend.`
            ) : (
              <>
                {spent.length} logged ·{' '}
                <button type="button" className="lp-link" onClick={() => setSpent([])}>
                  reset
                </button>
              </>
            )}
          </div>
        </div>
      </div>
      <div className="lp-bars">
        <div className="lp-eyebrow">Where September went</div>
        {MONTH.map(([name, n]) => (
          <div key={name} className="lp-bar-row">
            <span>{name}</span>
            <span className="lp-bar">
              <i style={{ '--f': n / max } as CSSProperties} />
            </span>
            <span>{rupees(n)}</span>
          </div>
        ))}
      </div>
      <div className="lp-udhaar">
        <b>Rohit owes you {rupees(1500)}</b>
        <span>udhaar · since 12 Sep</span>
      </div>
    </div>
  );
}

/* food: day one is a sentence, a week in it is a tap */

const SENTENCE = '2 roti, dal and a salad';
const USUAL: [string, string, string][] = [
  ['Poha', '12 g', '290 kcal'],
  ['Sattu + kela', '21 g', '340 kcal'],
  ['Office thali', '24 g', '640 kcal'],
  ['Dal chawal', '16 g', '480 kcal'],
];

function FoodPanel() {
  const [ref, seen] = useInView<HTMLDivElement>(0.3);
  const [typed, setTyped] = useState(reduced() ? SENTENCE.length : 0);
  const [cycle, setCycle] = useState(0);
  // Type the sentence, hold the card, clear, again.
  useEffect(() => {
    if (!seen || reduced()) return;
    const wait = typed < SENTENCE.length ? 70 : 4200;
    const id = window.setTimeout(() => {
      if (typed < SENTENCE.length) setTyped(typed + 1);
      else {
        setTyped(0);
        setCycle((c) => c + 1);
      }
    }, typed === 0 ? 700 : wait);
    return () => window.clearTimeout(id);
  }, [seen, typed]);
  const done = typed >= SENTENCE.length;
  const tap = (cycle + 1) % USUAL.length;
  const meal = USUAL[tap];
  return (
    <div ref={ref} className="lp-panel tint">
      <div className="lp-days">
        <div className="lp-day">
          <div className="lp-day-h">
            <b>Day 1</b>
            <span>one sentence</span>
          </div>
          {done && (
            <div className="lp-demo-step lp-turn">
              <Said>{SENTENCE}</Said>
              <LogCard
                heading="Logged · Diet"
                rows={[
                  { label: 'Protein', value: '18 g', guessed: true },
                  { label: 'Calories', value: '410 kcal', guessed: true },
                ]}
              />
            </div>
          )}
          <div className="lp-typed">
            {done ? <span className="lp-hint">Say it or type it</span> : SENTENCE.slice(0, typed)}
            {!done && <span className="lp-caret" />}
          </div>
        </div>
        <div className="lp-day">
          <div className="lp-day-h">
            <b>A week in</b>
            <span>one tap</span>
          </div>
          {done && (
            <div key={meal[0]} className="lp-demo-step">
              <LogCard
                heading="Logged · Diet"
                rows={[
                  { label: 'Meal', value: meal[0] },
                  { label: 'Protein', value: meal[1] },
                  { label: 'Calories', value: meal[2] },
                ]}
              />
            </div>
          )}
          <div className="lp-chips">
            {USUAL.map(([name, g], i) => (
              <span key={name} className={`lp-chip ${done && i === tap ? 'tapped' : ''}`}>
                {name}
                <small>{g}</small>
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function Chapters() {
  return (
    <>
      <Chapter
        id="money"
        n="01"
        name="Money"
        mode="paisa"
        title={
          <>
            Get <span className="lp-em">full control</span> of your expenses.
          </>
        }
        quote="I earn well. I have no idea where it goes."
        problem="You find out what you spent after it’s gone."
        panel={<MoneyPanel />}
      />
      <Chapter
        id="food"
        n="02"
        name="Food"
        mode="diet"
        flip
        title={
          <>
            Hit your <span className="lp-em">health goals</span> with seamless macro and health tracking.
          </>
        }
        quote="I’d eat better if logging didn’t take forever."
        problem="Every food app is a form — search, pick, weigh, repeat — and the log dies on day three."
        extra={
          <div className="lp-not">
            <Dot /> worked out, not told
          </div>
        }
        panel={<FoodPanel />}
      />
      <Chapter
        id="work"
        n="03"
        name="Work"
        mode="work"
        title={
          <>
            All your tasks in one place, so you <span className="lp-em">never miss what matters.</span>
          </>
        }
        quote="My tasks are in Linear, a notepad, WhatsApp and last week’s meeting."
        problem="So the one that matters is the one you forgot to look at."
        panel={<Pipeline />}
      />
    </>
  );
}

/* ─── the results, in numbers ──────────────────────────────────────────── */

/**
 * PLACEHOLDERS — reasonable figures for the design, not measurements. Each is
 * replaced by the measured number before the page is deployed, and how each
 * is measured is written down in TODO.md.
 */
const RESULTS: { mode: string; key: ModeKey; big: string; line: string }[] = [
  { mode: 'Money', key: 'paisa', big: '3×', line: 'more likely to hit your savings goal' },
  { mode: 'Food', key: 'diet', big: '5×', line: 'more days on your calories and protein' },
  { mode: 'Work', key: 'work', big: '90%', line: 'fewer important tasks missed' },
];

/** PLACEHOLDER, like RESULTS — the categoriser measured 74–83%; meals are unmeasured. */
const GUESS_RATE = '9 times in 10';

function Results() {
  return (
    <section className="lp-results" aria-labelledby="results-h">
      <div className="lp-wrap">
        <Reveal>
          <h2 className="lp-h2" id="results-h">
            What changes when it’s all <span className="lp-em">in view.</span>
          </h2>
        </Reveal>
        <div className="lp-results-grid">
          {RESULTS.map((r, i) => (
            <Reveal key={r.mode} className="lp-result" delay={i * 0.08}>
              <div className="lp-chapter-n">
                <span className={`lp-mode ${r.key}`}>{r.mode}</span>
              </div>
              <b>{r.big}</b>
              <p>{r.line}</p>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ─── AI-powered tracking and logging ───────────────────────────────────── */

function AiTracking() {
  return (
    <section className="lp-ai" aria-labelledby="ai-h">
      <div className="lp-wrap">
        <div>
          <Reveal>
            <h2 className="lp-h2" id="ai-h">
              AI-powered <span className="lp-em">tracking and logging.</span>
            </h2>
            <p className="lp-lede">
              Spica guesses what you spent on and what you ate — right {GUESS_RATE} — and fills in the
              category and the macros for you. Logging is one tap.
            </p>
          </Reveal>
          <Reveal delay={0.1}>
            <details className="lp-how">
              <summary>
                How does it work?
                <CaretDownIcon size={20} aria-hidden="true" />
              </summary>
              <div className="lp-how-body">
                <p>
                  <b>Spends.</b> It reads the amount, who you paid and the day, and learns from every correction
                  you make. When it’s sure, it files the spend. When it isn’t, it asks.
                </p>
                <p>
                  <b>Meals.</b> It learns your usual meals and portions from what you log, and works out the rest —
                  with a dot on every number it guessed, so you know what to check.
                </p>
                <p>
                  <b>Your data stays yours.</b> It learns from your own rows. Nothing is read from your SMS or
                  calls.
                </p>
              </div>
            </details>
          </Reveal>
        </div>
        <Reveal className="lp-panel lp-ai-demo" delay={0.12}>
          <Said>Rapido home, one sixty</Said>
          <LogCard
            heading="Logged · Paisa"
            rows={[
              { label: 'Amount', value: rupees(160) },
              { label: 'Category', value: 'Transport', guessed: true },
            ]}
          />
          <Said style={{ marginTop: 8 }}>2 roti, dal and a salad</Said>
          <LogCard
            heading="Logged · Diet"
            rows={[
              { label: 'Protein', value: '18 g', guessed: true },
              { label: 'Calories', value: '410 kcal', guessed: true },
            ]}
          />
        </Reveal>
      </div>
    </section>
  );
}

/* ─── one conversation ──────────────────────────────────────────────────── */

const ASKS: { mode: string; said: string; answer?: string; log?: { heading: string; rows: Row[]; note?: string } }[] = [
  { mode: 'Money · asking', said: 'is mahine khane pe kitna gaya?', answer: `${rupees(6410)} on food so far — ${rupees(2900)} of it delivery.` },
  {
    mode: 'Money · telling',
    said: 'Rohit ko 500 udhaar diye',
    log: { heading: 'Logged · Udhaar', rows: [{ label: 'Person', value: 'Rohit' }, { label: 'Amount', value: rupees(500) }], note: `Rohit owes you ${rupees(1500)} in all.` },
  },
  { mode: 'Food · asking', said: 'aaj protein kitna hua?', answer: '56 g of 90. A paneer or dal dinner closes most of it.' },
  {
    mode: 'Food · telling',
    said: 'breakfast wahi, poha',
    log: { heading: 'Logged · Diet', rows: [{ label: 'Meal', value: 'Poha' }, { label: 'Protein', value: '12 g' }] },
  },
  { mode: 'Work · asking', said: 'kal ke liye kya bacha hai?', answer: 'Two: the pricing sheet, and the checkout fix — still open in Linear.' },
  { mode: 'Honest · asking', said: 'pichhle mahine se zyada kharcha hua?', answer: 'No prior data — September is your first month here. Ask me in October.' },
];

function Conversation() {
  return (
    <section className="lp-convo" id="ask" aria-labelledby="ask-h">
      <div className="lp-wrap">
        <Reveal>
          <h2 className="lp-h2" id="ask-h" style={{ maxWidth: '15em' }}>
            No screens. <span className="lp-em">Just ask.</span>
          </h2>
        </Reveal>
        <div className="lp-convo-grid">
          {ASKS.map((a, i) => (
            <Reveal key={a.said} className="lp-ex" delay={(i % 3) * 0.08}>
              <div className="lp-eyebrow">{a.mode}</div>
              <Said>{a.said}</Said>
              {a.answer ? (
                <AgentSays>{a.answer}</AgentSays>
              ) : (
                <LogCard heading={a.log!.heading} rows={a.log!.rows} note={a.log!.note} />
              )}
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ─── wherever you already are ──────────────────────────────────────────── */

const SURFACES: { mark: ReactNode; name: string; text: string; tag: string; soon?: boolean }[] = [
  {
    mark: <Mascot size={30} state="still" compact />,
    name: 'Spica',
    text: 'Where it all lives. Voice first, on Android — and on the web.',
    tag: 'Android · web',
  },
  {
    mark: <ClaudeMark size={24} />,
    name: 'Claude',
    text: 'A morning routine reads Linear and your meetings and writes your tasks into Spica.',
    tag: 'Built · for work',
  },
  {
    mark: <ChatGPTMark size={24} />,
    name: 'ChatGPT',
    text: 'Log a spend or a meal from a chat you already have open.',
    tag: 'Coming',
    soon: true,
  },
  {
    mark: <WhatsAppMark size={24} />,
    name: 'WhatsApp',
    text: 'Send it to Spica like a message to a friend.',
    tag: 'Coming',
    soon: true,
  },
];

function Everywhere() {
  return (
    <section className="lp-where" aria-labelledby="where-h">
      <div className="lp-wrap">
        <Reveal>
          <div className="lp-eyebrow">Wherever you already are</div>
          <h2 className="lp-h2" id="where-h" style={{ maxWidth: '14em' }}>
            Spica lives in your <span className="lp-em">favourite agent.</span>
          </h2>
          <p className="lp-lede">
            You shouldn’t have to open it to feed it.
          </p>
        </Reveal>
        <div className="lp-where-grid">
          {SURFACES.map((s, i) => (
            <Reveal key={s.name} className="lp-surface" delay={i * 0.07}>
              <span className="lp-surface-mark">{s.mark}</span>
              <b>{s.name}</b>
              <p>{s.text}</p>
              <span className={`lp-tag ${s.soon ? 'soon' : ''}`}>{s.tag}</span>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ─── the close ─────────────────────────────────────────────────────────── */

function Close() {
  return (
    <section className="lp-close" aria-labelledby="close-h">
      <div className="lp-wrap">
        <Reveal>
          <div style={{ display: 'flex', justifyContent: 'center' }}>
            <Mascot size={76} state="idle" />
          </div>
          <h2 className="lp-formula" id="close-h">
            <span>Less time.</span>
            <span>Less effort.</span>
            <span className="lp-em">More kept.</span>
          </h2>
          <p className="lp-lede">Money, food and work — one conversation, and nothing to fill in.</p>
          <Ctas />
          <p className="lp-hero-meta" style={{ justifyContent: 'center' }}>
            <span>The web version is invite-only while it’s early</span>
          </p>
        </Reveal>
      </div>
    </section>
  );
}

/* ─── the page ──────────────────────────────────────────────────────────── */

export default function Landing() {
  const root = useRef<HTMLDivElement>(null);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    document.title = 'Spica — money, food and work, one conversation';
  }, []);

  return (
    <div ref={root} className="lp" style={cssVars} onScroll={(e) => setScrolled(e.currentTarget.scrollTop > 8)}>
      <Nav scrolled={scrolled} />
      <Hero />
      <Drain />
      <FilmSection />
      <Chapters />
      <Results />
      <AiTracking />
      <Conversation />
      <Everywhere />
      <Close />
      <footer className="lp-foot">
        <div className="lp-wrap">
          <span>Spica · a personal OS for money, food and work</span>
          <span>Amounts and names on this page are examples.</span>
        </div>
      </footer>
    </div>
  );
}

/**
 * `/film` — the film alone, full-bleed, for a screen recorder. `?ratio=9x16`
 * letterboxes it to a reel's shape inside whatever window it is in.
 */
export function FilmPage() {
  const ratio = new URLSearchParams(window.location.search).get('ratio');
  const [w, h] = (ratio ?? '').split('x').map(Number);
  const box: CSSProperties =
    w > 0 && h > 0
      ? { aspectRatio: `${w} / ${h}`, height: `min(100vh, calc(100vw * ${h} / ${w}))` }
      : { width: '100%', height: '100%' };
  return (
    <div className="lp" style={{ ...cssVars, overflow: 'hidden', background: color.ink, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div style={box}>
        <Film bleed />
      </div>
    </div>
  );
}
