import Mascot, { type MascotState } from './Mascot';

export const AVATAR_SIZE = 30;

interface Props {
  /** Only the newest face animates; everything older is a still portrait. */
  state?: MascotState;
}

/**
 * The agent's face, shown beside what it says. There is deliberately no
 * counterpart for you — you already know which side is yours.
 *
 * No chip behind it any more: the mascot's own outer arc was doing the same job
 * as the tinted circle, and stacking the two read as a badge rather than a face.
 */
export default function AgentAvatar({ state = 'still' }: Props) {
  return <Mascot size={AVATAR_SIZE} state={state} />;
}
