import React, { useMemo, useCallback, useRef } from 'react';
import { prepareWithSegments, layoutNextLine, type LayoutCursor } from '@chenglou/pretext';
import { usePretextCanvas } from '../../hooks/usePretextCanvas';

export interface Soloist {
  id: string;
  text: string;
  lineIndex?: number; // Force to a specific line, or let it flow
  color?: string;
  isFocus?: boolean;
}

interface ChorusPhysicProps {
  text: string;
  soloists?: Soloist[];
  width: number;
  lineHeight: number;
  fontDef: string;
  heavyFontDef?: string;
  amplitude?: number;
  frequency?: number;
  phase?: number;
  color?: string;
  intensity?: number;
}

/**
 * Soloist-Chorus Physics Engine (Variant v3).
 * Integrated HUD: UI elements are rendered as "Soloist" lines in the chorus.
 * Focal Interaction: Mouse proximity settles the wave into a "Calm Void".
 */
export const ChorusPhysic: React.FC<ChorusPhysicProps> = ({ 
  text, 
  soloists = [],
  width: _width, 
  lineHeight, 
  fontDef,
  heavyFontDef,
  amplitude = 50,
  frequency = 0.05,
  phase = 0,
  color = 'rgba(255, 255, 255, 0.4)',
  intensity = 0
}) => {
  const preparedNormal = useMemo(() => prepareWithSegments(text, fontDef), [text, fontDef]);
  
  // Prepare soloists
  const preparedSoloists = useMemo(() => 
    soloists.map(s => ({
      ...s,
      prep: prepareWithSegments(s.text, heavyFontDef || fontDef)
    }))
  , [soloists, heavyFontDef, fontDef]);

  const mouseRef = useRef({ x: -1000, y: -1000 });

  const render = useCallback((ctx: CanvasRenderingContext2D, w: number, h: number) => {
    ctx.clearRect(0, 0, w, h);
    ctx.textBaseline = 'top';

    const mouse = mouseRef.current;
    let cursor: LayoutCursor = { segmentIndex: 0, graphemeIndex: 0 };
    let currentY = 0;
    let lineIdx = 0;

    const interferenceFreq = frequency * 1.5;
    const baseAmp = amplitude * (1 + intensity);

    while (currentY < h) {
      // Find if this line should be a soloist
      const soloist = preparedSoloists.find(s => s.lineIndex === lineIdx || (lineIdx > 10 && lineIdx % 15 === 0 && !s.lineIndex));
      
      // MOUSE INTERACTIVE: Proximity settling
      const distToMouseY = Math.abs(currentY + lineHeight / 2 - mouse.y);
      const mouseFactor = Math.max(0, 1 - distToMouseY / 300); // 300px radius of influence
      const focalSettling = 1 - (mouseFactor * 0.9); // Reduce amplitude near mouse
      
      const currentAmp = baseAmp * focalSettling;
      const primaryWave = Math.sin((currentY * frequency) + phase);
      const interferenceWave = Math.cos((currentY * interferenceFreq) - phase * 0.5);
      
      const waveShift = (primaryWave * currentAmp) + (interferenceWave * currentAmp * 0.3);
      const startX = w * 0.1 + waveShift;
      const availableWidth = w * 0.8 - Math.abs(waveShift);

      // ISOLATION ZONE: Background text yields to Soloists
      const isSoloistZone = preparedSoloists.some(s => 
        s.lineIndex !== undefined && Math.abs(s.lineIndex - lineIdx) <= 1
      );

      if (soloist) {
        ctx.font = heavyFontDef || fontDef;
        ctx.fillStyle = soloist.color || '#fff';
        ctx.globalAlpha = 1;
        
        const line = layoutNextLine(soloist.prep, { segmentIndex: 0, graphemeIndex: 0 }, Math.max(0, availableWidth));
        if (line) ctx.fillText(line.text, startX, currentY);
      } else {
        ctx.font = fontDef;
        ctx.fillStyle = color;
        
        const isolationFactor = isSoloistZone ? 0.05 : 1.0;
        ctx.globalAlpha = 0.3 * (1 - mouseFactor * 0.5) * isolationFactor;

        const line = layoutNextLine(preparedNormal, cursor, Math.max(0, availableWidth));
        if (line) {
          ctx.fillText(line.text, startX, currentY);
          cursor = line.end;
        }
      }

      currentY += lineHeight;
      lineIdx++;
    }
  }, [preparedNormal, preparedSoloists, fontDef, heavyFontDef, amplitude, frequency, phase, color, intensity, lineHeight]);

  const onMouseMove = useCallback((e: React.MouseEvent) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (rect) {
      mouseRef.current = {
        x: e.clientX - rect.left,
        y: e.clientY - rect.top
      };
    }
  }, []);

  const canvasRef = usePretextCanvas({ onRender: render, isAnimated: true });

  return (
    <canvas 
      ref={canvasRef} 
      onMouseMove={onMouseMove}
      style={{ 
        width: '100%', 
        height: '100vh',
        pointerEvents: 'auto', // Now intercepting for conduction
        cursor: 'crosshair'
      }} 
    />
  );
};
