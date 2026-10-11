import { color, font } from '../../theme';
import type { SourceRow } from '../../vault/stats';

const PRETTY: Record<string, string> = {
  agent: 'Made by the agent',
  maps: 'Maps',
};

/** Capture spreads across a long tail of one-offs; only the regulars get a bar. */
const TOP = 6;

export default function SourceBars({ rows }: { rows: SourceRow[] }) {
  const peak = Math.max(...rows.map((r) => r.count), 1);
  const shown = rows.slice(0, TOP);
  const rest = rows.slice(TOP);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
      {shown.map((r) => (
        <div key={r.source}>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              gap: 8,
              marginBottom: 4,
              fontSize: 13,
            }}
          >
            <span
              style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
            >
              {PRETTY[r.source] ?? r.source}
            </span>
            <span style={{ fontFamily: font.sans, fontSize: 12, color: color.muted }}>
              {r.count}
            </span>
          </div>
          <div
            style={{ height: 5, borderRadius: 3, background: color.ringIdle, overflow: 'hidden' }}
          >
            <div
              style={{
                width: `${(r.count / peak) * 100}%`,
                height: '100%',
                background: color.muted,
              }}
            />
          </div>
        </div>
      ))}
      {rest.length > 0 && (
        <div style={{ fontFamily: font.sans, fontSize: 11, color: color.faint, marginTop: 2 }}>
          +{rest.length} more places · {rest.reduce((a, r) => a + r.count, 0)} things
        </div>
      )}
    </div>
  );
}
