import type { ReactNode } from 'react';
import { space } from '../../theme';

export type Side = 'agent' | 'user';

interface Props {
  side: Side;
  /**
   * True when this row changes speaker. Consecutive rows from one speaker sit
   * 8px apart; a change of speaker gets 20, so a turn reads as a turn.
   */
  newSpeaker: boolean;
  /** The first row of the thread: no gap above it. */
  first?: boolean;
  children: ReactNode;
}

/**
 * The agent across the full width, you on the right. The agent has no face
 * here — its words are the serif, and typography already says who is
 * speaking. The mascot appears only on the live row while a turn is working.
 */
export default function MessageRow({ side, newSpeaker, first = false, children }: Props) {
  const marginTop = first ? 0 : newSpeaker ? space.newSpeaker : space.sameSpeaker;

  if (side === 'user') {
    return (
      <div style={{ display: 'flex', justifyContent: 'flex-end', paddingLeft: 48, marginTop }}>
        <div data-bubble style={{ maxWidth: '100%' }}>{children}</div>
      </div>
    );
  }

  return (
    <div data-bubble style={{ marginTop, minWidth: 0 }}>
      {children}
    </div>
  );
}
