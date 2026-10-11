import { useEffect, useRef, useState } from 'react';
import { Lock } from '@phosphor-icons/react';
import { BRAND, PITCH, WORDMARK } from '../brand';
import type { Profile } from '../data/api';
import { errorStatus, signInWithGoogle } from '../data/api';
import DoorFilm from '../door/DoorFilm';
import { color, font, inset } from '../theme';
import { agentVoice } from './messages/bubble';

/**
 * The door: the one screen before sign-in, and the whole pitch.
 *
 * The wordmark, a film made only of dots, the line, and Google's own button.
 * The film sells the outcome — a life put in order, becoming results — rather
 * than a logger; it plays while the person signs in, and loops. No subheading,
 * no controls, no labels.
 *
 * spec/done/onboarding-goals.md § 1 · The door.
 */

const CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined;
const GSI = 'https://accounts.google.com/gsi/client';

/** Google draws its button between these widths. */
const GSI_MIN = 200;
const GSI_MAX = 400;

function useGoogleScript(): boolean {
  const [ready, setReady] = useState(() => Boolean(window.google?.accounts?.id));

  useEffect(() => {
    if (ready || !CLIENT_ID) return;
    const existing = document.querySelector<HTMLScriptElement>(`script[src="${GSI}"]`);
    const el = existing ?? document.createElement('script');
    const done = () => setReady(Boolean(window.google?.accounts?.id));
    el.addEventListener('load', done);
    if (!existing) {
      el.src = GSI;
      el.async = true;
      document.head.appendChild(el);
    } else if (window.google?.accounts?.id) done();
    return () => el.removeEventListener('load', done);
  }, [ready]);

  return ready;
}

export default function Door({ onSignedIn }: { onSignedIn: (p: Profile) => void }) {
  const ready = useGoogleScript();
  const button = useRef<HTMLDivElement>(null);
  const [problem, setProblem] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!ready || !button.current || !CLIENT_ID) return;
    const id = window.google!.accounts!.id;
    id.initialize({
      client_id: CLIENT_ID,
      callback: async (res: { credential?: string }) => {
        if (!res.credential) return;
        setBusy(true);
        setProblem('');
        try {
          onSignedIn(await signInWithGoogle(res.credential));
        } catch (e) {
          // 403 is a sentence for the user, not a failure to retry.
          setProblem(
            errorStatus(e) === 403
              ? `${BRAND} is invite-only right now.`
              : 'That did not go through. Try again.',
          );
          setBusy(false);
        }
      },
    });
    // The column's width, within what Google will draw: the button spans the
    // door the way the rest of the screens' buttons do.
    // Measured before layout has settled it can read 0: then the widest.
    const avail = button.current.getBoundingClientRect().width || GSI_MAX;
    const width = Math.round(Math.min(GSI_MAX, Math.max(GSI_MIN, avail)));
    id.renderButton(button.current, {
      theme: 'outline',
      size: 'large',
      shape: 'pill',
      text: 'continue_with',
      width,
    });
  }, [ready, onSignedIn]);

  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        background: color.paper,
        display: 'flex',
        flexDirection: 'column',
        padding: `${inset.top} 0 ${inset.bottom}`,
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          flex: '0 0 auto',
          paddingTop: 16,
          textAlign: 'center',
          fontFamily: font.sans,
          fontWeight: 600,
          fontSize: 20,
          letterSpacing: -0.5,
          color: color.ink,
        }}
      >
        {WORDMARK}
      </div>

      {/* The film takes what is left, whole and centred: it scales down to
          fit, never up, and the door never scrolls. */}
      <div style={{ flex: '1 1 0', minHeight: 0, marginTop: 6 }}>
        <DoorFilm />
      </div>

      <div
        style={{
          ...agentVoice,
          flex: '0 0 auto',
          marginTop: 6,
          padding: '0 20px',
          fontSize: 25,
          lineHeight: '31px',
          fontWeight: 500,
          textAlign: 'center',
        }}
      >
        {PITCH[0]}
        <br />
        {PITCH[1]}
      </div>

      <div
        style={{
          flex: '0 0 auto',
          padding: '24px 20px 10px',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 12,
        }}
      >
        {/* Google draws its own button; the wrapper reserves the space so the
            layout does not jump when the script finishes loading. */}
        <div
          ref={button}
          style={{
            width: '100%',
            maxWidth: GSI_MAX,
            minHeight: 44,
            display: 'flex',
            justifyContent: 'center',
            opacity: busy ? 0.5 : 1,
          }}
        />
        {!CLIENT_ID && (
          <div style={{ ...agentVoice, color: color.red, textAlign: 'center' }}>
            Sign-in is not configured. VITE_GOOGLE_CLIENT_ID is unset.
          </div>
        )}
        {problem && (
          <div style={{ ...agentVoice, color: color.red, textAlign: 'center' }}>{problem}</div>
        )}
        {/* No export, no sale, delete anything — not "it stays on the phone". */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            fontFamily: font.sans,
            fontSize: 13,
            color: color.faint,
          }}
        >
          <Lock size={14} color={color.faint} aria-hidden />
          Your data stays yours
        </div>
      </div>
    </div>
  );
}
