import React, { useRef, useEffect, useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { prepareWithSegments, layoutNextLineRange, materializeLineRange } from '@chenglou/pretext';

interface PretextEditorialProps {
  text: string;
  width: number;
  fontDef?: string;
  lineHeight?: number;
  className?: string;
  style?: React.CSSProperties;
  color?: string;
  delay?: number;
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
  delay = 0
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [lines, setLines] = useState<string[]>([]);
  const [containerWidth, setContainerWidth] = useState(width);

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

  return (
    <div 
      ref={containerRef} 
      className={`relative ${className}`} 
      style={{ ...style, width: '100%', minHeight: lines.length * lineHeight }}
    >
      <AnimatePresence>
        {lines.map((line, index) => (
          <motion.div
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
            {line}
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
};
