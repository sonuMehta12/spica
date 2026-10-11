import { SALARY, TODAY_ISO } from '../../data/live';
import type { LimitInfo, PendingItem } from '../../data/api';
import { diffDays } from '../../lib/day';
import { rupees } from '../../lib/format';
import { color, font } from '../../theme';
import { agentCard } from './bubble';
import { flowNote } from '../../agent/notes';
import { AgentLine, Fig, ListRow } from './parts';

function Line({ first, name, when, figure, tone }: { first: boolean; name: string; when: string; figure: string; tone: string }) {
  return (
    <ListRow first={first} pad="8px 0">
      <span style={{ fontFamily: font.sans, fontSize: 14.5, lineHeight: '20px', color: color.ink, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {name}
      </span>
      <span style={{ fontFamily: font.sans, fontSize: 12, lineHeight: '16px', color: color.faint, flex: 1, whiteSpace: 'nowrap' }}>{when}</span>
      <Fig size={14.5} tone={tone}>{figure}</Fig>
    </ListRow>
  );
}

/**
 * The month from the + menu: what is left at month end leads, one bar shows
 * how much of what came in is going out, then the lines it is made of.
 *
 * The figures are the server's — `pool` and `locked` from `GET /paisa/summary`,
 * the same function the Paisa card and the agent read — so this card cannot
 * disagree with either. What is lent out is listed but never counted: a
 * friend's promise is not money in hand. The agent's line is worked out from
 * the same rows each time the card is drawn.
 */
export default function FlowCard({ limit, pending }: { limit: LimitInfo | null; pending: PendingItem[] }) {
  const cameIn = SALARY;
  const left = limit ? limit.pool - limit.locked : null;
  const note = <AgentLine>{flowNote({ cameIn, left, locked: limit?.locked ?? null, pending })}</AgentLine>;
  // Not loaded yet, or a month with nothing in it: the line says so, and no
  // empty box of ₹0s sits under it.
  if (!limit || left == null) return note;
  const gone = cameIn - limit.pool;
  if (cameIn === 0 && gone === 0 && limit.locked === 0 && !pending.length) return note;

  const goingOut = gone + limit.locked;
  const share = cameIn > 0 ? Math.min(1, Math.max(0, goingOut / cameIn)) : 1;
  const over = goingOut > cameIn;

  return (
    <div>
      {note}
      <div style={agentCard('12px 14px 6px')}>
        <span style={{ fontFamily: font.sans, fontSize: 12.5, lineHeight: '17px', color: color.faint }}>Left at month end</span>
        <div>
          <Fig size={28} tone={left < 0 ? color.red : color.ink}>{rupees(left)}</Fig>
        </div>
        {cameIn > 0 && (
          <>
            <div style={{ display: 'flex', height: 8, borderRadius: 4, overflow: 'hidden', margin: '12px 0 6px', background: color.ringIdle }}>
              {/* Going out fills; what stays is the track. Red only when going out is more than came in. */}
              <div style={{ width: `${Math.round(share * 100)}%`, background: over ? color.red : color.paisa }} />
            </div>
            <div style={{ display: 'flex', gap: 8, fontFamily: font.sans, fontSize: 12, lineHeight: '16px', color: color.faint }}>
              <span style={{ flex: 1 }}>{rupees(goingOut)} going out</span>
              <span>{left >= 0 ? `${rupees(left)} stays` : `${rupees(-left)} short`}</span>
            </div>
          </>
        )}
        <div style={{ height: 1, background: color.line, margin: '12px 0 2px' }} />
        <Line first name="Came in" when="this month" figure={`+${rupees(cameIn)}`} tone={color.paisaInk} />
        <Line first={false} name="Gone out" when="so far" figure={rupees(gone)} tone={color.ink} />
        {limit.locked > 0 && <Line first={false} name="Still to go" when="committed" figure={rupees(limit.locked)} tone={color.ink} />}
        {pending.map((p) => {
          const age = diffDays(p.date, TODAY_ISO);
          return (
            <Line
              key={p.id}
              first={false}
              name={p.label}
              when={age > 0 ? `owes you · ${age} ${age === 1 ? 'day' : 'days'}` : 'owes you'}
              figure={rupees(p.remaining)}
              tone={color.muted}
            />
          );
        })}
      </div>
    </div>
  );
}
