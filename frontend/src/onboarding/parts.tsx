import type { CSSProperties, ReactNode } from 'react';
import { ArrowLeft } from '@phosphor-icons/react';
import { WORDMARK } from '../brand';
import Mascot from '../components/Mascot';
import { agentVoice } from '../components/messages/bubble';
import { color, font, inset, radius, space } from '../theme';

/**
 * The pieces the first run's screens share. They wear the web's surfaces —
 * a white page, hairline borders, no shadow (THEME.md § Surface).
 */

/** The logo: the mark at 24, the smallest size it draws all nine dots, and the wordmark. Still. */
export function Logo() {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 7 }}>
      <Mascot size={24} state="still" />
      <span style={{ fontFamily: font.sans, fontWeight: 600, fontSize: 19, letterSpacing: -0.5, color: color.ink }}>
        {WORDMARK}
      </span>
    </span>
  );
}

/**
 * Logo top left, after a ← on the screens that have a step before them; Skip,
 * when the screen has one, top right. The ← is the browser's back, so the two
 * are one path.
 */
export function TopBar({ onSkip, onBack }: { onSkip?: () => void; onBack?: () => void }) {
  return (
    <div
      style={{
        flex: '0 0 auto',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        height: 44,
        padding: `0 ${space.gutter + 4}px`,
        marginTop: `calc(${inset.top} - 6px)`,
      }}
    >
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
        {onBack && (
          <button
            type="button"
            onClick={onBack}
            aria-label="Back"
            className="hov-tint"
            style={{
              width: 36,
              height: 36,
              marginLeft: -8,
              borderRadius: '50%',
              background: 'none',
              border: 'none',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              padding: 0,
              color: color.muted,
            }}
          >
            <ArrowLeft size={20} aria-hidden />
          </button>
        )}
        <Logo />
      </span>
      {onSkip && (
        <button
          type="button"
          onClick={onSkip}
          className="hov-ink"
          style={{
            background: 'none',
            border: 'none',
            padding: '12px 0 12px 12px',
            fontFamily: font.sans,
            fontSize: 15,
            color: color.muted,
            cursor: 'pointer',
          }}
        >
          Skip
        </button>
      )}
    </div>
  );
}

/** A screen's opening: the agent's words, large, then its one line under them. */
export function Opening({ title, line, top = 34 }: { title: string; line: string; top?: number }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: `${top}px 4px 0` }}>
      <div style={{ ...agentVoice, fontSize: 30, lineHeight: '36px', fontWeight: 500, letterSpacing: -0.3 }}>{title}</div>
      <div style={{ ...agentVoice, fontSize: 17, lineHeight: '25px' }}>{line}</div>
    </div>
  );
}

/** The screen's one way on: the brand, filled, the width of the column. */
export function BigButton({
  label,
  onClick,
  busy = false,
}: {
  label: string;
  onClick: () => void;
  busy?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={busy}
      className={busy ? undefined : 'hov-brand'}
      style={{
        width: '100%',
        height: 52,
        border: 'none',
        borderRadius: radius.pill,
        background: color.brand,
        color: color.white,
        fontFamily: font.sans,
        fontSize: 16,
        fontWeight: 500,
        cursor: busy ? 'default' : 'pointer',
        opacity: busy ? 0.6 : 1,
        flex: '0 0 auto',
      }}
    >
      {label}
    </button>
  );
}

/** A card on the page: white, a hairline, no lift. */
export const card: CSSProperties = {
  background: color.white,
  border: `1px solid ${color.line}`,
  borderRadius: radius.card,
};

/** A whole screen, filling the app column. */
export function Screen({ children }: { children: ReactNode }) {
  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        background: color.paper,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}
    >
      {children}
    </div>
  );
}
