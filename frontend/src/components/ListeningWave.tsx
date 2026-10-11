import { color, font } from '../theme';

/** Staggered offsets so the bars read as a voice, not a metronome. */
const DELAYS = [0, 0.12, 0.24, 0.08, 0.3, 0.18];

export default function ListeningWave() {
  return (
    <div style={{ padding: '10px 0' }} role="status" aria-live="polite">
      <div
        style={{
          display: 'flex',
          gap: 3,
          alignItems: 'center',
          justifyContent: 'center',
          height: 28,
        }}
      >
        {DELAYS.map((d, i) => (
          <i
            key={i}
            style={{
              display: 'block',
              width: 3,
              background: color.brand,
              borderRadius: 2,
              animation: `wv 1.05s ease-in-out ${d}s infinite`,
            }}
          />
        ))}
      </div>
      <div
        style={{
          textAlign: 'center',
          fontFamily: font.sans,
          fontSize: 12.5,
          color: color.muted,
          marginTop: 4,
        }}
      >
        Listening…
      </div>
    </div>
  );
}
