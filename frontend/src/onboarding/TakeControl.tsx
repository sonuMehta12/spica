import { Check } from '@phosphor-icons/react';
import { Coin } from '../components/messages/parts';
import { color, font, inset, space } from '../theme';
import { HELLO, PICKS, TAKE_CONTROL, type PickId } from './copy';
import { BigButton, Opening, Screen, TopBar, card } from './parts';

/**
 * Screen 2 · Take control. Five picks, none made for the person, each said as
 * what they get. The picks choose screen 3's questions; nothing on the server
 * reads them. With none picked, the way on reads *Skip for now* and goes to
 * Home. spec/done/onboarding-goals.md § 2.
 */
export default function TakeControl({
  picks,
  onToggle,
  onContinue,
  onSkip,
  busy,
}: {
  picks: ReadonlySet<PickId>;
  onToggle: (id: PickId) => void;
  onContinue: () => void;
  onSkip: () => void;
  /** Leaving for Home: the flag is on its way. */
  busy: boolean;
}) {
  const none = picks.size === 0;
  return (
    <Screen>
      <TopBar onSkip={busy ? undefined : onSkip} />
      <div className="scroll-y" style={{ flex: '1 1 auto', minHeight: 0, padding: `0 ${space.gutter}px` }}>
        <Opening title={HELLO} line={TAKE_CONTROL} />
        <div style={{ ...card, marginTop: 24, overflow: 'hidden' }}>
          {PICKS.map((p, k) => {
            const on = picks.has(p.id);
            return (
              <button
                key={p.id}
                type="button"
                aria-pressed={on}
                onClick={() => onToggle(p.id)}
                className="hov-tint"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12,
                  width: '100%',
                  minHeight: 68,
                  padding: '12px 16px',
                  border: 'none',
                  borderTop: k === 0 ? 'none' : `1px solid ${color.line}`,
                  background: color.white,
                  textAlign: 'left',
                  cursor: 'pointer',
                  color: color.ink,
                }}
              >
                <Coin icon={p.icon} tint={p.tint} ink={p.ink} size={40} />
                <span style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <span style={{ fontFamily: font.sans, fontSize: 16, lineHeight: '21px', fontWeight: 500 }}>{p.title}</span>
                  <span style={{ fontFamily: font.sans, fontSize: 13.5, lineHeight: '18px', color: color.muted }}>{p.line}</span>
                </span>
                {/* A selection, so the brand — and the tick says it without the colour. */}
                <span
                  aria-hidden="true"
                  style={{
                    flex: '0 0 auto',
                    width: 24,
                    height: 24,
                    borderRadius: '50%',
                    boxSizing: 'border-box',
                    border: on ? 'none' : `1.5px solid ${color.border}`,
                    background: on ? color.brand : color.white,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    transition: 'background-color 0.2s ease, border-color 0.2s ease',
                  }}
                >
                  {on && <Check size={13} weight="bold" color={color.white} />}
                </span>
              </button>
            );
          })}
        </div>
      </div>
      <div style={{ flex: '0 0 auto', padding: `16px ${space.gutter}px ${inset.bottom}` }}>
        <BigButton label={none ? 'Skip for now' : 'Continue'} onClick={none ? onSkip : onContinue} busy={busy} />
      </div>
    </Screen>
  );
}
