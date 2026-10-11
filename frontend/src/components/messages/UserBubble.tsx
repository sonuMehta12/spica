import { ArrowElbowDownRight, X } from '@phosphor-icons/react';
import { color, font, radius } from '../../theme';
import { TextBtn } from './parts';

/**
 * What you said: a pale pill of the brand, ink on it, on the right. The tail
 * is the bottom-right corner — this side is yours. A heavy black pill used to
 * outweigh everything the agent wrote.
 *
 * Said about a row — a card's Change — the row's label sits on a faint line
 * above the bubble, and the bubble keeps only what was typed: "transport",
 * under "Auto · category". The agent got the whole sentence.
 *
 * A message that never reached the server says so itself — "Not sent ·
 * Retry" under the bubble. It was yours that did not go, so no agent bubble
 * speaks for it.
 */
export default function UserBubble({
  text,
  context,
  failed = false,
  onRetry,
}: {
  text: string;
  /** The label of the row it was said about. */
  context?: string;
  failed?: boolean;
  onRetry?: () => void;
}) {
  const r = radius.bubble;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', maxWidth: '100%' }}>
      {context && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 4,
            maxWidth: '100%',
            marginBottom: 4,
            fontFamily: font.sans,
            fontSize: 12,
            lineHeight: '16px',
            color: color.faint,
          }}
        >
          <ArrowElbowDownRight size={12} color={color.faint} aria-hidden style={{ flex: '0 0 auto' }} />
          <span style={{ minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{context}</span>
        </div>
      )}
      <div
        style={{
          background: color.brandTint,
          color: color.ink,
          borderRadius: `${r}px ${r}px 4px ${r}px`,
          padding: '10px 14px',
          fontFamily: font.sans,
          fontSize: 14,
          lineHeight: '20px',
          maxWidth: '100%',
          overflowWrap: 'anywhere',
          opacity: failed ? 0.7 : 1,
          animation: 'fadeup 0.35s',
        }}
      >
        {text}
      </div>
      {failed && (
        <div
          role="status"
          style={{ display: 'flex', alignItems: 'center', gap: 5, marginTop: 5, fontFamily: font.sans, fontSize: 12, lineHeight: '16px' }}
        >
          <X size={12} weight="bold" color={color.red} aria-hidden />
          <span style={{ color: color.red }}>Not sent</span>
          {onRetry && (
            <>
              <span aria-hidden="true" style={{ color: color.faint }}>·</span>
              <TextBtn label="Retry" tone={color.brand} size={12.5} onClick={onRetry} />
            </>
          )}
        </div>
      )}
    </div>
  );
}
