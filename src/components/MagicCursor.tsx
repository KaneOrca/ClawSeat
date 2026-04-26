import { useEffect, useState } from 'react';
import { motion, useSpring } from 'framer-motion';

export function MagicCursor() {
  const [mousePos, setMousePos] = useState({ x: -1000, y: -1000 });
  
  // Spring physics for the organic follow feel
  const springConfig = { damping: 25, stiffness: 150, mass: 1 };
  const cursorX = useSpring(mousePos.x, springConfig);
  const cursorY = useSpring(mousePos.y, springConfig);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      setMousePos({ x: e.clientX, y: e.clientY });
      cursorX.set(e.clientX - 150); // offset by half width
      cursorY.set(e.clientY - 150);
    };

    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, [cursorX, cursorY]);

  return (
    <motion.div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        width: 300,
        height: 300,
        x: cursorX,
        y: cursorY,
        background: 'radial-gradient(circle, rgba(255,255,255,0.15) 0%, transparent 50%)',
        borderRadius: '50%',
        pointerEvents: 'none',
        zIndex: 100,
        mixBlendMode: 'overlay', // Interact with the Aurora background
      }}
    />
  );
}
