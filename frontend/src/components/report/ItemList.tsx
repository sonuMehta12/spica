import { useState, type KeyboardEvent } from 'react';
import { DotsThreeVertical } from '@phosphor-icons/react';
import { color, font, radius } from '../../theme';
import Dot from '../messages/Dot';
import { trayBtn } from '../messages/Tray';
import { useBack } from '../../state/nav';

export type Tone = 'good' | 'bad' | 'warn' | 'muted';
/** What a row's ⋮ acts on. Absent = a read-only row (sleep). */
export type RowKind = 'paisa' | 'diet' | 'habit' | 'task' | 'repayment';

/**
 * A row-specific action in the ⋮ tray, ahead of Edit and Delete. With a
 * `prompt` it opens a one-field editor in place (Repaid: the amount) and runs
 * with what was typed; `run` returning false keeps the editor open and shows
 * the prompt's `refused` line.
 */
export interface ItemAction {
  label: string;
  tone?: 'good' | 'muted';
  prompt?: { initial: string; prefix?: string; hint: string; refused: string };
  /** A pick from a short list — Counts toward…: tapping shows the choices in place of the tray. */
  choices?: { label: string; run: () => void }[];
  run: (value?: string) => void | boolean | Promise<boolean | void>;
}

export interface Item {
  id: string;
  label: string;
  sub?: string;
  /** The commitment a payment counts toward, after the sub: `· Rent`, amber-dotted when only guessed. */
  link?: { name: string; inferred: boolean };
  valueStr: string;
  tone: Tone;
  kind?: RowKind;
  /** Present when the row can be edited from the composer. */
  editText?: string;
  actions?: ItemAction[];
}

/**
 * Only "bad" takes a colour. A good number needs no applause, and amber is
 * only ever the estimate dot — so "due today" is plain ink, not a warning.
 */
const TONE: Record<Tone, string> = {
  good: color.ink,
  bad: color.red,
  warn: color.ink,
  muted: color.faint,
};

interface Props {
  items: Item[];
  onEdit?: (kind: 'paisa' | 'diet', id: string, text: string) => void;
  onDelete?: (kind: RowKind, id: string) => void;
}

/**
 * The selected tab's contents. Money, meals, habits and sleep all reduce to
 * label · sub · value, so one list renders every tab in the report — and one
 * ⋮ tray, the same as the chat table's, so the two cannot drift.
 */
export default function ItemList({ items, onEdit, onDelete }: Props) {
  const [open, setOpen] = useState<string | null>(null);
  /** An action's inline prompt, if one is showing: which row, which action, the draft. */
  const [prompt, setPrompt] = useState<{ row: string; action: string; draft: string; refused: boolean } | null>(null);
  /** An action's list of choices, if one is showing: which row, which action. */
  const [picking, setPicking] = useState<{ row: string; action: string } | null>(null);
  // Back closes, innermost first: the amount being typed (Repaid, Paid back),
  // the list of choices, the row's tray — and only then the Report. Only what
  // is on screen: a tab switch can leave a row's state behind, and a press
  // must never close something unseen.
  const shown = (id: string | undefined | null) => id != null && items.some((it) => it.id === id && it.kind);
  useBack(shown(open), () => {
    setOpen(null);
    setPicking(null);
    setPrompt(null);
  });
  useBack(picking != null && picking.row === open && shown(picking.row), () => setPicking(null));
  useBack(shown(prompt?.row), () => setPrompt(null));

  const runPrompt = async (act: ItemAction) => {
    if (!prompt) return;
    const ok = await act.run(prompt.draft);
    if (ok === false) setPrompt({ ...prompt, refused: true });
    else {
      setPrompt(null);
      setOpen(null);
    }
  };

  if (!items.length) {
    return (
      <div
        style={{
          background: color.white,
          border: `1px solid ${color.line}`,
          borderRadius: radius.card,
          padding: '14px',
          fontSize: 13.5,
          color: color.muted,
        }}
      >
        Nothing in this period.
      </div>
    );
  }

  return (
    <div
      style={{
        background: color.white,
        border: `1px solid ${color.line}`,
        borderRadius: radius.card,
        overflow: 'hidden',
      }}
    >
      {items.map((it, i) => (
        <div key={it.id} style={{ borderTop: i ? `1px solid ${color.lineSoft}` : 'none' }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'baseline',
              justifyContent: 'space-between',
              gap: 10,
              padding: '10px 6px 10px 14px',
            }}
          >
            {/* The label takes the slack, so every amount ends at the same edge
                instead of floating wherever its label's width left it. */}
            <span style={{ minWidth: 0, flex: 1 }}>
              <span style={{ fontSize: 13.5 }}>{it.label}</span>
              {it.sub && (
                <span
                  style={{ fontFamily: font.sans, fontSize: 12, color: color.faint, marginLeft: 6 }}
                >
                  {it.sub}
                  {it.link && (
                    <>
                      {' · '}
                      {it.link.inferred && <Dot />}
                      {it.link.name}
                    </>
                  )}
                </span>
              )}
            </span>
            <span
              style={{
                fontFamily: font.sans,
                fontSize: 13.5,
                fontWeight: 500,
                whiteSpace: 'nowrap',
                minWidth: 72,
                textAlign: 'right',
                color: TONE[it.tone],
              }}
            >
              {it.valueStr}
            </span>
            {it.kind && onDelete && (
              <button
                type="button"
                onClick={() => setOpen((o) => (o === it.id ? null : it.id))}
                aria-label={`Options — ${it.label}`}
                aria-expanded={open === it.id}
                className="hov-tint"
                style={{
                  width: 28,
                  height: 28,
                  borderRadius: '50%',
                  background: open === it.id ? color.lineSoft : 'none',
                  border: 'none',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  padding: 0,
                  alignSelf: 'center',
                  flex: '0 0 auto',
                }}
              >
                <DotsThreeVertical size={18} weight="bold" color={color.faint} aria-hidden />
              </button>
            )}
          </div>

          {open === it.id && it.kind && picking?.row === it.id && (() => {
            const act = it.actions?.find((a) => a.label === picking.action);
            return (
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', padding: '0 8px 10px', justifyContent: 'flex-end', animation: 'fadeup 0.2s', alignItems: 'center' }}>
                <span style={{ fontFamily: font.sans, fontSize: 12, color: color.faint, marginRight: 'auto', paddingLeft: 6 }}>
                  {act?.choices?.length ? act.label : 'No other commitment this month'}
                </span>
                {act?.choices?.map((c) => (
                  <button
                    key={c.label}
                    type="button"
                    style={trayBtn}
                    onClick={() => {
                      c.run();
                      setPicking(null);
                      setOpen(null);
                    }}
                  >
                    {c.label}
                  </button>
                ))}
                <button type="button" style={trayBtn} onClick={() => setPicking(null)}>
                  Cancel
                </button>
              </div>
            );
          })()}

          {open === it.id && it.kind && picking?.row !== it.id && (
            <div
              style={{
                display: 'flex',
                gap: 8,
                flexWrap: 'wrap',
                padding: '0 8px 10px',
                justifyContent: 'flex-end',
                animation: 'fadeup 0.2s',
              }}
            >
              {it.actions?.map((act) => (
                <button
                  key={act.label}
                  type="button"
                  style={{
                    ...trayBtn,
                    ...(act.tone === 'good'
                      ? { color: color.brand, background: color.brandTint, borderColor: color.brandTint }
                      : {}),
                  }}
                  onClick={() => {
                    if (act.choices) {
                      setPicking({ row: it.id, action: act.label });
                      return;
                    }
                    if (act.prompt) {
                      setPrompt({ row: it.id, action: act.label, draft: act.prompt.initial, refused: false });
                      return;
                    }
                    void act.run();
                    setOpen(null);
                  }}
                >
                  {act.label}
                </button>
              ))}
              {it.editText && onEdit && (it.kind === 'paisa' || it.kind === 'diet') && (
                <button
                  type="button"
                  style={trayBtn}
                  onClick={() => {
                    onEdit(it.kind as 'paisa' | 'diet', it.id, it.editText!);
                    setOpen(null);
                  }}
                >
                  Edit
                </button>
              )}
              {it.kind !== 'repayment' && (
                <button
                  type="button"
                  style={{ ...trayBtn, color: color.red, background: color.redSurface, borderColor: color.redBorder }}
                  onClick={() => {
                    onDelete?.(it.kind!, it.id);
                    setOpen(null);
                  }}
                >
                  Delete
                </button>
              )}
            </div>
          )}

          {prompt && prompt.row === it.id && (() => {
            const act = it.actions?.find((a) => a.label === prompt.action);
            if (!act?.prompt) return null;
            const keys = (e: KeyboardEvent<HTMLInputElement>) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                void runPrompt(act);
              } else if (e.key === 'Escape') {
                e.preventDefault();
                setPrompt(null);
              }
            };
            return (
              <div style={{ padding: '0 14px 12px', animation: 'fadeup 0.2s' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  {act.prompt.prefix && (
                    <span style={{ fontFamily: font.sans, fontSize: 13.5, color: color.muted }}>{act.prompt.prefix}</span>
                  )}
                  <input
                    autoFocus
                    inputMode="decimal"
                    value={prompt.draft}
                    onChange={(e) => setPrompt({ ...prompt, draft: e.target.value, refused: false })}
                    onKeyDown={keys}
                    onFocus={(e) => e.currentTarget.select()}
                    style={{
                      fontFamily: font.sans,
                      fontSize: 14,
                      color: color.ink,
                      background: color.white,
                      border: `1px solid ${color.border}`,
                      borderRadius: 10,
                      padding: '6px 10px',
                      width: 110,
                      outline: 'none',
                    }}
                  />
                  <span style={{ flex: 1 }} />
                  <button type="button" style={trayBtn} onClick={() => setPrompt(null)}>
                    Cancel
                  </button>
                  <button
                    type="button"
                    className="hov-brand"
                    style={{ ...trayBtn, color: color.white, background: color.brand, borderColor: color.brand }}
                    onClick={() => void runPrompt(act)}
                  >
                    {act.label}
                  </button>
                </div>
                <div style={{ fontFamily: font.sans, fontSize: 12, marginTop: 6, color: prompt.refused ? color.red : color.faint }}>
                  {prompt.refused ? act.prompt.refused : act.prompt.hint}
                </div>
              </div>
            );
          })()}
        </div>
      ))}
    </div>
  );
}
