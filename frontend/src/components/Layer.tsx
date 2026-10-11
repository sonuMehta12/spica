import { useEffect, useRef, type ReactNode } from 'react';
import { LayerDepth } from '../state/nav';

/**
 * One screen of the back stack, drawn over the ones under it. Lower layers
 * stay mounted — same scroll, same tab, no entrance replayed when they show
 * again — but inert and hidden from screen readers, so only the top one takes
 * a tap, a Tab or a Back step (state/nav.ts § useBack).
 *
 * On opening, focus moves into the screen, unless something inside already
 * took it (an editor opened by Edit goal, a sheet's first field).
 */
export default function Layer({ depth, top, children }: { depth: number; top: boolean; children: ReactNode }) {
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const dialog = box.current?.querySelector<HTMLElement>('[role="dialog"]');
    if (dialog && !dialog.contains(document.activeElement)) dialog.focus({ preventScroll: true });
  }, []);
  return (
    <LayerDepth.Provider value={depth}>
      <div
        ref={box}
        data-layer={depth}
        inert={!top}
        aria-hidden={top ? undefined : true}
        style={{ position: 'absolute', inset: 0, zIndex: 60 + depth }}
      >
        {children}
      </div>
    </LayerDepth.Provider>
  );
}
