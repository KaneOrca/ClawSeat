import React, { useMemo, useCallback } from 'react';
import { prepareWithSegments, layoutNextLine, type LayoutCursor } from '@chenglou/pretext';
import { usePretextCanvas } from '../../hooks/usePretextCanvas';
import type { RectObstacle } from '../../types/physics';

interface ManuscriptPhysicProps {
  text: string;
  obstacles: RectObstacle[];
  width: number;
  lineHeight: number;
  fontDef: string;
  color?: string;
}

/**
 * Editorial Physics Engine for Variant v2 (Manuscript).
 * Wraps text around rectangular obstacles (Marginalia Rail).
 */
export const ManuscriptPhysic: React.FC<ManuscriptPhysicProps> = ({ 
  text, 
  obstacles, 
  width: _width, 
  lineHeight, 
  fontDef,
  color = 'rgba(26, 26, 26, 0.9)'
}) => {
  const prepared = useMemo(() => prepareWithSegments(text, fontDef), [text, fontDef]);

  const render = useCallback((ctx: CanvasRenderingContext2D, w: number, h: number) => {
    ctx.clearRect(0, 0, w, h);
    ctx.font = fontDef;
    ctx.fillStyle = color;
    ctx.textBaseline = 'top';

    let cursor: LayoutCursor = { segmentIndex: 0, graphemeIndex: 0 };
    let currentY = 0;
    const padding = 30;

    while (currentY < h) {
      let startX = 0;
      let availableWidth = w;

      for (const rect of obstacles) {
        if (currentY + lineHeight > rect.y && currentY < rect.y + rect.h) {
          if (rect.x < w / 2) {
            startX = Math.max(startX, rect.x + rect.w + padding);
          } else {
            availableWidth = Math.min(availableWidth, rect.x - padding - startX);
          }
        }
      }

      const line = layoutNextLine(prepared, cursor, Math.max(0, availableWidth));
      if (!line) break;

      ctx.fillText(line.text, startX, currentY);
      cursor = line.end;
      currentY += lineHeight;
    }
  }, [prepared, obstacles, fontDef, color, lineHeight]);

  const canvasRef = usePretextCanvas({ onRender: render, isAnimated: false });

  return (
    <canvas 
      ref={canvasRef} 
      style={{ 
        width: '100%', 
        height: '100vh',
        pointerEvents: 'none'
      }} 
    />
  );
};
