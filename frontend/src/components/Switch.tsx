import { color, radius } from '../theme';

/**
 * On or off: a track that fills with Jamun, a white knob that slides. The
 * phone's `Switch` in `Page.kt`, px for dp — a 44 × 26 round track, `brand`
 * on and `border` off, a 20 knob inset 3. No shadow on the knob: on the web
 * only menus and the toast lift.
 *
 * `label` names what it turns on or off; the state is `aria-checked`, so a
 * screen reader hears both.
 */
export default function Switch({ on, onToggle, label }: { on: boolean; onToggle: () => void; label: string }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={label}
      onClick={onToggle}
      style={{
        display: 'block',
        flex: '0 0 auto',
        width: 44,
        height: 26,
        borderRadius: radius.pill,
        border: 'none',
        padding: 3,
        cursor: 'pointer',
        background: on ? color.brand : color.border,
        transition: 'background 0.15s',
      }}
    >
      <span
        style={{
          display: 'block',
          width: 20,
          height: 20,
          borderRadius: '50%',
          background: color.white,
          transform: on ? 'translateX(18px)' : 'none',
          transition: 'transform 0.15s',
        }}
      />
    </button>
  );
}
