import { Fragment, type CSSProperties, type ReactNode } from 'react';
import { Check, CheckCircle, type Icon } from '@phosphor-icons/react';
import { TODAY_ISO } from '../../data/live';
import { shortDate } from '../../lib/format';
import { color, font, radius } from '../../theme';
import { agentVoice } from './bubble';
import Dot from './Dot';

/**
 * The pieces every card in the thread is built from (spec/done/card-redesign.md).
 *
 * One vocabulary, so a payment, a meal and a pin read as the same kind of
 * object: a coin for the mode, what happened, its meta, the figure on the
 * right. Figures are the interface face at medium weight — data, never the
 * agent's voice — and in ink: red means over, late or negative, never "spent".
 */

/** A mode's round mark: its tint behind, its ink for the glyph. */
export function Coin({
  icon: Glyph,
  tint,
  ink,
  size = 34,
  weight = 'regular',
  children,
}: {
  icon?: Icon;
  tint: string;
  ink: string;
  size?: number;
  weight?: 'regular' | 'fill' | 'bold';
  /** Drawn instead of a glyph — an initial, a project's own mark. */
  children?: ReactNode;
}) {
  return (
    <span
      aria-hidden="true"
      style={{
        width: size,
        height: size,
        borderRadius: '50%',
        background: tint,
        color: ink,
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        flex: '0 0 auto',
        fontFamily: font.sans,
        fontWeight: 600,
        fontSize: Math.round(size / 2) - 1,
        lineHeight: 1,
      }}
    >
      {Glyph ? <Glyph size={Math.round(size / 2)} weight={weight} color={ink} /> : children}
    </span>
  );
}

/** A figure: the interface face, medium, tabular. */
export function Fig({
  children,
  size = 17,
  tone = color.ink,
  weight = 500,
  struck = false,
  style,
}: {
  children: ReactNode;
  size?: number;
  tone?: string;
  weight?: number;
  struck?: boolean;
  style?: CSSProperties;
}) {
  return (
    <span
      style={{
        fontFamily: font.sans,
        fontSize: size,
        lineHeight: `${Math.round(size * 1.3)}px`,
        fontWeight: weight,
        fontFeatureSettings: "'tnum'",
        color: struck ? color.faint : tone,
        textDecoration: struck ? 'line-through' : undefined,
        whiteSpace: 'nowrap',
        flex: '0 0 auto',
        ...style,
      }}
    >
      {children}
    </span>
  );
}

/** A small fact — a reason, a project, a relation. */
export function Chip({
  children,
  tone = color.muted,
  bg = color.surface,
  style,
}: {
  children: ReactNode;
  tone?: string;
  bg?: string;
  style?: CSSProperties;
}) {
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
        fontFamily: font.sans,
        fontSize: 12,
        lineHeight: '16px',
        color: tone,
        background: bg,
        borderRadius: radius.pill,
        padding: '3px 9px',
        whiteSpace: 'nowrap',
        maxWidth: '100%',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        ...style,
      }}
    >
      {children}
    </span>
  );
}

/**
 * A quiet action — Undo, Fixed cost?, Forget. Text, not a pill: the card's one
 * filled button is its primary action, and these are not it.
 */
export function TextBtn({
  label,
  onClick,
  tone = color.muted,
  icon: Glyph,
  iconWeight = 'regular',
  disabled = false,
  size = 13.5,
}: {
  label: string;
  onClick?: () => void;
  tone?: string;
  icon?: Icon;
  iconWeight?: 'regular' | 'fill' | 'bold';
  disabled?: boolean;
  size?: number;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={(e) => {
        e.stopPropagation();
        onClick?.();
      }}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 5,
        background: 'none',
        border: 'none',
        padding: '2px 0',
        margin: 0,
        fontFamily: font.sans,
        fontSize: size,
        lineHeight: '18px',
        fontWeight: 500,
        color: tone,
        cursor: disabled ? 'default' : 'pointer',
        whiteSpace: 'nowrap',
        flex: '0 0 auto',
      }}
    >
      {Glyph && <Glyph size={15} weight={iconWeight} color={tone} aria-hidden />}
      {label}
    </button>
  );
}

/** The card's one filled button — Log it, Do it, Yes. */
export function PrimaryBtn({
  label,
  onClick,
  disabled = false,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      className="hov-brand"
      disabled={disabled}
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      style={{
        fontFamily: font.sans,
        fontSize: 13,
        lineHeight: '16px',
        fontWeight: 500,
        padding: '6px 12px',
        borderRadius: radius.pill,
        border: `1px solid ${color.brand}`,
        background: color.brand,
        color: color.white,
        cursor: disabled ? 'default' : 'pointer',
        opacity: disabled ? 0.6 : 1,
        whiteSpace: 'nowrap',
        flex: '0 0 auto',
        maxWidth: '100%',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
      }}
    >
      {label}
    </button>
  );
}

/** An outlined pill — an answer that is not the primary one, an exercise's Done. */
export function PillBtn({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      className="hov-chip"
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      style={{
        fontFamily: font.sans,
        fontSize: 13,
        lineHeight: '16px',
        fontWeight: 500,
        padding: '6px 12px',
        borderRadius: radius.pill,
        border: `1px solid ${color.border}`,
        background: color.white,
        color: color.muted,
        cursor: 'pointer',
        whiteSpace: 'nowrap',
        flex: '0 0 auto',
      }}
    >
      {label}
    </button>
  );
}

/** A thin bar against a target. Past 100% it fills; it never overflows. */
export function Bar({ pct, tone, height = 4 }: { pct: number; tone: string; height?: number }) {
  const w = Math.max(0, Math.min(100, Math.round(pct * 100)));
  return (
    <div style={{ height, borderRadius: height, background: color.ringIdle, overflow: 'hidden' }}>
      <div style={{ width: `${w}%`, height, background: tone }} />
    </div>
  );
}

/** Text that can run long: so many lines, then an ellipsis. */
export function clamp(lines: number): CSSProperties {
  return {
    display: '-webkit-box',
    WebkitLineClamp: lines,
    WebkitBoxOrient: 'vertical',
    overflow: 'hidden',
    overflowWrap: 'anywhere',
  };
}

/**
 * The receipt line — the one line a confirm card is: a coin, what happened,
 * its meta, and the figure on the right. A removed row keeps its line, struck
 * and faint, so a deletion never disappears without a trace.
 */
export function Receipt({
  coin,
  what,
  meta,
  figure,
  struck = false,
}: {
  coin: ReactNode;
  what: ReactNode;
  meta?: ReactNode;
  figure?: ReactNode;
  struck?: boolean;
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0 }}>
      {coin}
      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 1 }}>
        <span
          style={{
            fontFamily: font.sans,
            fontSize: 15,
            lineHeight: '20px',
            fontWeight: 500,
            color: struck ? color.faint : color.ink,
            textDecoration: struck ? 'line-through' : undefined,
            ...clamp(2),
          }}
        >
          {what}
        </span>
        {meta != null && meta !== '' && (
          <span style={{ fontFamily: font.sans, fontSize: 12.5, lineHeight: '17px', color: color.faint, ...clamp(2) }}>
            {meta}
          </span>
        )}
      </div>
      {figure}
    </div>
  );
}

/**
 * A figure with what it counts under it, right-aligned — protein over kcal,
 * "3×" over "in all". `parts` are joined by the middle dot — "520 kcal · 60 g
 * carbs · 14 g fat" — and wrap between parts, never inside one, so a long
 * line never squeezes the name the receipt leads with.
 */
export function Stacked({ top, under, parts }: { top: ReactNode; under?: ReactNode; parts?: string[] }) {
  const small: CSSProperties = { fontFamily: font.sans, fontSize: 12, lineHeight: '16px', color: color.faint };
  return (
    <span
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'flex-end',
        flex: parts ? '0 1 auto' : '0 0 auto',
        maxWidth: parts ? '50%' : undefined,
      }}
    >
      {top}
      {parts ? (
        parts.length > 0 && (
          <span style={{ ...small, textAlign: 'right' }}>
            {parts.map((p, i) => (
              <Fragment key={p}>
                {i > 0 && ' '}
                <span style={{ whiteSpace: 'nowrap' }}>{i > 0 ? `· ${p}` : p}</span>
              </Fragment>
            ))}
          </span>
        )
      ) : (
        <span style={{ ...small, whiteSpace: 'nowrap' }}>{under}</span>
      )}
    </span>
  );
}

/** A line under the receipt, over a hairline — the guess, a total, a follow-up. */
export function Section({ children, gap = 10, style }: { children: ReactNode; gap?: number; style?: CSSProperties }) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap,
        marginTop: 10,
        paddingTop: 10,
        borderTop: `1px solid ${color.line}`,
        minWidth: 0,
        ...style,
      }}
    >
      {children}
    </div>
  );
}

/** A label and its figure across one line — "This month · ₹40,000 in · ₹0 out". */
export function FactLine({ label, value, tone = color.muted }: { label: ReactNode; value: ReactNode; tone?: string }) {
  return (
    <Section>
      <span style={{ fontFamily: font.sans, fontSize: 12.5, lineHeight: '17px', color: color.faint, flex: 1, minWidth: 0 }}>
        {label}
      </span>
      <Fig size={12.5} tone={tone}>{value}</Fig>
    </Section>
  );
}

/**
 * A guess, asked where it sits: "Food, I guessed · Right · Change". Nothing a
 * person must answer hides behind ⋮.
 */
export function GuessLine({ text, onRight, onChange }: { text: string; onRight: () => void; onChange: () => void }) {
  return (
    <Section>
      <span style={{ flex: 1, minWidth: 0, display: 'flex', alignItems: 'center' }}>
        <Dot />
        <span style={{ fontFamily: font.sans, fontSize: 13, lineHeight: '18px', color: color.muted, ...clamp(2) }}>
          {text}
        </span>
      </span>
      <TextBtn label="Right" tone={color.brand} onClick={onRight} />
      <TextBtn label="Change" onClick={onChange} />
    </Section>
  );
}

/** The quiet actions under a card's line. */
export function Quiet({ children }: { children: ReactNode }) {
  return <div style={{ display: 'flex', gap: 16, marginTop: 10, flexWrap: 'wrap' }}>{children}</div>;
}

/** A flag drawn as a quiet action: a question until it is true, then a tick. */
export function ToggleBtn({ on, ask, done, onClick }: { on: boolean; ask: string; done: string; onClick: () => void }) {
  return on ? (
    <TextBtn label={done} tone={color.brand} icon={CheckCircle} iconWeight="fill" onClick={onClick} />
  ) : (
    <TextBtn label={ask} onClick={onClick} />
  );
}

/**
 * The agent's own line, drawn ABOVE a card the phone built (+ menu: To-do,
 * Pantry, Cash flow) where no reply exists. Worked out from the live rows each
 * time it is drawn — never stored, never inside the card.
 */
export function AgentLine({ children }: { children: ReactNode }) {
  return <div style={{ ...agentVoice, marginBottom: 8 }}>{children}</div>;
}

/** A row in a list card: the hairline sits between rows, not around them. */
export function ListRow({
  first,
  children,
  pad = '9px 0',
  align = 'center',
}: {
  first: boolean;
  children: ReactNode;
  pad?: string;
  align?: 'center' | 'flex-start';
}) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: align,
        gap: 10,
        padding: pad,
        borderTop: first ? undefined : `1px solid ${color.line}`,
        minWidth: 0,
      }}
    >
      {children}
    </div>
  );
}

/** A group's label inside a list card — Late, Use soon, Today. */
export function GroupLabel({ children, tone = color.muted }: { children: ReactNode; tone?: string }) {
  return (
    <div style={{ fontFamily: font.sans, fontSize: 12, lineHeight: '16px', fontWeight: 500, color: tone, marginTop: 14 }}>
      {children}
    </div>
  );
}

/** A count that leads a list card — "14 open · 2 late", "11 in the kitchen". */
export function Lead({ children }: { children: ReactNode }) {
  return <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, flexWrap: 'wrap' }}>{children}</div>;
}

/** The small grey word beside a lead figure. */
export function LeadWord({ children }: { children: ReactNode }) {
  return <span style={{ fontFamily: font.sans, fontSize: 13, lineHeight: '18px', color: color.faint }}>{children}</span>;
}

/**
 * A task's checkbox — live: a tap ticks the task itself, wherever it is shown.
 * Filled in the project's colour once done. Without `onToggle` (a task the
 * client does not hold) it is drawn but not a control.
 */
export function TaskCheck({
  done,
  tint = color.work,
  size = 20,
  label,
  onToggle,
}: {
  done: boolean;
  tint?: string;
  size?: number;
  label: string;
  onToggle?: () => void;
}) {
  const box: CSSProperties = {
    width: size,
    height: size,
    borderRadius: '50%',
    border: `1.5px solid ${done ? tint : color.border}`,
    background: done ? tint : color.white,
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    flex: '0 0 auto',
    padding: 0,
    marginTop: 1,
  };
  const tick = done && <Check size={Math.round(size * 0.6)} weight="bold" color={color.white} aria-hidden />;
  if (!onToggle) return <span aria-hidden="true" style={box}>{tick}</span>;
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={done}
      aria-label={label}
      onClick={(e) => {
        e.stopPropagation();
        onToggle();
      }}
      style={{ ...box, cursor: 'pointer' }}
    >
      {tick}
    </button>
  );
}

/** "Wed, 16 Sep" — or "today", which reads faster for the day you are in. */
export function dayText(iso: string | null | undefined, today = TODAY_ISO): string {
  if (!iso) return '';
  return iso === today ? 'today' : shortDate(iso);
}

/** The first letter up — a meta line is a sentence-case phrase. */
export const cap = (s: string) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s);

/** The parts of a meta line, empty ones dropped, joined by the middle dot. */
export const metaLine = (...parts: (string | null | undefined | false)[]) =>
  cap(parts.filter((p): p is string => Boolean(p)).join(' · '));
