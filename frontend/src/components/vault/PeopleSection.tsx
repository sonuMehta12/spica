import { useState, type ReactNode } from 'react';
import { Plus } from '@phosphor-icons/react';
import { color, font } from '../../theme';
import Dot from '../messages/Dot';
import type { PersonKind, PersonRow } from '../../data/api';
import { useBack } from '../../state/nav';

/**
 * Your data → People. spec/done/people.md.
 *
 * A counterparty row plus what the ledger knows about it. Only five things
 * here are stored — kind, display name, relation, usual category, note — and
 * everything with a number beside it is computed per request, so deleting a
 * payment corrects the row with no write anywhere.
 *
 * **Unsorted never nags.** No badge, no count to clear: a shop with no kind
 * breaks nothing, and the rows that matter announce themselves when money
 * comes back. Classifying is a one-time pass, then a trickle.
 *
 * Adding and editing render the *same* fields, because they are the same five
 * columns; adding only puts `raw_name` on top, which is the one thing that can
 * never be changed afterwards.
 */
interface Props {
  people: PersonRow[];
  onFile: (id: string, patch: Edits) => Promise<boolean>;
  onAdd: (name: string, patch: Edits) => Promise<boolean>;
}

export interface Edits {
  kind?: PersonKind | null;
  display_name?: string | null;
  relation?: string | null;
  note?: string | null;
  default_category?: string | null;
}

type Tab = 'person' | 'shop' | 'service' | 'unsorted';

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

const button = (on: boolean) => ({
  fontFamily: font.sans,
  fontSize: 11.5,
  padding: '6px 14px',
  borderRadius: 14,
  border: 'none',
  cursor: on ? 'pointer' : 'default',
  background: on ? color.brand : color.ringIdle,
  color: on ? color.white : color.faint,
});

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const shortDate = (iso: string) => `${Number(iso.slice(8, 10))} ${MONTHS[Number(iso.slice(5, 7)) - 1]}`;
const rupees = (paise: number) => `₹${Math.round(paise / 100).toLocaleString('en-IN')}`;

const KINDS: PersonKind[] = ['person', 'shop', 'service'];
const title = (s: string) => s[0].toUpperCase() + s.slice(1);

/** The five stored fields, as the form holds them. */
type Draft = {
  kind: string;
  display_name: string;
  relation: string;
  default_category: string;
  note: string;
};
const EMPTY: Draft = { kind: '', display_name: '', relation: '', default_category: '', note: '' };
const draftOf = (p: PersonRow): Draft => ({
  kind: p.kind ?? '',
  display_name: p.displayName ?? '',
  relation: p.relation ?? '',
  default_category: p.defaultCategory ?? '',
  note: p.note ?? '',
});
/** Only what changed. Empty string clears the column; absent leaves it alone. */
const diff = (d: Draft, was: Draft): Edits =>
  Object.fromEntries(
    (Object.keys(d) as (keyof Draft)[])
      .filter((k) => d[k].trim() !== was[k])
      .map((k) => [k, d[k].trim() || null]),
  );

function Labelled({ name, hint, children }: { name: string; hint?: string; children: ReactNode }) {
  return (
    <div style={{ marginTop: 10 }}>
      <span style={label}>
        {name}
        {hint && (
          <span style={{ color: color.faint }}>
            {'  '}
            {hint}
          </span>
        )}
      </span>
      {children}
    </div>
  );
}

function Field({
  name,
  hint,
  value,
  placeholder,
  onChange,
}: {
  name: string;
  hint?: string;
  value: string;
  placeholder?: string;
  onChange: (v: string) => void;
}) {
  return (
    <Labelled name={name} hint={hint}>
      <input value={value} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} style={input} />
    </Labelled>
  );
}

/**
 * The five columns, identical whether you are adding or editing.
 *
 * `kind` is a dropdown, not a row of pills: pills were the same shape as the
 * tabs above the list, so the field read as navigation — and one of them filed
 * a sister as a shop.
 */
function PersonFields({
  draft,
  onChange,
  namePlaceholder,
}: {
  draft: Draft;
  onChange: (d: Draft) => void;
  namePlaceholder?: string;
}) {
  const set = (k: keyof Draft) => (v: string) => onChange({ ...draft, [k]: v });
  return (
    <>
      <Labelled name="What is this">
        <select
          value={draft.kind}
          aria-label="What is this"
          onChange={(e) => set('kind')(e.target.value)}
          style={{ ...input, fontFamily: font.sans }}
        >
          <option value="">Not said</option>
          {KINDS.map((k) => (
            <option key={k} value={k}>
              {title(k)}
            </option>
          ))}
        </select>
      </Labelled>
      <Field
        name="What you call them"
        value={draft.display_name}
        placeholder={namePlaceholder ?? 'Didi, chai wala…'}
        onChange={set('display_name')}
      />
      <Field
        name="Relation"
        hint="your word for it"
        value={draft.relation}
        placeholder="dost, badi behen, landlord…"
        onChange={set('relation')}
      />
      <Field
        name="Usual category"
        hint="where their payments land"
        value={draft.default_category}
        placeholder="Dost & Bahar, Transport, Rent…"
        onChange={set('default_category')}
      />
      <Field
        name="Note"
        value={draft.note}
        placeholder="anything worth remembering"
        onChange={set('note')}
      />
    </>
  );
}

export default function PeopleSection({ people, onFile, onAdd }: Props) {
  const [view, setView] = useState<Tab>('person');
  const [open, setOpen] = useState<string | null>(null);
  const [form, setForm] = useState<Draft>(EMPTY);
  const [adding, setAdding] = useState(false);
  const [newName, setNewName] = useState('');
  const [newForm, setNewForm] = useState<Draft>(EMPTY);
  const [busy, setBusy] = useState(false);
  const of = (t: Tab) =>
    t === 'unsorted' ? people.filter((p) => p.kind == null) : people.filter((p) => p.kind === t);
  const shown = of(view);
  // Back closes the open person, or the new one, before it leaves People —
  // the person only while their tab is showing them.
  useBack(open != null && shown.some((p) => p.id === open), () => setOpen(null));
  useBack(adding, () => setAdding(false));

  /**
   * Only one editor at a time. Two open panels put two identical field sets on
   * screen, and there is no way to tell which one a keystroke belongs to.
   */
  const expand = (p: PersonRow) => {
    const same = open === p.id;
    setAdding(false);
    setOpen(same ? null : p.id);
    if (!same) setForm(draftOf(p));
  };

  const openAdd = () => {
    setOpen(null);
    setNewForm(EMPTY);
    setAdding(true);
  };

  /**
   * Everything commits together. The kind used to save on its own tap, which
   * re-filed the row into another tab mid-edit and stranded whatever was still
   * being typed — so one Save, and the row moves once.
   */
  const commit = async (p: PersonRow) => {
    const body = diff(form, draftOf(p));
    if (Object.keys(body).length === 0) return;
    setBusy(true);
    await onFile(p.id, body);
    setBusy(false);
  };

  const add = async () => {
    const clean = newName.trim();
    if (!clean) return;
    setBusy(true);
    const ok = await onAdd(clean, diff(newForm, EMPTY));
    setBusy(false);
    if (ok) {
      setNewName('');
      setNewForm(EMPTY);
      setAdding(false);
    }
  };

  const tab = (id: Tab, text: string) => (
    <button
      key={id}
      type="button"
      onClick={() => setView(id)}
      style={{
        fontFamily: font.sans,
        fontSize: 11.5,
        padding: '5px 12px',
        borderRadius: 14,
        border: `1px solid ${view === id ? color.brand : color.border}`,
        background: view === id ? color.brand : color.white,
        color: view === id ? color.white : color.muted,
        cursor: 'pointer',
      }}
    >
      {text}
    </button>
  );

  return (
    <>
      <div style={{ display: 'flex', gap: 7, marginBottom: 4, flexWrap: 'wrap' }}>
        {tab('person', `People · ${of('person').length}`)}
        {tab('shop', `Shops · ${of('shop').length}`)}
        {tab('service', `Services · ${of('service').length}`)}
        {tab('unsorted', `Unsorted · ${of('unsorted').length}`)}
      </div>

      <div style={shell}>
        {shown.length === 0 && (
          <div style={{ padding: 14, fontSize: 13.5, color: color.muted }}>
            {view === 'unsorted'
              ? 'Everyone is filed. Nothing to do here.'
              : `No ${view === 'person' ? 'people' : view + 's'} yet — tap a row under Unsorted to file it.`}
          </div>
        )}

        {shown.map((p, i) => {
          const owed = p.stillOut > 0 || p.youOwe > 0;
          const dirty = open === p.id && Object.keys(diff(form, draftOf(p))).length > 0;
          return (
            <div key={p.id} style={{ borderTop: i ? `1px solid ${color.lineSoft}` : 'none' }}>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, padding: '11px 13px' }}>
                <button
                  type="button"
                  className="hov-tint"
                  onClick={() => expand(p)}
                  aria-expanded={open === p.id}
                  style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', textAlign: 'left', minWidth: 0, flex: 1 }}
                >
                  <span style={{ fontSize: 13.5, fontWeight: 500, color: color.ink }}>{p.name}</span>
                  {p.relation && (
                    <span style={{ fontFamily: font.sans, fontSize: 11, color: color.faint, marginLeft: 6 }}>
                      {p.relation}
                    </span>
                  )}
                  <span style={{ display: 'block', fontFamily: font.sans, fontSize: 11, marginTop: 3, color: color.faint }}>
                    {p.txCount > 0
                      ? `${p.txCount}×${p.lastDay ? ` · ${shortDate(p.lastDay)}` : ''}`
                      : 'no payments'}
                    {p.typicalDays != null && ` · usually ${p.typicalDays}d to return`}
                    {/* The kind is the agent's guess until you file it: the
                        dot says so, before the value it worked out. */}
                    {p.kind != null && !p.confirmed && (
                      <>
                        {' · '}
                        <Dot />
                        {p.kind}
                      </>
                    )}
                  </span>
                </button>

                {/* One column, two meanings — outstanding money and money
                    already spent — so every number carries its own word. */}
                <span style={{ textAlign: 'right', minWidth: 78, flex: '0 0 auto' }}>
                  <span
                    style={{
                      display: 'block',
                      fontFamily: font.sans,
                      fontSize: 13.5,
                      fontWeight: owed ? 500 : 400,
                      whiteSpace: 'nowrap',
                      color: p.stillOut > 0 ? color.ink : p.youOwe > 0 ? color.red : color.muted,
                    }}
                  >
                    {p.stillOut > 0
                      ? rupees(p.stillOut)
                      : p.youOwe > 0
                        ? rupees(p.youOwe)
                        : p.sent > 0
                          ? rupees(p.sent)
                          : '—'}
                  </span>
                  <span
                    style={{
                      display: 'block',
                      fontFamily: font.sans,
                      fontSize: 11,
                      whiteSpace: 'nowrap',
                      marginTop: 2,
                      color: color.faint,
                    }}
                  >
                    {p.stillOut > 0 ? 'still out' : p.youOwe > 0 ? 'you owe' : p.sent > 0 ? 'sent' : ''}
                  </span>
                </span>
              </div>

              {open === p.id && (
                <div style={{ padding: '0 13px 13px', animation: 'fadeup 0.2s' }}>
                  {/* The ledger's own words. `received`, not `is_peer` — that
                      flag was hand-set on the imported rows and says money came
                      back from people who have never repaid anything. */}
                  <div style={{ fontFamily: font.sans, fontSize: 11.5, color: color.muted, lineHeight: 1.7 }}>
                    {p.txCount > 0 ? `sent ${rupees(p.sent)}` : 'nothing has moved yet'}
                    {p.received > 0 && ` · back ${rupees(p.received)}`}
                    {p.stillOut > 0 && ` · ${rupees(p.stillOut)} still out`}
                    {p.youOwe > 0 && ` · you owe ${rupees(p.youOwe)}`}
                  </div>

                  <PersonFields draft={form} onChange={setForm} namePlaceholder={p.rawName} />

                  <div style={{ display: 'flex', alignItems: 'flex-end', gap: 10, marginTop: 12 }}>
                    {/* raw_name is shown, never edited: it is how the next
                        notification finds this row again. */}
                    <span style={{ flex: 1, fontFamily: font.sans, fontSize: 11, color: color.faint, lineHeight: 1.6 }}>
                      Pays as <span style={{ color: color.muted }}>{p.rawName}</span>
                      <br />
                      The name a notification matches on — it cannot be changed.
                    </span>
                    <button
                      type="button"
                      disabled={!dirty || busy}
                      onClick={() => void commit(p)}
                      style={{ ...button(dirty && !busy), flex: '0 0 auto' }}
                    >
                      Save
                    </button>
                  </div>
                </div>
              )}
            </div>
          );
        })}

        {/* Almost everyone arrives from a payment. This is for the one who does
            not: cash you owe, or a friend you are about to lend to. */}
        <div style={{ borderTop: shown.length ? `1px solid ${color.lineSoft}` : 'none' }}>
          {adding ? (
            <div style={{ padding: '2px 13px 13px', animation: 'fadeup 0.2s' }}>
              {/* The only field that exists here and not in the editor: once
                  written it is the match key, so it is set exactly once. */}
              <Field
                name="Name"
                hint="as their payments will show it"
                value={newName}
                placeholder="MOHD WASIM"
                onChange={setNewName}
              />
              <PersonFields draft={newForm} onChange={setNewForm} />
              <div style={{ display: 'flex', gap: 7, marginTop: 12 }}>
                <button
                  type="button"
                  disabled={!newName.trim() || busy}
                  onClick={() => void add()}
                  style={button(!!newName.trim() && !busy)}
                >
                  Add
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setAdding(false);
                    setNewName('');
                    setNewForm(EMPTY);
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
              onClick={openAdd}
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
              Add someone
            </button>
          )}
        </div>
      </div>
    </>
  );
}
