import { color, font, radius } from '../theme';
import MessageRow from './messages/MessageRow';
import { agentVoice } from './messages/bubble';
import type { Suggestion } from '../types';

interface Props {
  body: string;
  suggestions: (Suggestion & { tap: () => void })[];
}

/**
 * Head of the conversation: the agent's first words, and the fastest things
 * to log right now. The chips are yours — your own most repeated entries —
 * so they are white with a border, not the brand's colour.
 */
export default function Greeting({ body, suggestions }: Props) {
  // Nothing to say and nothing to offer: no row at all. An empty thread is empty.
  if (!body && suggestions.length === 0) return null;
  return (
    <MessageRow side="agent" newSpeaker first>
      {body && <div style={{ ...agentVoice, marginBottom: suggestions.length ? 12 : 0 }}>{body}</div>}
      {suggestions.length > 0 && (
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {suggestions.map((s) => (
            <button
              key={s.id}
              type="button"
              onClick={s.tap}
              className="hov-chip"
              style={{
                display: 'flex',
                gap: 6,
                alignItems: 'baseline',
                background: color.chip,
                border: `1px solid ${color.chipBorder}`,
                borderRadius: radius.pill,
                padding: '8px 14px',
                cursor: 'pointer',
                fontFamily: font.sans,
                fontSize: 13,
                fontWeight: 500,
                lineHeight: '16px',
                color: color.ink,
                transition: 'background 0.15s, border-color 0.15s',
              }}
            >
              {s.name}
              {/* A figure beside the name is data, so it is grey. */}
              {s.tag && <span style={{ fontWeight: 400, color: color.faint }}>{s.tag}</span>}
            </button>
          ))}
        </div>
      )}
    </MessageRow>
  );
}
