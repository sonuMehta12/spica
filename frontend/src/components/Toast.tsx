import { Check, X } from '@phosphor-icons/react';
import { color, font, inset, radius, shadow } from '../theme';

export interface ToastMsg {
  id: number;
  text: string;
  sub?: string;
  /** A refusal: drawn with a ✕, never the success tick. */
  failed?: boolean;
}

/**
 * A receipt. It appears above the composer for a few seconds and goes — the
 * way a payment app confirms a payment. It is not a message: the thread is for
 * things that were said, the ledger holds the fact, and the card that was
 * tapped already reads `✓ Logged` from the ledger. spec/done/chat-cards.md § 3.
 *
 * One of the two things that float, so it lifts. The tick is the brand's soft
 * stop — amber is only ever the estimate dot.
 *
 * `role=status` so it is read aloud once; tapping it dismisses it early.
 */
export default function Toast({ toast, onDismiss }: { toast: ToastMsg | null; onDismiss: () => void }) {
  if (!toast) return null;
  return (
    <div
      style={{
        position: 'fixed',
        left: 0,
        right: 0,
        bottom: `calc(${inset.bottom} + 78px)`,
        display: 'flex',
        justifyContent: 'center',
        pointerEvents: 'none',
        // Above every screen of the stack (60 + depth) and the sheet, so a
        // refusal raised on a page is seen on that page.
        zIndex: 130,
      }}
    >
      <button
        key={toast.id}
        type="button"
        role="status"
        aria-live="polite"
        onClick={onDismiss}
        style={{
          pointerEvents: 'auto',
          display: 'flex',
          alignItems: 'flex-start',
          gap: 8,
          maxWidth: 'min(92vw, 420px)',
          padding: '9px 14px 9px 12px',
          borderRadius: radius.card,
          border: 'none',
          background: color.ink,
          color: color.paper,
          boxShadow: shadow.popover,
          cursor: 'pointer',
          textAlign: 'left',
          animation: 'toast-in 0.28s cubic-bezier(0.2, 1.2, 0.4, 1)',
        }}
      >
        {toast.failed ? (
          <X size={15} weight="bold" color={color.red} aria-hidden style={{ flex: '0 0 auto', marginTop: 2 }} />
        ) : (
          <Check size={15} weight="bold" color={color.brandSoft} aria-hidden style={{ flex: '0 0 auto', marginTop: 2 }} />
        )}
        <span style={{ fontFamily: font.sans, fontSize: 13, lineHeight: '18px' }}>
          {toast.text}
          {toast.sub && (
            <span style={{ display: 'block', fontSize: 11.5, lineHeight: '15px', color: color.ringIdle, marginTop: 2 }}>
              {toast.sub}
            </span>
          )}
        </span>
      </button>
    </div>
  );
}
