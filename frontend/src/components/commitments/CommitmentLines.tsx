import { useState, type ReactNode } from 'react';
import { color, font } from '../../theme';
import Dot from '../messages/Dot';
import { Fig } from '../messages/parts';
import { TrayActions, TrayToggle, type TrayAction } from '../messages/Tray';
import { carriedLabel, inr, ordinal } from './kit';
import type { CommitmentRow } from '../../data/api';
import { useBack } from '../../state/nav';

/** What a line's ⋮ can do. Each is one write; none is optimistic. */
export interface LineHandlers {
  onEdit: (c: CommitmentRow) => void;
  onSkip: (c: CommitmentRow, skipped: boolean) => void;
  onRepeat: (c: CommitmentRow, repeats: boolean) => void;
  onDelete: (c: CommitmentRow) => void;
}

interface Props {
  items: CommitmentRow[];
  /** Past months are what was recorded: no ⋮ at all. */
  editable: boolean;
  handlers: LineHandlers;
  /** Tighter rows, for a card in the thread. */
  compact?: boolean;
}

const small = { fontFamily: font.sans, fontSize: 12, lineHeight: '16px', color: color.faint } as const;

/** "due 5th · from September" — only what is true of the line, in the order a person looks. */
function subLine(c: CommitmentRow): string {
  return [
    c.source === 'borrowing' ? 'borrowed' : null,
    carriedLabel(c),
    c.dueDay != null ? `due ${ordinal(c.dueDay)}` : null,
    c.source === 'commitment' ? (c.repeats ? 'every month' : 'this month only') : null,
  ]
    .filter(Boolean)
    .join(' · ');
}

/** The right-hand side: the amount, and under it what has gone against it. */
function Figures({ c }: { c: CommitmentRow }) {
  const struck = c.settled || c.skipped;
  let under: string;
  if (c.skipped) under = 'skipped this month';
  else if (c.settled) under = c.overPaise > 0 ? `paid · +${inr(c.overPaise)}` : 'paid';
  else if (c.paidPaise > 0) under = `${inr(c.paidPaise)} paid · owed ${inr(c.owedPaise)}`;
  else under = `owed ${inr(c.owedPaise)}`;
  return (
    <span style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', flex: '0 0 auto' }}>
      <span style={{ display: 'inline-flex', alignItems: 'center' }}>
        {/* Amber means inferred and nothing else: this amount was carried from
            last month, not stated, until it is edited or paid. */}
        {c.rolled && !struck && <Dot />}
        <Fig size={14.5} weight={600} struck={struck}>
          {inr(c.expectedPaise)}
        </Fig>
      </span>
      <span style={small}>{under}</span>
    </span>
  );
}

/**
 * The commitment lines: open ones first, then settled ones struck, then the
 * skipped group. Used by Your data and by the chat card, so a line reads the
 * same wherever it is drawn. Each editable line has a ⋮ with Edit, Skip this
 * month / Unskip, Stop repeating / Repeat and Delete — and Delete asks first,
 * because there is no undo.
 */
export default function CommitmentLines({ items, editable, handlers, compact = false }: Props) {
  const [open, setOpen] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<string | null>(null);
  useBack(open != null, () => setOpen(null));
  useBack(confirming != null, () => setConfirming(null));

  const live = items.filter((c) => !c.skipped);
  const groups: { key: string; label?: string; rows: CommitmentRow[] }[] = [
    { key: 'open', rows: live.filter((c) => !c.settled) },
    { key: 'settled', rows: live.filter((c) => c.settled) },
    { key: 'skipped', label: 'Skipped', rows: items.filter((c) => c.skipped) },
  ].filter((g) => g.rows.length);

  const actionsFor = (c: CommitmentRow): TrayAction[] => [
    { label: 'Edit', onClick: () => { setOpen(null); handlers.onEdit(c); } },
    c.skipped
      ? { label: 'Unskip', onClick: () => handlers.onSkip(c, false) }
      : { label: 'Skip this month', onClick: () => handlers.onSkip(c, true) },
    c.repeats
      ? { label: 'Stop repeating', onClick: () => handlers.onRepeat(c, false) }
      : { label: 'Repeat', onClick: () => handlers.onRepeat(c, true) },
    { label: 'Delete', tone: 'danger', onClick: () => { setOpen(null); setConfirming(c.id); } },
  ];

  const confirm = (c: CommitmentRow): ReactNode => (
    <div style={{ padding: '0 0 10px', animation: 'fadeup 0.2s' }}>
      <div style={{ fontFamily: font.sans, fontSize: 13, lineHeight: '18px', color: color.muted, marginBottom: 8 }}>
        {c.repeats
          ? `Delete ${c.name}? It stops coming back, and its payments become ordinary spending. This can't be undone. To leave out only this month, skip it.`
          : `Delete ${c.name}? Its payments become ordinary spending. This can't be undone.`}
      </div>
      <TrayActions
        align="start"
        pad="0"
        actions={[
          { label: 'Delete', tone: 'danger', onClick: () => { setConfirming(null); handlers.onDelete(c); } },
          ...(c.repeats && !c.skipped
            ? [{ label: 'Skip this month', onClick: () => { setConfirming(null); handlers.onSkip(c, true); } }]
            : []),
          { label: 'Cancel', onClick: () => setConfirming(null) },
        ]}
      />
    </div>
  );

  return (
    <div>
      {groups.map((g) => (
        <div key={g.key}>
          {g.label && (
            <div style={{ ...small, fontWeight: 500, padding: compact ? '10px 0 2px' : '14px 0 4px' }}>{g.label}</div>
          )}
          {g.rows.map((c, i) => {
            const struck = c.settled || c.skipped;
            const mine = c.source === 'commitment' && editable;
            return (
              <div
                key={c.id}
                data-commitment={c.id}
                style={{ borderTop: i === 0 && !g.label && g === groups[0] ? undefined : `1px solid ${color.lineSoft}` }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: compact ? '8px 0' : '11px 0' }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div
                      style={{
                        fontFamily: font.sans,
                        fontSize: 14.5,
                        lineHeight: '19px',
                        fontWeight: 500,
                        color: struck ? color.faint : color.ink,
                        textDecoration: c.settled && !c.skipped ? 'line-through' : undefined,
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                      }}
                    >
                      {c.name}
                    </div>
                    {subLine(c) && <div style={{ ...small, marginTop: 1 }}>{subLine(c)}</div>}
                  </div>
                  <Figures c={c} />
                  {mine ? (
                    <TrayToggle
                      open={open === c.id}
                      onToggle={() => {
                        setConfirming(null);
                        setOpen(open === c.id ? null : c.id);
                      }}
                      label={c.name}
                    />
                  ) : (
                    <div style={{ width: 28, flex: '0 0 auto' }} />
                  )}
                </div>
                {mine && open === c.id && <TrayActions actions={actionsFor(c)} pad="0 0 10px" />}
                {mine && confirming === c.id && confirm(c)}
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}
