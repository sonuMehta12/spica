import { useMemo, useState } from 'react';
import { ArrowUpRight, Check, Plus } from '@phosphor-icons/react';
import { color, font } from '../../theme';
import type { ExerciseRow } from '../../data/api';
import { useBack } from '../../state/nav';

/**
 * Your data → Workouts. spec/done/workouts.md.
 *
 * A **library**, the way Dishes is one — what exists to suggest from, not a
 * record of what happened. *"Aaj leg lagana hai"* is a muscle-group query;
 * what the library does not hold, the agent finds and offers to keep.
 *
 * There is no session list, and that is the point of the 2026-09-07 revert: a
 * workout is logged as a habit, yes or no, the same as a cigarette. The Diet
 * card's strip still shows the days.
 *
 * `tried` is the only stored count in the app, because it is the only one with
 * no ledger under it — a declaration, not a measurement. 0 means bookmarked
 * but never done.
 */
interface Props {
  exercises: ExerciseRow[];
  onDid: (id: string) => void;
  onAdd: (row: {
    name: string;
    kind: string | null;
    muscle_group: string | null;
    equipment: string | null;
    typical_minutes: number | null;
    steps: string | null;
    source_url: string | null;
  }) => Promise<boolean>;
}

const shell = {
  background: color.white,
  border: `1px solid ${color.line}`,
  borderRadius: 14,
  overflow: 'hidden' as const,
};

const label = {
  display: 'block',
  fontFamily: font.sans,
  fontSize: 12,
  color: color.muted,
  marginBottom: 4,
};

const input = {
  width: '100%',
  boxSizing: 'border-box' as const,
  fontFamily: font.sans,
  fontSize: 14,
  padding: '6px 9px',
  borderRadius: 10,
  border: `1px solid ${color.border}`,
  background: color.paper,
  color: color.ink,
  outline: 'none',
};

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const shortDate = (iso: string) => `${Number(iso.slice(8, 10))} ${MONTHS[Number(iso.slice(5, 7)) - 1]}`;

const KINDS = ['strength', 'cardio', 'mobility', 'stretch'];
type Tab = 'all' | 'done' | 'new';

const EMPTY = {
  name: '',
  kind: 'strength',
  muscle_group: '',
  equipment: '',
  typical_minutes: '',
  steps: '',
  source_url: '',
};

export default function WorkoutsSection({ exercises, onDid, onAdd }: Props) {
  const [view, setView] = useState<Tab>('all');
  const [filterOpen, setFilterOpen] = useState(false);
  // Three independent filters rather than one shared slot: "cardio, at home"
  // is a real question and one slot could not hold it.
  const [kind, setKind] = useState<string | null>(null);
  const [muscle, setMuscle] = useState<string | null>(null);
  const [gear, setGear] = useState<string | null>(null);
  const [q, setQ] = useState('');
  const [open, setOpen] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ ...EMPTY });
  const [busy, setBusy] = useState(false);

  /** Only values the library actually has — an empty filter is a dead end. */
  const options = useMemo(
    () => ({
      kind: KINDS.filter((k) => exercises.some((e) => e.kind === k)),
      muscle: [...new Set(exercises.map((e) => e.muscleGroup).filter(Boolean))].sort() as string[],
      gear: [...new Set(exercises.map((e) => e.equipment).filter(Boolean))].sort() as string[],
    }),
    [exercises],
  );

  const active = [kind, muscle, gear].filter(Boolean).length;
  const clear = () => {
    setKind(null);
    setMuscle(null);
    setGear(null);
  };

  const shown = useMemo(() => {
    const hit = q.trim().toLowerCase();
    return exercises.filter(
      (e) =>
        (view === 'all' || (view === 'done' ? e.tried > 0 : e.tried === 0)) &&
        (!kind || e.kind === kind) &&
        (!muscle || e.muscleGroup === muscle) &&
        (!gear || e.equipment === gear) &&
        (!hit || e.name.toLowerCase().includes(hit) || e.aliases.some((a) => a.includes(hit))),
    );
  }, [exercises, view, kind, muscle, gear, q]);
  // Back closes, innermost first: the new exercise, an open one, the filters
  // — an open exercise only while the list still shows it.
  useBack(filterOpen, () => setFilterOpen(false));
  useBack(open != null && shown.some((e) => e.id === open), () => setOpen(null));
  useBack(adding, () => setAdding(false));

  const add = async () => {
    const name = form.name.trim();
    if (!name) return;
    setBusy(true);
    const ok = await onAdd({
      name,
      kind: form.kind || null,
      muscle_group: form.muscle_group.trim() || null,
      equipment: form.equipment.trim() || null,
      typical_minutes: form.typical_minutes ? Number(form.typical_minutes) : null,
      steps: form.steps.trim() || null,
      source_url: form.source_url.trim() || null,
    });
    setBusy(false);
    if (ok) {
      setForm({ ...EMPTY });
      setAdding(false);
    }
  };

  const chip = (on: boolean, text: string, onClick: () => void) => (
    <button
      key={text}
      type="button"
      onClick={onClick}
      style={{
        fontFamily: font.sans,
        fontSize: 11.5,
        padding: '5px 12px',
        borderRadius: 14,
        border: `1px solid ${on ? color.brand : color.border}`,
        background: on ? color.brand : color.white,
        color: on ? color.white : color.muted,
        cursor: 'pointer',
      }}
    >
      {text}
    </button>
  );

  const done = exercises.filter((e) => e.tried > 0).length;

  return (
    <>
      {/* Three tabs and nothing else. Kind, muscle and equipment were two rows
          of chips on arrival — noise before anyone had asked a question — so
          they live behind Filter, which counts itself when it is on. */}
      <div style={{ display: 'flex', gap: 7, marginBottom: 6, alignItems: 'center' }}>
        {chip(view === 'all', `All · ${exercises.length}`, () => setView('all'))}
        {chip(view === 'done', `Done · ${done}`, () => setView('done'))}
        {chip(view === 'new', `Not tried · ${exercises.length - done}`, () => setView('new'))}
        <span style={{ flex: 1 }} />
        <button
          type="button"
          onClick={() => setFilterOpen((o) => !o)}
          aria-expanded={filterOpen}
          style={{
            fontFamily: font.sans,
            fontSize: 12.5,
            fontWeight: 500,
            lineHeight: '16px',
            padding: '6px 12px',
            borderRadius: 999,
            cursor: 'pointer',
            whiteSpace: 'nowrap',
            // The brand whenever a filter is on, open or shut: a filtered
            // list that looks unfiltered is a lie by omission.
            border: `1px solid ${active || filterOpen ? color.brand : color.border}`,
            background: active ? color.brandTint : color.white,
            color: active || filterOpen ? color.brand : color.muted,
          }}
        >
          Filter{active ? ` · ${active}` : ''}
        </button>
      </div>

      {filterOpen && (
        <div
          style={{
            ...shell,
            padding: '11px 13px 13px',
            marginBottom: 6,
            animation: 'fadeup 0.18s',
          }}
        >
          {([
            ['Type', options.kind, kind, setKind],
            ['Muscle group', options.muscle, muscle, setMuscle],
            ['Equipment', options.gear, gear, setGear],
          ] as const).map(([name, values, current, set]) => (
            <div key={name} style={{ marginBottom: 10 }}>
              <span style={label}>{name}</span>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {values.map((v) =>
                  chip(current === v, v, () => set(current === v ? null : v)),
                )}
              </div>
            </div>
          ))}
          <button
            type="button"
            disabled={!active}
            onClick={clear}
            style={{
              fontFamily: font.sans,
              fontSize: 11.5,
              padding: '5px 12px',
              borderRadius: 14,
              border: `1px solid ${active ? color.border : color.line}`,
              background: color.paper,
              color: active ? color.muted : color.faint,
              cursor: active ? 'pointer' : 'default',
            }}
          >
            Clear
          </button>
        </div>
      )}

      <div style={shell}>
        <div style={{ padding: '11px 13px 2px' }}>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search — the name, or what you call it"
            style={input}
          />
        </div>

        {shown.length === 0 && (
          <div style={{ padding: 14, fontSize: 13.5, color: color.muted }}>
            Nothing matches.
          </div>
        )}

        {shown.map((e, i) => (
          <div key={e.id} style={{ borderTop: i ? `1px solid ${color.lineSoft}` : 'none' }}>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 9, padding: '10px 13px' }}>
              <button
                type="button"
                className="hov-tint"
                onClick={() => setOpen(open === e.id ? null : e.id)}
                aria-expanded={open === e.id}
                style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', textAlign: 'left', minWidth: 0, flex: 1 }}
              >
                <span style={{ fontSize: 13.5, fontWeight: 500, color: color.ink }}>{e.name}</span>
                <span style={{ display: 'block', fontFamily: font.sans, fontSize: 11, color: color.faint, marginTop: 3 }}>
                  {[e.kind, e.muscleGroup, e.equipment].filter(Boolean).join(' · ')}
                  {e.typicalMinutes != null && ` · ${e.typicalMinutes}m`}
                </span>
              </button>

              {/* 0 is a real answer, not missing data — it says bookmarked,
                  never done, which is exactly what the old star meant. */}
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3, fontFamily: font.sans, fontSize: 12, whiteSpace: 'nowrap', color: e.tried ? color.dietInk : color.faint }}>
                {e.tried ? <><Check size={12} weight="bold" color={color.dietInk} aria-label="Tried" />{`${e.tried}×`}</> : 'not tried'}
                {e.lastTried && ` · ${shortDate(e.lastTried)}`}
              </span>
              <button
                type="button"
                onClick={() => onDid(e.id)}
                aria-label={`Did ${e.name} today`}
                className="hov-tint"
                style={{
                  fontFamily: font.sans,
                  fontSize: 11.5,
                  padding: '3px 9px',
                  borderRadius: 11,
                  border: `1px solid ${color.border}`,
                  background: color.paper,
                  color: color.muted,
                  cursor: 'pointer',
                  flex: '0 0 auto',
                }}
              >
                +1
              </button>
            </div>

            {open === e.id && (
              <div style={{ padding: '0 13px 12px', animation: 'fadeup 0.2s' }}>
                {e.aliases.length > 0 && (
                  <div style={{ fontFamily: font.sans, fontSize: 11, color: color.faint }}>
                    also: {e.aliases.join(' · ')}
                  </div>
                )}
                {/* Empty on the seeded rows on purpose: forty form guides
                    written from memory is forty chances to teach a lift wrong. */}
                <div style={{ fontFamily: font.sans, fontSize: 11.5, color: e.steps ? color.muted : color.faint, marginTop: 6, lineHeight: 1.55 }}>
                  {e.steps ?? 'No how-to yet — ask the agent and keep what it finds.'}
                </div>
                {e.note && (
                  <div style={{ fontFamily: font.sans, fontSize: 11.5, color: color.muted, marginTop: 5 }}>
                    {e.note}
                  </div>
                )}
                {e.sourceUrl && (
                  <a
                    href={e.sourceUrl}
                    target="_blank"
                    rel="noreferrer"
                    style={{ display: 'inline-flex', alignItems: 'center', gap: 2, marginTop: 8, fontFamily: font.sans, fontSize: 12.5, color: color.brand }}
                  >
                    Watch it
                    <ArrowUpRight size={13} aria-hidden />
                  </a>
                )}
                <div style={{ fontFamily: font.sans, fontSize: 11, color: color.faint, marginTop: 7 }}>
                  from {e.source}
                </div>
              </div>
            )}
          </div>
        ))}

        <div style={{ borderTop: `1px solid ${color.lineSoft}` }}>
          {adding ? (
            <div style={{ padding: '2px 13px 13px', animation: 'fadeup 0.2s' }}>
              {[
                ['Name', 'name', 'Copenhagen plank'],
                ['Muscle group', 'muscle_group', 'legs, chest, core…'],
                ['Equipment', 'equipment', 'barbell, bodyweight, none…'],
                ['Minutes', 'typical_minutes', '10'],
                ['How to', 'steps', 'what to actually do'],
                ['Link', 'source_url', 'the YouTube or Instagram link'],
              ].map(([name, key, placeholder]) => (
                <div key={key} style={{ marginTop: 10 }}>
                  <span style={label}>{name}</span>
                  <input
                    value={form[key as keyof typeof form]}
                    placeholder={placeholder}
                    onChange={(ev) => setForm({ ...form, [key]: ev.target.value })}
                    style={input}
                  />
                </div>
              ))}
              <div style={{ marginTop: 10 }}>
                <span style={label}>Type</span>
                <select
                  value={form.kind}
                  aria-label="Type"
                  onChange={(ev) => setForm({ ...form, kind: ev.target.value })}
                  style={{ ...input, fontFamily: font.sans }}
                >
                  {KINDS.map((k) => (
                    <option key={k} value={k}>
                      {k}
                    </option>
                  ))}
                </select>
              </div>
              <div style={{ display: 'flex', gap: 7, marginTop: 12 }}>
                <button
                  type="button"
                  disabled={!form.name.trim() || busy}
                  onClick={() => void add()}
                  style={{
                    fontFamily: font.sans,
                    fontSize: 11.5,
                    padding: '6px 14px',
                    borderRadius: 14,
                    border: 'none',
                    cursor: form.name.trim() && !busy ? 'pointer' : 'default',
                    background: form.name.trim() && !busy ? color.brand : color.ringIdle,
                    color: form.name.trim() && !busy ? color.white : color.faint,
                  }}
                >
                  Add
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setAdding(false);
                    setForm({ ...EMPTY });
                  }}
                  style={{
                    fontFamily: font.sans,
                    fontSize: 11.5,
                    padding: '6px 12px',
                    borderRadius: 14,
                    border: `1px solid ${color.border}`,
                    background: color.paper,
                    color: color.muted,
                    cursor: 'pointer',
                  }}
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <button
              type="button"
              className="hov-tint"
              onClick={() => {
                setOpen(null);
                setAdding(true);
              }}
              style={{
                width: '100%',
                display: 'block',
                textAlign: 'left',
                padding: '12px 14px',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                fontFamily: font.sans,
                fontSize: 13.5,
                fontWeight: 500,
                color: color.brand,
              }}
            >
              <Plus size={15} aria-hidden style={{ verticalAlign: '-2px', marginRight: 6 }} />
              Add an exercise
            </button>
          )}
        </div>
      </div>

      <div style={{ fontFamily: font.sans, fontSize: 11.5, color: color.muted, padding: '10px 2px 0', lineHeight: 1.5 }}>
        Whether you trained is a habit — yes or no, on the Diet card. This is the
        library the agent suggests from.
      </div>
    </>
  );
}
