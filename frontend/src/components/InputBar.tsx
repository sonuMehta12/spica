import { useLayoutEffect, useRef, type ChangeEvent, type KeyboardEvent, type ReactNode, type Ref } from 'react';
import { PencilSimple, X } from '@phosphor-icons/react';
import { useBack } from '../state/nav';
import { color, font, inset, radius, space } from '../theme';
import { MediaIcon, MicIcon, SendIcon } from './Icons';
import type { ComposerContext } from '../types';

interface Props {
  typed: string;
  /**
   * Bumped when something outside the composer claims it — a card's Change,
   * a chip on the first run. The cursor follows: filling a box and leaving the
   * user to find it is half a gesture. A counter, not a boolean, so the same
   * claim twice still focuses.
   */
  focusKey?: number;
  /**
   * Take the cursor on mount — Home's composer coming back after an ask sent
   * from a page, when the person is mid-conversation. Off by default: an
   * autofocused composer would open the keyboard over the deck at every start.
   */
  focusOnMount?: boolean;
  onType: (v: string) => void;
  onSend: () => void;
  /** No mic button without one — where there is nothing to listen with. */
  onMic?: () => void;
  /** No photo button without one. */
  onMedia?: () => void;
  /** The mic is listening: its button stops it. */
  listening?: boolean;
  /** A turn is in flight: send and the mic wait for it. */
  waiting?: boolean;
  /** What the field is called to a screen reader. */
  label?: string;
  /** What the mic button is called to a screen reader. */
  micLabel?: string;
  /** Drawn above the field, inside the composer's band — the first run's chips. */
  above?: ReactNode;
  /** The band itself, for a screen that keeps its thread clear of it by measuring it. */
  bandRef?: Ref<HTMLDivElement>;
  /** False on a dormant mode — there is nothing to log against. */
  canLog: boolean;
  /** What the composer invites on the current card; the default otherwise. */
  hint?: string;
  /** Raised while the composer is in use so the deck can collapse. */
  onComposing: (v: boolean) => void;
  /** The row being corrected — shown as a chip so an edit is never invisible. */
  editing?: string | null;
  onCancelEdit?: () => void;
  /**
   * What a card's Change hung on the composer: a pill above the text, and the
   * words that go before it when sent. ✕ or Escape takes it off.
   */
  context?: ComposerContext | null;
  onClearContext?: () => void;
}

const roundBtn = {
  width: 40,
  height: 40,
  borderRadius: '50%',
  background: 'none',
  border: 'none',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  cursor: 'pointer',
  flex: '0 0 auto',
  padding: 0,
};

/** Sound going in, on the mic's own button while it listens. */
function MicBars() {
  return (
    <>
      {[0, 0.15, 0.3, 0.45].map((d) => (
        <i
          key={d}
          aria-hidden="true"
          style={{
            display: 'block',
            width: 3,
            borderRadius: 2,
            background: color.white,
            animation: `wv 0.9s ease-in-out ${d}s infinite`,
          }}
        />
      ))}
    </>
  );
}

/** One line of typed text, and the padding around the stack. The composer
 *  grows to three of these and then scrolls inside itself. */
const ROW = 20;
const PAD = 10;
const MAX_ROWS = 3;

export default function InputBar({
  typed,
  focusKey = 0,
  focusOnMount = false,
  onType,
  onSend,
  onMic,
  onMedia,
  listening = false,
  waiting = false,
  label = 'What to log',
  micLabel = 'Log by voice',
  above,
  bandRef,
  canLog,
  hint,
  onComposing,
  editing = null,
  onCancelEdit,
  context = null,
  onClearContext,
}: Props) {
  const hasText = canLog && typed.trim().length > 0;

  // A textarea, not an input, so a long sentence wraps instead of scrolling
  // sideways out of view. It grows to `MAX_ROWS` and then scrolls inside
  // itself — past three rows the composer starts eating the conversation.
  const box = useRef<HTMLTextAreaElement>(null);
  useLayoutEffect(() => {
    const el = box.current;
    if (!el) return;
    // Collapse first: without it the height only ever ratchets up, because
    // scrollHeight can never report less than the element already is.
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, ROW * MAX_ROWS + PAD)}px`;
  }, [typed, canLog]);

  // Only on a change, never on mount: an autofocused composer would open the
  // keyboard over the deck every time the app starts. Compared with the last
  // value rather than skipping a first run, so a second run of the effect
  // (StrictMode, or a page closing over Home) does not grab focus.
  const lastFocus = useRef(focusKey);
  useLayoutEffect(() => {
    if (focusKey === lastFocus.current) return;
    lastFocus.current = focusKey;
    const el = box.current;
    if (!el) return;
    el.focus();
    el.setSelectionRange(el.value.length, el.value.length);
  }, [focusKey]);
  const mountFocus = useRef(focusOnMount);
  useLayoutEffect(() => {
    const el = box.current;
    if (!mountFocus.current || !el) return;
    el.focus({ preventScroll: true });
    el.setSelectionRange(el.value.length, el.value.length);
  }, []);

  // Back drops the edit, then the context, before it leaves the screen — on
  // the layer this composer is drawn in, and only while it is on top.
  useBack(Boolean((editing && onCancelEdit) || (context && onClearContext)), () => {
    if (editing && onCancelEdit) onCancelEdit();
    else onClearContext?.();
  });

  const change = (e: ChangeEvent<HTMLTextAreaElement>) => onType(e.target.value);
  const key = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      if (!waiting) onSend();
    }
    if (e.key === 'Escape') {
      // Esc first leaves edit mode, or takes the context off; a second Esc
      // leaves the composer. Each is this field's own, so the app's Escape
      // (Back) does not act on the same press.
      e.preventDefault();
      if (editing && onCancelEdit) {
        onCancelEdit();
        return;
      }
      if (context && onClearContext) {
        onClearContext();
        return;
      }
      e.currentTarget.blur();
      onComposing(false);
    }
  };

  return (
    <div
      ref={bandRef}
      style={{
        position: 'absolute',
        left: 0,
        right: 0,
        bottom: 0,
        padding: `10px ${space.gutter}px ${inset.bottom}`,
        background: `linear-gradient(transparent, ${color.paper} 30%)`,
        zIndex: 40,
      }}
    >
      {above}
      {/* A field on the page: white, a border, no lift. */}
      <div
        style={{
          background: color.white,
          border: `1px solid ${color.border}`,
          // Full at one line; a grown composer keeps the same corners.
          borderRadius: 26,
          padding: 5,
        }}
      >
        {/* The row a Change is about, as an annotation on what you type — a
            quote, not a prefill. Inside the field and lined up with the text,
            so it never sits over the thread. */}
        {context && (
          <div style={{ display: 'flex', padding: '4px 4px 2px 13px', minWidth: 0 }}>
            <span
              title={context.label}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                maxWidth: '100%',
                minWidth: 0,
                padding: '3px 6px 3px 10px',
                borderRadius: radius.pill,
                background: color.surface,
                border: `1px solid ${color.border}`,
                fontFamily: font.sans,
                fontSize: 12.5,
                lineHeight: '17px',
                color: color.muted,
                whiteSpace: 'nowrap',
              }}
            >
              <span style={{ minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis' }}>{context.label}</span>
              <button
                type="button"
                onClick={() => {
                  onClearContext?.();
                  box.current?.focus();
                }}
                aria-label={`Remove — ${context.label}`}
                style={{
                  border: 'none', background: 'none', cursor: 'pointer', padding: 2, margin: -2,
                  display: 'flex', flex: '0 0 auto',
                }}
              >
                <X size={13} color={color.muted} aria-hidden />
              </button>
            </span>
          </div>
        )}
        <div
          style={{
            display: 'flex',
            gap: 4,
            paddingLeft: 13,
            // Bottom, not centre: with two or three rows of text the buttons
            // must stay on the send line rather than float in the middle.
            alignItems: 'flex-end',
          }}
        >
          {/* The row being corrected is a selection, so it takes the brand's
              tint — amber is only ever the estimate dot. */}
          {editing && (
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 5,
                flex: '0 0 auto',
                alignSelf: 'center',
                maxWidth: '45%',
                padding: '4px 6px 4px 9px',
                borderRadius: radius.pill,
                background: color.brandTint,
                fontFamily: font.sans,
                fontSize: 12,
                lineHeight: '16px',
                color: color.ink,
                whiteSpace: 'nowrap',
                overflow: 'hidden',
              }}
              title={`Editing · ${editing}`}
            >
              <PencilSimple size={13} color={color.brand} aria-hidden style={{ flex: '0 0 auto' }} />
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{editing}</span>
              <button
                type="button"
                onClick={onCancelEdit}
                aria-label="Cancel edit"
                style={{
                  border: 'none', background: 'none', cursor: 'pointer', padding: 0,
                  display: 'flex', flex: '0 0 auto',
                }}
              >
                <X size={13} color={color.muted} aria-hidden />
              </button>
            </span>
          )}

          <textarea
            ref={box}
            rows={1}
            value={canLog ? typed : ''}
            onChange={change}
            onKeyDown={key}
            // Focus enters compose mode. Blur deliberately does NOT leave it:
            // clicking a bubble to press a button or select text blurs the input
            // natively, and the deck must not spring back for that.
            onFocus={() => onComposing(true)}
            disabled={!canLog}
            placeholder={
              editing
                ? 'Fix it and send'
                : canLog
                  ? (hint ?? 'Say what happened…')
                  : 'Nothing to log here'
            }
            aria-label={label}
            enterKeyHint="send"
            style={{
              flex: 1,
              border: 'none',
              background: 'none',
              fontSize: 15,
              fontFamily: font.sans,
              outline: 'none',
              color: color.ink,
              minWidth: 0,
              // The text has to sit on the same line as the round buttons beside
              // it, so the line box is set here rather than left to the browser.
              lineHeight: `${ROW}px`,
              padding: `${PAD / 2}px 0`,
              resize: 'none',
              overflowY: 'auto',
              maxHeight: ROW * MAX_ROWS + PAD,
            }}
          />

          {onMedia && (
            <button
              type="button"
              onClick={onMedia}
              aria-label="Log from a photo"
              disabled={!canLog}
              className="hov-tint"
              style={{ ...roundBtn, opacity: canLog ? 1 : 0.35, cursor: canLog ? 'pointer' : 'default' }}
            >
              <MediaIcon />
            </button>
          )}

          {hasText || !onMic ? (
            // With no mic, an empty field still shows where send will be.
            <button
              type="button"
              onClick={onSend}
              aria-label="Send"
              disabled={!hasText || waiting}
              className={hasText && !waiting ? 'hov-brand' : undefined}
              style={{
                ...roundBtn,
                background: hasText && !waiting ? color.brand : color.ringIdle,
                cursor: hasText && !waiting ? 'pointer' : 'default',
              }}
            >
              <SendIcon />
            </button>
          ) : (
            <button
              type="button"
              onClick={onMic}
              aria-label={listening ? 'Stop listening' : micLabel}
              aria-pressed={listening || undefined}
              disabled={!canLog || waiting}
              className={canLog && !waiting ? 'hov-brand' : undefined}
              style={{
                ...roundBtn,
                gap: 3,
                background: canLog && !waiting ? color.brand : color.ringIdle,
                cursor: canLog && !waiting ? 'pointer' : 'default',
              }}
            >
              {listening ? <MicBars /> : <MicIcon />}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
