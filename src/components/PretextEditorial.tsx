import React, { useRef, useEffect, useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { prepareWithSegments, layoutNextLineRange, materializeLineRange } from '@chenglou/pretext';
import { tokens } from '../design/tokens';

interface PretextEditorialProps {
  text: string;
  width: number;
  fontDef?: string;
  lineHeight?: number;
  className?: string;
  style?: React.CSSProperties;
  color?: string;
  delay?: number;
  revealProgress?: number;
}

const HEX = '0123456789ABCDEF';

function clamp(n: number, min: number, max: number) {
  return Math.max(min, Math.min(max, n));
}

function edgeJitter(lineIndex: number, charIndex: number, diff: number) {
  if (diff >= 0.1) return 0;
  const seed = Math.sin((lineIndex + 1) * 19.19 + (charIndex + 1) * 37.37);
  return seed * 2.5 * (1 - diff / 0.1);
}

/**
 * PretextEditorial: Flagship typographic composition.
 * Uses @chenglou/pretext for precise layout and adds a line-by-line reveal effect.
 */
export const PretextEditorial: React.FC<PretextEditorialProps> = ({
  text,
  width,
  fontDef = "400 16px Satoshi",
  lineHeight = 24,
  className = '',
  style,
  color = 'var(--text-secondary)',
  delay = 0,
  revealProgress
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [lines, setLines] = useState<string[]>([]);
  const [containerWidth, setContainerWidth] = useState(width);
  const [internalRevealProgress, setInternalRevealProgress] = useState(0);
  const hasRevealedRef = useRef(false);
  const rafRef = useRef<number | null>(null);
  const reveal = revealProgress ?? internalRevealProgress;

  const prepared = useMemo(() => {
    try {
      return prepareWithSegments(text, fontDef);
    } catch (e) {
      console.error("Pretext prepare error:", e);
      return null;
    }
  }, [text, fontDef]);

  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver((entries) => {
      for (let entry of entries) {
        setContainerWidth(Math.floor(entry.contentRect.width));
      }
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!prepared) return;
    
    let cursor = { segmentIndex: 0, graphemeIndex: 0 };
    let currentLines: string[] = [];

    try {
      while (true) {
        const range = layoutNextLineRange(prepared, cursor, containerWidth);
        if (range === null) break;
        const line = materializeLineRange(prepared, range);
        currentLines.push(line.text);
        cursor = range.end;
        if (currentLines.length > 500) break;
      }
      setLines(currentLines);
    } catch (e) {
      console.error("Pretext layout error:", e);
      setLines([text]);
    }
  }, [prepared, containerWidth, text]);

  useEffect(() => {
    if (revealProgress !== undefined || !containerRef.current) return;

    const node = containerRef.current;
    const startReveal = () => {
      if (hasRevealedRef.current) return;
      hasRevealedRef.current = true;

      const duration = 800;
      const delayMs = delay * 1000;
      const startAt = performance.now() + delayMs;

      const step = (now: number) => {
        if (now < startAt) {
          rafRef.current = requestAnimationFrame(step);
          return;
        }

        const p = clamp((now - startAt) / duration, 0, 1);
        setInternalRevealProgress(p);
        if (p < 1) {
          rafRef.current = requestAnimationFrame(step);
        } else {
          rafRef.current = null;
        }
      };

      rafRef.current = requestAnimationFrame(step);
    };

    const observer = new IntersectionObserver((entries) => {
      if (entries.some(entry => entry.isIntersecting)) startReveal();
    }, { threshold: 0.15 });

    observer.observe(node);
    return () => {
      observer.disconnect();
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    };
  }, [delay, revealProgress]);

  const textCols = useMemo(() => Math.max(1, ...lines.map(line => line.length)), [lines]);

  return (
    <div 
      ref={containerRef} 
      className={`relative ${className}`} 
      style={{ ...style, width: '100%', minHeight: lines.length * lineHeight }}
    >
      <AnimatePresence>
        {lines.map((line, index) => (
          <motion.div
            className="pretext-editorial-line"
            key={`${index}-${line.substring(0, 10)}`}
            initial={{ opacity: 0, y: 10, filter: 'blur(4px)' }}
            animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
            transition={{ 
              duration: 0.8, 
              delay: delay + index * 0.05,
              ease: [0.16, 1, 0.3, 1]
            }}
            style={{
              position: 'absolute',
              top: index * lineHeight,
              left: 0,
              font: fontDef,
              color: color,
              whiteSpace: 'pre',
            }}
          >
            {Array.from(line).map((char, charIndex) => {
              const lineBase = lines.length > 1 ? index / lines.length : 0;
              const slotProgress = clamp(lineBase + (charIndex / textCols) / Math.max(1, lines.length), 0, 1);
              const diff = Math.abs(reveal - slotProgress);
              const isResolved = reveal > slotProgress;
              const isTextSlot = char.trim().length > 0;
              const dormantChar = isTextSlot ? HEX[(index * 7 + charIndex) % HEX.length] : '\u00a0';

              return (
                <span
                  key={`${index}-${charIndex}`}
                  style={{
                    display: 'inline-block',
                    minWidth: char === ' ' ? '0.35em' : undefined,
                    fontFamily: isResolved ? undefined : tokens.fonts.mono,
                    color,
                    opacity: isResolved ? 1 : (isTextSlot ? 0.25 : 0.1),
                    transform: `translateX(${edgeJitter(index, charIndex, diff)}px)`,
                    transition: 'opacity 80ms linear',
                  }}
                >
                  {isResolved ? (char === ' ' ? '\u00a0' : char) : dormantChar}
                </span>
              );
            })}
          </motion.div>
        ))}
      </AnimatePresence>
      <style>{`
        @media (max-width: 768px) {
          .pretext-editorial-line {
            position: relative !important;
            top: auto !important;
            left: auto !important;
          }
        }
      `}</style>
    </div>
  );
};
