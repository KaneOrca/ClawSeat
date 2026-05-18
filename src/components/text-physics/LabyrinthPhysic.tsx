import React, { useCallback, useEffect, useMemo, useRef } from 'react';
import { prepareWithSegments, layoutNextLine, type LayoutCursor } from '@chenglou/pretext';
import { usePhysicsRegistry, type RectObstacle } from '../../context/PhysicsContext';
import { useLanguage } from '../../context/LanguageContext';
import { usePretextCanvas } from '../../hooks/usePretextCanvas';

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
const MAZE_DRIFT_PX = 24;

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
  const { obstaclesRef, environment } = usePhysicsRegistry();
  const { locale } = useLanguage();
  const envRef = useRef(environment);
  useEffect(() => {
    envRef.current = environment;
  }, [environment]);

  const variantFont = useMemo(() => {
    if (variant === 'v2') {
      return locale === 'zh-CN' ? "400 8px 'Noto Serif SC'" : "400 9px 'Playfair Display'";
    }
    return fontDef;
  }, [variant, fontDef, locale]);

  const prepared = useMemo(() => prepareWithSegments(text, variantFont), [text, variantFont]);

  const render = useCallback((ctx: CanvasRenderingContext2D, width: number, height: number, time: number) => {
    ctx.clearRect(0, 0, width, height);
    ctx.textBaseline = 'top';
    const obstacles = obstaclesRef.current ?? [];
    const env = envRef.current;

    const currentAlpha = env.opacity ?? opacity;
    const currentWaveAmp = env.waveAmplitude ?? 60;
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

    while (currentY < height) {
      ctx.font = variantFont;

      // MULTI-SPAN OBSTACLE AVOIDANCE
      const freeSpans = computeFreeSpans(currentY, lineHeight, width, obstacles);

      // Apply a continuous manuscript drift instead of hard random insets.
      const mazeDrift = Math.sin(currentY * 0.012 + time * 0.00012) * MAZE_DRIFT_PX;
      const spans: Span[] = [];
      for (const span of freeSpans) {
        const s = Math.max(0, span.start + mazeDrift);
        const e = Math.min(width, span.end + mazeDrift);
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
      for (const span of spans) {
        let startX = span.start;

        if (variant === 'v3') {
          const waveShift = Math.sin((currentY * 0.05) + (time * 0.002)) * (20 + currentWaveAmp * 0.2);
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

        const halftone = (Math.sin(currentY * 0.3) + Math.sin(startX * 0.3)) * 0.5 + 0.5;
        let drawX = startX;
        let drawY = currentY;

        if (isTransitioning && transitionFrom === 'v3') {
          drawX += Math.sin(time * 0.002 + currentY * 0.1) * transitionJitter * 15;
          drawY += Math.cos(time * 0.002 + startX * 0.1) * transitionJitter * 15;
        }

        switch (variant) {
          case 'v2': {
            const v2Alpha = currentAlpha;
            ctx.fillStyle = env.ambientColor || `rgba(40, 30, 20, ${Math.min(1, v2Alpha * transitionAlphaScale)})`;
            break;
          }
          case 'v3': {
            const v3Alpha = (currentAlpha * 0.2) + (halftone * 0.2);
            const hueShift = Math.sin(time * 0.001) * 20;
            ctx.fillStyle = env.ambientColor || `hsla(${270 + hueShift}, 70%, 70%, ${Math.min(1, v3Alpha * transitionAlphaScale)})`;
            break;
          }
        }

        ctx.fillText(line.text, drawX, drawY);
        cursor = line.end;
      }

      currentY += lineHeight;
      if (currentY > height) break;
    }
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
