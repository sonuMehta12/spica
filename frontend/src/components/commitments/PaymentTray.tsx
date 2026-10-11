import { useState, type CSSProperties, type ReactNode } from 'react';
import { color, font } from '../../theme';
import Dot from '../messages/Dot';
import { Quiet, TextBtn } from '../messages/parts';
import { TrayActions, type TrayAction } from '../messages/Tray';
import type { CommitmentRow } from '../../data/api';
import type { Tx } from '../../types';
import { useBack } from '../../state/nav';

/** The three things a payment's ⋮ can say about commitments. */
export interface LinkHandlers {
  /** Count the payment toward a commitment (confirms a guess too), or `null`: Not a commitment. */
  onLink: (txId: string, commitmentId: string | null) => void;
  /** Open the sheet pre-filled from the payment; saving makes the line and counts the payment. */
  onMake: (tx: Tx) => void;
}

/** Only a real expense can count toward a commitment — never money in, never udhaar. */
export const canCount = (t: Tx) => t.kind === 'expense' && !t.credit;

/** "Counts toward Rent, I guessed · Right · Not this" — the amber dot says it was inferred. */
export function LinkGuess({
  name,
  onRight,
  onNot,
  pad = '0 0 8px',
  style,
}: {
  name: string;
  onRight: () => void;
  onNot: () => void;
  pad?: string;
  style?: CSSProperties;
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: pad, animation: 'fadeup 0.2s', ...style }}>
      <span style={{ flex: 1, minWidth: 0, display: 'flex', alignItems: 'center' }}>
        <Dot />
        <span style={{ fontFamily: font.sans, fontSize: 13, lineHeight: '18px', color: color.muted }}>
          Counts toward {name}, I guessed
        </span>
      </span>
      <TextBtn label="Right" tone={color.brand} onClick={onRight} />
      <TextBtn label="Not this" onClick={onNot} />
    </div>
  );
}

/**
 * The payment tray's commitment actions, then whatever the host adds (Edit,
 * Delete). *Counts toward…* picks from this month's lines; *Not a commitment*
 * shows when it is linked; *Make this a commitment* when it is not. A guessed
 * link says so above the chips, with Right and Not this.
 */
export default function PaymentTray({
  tx,
  targets,
  handlers,
  rest,
  pad = '0 0 9px',
}: {
  tx: Tx;
  /** This month's commitments a payment can count toward. */
  targets: CommitmentRow[];
  handlers: LinkHandlers;
  rest: TrayAction[];
  pad?: string;
}) {
  const [picking, setPicking] = useState(false);
  useBack(picking, () => setPicking(false));
  const counts = canCount(tx);
  const linked = Boolean(tx.commitmentId);
  const current = targets.find((c) => c.id === tx.commitmentId);
  const options = targets.filter((c) => c.id !== tx.commitmentId);

  if (picking) {
    return (
      <div style={{ padding: pad, animation: 'fadeup 0.2s' }}>
        <div style={{ fontFamily: font.sans, fontSize: 12, lineHeight: '16px', color: color.faint, textAlign: 'right', marginBottom: 6 }}>
          {options.length ? 'Counts toward' : 'No other commitment this month'}
        </div>
        <TrayActions
          pad="0"
          actions={[
            ...options.map((c) => ({
              label: c.name,
              onClick: () => {
                setPicking(false);
                handlers.onLink(tx.id, c.id);
              },
            })),
            { label: 'Cancel', onClick: () => setPicking(false) },
          ]}
        />
      </div>
    );
  }

  const actions: TrayAction[] = [];
  if (counts) {
    actions.push({ label: 'Counts toward…', onClick: () => setPicking(true) });
    actions.push(
      linked
        ? { label: 'Not a commitment', onClick: () => handlers.onLink(tx.id, null) }
        : { label: 'Make this a commitment', onClick: () => handlers.onMake(tx) },
    );
  }
  actions.push(...rest);

  return (
    <>
      {counts && linked && tx.commitmentInferred && (
        <LinkGuess
          name={current?.name ?? 'a commitment'}
          onRight={() => tx.commitmentId && handlers.onLink(tx.id, tx.commitmentId)}
          onNot={() => handlers.onLink(tx.id, null)}
        />
      )}
      <TrayActions actions={actions} pad={pad} />
    </>
  );
}

/**
 * The same three actions as quiet text under a confirm card's receipt: the
 * guess (when the link was inferred) over a hairline, then Counts toward…, Not
 * a commitment or Make this a commitment beside whatever the card already
 * offers (`children`, its Undo).
 */
export function PaymentLinkQuiet({
  tx,
  targets,
  handlers,
  children,
}: {
  tx: Tx;
  targets: CommitmentRow[];
  handlers: LinkHandlers;
  children?: ReactNode;
}) {
  const [picking, setPicking] = useState(false);
  useBack(picking, () => setPicking(false));
  const counts = canCount(tx);
  const linked = Boolean(tx.commitmentId);
  const current = targets.find((c) => c.id === tx.commitmentId);
  const options = targets.filter((c) => c.id !== tx.commitmentId);
  return (
    <>
      {counts && linked && tx.commitmentInferred && (
        <LinkGuess
          name={current?.name ?? 'a commitment'}
          pad="10px 0 0"
          style={{ marginTop: 10, borderTop: `1px solid ${color.line}` }}
          onRight={() => tx.commitmentId && handlers.onLink(tx.id, tx.commitmentId)}
          onNot={() => handlers.onLink(tx.id, null)}
        />
      )}
      <Quiet>
        {children}
        {counts && <TextBtn label="Counts toward…" onClick={() => setPicking(!picking)} />}
        {counts && linked && <TextBtn label="Not a commitment" onClick={() => handlers.onLink(tx.id, null)} />}
        {counts && !linked && <TextBtn label="Make this a commitment" onClick={() => handlers.onMake(tx)} />}
      </Quiet>
      {picking && (
        <div style={{ marginTop: 8 }}>
          {options.length === 0 && (
            <span style={{ fontFamily: font.sans, fontSize: 12.5, color: color.faint }}>No other commitment this month</span>
          )}
          <TrayActions
            align="start"
            pad="0"
            actions={options.map((c) => ({
              label: c.name,
              onClick: () => {
                setPicking(false);
                handlers.onLink(tx.id, c.id);
              },
            }))}
          />
        </div>
      )}
    </>
  );
}
