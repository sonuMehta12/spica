import { Fragment } from 'react';
import { TODAY_ISO } from '../../data/live';
import { addDays, diffDays, weekIndex } from '../../lib/day';
import { shortDate } from '../../lib/format';
import { color, font } from '../../theme';
import MoveReminder from '../MoveReminder';
import Dot from './Dot';
import { agentCard } from './bubble';
import { AgentLine, Chip, Fig, GroupLabel, Lead, LeadWord, TaskCheck, clamp } from './parts';
import { todoNote } from '../../agent/notes';
import { projectOf, sortTasks } from '../../work/tasks';
import type { Todo, TodoMsg } from '../../types';

interface Props {
  todos: Todo[];
  scope: TodoMsg['scope'];
  /** A project's name, from the agent: only its tasks. Matched by name, any case. */
  project?: string | null;
  /** The agent answered with this card: its reply is the line, so none is drawn here. */
  agent?: boolean;
  onToggle: (id: string) => void;
}

type When = 'late' | 'today' | 'week' | 'later';

const GROUPS: { key: When; label: string; tone: string }[] = [
  { key: 'late', label: 'Late', tone: color.red },
  { key: 'today', label: 'Today', tone: color.ink },
  { key: 'week', label: 'This week', tone: color.muted },
  { key: 'later', label: 'Later', tone: color.faint },
];

/** Which block a task sits in. Undated is later, not never — it is still on the plate. */
function whenOf(t: Todo, sunday: string): When {
  if (t.due == null) return 'later';
  if (t.due < TODAY_ISO) return 'late';
  if (t.due === TODAY_ISO) return 'today';
  return t.due <= sunday ? 'week' : 'later';
}

/** The small print beside a task's project: how late, which day, P1, where it came from. */
function detail(t: Todo, when: When): string {
  const due =
    t.due == null || when === 'today'
      ? null
      : when === 'late'
        ? `${diffDays(t.due, TODAY_ISO)} ${diffDays(t.due, TODAY_ISO) === 1 ? 'day' : 'days'} late`
        : shortDate(t.due);
  return [due, t.priority != null && t.priority <= 2 && !t.done ? `P${t.priority}` : null, t.src]
    .filter(Boolean)
    .join(' · ');
}

/**
 * The task list, grouped by when it is due — what you are behind on first.
 * From the + menu it is built on the phone, so the agent's line about it is
 * drawn above the card, worked out from the live tasks each time. When the
 * agent answers a task question with it, its own sentence is that line, and
 * the card draws none — two sentences would say the same thing.
 *
 * A task ticked today stays where it was, struck, so a tick never makes the
 * list jump out from under your finger; one finished on an earlier day is
 * done and gone.
 */
export default function TodoCard({ todos, scope, project, agent = false, onToggle }: Props) {
  const inScope = scope === 'work' ? todos.filter((t) => t.kind === 'work') : todos;
  const want = project?.trim().toLowerCase();
  const pool = want ? inScope.filter((t) => projectOf(t.project)?.name.trim().toLowerCase() === want) : inScope;
  const shown = pool.filter((t) => !t.done || t.doneOn === TODAY_ISO);
  const open = pool.filter((t) => !t.done);
  const late = open.filter((t) => t.due != null && t.due < TODAY_ISO).length;
  const sunday = addDays(TODAY_ISO, 6 - weekIndex(TODAY_ISO));
  const groups = GROUPS.map((g) => ({ ...g, tasks: sortTasks(shown.filter((t) => whenOf(t, sunday) === g.key)) })).filter(
    (g) => g.tasks.length,
  );

  const note = agent ? null : <AgentLine>{todoNote(pool)}</AgentLine>;
  // Nothing to list: the line alone, never an empty box under a sentence.
  if (!groups.length) return note;

  return (
    <div>
      {note}
      <div style={agentCard('12px 14px 6px')}>
        <Lead>
          <Fig size={22}>{open.length}</Fig>
          <LeadWord>open</LeadWord>
          {late > 0 && (
            <>
              <LeadWord>·</LeadWord>
              <Fig size={22} tone={color.red}>{late}</Fig>
              <LeadWord>late</LeadWord>
            </>
          )}
        </Lead>
        {groups.map((g) => (
          <div key={g.key}>
            <GroupLabel tone={g.tone}>{g.label}</GroupLabel>
            {g.tasks.map((t, i) => {
              const project = projectOf(t.project);
              const more = detail(t, g.key);
              return (
                <Fragment key={t.id}>
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: 10,
                      padding: '8px 0',
                      borderTop: i === 0 ? undefined : `1px solid ${color.lineSoft}`,
                      minWidth: 0,
                    }}
                  >
                    <TaskCheck done={t.done} tint={project?.color ?? color.work} size={18} label={t.name} onToggle={() => onToggle(t.id)} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <span
                        style={{
                          fontFamily: font.sans,
                          fontSize: 14.5,
                          lineHeight: '20px',
                          color: t.done ? color.faint : color.ink,
                          textDecoration: t.done ? 'line-through' : undefined,
                          ...clamp(2),
                        }}
                      >
                        {t.name}
                      </span>
                      {(project || more) && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 4, minWidth: 0 }}>
                          {project && (
                            <Chip style={{ flex: '0 1 auto' }}>
                              {t.projectGuessed && <Dot />}
                              {project.name}
                            </Chip>
                          )}
                          {more && (
                            <span
                              style={{
                                fontFamily: font.sans,
                                fontSize: 12,
                                lineHeight: '16px',
                                color: color.faint,
                                minWidth: 0,
                                whiteSpace: 'nowrap',
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                              }}
                            >
                              {more}
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                  <MoveReminder task={t} indent={28} />
                </Fragment>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}
