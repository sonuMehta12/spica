import { useEffect, useRef, useState, type ReactNode } from 'react';
import { KebabIcon } from '../Icons';
import { color, font, radius, shadow } from '../../theme';
import type { Tile } from '../../report/metrics';
import { useBack } from '../../state/nav';

const microLabel = {
  fontFamily: font.sans,
  fontSize: 12,
  color: color.faint,
};

/**
 * Red when the number moved the way you did not want; plain ink when it did.
 * There is no "good" colour: a flattering move needs no applause, and the
 * mode greens are data, not praise.
 */
function deltaColor(t: Tile): string {
  if (t.delta === null || t.delta === 0 || t.good === 'none') return color.muted;
  const up = t.delta > 0;
  return (t.good === 'up') === up ? color.ink : color.red;
}

/**
 * One card: the answer, then the context.
 *
 * It was four equal quadrants, which is the wrong shape for these numbers —
 * *what did I spend* is the question, and *daily average* is a footnote to it.
 * Four tiles of one size said all four mattered the same.
 *
 * So the first `lead` tiles are the headline and the rest are rows. Paisa and
 * Work lead with one — total spend, open tasks. Diet leads with two, because
 * protein and calories genuinely are the same question asked twice, and
 * demoting either would be a lie about how this user eats.
 */
interface Props {
  tiles: Tile[];
  hasPrev: boolean;
  /** How many tiles are the headline. The rest become rows. */
  lead?: number;
  /** Secondary figures, revealed from the card's overflow menu. */
  extra?: Tile[];
}

/**
 * "73% more".
 *
 * Built from the delta's own label rather than a re-derived percentage, so a
 * tile measured in grams says grams. The sign becomes the word — a `+` the
 * reader has to decode is the thing this replaces.
 *
 * It does not say *than the previous 7 days*: the range picker sits directly
 * above the card and already does.
 */
function sentence(t: Tile, hasPrev: boolean): ReactNode {
  if (!t.deltaLabel) {
    // Never a 0% that was really "nothing to compare against".
    return t.noDelta ? null : <span style={{ color: color.faint }}>{hasPrev ? '—' : 'no prior data'}</span>;
  }
  const sign = t.deltaLabel[0];
  const word = sign === '+' ? 'more' : sign === '−' || sign === '-' ? 'less' : null;
  return (
    <>
      <span style={{ color: deltaColor(t), fontWeight: 500 }}>
        {word ? t.deltaLabel.slice(1) : t.deltaLabel}
      </span>
      {word && <span style={{ color: color.muted }}>{` ${word}`}</span>}
    </>
  );
}

export default function Scorecard({ tiles, hasPrev, lead = 1, extra = [] }: Props) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [showExtra, setShowExtra] = useState(false);
  const wrap = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menuOpen) return;
    const close = (e: Event) => {
      if (!wrap.current?.contains(e.target as Node)) setMenuOpen(false);
    };
    document.addEventListener('pointerdown', close);
    return () => document.removeEventListener('pointerdown', close);
  }, [menuOpen]);
  // Escape, and Back on the screen this sits on, close the ⋮ and nothing else.
  useBack(menuOpen, () => setMenuOpen(false));

  const shown = showExtra ? [...tiles, ...extra] : tiles;
  const heads = shown.slice(0, lead);
  const rows = shown.slice(lead);

  return (
    <div
      style={{
        position: 'relative',
        background: color.white,
        border: `1px solid ${color.line}`,
        borderRadius: radius.card,
        padding: '14px 16px 4px',
      }}
    >
      {extra.length > 0 && (
        <div ref={wrap} style={{ position: 'absolute', top: 8, right: 8, zIndex: 4 }}>
          <button
            type="button"
            onClick={() => setMenuOpen((o) => !o)}
            aria-label="More figures"
            aria-haspopup="menu"
            aria-expanded={menuOpen}
            className="hov-tint"
            style={{
              width: 32,
              height: 32,
              borderRadius: '50%',
              border: 'none',
              background: menuOpen ? color.lineSoft : 'none',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              padding: 0,
            }}
          >
            <KebabIcon size={18} stroke={color.muted} />
          </button>

          {menuOpen && (
            <div
              role="menu"
              style={{
                position: 'absolute',
                right: 0,
                top: 36,
                background: color.white,
                border: `1px solid ${color.line}`,
                borderRadius: radius.card,
                boxShadow: shadow.popover,
                padding: 4,
                minWidth: 150,
                animation: 'fadeup 0.16s',
              }}
            >
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  setShowExtra((v) => !v);
                  setMenuOpen(false);
                }}
                className="hov-tint"
                style={{
                  display: 'block',
                  width: '100%',
                  background: 'none',
                  border: 'none',
                  borderRadius: 10,
                  padding: '10px 12px',
                  cursor: 'pointer',
                  fontFamily: font.sans,
                  fontSize: 14,
                  color: color.ink,
                  textAlign: 'left',
                }}
              >
                {showExtra ? 'Hide' : 'More'}
              </button>
            </div>
          )}
        </div>
      )}

      {/* The headline, or two of them side by side. */}
      <div style={{ display: 'flex', gap: 14 }}>
        {heads.map((t) => (
          <div key={t.key} style={{ flex: 1, minWidth: 0, paddingRight: extra.length > 0 ? 24 : 0 }}>
            <div style={microLabel}>{t.label}</div>
            <div
              style={{
                fontFamily: font.sans,
                fontWeight: 500,
                // Two headlines share the width, so they take a smaller size —
                // still unmistakably the largest thing on the card.
                fontSize: heads.length > 1 ? 27 : 34,
                lineHeight: 1.05,
                marginTop: 5,
                color: color.ink,
              }}
            >
              {t.value}
            </div>
            <div style={{ marginTop: 6, fontFamily: font.sans, fontSize: 12.5, lineHeight: 1.4 }}>
              {sentence(t, hasPrev)}
            </div>
          </div>
        ))}
      </div>

      {/* Everything else: a label and a number, one line each. */}
      {rows.map((t) => (
        <div
          key={t.key}
          style={{
            display: 'flex',
            alignItems: 'baseline',
            gap: 10,
            padding: '11px 0',
            borderTop: `1px solid ${color.lineSoft}`,
            marginTop: 11,
          }}
        >
          <span style={{ flex: 1, fontFamily: font.sans, fontSize: 13.5, color: color.ink }}>
            {t.label}
          </span>
          {/* One piece of context, beside the number rather than under it — a
              second line per row would rebuild the equal weight this card just
              removed. The delta when there is one, otherwise whatever the tile
              carries instead: a target, a limit, how many lendings are open.
              Both together would say the same thing twice. */}
          {t.deltaLabel ? (
            <span style={{ fontFamily: font.sans, fontSize: 12, fontWeight: 500, color: deltaColor(t) }}>
              {t.deltaLabel}
            </span>
          ) : (
            t.sub && (
              <span style={{ fontFamily: font.sans, fontSize: 12, color: color.faint }}>{t.sub}</span>
            )
          )}
          <span
            style={{
              fontFamily: font.sans,
              fontSize: 13.5,
              fontWeight: 500,
              color: color.ink,
              whiteSpace: 'nowrap',
            }}
          >
            {t.value}
          </span>
        </div>
      ))}
    </div>
  );
}
