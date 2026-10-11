import { lazy, Suspense, useCallback, useEffect, useState, type ReactNode } from 'react';
import App from './App';
import ConnectPage from './components/ConnectPage';
import Door from './components/Door';
import type { Profile } from './data/api';
import { errorStatus, getToken, onSignedOut } from './data/api';
import { loadDeck, ONBOARDING_DONE_AT, PROFILE } from './data/live';
import { useViewportHeight } from './lib/useViewportHeight';
import FirstRun from './onboarding/FirstRun';
import { leaveStack } from './state/nav';
import { finishedHere, forgetFinish, sendFinish } from './onboarding/finish';
import { color, font, radius } from './theme';

/**
 * The gate: signed in and loaded, or the door — and, between the two, the
 * first run, while the server says it is still owed.
 *
 * It exists because `data/live.ts` exposes module values that only become real
 * after the fetch. Rendering first and filling in later would flash zeros — and
 * a zero the server did not send is a fabricated number, which is the one thing
 * the deck must never show.
 *
 * Sign-in sits in front of that for the same reason: with no token there is
 * nothing to load, and a 401 mid-session means the deck on screen is no longer
 * anybody's, so it goes back to the door rather than sitting there stale.
 */
/**
 * Where things live. The root is the landing page, so the domain itself is
 * the pitch; the app is at `/app`. `/connect` stays at the top because the
 * backend's `/authorize` sends the browser there (`APP_URL/connect`), and
 * `/film` is the film alone, for recording. Any other path is the landing.
 */
const path = window.location.pathname.replace(/\/+$/, '') || '/';
const inApp = path === '/app' || path.startsWith('/app/') || path === '/connect';

/** `/connect?request=…` — the page OAuth's `/authorize` sends the browser to. */
const connectRequest =
  path === '/connect' ? new URLSearchParams(window.location.search).get('request') : null;

/**
 * The pages that need no account are loaded only when asked for, so the app's
 * bundle does not carry them — and the landing's example deck, which it writes
 * into the live bindings, is never evaluated in a signed-in session.
 */
const Landing = lazy(() => import('./landing/Landing'));
const FilmPage = lazy(() => import('./landing/Landing').then((m) => ({ default: m.FilmPage })));

export default function Boot() {
  if (inApp) return <Gate />;
  const Page = path === '/film' ? FilmPage : Landing;
  return (
    <Suspense fallback={null}>
      <Page />
    </Suspense>
  );
}

/** The app's column, the same width the app itself sits in. */
function Column({ children }: { children: ReactNode }) {
  return <div className="app-shell">{children}</div>;
}

/**
 * Whether the first run stands in front of Home: while the deck's flag is
 * unset (spec/done/onboarding-goals.md § Which flag). A first run finished here
 * whose flag never landed does not show again — the flag goes again now.
 */
function firstRunOwed(): boolean {
  if (ONBOARDING_DONE_AT) {
    forgetFinish();
    return false;
  }
  if (finishedHere(PROFILE.id)) {
    sendFinish(PROFILE.id).catch(() => undefined);
    return false;
  }
  return true;
}

function Gate() {
  const [status, setStatus] = useState<'loading' | 'first-run' | 'ready' | 'error' | 'door'>(
    getToken() ? 'loading' : 'door',
  );
  const [detail, setDetail] = useState('');
  useViewportHeight();

  /**
   * Signed out — by the menu, or by a 401 mid-session. The screens that were
   * open are someone's session: history steps back to the app's first entry
   * and wipes it, so neither the door's Back nor the next sign-in (perhaps
   * another account) can reach their Report or Menu again.
   */
  const toDoor = useCallback(() => {
    leaveStack();
    setStatus('door');
  }, []);

  const load = useCallback(() => {
    setStatus('loading');
    loadDeck().then(
      () => setStatus(firstRunOwed() ? 'first-run' : 'ready'),
      (e: Error) => {
        // A stale token reads as *sign in*, not as a dead API.
        if (errorStatus(e) === 401) {
          toDoor();
          return;
        }
        setDetail(e.message);
        setStatus('error');
      },
    );
  }, [toDoor]);

  useEffect(() => {
    if (getToken()) load();
  }, [load]);

  // The one thing to do about being signed out is to show the door.
  useEffect(() => {
    onSignedOut(toDoor);
    return () => onSignedOut(null);
  }, [toDoor]);

  const signedIn = useCallback((_p: Profile) => load(), [load]);

  /**
   * Get started, Skip, Skip for now: the flag, then the deck again — so the
   * habits and targets just set are on Home — then Home. A flag that does not
   * land still opens Home; it is sent again on the next start.
   */
  const finishFirstRun = useCallback(async () => {
    try {
      await sendFinish(PROFILE.id);
    } catch (e) {
      if (errorStatus(e) === 401) return; // signed out: the door is up
    }
    try {
      await loadDeck();
    } catch (e) {
      if (errorStatus(e) === 401) return;
      // The deck already loaded stands: real rows, if not the newest.
    }
    setStatus('ready');
  }, []);

  // Another app asking to reach Spica (spec/work-sync.md § Auth). The answer
  // needs the person signed in and nothing else — not the deck.
  // Opening this before the first run skips it; it shows on the next visit to the app.
  if (connectRequest) {
    if (status === 'door') return <Column><Door onSignedIn={signedIn} /></Column>;
    return <ConnectPage request={connectRequest} />;
  }

  if (status === 'door') return <Column><Door onSignedIn={signedIn} /></Column>;
  if (status === 'first-run') return <Column><FirstRun onDone={finishFirstRun} /></Column>;
  if (status === 'ready') return <App onSignedOut={toDoor} />;

  return (
    <div
      style={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        gap: 8,
        padding: 24,
        fontFamily: font.sans,
        fontSize: 12.5,
        lineHeight: 1.55,
        color: status === 'error' ? color.ink : color.faint,
      }}
    >
      {status === 'loading' ? (
        'Loading…'
      ) : (
        <>
          <div>Couldn’t reach the server.</div>
          {/* Say what broke rather than rendering an empty deck that looks
              like a day with nothing in it. */}
          <div style={{ fontFamily: font.sans, fontSize: 12, color: color.faint }}>{detail}</div>
          {/* Not a dead end: the phone's boot screen has the same way on. */}
          <button
            type="button"
            onClick={load}
            className="hov-chip"
            style={{
              alignSelf: 'flex-start',
              marginTop: 8,
              fontFamily: font.sans,
              fontSize: 13.5,
              fontWeight: 500,
              padding: '8px 16px',
              borderRadius: radius.pill,
              border: `1px solid ${color.border}`,
              background: color.white,
              color: color.brand,
              cursor: 'pointer',
            }}
          >
            Retry
          </button>
        </>
      )}
    </div>
  );
}
