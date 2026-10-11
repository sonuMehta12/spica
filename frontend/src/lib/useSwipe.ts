import { useRef, useState, type PointerEvent as ReactPointerEvent } from 'react';

interface Options {
  index: number;
  count: number;
  onIndex: (i: number) => void;
}

/** Travel before we decide whether this gesture is a horizontal swipe or a vertical scroll. */
const AXIS_LOCK = 8;
/** Fraction of the deck width that counts as a page turn. */
const COMMIT_RATIO = 0.22;
/** A flick this fast turns the page whatever the distance, in px per ms. */
const FLICK = 0.5;

/**
 * Drag-to-page for a ring of cards. Locks to one axis on the first few pixels
 * so a vertical scroll never gets hijacked. There are no ends to rubber-band
 * against: past the last card is the first. A drag is held to one card's
 * width each way — beyond that there is no card to show.
 */
export function useSwipe({ index, count, onIndex }: Options) {
  const [drag, setDrag] = useState(0);
  const [dragging, setDragging] = useState(false);

  const origin = useRef<{ x: number; y: number } | null>(null);
  const axis = useRef<'none' | 'x' | 'y'>('none');
  const width = useRef(1);
  // Authoritative during the gesture; `drag` state exists only to re-render.
  const offset = useRef(0);
  // The last two moves — enough for the speed at release.
  const trail = useRef<{ x: number; t: number }[]>([]);

  const reset = () => {
    origin.current = null;
    axis.current = 'none';
    offset.current = 0;
    trail.current = [];
    setDrag(0);
    setDragging(false);
  };

  const onPointerDown = (e: ReactPointerEvent<HTMLDivElement>) => {
    if (!e.isPrimary || e.button !== 0) return;
    origin.current = { x: e.clientX, y: e.clientY };
    axis.current = 'none';
    width.current = e.currentTarget.clientWidth || 1;
    trail.current = [{ x: e.clientX, t: e.timeStamp }];
    setDragging(true);
  };

  const onPointerMove = (e: ReactPointerEvent<HTMLDivElement>) => {
    const from = origin.current;
    if (!from) return;
    const dx = e.clientX - from.x;
    const dy = e.clientY - from.y;

    if (axis.current === 'none') {
      if (Math.abs(dx) < AXIS_LOCK && Math.abs(dy) < AXIS_LOCK) return;
      axis.current = Math.abs(dx) > Math.abs(dy) ? 'x' : 'y';
      if (axis.current === 'x') {
        // Throws if the pointer is no longer active — losing capture just means
        // the gesture ends early, so it must not break the drag.
        try {
          e.currentTarget.setPointerCapture(e.pointerId);
        } catch {
          /* no capture available; the move handler still works */
        }
      }
    }
    if (axis.current !== 'x') return;

    const next = Math.max(-width.current, Math.min(width.current, dx));
    offset.current = next;
    trail.current = [...trail.current.slice(-1), { x: e.clientX, t: e.timeStamp }];
    setDrag(next);
  };

  const onPointerUp = () => {
    const [a, b] = trail.current;
    const speed = a && b && b.t > a.t ? (b.x - a.x) / (b.t - a.t) : 0;
    const direction = Math.sign(offset.current);
    const far = Math.abs(offset.current) > width.current * COMMIT_RATIO;
    const flick = Math.abs(speed) > FLICK && Math.sign(speed) === direction;
    const committed = axis.current === 'x' && direction !== 0 && (far || flick);
    reset();
    if (committed) onIndex((index - direction + count) % count);
  };

  return {
    drag,
    dragging,
    /** The deck's width at the start of the gesture — what a drag is measured against. */
    width: width.current,
    /**
     * Spread onto the element that should receive the gesture.
     *
     * Deliberately no `onLostPointerCapture`: it can land *before* `pointerup`,
     * and resetting there throws away a gesture the user actually completed.
     * `pointerup` commits, `pointercancel` abandons — that covers both endings.
     */
    handlers: {
      onPointerDown,
      onPointerMove,
      onPointerUp,
      onPointerCancel: reset,
    },
  };
}
