import React, { useRef, useState } from 'react';
import { motion, useMotionValue, useSpring, useTransform } from 'framer-motion';

interface MagneticSurfaceProps {
  children: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
  pull?: number; // 0 to 1
  padding?: number;
  activeScale?: number;
}

/**
 * MagneticSurface: Advanced pointer attraction.
 * Wraps elements to provide a high-end magnetic pull effect with spring physics.
 */
export const MagneticSurface: React.FC<MagneticSurfaceProps> = ({ 
  children, 
  className = '', 
  style,
  pull = 0.35,
  padding = 10,
  activeScale = 1.05
}) => {
  const containerRef = useRef<HTMLDivElement>(null);

  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const springConfig = { damping: 20, stiffness: 200, mass: 0.6 };
  const smoothX = useSpring(x, springConfig);
  const smoothY = useSpring(y, springConfig);

  const rotateX = useTransform(smoothY, (v) => v * -0.1);
  const rotateY = useTransform(smoothX, (v) => v * 0.1);

  const [isHovered, setIsHovered] = useState(false);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!containerRef.current) return;
    const { clientX, clientY } = e;
    const { top, left, width, height } = containerRef.current.getBoundingClientRect();
    
    const centerX = left + width / 2;
    const centerY = top + height / 2;
    
    const distanceX = clientX - centerX;
    const distanceY = clientY - centerY;
    
    x.set(distanceX * pull);
    y.set(distanceY * pull);
  };

  return (
    <motion.div
      ref={containerRef}
      className={`relative inline-flex items-center justify-center ${className}`}
      style={{
        ...style,
        padding: `${padding}px`,
        margin: `-${padding}px`,
      }}
      onMouseMove={handleMouseMove}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => {
        setIsHovered(false);
        x.set(0);
        y.set(0);
      }}
    >
      <motion.div
        animate={{ scale: isHovered ? activeScale : 1 }}
        style={{
          x: smoothX,
          y: smoothY,
          rotateX,
          rotateY,
          zIndex: isHovered ? 10 : 1,
          transformStyle: 'preserve-3d',
        }}
        transition={{ type: 'spring', damping: 15, stiffness: 200 }}
      >
        {children}
      </motion.div>
    </motion.div>
  );
};
