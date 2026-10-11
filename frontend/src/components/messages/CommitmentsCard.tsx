import { color, font } from '../../theme';
import type { CommitmentsPage } from '../../data/api';
import CommitmentLines, { type LineHandlers } from '../commitments/CommitmentLines';
import { inr } from '../commitments/kit';
import { agentCard } from './bubble';
import { Fig, Lead, LeadWord } from './parts';

/**
 * What is owed this month, as the agent answered with it. It holds no rows:
 * the lines are the current month's commitments from live state, so an edit,
 * a skip or a delete anywhere shows here too — and the lead is worked out
 * from them each time the card is drawn, never stored.
 */
export default function CommitmentsCard({
  page,
  handlers,
}: {
  page: CommitmentsPage | null;
  handlers: LineHandlers;
}) {
  if (!page) {
    return (
      <div style={agentCard('12px 14px')}>
        <span style={{ fontFamily: font.sans, fontSize: 12.5, color: color.faint }}>Loading…</span>
      </div>
    );
  }
  const own = page.items.filter((c) => c.source === 'commitment');
  const skipped = own.filter((c) => c.skipped).length;
  const lines = page.items.filter((c) => !c.skipped).length;
  const n = (c: number, one: string, many: string) => `${c} ${c === 1 ? one : many}`;

  return (
    <div style={agentCard('12px 14px 6px')}>
      {own.length === 0 && page.items.length === 0 ? (
        <LeadWord>No commitments yet</LeadWord>
      ) : (
        <>
          <Lead>
            <Fig size={26}>{inr(page.owedPaise)}</Fig>
            <LeadWord>
              owed · {n(lines, 'line', 'lines')}
              {skipped ? ` · ${skipped} skipped` : ''}
            </LeadWord>
          </Lead>
          <div style={{ height: 1, background: color.line, marginTop: 12 }} />
          <CommitmentLines items={page.items} editable={page.editable} handlers={handlers} compact />
        </>
      )}
    </div>
  );
}
