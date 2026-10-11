import { useEffect, useRef, useState } from 'react';
import { leavingStack } from '../state/nav';
import AboutYou from './AboutYou';
import AllSet from './AllSet';
import type { PickId } from './copy';
import TakeControl from './TakeControl';
import { useAboutYou } from './useAboutYou';

/**
 * The first run: screens 2–4, between sign-in and Home, shown while
 * `onboarding_done_at` is null. spec/done/onboarding-goals.md.
 *
 * Nothing here is stored but the answers themselves — written as they come,
 * through the onboarding agent — and the flag at the end. A reload brings
 * back screen 2 with nothing picked, and screen 3 then passes over any
 * question whose facts are already on the rows.
 *
 * Back is the browser's: screen 3 returns to screen 2 (an Edit is cleared
 * first, then a waiting answer cancelled), screen 4 to screen 3, and on
 * screen 2 it leaves the app, as on the door. One history entry stands above
 * the app's own while screen 3 or 4 is up, so that back lands here. The ←
 * those screens show is the same back, through history.
 */
type Step = 'choose' | 'about' | 'set';

export default function FirstRun({ onDone }: { onDone: () => Promise<void> }) {
  const [step, setStep] = useState<Step>('choose');
  const [picks, setPicks] = useState<ReadonlySet<PickId>>(() => new Set());
  const [leaving, setLeaving] = useState(false);

  const finish = () => {
    if (leaving) return;
    setLeaving(true);
    about.leave();
    release();
    void onDone();
  };
  const about = useAboutYou(picks, finish);

  // ── back ─────────────────────────────────────────────────────────────
  //
  // One entry stands above the app's own while screen 3 or 4 is up. It is
  // pushed on a tap (Continue), never from inside a popstate: Chrome skips
  // back over entries a page adds with no input behind it, and Back would
  // then run straight past the app. When Back only clears an Edit, or steps
  // from screen 4 to 3, this screen steps forward onto the entry it just
  // left, which adds nothing.
  /** This screen's entry is the current one. */
  const held = useRef(false);
  /** A back this screen started itself — finishing, or clearing a leftover entry — not the person's. */
  const releasing = useRef(false);
  /** A forward this screen started, back onto its entry. */
  const returning = useRef(false);
  /** A back from the ← in flight: a second tap must not run past screen 2 and out of the app. */
  const pending = useRef(false);
  /** Continue pressed while a leftover entry was still being cleared: step back onto it once it is. */
  const holdNext = useRef(false);
  const stepRef = useRef(step);
  stepRef.current = step;

  const hold = () => {
    // Checked first: a leftover entry on its way out is this screen's entry,
    // so it is stepped back onto when the clearing lands — not added again.
    if (releasing.current) {
      holdNext.current = true;
      return;
    }
    if (held.current || returning.current) return;
    window.history.pushState({ firstRun: true }, '');
    held.current = true;
  };
  const stepForward = () => {
    returning.current = true;
    // The mark clears itself, so a forward that never lands cannot freeze the ←.
    setTimeout(() => {
      returning.current = false;
    }, 1000);
    window.history.forward();
  };
  const release = () => {
    holdNext.current = false;
    if (!held.current || releasing.current) return;
    releasing.current = true;
    window.history.back();
  };
  /** The person's back, once it has left this screen's entry. True when it only closed something here, so the entry comes back. */
  const onBack = useRef<() => boolean>(() => false);
  onBack.current = () => {
    if (step === 'set') {
      setStep('about');
      return true;
    }
    if (step === 'about') {
      if (about.back()) return true;
      about.leave();
      setStep('choose');
    }
    return false;
  };
  /** The on-screen ←: the browser's back, so both take the same path. */
  const goBack = () => {
    if (pending.current || releasing.current || returning.current) return;
    if (!held.current) {
      // No entry to go back through: act here. The ← is a tap, so the entry may come back.
      if (onBack.current()) hold();
      return;
    }
    pending.current = true;
    setTimeout(() => {
      pending.current = false;
    }, 1000);
    window.history.back();
  };
  useEffect(() => {
    const pop = (e: PopStateEvent) => {
      pending.current = false;
      // Signed out on the way: the app is stepping back to its first entry.
      if (leavingStack()) return;
      if ((e.state as { firstRun?: boolean } | null)?.firstRun) {
        // On this screen's entry again: a forward this screen started, or the person's Forward.
        held.current = true;
        if (returning.current) {
          returning.current = false;
          return;
        }
        // Forward onto it from screen 2, which holds no entry: step off it, silently.
        if (stepRef.current === 'choose') release();
        return;
      }
      if (releasing.current) {
        releasing.current = false;
        held.current = false;
        if (holdNext.current) {
          holdNext.current = false;
          stepForward();
        }
        return;
      }
      // Only the entry this screen pushed is ours to answer.
      if (!held.current) return;
      held.current = false;
      if (onBack.current()) stepForward();
    };
    window.addEventListener('popstate', pop);
    return () => window.removeEventListener('popstate', pop);
    // Reads refs and history only, so the first render's copy is current.
  }, []);
  // A reload on screen 3 or 4 starts again on screen 2, on top of the entry
  // those screens held. Step off it, silently, so the first back here is a
  // real one — and Home never sits on a dead entry.
  useEffect(() => {
    if (held.current || releasing.current) return;
    if (!(window.history.state as { firstRun?: boolean } | null)?.firstRun) return;
    releasing.current = true;
    window.history.back();
  }, []);

  if (step === 'choose') {
    return (
      <TakeControl
        picks={picks}
        busy={leaving}
        onToggle={(id) =>
          setPicks((cur) => {
            const next = new Set(cur);
            if (next.has(id)) next.delete(id);
            else next.add(id);
            return next;
          })
        }
        onContinue={() => {
          setStep('about');
          hold();
          void about.enter();
        }}
        onSkip={finish}
      />
    );
  }

  if (step === 'about') {
    return (
      <AboutYou
        about={about}
        onBack={goBack}
        onSkip={() => {
          about.leave();
          setStep('set');
        }}
        onContinue={() => {
          about.leave();
          setStep('set');
        }}
      />
    );
  }

  return <AllSet busy={leaving} onBack={goBack} onEdit={() => setStep('about')} onStart={finish} />;
}
