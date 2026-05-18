import type { MutableRefObject } from 'react';
import type { RectObstacle } from '../PhysicsContext';

export interface MaskBuffer {
  canvas: HTMLCanvasElement;
  ctx: CanvasRenderingContext2D;
  width: number;
  height: number;
  dirty: boolean;
}

export function renderMask(
  tracked: Map<string, HTMLElement>,
  obstacles: RectObstacle[],
  bufRef: MutableRefObject<MaskBuffer | null>,
) {
  const w = window.innerWidth;
  const h = window.innerHeight;

  let buf = bufRef.current;
  if (!buf || buf.width !== w || buf.height !== h) {
    const canvas = buf?.canvas ?? document.createElement('canvas');
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    if (!ctx) return;
    buf = { canvas, ctx, width: w, height: h, dirty: false };
    bufRef.current = buf;
  }

  const { ctx } = buf;
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = 'white';
  ctx.textBaseline = 'top';

  for (const obs of obstacles) {
    if (obs.y + obs.h < 0 || obs.y > h || obs.x + obs.w < 0 || obs.x > w) continue;

    const el = tracked.get(obs.id);
    if (!el) {
      // Mouse handled via direct distance-push in physics engines
      continue;
    }

    try {
      const style = getComputedStyle(el);
      const font = `${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
      ctx.font = font;

      if (obs.charRects && obs.charRects.length > 0) {
        for (const cr of obs.charRects) {
          ctx.fillText(cr.char, cr.x, cr.y);
        }
      } else {
        const fontSize = parseFloat(style.fontSize);
        const yOffset = (obs.h - fontSize) * 0.35;
        ctx.fillText(el.textContent ?? '', obs.x, obs.y + yOffset);
      }
    } catch {
      // Skip
    }
  }

  buf.dirty = true;
}
