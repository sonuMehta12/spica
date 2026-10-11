import { useState } from 'react';
import { color, font } from '../theme';

/**
 * The user's face, wherever it appears.
 *
 * Google's picture URL when there is one, the initial when there is not —
 * and the initial again if the URL fails to load, which it will: the URL
 * rotates, and a broken image is worse than a letter. An empty name draws the
 * plain circle rather than a letter that is not there.
 */
export default function UserAvatar({
  name,
  url,
  size = 46,
}: {
  name: string;
  url: string | null;
  size?: number;
}) {
  const [broken, setBroken] = useState(false);
  const initial = name.trim().charAt(0).toUpperCase();

  if (url && !broken) {
    return (
      <img
        src={url}
        alt=""
        width={size}
        height={size}
        referrerPolicy="no-referrer"
        onError={() => setBroken(true)}
        style={{ width: size, height: size, borderRadius: '50%', objectFit: 'cover' }}
      />
    );
  }

  return (
    <div
      aria-hidden
      style={{
        width: size,
        height: size,
        borderRadius: '50%',
        background: color.brand,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontFamily: font.sans,
        fontWeight: 600,
        fontSize: Math.round(size * 0.41),
        color: color.white,
      }}
    >
      {initial}
    </div>
  );
}
