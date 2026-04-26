import { useEffect, useRef, useId } from 'react';
import { usePhysicsRegistry } from '../context/PhysicsContext';
import { useArena } from '../context/ArenaContext';

/**
 * Hook to register a component's BBox as a physics obstacle.
 * Registers the DOM element with the central tracker in PhysicsContext.
 * No per-hook RAF loop — the central tracker polls all elements in one batch.
 */
export function useObstacle(active: boolean = true) {
  const { isZenMode } = useArena();
  return useObstacleCore(active, isZenMode);
}

/**
 * Context-free variant for perf-critical memo'd components.
 */
export function useObstacleDetached(active: boolean, isZenMode: boolean) {
  return useObstacleCore(active, isZenMode);
}

function useObstacleCore(active: boolean, isZenMode: boolean) {
  const id = useId();
  const ref = useRef<HTMLElement>(null);
  const { trackObstacle, untrackObstacle } = usePhysicsRegistry();

  useEffect(() => {
    if (!active || isZenMode || !ref.current) {
      untrackObstacle(id);
      return;
    }

    trackObstacle(id, ref.current);

    return () => {
      untrackObstacle(id);
    };
  }, [id, active, isZenMode, trackObstacle, untrackObstacle]);

  return ref;
}
