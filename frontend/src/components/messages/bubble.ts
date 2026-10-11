import type { CSSProperties } from 'react';
import { color, font, radius } from '../../theme';

/**
 * A card in the thread — a table, a confirmation, a tray of options. White
 * with a hairline, no shadow: nothing that sits in the page lifts. The agent's
 * plain words take no card at all (`agentVoice`). Spacing is the row's job.
 */
export function agentCard(padding: string): CSSProperties {
  return {
    background: color.white,
    border: `1px solid ${color.line}`,
    borderRadius: radius.card,
    padding,
    animation: 'fadeup 0.35s',
  };
}

/** A card's heading: sentence case, a quiet second rank. No tracked caps. */
export const cardHeading: CSSProperties = {
  fontFamily: font.sans,
  fontSize: 12.5,
  fontWeight: 500,
  color: color.muted,
};

/**
 * How the agent's own words look, wherever they appear — the greeting, a
 * reply, the line over a card the phone built. The serif is Spica speaking;
 * the sans in grey is data. Typography says who is talking, so the agent needs
 * neither a bubble nor a face beside every reply — and its words never sit
 * inside a card (spec/done/card-redesign.md).
 */
export const agentVoice: CSSProperties = {
  fontFamily: font.display,
  fontSize: 15.5,
  lineHeight: '23px',
  color: color.ink,
};

/** A label beside data: the interface face, small, grey — never uppercase. */
export const dataLabel: CSSProperties = {
  fontFamily: font.sans,
  fontSize: 11,
  color: color.faint,
};

/** A figure: the interface face at medium weight. Numbers are data, not the agent's voice. */
export const figure: CSSProperties = {
  fontFamily: font.sans,
  fontWeight: 500,
  color: color.ink,
};

/**
 * A filter pill — All · Cook now · Saved. The one picked is a selection, so it
 * takes the brand; the rest are white with a border.
 */
export function filterPill(on: boolean): CSSProperties {
  return {
    fontFamily: font.sans,
    fontSize: 12.5,
    fontWeight: 500,
    lineHeight: '16px',
    padding: '6px 12px',
    borderRadius: radius.pill,
    border: `1px solid ${on ? color.brand : color.border}`,
    background: on ? color.brand : color.white,
    color: on ? color.white : color.muted,
    cursor: 'pointer',
    whiteSpace: 'nowrap',
  };
}

/** A primary button — Save, Add, Done: the brand, filled. */
export const primaryBtn: CSSProperties = {
  fontFamily: font.sans,
  fontSize: 13,
  fontWeight: 500,
  lineHeight: '16px',
  padding: '7px 14px',
  borderRadius: radius.pill,
  border: `1px solid ${color.brand}`,
  background: color.brand,
  color: color.white,
  cursor: 'pointer',
};
