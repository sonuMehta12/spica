import { agentVoice } from './bubble';
import MarkdownBody from './MarkdownBody';
import type { AgentMsg } from '../../types';

/**
 * The agent's reply: its words, in the serif, across the thread's full width —
 * no bubble and no face. Prose renders as markdown — the model already writes
 * `**bold**`, and literal asterisks on screen were the ugliest thing in the
 * app. The headline row is only drawn when there is one: `/chat` replies have
 * none, and an empty bold line above every answer was a blank hat.
 *
 * A send that failed is not the agent's to report: your own message carries
 * "Not sent · Retry" (UserBubble). Failure is not a mood — the mascot has no
 * state for it.
 */
export default function AgentCard({ msg }: { msg: AgentMsg }) {
  return (
    <div style={{ animation: 'fadeup 0.35s' }}>
      {msg.title && (
        <div style={{ ...agentVoice, fontWeight: 500, marginBottom: 2 }}>
          {msg.title} {msg.hl && <span style={{ color: msg.hlColor }}>{msg.hl}</span>}
        </div>
      )}
      <MarkdownBody text={msg.body} />
    </div>
  );
}
