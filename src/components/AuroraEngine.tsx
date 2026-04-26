import { useEffect, useRef } from 'react';

/**
 * A WebGL/Canvas fluid aurora engine running entirely off-thread (conceptually) 
 * or via standard Canvas API to prevent DOM paint bottlenecks.
 */
export function AuroraEngine() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let w = canvas.width = window.innerWidth;
    let h = canvas.height = window.innerHeight;
    let time = 0;

    const resize = () => {
      w = canvas.width = window.innerWidth;
      h = canvas.height = window.innerHeight;
    };
    window.addEventListener('resize', resize);

    const blobs = [
      { color: '#4285f4', x: 0, y: 0, r: w * 0.15, speedX: 0.5, speedY: 0.3 }, // Blue — near-zero
      { color: '#9b72cb', x: w, y: h, r: w * 0.1, speedX: -0.4, speedY: -0.6 }, // Purple — near-zero
      { color: '#d96570', x: w/2, y: h/2, r: w * 0.12, speedX: 0.6, speedY: -0.4 }, // Rose — near-zero
      { color: '#00f0ff', x: 0, y: h, r: w * 0.08, speedX: 0.3, speedY: -0.3 }  // Cyan — near-zero
    ];

    const animate = () => {
      // Clear with very low opacity to create motion trails
      ctx.globalCompositeOperation = 'source-over';
      ctx.fillStyle = '#000005'; // Deep void
      ctx.fillRect(0, 0, w, h);

      ctx.globalCompositeOperation = 'screen';
      
      blobs.forEach((blob) => {
        // Move blobs
        blob.x += Math.sin(time * 0.01 * blob.speedX) * 2;
        blob.y += Math.cos(time * 0.01 * blob.speedY) * 2;

        // Wrap around bounds (soft bounds)
        if (blob.x > w + blob.r) blob.x = -blob.r;
        if (blob.x < -blob.r) blob.x = w + blob.r;
        if (blob.y > h + blob.r) blob.y = -blob.r;
        if (blob.y < -blob.r) blob.y = h + blob.r;

        // Draw radial gradient
        const gradient = ctx.createRadialGradient(blob.x, blob.y, 0, blob.x, blob.y, blob.r);
        gradient.addColorStop(0, blob.color);
        gradient.addColorStop(1, 'rgba(0,0,0,0)');

        ctx.fillStyle = gradient;
        ctx.beginPath();
        ctx.arc(blob.x, blob.y, blob.r, 0, Math.PI * 2);
        ctx.fill();
      });

      time++;
      requestAnimationFrame(animate);
    };

    animate();

    return () => window.removeEventListener('resize', resize);
  }, []);

  return (
      <canvas 
        ref={canvasRef} 
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          width: '100vw',
          height: '100vh',
          zIndex: -2,
          filter: 'blur(120px)', // Extra blur for near-invisible ambient
          opacity: 0.15
        }}
      />
  );
}
