import { CaretRight } from '@phosphor-icons/react';
import { color, font } from '../../theme';
import { agentCard } from './bubble';
import { AgentLine } from './parts';
import type { AskMsg } from '../../types';

/**
 * One question, and only when the answer changes a number.
 *
 * The question is the agent speaking, so it stands above the card in the
 * serif; the card holds only the answers, each a full-width row that is easy
 * to hit. Tapping one sends it as the next thing said, so the answer stays a
 * sentence. When the question is holding up a write, the row it is about sits
 * over the answers, struck, so the question is visibly about *that*.
 */
export default function AskCard({
  msg,
  pending,
  onAnswer,
}: {
  msg: AskMsg;
  /** The lede of the row this question blocks, if the client can name it. */
  pending?: string | null;
  onAnswer: (text: string) => void;
}) {
  return (
    <div>
      <AgentLine>{msg.question}</AgentLine>
      {(msg.options.length > 0 || pending) && (
        <div style={agentCard('2px 14px')}>
          {pending && (
            <div
              style={{
                fontFamily: font.sans,
                fontSize: 13.5,
                lineHeight: '18px',
                fontWeight: 500,
                color: color.faint,
                textDecoration: 'line-through',
                padding: '12px 0',
              }}
            >
              {pending}
            </div>
          )}
          {msg.options.map((o, i) => (
            <button
              key={o}
              type="button"
              className="hov-tint"
              onClick={() => onAnswer(o)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                width: '100%',
                padding: '12px 0',
                background: 'none',
                border: 'none',
                borderTop: i === 0 && !pending ? 'none' : `1px solid ${color.line}`,
                cursor: 'pointer',
                textAlign: 'left',
                fontFamily: font.sans,
                fontSize: 15,
                lineHeight: '20px',
                fontWeight: 500,
                color: color.ink,
              }}
            >
              <span style={{ flex: 1, minWidth: 0 }}>{o}</span>
              <CaretRight size={14} weight="bold" color={color.faint} aria-hidden />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
