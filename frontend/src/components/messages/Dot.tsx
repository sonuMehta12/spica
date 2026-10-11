import { color } from '../../theme';

/**
 * The confidence mark. Drawn before a value the agent worked out rather than
 * was told, and before a weight the person gave as a guess ("around 72")
 * until an exact one replaces it; absent before one the user stated. There is no "confirmed" dot —
 * certainty is the default and does not decorate itself (spec/chat-cards.md).
 * It replaced the word `· andaaza`: a state is copy, and copy is English.
 */
export default function Dot() {
  return (
    <span
      role="img"
      aria-label="estimated"
      title="Estimated"
      style={{
        display: 'inline-block',
        width: 6,
        height: 6,
        borderRadius: '50%',
        background: color.amber,
        marginRight: 6,
        verticalAlign: 'middle',
        position: 'relative',
        top: -1,
      }}
    />
  );
}
