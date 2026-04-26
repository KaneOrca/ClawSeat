import React, { useEffect } from 'react';
import { motion, useMotionValue, useSpring, useTransform } from 'framer-motion';

interface SpatialParallaxProps {
  children: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
  depth?: number;
  direction?: 1 | -1;
  tilt?: boolean;
}

/**
 * SpatialParallax: Deep space interaction.
 * Moves content relative to pointer position to create architectural depth.
 */
export const SpatialParallax: React.FC<SpatialParallaxProps> = ({ 
  children, 
  className = '', 
  style,
  depth = 0.05,
  direction = -1,
  tilt = false
}) => {
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  
  const springConfig = { damping: 40, stiffness: 80, mass: 1 };
  const smoothX = useSpring(x, springConfig);
  const smoothY = useSpring(y, springConfig);

  const rotateX = useTransform(smoothY, (v) => tilt ? v * -0.05 : 0);
  const rotateY = useTransform(smoothX, (v) => tilt ? v * 0.05 : 0);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      const centerX = window.innerWidth / 2;
      const centerY = window.innerHeight / 2;
      
      const distanceX = e.clientX - centerX;
      const distanceY = e.clientY - centerY;
      
      x.set(distanceX * depth * direction);
      y.set(distanceY * depth * direction);
    };

    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, [x, y, depth, direction]);

  return (
    <motion.div
      className={className}
      style={{
        ...style,
        x: smoothX,
        y: smoothY,
        rotateX,
        rotateY,
        transformStyle: 'preserve-3d',
      }}
    >
      {children}
    </motion.div>
  );
};
