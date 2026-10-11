import { useEffect, useRef, useState } from 'react';
import { Heartbeat, Repeat, Wallet } from '@phosphor-icons/react';
import { habitGlyph } from '../components/HabitIcon';
import Dot from '../components/messages/Dot';
import { Coin, TextBtn } from '../components/messages/parts';
import { PROFILE } from '../data/live';
import { localToday } from '../lib/day';
import { color, font, inset, radius, space } from '../theme';
import { LINES } from './copy';
import { aboutTags, goals, loadFacts, type Facts, type Goal } from './facts';
import { BigButton, Opening, Screen, TopBar, card } from './parts';

/**
 * Screen 4 · You're all set. Where the person starts, and where they are
 * headed — read from the live rows on entry, never from the cards' copies.
 * No calories, no protein, no daily targets: a daily target is the app's
 * number, not the person's goal. spec/done/onboarding-goals.md § 4.
 */

/** Each goal's mode coin: the body and habits in Diet's tint, money in Paisa's. */
function GoalCoin({ goal }: { goal: Goal }) {
  if (goal.domain === 'money') return <Coin icon={Wallet} tint={color.paisaTint} ink={color.paisaInk} size={40} />;
  const glyph = goal.domain === 'habit' ? (habitGlyph(goal.habit ?? '') ?? Repeat) : Heartbeat;
  return <Coin icon={glyph} tint={color.dietTint} ink={color.dietInk} size={40} />;
}

function CardHead({ title, onEdit }: { title: string; onEdit: () => void }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
      <span style={{ fontFamily: font.sans, fontSize: 12.5, fontWeight: 500, color: color.muted }}>{title}</span>
      <TextBtn label="Edit" tone={color.brand} size={12.5} onClick={onEdit} />
    </div>
  );
}

/**
 * How long a tap is ignored once this screen is up. Get started sits where
 * screen 3's Continue was, and a double tap on that would otherwise finish
 * past the summary unseen — the input protection Chrome gives a permission
 * prompt, at its 500 ms.
 */
const SETTLE_MS = 500;

export default function AllSet({
  onBack,
  onEdit,
  onStart,
  busy,
}: {
  /** The ←: what the browser's back does here — screen 3. */
  onBack: () => void;
  /** Back to screen 3 and its thread, where each write has its own Edit. */
  onEdit: () => void;
  onStart: () => void;
  busy: boolean;
}) {
  const shownAt = useRef(performance.now());
  const [facts, setFacts] = useState<Facts | null>(null);
  const [unread, setUnread] = useState(false);
  useEffect(() => {
    let live = true;
    loadFacts().then(
      (f) => live && setFacts(f),
      () => live && setUnread(true),
    );
    return () => {
      live = false;
    };
  }, []);

  const tags = facts ? aboutTags(facts, localToday()) : [];
  const rows = facts ? goals(facts) : [];
  const name = (facts?.profile ?? PROFILE).displayName.trim();
  // A card with nothing in it is not drawn; with both empty, the line says how they fill.
  const line = unread ? LINES.unread : facts && !tags.length && !rows.length ? LINES.nothing : LINES.headed;

  return (
    <Screen>
      <TopBar onBack={onBack} />
      <div className="scroll-y" style={{ flex: '1 1 auto', minHeight: 0, padding: `0 ${space.gutter}px 16px` }}>
        <Opening title={LINES.allSet(name)} line={facts || unread ? line : ' '} top={26} />

        {tags.length > 0 && (
          <div style={{ ...card, marginTop: 20, padding: '12px 16px 14px' }}>
            <CardHead title="About you" onEdit={onEdit} />
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 10 }}>
              {tags.map((t) => (
                <span
                  key={t.text}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    fontFamily: font.sans,
                    fontSize: 13.5,
                    lineHeight: '18px',
                    padding: '6px 11px',
                    borderRadius: radius.pill,
                    background: color.lineSoft,
                    color: color.ink,
                  }}
                >
                  {t.estimated && <Dot />}
                  {t.text}
                </span>
              ))}
            </div>
          </div>
        )}

        {rows.length > 0 && (
          <div style={{ ...card, marginTop: 12, padding: '12px 16px 4px' }}>
            <CardHead title="Your goals" onEdit={onEdit} />
            {rows.map((g, k) => (
              <div
                key={g.key}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12,
                  padding: '10px 0',
                  borderTop: k === 0 ? 'none' : `1px solid ${color.line}`,
                  marginTop: k === 0 ? 4 : 0,
                }}
              >
                <GoalCoin goal={g} />
                <span style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <span style={{ fontFamily: font.sans, fontSize: 16, lineHeight: '21px', fontWeight: 500, color: color.ink, overflowWrap: 'anywhere' }}>
                    {g.titleEstimated && <Dot />}
                    {g.title}
                  </span>
                  {g.sub && (
                    <span style={{ fontFamily: font.sans, fontSize: 13.5, lineHeight: '18px', color: color.muted }}>
                      {g.sub.map((part, n) => (
                        <span key={n}>
                          {n > 0 && ' '}
                          {part.estimated && <Dot />}
                          {part.text}
                        </span>
                      ))}
                    </span>
                  )}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
      <div style={{ flex: '0 0 auto', padding: `12px ${space.gutter}px ${inset.bottom}` }}>
        <BigButton
          label="Get started"
          onClick={() => {
            if (performance.now() - shownAt.current >= SETTLE_MS) onStart();
          }}
          busy={busy}
        />
      </div>
    </Screen>
  );
}
