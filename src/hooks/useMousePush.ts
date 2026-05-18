import { useEffect, useRef, type RefObject } from 'react';

interface UseMousePushOptions {
  enabled?: boolean;
  pushRadius?: number;
  maxForce?: number;
  lerpFactor?: number;
}

export function useMousePush(options: UseMousePushOptions = {}): RefObject<HTMLElement | null> {
  const {
    enabled = true,
    pushRadius = 90,
    maxForce = 12,
    lerpFactor = 0.2,
  } = options;
  const ref = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!enabled) return;

    const element = ref.current;
    if (!element) return;

    let rafId = 0;
    let currentDx = 0;
    let currentDy = 0;
    const mouse = { x: window.innerWidth / 2, y: window.innerHeight / 2 };
    const originalTransform = element.style.transform;
    const originalWillChange = element.style.willChange;

    element.style.willChange = 'transform';

    const handleMouseMove = (event: MouseEvent) => {
      mouse.x = event.clientX;
      mouse.y = event.clientY;
    };

    const tick = () => {
      const rect = element.getBoundingClientRect();
      const centerX = rect.left + rect.width / 2;
      const centerY = rect.top + rect.height / 2;
      const dx = centerX - mouse.x;
      const dy = centerY - mouse.y;
      const dist = Math.hypot(dx, dy);

      let targetDx = 0;
      let targetDy = 0;
      if (dist < pushRadius) {
        const force = Math.pow(1 - dist / pushRadius, 2) * maxForce;
        const angle = Math.atan2(dy, dx);
        targetDx = Math.cos(angle) * force;
        targetDy = Math.sin(angle) * force;
      }

      currentDx += (targetDx - currentDx) * lerpFactor;
      currentDy += (targetDy - currentDy) * lerpFactor;
      element.style.transform = `translate(${currentDx}px, ${currentDy}px)`;
      rafId = window.requestAnimationFrame(tick);
    };

    window.addEventListener('mousemove', handleMouseMove, { passive: true });
    rafId = window.requestAnimationFrame(tick);

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.cancelAnimationFrame(rafId);
      element.style.transform = originalTransform;
      element.style.willChange = originalWillChange;
    };
  }, [enabled, lerpFactor, maxForce, pushRadius]);

  return ref;
}
