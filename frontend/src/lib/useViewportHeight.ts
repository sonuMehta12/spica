import { useEffect } from 'react';

/**
 * Publishes the *visible* viewport height as `--app-h`.
 *
 * `interactive-widget=resizes-content` already does this on Android Chrome, but
 * iOS Safari ignores it: there the keyboard only shrinks the visual viewport, so
 * a `100dvh` shell overflows and the browser scrolls the header out of view.
 * Tracking visualViewport covers both.
 */
export function useViewportHeight(): void {
  useEffect(() => {
    const vv = window.visualViewport;
    const apply = () => {
      const h = vv ? vv.height : window.innerHeight;
      document.documentElement.style.setProperty('--app-h', `${Math.round(h)}px`);
    };
    apply();
    if (vv) {
      vv.addEventListener('resize', apply);
      // iOS shifts the visual viewport instead of resizing when the caret moves.
      vv.addEventListener('scroll', apply);
    }
    window.addEventListener('orientationchange', apply);
    return () => {
      if (vv) {
        vv.removeEventListener('resize', apply);
        vv.removeEventListener('scroll', apply);
      }
      window.removeEventListener('orientationchange', apply);
    };
  }, []);
}
