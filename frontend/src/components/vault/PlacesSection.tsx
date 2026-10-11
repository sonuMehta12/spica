import { useEffect, useMemo, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { color, font } from '../../theme';
import Dot from '../messages/Dot';
import { searchPlaces, type Found, type PersonRow, type PlaceRow } from '../../data/api';
import { useBack } from '../../state/nav';

/**
 * Your data → Places. spec/in-progress/places.md.
 *
 * Where the money was spent — not a list of places to visit. A pin appears
 * because you dropped it, or (once capture exists) because payments kept
 * landing in the same small circle three separate days running.
 *
 * Every number on a pin is counted server-side over the transactions pointing
 * at it, or at the counterparty it belongs to. That second path is what lets
 * Mohan Lal's shop show its spend with nothing tagged by hand.
 *
 * Leaflet with OpenStreetMap tiles, search via Nominatim: free, keyless, and
 * enough to prove the gesture. Android gets a native map and the schema does
 * not change.
 */
interface Props {
  places: PlaceRow[];
  people: PersonRow[];
  onAdd: (row: { name: string; lat: number; lng: number; kind: string | null;
                 address: string | null; source: string }) => Promise<boolean>;
  onPatch: (id: string, patch: { name?: string; kind?: string | null;
                                 counterparty_id?: string | null; note?: string | null;
                                 radius_m?: number }) => Promise<boolean>;
  onDelete: (id: string) => void;
}

const KINDS = ['home', 'office', 'shop', 'eat', 'hangout', 'pickup', 'gym', 'other'];
/** Delhi. The map has to start somewhere, and this is where the payments are. */
const HOME: [number, number] = [28.6139, 77.209];

const shell = {
  background: color.white,
  border: `1px solid ${color.line}`,
  borderRadius: 14,
  overflow: 'hidden' as const,
};

const label = {
  display: 'block',
  fontFamily: font.sans,
  fontSize: 12,
  color: color.muted,
  marginBottom: 4,
};

const input = {
  width: '100%',
  boxSizing: 'border-box' as const,
  fontFamily: font.sans,
  fontSize: 14,
  padding: '6px 9px',
  borderRadius: 10,
  border: `1px solid ${color.border}`,
  background: color.paper,
  color: color.ink,
  outline: 'none',
};

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const shortDate = (iso: string) => `${Number(iso.slice(8, 10))} ${MONTHS[Number(iso.slice(5, 7)) - 1]}`;
const rupees = (paise: number) => `₹${Math.round(paise / 100).toLocaleString('en-IN')}`;

/** A dot, not Leaflet's default marker — that ships a PNG Vite would have to
 *  resolve, and a circle reads better at this size anyway. */
const dot = (fill: string) =>
  L.divIcon({
    className: '',
    html: `<span style="display:block;width:13px;height:13px;border-radius:50%;background:${fill};border:2px solid ${color.white};box-shadow:0 1px 3px rgba(0,0,0,.35)"></span>`,
    iconSize: [13, 13],
    iconAnchor: [7, 7],
  });

export default function PlacesSection({ places, people, onAdd, onPatch, onDelete }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const layer = useRef<L.LayerGroup | null>(null);

  const [q, setQ] = useState('');
  const [hits, setHits] = useState<Found[] | null>(null);
  const [searching, setSearching] = useState(false);
  /** Where a new pin is going, before it has a name. */
  const [dropped, setDropped] = useState<{ lat: number; lng: number; name: string; address: string | null } | null>(null);
  const [kind, setKind] = useState('shop');
  const [open, setOpen] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // Back closes, innermost first: a pin being dropped, an open place, the
  // search's results.
  useBack(hits != null, () => setHits(null));
  useBack(open != null && places.some((p) => p.id === open), () => setOpen(null));
  useBack(dropped != null, () => setDropped(null));

  // Leaflet owns its own DOM, so it is created once and told about React's
  // state afterwards — never re-created on a render.
  useEffect(() => {
    if (map.current || !host.current) return;
    const m = L.map(host.current, { attributionControl: false }).setView(HOME, 12);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '© OpenStreetMap',
    }).addTo(m);
    L.control.attribution({ prefix: false }).addTo(m);
    layer.current = L.layerGroup().addTo(m);
    m.on('click', (e: L.LeafletMouseEvent) =>
      setDropped({ lat: e.latlng.lat, lng: e.latlng.lng, name: '', address: null }),
    );
    map.current = m;
    // The pane is sized by flexbox, which Leaflet cannot see until it settles.
    setTimeout(() => m.invalidateSize(), 60);
    return () => {
      m.remove();
      map.current = null;
    };
  }, []);

  // Redraw the pins whenever the rows or the pending drop change.
  useEffect(() => {
    const g = layer.current;
    if (!g) return;
    g.clearLayers();
    for (const p of places) {
      // Places are where money went, so a pin is Paisa's; one the agent
      // only guessed is the estimate's amber, the same meaning as the dot.
      L.marker([p.lat, p.lng], { icon: dot(p.confirmed ? color.paisa : color.amber) })
        .addTo(g)
        .bindTooltip(`${p.name}${p.payments ? ` · ${p.payments}×` : ''}`)
        .on('click', () => setOpen(p.id));
      // The radius is a real thing a payment gets matched against, so it is
      // drawn rather than left as a number in a form.
      L.circle([p.lat, p.lng], {
        radius: p.radiusM,
        color: color.paisa,
        weight: 1,
        opacity: 0.35,
        fillOpacity: 0.06,
      }).addTo(g);
    }
    if (dropped) {
      L.marker([dropped.lat, dropped.lng], { icon: dot(color.red) }).addTo(g);
    }
  }, [places, dropped]);

  const search = async () => {
    const clean = q.trim();
    if (!clean) return;
    setSearching(true);
    try {
      setHits(await searchPlaces(clean));
    } catch {
      setHits([]);
    }
    setSearching(false);
  };

  const jumpTo = (f: Found) => {
    map.current?.setView([f.lat, f.lng], 16);
    setDropped({ lat: f.lat, lng: f.lng, name: f.name, address: f.address });
    setHits(null);
  };

  const save = async () => {
    if (!dropped || !dropped.name.trim()) return;
    setBusy(true);
    const ok = await onAdd({
      name: dropped.name.trim(),
      lat: dropped.lat,
      lng: dropped.lng,
      kind,
      address: dropped.address,
      // Searched or tapped — both are yours, and neither is a guess.
      source: dropped.address ? 'search' : 'manual',
    });
    setBusy(false);
    if (ok) {
      setDropped(null);
      setQ('');
    }
  };

  const byKind = useMemo(() => {
    const groups = new Map<string, PlaceRow[]>();
    for (const p of places) {
      const k = p.kind ?? 'other';
      groups.set(k, [...(groups.get(k) ?? []), p]);
    }
    return [...groups.entries()];
  }, [places]);

  return (
    <>
      <div style={{ ...shell, marginBottom: 8 }}>
        <div style={{ padding: '11px 13px', display: 'flex', gap: 7 }}>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && void search()}
            placeholder="Search a place, or tap the map"
            style={input}
          />
          <button
            type="button"
            onClick={() => void search()}
            disabled={!q.trim() || searching}
            style={{
              fontFamily: font.sans,
              fontSize: 11.5,
              padding: '6px 13px',
              borderRadius: 14,
              border: 'none',
              whiteSpace: 'nowrap',
              cursor: q.trim() && !searching ? 'pointer' : 'default',
              background: q.trim() && !searching ? color.brand : color.ringIdle,
              color: q.trim() && !searching ? color.white : color.faint,
            }}
          >
            {searching ? '…' : 'Find'}
          </button>
        </div>

        {hits != null && (
          <div style={{ borderTop: `1px solid ${color.lineSoft}` }}>
            {hits.length === 0 ? (
              <div style={{ padding: '10px 14px', fontSize: 13, color: color.muted }}>
                Nothing found. Tap the map instead.
              </div>
            ) : (
              hits.map((f, i) => (
                <button
                  key={i}
                  type="button"
                  className="hov-tint"
                  onClick={() => jumpTo(f)}
                  style={{
                    display: 'block',
                    width: '100%',
                    textAlign: 'left',
                    background: 'none',
                    border: 'none',
                    borderTop: i ? `1px solid ${color.lineSoft}` : 'none',
                    padding: '9px 13px',
                    cursor: 'pointer',
                  }}
                >
                  <span style={{ fontSize: 13.5, fontWeight: 500, color: color.ink }}>{f.name}</span>
                  <span style={{ display: 'block', fontFamily: font.sans, fontSize: 11, color: color.faint, marginTop: 2 }}>
                    {f.address}
                  </span>
                </button>
              ))
            )}
          </div>
        )}

        <div ref={host} style={{ height: 260, width: '100%', background: color.lineSoft }} />

        {dropped && (
          <div style={{ padding: '11px 13px 13px', borderTop: `1px solid ${color.lineSoft}`, animation: 'fadeup 0.18s' }}>
            <div style={{ marginTop: 0 }}>
              <span style={label}>Name</span>
              <input
                value={dropped.name}
                autoFocus
                placeholder="Mohan Lal, Ghar, chai tapri…"
                onChange={(e) => setDropped({ ...dropped, name: e.target.value })}
                style={input}
              />
            </div>
            <div style={{ marginTop: 10 }}>
              <span style={label}>What is it</span>
              <select
                value={kind}
                aria-label="What is it"
                onChange={(e) => setKind(e.target.value)}
                style={{ ...input, fontFamily: font.sans }}
              >
                {KINDS.map((k) => (
                  <option key={k} value={k}>
                    {k}
                  </option>
                ))}
              </select>
            </div>
            <div style={{ fontFamily: font.sans, fontSize: 11, color: color.faint, marginTop: 8 }}>
              {dropped.lat.toFixed(5)}, {dropped.lng.toFixed(5)}
            </div>
            <div style={{ display: 'flex', gap: 7, marginTop: 10 }}>
              <button
                type="button"
                disabled={!dropped.name.trim() || busy}
                onClick={() => void save()}
                style={{
                  fontFamily: font.sans,
                  fontSize: 11.5,
                  padding: '6px 14px',
                  borderRadius: 14,
                  border: 'none',
                  cursor: dropped.name.trim() && !busy ? 'pointer' : 'default',
                  background: dropped.name.trim() && !busy ? color.brand : color.ringIdle,
                  color: dropped.name.trim() && !busy ? color.white : color.faint,
                }}
              >
                Drop pin
              </button>
              <button
                type="button"
                onClick={() => setDropped(null)}
                style={{
                  fontFamily: font.sans,
                  fontSize: 11.5,
                  padding: '6px 12px',
                  borderRadius: 14,
                  border: `1px solid ${color.border}`,
                  background: color.paper,
                  color: color.muted,
                  cursor: 'pointer',
                }}
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>

      <div style={shell}>
        {places.length === 0 && (
          <div style={{ padding: 14, fontSize: 13.5, color: color.muted }}>
            No places yet. Search for one, or tap the map where you pay.
          </div>
        )}

        {byKind.map(([k, rows]) => (
          <div key={k} style={{ padding: '12px 13px 4px' }}>
            <span style={label}>{k}</span>
            {rows.map((p) => (
              <div key={p.id}>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 9, padding: '6px 0' }}>
                  <button
                    type="button"
                    className="hov-tint"
                    onClick={() => {
                      setOpen(open === p.id ? null : p.id);
                      map.current?.setView([p.lat, p.lng], 16);
                    }}
                    aria-expanded={open === p.id}
                    style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', textAlign: 'left', minWidth: 0, flex: 1 }}
                  >
                    <span style={{ fontSize: 13.5, fontWeight: 500, color: color.ink }}>
                      {!p.confirmed && <Dot />}
                      {p.name}
                    </span>
                    {p.counterpartyName && (
                      <span style={{ fontFamily: font.sans, fontSize: 11, color: color.faint, marginLeft: 6 }}>
                        {p.counterpartyName}
                      </span>
                    )}
                    <span style={{ display: 'block', fontFamily: font.sans, fontSize: 11, marginTop: 3, color: color.faint }}>
                      {p.payments
                        ? `${p.payments} payment${p.payments > 1 ? 's' : ''}${p.lastSeen ? ` · ${shortDate(p.lastSeen)}` : ''}`
                        : 'nothing spent here yet'}
                      {' · '}
                      {p.radiusM}m
                    </span>
                  </button>
                  <span style={{ fontFamily: font.sans, fontSize: 13.5, fontWeight: p.spent ? 500 : 400, color: p.spent ? color.ink : color.faint, whiteSpace: 'nowrap' }}>
                    {p.spent ? rupees(p.spent) : '—'}
                  </span>
                </div>

                {open === p.id && (
                  <div style={{ padding: '2px 0 10px', animation: 'fadeup 0.2s' }}>
                    {p.address && (
                      <div style={{ fontFamily: font.sans, fontSize: 11, color: color.faint, marginBottom: 7 }}>
                        {p.address}
                      </div>
                    )}
                    {/* The link is what makes a pin show its spend without a
                        single payment being tagged by hand. */}
                    <span style={label}>Whose place</span>
                    <select
                      value={p.counterpartyId ?? ''}
                      aria-label={`Who ${p.name} belongs to`}
                      onChange={(e) =>
                        void onPatch(p.id, { counterparty_id: e.target.value || null })
                      }
                      style={{ ...input, fontFamily: font.sans }}
                    >
                      <option value="">nobody in particular</option>
                      {people.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.name}
                        </option>
                      ))}
                    </select>

                    <div style={{ marginTop: 10 }}>
                      <span style={label}>
                        How big
                        <span style={{ color: color.faint }}>
                          {'  '}a paan shop is 20m, a mall 200m
                        </span>
                      </span>
                      <input
                        defaultValue={p.radiusM}
                        inputMode="numeric"
                        aria-label={`Radius of ${p.name}`}
                        onBlur={(e) => {
                          const n = Number(e.target.value);
                          if (n > 0 && n !== p.radiusM) void onPatch(p.id, { radius_m: n });
                        }}
                        // It saves on blur, so the app's Escape (which blurs a
                        // field) would save it. Escape here puts it back instead.
                        onKeyDown={(e) => {
                          if (e.key !== 'Escape') return;
                          e.preventDefault();
                          e.currentTarget.value = String(p.radiusM);
                          e.currentTarget.blur();
                        }}
                        style={input}
                      />
                    </div>

                    <button
                      type="button"
                      onClick={() => onDelete(p.id)}
                      style={{
                        marginTop: 10,
                        fontFamily: font.sans,
                        fontSize: 11.5,
                        padding: '5px 12px',
                        borderRadius: 14,
                        border: `1px solid ${color.redBorder}`,
                        background: color.redSurface,
                        color: color.red,
                        cursor: 'pointer',
                      }}
                    >
                      Remove pin
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        ))}
        <div style={{ height: 8 }} />
      </div>
    </>
  );
}
