import React, { useMemo, useCallback } from 'react';
import { prepareWithSegments, layoutNextLine, type LayoutCursor } from '@chenglou/pretext';
import { usePretextCanvas } from '../hooks/usePretextCanvas';
import type { OrbObstacle } from '../types/physics';

interface PhysicsTextProps {
  text: string;
  orbs: OrbObstacle[];
  width: number;
  lineHeight: number;
  fontDef: string;
}

/**
 * The "Generative Nebula" engine component.
 * It uses @chenglou/pretext to calculate line-by-line wrapping around 
 * dynamic circular obstacles (Gemini Orbs).
 */
export const PhysicsText: React.FC<PhysicsTextProps> = ({ 
  text, 
  orbs, 
  width: _width, 
  lineHeight, 
  fontDef 
}) => {
  const prepared = useMemo(() => prepareWithSegments(text, fontDef), [text, fontDef]);

  const render = useCallback((ctx: CanvasRenderingContext2D, w: number, h: number) => {
    ctx.clearRect(0, 0, w, h);
    ctx.font = fontDef;
    ctx.fillStyle = 'rgba(255, 255, 255, 0.7)';
    ctx.textBaseline = 'top';

    let cursor: LayoutCursor = { segmentIndex: 0, graphemeIndex: 0 };
    let currentY = 0;
    const padding = 20;

    while (currentY < h) {
      let startX = 0;
      let availableWidth = w;
      let maxOrbIntensity = 0;

      for (const orb of orbs) {
        const dy = Math.abs((currentY + lineHeight / 2) - orb.y);
        
        // Calculate intensity based on distance to the orb center
        const dxCenter = Math.min(w, Math.max(0, orb.x)) - orb.x;
        const dist = Math.sqrt(Math.pow(currentY - orb.y, 2) + Math.pow(dxCenter, 2));
        
        const intensity = Math.max(0, 1 - dist / (orb.r * 2));
        maxOrbIntensity = Math.max(maxOrbIntensity, intensity);

        if (dy < orb.r) {
          const dx = Math.sqrt(Math.pow(orb.r, 2) - Math.pow(dy, 2));
          if (orb.x < w / 2) {
            startX = Math.max(startX, orb.x + dx + padding);
          } else {
            availableWidth = Math.min(availableWidth, orb.x - dx - padding - startX);
          }
        }
      }

      const line = layoutNextLine(prepared, cursor, Math.max(0, availableWidth));
      if (!line) break;

      // VISUAL TENSION: Scale opacity and add glow based on proximity to active orbs
      ctx.globalAlpha = 0.2 + (maxOrbIntensity * 0.8);
      ctx.shadowBlur = maxOrbIntensity > 0.4 ? 8 * maxOrbIntensity : 0;
      ctx.shadowColor = 'rgba(255, 255, 255, 0.4)';

      ctx.fillText(line.text, startX, currentY);
      cursor = line.end;
      currentY += lineHeight;
    }
  }, [prepared, orbs, fontDef, lineHeight]);

  const canvasRef = usePretextCanvas({ onRender: render, isAnimated: false });

  return (
    <canvas 
      ref={canvasRef} 
      style={{ 
        width: '100%', 
        height: '100vh',
        pointerEvents: 'none',
        mixBlendMode: 'lighten'
      }} 
    />
  );
};
