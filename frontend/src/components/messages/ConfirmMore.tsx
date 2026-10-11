import type { ReactNode } from 'react';
import {
  ArrowCounterClockwise,
  ArrowUpRight,
  BowlFood,
  Brain,
  Cake,
  CalendarBlank,
  CurrencyInr,
  MapPin,
  Moon,
  Ruler,
  Scales,
  SneakerMove,
  Target,
  User,
  type Icon,
} from '@phosphor-icons/react';
import { PROJECTS, TODAY_ISO } from '../../data/live';
import type { Profile } from '../../data/api';
import { diffDays } from '../../lib/day';
import { rupees, shortDate } from '../../lib/format';
import { FIELDS, ageText, optionLabel, type FieldDef } from '../../state/profileEdit';
import { color, font } from '../../theme';
import { projectOf } from '../../work/tasks';
import ProjectIcon from '../ProjectIcon';
import { agentCard } from './bubble';
import {
  field,
  initial,
  ledeState,
  ledeTitle,
  num,
  targetContext,
  val,
  type ConfirmActions,
  type ConfirmData,
} from './confirmKit';
import { Removed } from './ConfirmMoney';
import Dot from './Dot';
import { Chip, Coin, Fig, Quiet, Receipt, Section, TaskCheck, TextBtn, cap, clamp, metaLine } from './parts';
import type { ConfirmMsg } from '../../types';

const n = (count: number, one: string, many: string) => `${count} ${count === 1 ? one : many}`;

/** A due date as a chip: Today, Tomorrow, "Thu, 1 Oct" in Work's ink; late in red — red means late. */
function DueChip({ due, done }: { due: string; done: boolean }) {
  const d = diffDays(TODAY_ISO, due);
  const late = d < 0 && !done;
  const text = d === 0 ? 'Today' : d === 1 ? 'Tomorrow' : late ? `${n(-d, 'day', 'days')} late` : shortDate(due);
  const tone = done ? color.faint : late ? color.red : color.workInk;
  return (
    <Chip tone={tone} bg={done ? color.surface : late ? color.redTint : color.workTint}>
      <CalendarBlank size={12} color={tone} aria-hidden />
      {text}
    </Chip>
  );
}

/** The small line under a task's title that says what happened to it — Removed, Already on your list. */
function TaskMeta({ children }: { children: string }) {
  return (
    <div style={{ fontFamily: font.sans, fontSize: 12.5, lineHeight: '17px', color: color.faint, marginTop: 2 }}>{children}</div>
  );
}

/**
 * A task, any state: the task itself, not a form about it. Its checkbox is
 * live — a tap ticks the task wherever it is shown. A tracker's task ticked
 * here but not moved there gets its own line and the way to do it.
 *
 * A task just added can be undone, which removes it; the card then stays as
 * the task, struck. One the agent found already on the list says so and
 * offers no Undo — undoing it would delete the task that was there before.
 */
export function TaskCard({ msg, data, a, quiet }: { msg: ConfirmMsg; data: ConfirmData; a: ConfirmActions; quiet?: ReactNode }) {
  const task = msg.rowId ? data.todos.find((t) => t.id === msg.rowId) : undefined;
  const state = ledeState(msg.lede);
  const title = task?.name ?? ledeTitle(msg.lede);
  const removed = data.live.deleted;
  const done = task ? task.done : state === 'done';
  const archived = !task && state === 'archived';
  const already = state === 'already on the list';
  const project = task ? projectOf(task.project) : PROJECTS.find((p) => p.name === val(msg, 'project'));
  const projectName = project?.name ?? val(msg, 'project');
  const guessed = task ? Boolean(task.projectGuessed) : Boolean(field(msg, 'project')?.guessed);
  const due = task?.due ?? val(msg, 'due');
  const priority = task?.priority ?? num(val(msg, 'priority'));
  const struck = done || archived || removed;

  const moveIn = val(msg, 'move_in');
  const showMove = !removed && Boolean(moveIn) && (!task || Boolean(task.awaitingMove));
  const ref = moveIn ? /move (\S+) forward/.exec(moveIn)?.[1] : undefined;
  const origin = task?.origin ?? (moveIn ? /forward in (.+)$/.exec(moveIn)?.[1] : undefined) ?? 'the tracker';

  return (
    <div style={agentCard('12px 14px')}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, minWidth: 0 }}>
        <TaskCheck
          done={done && !removed}
          tint={project?.color ?? color.work}
          label={title}
          onToggle={task && !removed ? () => a.onToggleTodo(task.id) : undefined}
        />
        <div style={{ flex: 1, minWidth: 0 }}>
          <span
            style={{
              fontFamily: font.sans,
              fontSize: 15,
              lineHeight: '20px',
              fontWeight: 500,
              color: struck ? color.faint : color.ink,
              textDecoration: struck ? 'line-through' : undefined,
              ...clamp(2),
            }}
          >
            {title}
          </span>
          {removed ? (
            <TaskMeta>Removed</TaskMeta>
          ) : (
            <>
              {already && <TaskMeta>Already on your list</TaskMeta>}
              {(due || projectName || (priority != null && priority <= 2) || archived) && (
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 6 }}>
                  {due && <DueChip due={due} done={done} />}
                  {projectName && (
                    <Chip>
                      {guessed && <Dot />}
                      {projectName}
                    </Chip>
                  )}
                  {priority != null && priority <= 2 && !done && <Chip>P{priority}</Chip>}
                  {archived && <Chip>Archived</Chip>}
                </div>
              )}
            </>
          )}
        </div>
      </div>
      {/* Only a task the client holds: once it is gone there is nothing left to undo. */}
      {quiet !== undefined
        ? quiet != null && <Quiet>{quiet}</Quiet>
        : state === 'added' && task && !removed && (
            <Quiet>
              <TextBtn label="Undo" icon={ArrowCounterClockwise} onClick={() => a.onDelete(msg)} />
            </Quiet>
          )}
      {showMove && (
        <Section>
          <span style={{ flex: 1, minWidth: 0, fontFamily: font.sans, fontSize: 13, lineHeight: '18px', color: color.muted, ...clamp(2) }}>
            <span style={{ color: color.faint }}>{origin}</span>
            {ref ? ` · ${ref}` : ''} · {task?.stage ?? 'not moved yet'}
          </span>
          {task?.link && (
            <a
              href={task.link}
              target="_blank"
              rel="noreferrer"
              onClick={(e) => e.stopPropagation()}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 3,
                fontFamily: font.sans,
                fontSize: 13.5,
                lineHeight: '18px',
                fontWeight: 500,
                color: color.brand,
                textDecoration: 'none',
                whiteSpace: 'nowrap',
              }}
            >
              Move it
              <ArrowUpRight size={13} weight="bold" aria-hidden />
            </a>
          )}
        </Section>
      )}
    </div>
  );
}

/** A project made, changed or retired: its mark and name, and how much it holds now. */
export function ProjectCard({ msg, data }: { msg: ConfirmMsg; data: ConfirmData }) {
  const project = msg.rowId ? projectOf(msg.rowId) : undefined;
  const name = project?.name ?? val(msg, 'name') ?? ledeTitle(msg.lede);
  const mark = (
    <Coin tint={color.surface} ink={color.ink}>
      <ProjectIcon project={project ?? { name, color: msg.state === 'deleted' ? color.grey : color.work }} size={18} />
    </Coin>
  );
  if (msg.state === 'deleted') {
    return (
      <div style={agentCard('12px 14px')}>
        <Receipt coin={mark} what={name} struck meta={metaLine('Removed', val(msg, 'tasks'))} />
      </div>
    );
  }
  const count = data.todos.filter((t) => t.project === msg.rowId).length;
  const tasks = count ? n(count, 'task', 'tasks') : 'no tasks yet';
  const state = ledeState(msg.lede);
  return (
    <div style={agentCard('12px 14px')}>
      <Receipt
        coin={mark}
        what={name}
        meta={metaLine(state === 'created' ? 'New project' : state === 'archived' ? 'Archived' : 'Project', tasks)}
      />
    </div>
  );
}

/** Someone filed: an initial, the name, the relation as a chip. */
export function PersonCard({ msg, data }: { msg: ConfirmMsg; data: ConfirmData }) {
  const p = msg.rowId ? data.rows.people.find((x) => x.id === msg.rowId) : undefined;
  const name = p?.name ?? msg.lede.split(' · ')[0];
  const relation = p?.relation ?? val(msg, 'relation') ?? p?.kind ?? val(msg, 'kind');
  const note = p?.note ?? val(msg, 'note');
  return (
    <div style={agentCard('12px 14px')}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0 }}>
        <Coin tint={color.paisaTint} ink={color.paisaInk} size={40}>
          {initial(name)}
        </Coin>
        <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', alignItems: 'flex-start' }}>
          <span style={{ fontFamily: font.sans, fontSize: 15, lineHeight: '20px', fontWeight: 500, color: color.ink, ...clamp(2) }}>
            {name}
          </span>
          {relation && <Chip style={{ marginTop: 4 }}>{cap(relation)}</Chip>}
        </div>
      </div>
      {note && (
        <div style={{ fontFamily: font.sans, fontSize: 13, lineHeight: '19px', color: color.muted, marginTop: 10 }}>{note}</div>
      )}
    </div>
  );
}

/** A pin: its kind and visits, and what was spent there — counted live over the ledger. */
export function PlaceCard({ msg, data, a }: { msg: ConfirmMsg; data: ConfirmData; a: ConfirmActions }) {
  const pl = msg.rowId ? data.rows.places.find((x) => x.id === msg.rowId) : undefined;
  const name = pl?.name ?? msg.lede.split(' · ')[0];
  if (data.live.deleted) {
    return <Removed coin={<Coin icon={MapPin} tint={color.lineSoft} ink={color.grey} />} what={name} />;
  }
  const kind = pl?.kind ?? val(msg, 'kind');
  const visits = pl ? pl.payments : num(val(msg, 'payments'));
  // The live row counts in paise; the payload already printed rupees.
  const spent = pl ? Math.round(pl.spent / 100) : num(val(msg, 'spent'));
  return (
    <div style={agentCard('12px 14px')}>
      <Receipt
        coin={<Coin icon={MapPin} tint={color.paisaTint} ink={color.paisaInk} />}
        what={name}
        meta={metaLine(kind ?? 'place', visits != null && n(visits, 'visit', 'visits'))}
        figure={spent ? <Fig>{rupees(spent)}</Fig> : undefined}
      />
      {msg.rowId && (
        <Quiet>
          <TextBtn label="Undo" icon={ArrowCounterClockwise} onClick={() => a.onDelete(msg)} />
        </Quiet>
      )}
    </div>
  );
}

/**
 * A fact kept about you: always one tap from gone. Its coin is a fact about
 * the person, so it takes Diet's tint, as every profile fact does
 * (spec/done/onboarding-goals.md § 3) — the brand is an action, never data.
 */
export function MemoryCard({ msg, data, a, quiet }: { msg: ConfirmMsg; data: ConfirmData; a: ConfirmActions; quiet?: ReactNode }) {
  const fact = val(msg, 'text') ?? '';
  const kind = field(msg, 'text')?.label;
  const gone = data.live.deleted;
  return (
    <div style={agentCard('12px 14px')}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <Coin icon={Brain} tint={gone ? color.lineSoft : color.dietTint} ink={gone ? color.grey : color.dietInk} />
        <span style={{ flex: 1, fontFamily: font.sans, fontSize: 13, lineHeight: '18px', color: color.faint }}>
          {gone ? 'Forgotten' : 'I’ll remember'}
        </span>
        {kind && <Chip>{cap(kind)}</Chip>}
      </div>
      <div
        style={{
          fontFamily: font.sans,
          fontSize: 15,
          lineHeight: '22px',
          color: gone ? color.faint : color.ink,
          textDecoration: gone ? 'line-through' : undefined,
          marginTop: 10,
          overflowWrap: 'anywhere',
        }}
      >
        {fact}
      </div>
      {quiet !== undefined
        ? quiet != null && <Quiet>{quiet}</Quiet>
        : !gone && msg.rowId && (
            <Quiet>
              <TextBtn label="Forget" tone={color.red} onClick={() => a.onDelete(msg)} />
            </Quiet>
          )}
    </div>
  );
}

/** A fact's coin: money in Paisa's tint, the person's body and food in Diet's. */
const COIN: Record<string, { icon: Icon; tint: string; ink: string }> = {
  goal: { icon: CurrencyInr, tint: color.paisaTint, ink: color.paisaInk },
  kcal: { icon: BowlFood, tint: color.dietTint, ink: color.dietInk },
  protein: { icon: BowlFood, tint: color.dietTint, ink: color.dietInk },
  carbs: { icon: BowlFood, tint: color.dietTint, ink: color.dietInk },
  fat: { icon: BowlFood, tint: color.dietTint, ink: color.dietInk },
  fibre: { icon: BowlFood, tint: color.dietTint, ink: color.dietInk },
  sleep: { icon: Moon, tint: color.dietTint, ink: color.dietInk },
  steps: { icon: SneakerMove, tint: color.dietTint, ink: color.dietInk },
  weight: { icon: Scales, tint: color.dietTint, ink: color.dietInk },
  name: { icon: User, tint: color.dietTint, ink: color.dietInk },
  gender: { icon: User, tint: color.dietTint, ink: color.dietInk },
  dob: { icon: Cake, tint: color.dietTint, ink: color.dietInk },
  height: { icon: Ruler, tint: color.dietTint, ink: color.dietInk },
  city: { icon: MapPin, tint: color.dietTint, ink: color.dietInk },
  diet: { icon: BowlFood, tint: color.dietTint, ink: color.dietInk },
};

const PER: Record<string, string> = {
  goal: 'each month',
  kcal: 'each day',
  protein: 'each day',
  carbs: 'each day',
  fat: 'each day',
  fibre: 'each day',
  steps: 'each day',
  sleep: 'each night',
  weight: 'to reach',
};

const hm = (min: number) => {
  const h = Math.floor(min / 60);
  const m = Math.round(min % 60);
  return m ? `${h} h ${m} m` : `${h} h`;
};

/** The profile's value now, in the card's words. Null when it is unset. */
function shown(def: FieldDef, p: Profile): string | null {
  const v = p[def.key];
  if (v == null || v === '') return null;
  const x = Number(v);
  switch (def.kind) {
    case 'rupees':
      return rupees(x);
    case 'grams':
      return `${x} g`;
    case 'int':
      return def.id === 'steps' ? `${x.toLocaleString('en-IN')} steps` : `${x.toLocaleString('en-IN')} kcal`;
    case 'sleep':
      return hm(x);
    case 'kg':
      return `${x} kg`;
    case 'cm':
      // Stored at the column's precision (175.3), shown whole.
      return `${Math.round(x)} cm`;
    case 'date':
      return ageText(String(v));
    case 'choice':
      return optionLabel(def.options ?? [], String(v));
    default:
      return String(v);
  }
}

/**
 * A target changed: the target and its value now. Change hangs it on the
 * composer — the new value is a sentence, the same way it was set.
 */
export function ProfileCard({ msg, data, a, quiet }: { msg: ConfirmMsg; data: ConfirmData; a: ConfirmActions; quiet?: ReactNode }) {
  const f = msg.fields[0];
  if (!f) return null;
  // An age arrives keyed `age`, never `dob`: it is the date of birth, shown
  // as the age it was said as, never as the 1 January it was stored as.
  const def = FIELDS.find((x) => x.wire === (f.key === 'age' ? 'dob' : f.key));
  const coin = (def && COIN[def.id]) ?? { icon: Target, tint: color.brandTint, ink: color.brand };
  // Taken back (the first run's Undo): the write it was, struck — it is not
  // the value now.
  if (data.live.deleted) {
    return (
      <div style={agentCard('12px 14px')}>
        <Receipt
          coin={<Coin icon={coin.icon} tint={color.lineSoft} ink={color.grey} />}
          what={f.label}
          struck
          meta="Removed"
          figure={<Fig struck>{val(msg, f.key) ?? '—'}</Fig>}
        />
      </div>
    );
  }
  // The live profile wins: a target changed since reads as it is now.
  const now = (def && shown(def, data.rows.profile)) ?? val(msg, f.key) ?? null;
  return (
    <div style={agentCard('12px 14px')}>
      <Receipt
        coin={<Coin icon={coin.icon} tint={coin.tint} ink={coin.ink} />}
        what={f.label}
        meta={def ? PER[def.id] : undefined}
        figure={<Fig>{now ?? '—'}</Fig>}
      />
      {quiet !== undefined
        ? quiet != null && <Quiet>{quiet}</Quiet>
        : def && (
            <Quiet>
              <TextBtn label="Change" onClick={() => a.onContext(targetContext(f.label, now))} />
            </Quiet>
          )}
    </div>
  );
}
