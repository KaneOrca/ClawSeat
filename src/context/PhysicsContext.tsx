import React, { createContext, useContext, useState, useCallback, useMemo, useEffect, useRef } from 'react';
import type { VariantType } from './ArenaContext';

export interface CharRect {
  char: string;
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface RectObstacle {
  id: string;
  x: number;
  y: number;
  w: number;
  h: number;
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
  transitionProgress: number;
  transitionFrom: VariantType | null;
}

interface PhysicsContextType {
  obstacles: RectObstacle[];
  obstaclesRef: React.RefObject<RectObstacle[]>;
  maskRef: React.RefObject<{ canvas: HTMLCanvasElement; ctx: CanvasRenderingContext2D; width: number; height: number; dirty: boolean } | null>;
  /** Mutable viewport state — scroll offset, dimensions, DPR. Updated every frame. */
  viewportRef: React.RefObject<ViewportState>;
  trackObstacle: (id: string, element: HTMLElement) => void;
  untrackObstacle: (id: string) => void;

  soloists: Soloist[];
  registerSoloist: (soloist: Soloist) => void;
  unregisterSoloist: (id: string) => void;

  environment: EnvironmentSettings;
  setEnvironment: (settings: Partial<EnvironmentSettings>) => void;
}

const PhysicsContext = createContext<PhysicsContextType | undefined>(undefined);

const POLL_EVERY_N_FRAMES = 1;
const CHANGE_THRESHOLD = 1; // px
const SNAPSHOT_DEBOUNCE_MS = 50;

// ── CharRect decomposition with caching ─────────────────────────────

interface CharRectCache {
  text: string;
  font: string;
  relRects: { char: string; dx: number; dy: number; w: number; h: number }[];
}

const _charRectCache = new Map<string, CharRectCache>();
let _measureCanvas: HTMLCanvasElement | null = null;

/**
 * Decompose a text element into per-character sub-rects.
 * Tries Range API first (handles multi-line/wrapping accurately),
 * falls back to canvas measureText for single-line.
 * Caches relative positions keyed by obstacle ID — only recomputes
 * when textContent or font changes. Static elements cost zero.
 */
function getCharRects(id: string, el: HTMLElement, bbox: DOMRect): CharRect[] | undefined {
  const text = el.textContent;
  if (!text || text.length < 2 || text.length > 100) return undefined;

  const style = getComputedStyle(el);
  const font = `${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;

  // Cache hit — reuse relative rects, just offset by current bbox
  const cached = _charRectCache.get(id);
  if (cached && cached.text === text && cached.font === font) {
    return cached.relRects.map(r => ({
      char: r.char,
      x: bbox.left + r.dx,
      y: bbox.top + r.dy,
      w: r.w,
      h: r.h,
    }));
  }

  // Cache miss — compute relative rects
  const relRects: CharRectCache['relRects'] = [];
  let measured = false;

  // Strategy 1: Range API (handles multi-line, wrapping, mixed content)
  const textNode = findFirstTextNode(el);
  if (textNode && textNode.textContent === text) {
    try {
      const range = document.createRange();
      for (let i = 0; i < text.length; i++) {
        if (text[i] === ' ' || text[i] === '\n' || text[i] === '\t') continue;
        range.setStart(textNode, i);
        range.setEnd(textNode, i + 1);
        const cr = range.getBoundingClientRect();
        if (cr.width < 0.5) continue;
        relRects.push({
          char: text[i],
          dx: cr.left - bbox.left,
          dy: cr.top - bbox.top,
          w: cr.width,
          h: cr.height,
        });
      }
      range.detach();
      measured = relRects.length > 0;
    } catch {
      // Range API failed — fall through to measureText
    }
  }

  // Strategy 2: Canvas measureText fallback (single-line only)
  if (!measured) {
    if (!_measureCanvas) _measureCanvas = document.createElement('canvas');
    const ctx = _measureCanvas.getContext('2d');
    if (ctx) {
      ctx.font = font;
      let cursorX = 0;
      for (let i = 0; i < text.length; i++) {
        const ch = text[i];
        const w = ctx.measureText(ch).width;
        if (ch !== ' ' && ch !== '\n' && ch !== '\t') {
          relRects.push({ char: ch, dx: cursorX, dy: 0, w, h: bbox.height });
        }
        cursorX += w;
      }
    }
  }

  if (relRects.length === 0) return undefined;

  // Store cache
  _charRectCache.set(id, { text, font, relRects });

  return relRects.map(r => ({
    char: r.char,
    x: bbox.left + r.dx,
    y: bbox.top + r.dy,
    w: r.w,
    h: r.h,
  }));
}

function findFirstTextNode(el: Node): Text | null {
  if (el.nodeType === Node.TEXT_NODE) return el as Text;
  for (let i = 0; i < el.childNodes.length; i++) {
    const found = findFirstTextNode(el.childNodes[i]);
    if (found) return found;
  }
  return null;
}

/**
 * Render all visible tracked text elements onto an offscreen canvas as white-on-black.
 * The alpha channel of this mask is sampled by BitmaskPhysic to determine
 * pixel-level occlusion — glyph holes (o, d, e counters) remain transparent.
 */
function renderMask(
  tracked: Map<string, HTMLElement>,
  obstacles: RectObstacle[],
  bufRef: React.MutableRefObject<{ canvas: HTMLCanvasElement; ctx: CanvasRenderingContext2D; width: number; height: number; dirty: boolean } | null>,
) {
  const w = window.innerWidth;
  const h = window.innerHeight;

  let buf = bufRef.current;
  if (!buf || buf.width !== w || buf.height !== h) {
    const canvas = buf?.canvas ?? document.createElement('canvas');
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    if (!ctx) return;
    buf = { canvas, ctx, width: w, height: h, dirty: false };
    bufRef.current = buf;
  }

  const { ctx } = buf;
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = 'white';
  ctx.textBaseline = 'top';

  // Zero-offset rendering — mask coordinates match obstacle coordinates 1:1.
  // Prediction offset is applied on the sampling side (BitmaskPhysic).
  for (const obs of obstacles) {
    // Synchronous AABB visibility: skip obstacles entirely outside viewport
    if (obs.y + obs.h < 0 || obs.y > h || obs.x + obs.w < 0 || obs.x > w) continue;

    const el = tracked.get(obs.id);
    if (!el) continue;

    try {
      const style = getComputedStyle(el);
      const font = `${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
      ctx.font = font;

      if (obs.charRects && obs.charRects.length > 0) {
        for (const cr of obs.charRects) {
          ctx.fillText(cr.char, cr.x, cr.y);
        }
      } else {
        const fontSize = parseFloat(style.fontSize);
        const yOffset = (obs.h - fontSize) * 0.35;
        ctx.fillText(el.textContent ?? '', obs.x, obs.y + yOffset);
      }
    } catch {
      // Skip
    }
  }

  buf.dirty = true;
}

export const PhysicsProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
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
  const maskBufRef = useRef<{ canvas: HTMLCanvasElement; ctx: CanvasRenderingContext2D; width: number; height: number; dirty: boolean } | null>(null);
  const [obstaclesSnapshot, setObstaclesSnapshot] = useState<RectObstacle[]>([]);
  const frameRef = useRef(0);
  const firstMaskDoneRef = useRef(false);
  const snapshotTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const ioRef = useRef<IntersectionObserver | null>(null);

  // Lazy-init IntersectionObserver
  const getIO = useCallback(() => {
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
        { rootMargin: '50px' }
      );
    }
    return ioRef.current;
  }, []);

  const trackObstacle = useCallback((id: string, element: HTMLElement) => {
    element.dataset.obstacleId = id;
    trackedRef.current.set(id, element);
    visibleRef.current.add(id); // Assume visible until IO reports otherwise
    getIO().observe(element);
  }, [getIO]);

  const untrackObstacle = useCallback((id: string) => {
    const el = trackedRef.current.get(id);
    if (el) getIO().unobserve(el);
    trackedRef.current.delete(id);
    visibleRef.current.delete(id);
    prevRectsRef.current.delete(id);
    prevContentRef.current.delete(id);
    _charRectCache.delete(id);
  }, [getIO]);

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

        let changed = prevRects.size !== tracked.size;
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
            const obs: RectObstacle = { id, x: r.left, y: r.top, w: r.width, h: r.height, charRects };
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

  const registerSoloist = useCallback((soloist: Soloist) => {
    setSoloistsMap(prev => {
      const next = new Map(prev);
      next.set(soloist.id, soloist);
      return next;
    });
  }, []);

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
    }
  });

  const mergeEnvironment = useCallback((patch: Partial<EnvironmentSettings>) => {
    setEnvironmentRaw(prev => ({
      ...prev,
      ...patch,
      effects: patch.effects ? { ...prev.effects, ...patch.effects } : prev.effects,
    }));
  }, []);

  // ── Provider ──────────────────────────────────────────────────────

  const value = useMemo(() => ({
    obstacles: obstaclesSnapshot,
    obstaclesRef: obstaclesLiveRef,
    maskRef: maskBufRef,
    viewportRef,
    trackObstacle,
    untrackObstacle,
    soloists,
    registerSoloist,
    unregisterSoloist,
    environment,
    setEnvironment: mergeEnvironment,
  }), [
    obstaclesSnapshot, trackObstacle, untrackObstacle,
    soloists, registerSoloist, unregisterSoloist,
    environment, mergeEnvironment,
  ]);

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
