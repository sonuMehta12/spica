/**
 * The film's sound: small effects on the beats, and a soft pad under each
 * scene. All synthesised with Web Audio — no files to fetch, nothing to
 * license, and it can never drift out of sync with a picture that is itself
 * drawn from a clock.
 *
 * On by default. What no code can do is make a browser play sound before the
 * visitor has clicked, tapped or pressed a key on the page — scrolling does
 * not count, in Chrome, Safari or Firefox. So this does everything short of
 * that, in order:
 *
 * 1. Asks at once. The context is created on load; where the browser already
 *    allows sound for the site (Chrome's media engagement, a site permission,
 *    an installed app) it runs straight away.
 * 2. Listens for every gesture that counts, anywhere on the page, and keeps
 *    listening until the context actually runs — a touch that turns out to be
 *    a scroll does not count, so one attempt is not enough.
 * 3. Plays a silent sample inside that gesture (older iOS Safari needs a
 *    sound started, not only `resume()`), and asks iOS for the *playback*
 *    session so the ring/silent switch does not mute it.
 * 4. Says when it is still waiting (`locked`), so the film can show *Tap for
 *    sound* instead of playing silent without a word.
 *
 * Effects are only scheduled while the context runs: a suspended context's
 * clock is frozen, and anything queued on it would fire in one burst later.
 */

/** Events a browser treats as the visitor's activation. */
const GESTURES = ['pointerup', 'pointerdown', 'mousedown', 'touchend', 'click', 'keydown'] as const;

export type Sfx = 'pop' | 'tick' | 'whoosh' | 'chime' | 'drop' | 'thud' | 'done' | 'tap' | 'rise';

/** One chord per scene, low and open — it marks the cut without a cue. */
const CHORDS: number[][] = [
  [146.83, 185.0, 220.0, 277.18], // D maj7 — salary day
  [123.47, 146.83, 185.0, 220.0], // B m7 — it leaves
  [82.41, 123.47, 146.83, 196.0], // E m7 — day 18
  [98.0, 146.83, 185.0, 246.94], // G maj7 — one number
  [146.83, 185.0, 220.0, 277.18], // D maj7 — say it
  [110.0, 164.81, 220.0, 277.18], // A — food
  [123.47, 146.83, 185.0, 246.94], // B m — work
  [98.0, 146.83, 185.0, 246.94], // G maj7 — ask
  [110.0, 146.83, 196.0, 246.94], // A sus — everywhere
  [146.83, 220.0, 277.18, 329.63], // D maj9 — the close
];

type Voice = { oscs: OscillatorNode[]; gain: GainNode };

export class FilmSound {
  private ctx: AudioContext | null = null;
  private out: GainNode | null = null;
  private noiseBuf: AudioBuffer | null = null;
  private voice: Voice | null = null;
  private chord = -1;
  private listening = false;
  private subscribers = new Set<() => void>();
  /** The viewer's choice: sound on. On by default; the button turns it off. */
  wanted = false;

  /** Sound is actually coming out. */
  get on() {
    return this.wanted && this.ctx?.state === 'running';
  }

  /** Wanted, but the browser is still holding it for a gesture. */
  get locked() {
    return this.wanted && this.ctx?.state !== 'running';
  }

  /** Called whenever `on` or `locked` may have changed. */
  subscribe(fn: () => void) {
    this.subscribers.add(fn);
    return () => void this.subscribers.delete(fn);
  }

  private emit() {
    this.subscribers.forEach((fn) => fn());
  }

  /** Turn sound on. Safe to call without a gesture: it asks, then waits for one. */
  want() {
    this.wanted = true;
    this.context();
    void this.ctx?.resume().catch(() => {});
    if (this.ctx?.state !== 'running') this.listen();
    this.emit();
  }

  /** Turn sound off — the viewer's choice, kept until they turn it back on. */
  unwant() {
    this.wanted = false;
    this.stopListening();
    this.hush();
    void this.ctx?.suspend().catch(() => {});
    this.emit();
  }

  /** Inside a gesture: the moment a browser lets audio start. */
  unlock = () => {
    if (!this.wanted) return;
    const ctx = this.context();
    if (!ctx) return;
    void ctx.resume().catch(() => {});
    // Older iOS Safari only unlocks when a sound is started in the gesture.
    const blip = ctx.createBufferSource();
    blip.buffer = ctx.createBuffer(1, 1, ctx.sampleRate);
    blip.connect(ctx.destination);
    blip.start(0);
  };

  /** Stop and let go of the context — the film is leaving the page. */
  dispose() {
    this.unwant();
    this.subscribers.clear();
  }

  private context(): AudioContext | null {
    if (this.ctx && this.ctx.state !== 'closed') return this.ctx;
    const AC =
      window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!AC) return null;
    // iOS 16.4+: the playback session plays through the silent switch, the
    // way a video does; without it Web Audio is muted by the switch.
    const session = (navigator as Navigator & { audioSession?: { type: string } }).audioSession;
    if (session) session.type = 'playback';
    const ctx = new AC();
    const comp = ctx.createDynamicsCompressor();
    comp.threshold.value = -14;
    comp.ratio.value = 4;
    const out = ctx.createGain();
    out.gain.value = 0.9;
    out.connect(comp).connect(ctx.destination);
    const buf = ctx.createBuffer(1, ctx.sampleRate, ctx.sampleRate);
    const data = buf.getChannelData(0);
    for (let i = 0; i < data.length; i++) data[i] = Math.random() * 2 - 1;
    ctx.onstatechange = () => {
      // Running: stop listening. Suspended again (a phone call, a hidden tab
      // on iOS): listen again, so the next tap brings it back.
      if (ctx.state === 'running') this.stopListening();
      else if (this.wanted) this.listen();
      this.emit();
    };
    this.ctx = ctx;
    this.out = out;
    this.noiseBuf = buf;
    return ctx;
  }

  private listen() {
    if (this.listening) return;
    this.listening = true;
    GESTURES.forEach((ev) => window.addEventListener(ev, this.unlock, { capture: true, passive: true }));
  }

  private stopListening() {
    if (!this.listening) return;
    this.listening = false;
    GESTURES.forEach((ev) => window.removeEventListener(ev, this.unlock, { capture: true }));
  }

  /** Stop the pad (a pause); effects simply stop being asked for. */
  hush() {
    this.release(this.voice, 0.4);
    this.voice = null;
    this.chord = -1;
  }

  /** The pad for scene `i`; a no-op if it is already sounding. */
  bed(i: number) {
    if (!this.on || !this.ctx || !this.out || i === this.chord) return;
    const ctx = this.ctx;
    this.release(this.voice, 1.4);
    this.chord = i;
    const gain = ctx.createGain();
    gain.gain.setValueAtTime(0, ctx.currentTime);
    gain.gain.linearRampToValueAtTime(0.05, ctx.currentTime + 1.2);
    const lp = ctx.createBiquadFilter();
    lp.type = 'lowpass';
    lp.frequency.value = 900;
    gain.connect(lp).connect(this.out);
    const oscs: OscillatorNode[] = [];
    for (const f of CHORDS[i % CHORDS.length]) {
      for (const [type, cents] of [['sine', 0], ['triangle', 7]] as const) {
        const o = ctx.createOscillator();
        o.type = type;
        o.frequency.value = f;
        o.detune.value = cents;
        o.connect(gain);
        o.start();
        oscs.push(o);
      }
    }
    this.voice = { oscs, gain };
  }

  play(name: Sfx) {
    if (!this.on || !this.ctx) return;
    switch (name) {
      case 'pop':
        this.tone(560, { to: 840, dur: 0.12, gain: 0.1 });
        break;
      case 'tick':
        this.tone(1800, { type: 'triangle', dur: 0.035, gain: 0.035 });
        break;
      case 'tap':
        this.tone(1000, { type: 'triangle', to: 700, dur: 0.06, gain: 0.08 });
        break;
      case 'drop':
        this.tone(700, { to: 350, dur: 0.14, gain: 0.045 });
        break;
      case 'thud':
        this.tone(95, { to: 48, dur: 0.38, gain: 0.32 });
        break;
      case 'rise':
        this.tone(320, { to: 960, dur: 0.85, gain: 0.035, attack: 0.3 });
        break;
      case 'chime':
        this.tone(1318.5, { dur: 1.3, gain: 0.07 });
        this.tone(1975.5, { dur: 1.2, gain: 0.05, delay: 0.09 });
        break;
      case 'done':
        this.tone(880, { dur: 0.18, gain: 0.08 });
        this.tone(1318.5, { dur: 0.3, gain: 0.08, delay: 0.08 });
        break;
      case 'whoosh':
        this.noise({ dur: 0.45, gain: 0.06, from: 350, to: 2600 });
        break;
    }
  }

  private tone(
    freq: number,
    o: { type?: OscillatorType; to?: number; dur: number; gain: number; attack?: number; delay?: number },
  ) {
    const ctx = this.ctx!;
    const t0 = ctx.currentTime + (o.delay ?? 0);
    const osc = ctx.createOscillator();
    osc.type = o.type ?? 'sine';
    osc.frequency.setValueAtTime(freq, t0);
    if (o.to) osc.frequency.exponentialRampToValueAtTime(o.to, t0 + o.dur);
    const g = ctx.createGain();
    const a = o.attack ?? 0.005;
    g.gain.setValueAtTime(0.0001, t0);
    g.gain.exponentialRampToValueAtTime(o.gain, t0 + a);
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + o.dur);
    osc.connect(g).connect(this.out!);
    osc.start(t0);
    osc.stop(t0 + o.dur + 0.05);
  }

  private noise(o: { dur: number; gain: number; from: number; to: number }) {
    const ctx = this.ctx!;
    const t0 = ctx.currentTime;
    const src = ctx.createBufferSource();
    src.buffer = this.noiseBuf;
    const bp = ctx.createBiquadFilter();
    bp.type = 'bandpass';
    bp.Q.value = 0.9;
    bp.frequency.setValueAtTime(o.from, t0);
    bp.frequency.exponentialRampToValueAtTime(o.to, t0 + o.dur);
    const g = ctx.createGain();
    g.gain.setValueAtTime(0.0001, t0);
    g.gain.exponentialRampToValueAtTime(o.gain, t0 + o.dur * 0.35);
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + o.dur);
    src.connect(bp).connect(g).connect(this.out!);
    src.start(t0);
    src.stop(t0 + o.dur + 0.05);
  }

  private release(v: Voice | null, secs: number) {
    if (!v || !this.ctx) return;
    const t = this.ctx.currentTime;
    v.gain.gain.cancelScheduledValues(t);
    v.gain.gain.setValueAtTime(v.gain.gain.value, t);
    v.gain.gain.linearRampToValueAtTime(0, t + secs);
    v.oscs.forEach((o) => o.stop(t + secs + 0.05));
  }
}
