import type { ReactNode } from 'react';
import { ArrowCounterClockwise, Barbell, Scales } from '@phosphor-icons/react';
import { SLEEP_HOURS, TODAY_ISO } from '../../data/live';
import type { HabitLogRow } from '../../data/api';
import { addDays, weekIndex } from '../../lib/day';
import { shortDate, shortDay } from '../../lib/format';
import { color, font } from '../../theme';
import { habitGlyph, habitTone } from '../HabitIcon';
import { agentCard } from './bubble';
import { field, ledeState, ledeTitle, num, val, type ConfirmActions, type ConfirmData } from './confirmKit';
import Dot from './Dot';
import { useWeighIns } from './live';
import { Bar, Coin, Fig, Quiet, Receipt, Stacked, TextBtn, cap, dayText, metaLine } from './parts';
import type { ConfirmMsg } from '../../types';

const LETTERS = ['M', 'T', 'W', 'T', 'F', 'S', 'S'];

const same = (a: string, b: string) => a.trim().toLowerCase() === b.trim().toLowerCase();

/** A habit's count on one day, summed over its logs: a ×2 log and two ×1 logs both read 2. */
function countOn(logs: HabitLogRow[], habit: string, day: string): number {
  return logs
    .filter((l) => l.date === day && same(l.habit, habit))
    .reduce((s, l) => s + (l.amount ?? 1), 0);
}

/** The habit's own coin: its glyph and tone, from the one place the app decides them. */
function HabitCoin({ habit, gone = false }: { habit: string; gone?: boolean }) {
  const tone = habitTone(habit);
  const glyph = habitGlyph(habit);
  return (
    <Coin icon={glyph} weight="fill" tint={gone ? color.lineSoft : tone.bg} ink={gone ? color.grey : tone.ink}>
      {habit.trim().charAt(0).toUpperCase()}
    </Coin>
  );
}

/**
 * The week the card's day sits in, as seven marks with the count inside. No
 * streak, no target: a pattern across days, plainly. A day still to come is
 * drawn faint — a Thursday that has not happened is not one you skipped.
 */
function WeekMarks({ habit, day, logs }: { habit: string; day: string; logs: HabitLogRow[] }) {
  const tone = habitTone(habit);
  const monday = addDays(day, -weekIndex(day));
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 6, marginTop: 14 }}>
      {LETTERS.map((letter, i) => {
        const d = addDays(monday, i);
        const n = countOn(logs, habit, d);
        const future = d > TODAY_ISO;
        return (
          <div key={d} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
            <span
              style={{
                fontFamily: font.sans,
                fontSize: 10.5,
                lineHeight: '14px',
                fontWeight: d === day ? 500 : 400,
                color: d === day ? color.ink : color.faint,
              }}
            >
              {letter}
            </span>
            <span
              title={`${shortDate(d)}: ${n}`}
              style={{
                width: 26,
                height: 26,
                borderRadius: '50%',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                background: n ? tone.bg : color.white,
                border: `1px solid ${n ? tone.line : future ? color.lineSoft : color.line}`,
                fontFamily: font.sans,
                fontSize: 11,
                fontWeight: 500,
                color: tone.ink,
              }}
            >
              {n || ''}
            </span>
          </div>
        );
      })}
    </div>
  );
}

/** "6 h 30 m" ↔ minutes. The server writes hours this way; a target is minutes. */
function minutesOf(s: string | undefined): number | null {
  const m = s ? /(\d+)\s*h(?:\s*(\d+)\s*m)?/.exec(s) : null;
  return m ? Number(m[1]) * 60 + Number(m[2] ?? 0) : null;
}
const hm = (min: number) => {
  const h = Math.floor(min / 60);
  const m = Math.round(min % 60);
  return m ? `${h} h ${m} m` : `${h} h`;
};

function Tile({ label, figure, children }: { label: string; figure: string; children?: ReactNode }) {
  return (
    <div style={{ ...agentCard('12px 14px'), minWidth: 0, display: 'flex', flexDirection: 'column' }}>
      <span style={{ fontFamily: font.sans, fontSize: 12.5, lineHeight: '17px', color: color.faint }}>{label}</span>
      <Fig size={20}>{figure}</Fig>
      {children}
    </div>
  );
}

function SleepTile({ minutes, target }: { minutes: number; target: number | null }) {
  return (
    <Tile label="Sleep" figure={hm(minutes)}>
      {target ? (
        <>
          <div style={{ margin: '8px 0 4px' }}>
            <Bar pct={minutes / target} tone={color.diet} />
          </div>
          <span style={{ fontFamily: font.sans, fontSize: 12, lineHeight: '16px', color: color.faint }}>of {hm(target)}</span>
        </>
      ) : (
        <span style={{ fontFamily: font.sans, fontSize: 12, lineHeight: '16px', color: color.faint, marginTop: 12 }}>no target set</span>
      )}
    </Tile>
  );
}

/**
 * Weight against the weigh-in before it — or "no earlier weigh-in", never an
 * invented change. Until the weigh-ins have been read, nothing is said.
 */
function WeightTile({ kg, day }: { kg: number; day: string }) {
  const all = useWeighIns(true);
  const prev = all?.filter((w) => w.day < day).sort((a, b) => b.day.localeCompare(a.day))[0];
  const delta = prev ? Math.round((kg - prev.kg) * 10) / 10 : null;
  return (
    <Tile label="Weight" figure={`${kg} kg`}>
      {all && (
        <span
          style={{
            fontFamily: font.sans,
            fontSize: 12,
            lineHeight: '16px',
            color: prev ? color.muted : color.faint,
            marginTop: 12,
          }}
        >
          {!prev
            ? 'no earlier weigh-in'
            : delta === 0
              ? `same as ${shortDay(prev.day)}`
              : `${delta! > 0 ? '+' : '−'}${Math.abs(delta!)} kg since ${shortDay(prev.day)}`}
        </span>
      )}
    </Tile>
  );
}

/**
 * A weight — a weigh-in, on its own card, holding that row: Undo deletes the
 * reading, and a reading deleted anywhere strikes it here. A weight said as a
 * guess wears the dot until an exact reading replaces it, read off the live
 * row when the client holds it.
 *
 * Undo is offered only while the weigh-in is live in the list: a card from
 * before weights became weigh-ins holds the day's id, which the weigh-ins
 * route does not know.
 */
function WeightCard({ msg, data, a, quiet }: { msg: ConfirmMsg; data: ConfirmData; a: ConfirmActions; quiet?: ReactNode }) {
  const all = useWeighIns(true);
  const row = msg.rowId ? all?.find((w) => w.id === msg.rowId) : undefined;
  const kg = row?.kg ?? num(val(msg, 'weight_kg'));
  const day = row?.day ?? data.day ?? TODAY_ISO;
  const gone = data.live.deleted;
  const estimated = !gone && (row ? row.estimated : Boolean(field(msg, 'weight_kg')?.guessed));
  const prev = all?.filter((w) => w.day < day).sort((a, b) => b.day.localeCompare(a.day))[0];
  const delta = prev && kg != null ? Math.round((kg - prev.kg) * 10) / 10 : null;
  // Until the weigh-ins have been read, nothing is said about the one before.
  const since = !all
    ? null
    : !prev
      ? 'no earlier weigh-in'
      : delta === 0
        ? `same as ${shortDay(prev.day)}`
        : `${delta! > 0 ? '+' : '−'}${Math.abs(delta!)} kg since ${shortDay(prev.day)}`;
  return (
    <div style={agentCard('12px 14px')}>
      <Receipt
        coin={<Coin icon={Scales} tint={gone ? color.lineSoft : color.dietTint} ink={gone ? color.grey : color.dietInk} />}
        what="Weight"
        struck={gone}
        meta={gone ? 'Removed' : metaLine(cap(dayText(day)), since)}
        figure={
          kg != null ? (
            <Fig struck={gone}>
              {estimated && <Dot />}
              {kg} kg
            </Fig>
          ) : undefined
        }
      />
      {quiet !== undefined
        ? quiet != null && <Quiet>{quiet}</Quiet>
        : row && !gone && (
            <Quiet>
              <TextBtn label="Undo" icon={ArrowCounterClockwise} onClick={() => a.onDelete(msg)} />
            </Quiet>
          )}
    </div>
  );
}

/**
 * Everything `log_day`, `manage_habit` and `log_exercise` write: the day's
 * facts as tiles, a weight on its own card, a habit's count with its week, a
 * habit started or stopped, an exercise done.
 */
export function BodyCard({ msg, data, a, quiet }: { msg: ConfirmMsg; data: ConfirmData; a: ConfirmActions; quiet?: ReactNode }) {
  const day = data.day ?? TODAY_ISO;
  const logs = data.rows.habitLogs;
  const name = val(msg, 'name') ?? ledeTitle(msg.lede);

  // A habit no longer tracked — or one just started and undone: its logs
  // stay, the tracking stops.
  if ((msg.state === 'deleted' || (data.live.deleted && field(msg, 'direction'))) && field(msg, 'name')) {
    return (
      <div style={agentCard('12px 14px')}>
        <Receipt coin={<HabitCoin habit={name} gone />} what={name} struck meta="Stopped" />
      </div>
    );
  }

  // A habit started: plain words for its aim, and the week it will fill. One
  // already tracked was left as it was, and says so.
  if (field(msg, 'direction')) {
    const habit = msg.rowId ? data.rows.habits.find((h) => h.id === msg.rowId) : undefined;
    const way = habit?.direction ?? (val(msg, 'direction') === 'build' ? 'build' : 'break');
    const already = ledeState(msg.lede) === 'already tracked';
    return (
      <div style={agentCard('12px 14px')}>
        <Receipt
          coin={<HabitCoin habit={habit?.name ?? name} />}
          what={habit?.name ?? name}
          meta={already ? 'Already tracked' : metaLine('Tracking', way === 'build' ? 'to build' : 'to cut down')}
        />
        <WeekMarks habit={habit?.name ?? name} day={day} logs={logs} />
        {quiet != null && <Quiet>{quiet}</Quiet>}
      </div>
    );
  }

  // The weight alone: since it became a weigh-in, it is a card of its own.
  if (msg.fields.length === 1 && field(msg, 'weight_kg')) return <WeightCard msg={msg} data={data} a={a} quiet={quiet} />;

  // An exercise done. How many times in all is the library's live count.
  if (field(msg, 'name')?.label === 'Exercise') {
    const ex = msg.rowId ? data.rows.exercises.find((e) => e.id === msg.rowId) : undefined;
    const times = ex?.tried ?? num(/· (\d+)×$/.exec(msg.lede)?.[1]);
    return (
      <div style={agentCard('12px 14px')}>
        <Receipt
          coin={<Coin icon={Barbell} weight="fill" tint={color.dietTint} ink={color.dietInk} />}
          what={ex?.name ?? name}
          meta={day === TODAY_ISO ? 'Done today' : metaLine('Done', shortDate(day))}
          figure={times != null ? <Stacked top={<Fig>{times}×</Fig>} under="in all" /> : undefined}
        />
      </div>
    );
  }

  // The card knows the day it was said, not the day it was logged for, and
  // "kal 2 cigarettes" lands on yesterday. So a fact with nothing on the day
  // it was said, and something the day before, is read from the day before.
  const before = addDays(day, -1);
  const habitDay = (habit: string) =>
    countOn(logs, habit, day) === 0 && countOn(logs, habit, before) > 0 ? before : day;

  // The day's facts. Sleep reads the day's live row when the deck holds it.
  const sleepLive = (SLEEP_HOURS.find((s) => s.date === day) ?? SLEEP_HOURS.find((s) => s.date === before))?.hours;
  const sleep = sleepLive != null ? Math.round(sleepLive * 60) : minutesOf(val(msg, 'sleep_hours'));
  const weight = num(val(msg, 'weight_kg'));
  const habits = msg.fields.filter((f) => f.key.startsWith('habit:'));
  const tiles = [
    sleep != null && field(msg, 'sleep_hours') && <SleepTile key="s" minutes={sleep} target={data.rows.profile.sleepTargetMin} />,
    weight != null && <WeightTile key="w" kg={weight} day={day} />,
  ].filter(Boolean);

  return (
    <div style={{ display: 'grid', gap: 8 }}>
      {tiles.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: `repeat(${tiles.length}, minmax(0, 1fr))`, gap: 10 }}>{tiles}</div>
      )}
      {habits.map((f) => {
        const habit = f.label;
        const row = data.rows.habits.find((h) => same(h.name, habit));
        const on = habitDay(habit);
        return (
          <div key={f.key} style={agentCard('12px 14px')}>
            <Receipt
              coin={<HabitCoin habit={habit} />}
              what={habit}
              // What the figure counts, and on which day — the count is that
              // day's from the live log, not "Ticked".
              meta={metaLine(cap(dayText(on)), row?.unit)}
              figure={<Fig size={20}>{countOn(logs, habit, on)}</Fig>}
            />
            <WeekMarks habit={habit} day={on} logs={logs} />
          </div>
        );
      })}
    </div>
  );
}
