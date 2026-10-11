import { useEffect, useRef, useState } from 'react';
import { Bell, CaretRight, ChartBar, CreditCard, Database, Question, ShieldCheck, X, type Icon } from '@phosphor-icons/react';
import { BRAND } from '../brand';
import { BUILT, MENU_GROUPS } from '../data/config';
import { useBack } from '../state/nav';
import { color, font, inset, radius } from '../theme';
import { SignOutIcon } from './Icons';
import Mascot from './Mascot';
import { trayBtn } from './messages/Tray';
import UserAvatar from './UserAvatar';

interface Props {
  /** On top of the stack. Under a page it keeps its scroll, and drops a half-asked sign out. */
  top: boolean;
  userName: string;
  avatarUrl: string | null;
  onClose: () => void;
  onRow: (name: string) => void;
  onSignOut: () => void;
}

const signOutPill = {
  display: 'flex',
  alignItems: 'center',
  gap: 6,
  padding: '7px 12px',
  borderRadius: radius.pill,
  border: `1px solid ${color.redBorder}`,
  background: color.redSurface,
  cursor: 'pointer',
  fontFamily: font.sans,
  fontSize: 13,
  lineHeight: '16px',
  color: color.red,
} as const;

/** Each row's glyph, the phone's set. */
const ROW_ICON: Record<string, Icon> = {
  Reports: ChartBar,
  'Your data': Database,
  Notifications: Bell,
  Permissions: ShieldCheck,
  Billing: CreditCard,
  'Help & feedback': Question,
};

/** A panel of the menu: the web's card — white, a hairline, no lift. */
const card = {
  background: color.white,
  border: `1px solid ${color.line}`,
  borderRadius: radius.card,
  overflow: 'hidden',
} as const;

/**
 * The menu: a place, not a chooser. A row opens its page over the menu, and
 * Back from that page comes back here as it was left. You at the top — a tap
 * is your Profile — then the rows in the phone's three groups. A row that
 * leads nowhere yet says Soon and does nothing. X returns Home.
 */
export default function Drawer({ top, userName, avatarUrl, onClose, onRow, onSignOut }: Props) {
  /** Sign out asks first: it is one tap from the rows, and it ends the session. */
  const [confirming, setConfirming] = useState(false);
  useEffect(() => {
    if (!top) setConfirming(false);
  }, [top]);
  useBack(confirming, () => setConfirming(false));
  // A cancelled ask hands focus back to the pill that asked it.
  const pill = useRef<HTMLButtonElement>(null);
  const asked = useRef(false);
  useEffect(() => {
    if (confirming) asked.current = true;
    else if (asked.current) {
      asked.current = false;
      if (top) pill.current?.focus();
    }
  }, [confirming, top]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Menu"
      tabIndex={-1}
      style={{ position: 'absolute', inset: 0, zIndex: 70, display: 'flex', outline: 'none' }}
    >
      <div
        style={{
          width: '100%',
          height: '100%',
          background: color.paper,
          padding: `${inset.top} 0 ${inset.bottom}`,
          animation: 'slidein 0.28s cubic-bezier(0.3,0.7,0.3,1)',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {/* X alone on its own row, as on the phone: it closes the menu, nothing else. */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', padding: '0 12px' }}>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="hov-tint"
            style={{
              width: 40,
              height: 40,
              borderRadius: '50%',
              background: 'none',
              border: 'none',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              padding: 0,
            }}
          >
            <X size={20} color={color.muted} aria-hidden />
          </button>
        </div>

        <div className="scroll-y" style={{ flex: 1, padding: '4px 16px 12px' }}>
          {/* You: the way into Profile, where the goals and the memories live. */}
          <button
            type="button"
            onClick={() => onRow('Profile')}
            className="hov-tint"
            style={{ ...card, width: '100%', display: 'flex', gap: 14, alignItems: 'center', padding: 18, cursor: 'pointer', textAlign: 'left' }}
          >
            <UserAvatar name={userName} url={avatarUrl} size={56} />
            <span style={{ flex: 1, minWidth: 0 }}>
              <span style={{ display: 'block', fontFamily: font.sans, fontWeight: 600, fontSize: 21, lineHeight: '25px', color: color.ink }}>
                {userName}
              </span>
              <span style={{ display: 'block', fontFamily: font.sans, fontSize: 13, lineHeight: '17px', color: color.faint, marginTop: 2 }}>
                Your goals, and what Spica remembers
              </span>
            </span>
            <CaretRight size={12} weight="bold" color={color.grey} aria-hidden />
          </button>

          {MENU_GROUPS.map((group) => (
            <div key={group[0]} style={{ ...card, marginTop: 14 }}>
              {group.map((name, i) => {
                const built = BUILT.has(name);
                const Glyph = ROW_ICON[name];
                return (
                  <div key={name}>
                    {i > 0 && <div style={{ height: 1, background: color.lineSoft, margin: '0 18px 0 66px' }} />}
                    <button
                      type="button"
                      // A row marked Soon is not a door: no page, no message, the menu stays.
                      onClick={built ? () => onRow(name) : undefined}
                      aria-disabled={built ? undefined : true}
                      className={built ? 'hov-tint' : undefined}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 14,
                        width: '100%',
                        background: 'none',
                        border: 'none',
                        padding: '13px 16px',
                        cursor: built ? 'pointer' : 'default',
                        fontFamily: font.sans,
                        fontWeight: 500,
                        fontSize: 16,
                        lineHeight: '20px',
                        color: color.ink,
                        textAlign: 'left',
                      }}
                    >
                      {/* The row's coin: its glyph in ink on the surface tint, as on the phone. */}
                      <span
                        aria-hidden
                        style={{
                          width: 36,
                          height: 36,
                          flex: '0 0 auto',
                          borderRadius: '50%',
                          background: color.surface,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                        }}
                      >
                        <Glyph size={19} color={color.ink} />
                      </span>
                      <span style={{ flex: 1, minWidth: 0 }}>{name}</span>
                      {built ? (
                        <CaretRight size={11} weight="bold" color={color.grey} aria-hidden />
                      ) : (
                        <span
                          style={{
                            fontFamily: font.sans,
                            fontSize: 12,
                            lineHeight: '15px',
                            fontWeight: 500,
                            color: color.faint,
                            background: color.surface,
                            borderRadius: radius.pill,
                            padding: '4px 9px',
                          }}
                        >
                          Soon
                        </span>
                      )}
                    </button>
                  </div>
                );
              })}
            </div>
          ))}
        </div>

        {/* One footer row: who made this on the left, the way out on the
            right. They were stacked, which read as two unrelated things and
            gave a destructive action the same weight as a version number. */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            margin: '8px 12px 0',
            padding: '12px 8px 2px',
            borderTop: `1px solid ${color.line}`,
          }}
        >
          {/* The agent signs the app — one of the three places its face
              appears, with the live row and the door. */}
          <Mascot size={28} state="still" />
          {confirming ? (
            <>
              <div style={{ flex: 1, minWidth: 0, fontFamily: font.sans, fontWeight: 500, fontSize: 15, lineHeight: '18px', color: color.ink }}>
                Sign out?
              </div>
              <button
                type="button"
                autoFocus
                onClick={() => setConfirming(false)}
                style={{ ...trayBtn, fontSize: 13, padding: '7px 14px' }}
              >
                Cancel
              </button>
              <button type="button" onClick={onSignOut} style={signOutPill}>
                <SignOutIcon />
                Sign out
              </button>
            </>
          ) : (
            <>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontFamily: font.sans, fontWeight: 600, fontSize: 15, lineHeight: '18px', color: color.ink }}>
                  {BRAND}
                </div>
                <div style={{ fontFamily: font.sans, fontSize: 11, lineHeight: '14px', color: color.faint, marginTop: 2 }}>
                  v0.1 · web version
                </div>
              </div>
              <button ref={pill} type="button" onClick={() => setConfirming(true)} style={signOutPill}>
                <SignOutIcon />
                Sign out
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
