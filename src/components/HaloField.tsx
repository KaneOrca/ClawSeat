import React, { useRef, useState } from 'react';
import { motion, useMotionValue, useSpring, useTransform } from 'framer-motion';

import { tokens } from '../design/tokens';

interface HaloFieldProps {
  children: React.ReactNode;
  id?: string;
  className?: string;
  style?: React.CSSProperties;
  intensity?: number;
  color?: string;
  size?: number;
}

/**
 * HaloField: A flagship Gemini-inspired light field.
 * It tracks the mouse and creates a soft, refractive aura that feels intelligent.
 */
export const HaloField: React.FC<HaloFieldProps> = ({ 
  children, 
  id,
  className = '', 
  style,
  intensity = 0.12,
  color = 'var(--aurora-1)',
  size = 600
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);
  
  const springConfig = { damping: 40, stiffness: 120, mass: 1 };
  const smoothX = useSpring(mouseX, springConfig);
  const smoothY = useSpring(mouseY, springConfig);

  const [isHovered, setIsHovered] = useState(false);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left - rect.width / 2;
    const y = e.clientY - rect.top - rect.height / 2;
    mouseX.set(x);
    mouseY.set(y);
  };

  const haloBackground = useTransform(
    [smoothX, smoothY],
    ([xVal, yVal]) => {
      const x = xVal as number;
      const y = yVal as number;
      return `
        radial-gradient(
          ${size}px circle at calc(50% + ${x}px) calc(50% + ${y}px), 
          ${color}${Math.floor(intensity * 255).toString(16).padStart(2, '0')} 0%, 
          transparent 100%
        )
      `;
    }
  );

  return (
    <motion.div
      ref={containerRef}
      id={id}
      className={`relative ${className}`}
      style={{ ...style }}
      onMouseMove={handleMouseMove}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => {
        setIsHovered(false);
        mouseX.set(0);
        mouseY.set(0);
      }}
    >
      {/* The Intelligence Field Layer */}
      <motion.div
        className="pointer-events-none absolute inset-0 z-0"
        style={{
          background: haloBackground,
          opacity: isHovered ? 0.6 : 0,
          mixBlendMode: 'plus-lighter',
          filter: 'blur(80px)',
          transition: 'opacity 1.2s ease-in-out'
        }}
      />
      
      {/* Noise Texture for High-End Quality */}
      <div className="pointer-events-none absolute inset-0 z-0 opacity-[0.02] mix-blend-overlay" 
           style={{ backgroundImage: tokens.effects.noise }} />

      <div className="relative z-10 w-full h-full">
        {children}
      </div>
    </motion.div>
  );
};
