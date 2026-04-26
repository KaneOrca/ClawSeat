import { useEffect, useRef } from 'react';

interface UsePretextCanvasProps {
  onRender: (ctx: CanvasRenderingContext2D, width: number, height: number, time: number) => void;
  isAnimated?: boolean;
}

/**
 * Canvas hook with DPR scaling.
 * Resize only on ResizeObserver — never in the animation loop.
 */
export function usePretextCanvas({ onRender, isAnimated = false }: UsePretextCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const renderRef = useRef(onRender);
  const sizeRef = useRef({ width: 0, height: 0 });

  useEffect(() => {
    renderRef.current = onRender;
  }, [onRender]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let frame: number;

    const resize = () => {
      const dpr = window.devicePixelRatio || 1;
      const width = canvas.clientWidth;
      const height = canvas.clientHeight;

      if (canvas.width !== width * dpr || canvas.height !== height * dpr) {
        canvas.width = width * dpr;
        canvas.height = height * dpr;
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      }

      sizeRef.current = { width, height };
    };

    // Initial size
    resize();

    const loop = (time: number) => {
      const { width, height } = sizeRef.current;
      renderRef.current(ctx, width, height, time);
      if (isAnimated) {
        frame = requestAnimationFrame(loop);
      }
    };

    if (isAnimated) {
      frame = requestAnimationFrame(loop);
    } else {
      renderRef.current(ctx, sizeRef.current.width, sizeRef.current.height, 0);
    }

    const observer = new ResizeObserver(() => {
      resize();
      if (!isAnimated) {
        renderRef.current(ctx, sizeRef.current.width, sizeRef.current.height, 0);
      }
    });
    observer.observe(canvas);

    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
    };
  }, [isAnimated]);

  return canvasRef;
}
