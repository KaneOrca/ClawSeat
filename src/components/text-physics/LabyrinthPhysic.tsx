import React, { useMemo, useCallback, useRef, useEffect } from 'react';
import { prepareWithSegments, layoutNextLine, type LayoutCursor } from '@chenglou/pretext';
import { usePhysicsRegistry, type RectObstacle } from '../../context/PhysicsContext';
import { usePretextCanvas } from '../../hooks/usePretextCanvas';
import { useLanguage } from '../../context/LanguageContext';

interface LabyrinthPhysicProps {
  text: string;
  fontDef: string;
  lineHeight: number;
  opacity?: number;
  variant: 'v2' | 'v3';
}

interface Span {
  start: number;
  end: number;
}

const PADDING = 8;
const MIN_SPAN_WIDTH = 20;

/**
 * Compute free X-axis spans for a given Y row by subtracting all
 * overlapping obstacles from the full width.
 */
function computeFreeSpans(
  y: number,
  lineHeight: number,
  width: number,
  obstacles: RectObstacle[],
): Span[] {
  // Collect blocked X-ranges that overlap this Y row.
  // When charRects are available, block per-character instead of whole AABB.
  const blocked: Span[] = [];
  for (const obs of obstacles) {
    if (!(y + lineHeight > obs.y && y < obs.y + obs.h)) continue;

    if (obs.charRects && obs.charRects.length > 0) {
      for (const cr of obs.charRects) {
        if (y + lineHeight > cr.y && y < cr.y + cr.h) {
          blocked.push({
            start: Math.max(0, cr.x - PADDING),
            end: Math.min(width, cr.x + cr.w + PADDING),
          });
        }
      }
    } else {
      blocked.push({
        start: Math.max(0, obs.x - PADDING),
        end: Math.min(width, obs.x + obs.w + PADDING),
      });
    }
  }

  if (blocked.length === 0) {
    return [{ start: 0, end: width }];
  }

  // Sort by start, merge overlapping
  blocked.sort((a, b) => a.start - b.start);
  const merged: Span[] = [blocked[0]];
  for (let i = 1; i < blocked.length; i++) {
    const prev = merged[merged.length - 1];
    if (blocked[i].start <= prev.end) {
      prev.end = Math.max(prev.end, blocked[i].end);
    } else {
      merged.push(blocked[i]);
    }
  }

  // Invert to get free spans
  const free: Span[] = [];
  let cursor = 0;
  for (const block of merged) {
    if (block.start > cursor) {
      free.push({ start: cursor, end: block.start });
    }
    cursor = block.end;
  }
  if (cursor < width) {
    free.push({ start: cursor, end: width });
  }

  return free.filter(s => (s.end - s.start) >= MIN_SPAN_WIDTH);
}

/**
 * The Luminescent Labyrinth Engine (Refactored).
 * High-density background field with multi-span obstacle avoidance.
 */
export const LabyrinthPhysic: React.FC<LabyrinthPhysicProps> = ({
  text,
  fontDef,
  lineHeight,
  opacity = 0.15,
  variant
}) => {
  const mouseRef = useRef({ x: -1000, y: -1000 });
  const { obstaclesRef, soloists, environment } = usePhysicsRegistry();
  const { locale } = useLanguage();

  // Keep soloists + environment in refs so the render callback is stable
  const soloistsRef = useRef(soloists);
  useEffect(() => { soloistsRef.current = soloists; }, [soloists]);
  const envRef = useRef(environment);
  useEffect(() => { envRef.current = environment; }, [environment]);

  const variantFont = useMemo(() => {
    if (variant === 'v2') {
      return locale === 'zh-CN' ? "400 8px 'Noto Serif SC'" : "400 9px 'Playfair Display'";
    }
    return fontDef;
  }, [variant, fontDef, locale]);

  const prepared = useMemo(() => prepareWithSegments(text, variantFont), [text, variantFont]);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      mouseRef.current = { x: e.clientX, y: e.clientY };
    };
    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, []);

  const render = useCallback((ctx: CanvasRenderingContext2D, width: number, height: number, time: number) => {
    ctx.clearRect(0, 0, width, height);
    ctx.textBaseline = 'top';
    const obstacles = obstaclesRef.current ?? [];
    const env = envRef.current;

    const currentAlpha = env.opacity ?? opacity;
    const currentWaveAmp = env.waveAmplitude ?? 60;
    const surgeNorm = Math.max(0, (currentWaveAmp - 60) / 60);
    const transition = env.effects;
    const transitionProgress = transition?.transitionProgress ?? 0;
    const transitionFrom = transition?.transitionFrom ?? null;
    const isTransitioning = !!transitionFrom && transitionProgress > 0;
    const transitionJitter = isTransitioning ? Math.max(0, Math.min(1, (currentWaveAmp - 60) / 90)) : 0;
    const transitionAlphaScale = !isTransitioning
      ? 1
      : transitionFrom === 'v3'
        ? transitionProgress
        : 1 - transitionProgress;

    let cursor: LayoutCursor = { segmentIndex: 0, graphemeIndex: 0 };
    let currentY = 0;
    const mouse = mouseRef.current;

    // TRACKING LINES FOR SOLOISTS
    const lineMap: Map<number, { text: string; x: number }> = new Map();

    while (currentY < height) {
      ctx.font = variantFont;

      // MAZE LOGIC
      let mazeInsetLeft = 0;
      let mazeInsetRight = 0;
      const pathSeed = Math.sin(currentY * 0.01) * 100;
      if (pathSeed > 88) { mazeInsetLeft = 60; }
      if (pathSeed < -88) { mazeInsetRight = 60; }

      // MULTI-SPAN OBSTACLE AVOIDANCE
      const freeSpans = computeFreeSpans(currentY, lineHeight, width, obstacles);

      // Apply maze insets to spans
      const spans: Span[] = [];
      for (const span of freeSpans) {
        let s = span.start;
        let e = span.end;
        if (s < mazeInsetLeft) s = mazeInsetLeft;
        if (e > width - mazeInsetRight) e = width - mazeInsetRight;
        if (e - s >= MIN_SPAN_WIDTH) {
          spans.push({ start: s, end: e });
        }
      }

      // If no drawable spans, advance line
      if (spans.length === 0) {
        currentY += lineHeight;
        continue;
      }

      // FILL EACH SPAN WITH TEXT
      let drewAnything = false;
      for (const span of spans) {
        let startX = span.start;

        // VARIANT-SPECIFIC WAVE WARPING (V3)
        // Apply wave shift then clamp to safe span bounds so text
        // never drifts into obstacle regions.
        if (variant === 'v3') {
          const spanMidX = (span.start + span.end) / 2;
          const distToMouse = Math.sqrt(
            Math.pow(currentY - mouse.y, 2) +
            Math.pow(spanMidX - mouse.x, 2)
          );
          const mouseFactor = Math.max(0, 1 - distToMouse / 400);
          const waveShift = Math.sin((currentY * 0.05) + (time * 0.002)) * (20 + currentWaveAmp * mouseFactor);
          startX += waveShift;
        }

        // Clamp startX within the safe span
        startX = Math.max(span.start, Math.min(startX, span.end - MIN_SPAN_WIDTH));
        const clampedWidth = span.end - startX;

        if (clampedWidth < MIN_SPAN_WIDTH) continue;

        const line = layoutNextLine(prepared, cursor, clampedWidth);
        if (!line) {
          cursor = { segmentIndex: 0, graphemeIndex: 0 };
          continue;
        }

        // VARIANT-SPECIFIC STYLING
        const distToMouse = Math.sqrt(
          Math.pow(currentY - mouse.y, 2) +
          Math.pow(startX + clampedWidth / 2 - mouse.x, 2)
        );
        const mouseFactor = Math.max(0, 1 - distToMouse / 400);
        const halftone = (Math.sin(currentY * 0.3) + Math.sin(startX * 0.3)) * 0.5 + 0.5;
        let drawX = startX;
        let drawY = currentY;

        if (isTransitioning && transitionFrom === 'v3') {
          drawX += Math.sin(time * 0.002 + currentY * 0.1) * transitionJitter * 15;
          drawY += Math.cos(time * 0.002 + startX * 0.1) * transitionJitter * 15;
        }

        switch (variant) {
          case 'v2': {
            const v2Alpha = 0.05 + Math.pow(mouseFactor, 3) * 0.8;
            ctx.fillStyle = env.ambientColor || `rgba(40, 30, 20, ${Math.min(1, v2Alpha * transitionAlphaScale)})`;
            break;
          }
          case 'v3': {
            const v3Alpha = (currentAlpha * 0.2) + (halftone * 0.2) + (Math.pow(mouseFactor, 1.5) * 1.2);
            const hueShift = Math.sin(time * 0.001) * 20;
            ctx.fillStyle = env.ambientColor || `hsla(${270 + hueShift}, 70%, 70%, ${Math.min(1, v3Alpha * transitionAlphaScale)})`;
            break;
          }
        }

        ctx.fillText(line.text, drawX, drawY);

        // Store first span position for soloist mapping
        if (!drewAnything) {
          const currentLineIndex = Math.floor(currentY / lineHeight);
          lineMap.set(currentLineIndex, { text: line.text, x: drawX });
          drewAnything = true;
        }

        cursor = line.end;
      }

      currentY += lineHeight;
      if (currentY > height) break;
    }

    // RENDER SOLOISTS
    (soloistsRef.current ?? []).forEach(soloist => {
      const lineData = lineMap.get(soloist.lineIndex);
      if (lineData) {
        const distToMouse = Math.sqrt(
          Math.pow(soloist.lineIndex * lineHeight - mouse.y, 2) +
          Math.pow(lineData.x - mouse.x, 2)
        );
        const mouseFactor = Math.max(0, 1 - distToMouse / 400);

        ctx.font = `900 ${variant === 'v2' ? '32px' : '48px'} ${variant === 'v2' ? 'serif' : 'sans-serif'}`;
        ctx.fillStyle = soloist.color || '#fff';
        ctx.globalAlpha = 0.3 + surgeNorm * 0.7;
        const soloistCtx = ctx as CanvasRenderingContext2D & { letterSpacing?: string };
        if (surgeNorm > 0.8) {
          ctx.filter = `blur(${surgeNorm * 2}px)`;
          soloistCtx.letterSpacing = `${surgeNorm * 10}px`;
        }
        ctx.fillText(soloist.text, lineData.x, soloist.lineIndex * lineHeight - 10);
        ctx.filter = 'none';
        soloistCtx.letterSpacing = '0px';
        ctx.globalAlpha = 1;
      }
    });

  }, [prepared, obstaclesRef, variantFont, lineHeight, opacity, variant]);

  const canvasRef = usePretextCanvas({ onRender: render, isAnimated: true });

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: 'absolute',
        inset: 0,
        width: '100%',
        height: '100%',
        pointerEvents: 'none',
      }}
    />
  );
};
