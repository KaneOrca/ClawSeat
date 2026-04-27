import type { MutableRefObject } from 'react';
import type { RectObstacle } from '../PhysicsContext';
import { clearCharRectCache } from './char-metrics';

export function getIntersectionObserver(
  ioRef: MutableRefObject<IntersectionObserver | null>,
  visibleRef: MutableRefObject<Set<string>>,
): IntersectionObserver {
  if (!ioRef.current) {
    ioRef.current = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          const id = (entry.target as HTMLElement).dataset.obstacleId;
          if (!id) continue;
          if (entry.isIntersecting) {
            visibleRef.current.add(id);
          } else {
            visibleRef.current.delete(id);
          }
        }
      },
      { rootMargin: '50px' },
    );
  }
  return ioRef.current;
}

export function trackElementObstacle(
  id: string,
  element: HTMLElement,
  trackedRef: MutableRefObject<Map<string, HTMLElement>>,
  visibleRef: MutableRefObject<Set<string>>,
  ioRef: MutableRefObject<IntersectionObserver | null>,
): void {
  element.dataset.obstacleId = id;
  trackedRef.current.set(id, element);
  visibleRef.current.add(id);
  getIntersectionObserver(ioRef, visibleRef).observe(element);
}

export function untrackElementObstacle(
  id: string,
  trackedRef: MutableRefObject<Map<string, HTMLElement>>,
  visibleRef: MutableRefObject<Set<string>>,
  prevRectsRef: MutableRefObject<Map<string, RectObstacle>>,
  prevContentRef: MutableRefObject<Map<string, string>>,
  ioRef: MutableRefObject<IntersectionObserver | null>,
): void {
  const el = trackedRef.current.get(id);
  if (el) getIntersectionObserver(ioRef, visibleRef).unobserve(el);
  trackedRef.current.delete(id);
  visibleRef.current.delete(id);
  prevRectsRef.current.delete(id);
  prevContentRef.current.delete(id);
  clearCharRectCache(id);
}
