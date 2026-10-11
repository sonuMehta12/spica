import { TODAY_ISO } from '../data/live';
import { longDay } from '../lib/format';
import { color, font, space } from '../theme';
import { ClearIcon, MenuIcon, SpinnerIcon } from './Icons';

const round = {
  width: 36,
  height: 36,
  borderRadius: '50%',
  background: 'none',
  border: 'none',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  cursor: 'pointer',
  flex: '0 0 auto',
  padding: 0,
} as const;

/**
 * The app bar. Today's date heads the page, as it would a journal's — the one
 * line of chrome that says something, in the agent's italic serif. The icon
 * buttons beside it are borderless: chrome, not cards.
 *
 * Clear sits left of the menu, and only when there is something to clear. It
 * hides the thread rather than deleting it — the server folds what it hides
 * into the summary, so the screen starts fresh and the agent keeps the gist
 * (`spec/done/chat-history.md`).
 *
 * That fold is a model call, so the press can take a few seconds. The button
 * spins and stops taking presses while it runs: with no feedback the natural
 * thing is to press again, and each press is another summariser call.
 */
export default function Header({
  onMenu,
  onClear,
  canClear,
  clearing,
  today = TODAY_ISO,
}: {
  onMenu: () => void;
  onClear: () => void;
  canClear: boolean;
  clearing: boolean;
  /** The day the page is about, ISO. The deck's own today by default. */
  today?: string;
}) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 4,
        marginBottom: space.headerToTabs,
        minHeight: 36,
      }}
    >
      <h1
        style={{
          flex: 1,
          minWidth: 0,
          margin: 0,
          fontFamily: font.display,
          fontStyle: 'italic',
          fontWeight: 400,
          fontSize: 21,
          lineHeight: '26px',
          color: color.ink,
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}
      >
        {longDay(today)}
      </h1>
      {(canClear || clearing) && (
        <button
          type="button"
          onClick={onClear}
          disabled={clearing}
          aria-label={clearing ? 'Clearing the conversation' : 'Clear the conversation from view'}
          aria-busy={clearing}
          title="Clear from view — nothing is deleted"
          className={clearing ? undefined : 'hov-tint'}
          style={{ ...round, cursor: clearing ? 'default' : 'pointer' }}
        >
          {clearing ? <SpinnerIcon /> : <ClearIcon stroke={color.muted} />}
        </button>
      )}
      <button type="button" onClick={onMenu} aria-label="Menu" aria-haspopup="dialog" className="hov-tint" style={round}>
        <MenuIcon />
      </button>
    </div>
  );
}
