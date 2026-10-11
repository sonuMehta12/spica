import { Fragment } from 'react';
import { Check } from '@phosphor-icons/react';
import { dueTone, projectOf, statusLabel } from '../work/tasks';
import { color, font } from '../theme';
import type { Todo } from '../types';
import MoveReminder from './MoveReminder';
import Dot from './messages/Dot';

interface Props {
  tasks: Todo[];
  onToggle: (id: string) => void;
  tabIndex: number;
}

/**
 * The Work card's right-hand column: what to do next, in order.
 *
 * This stands where Paisa and Diet put their legend, and does that job too —
 * each checkbox is drawn in its project's colour, so the row keys back to its
 * arc without a separate swatch list. Three rows is the cap — the rest lives
 * behind the card's menu rather than making this taller.
 */
export default function TaskList({ tasks, onToggle, tabIndex }: Props) {
  return (
    <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 2 }}>
      {tasks.map((task) => {
        const proj = projectOf(task.project);
        const tint = proj?.color ?? color.work;
        return (
          // The reminder sits beside the row, not in it: it holds a link, and
          // a link inside the checkbox's button would tick the task too.
          <Fragment key={task.id}>
          <button
            type="button"
            role="checkbox"
            aria-checked={task.done}
            tabIndex={tabIndex}
            onClick={() => onToggle(task.id)}
            className="hov-tint"
            style={{
              display: 'flex',
              gap: 8,
              alignItems: 'flex-start',
              width: '100%',
              background: 'none',
              border: 'none',
              borderRadius: 8,
              padding: '4px 4px',
              margin: 0,
              cursor: 'pointer',
              fontFamily: font.sans,
              textAlign: 'left',
            }}
          >
            <span
              aria-hidden="true"
              style={{
                width: 16,
                height: 16,
                borderRadius: '50%',
                border: `1.6px solid ${tint}`,
                background: task.done ? tint : 'transparent',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flex: '0 0 auto',
                marginTop: 2,
                transition: 'background 0.18s',
              }}
            >
              {task.done && <Check size={10} weight="bold" color={color.white} />}
            </span>

            <span style={{ minWidth: 0, flex: 1 }}>
              <span
                // One line, always. A title is a handle, not a description —
                // the hover title carries the rest.
                title={task.name}
                style={{
                  display: 'block',
                  fontSize: 13.5,
                  lineHeight: '18px',
                  fontWeight: 500,
                  color: task.done ? color.faint : color.ink,
                  textDecoration: task.done ? 'line-through' : 'none',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {task.name}
              </span>
              <span
                style={{
                  display: 'block',
                  fontFamily: font.sans,
                  fontSize: 11,
                  lineHeight: '14px',
                  marginTop: 1,
                  color: color.faint,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {task.projectGuessed && <Dot />}
                {proj?.name}
                {statusLabel(task) && (
                  <span style={{ color: dueTone(task) }}> · {statusLabel(task)}</span>
                )}
              </span>
            </span>
          </button>
          <MoveReminder task={task} indent={27} />
          </Fragment>
        );
      })}

    </div>
  );
}
