import { ArrowLeft } from '@phosphor-icons/react';
import { color, font } from '../theme';

/** A page's one way out, and the screen it returns to — said to a screen reader, not on screen. */
export interface Back {
  label: string;
  onClick: () => void;
}

/**
 * The ← of a page: a round, borderless button at the header's top right,
 * where a page's close once sat — an arrow and nothing else. It pops one
 * screen, back to whatever opened this one, and a screen reader hears where
 * it goes: *Back to Menu*.
 */
export function BackButton({ back }: { back: Back }) {
  return (
    <button
      type="button"
      onClick={back.onClick}
      aria-label={`Back to ${back.label}`}
      className="hov-tint"
      style={{
        width: 36,
        height: 36,
        borderRadius: '50%',
        background: 'none',
        border: 'none',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        cursor: 'pointer',
        padding: 0,
        flex: '0 0 auto',
      }}
    >
      <ArrowLeft size={20} color={color.muted} aria-hidden />
    </button>
  );
}

interface Props {
  back: Back;
  /** A quiet line above the title naming the page's family — Report, Profile, Your data. */
  eyebrow?: string;
  title: string;
}

/**
 * The head of a full page — the Report, Your data, Profile, and their
 * sections. One shape everywhere: the title in the interface face on the
 * left, ← at the top right. A page has no X: ← is its one exit
 * (THEME.md § Back).
 */
export default function PageHeader({ back, eyebrow, title }: Props) {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
      <div style={{ minWidth: 0 }}>
        {eyebrow && (
          <div style={{ fontFamily: font.sans, fontSize: 13, lineHeight: '16px', fontWeight: 500, color: color.faint }}>
            {eyebrow}
          </div>
        )}
        <h1
          style={{
            margin: '2px 0 0',
            fontFamily: font.sans,
            fontWeight: 600,
            fontSize: 24,
            lineHeight: '28px',
            color: color.ink,
          }}
        >
          {title}
        </h1>
      </div>
      <BackButton back={back} />
    </div>
  );
}
