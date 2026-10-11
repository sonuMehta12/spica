import { useEffect, useState } from 'react';
import type { ConnectRequest } from '../data/api';
import { answerConnect, errorStatus, fetchConnectRequest } from '../data/api';
import { BRAND } from '../brand';
import { color, font, inset } from '../theme';
import Mascot from './Mascot';
import { agentVoice } from './messages/bubble';

interface Props {
  request: string;
}

/**
 * Another app asking to reach Spica — in practice, Claude adding Spica as a
 * connector so the work sync can run. spec/work-sync.md § Auth.
 *
 * The SDK's `/authorize` parks the request and sends the browser here, because
 * this is where the person is already signed in. Saying yes is the only thing
 * that grants access: a client that merely registered gets nothing.
 *
 * The page says plainly what the yes covers and what it does not. A consent
 * screen that hides its scope is one nobody should click through.
 */
export default function ConnectPage({ request }: Props) {
  const [asking, setAsking] = useState<ConnectRequest | null>(null);
  const [state, setState] = useState<'loading' | 'ready' | 'sending' | 'gone' | 'error'>(
    'loading',
  );

  useEffect(() => {
    fetchConnectRequest(request).then(
      (r) => {
        setAsking(r);
        setState('ready');
      },
      (e: Error) => setState(errorStatus(e) === 404 ? 'gone' : 'error'),
    );
  }, [request]);

  const answer = (allow: boolean) => {
    setState('sending');
    answerConnect(request, allow).then(
      ({ redirect }) => window.location.assign(redirect),
      (e: Error) => setState(errorStatus(e) === 404 ? 'gone' : 'error'),
    );
  };

  const who = asking?.client_name ?? 'An app';

  return (
    <div
      style={{
        minHeight: '100%',
        background: color.surface,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: `${inset.top} 16px ${inset.bottom}`,
        fontFamily: font.sans,
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: 380,
          background: color.white,
          border: `1px solid ${color.line}`,
          borderRadius: 18,
          padding: '22px 20px 18px',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 12 }}>
          <Mascot size={56} />
        </div>

        {state === 'loading' && <p style={{ ...agentVoice, margin: 0 }}>Checking the request…</p>}

        {state === 'gone' && (
          <p style={{ ...agentVoice, margin: 0 }}>
            This request has expired or was already answered. Start again from the app that
            asked.
          </p>
        )}

        {state === 'error' && (
          <p style={{ ...agentVoice, margin: 0 }}>
            Couldn’t reach Spica to answer this. Try again in a moment.
          </p>
        )}

        {/* Not a dead end: the way into the app, whatever happened to the request. */}
        {(state === 'gone' || state === 'error') && (
          <a
            href="/app"
            style={{
              display: 'inline-block',
              marginTop: 14,
              fontFamily: font.sans,
              fontSize: 14,
              fontWeight: 500,
              color: color.brand,
              textDecoration: 'none',
            }}
          >
            Open {BRAND}
          </a>
        )}

        {(state === 'ready' || state === 'sending') && asking && (
          <>
            <h1
              style={{
                fontFamily: font.sans,
                fontSize: 19,
                lineHeight: 1.25,
                fontWeight: 600,
                color: color.ink,
                margin: '0 0 10px',
                textAlign: 'center',
              }}
            >
              {who} wants to reach your tasks
            </h1>

            <p style={{ ...agentVoice, margin: '0 0 8px' }}>
              It can read your open tasks and add the ones it finds in Linear and your meetings.
            </p>
            <p style={{ ...agentVoice, margin: '0 0 14px' }}>
              It can’t see your money, food or anything else in Spica, and Spica never changes
              anything in Linear.
            </p>

            <div
              style={{
                fontFamily: font.sans,
                fontSize: 12,
                color: color.faint,
                borderTop: `1px solid ${color.line}`,
                paddingTop: 10,
                marginBottom: 16,
              }}
            >
              Returns to · {asking.redirect_host}
            </div>

            <div style={{ display: 'flex', gap: 8 }}>
              <button
                type="button"
                disabled={state === 'sending'}
                onClick={() => answer(false)}
                style={{
                  flex: 1,
                  height: 40,
                  borderRadius: 999,
                  border: `1px solid ${color.border}`,
                  background: color.white,
                  color: color.ink,
                  fontFamily: font.sans,
                  fontSize: 14,
                  fontWeight: 500,
                  cursor: 'pointer',
                }}
              >
                Not now
              </button>
              <button
                type="button"
                disabled={state === 'sending'}
                onClick={() => answer(true)}
                style={{
                  flex: 1,
                  height: 40,
                  borderRadius: 999,
                  border: 'none',
                  background: color.brand,
                  color: color.white,
                  fontFamily: font.sans,
                  fontSize: 14,
                  fontWeight: 500,
                  cursor: 'pointer',
                  opacity: state === 'sending' ? 0.7 : 1,
                }}
              >
                {state === 'sending' ? 'Sending…' : 'Allow'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
