import React, { createContext, useContext, useState, useCallback, useMemo, useEffect, useRef } from 'react';
import type { VariantType } from './ArenaContext';
import { getCharRects, type CharRect } from './physics/char-metrics';
import { renderMask, type MaskBuffer } from './physics/mask-renderer';
import { trackElementObstacle, untrackElementObstacle } from './physics/obstacle-tracker';
import { tokens } from '../design/tokens';
import { useFunctionalTextHover } from '../hooks/useFunctionalTextHover';

export type { CharRect } from './physics/char-metrics';

export interface RectObstacle {
  id: string;
  x: number;
  y: number;
  w: number;
  h: number;
  isClimbing?: boolean;
  /** Per-character sub-rects from measureText decomposition. */
  charRects?: CharRect[];
}

export interface Soloist {
  id: string;
  text: string;
  lineIndex: number;
  color?: string;
  opacity?: number;
}

export interface ViewportState {
  width: number;
  height: number;
  scrollX: number;
  scrollY: number;
  dpr: number;
  /** Scroll velocity in px/frame (predicted from last two scroll positions). */
  scrollVelX: number;
  scrollVelY: number;
}

export interface EnvironmentSettings {
  ambientColor?: string;
  waveAmplitude?: number;
  waveFrequency?: number;
  opacity?: number;
  /** When true, BitmaskPhysic draws obstacle alignment lines. */
  debugAlignment?: boolean;
  effects?: PhysicsEffects;
}

export interface PhysicsEffects {
  transitionProgress?: number;
  transitionFrom?: VariantType | null;
  alignmentPulse?: {
    active: boolean;
    startTime: number;
    duration: number;
  };
  recoilVelocity?: {
    x: number;
    y: number;
  };
  catharsis?: {
    active: boolean;
    stepId: string;
    agentNickname: string;
    timestamp: number;
  };
}

interface PhysicsContextType {
  obstacles: RectObstacle[];
  obstaclesRef: React.RefObject<RectObstacle[]>;
  maskRef: React.RefObject<MaskBuffer | null>;
  /** Mutable viewport state — scroll offset, dimensions, DPR. Updated every frame. */
  viewportRef: React.RefObject<ViewportState>;
  trackObstacle: (id: string, element: HTMLElement) => void;
  untrackObstacle: (id: string) => void;
  updateMouseObstacle: (rect: DOMRect | null) => void;

  soloists: Soloist[];
  registerSoloist: (soloist: Soloist) => void;
  unregisterSoloist: (id: string) => void;

  environment: EnvironmentSettings;
  setEnvironment: (settings: Partial<EnvironmentSettings>) => void;
}

interface FlashLogEntry {
  time: number;
  waveAmplitude: number;
  opacity?: number;
  source: string;
  delta?: number;
  stack: string;
}

const PhysicsContext = createContext<PhysicsContextType | undefined>(undefined);

const POLL_EVERY_N_FRAMES = 1;
const CHANGE_THRESHOLD = 1; // px
const SNAPSHOT_DEBOUNCE_MS = 50;
const RECOIL_DECAY = 0.92;

export const PhysicsProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  useFunctionalTextHover();

  // ── Obstacle tracking ─────────────────────────────────────────────

  const trackedRef = useRef<Map<string, HTMLElement>>(new Map());
  const visibleRef = useRef<Set<string>>(new Set());
  const viewportRef = useRef<ViewportState>({
    width: typeof window !== 'undefined' ? window.innerWidth : 0,
    height: typeof window !== 'undefined' ? window.innerHeight : 0,
    scrollX: 0,
    scrollY: 0,
    dpr: typeof window !== 'undefined' ? (window.devicePixelRatio || 1) : 1,
    scrollVelX: 0,
    scrollVelY: 0,
  });
  const prevScrollRef = useRef({
    x: typeof window !== 'undefined' ? window.scrollX : 0,
    y: typeof window !== 'undefined' ? window.scrollY : 0,
  });
  const prevRectsRef = useRef<Map<string, RectObstacle>>(new Map());
  const prevContentRef = useRef<Map<string, string>>(new Map());
  const obstaclesLiveRef = useRef<RectObstacle[]>([]);
  const mouseObstacleRef = useRef<RectObstacle | null>(null);
  const maskBufRef = useRef<MaskBuffer | null>(null);
  const [obstaclesSnapshot, setObstaclesSnapshot] = useState<RectObstacle[]>([]);
  const frameRef = useRef(0);
  const firstMaskDoneRef = useRef(false);
  const snapshotTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const ioRef = useRef<IntersectionObserver | null>(null);

  const trackObstacle = useCallback((id: string, element: HTMLElement) => {
    trackElementObstacle(id, element, trackedRef, visibleRef, ioRef);
  }, []);

  const untrackObstacle = useCallback((id: string) => {
    untrackElementObstacle(id, trackedRef, visibleRef, prevRectsRef, prevContentRef, ioRef);
  }, []);

  // Cleanup IO on unmount
  useEffect(() => {
    return () => {
      ioRef.current?.disconnect();
    };
  }, []);

  // Debounced snapshot push — coalesces rapid changes into one React update
  const pushSnapshot = useCallback((next: RectObstacle[]) => {
    if (snapshotTimerRef.current) clearTimeout(snapshotTimerRef.current);
    snapshotTimerRef.current = setTimeout(() => {
      setObstaclesSnapshot(next);
      snapshotTimerRef.current = null;
    }, SNAPSHOT_DEBOUNCE_MS);
  }, []);

  // Immediate scroll sync — captures scroll position between RAF frames
  useEffect(() => {
    const onScroll = () => {
      const prev = viewportRef.current;
      viewportRef.current = {
        ...prev,
        scrollX: window.scrollX,
        scrollY: window.scrollY,
      };
      // Force mask re-render on next poll — highest priority during scroll
      const buf = maskBufRef.current;
      if (buf) buf.dirty = true;
    };
    // passive: false ensures we run synchronously with the scroll event
    window.addEventListener('scroll', onScroll, { passive: false });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  // Single RAF loop
  useEffect(() => {
    let frame: number;
    let alive = true;

    const poll = () => {
      if (!alive) return;
      frameRef.current++;

      // Update viewport state + compute scroll velocity
      const sx = window.scrollX;
      const sy = window.scrollY;
      const ps = prevScrollRef.current;
      viewportRef.current = {
        width: window.innerWidth,
        height: window.innerHeight,
        scrollX: sx,
        scrollY: sy,
        dpr: window.devicePixelRatio || 1,
        scrollVelX: sx - ps.x,
        scrollVelY: sy - ps.y,
      };
      prevScrollRef.current = { x: sx, y: sy };

      setEnvironmentRaw(prev => {
        const recoilX = prev.effects?.recoilVelocity?.x ?? 0;
        const recoilY = prev.effects?.recoilVelocity?.y ?? 0;
        if (Math.abs(recoilX) < 0.01 && Math.abs(recoilY) < 0.01) {
          if (recoilX === 0 && recoilY === 0) return prev;
          return {
            ...prev,
            effects: {
              ...prev.effects,
              recoilVelocity: { x: 0, y: 0 },
            },
          };
        }
        return {
          ...prev,
          effects: {
            ...prev.effects,
            recoilVelocity: { x: recoilX * RECOIL_DECAY, y: recoilY * RECOIL_DECAY },
          },
        };
      });

      if (frameRef.current % POLL_EVERY_N_FRAMES === 0) {
        const tracked = trackedRef.current;
        const visible = visibleRef.current;
        const prevRects = prevRectsRef.current;

        // Handle zero tracked: clear stale data
        if (tracked.size === 0) {
          if (obstaclesLiveRef.current.length > 0) {
            obstaclesLiveRef.current = [];
            prevRectsRef.current = new Map();
            prevContentRef.current = new Map();
            pushSnapshot([]);
          }
          // Clear mask buffer to prevent "pixel ghosts"
          const buf = maskBufRef.current;
          if (buf) {
            buf.ctx.clearRect(0, 0, buf.width, buf.height);
            buf.dirty = true;
          }
          firstMaskDoneRef.current = false;
          frame = requestAnimationFrame(poll);
          return;
        }

        let changed = prevRects.size !== tracked.size + (mouseObstacleRef.current ? 1 : 0);
        let contentChanged = false;
        const next: RectObstacle[] = [];
        const prevContent = prevContentRef.current;
        const vp = viewportRef.current;
        // When scrolling, bypass IO visibility — measure ALL tracked elements
        // so newly-entered elements get positions immediately
        const forceAllMeasure = Math.abs(vp.scrollVelX) > 0.01 || Math.abs(vp.scrollVelY) > 0.01;

        tracked.forEach((el, id) => {
          try {
            if (!el.isConnected) return;

            // Detect text content changes for mask re-render
            const text = (el.textContent ?? '').trim();
            if (prevContent.get(id) !== text) {
              contentChanged = true;
              prevContent.set(id, text);
            }

            // Skip getBoundingClientRect for offscreen elements (only when static)
            if (!forceAllMeasure && !visible.has(id)) {
              const prev = prevRects.get(id);
              if (prev) next.push(prev);
              return;
            }

            const r = el.getBoundingClientRect();
            if (r.width < 1 || r.height < 1) return;

            const charRects = getCharRects(id, el, r);
            const obs: RectObstacle = {
              id,
              x: r.left,
              y: r.top,
              w: r.width,
              h: r.height,
              isClimbing: el.dataset.physicsClimbing === 'true',
              charRects,
            };
            next.push(obs);

            if (!changed) {
              const p = prevRects.get(id);
              if (!p ||
                Math.abs(r.left - p.x) > CHANGE_THRESHOLD ||
                Math.abs(r.top - p.y) > CHANGE_THRESHOLD ||
                Math.abs(r.width - p.w) > CHANGE_THRESHOLD ||
                Math.abs(r.height - p.h) > CHANGE_THRESHOLD) {
                changed = true;
              }
            }
          } catch {
            // Swallow errors from detached/invalid elements
          }
        });

        const mouseObstacle = mouseObstacleRef.current;
        if (mouseObstacle) next.push(mouseObstacle);
        if (mouseObstacle && !changed) {
          const prev = prevRects.get('system:mouse');
          if (
            !prev ||
            Math.abs(mouseObstacle.x - prev.x) > CHANGE_THRESHOLD ||
            Math.abs(mouseObstacle.y - prev.y) > CHANGE_THRESHOLD ||
            Math.abs(mouseObstacle.w - prev.w) > CHANGE_THRESHOLD ||
            Math.abs(mouseObstacle.h - prev.h) > CHANGE_THRESHOLD
          ) {
            changed = true;
          }
        }

        // Always update the mutable ref (canvas reads this directly)
        obstaclesLiveRef.current = next;

        // Render pixel mask — when positions, content, or scroll velocity changed
        const isScrolling = forceAllMeasure;
        const needsFirstRender = !firstMaskDoneRef.current && next.length > 0;
        if (changed || contentChanged || isScrolling || needsFirstRender) {
          renderMask(tracked, next, maskBufRef);
          firstMaskDoneRef.current = true;
        }

        // Debounced React state push
        if (changed) {
          const newPrev = new Map<string, RectObstacle>();
          for (const obs of next) newPrev.set(obs.id, obs);
          prevRectsRef.current = newPrev;
          pushSnapshot(next);
        }
      }

      frame = requestAnimationFrame(poll);
    };

    frame = requestAnimationFrame(poll);
    return () => {
      alive = false;
      cancelAnimationFrame(frame);
      if (snapshotTimerRef.current) {
        clearTimeout(snapshotTimerRef.current);
        snapshotTimerRef.current = null;
      }
    };
  }, []);

  // ── Soloists ──────────────────────────────────────────────────────

  const [soloistsMap, setSoloistsMap] = useState<Map<string, Soloist>>(new Map());

  /**
   * @deprecated Replaced by pretext-flow embed+data payload pattern. Will be removed after view migration.
   *
   * Active consumers:
   * - src/hooks/useHomeInit.ts
   * - src/components/PretextButton.tsx
   * - src/components/text-physics/useDecryptionCatharsis.ts
   * - src/views/Hall/v2/HallView.tsx
   * - src/views/Auth/v2/AuthView.tsx
   * - src/views/Auth/v3/AuthView.tsx
   * - src/views/ChallengeDetail/v3/ChallengeDetailV3.tsx
   * - src/views/ChallengeDetail/v3/ChallengeLayer.tsx
   * - src/views/Community/v2/CommunityView.tsx
   * - src/views/Community/v3/CommunityView.tsx
   * - src/views/Home/v2/HomeView.tsx
   * - src/views/Watch/v3/WatchViewV3.tsx
   */
  const registerSoloist = useCallback((soloist: Soloist) => {
    setSoloistsMap(prev => {
      const next = new Map(prev);
      next.set(soloist.id, soloist);
      return next;
    });
  }, []);

  /**
   * @deprecated Replaced by pretext-flow embed+data payload pattern. Will be removed after view migration.
   *
   * Active consumers:
   * - src/hooks/useHomeInit.ts
   * - src/components/PretextButton.tsx
   * - src/components/text-physics/useDecryptionCatharsis.ts
   * - src/views/Hall/v2/HallView.tsx
   * - src/views/Auth/v2/AuthView.tsx
   * - src/views/Auth/v3/AuthView.tsx
   * - src/views/ChallengeDetail/v3/ChallengeDetailV3.tsx
   * - src/views/ChallengeDetail/v3/ChallengeLayer.tsx
   * - src/views/Community/v2/CommunityView.tsx
   * - src/views/Community/v3/CommunityView.tsx
   * - src/views/Home/v2/HomeView.tsx
   * - src/views/Watch/v3/WatchViewV3.tsx
   */
  const unregisterSoloist = useCallback((id: string) => {
    setSoloistsMap(prev => {
      const next = new Map(prev);
      next.delete(id);
      return next;
    });
  }, []);

  const soloists = useMemo(() => Array.from(soloistsMap.values()), [soloistsMap]);

  // ── Environment ───────────────────────────────────────────────────

  const [environment, setEnvironmentRaw] = useState<EnvironmentSettings>({
    opacity: 0.15,
    waveAmplitude: 60,
    waveFrequency: 0.03,
    effects: {
      transitionProgress: 0,
      transitionFrom: null,
      recoilVelocity: { x: 0, y: 0 },
    }
  });

  const mergeEnvironment = useCallback((patch: Partial<EnvironmentSettings>) => {
    setEnvironmentRaw(prev => {
      const env = {
        ...prev,
        ...patch,
        effects: patch.effects ? { ...prev.effects, ...patch.effects } : prev.effects,
      };

      if (import.meta.env.DEV) {
        const flashLog = (window as any).__arenaFlashLog__ || [];
        (window as any).__arenaFlashLog__ = flashLog;
        flashLog.push({
          time: Date.now(),
          waveAmplitude: env.waveAmplitude,
          opacity: env.opacity,
          source: 'PhysicsContext',
          stack: new Error().stack?.split('\n').slice(2, 4).join(' -> ') ?? '',
        });
      }

      return env;
    });
  }, []);

  const updateMouseObstacle = useCallback((rect: DOMRect | null) => { mouseObstacleRef.current = rect ? { id: 'system:mouse', x: rect.x, y: rect.y, w: rect.width, h: rect.height, isClimbing: false, charRects: [] } : null; if (maskBufRef.current) maskBufRef.current.dirty = true; }, []);

  useEffect(() => {
    const onMove = (e: MouseEvent) => { const r = 60 + ((environment.waveAmplitude ?? 60) / 60) * 40; updateMouseObstacle(new DOMRect(e.clientX - r, e.clientY - r, r * 2, r * 2)); };
    const onLeave = () => updateMouseObstacle(null);
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseleave', onLeave);
    return () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseleave', onLeave); updateMouseObstacle(null); };
  }, [environment.waveAmplitude, updateMouseObstacle]);

  // ── Provider ──────────────────────────────────────────────────────

  const value = useMemo(() => ({
    obstacles: obstaclesSnapshot,
    obstaclesRef: obstaclesLiveRef,
    maskRef: maskBufRef,
    viewportRef,
    trackObstacle,
    untrackObstacle,
    updateMouseObstacle,
    soloists,
    registerSoloist,
    unregisterSoloist,
    environment,
    setEnvironment: mergeEnvironment,
  }), [
    obstaclesSnapshot, trackObstacle, untrackObstacle, updateMouseObstacle,
    soloists, registerSoloist, unregisterSoloist,
    environment, mergeEnvironment,
  ]);

  const flashHudRef = useRef<HTMLDivElement | null>(null);
  const flashHudFrameRef = useRef<number | null>(null);

  useEffect(() => {
    if (typeof window === 'undefined' || typeof document === 'undefined') return;
    if (!import.meta.env.DEV) return;
    if (!(window as any).__ARENA_DEBUG_FLASH__) return;

    const container = document.createElement('div');
    container.style.position = 'fixed';
    container.style.top = '0';
    container.style.left = '0';
    container.style.padding = '8px 12px';
    container.style.zIndex = '9999';
    container.style.background = 'rgba(0,0,0,0.75)';
    container.style.borderRadius = '4px';
    container.style.color = '#fff';
    container.style.fontFamily = tokens.fonts.mono;
    container.style.fontSize = '10px';
    container.style.lineHeight = '1.3';
    container.style.pointerEvents = 'none';
    container.style.whiteSpace = 'pre';
    flashHudRef.current = container;
    container.setAttribute('data-flash-hud', 'arena');

    const formatDelta = (value: number) => `${value >= 0 ? '+' : ''}${Math.round(value)}`;

    const renderHud = () => {
      const now = Date.now();
      const log = ((window as any).__arenaFlashLog__ as FlashLogEntry[] | undefined) ?? [];
      const current = log[log.length - 1];
      const previous = log[log.length - 2];
      const interval = previous ? current.time - previous.time : 0;

      if (!current) {
        container.textContent = 'FLASH HUD\\nLast: none\\nPrev: none\\nSource: none';
      } else {
        const prevText = previous
          ? `Prev: ${interval}ms ago  amp:${previous.waveAmplitude}  (${formatDelta(previous.delta ?? 0)})`
          : 'Prev: none';
        const lastText = `Last: ${now - current.time}ms ago  amp:${current.waveAmplitude}  (${formatDelta(current.delta ?? 0)})`;
        container.textContent = `FLASH HUD\\n${lastText}\\n${prevText}\\nSource: ${current.source}`;
      }

      flashHudFrameRef.current = requestAnimationFrame(renderHud);
    };

    document.body.appendChild(container);
    flashHudFrameRef.current = requestAnimationFrame(renderHud);

    return () => {
      if (flashHudFrameRef.current !== null) {
        cancelAnimationFrame(flashHudFrameRef.current);
        flashHudFrameRef.current = null;
      }
      if (flashHudRef.current) {
        flashHudRef.current.remove();
      }
      flashHudRef.current = null;
    };
  }, []);

  return (
    <PhysicsContext.Provider value={value}>
      {children}
    </PhysicsContext.Provider>
  );
};

export const usePhysicsRegistry = () => {
  const context = useContext(PhysicsContext);
  if (!context) throw new Error('usePhysicsRegistry must be used within PhysicsProvider');
  return context;
};
