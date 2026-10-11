import { color } from '../theme';

/**
 * An app's mark, drawn rather than named.
 *
 * Under a bar there is room for one glyph, not for "Instagram" — and the
 * shapes are the most over-learned images most people own, so recognition
 * beats reading here. Traced, not copied: a rounded square with a lens for
 * Instagram, a play tab for YouTube, a crosshair for the game. Enough to be
 * recognised, nothing anyone could mistake for the real logo.
 *
 * An unknown app falls back to its first letter, the same rule the habit
 * strip and the project chips already use.
 */
export default function AppIcon({
  app,
  name,
  tint = color.muted,
  size = 15,
}: {
  app: string;
  name: string;
  tint?: string;
  size?: number;
}) {
  const box = { width: size, height: size, flex: '0 0 auto' as const };

  if (/instagram|insta/i.test(app)) {
    return (
      <svg {...box} viewBox="0 0 24 24" fill="none" stroke={tint} strokeWidth={2.2} aria-label={name}>
        <rect x="3" y="3" width="18" height="18" rx="5.5" />
        <circle cx="12" cy="12" r="4" />
        <circle cx="17.2" cy="6.8" r="1.2" fill={tint} stroke="none" />
      </svg>
    );
  }

  if (/youtube|yt/i.test(app)) {
    return (
      <svg {...box} viewBox="0 0 24 24" fill="none" aria-label={name}>
        <rect x="2" y="5" width="20" height="14" rx="4.5" stroke={tint} strokeWidth={2.2} />
        <path d="M10.2 9.2v5.6l4.8-2.8z" fill={tint} />
      </svg>
    );
  }

  if (/bgmi|pubg|game|cod/i.test(app)) {
    return (
      <svg {...box} viewBox="0 0 24 24" fill="none" stroke={tint} strokeWidth={2.2} aria-label={name}>
        <circle cx="12" cy="12" r="8" />
        <path d="M12 2.5v4M12 17.5v4M2.5 12h4M17.5 12h4" strokeLinecap="round" />
      </svg>
    );
  }

  if (/chrome|browser/i.test(app)) {
    return (
      <svg {...box} viewBox="0 0 24 24" fill="none" stroke={tint} strokeWidth={2.2} aria-label={name}>
        <circle cx="12" cy="12" r="9" />
        <circle cx="12" cy="12" r="3.4" />
        <path d="M12 8.6h8.2M8.9 13.7 4.8 20.6M15.1 13.7 11 20.6" strokeLinecap="round" />
      </svg>
    );
  }

  if (/whatsapp|chat|message/i.test(app)) {
    return (
      <svg {...box} viewBox="0 0 24 24" fill="none" stroke={tint} strokeWidth={2.2} aria-label={name}>
        <path d="M21 11.5a8.5 8.5 0 0 1-12.6 7.4L3.5 20.5l1.7-4.7A8.5 8.5 0 1 1 21 11.5z" />
      </svg>
    );
  }

  return (
    <span
      aria-label={name}
      style={{
        ...box,
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        borderRadius: 4,
        border: `1.2px solid ${tint}`,
        fontSize: size * 0.55,
        color: tint,
      }}
    >
      {name.charAt(0).toUpperCase()}
    </span>
  );
}
