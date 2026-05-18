import { useEffect, useMemo, useState } from 'react';

interface ProgressiveRevealInput {
  content: string;
  decryptKeyMap: Record<string, string>;
  activeStepId: string;
  lineIndex?: number;
}

interface ProgressiveRevealResult {
  revealedSlice: string;
  shimmerActive: boolean;
}

const FORM_REVEAL_RATE = 42;

export function useProgressiveLiteraryReveal({
  content,
  activeStepId,
}: ProgressiveRevealInput): ProgressiveRevealResult {
  const [revealedChars, setRevealedChars] = useState(0);
  const [shimmerUntil, setShimmerUntil] = useState(0);

  useEffect(() => {
    setRevealedChars(0);
    setShimmerUntil(performance.now() + 800);

    let raf = 0;
    let last = performance.now();
    const tick = (now: number) => {
      const delta = Math.max(0, now - last);
      last = now;
      setRevealedChars(prev => {
        const predictedScrollBoost = 1.5;
        const next = prev + (delta / 1000) * FORM_REVEAL_RATE * predictedScrollBoost;
        return Math.min(content.length, next);
      });
      raf = requestAnimationFrame(tick);
    };

    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [content, activeStepId]);

  const revealedSlice = useMemo(() => {
    const visible = Math.max(1, Math.floor(revealedChars));
    return content.slice(0, visible);
  }, [content, revealedChars]);

  return {
    revealedSlice,
    shimmerActive: performance.now() < shimmerUntil || revealedChars < content.length,
  };
}
