import { DotsThreeVertical } from '@phosphor-icons/react';
import { color, font, radius } from '../../theme';

/**
 * The one ⋮ tray. `report/ItemList.tsx` and the chat table drew the same
 * tray twice; every chat card now draws this one, so the actions cannot drift
 * between a payment in the Paisa card and the same payment in a confirm card.
 *
 * Two parts, because the toggle sits inline on a row and the chips sit under
 * it: `TrayToggle` is the ⋮, `TrayActions` is the row of chips.
 */
export interface TrayAction {
  label: string;
  onClick: () => void;
  tone?: 'default' | 'danger' | 'good';
  /** Rendered but not tappable — "Logged", "Saved". */
  disabled?: boolean;
}

export const trayBtn = {
  fontFamily: font.sans,
  fontSize: 12,
  fontWeight: 500,
  lineHeight: '16px',
  padding: '5px 12px',
  borderRadius: radius.pill,
  border: `1px solid ${color.border}`,
  background: color.white,
  color: color.muted,
  cursor: 'pointer',
} as const;

export function TrayToggle({
  open,
  onToggle,
  label,
}: {
  open: boolean;
  onToggle: () => void;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        onToggle();
      }}
      aria-label={`Options — ${label}`}
      aria-expanded={open}
      className="hov-tint"
      style={{
        width: 28,
        height: 28,
        borderRadius: '50%',
        background: open ? color.lineSoft : 'none',
        border: 'none',
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 0,
        flex: '0 0 auto',
      }}
    >
      <DotsThreeVertical size={18} weight="bold" color={color.faint} />
    </button>
  );
}

export function TrayActions({
  actions,
  pad = '0 0 2px',
  align = 'end',
}: {
  actions: TrayAction[];
  pad?: string;
  align?: 'start' | 'end';
}) {
  if (!actions.length) return null;
  return (
    <div
      style={{
        display: 'flex',
        gap: 8,
        padding: pad,
        justifyContent: align === 'start' ? 'flex-start' : 'flex-end',
        flexWrap: 'wrap',
        animation: 'fadeup 0.2s',
      }}
    >
      {actions.map((a) => (
        <button
          key={a.label}
          type="button"
          disabled={a.disabled}
          onClick={(e) => {
            e.stopPropagation();
            a.onClick();
          }}
          style={{
            ...trayBtn,
            ...(a.tone === 'danger'
              ? { border: `1px solid ${color.redBorder}`, background: color.redSurface, color: color.red }
              : a.tone === 'good'
                ? { border: `1px solid ${color.brandTint}`, background: color.brandTint, color: color.brand }
                : {}),
            ...(a.disabled ? { cursor: 'default', opacity: 0.7 } : {}),
          }}
        >
          {a.label}
        </button>
      ))}
    </div>
  );
}
