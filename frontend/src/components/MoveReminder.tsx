import { ArrowUpRight } from '@phosphor-icons/react';
import { color, font } from '../theme';
import type { Todo } from '../types';

interface Props {
  task: Todo;
  /** Indent to sit under the title, past the checkbox. */
  indent: number;
}

/**
 * The one thing Spica asks after a tracker's task is ticked: move it there.
 *
 * Spica never moves an issue itself — a team's workflow is shared, and one
 * wrong move tells teammates something false (spec/work-sync.md § Linear —
 * read, then remind). So the tick here is a reminder, shown until the next run
 * sees the stage change. The stage is data, in grey; the ask is the
 * agent's, in ink, and a link in the brand. It names the stage the issue is in, never the one after:
 * Spica does not know a team's order, and would guess wrong for someone.
 */
export default function MoveReminder({ task, indent }: Props) {
  if (!task.done || !task.awaitingMove) return null;
  const where = task.origin ?? 'the tracker';
  const ask = `move it forward in ${where}`;

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'baseline',
        gap: 5,
        padding: `0 4px 5px ${indent}px`,
        minWidth: 0,
      }}
    >
      {task.stage && (
        <span
          style={{
            fontFamily: font.sans,
            fontSize: 11,
            color: color.faint,
            whiteSpace: 'nowrap',
            flex: '0 0 auto',
          }}
        >
          {task.stage} ·
        </span>
      )}
      {task.link ? (
        <a
          href={task.link}
          target="_blank"
          rel="noreferrer"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 2,
            fontFamily: font.sans,
            fontSize: 12,
            color: color.brand,
            textDecoration: 'none',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {ask}
          <ArrowUpRight size={12} aria-hidden style={{ flex: '0 0 auto' }} />
        </a>
      ) : (
        <span style={{ fontFamily: font.sans, fontSize: 12, color: color.ink }}>{ask}</span>
      )}
    </div>
  );
}
