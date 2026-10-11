import { useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from 'react';
import {
  Alarm,
  ArrowDown,
  ArrowUp,
  Brain,
  CaretRight,
  Heartbeat,
  IdentificationCard,
  Kanban,
  Plus,
  Scales,
  Wallet,
  X,
  type Icon,
} from '@phosphor-icons/react';
import { color, font, inset, radius, space } from '../theme';
import type { HabitRow, MemoryRow, Profile, ProjectRow, ScheduleRow, WeighInRow } from '../data/api';
import { createProject, deleteProject, fetchProjects, patchProject } from '../data/api';
import { shortDate } from '../lib/format';
import Dot from './messages/Dot';
import { cardHeading, filterPill } from './messages/bubble';
import PageHeader, { BackButton } from './PageHeader';
import ProjectIcon, { ICON_NAMES } from './ProjectIcon';
import Switch from './Switch';
import UserAvatar from './UserAvatar';
import {
  ABOUT_FIELDS,
  FINANCE_FIELDS,
  GROUP_TITLES,
  HEALTH_FIELDS,
  MEMORY_KINDS,
  WEIGHT_FIELDS,
  clearable,
  draftValue,
  formatValue,
  inputFor,
  type FieldDef,
  type FieldId,
  type GroupKey,
} from '../state/profileEdit';
import { useBack } from '../state/nav';

/**
 * Drawer → Profile. spec/done/users-profile.md § The settings surface.
 *
 * Two levels, each its own screen on the stack. The page opens as a grid of
 * tiles, one per group — an icon and the name, nothing else; what a group
 * holds is one tap away. Tap a tile and
 * the group opens as its own page over the grid, with its rows in one card;
 * ← (or Back) returns to the grid as it was. Edit goal opens the group alone,
 * so its ← returns Home.
 *
 * Quick edit inside a group, the way a settings app does it: tap a row and it
 * opens into a small editor right there — the current value, the unit, Save.
 * Enter saves, Esc closes, and Back closes an open row before it leaves the
 * page. No trip through the composer; that floats here too, but for asking
 * the agent.
 *
 * Unset values show as a dash, never an invented default.
 */
interface Props {
  profile: Profile;
  memories: MemoryRow[];
  habits: HabitRow[];
  weighIns: WeighInRow[];
  /** The group this page is; null is the grid. */
  group: GroupKey | null;
  /** A row to open in edit mode on arrival — ⋮ → Edit goal lands on `goal`. */
  focus: FieldId | null;
  /** On top of the stack: the grid reads its project tags again when a group comes off it. */
  top: boolean;
  onSaveField: (id: FieldId, raw: string) => Promise<boolean>;
  onSaveWeighIn: (raw: string) => Promise<boolean>;
  /** A reading deleted through its route; the one before it becomes the latest. */
  onDeleteWeighIn: (id: string) => void;
  onSaveMemory: (id: string, text: string) => Promise<boolean>;
  onAddMemory: (input: { slug: string; kind: string; text: string }) => Promise<boolean>;
  onDeleteMemory: (id: string) => void;
  onAddHabit: (row: { name: string; direction: 'build' | 'break'; unit: string | null }) => Promise<boolean>;
  onEditHabit: (id: string, patch: { name?: string; unit?: string | null }) => Promise<boolean>;
  onFlipHabit: (id: string, direction: 'build' | 'break') => Promise<boolean>;
  /** What Spica does on its own, and when. */
  schedules: ScheduleRow[];
  onEditSchedule: (id: string, patch: { at?: string; enabled?: boolean }) => Promise<boolean>;
  onDeleteHabit: (id: string) => void;
  /** A project was made, changed or removed — the deck's Work card follows. */
  onProjectsChanged?: () => void;
  /** A tile: its group, pushed over the grid. */
  onGroup: (g: GroupKey) => void;
  /** What ← returns to: the menu, the grid, or Home from Edit goal. */
  backTo: string;
  onBack: () => void;
  /** The same composer as the home screen, floating over this page while it is on top. */
  composer: ReactNode;
}

const rowStyle = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  gap: 10,
  width: '100%',
  background: 'none',
  border: 'none',
  padding: '12px 14px',
  cursor: 'pointer',
  fontFamily: font.sans,
  fontSize: 14,
  lineHeight: '18px',
  color: color.ink,
  textAlign: 'left' as const,
};

const inputStyle = {
  fontFamily: font.sans,
  fontSize: 14,
  color: color.ink,
  background: color.white,
  border: `1px solid ${color.border}`,
  borderRadius: 10,
  padding: '7px 10px',
  outline: 'none',
  minWidth: 0,
};

const saveBtn = {
  fontFamily: font.sans,
  fontSize: 13,
  fontWeight: 500,
  color: color.white,
  background: color.brand,
  border: 'none',
  borderRadius: 999,
  padding: '7px 14px',
  cursor: 'pointer',
};

const cancelBtn = {
  fontFamily: font.sans,
  fontSize: 13,
  color: color.muted,
  background: 'none',
  border: 'none',
  padding: '7px 6px',
  cursor: 'pointer',
};

/** A row that adds something — "Track a habit", "Add memory". Brand text: an action, not data. */
const addRow = { ...rowStyle, color: color.brand, fontWeight: 500, justifyContent: 'flex-start', gap: 6 };

/** A row's small second line: the interface face, grey. */
const subLine = { fontFamily: font.sans, fontSize: 12, lineHeight: '16px', color: color.faint };

/** One row's container: the hairline above, and the editor beneath when open. */
function Cell({ id, children }: { id: string; children: ReactNode }) {
  return (
    <div id={`pf-${id}`} className="profile-cell" style={{ borderTop: `1px solid ${color.line}` }}>
      {children}
    </div>
  );
}

function Chevron({ open }: { open: boolean }) {
  return (
    <CaretRight
      size={15}
      color={color.grey}
      aria-hidden
      style={{ transform: open ? 'rotate(90deg)' : 'none', transition: 'transform 0.15s', flex: '0 0 auto' }}
    />
  );
}

function RowButton({
  label,
  value,
  sub,
  estimated = false,
  open,
  onClick,
}: {
  label: string;
  value: string | null;
  sub?: string;
  /** The value was given as a guess: the amber dot before it. */
  estimated?: boolean;
  open: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className="hov-tint"
      style={rowStyle}
      onClick={onClick}
      aria-expanded={open}
    >
      <span>{label}</span>
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
        <span style={{ fontFamily: font.sans, fontSize: 13.5, color: value == null ? color.faint : color.muted }}>
          {estimated && value != null && <Dot />}
          {value ?? '—'}
          {sub && <span style={{ color: color.faint }}> {sub}</span>}
        </span>
        <Chevron open={open} />
      </span>
    </button>
  );
}

/**
 * The editor that opens under a row. Owns its draft; asks the parent to save
 * and closes on success. On refusal it stays open and says so — a value that
 * did not land must never look like it did.
 */
function Editor({
  initial,
  type = 'text',
  inputMode = 'text',
  prefix,
  suffix,
  hint,
  multiline = false,
  onSave,
  onClose,
}: {
  initial: string;
  type?: 'text' | 'date';
  inputMode?: 'decimal' | 'numeric' | 'text';
  prefix?: string;
  suffix?: string;
  hint?: string;
  multiline?: boolean;
  onSave: (raw: string) => Promise<boolean>;
  onClose: () => void;
}) {
  const [draft, setDraft] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const ref = useRef<HTMLInputElement | HTMLTextAreaElement>(null);

  useEffect(() => {
    ref.current?.focus();
    ref.current?.select();
  }, []);

  const save = async () => {
    if (busy) return;
    setBusy(true);
    const ok = await onSave(draft);
    setBusy(false);
    if (ok) onClose();
    else setFailed(true);
  };
  const keys = (e: KeyboardEvent) => {
    if (e.key === 'Enter' && !(multiline && e.shiftKey)) {
      e.preventDefault();
      void save();
    } else if (e.key === 'Escape') {
      e.preventDefault();
      onClose();
    }
  };

  return (
    <div style={{ padding: '2px 14px 12px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        {prefix && <span style={{ fontFamily: font.sans, fontSize: 14, color: color.muted }}>{prefix}</span>}
        {multiline ? (
          <textarea
            ref={ref as React.RefObject<HTMLTextAreaElement>}
            value={draft}
            rows={3}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={keys}
            style={{ ...inputStyle, flex: 1, fontFamily: font.sans, resize: 'vertical' }}
          />
        ) : (
          <input
            ref={ref as React.RefObject<HTMLInputElement>}
            type={type}
            inputMode={inputMode}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={keys}
            style={{ ...inputStyle, flex: type === 'date' ? 1 : suffix || prefix ? '0 1 120px' : 1 }}
          />
        )}
        {suffix && <span style={{ fontFamily: font.sans, fontSize: 14, color: color.muted }}>{suffix}</span>}
        <span style={{ flex: 1 }} />
        <button type="button" style={cancelBtn} onClick={onClose}>
          Cancel
        </button>
        <button type="button" className="hov-brand" style={{ ...saveBtn, opacity: busy ? 0.6 : 1 }} onClick={() => void save()} disabled={busy}>
          {busy ? 'Saving…' : 'Save'}
        </button>
      </div>
      <div style={{ fontFamily: font.sans, fontSize: 12, marginTop: 6, color: failed ? color.red : color.faint }}>
        {failed ? 'Not saved — check the value, or the server refused.' : hint}
      </div>
    </div>
  );
}

/**
 * The editor for a field that is one of a few values — gender, diet. A tap on
 * a value saves it; Clear empties the field. Like `Editor`, it stays open and
 * says so when the server refuses. The phone's ChoiceEditor, pill for pill.
 */
function ChoiceEditor({
  options,
  current,
  onSave,
  onClose,
}: {
  options: readonly (readonly [string, string])[];
  /** The value set now; null when the field is empty. */
  current: string | null;
  onSave: (raw: string) => Promise<boolean>;
  onClose: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  // The cursor goes to the value set now, or the first one: the editor is
  // reachable from the keyboard the moment it opens, as a field's is.
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    box.current?.querySelector<HTMLButtonElement>('[aria-pressed="true"], button')?.focus();
  }, []);

  const save = async (value: string) => {
    if (busy) return;
    setBusy(true);
    const ok = await onSave(value);
    setBusy(false);
    if (ok) onClose();
    else setFailed(true);
  };

  return (
    <div style={{ padding: '2px 14px 12px' }}>
      <div ref={box} style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        {options.map(([value, words]) => (
          <button
            key={value}
            type="button"
            aria-pressed={value === current}
            disabled={busy}
            onClick={() => {
              if (value !== current) void save(value);
            }}
            style={filterPill(value === current)}
          >
            {words}
          </button>
        ))}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 12 }}>
        <span style={{ flex: 1, fontFamily: font.sans, fontSize: 12, color: color.red }}>
          {failed ? 'Not saved — the server refused.' : ''}
        </span>
        {current != null && (
          <button type="button" style={cancelBtn} onClick={() => void save('')} disabled={busy}>
            Clear
          </button>
        )}
        <button type="button" style={cancelBtn} onClick={onClose}>
          Cancel
        </button>
      </div>
    </div>
  );
}

/** The groups in grid order, each with its name and its glyph. */
const GROUPS: { key: GroupKey; title: string; icon: Icon }[] = (
  [
    ['finance', Wallet],
    ['health', Heartbeat],
    ['projects', Kanban],
    ['runs', Alarm],
    ['weight', Scales],
    ['about', IdentificationCard],
    ['memory', Brain],
  ] as const
).map(([key, icon]) => ({ key, title: GROUP_TITLES[key], icon }));

export default function ProfilePage({
  profile,
  memories,
  habits,
  weighIns,
  group,
  focus,
  top,
  onSaveField,
  onSaveWeighIn,
  onDeleteWeighIn,
  onSaveMemory,
  onAddMemory,
  onDeleteMemory,
  onAddHabit,
  onEditHabit,
  onFlipHabit,
  schedules,
  onEditSchedule,
  onDeleteHabit,
  onProjectsChanged,
  onGroup,
  backTo,
  onBack,
  composer,
}: Props) {
  /** Which cell is open: a field id, 'weigh-in', 'memory:new', or 'memory:<id>'. */
  const [open, setOpen] = useState<string | null>(focus);
  const [newHabit, setNewHabit] = useState<{
    name: string; direction: 'build' | 'break'; unit: string;
  }>({ name: '', direction: 'build', unit: '' });
  const [newMemory, setNewMemory] = useState({ slug: '', kind: 'preference', text: '' });
  const [newFailed, setNewFailed] = useState(false);
  const latest = weighIns[0];
  /** Loaded here rather than passed in: the page is the only screen that
   *  edits them, and the deck only needs the names it already has. */
  const [projects, setProjects] = useState<ProjectRow[] | null>(null);
  const loadProjects = () =>
    fetchProjects().then(setProjects, () => setProjects((cur) => cur ?? []));
  // Read on arrival, and again when a group page comes off the grid — a
  // project made there shows on the grid's tile.
  useEffect(() => {
    if (top) void loadProjects();
  }, [top]);
  const projectsChanged = () => {
    void loadProjects();
    onProjectsChanged?.();
  };

  // Arriving from ⋮ → Edit goal: that row open, in view.
  useEffect(() => {
    if (!focus) return;
    setOpen(focus);
    const t = setTimeout(
      () => document.getElementById(`pf-${focus}`)?.scrollIntoView({ block: 'center' }),
      60,
    );
    return () => clearTimeout(t);
  }, [focus]);

  // Back closes an open row before it leaves the page. A field keeps its own
  // Escape (an editor cancels itself).
  useBack(open != null, () => setOpen(null));

  const toggle = (id: string) => setOpen((cur) => (cur === id ? null : id));

  const fieldRows = (fields: FieldDef[]) =>
    fields.map((f) => {
      const ask = inputFor(f);
      const value = formatValue(f, profile);
      // Saved empty, a field is cleared — every one but the name and the
      // timezone. Said only when there is something to clear.
      const hint = clearable(f) && value != null ? [ask.hint, 'Save it empty to clear it.'].filter(Boolean).join(' ') : ask.hint;
      return (
        <Cell key={f.id} id={f.id}>
          <RowButton label={f.label} value={value} open={open === f.id} onClick={() => toggle(f.id)} />
          {open === f.id &&
            (f.kind === 'choice' ? (
              <ChoiceEditor
                options={f.options ?? []}
                current={value == null ? null : draftValue(f, profile)}
                onSave={(raw) => onSaveField(f.id, raw)}
                onClose={() => setOpen(null)}
              />
            ) : (
              <Editor
                initial={draftValue(f, profile)}
                type={ask.type}
                inputMode={ask.inputMode}
                prefix={ask.prefix}
                suffix={ask.suffix}
                hint={hint}
                onSave={(raw) => onSaveField(f.id, raw)}
                onClose={() => setOpen(null)}
              />
            ))}
        </Cell>
      );
    });

  const addHabit = async () => {
    const name = newHabit.name.trim();
    if (!name) return;
    const ok = await onAddHabit({
      name,
      direction: newHabit.direction,
      // Blank means a tick is the whole fact — a cigarette is counted, not
      // measured — so it is NULL, never an empty string.
      unit: newHabit.unit.trim() || null,
    });
    if (ok) {
      setNewHabit({ name: '', direction: 'build', unit: '' });
      setOpen(null);
    }
  };

  const addMemory = async () => {
    const ok = await onAddMemory(newMemory);
    if (ok) {
      setNewMemory({ slug: '', kind: 'preference', text: '' });
      setOpen(null);
      setNewFailed(false);
    } else setNewFailed(true);
  };

  /** The rows of one group — its page's single card. */
  const body = (g: GroupKey): ReactNode => {
    switch (g) {
      case 'finance':
        return fieldRows(FINANCE_FIELDS);
      case 'health':
        return (
          <>
            {fieldRows(HEALTH_FIELDS)}

            {/* Habits. Until now one could only be created by a migration: the
                ticks had routes and the list did not. `direction` shows here —
                a long chain is progress on a `build` and a warning on a
                `break`. spec/in-progress/habits.md. */}
            <div style={{ ...cardHeading, padding: '14px 14px 4px', borderTop: `1px solid ${color.line}` }}>
              Habits
            </div>
            {habits.length === 0 && (
              <div style={{ fontFamily: font.sans, fontSize: 13.5, lineHeight: 1.5, color: color.ink, padding: '4px 14px 8px' }}>
                Nothing tracked yet. A habit is a yes-or-no you tick each day — gym, cigarettes,
                meditation — and the week strip on the deck counts it.
              </div>
            )}
            {habits.map((h) => (
              <Cell key={h.id} id={`habit:${h.id}`}>
                <div style={{ display: 'flex', alignItems: 'flex-start' }}>
                  <button
                    type="button"
                    className="hov-tint"
                    style={{ ...rowStyle, flexDirection: 'column', alignItems: 'flex-start', gap: 2 }}
                    onClick={() => toggle(`habit:${h.id}`)}
                    aria-expanded={open === `habit:${h.id}`}
                  >
                    <span>
                      {h.name}
                      {h.pending ? ' · saving' : ''}
                    </span>
                    <span style={subLine}>
                      {h.direction}
                      {h.unit ? ` · ${h.unit}` : ''} · {h.daysThisWeek}/7 this week
                    </span>
                  </button>
                  <button
                    type="button"
                    onClick={() => void onFlipHabit(h.id, h.direction === 'build' ? 'break' : 'build')}
                    aria-label={`Track ${h.name} as ${h.direction === 'build' ? 'break' : 'build'}`}
                    title={h.direction === 'build' ? 'Something you want more of' : 'Something you want less of'}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '13px 6px', display: 'flex' }}
                  >
                    {h.direction === 'build' ? (
                      <ArrowUp size={15} color={color.ink} aria-hidden />
                    ) : (
                      <ArrowDown size={15} color={color.red} aria-hidden />
                    )}
                  </button>
                  <button
                    type="button"
                    onClick={() => onDeleteHabit(h.id)}
                    aria-label={`Stop tracking ${h.name}`}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '13px 12px', display: 'flex' }}
                  >
                    <X size={15} color={color.faint} aria-hidden />
                  </button>
                </div>
                {open === `habit:${h.id}` && (
                  <Editor
                    initial={h.name}
                    hint={h.loggedEver ? `Ticked ${h.loggedEver}× so far. Renaming keeps every one.` : 'Never ticked yet.'}
                    onSave={(name) => onEditHabit(h.id, { name })}
                    onClose={() => setOpen(null)}
                  />
                )}
              </Cell>
            ))}
            <Cell id="habit:new">
              <button
                type="button"
                className="hov-tint"
                style={addRow}
                onClick={() => toggle('habit:new')}
                aria-expanded={open === 'habit:new'}
              >
                <Plus size={15} aria-hidden />
                Track a habit
              </button>
              {open === 'habit:new' && (
                <div style={{ padding: '2px 14px 12px', display: 'grid', gap: 8 }}>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <input
                      autoFocus
                      placeholder="Meditation"
                      value={newHabit.name}
                      onChange={(e) => setNewHabit({ ...newHabit, name: e.target.value })}
                      style={{ ...inputStyle, flex: 1 }}
                    />
                    <select
                      value={newHabit.direction}
                      onChange={(e) => setNewHabit({ ...newHabit, direction: e.target.value as 'build' | 'break' })}
                      style={{ ...inputStyle, fontSize: 13 }}
                    >
                      <option value="build">build</option>
                      <option value="break">break</option>
                    </select>
                  </div>
                  <input
                    placeholder="unit — minutes, units… or leave blank"
                    value={newHabit.unit}
                    onChange={(e) => setNewHabit({ ...newHabit, unit: e.target.value })}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') { e.preventDefault(); void addHabit(); }
                      else if (e.key === 'Escape') { e.preventDefault(); setOpen(null); }
                    }}
                    style={inputStyle}
                  />
                  <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                    <button type="button" onClick={() => setOpen(null)} style={cancelBtn}>
                      Cancel
                    </button>
                    <button type="button" className="hov-brand" onClick={() => void addHabit()} style={saveBtn}>
                      Track it
                    </button>
                  </div>
                </div>
              )}
            </Cell>
          </>
        );
      case 'projects':
        // Made here, placed into by chat and the work sync alike. spec/done/projects.md.
        return (
          <ProjectsSection
            rows={projects ?? []}
            open={open}
            toggle={toggle}
            close={() => setOpen(null)}
            changed={projectsChanged}
          />
        );
      case 'runs':
        return (
          <>
            {schedules.length === 0 && (
              <div style={{ fontFamily: font.sans, fontSize: 13.5, color: color.ink, padding: '12px 14px' }}>
                Nothing runs on its own yet.
              </div>
            )}
            {schedules.map((s) => (
              <Cell key={s.id} id={`sched:${s.id}`}>
                <div style={{ display: 'flex', alignItems: 'flex-start' }}>
                  <button
                    type="button"
                    className="hov-tint"
                    style={{ ...rowStyle, flexDirection: 'column', alignItems: 'flex-start', gap: 2 }}
                    onClick={() => toggle(`sched:${s.id}`)}
                    aria-expanded={open === `sched:${s.id}`}
                  >
                    <span>
                      {s.label}
                      {s.pending ? ' · saving' : ''}
                    </span>
                    {/* What it is, until it has run; after that, what it did. A
                        failure outranks both — a scheduled job that silently
                        stopped working is worse than one never built. */}
                    <span style={{ ...subLine, color: s.lastError ? color.red : color.faint }}>
                      {s.lastError
                        ? `failed · ${s.lastError.slice(0, 40)}`
                        : !s.enabled
                          ? 'off'
                          : s.lastRunDay
                            ? `${s.repeat} · last run ${shortDate(s.lastRunDay)}`
                            : `${s.repeat} · ${s.blurb.toLowerCase()}`}
                    </span>
                  </button>
                  <span
                    style={{
                      fontFamily: font.sans, fontSize: 14, fontWeight: 500, padding: '12px 6px',
                      color: s.enabled ? color.ink : color.faint,
                    }}
                  >
                    {s.at}
                  </span>
                  {/* The kit switch, as on the phone: centred on the label's line. */}
                  <span style={{ padding: '8px 14px 0 2px' }}>
                    <Switch
                      on={s.enabled}
                      onToggle={() => void onEditSchedule(s.id, { enabled: !s.enabled })}
                      label={`${s.enabled ? 'Turn off' : 'Turn on'} ${s.label}`}
                    />
                  </span>
                </div>
                {open === `sched:${s.id}` && (
                  <Editor
                    initial={s.at}
                    hint="24-hour clock, your time. A run missed while the app was closed still happens when it next opens."
                    onSave={async (raw) => {
                      const t = raw.trim();
                      if (!/^\d{1,2}:\d{2}$/.test(t)) return false;
                      return onEditSchedule(s.id, { at: t.padStart(5, '0') });
                    }}
                    onClose={() => setOpen(null)}
                  />
                )}
              </Cell>
            ))}
          </>
        );
      case 'weight':
        return (
          <>
            {fieldRows(WEIGHT_FIELDS)}
            <Cell id="weigh-in">
              <RowButton
                label={latest ? 'Last weigh-in' : 'Weigh-in'}
                value={latest ? `${latest.kg} kg` : null}
                estimated={latest?.estimated}
                sub={latest ? `· ${shortDate(latest.day)}${latest.pending ? ' · saving' : latest.failed ? ' · unsaved' : ''}` : undefined}
                open={open === 'weigh-in'}
                onClick={() => toggle('weigh-in')}
              />
              {open === 'weigh-in' && (
                <Editor
                  initial={latest ? String(latest.kg) : ''}
                  inputMode="decimal"
                  suffix="kg"
                  hint="Today's weight. A second reading today replaces the first."
                  onSave={onSaveWeighIn}
                  onClose={() => setOpen(null)}
                />
              )}
            </Cell>

            {/* Every reading, newest first, each with its own delete — the
                reading goes, and the day's copy of it with it. One said as a
                guess keeps its dot. As on the phone. */}
            {weighIns.length > 0 && (
              <div style={{ ...cardHeading, padding: '14px 14px 4px', borderTop: `1px solid ${color.line}` }}>
                Weigh-ins
              </div>
            )}
            {weighIns.map((w) => (
              <Cell key={w.id} id={`weigh:${w.id}`}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, paddingLeft: 14 }}>
                  <span style={{ flex: 1, minWidth: 0, fontFamily: font.sans, fontSize: 14, lineHeight: '18px', color: color.ink, padding: '12px 0' }}>
                    {shortDate(w.day)}
                    {w.pending ? ' · saving' : w.failed ? ' · unsaved' : ''}
                  </span>
                  <span style={{ fontFamily: font.sans, fontSize: 14, fontWeight: 500, color: color.ink, whiteSpace: 'nowrap' }}>
                    {w.estimated && <Dot />}
                    {w.kg} kg
                  </span>
                  {w.pending ? (
                    <span style={{ width: 39 }} />
                  ) : (
                    <button
                      type="button"
                      onClick={() => onDeleteWeighIn(w.id)}
                      aria-label={`Delete the weigh-in of ${shortDate(w.day)}`}
                      style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '13px 12px', display: 'flex' }}
                    >
                      <X size={15} color={color.faint} aria-hidden />
                    </button>
                  )}
                </div>
              </Cell>
            ))}
          </>
        );
      case 'about':
        return fieldRows(ABOUT_FIELDS);
      case 'memory':
        return (
          <>
            {memories.length === 0 && (
              <div style={{ fontFamily: font.sans, fontSize: 13.5, lineHeight: 1.5, color: color.ink, padding: '12px 14px 8px' }}>
                Nothing remembered yet. Facts about you — profession, how you like answers — live here,
                one per line, and any agent you connect reads them from this one place.
              </div>
            )}
            {memories.map((m) => (
              <Cell key={m.id} id={`memory:${m.id}`}>
                <div style={{ display: 'flex', alignItems: 'flex-start' }}>
                  <button
                    type="button"
                    className="hov-tint"
                    style={{ ...rowStyle, flexDirection: 'column', alignItems: 'flex-start', gap: 2 }}
                    onClick={() => toggle(`memory:${m.id}`)}
                    aria-expanded={open === `memory:${m.id}`}
                  >
                    <span style={subLine}>
                      {/* Nobody has said "still true": the fact is inferred, so it wears the dot. */}
                      {!m.confirmedAt && <Dot />}
                      {m.slug} · {m.kind}
                      {m.pending ? ' · saving' : m.failed ? ' · unsaved' : ''}
                    </span>
                    <span className={open === `memory:${m.id}` ? undefined : 'clamp-2'}>{m.text}</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => onDeleteMemory(m.id)}
                    aria-label={`Forget ${m.slug}`}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '13px 12px', display: 'flex' }}
                  >
                    <X size={15} color={color.faint} aria-hidden />
                  </button>
                </div>
                {open === `memory:${m.id}` && (
                  <Editor
                    initial={m.text}
                    multiline
                    hint="Enter saves · Shift+Enter for a new line"
                    onSave={(text) => onSaveMemory(m.id, text)}
                    onClose={() => setOpen(null)}
                  />
                )}
              </Cell>
            ))}
            <Cell id="memory:new">
              <button
                type="button"
                className="hov-tint"
                style={addRow}
                onClick={() => toggle('memory:new')}
                aria-expanded={open === 'memory:new'}
              >
                <Plus size={15} aria-hidden />
                Add memory
              </button>
              {open === 'memory:new' && (
                <div style={{ padding: '2px 14px 12px', display: 'grid', gap: 8 }}>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <input
                      autoFocus
                      placeholder="slug, like profession"
                      value={newMemory.slug}
                      onChange={(e) => setNewMemory({ ...newMemory, slug: e.target.value })}
                      style={{ ...inputStyle, flex: 1 }}
                    />
                    <select
                      value={newMemory.kind}
                      onChange={(e) => setNewMemory({ ...newMemory, kind: e.target.value })}
                      style={{ ...inputStyle, fontSize: 13 }}
                    >
                      {MEMORY_KINDS.map((k) => (
                        <option key={k} value={k}>
                          {k}
                        </option>
                      ))}
                    </select>
                  </div>
                  <textarea
                    placeholder="The fact, in your words"
                    rows={2}
                    value={newMemory.text}
                    onChange={(e) => setNewMemory({ ...newMemory, text: e.target.value })}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        void addMemory();
                      } else if (e.key === 'Escape') {
                        e.preventDefault();
                        setOpen(null);
                      }
                    }}
                    style={{ ...inputStyle, fontFamily: font.sans, resize: 'vertical' }}
                  />
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontFamily: font.sans, fontSize: 12, color: newFailed ? color.red : color.faint, flex: 1 }}>
                      {newFailed ? 'Not saved — slug is lowercase letters, digits and dashes; the fact cannot be empty.' : 'Same slug as an existing memory updates it.'}
                    </span>
                    <button type="button" style={cancelBtn} onClick={() => setOpen(null)}>
                      Cancel
                    </button>
                    <button type="button" className="hov-brand" style={saveBtn} onClick={() => void addMemory()}>
                      Save
                    </button>
                  </div>
                </div>
              )}
            </Cell>
          </>
        );
    }
  };

  const current = GROUPS.find((g) => g.key === group);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={current ? current.title : 'Profile'}
      tabIndex={-1}
      style={{
        position: 'absolute',
        inset: 0,
        zIndex: 80,
        background: color.paper,
        display: 'flex',
        flexDirection: 'column',
        padding: `${inset.top} 0 0`,
        animation: 'fadeup 0.28s cubic-bezier(0.3,0.7,0.3,1)',
        outline: 'none',
      }}
    >
      <div style={{ padding: `0 ${space.gutter}px 16px`, flex: '0 0 auto' }}>
        {current ? (
          <PageHeader back={{ label: backTo, onClick: onBack }} eyebrow="Profile" title={current.title} />
        ) : (
          // The face and the name head the page; ← sits at the right of the same row.
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <UserAvatar name={profile.displayName} url={profile.avatarUrl} size={40} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontFamily: font.sans, fontWeight: 600, fontSize: 18, lineHeight: '22px', color: color.ink }}>
                {profile.displayName || 'Profile'}
              </div>
              {/* The signed-in address. The one place that answers *which account
                  is this*, which has to be answerable before someone signs out. */}
              <div style={{ fontFamily: font.sans, fontSize: 12.5, lineHeight: '16px', color: color.faint, marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {profile.email ?? 'Tap a group to change it'}
              </div>
            </div>
            <BackButton back={{ label: backTo, onClick: onBack }} />
          </div>
        )}
      </div>

      {/* Room at the bottom for the floating composer. */}
      <div className="scroll-y" style={{ flex: 1, padding: `0 ${space.gutter}px 110px` }}>
        {current ? (
          <div
            key={current.key}
            className="profile-group"
            style={{
              background: color.white,
              border: `1px solid ${color.line}`,
              borderRadius: radius.card,
              overflow: 'hidden',
              animation: 'fadeup 0.2s',
            }}
          >
            {body(current.key)}
          </div>
        ) : (
          // Two to a row; the seventh sits alone. The heading is enough to
          // find a group — what it holds is behind the tap.
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            {GROUPS.map((g) => (
              <button
                key={g.key}
                type="button"
                onClick={() => onGroup(g.key)}
                className="hov-tint"
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'flex-start',
                  minWidth: 0,
                  background: color.white,
                  border: `1px solid ${color.line}`,
                  borderRadius: radius.card,
                  padding: 12,
                  cursor: 'pointer',
                  textAlign: 'left',
                  fontFamily: font.sans,
                }}
              >
                <g.icon size={20} color={color.muted} aria-hidden />
                <span style={{ fontWeight: 500, fontSize: 15, lineHeight: '20px', color: color.ink, marginTop: 10 }}>
                  {g.title}
                </span>
              </button>
            ))}
          </div>
        )}
      </div>

      {composer}
    </div>
  );
}

/* ─── Projects (spec/done/projects.md) ─────────────────────────────── */

interface Draft {
  name: string;
  description: string;
  icon: string;
  aliases: string;
}

const draftOf = (r?: ProjectRow): Draft => ({
  name: r?.name ?? '',
  description: r?.description ?? '',
  icon: r?.icon ?? '',
  aliases: (r?.aliases ?? []).join(', '),
});

const aliasList = (raw: string) =>
  raw.split(',').map((a) => a.trim()).filter(Boolean);

function ProjectsSection({
  rows,
  open,
  toggle,
  close,
  changed,
}: {
  rows: ProjectRow[];
  open: string | null;
  toggle: (id: string) => void;
  close: () => void;
  changed: () => void;
}) {
  const home = rows.find((r) => r.isDefault);
  return (
    <>
      <div style={{ fontFamily: font.sans, fontSize: 13.5, lineHeight: 1.5, color: color.ink, padding: '12px 14px 10px' }}>
        A task lands in the project you name. When you name none, Spica puts it where one
        plainly fits — the description is what it reads — and anything else goes to{' '}
        {home ? home.name : 'the default'}.
      </div>
      {rows.map((r) => (
        <Cell key={r.id} id={`project:${r.id}`}>
          <button
            type="button"
            className="hov-tint"
            style={{ ...rowStyle, alignItems: 'flex-start', opacity: r.archived ? 0.55 : 1 }}
            onClick={() => toggle(`project:${r.id}`)}
            aria-expanded={open === `project:${r.id}`}
          >
            <span style={{ display: 'flex', gap: 10, alignItems: 'flex-start', minWidth: 0 }}>
              <span style={{ marginTop: 1 }}>
                <ProjectIcon project={r} size={16} />
              </span>
              <span style={{ display: 'grid', gap: 2, minWidth: 0 }}>
                <span style={{ fontFamily: font.sans, fontSize: 14, color: color.ink }}>
                  {r.name}
                </span>
                <span
                  style={{
                    fontFamily: font.sans,
                    fontSize: 12,
                    color: color.faint,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {r.isDefault
                    ? 'default — tasks with no project land here'
                    : r.archived
                      ? 'archived'
                      : r.description || 'no description — add one so tasks can find it'}
                </span>
              </span>
            </span>
            <span style={{ fontFamily: font.sans, fontSize: 13, color: color.muted, flex: '0 0 auto' }}>
              {r.openTasks} open
            </span>
          </button>
          {open === `project:${r.id}` && (
            <ProjectEditor row={r} home={home} onDone={() => { close(); changed(); }} onCancel={close} />
          )}
        </Cell>
      ))}
      <Cell id="project:new">
        <button
          type="button"
          className="hov-tint"
          style={addRow}
          onClick={() => toggle('project:new')}
          aria-expanded={open === 'project:new'}
        >
          <Plus size={15} aria-hidden />
          New project
        </button>
        {open === 'project:new' && (
          <ProjectEditor home={home} onDone={() => { close(); changed(); }} onCancel={close} />
        )}
      </Cell>
    </>
  );
}

function ProjectEditor({
  row,
  home,
  onDone,
  onCancel,
}: {
  row?: ProjectRow;
  home?: ProjectRow;
  onDone: () => void;
  onCancel: () => void;
}) {
  const [d, setD] = useState<Draft>(() => draftOf(row));
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState('');
  const [confirmDelete, setConfirmDelete] = useState(false);
  // Back takes back a half-asked delete before it closes the editor.
  useBack(confirmDelete, () => setConfirmDelete(false));
  const set = (k: keyof Draft) => (v: string) => setD((cur) => ({ ...cur, [k]: v }));

  // Say what the server did beyond the obvious — an alias taken from
  // another project — then get out of the way.
  const finish = (r?: ProjectRow) => {
    const moved = r?.movedAliases ?? [];
    if (moved.length) {
      setNote(moved.map((m) => `${m.alias} moved here from ${m.from}`).join(' · '));
      setTimeout(onDone, 1400);
    } else {
      onDone();
    }
  };
  const run = (work: () => Promise<ProjectRow | void>) => {
    setBusy(true);
    setNote('');
    work().then(
      (r) => finish(r || undefined),
      (e: Error) => {
        setBusy(false);
        setNote(e.message || 'Not saved — the server refused.');
      },
    );
  };

  const save = () => {
    if (!d.name.trim()) {
      setNote('A project needs a name.');
      return;
    }
    const body = {
      name: d.name.trim(),
      description: d.description.trim() || null,
      icon: d.icon.trim() || null,
      aliases: aliasList(d.aliases),
    };
    run(() => (row ? patchProject(row.id, body) : createProject(body)));
  };

  const iconChoice = (value: string, label: string, mark: ReactNode) => (
    <button
      key={value || 'none'}
      type="button"
      title={label}
      aria-label={label}
      aria-pressed={d.icon === value}
      onClick={() => set('icon')(value)}
      style={{
        width: 30,
        height: 30,
        borderRadius: 8,
        border: `1px solid ${d.icon === value ? color.brand : color.line}`,
        background: d.icon === value ? color.brandTint : color.white,
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        cursor: 'pointer',
        padding: 0,
      }}
    >
      {mark}
    </button>
  );
  const preview = { name: d.name || '?', color: row?.color ?? color.work, icon: undefined };

  return (
    <div style={{ padding: '2px 14px 12px', display: 'grid', gap: 8 }}>
      <input
        autoFocus={!row}
        placeholder="NovaCart-chan"
        aria-label="Project name"
        value={d.name}
        onChange={(e) => set('name')(e.target.value)}
        style={inputStyle}
      />
      <textarea
        placeholder="What it is, in a line — the chatbot for the shop's catalogue"
        aria-label="Description"
        rows={2}
        value={d.description}
        onChange={(e) => set('description')(e.target.value)}
        style={{ ...inputStyle, fontFamily: font.sans, resize: 'vertical' }}
      />
      <div style={{ display: 'grid', gap: 6 }}>
        <div style={{ fontFamily: font.sans, fontSize: 12, color: color.faint }}>
          Icon — an emoji, or one of these
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, alignItems: 'center' }}>
          {iconChoice('', 'First letter', <ProjectIcon project={preview} size={15} />)}
          {ICON_NAMES.map((n) =>
            iconChoice(`icon:${n}`, n, <ProjectIcon project={{ ...preview, icon: `icon:${n}` }} size={15} />),
          )}
          <input
            aria-label="Emoji"
            placeholder="🛒"
            value={d.icon.startsWith('icon:') ? '' : d.icon}
            onChange={(e) => set('icon')(e.target.value.trim())}
            style={{ ...inputStyle, width: 52, textAlign: 'center', fontFamily: font.sans }}
          />
        </div>
      </div>
      <input
        placeholder="Also known as — linear:Kestrel, novachan"
        aria-label="Also known as"
        value={d.aliases}
        onChange={(e) => set('aliases')(e.target.value)}
        onKeyDown={(e: KeyboardEvent<HTMLInputElement>) => {
          if (e.key === 'Enter') { e.preventDefault(); save(); }
          else if (e.key === 'Escape') { e.preventDefault(); onCancel(); }
        }}
        style={inputStyle}
      />
      {note && (
        <div style={{ fontFamily: font.sans, fontSize: 12.5, color: color.ink }}>{note}</div>
      )}
      {confirmDelete && row ? (
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', justifyContent: 'flex-end' }}>
          <span style={{ fontFamily: font.sans, fontSize: 13, color: color.ink, marginRight: 'auto' }}>
            Delete {row.name}? {row.openTasks ? `Its ${row.openTasks} open tasks move to ` : 'Its tasks move to '}
            {home?.name ?? 'the default'}.
          </span>
          <button type="button" onClick={() => setConfirmDelete(false)} style={cancelBtn}>Keep</button>
          <button
            type="button"
            disabled={busy}
            onClick={() => run(() => deleteProject(row.id))}
            style={{ ...saveBtn, background: color.red }}
          >
            Delete
          </button>
        </div>
      ) : (
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', justifyContent: 'flex-end', flexWrap: 'wrap' }}>
          {row && !row.isDefault && (
            <>
              <button
                type="button"
                disabled={busy}
                onClick={() => run(() => patchProject(row.id, { is_default: true }))}
                style={cancelBtn}
              >
                Make default
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => run(() => patchProject(row.id, { archived: !row.archived }))}
                style={cancelBtn}
              >
                {row.archived ? 'Unarchive' : 'Archive'}
              </button>
              <button type="button" onClick={() => setConfirmDelete(true)} style={{ ...cancelBtn, color: color.red }}>
                Delete
              </button>
            </>
          )}
          {row?.isDefault && (
            // The buttons the other projects have are missing here on purpose;
            // say so, or the row reads as a delete that was forgotten.
            <span style={{ fontFamily: font.sans, fontSize: 12, color: color.faint, lineHeight: 1.4 }}>
              The default can’t be archived or deleted — every task without a project lands
              here. To remove it, open another project and choose Make default.
            </span>
          )}
          <span style={{ flex: 1 }} />
          <button type="button" onClick={onCancel} style={cancelBtn}>Cancel</button>
          <button type="button" className="hov-brand" disabled={busy} onClick={save} style={saveBtn}>
            {row ? 'Save' : 'Create'}
          </button>
        </div>
      )}
    </div>
  );
}
