import React, { useCallback, useRef, useEffect } from 'react';
import { usePhysicsRegistry, type RectObstacle } from '../../context/PhysicsContext';
import { usePretextCanvas } from '../../hooks/usePretextCanvas';

interface BitmaskPhysicProps {
  opacity?: number;
}

// ── Character palette ───────────────────────────────────────────────

// Neural data swarm character sets
const HEX = '0123456789ABCDEF';
const SYNAPTIC = ['∞', 'Σ', 'Δ', 'Ω', 'λ', 'π', 'μ', '∂', '∇', '≡', '⊕', '⊗'] as const;
const DATA = ['0', '1', ':', '.', '·', '∘'] as const;
const BASE_CELL_W = 10;
const BASE_CELL_H = 14;
const FONT = '11px monospace';

// Aggressive LOD: scale cell size by DPI and viewport width
function getCellSize(): { w: number; h: number } {
  if (typeof window === 'undefined') return { w: BASE_CELL_W, h: BASE_CELL_H };
  const dpr = window.devicePixelRatio || 1;
  const vw = window.innerWidth;
  // Ultra-wide / 4K: largest cells to stay under ~6000 total
  if (vw > 2500 || dpr > 2) return { w: 24, h: 32 };
  if (dpr > 1) return { w: 14, h: 19 };
  return { w: BASE_CELL_W, h: BASE_CELL_H };
}

// ── Sine LUT: pre-computed table eliminates per-cell Math.sin calls ──
const SINE_LUT_SIZE = 4096;
const SINE_LUT = new Float32Array(SINE_LUT_SIZE);
for (let i = 0; i < SINE_LUT_SIZE; i++) {
  SINE_LUT[i] = Math.sin((i / SINE_LUT_SIZE) * Math.PI * 2);
}

/** Fast sine approximation via LUT. Input in radians. */
function fsin(x: number): number {
  const idx = ((x % (Math.PI * 2)) + Math.PI * 2) * (SINE_LUT_SIZE / (Math.PI * 2));
  return SINE_LUT[((idx | 0) % SINE_LUT_SIZE + SINE_LUT_SIZE) % SINE_LUT_SIZE];
}

// fcos available if needed: fsin(x + Math.PI * 0.5)
const FEATHER_PX = 36;
const OCCLUDED_FLOOR = 0.12;

/**
 * Cheap pseudo-noise based on cell coordinates.
 * Returns a deterministic value in [-1, 1] (clamped) that varies
 * organically across the grid, breaking up straight AABB edges.
 */
function cellNoise(cx: number, cy: number): number {
  const raw = Math.sin(cx * 0.13 + cy * 0.07) * Math.cos(cx * 0.07 - cy * 0.11)
            + Math.sin(cx * 0.23 - cy * 0.19) * 0.5;
  return Math.max(-1, Math.min(1, raw));
}

/**
 * Distance from point to nearest edge of a rect. 0 = inside.
 */
function rectDist(cx: number, cy: number, rx: number, ry: number, rw: number, rh: number): number {
  const dx = Math.max(rx - cx, 0, cx - (rx + rw));
  const dy = Math.max(ry - cy, 0, cy - (ry + rh));
  return (dx === 0 && dy === 0) ? 0 : Math.sqrt(dx * dx + dy * dy);
}

/**
 * Feathered alpha for a single rect with noise.
 */
function featherRect(cx: number, cy: number, rx: number, ry: number, rw: number, rh: number): number {
  const d = rectDist(cx, cy, rx, ry, rw, rh);
  if (d === 0) return OCCLUDED_FLOOR * (0.8 + cellNoise(cx, cy) * 0.2);
  if (d >= FEATHER_PX) return 1;
  const jitter = cellNoise(cx, cy) * 8;
  const dist = Math.max(0, d + jitter);
  const t = Math.min(1, dist / FEATHER_PX);
  return OCCLUDED_FLOOR + (1 - OCCLUDED_FLOOR) * t * t * (3 - 2 * t);
}

/**
 * Organic feathered occlusion with character-level sub-rect support.
 * When an obstacle has charRects, masking follows individual character
 * contours. Falls back to AABB for obstacles without charRects.
 */
function getOcclusionAlpha(cx: number, cy: number, obstacles: RectObstacle[]): number {
  let minAlpha = 1;
  for (let i = 0; i < obstacles.length; i++) {
    const o = obstacles[i];

    // Quick AABB broad-phase: skip if far from the whole obstacle
    const broadDist = rectDist(cx, cy, o.x, o.y, o.w, o.h);
    if (broadDist >= FEATHER_PX) continue;

    // If charRects available, mask per-character
    if (o.charRects && o.charRects.length > 0) {
      for (const cr of o.charRects) {
        const a = featherRect(cx, cy, cr.x, cr.y, cr.w, cr.h);
        minAlpha = Math.min(minAlpha, a);
      }
      continue;
    }

    // Fallback: whole-obstacle AABB
    const dx = Math.max(o.x - cx, 0, cx - (o.x + o.w));
    const dy = Math.max(o.y - cy, 0, cy - (o.y + o.h));

    if (dx === 0 && dy === 0) {
      // Inside obstacle — noise-modulated floor for organic inner texture
      return OCCLUDED_FLOOR * (0.8 + cellNoise(cx, cy) * 0.2);
    }

    const rawDist = Math.sqrt(dx * dx + dy * dy);
    if (rawDist < FEATHER_PX) {
      // Jitter the distance with coordinate noise to break straight edges
      const jitter = cellNoise(cx, cy) * 8; // ±8px wobble
      const dist = Math.max(0, rawDist + jitter);

      // Smooth cubic ease for organic falloff (not linear)
      const t = Math.min(1, dist / FEATHER_PX);
      const eased = t * t * (3 - 2 * t); // smoothstep
      const edgeAlpha = OCCLUDED_FLOOR + (1 - OCCLUDED_FLOOR) * eased;
      minAlpha = Math.min(minAlpha, edgeAlpha);
    }
  }
  return minAlpha;
}

/**
 * Sample the pixel mask at (x, y). Returns 0→1 where 1 = text pixel present.
 * Uses ImageData for fast per-pixel reads.
 */
function sampleMask(
  maskData: ImageData | null,
  maskW: number,
  x: number,
  y: number,
): number {
  if (!maskData) return 0;
  const ix = Math.round(x);
  const iy = Math.round(y);
  if (ix < 0 || iy < 0 || ix >= maskW || iy >= maskData.height) return 0;
  // Alpha channel of RGBA pixel
  return maskData.data[(iy * maskW + ix) * 4 + 3] / 255;
}

/**
 * BitmaskPhysic: Character-grid simulation field.
 *
 * Primary masking: pixel-perfect mask buffer from PhysicsContext.
 * Fallback: geometric AABB + charRect occlusion when mask unavailable.
 */
export const BitmaskPhysic: React.FC<BitmaskPhysicProps> = ({ opacity = 0.25 }) => {
  const mouseRef = useRef({ x: -1000, y: -1000 });
  const { obstaclesRef, maskRef, viewportRef, environment } = usePhysicsRegistry();
  const lastFrameRef = useRef(0);
  const cellSizeRef = useRef(getCellSize());
  const cachedMaskDataRef = useRef<{ data: ImageData; width: number } | null>(null);

  // Keep environment in a ref so the render callback never needs to be recreated
  const envRef = useRef(environment);
  useEffect(() => { envRef.current = environment; }, [environment]);

  const opacityRef = useRef(opacity);
  useEffect(() => { opacityRef.current = opacity; }, [opacity]);

  useEffect(() => {
    const onMove = (e: MouseEvent) => { mouseRef.current = { x: e.clientX, y: e.clientY }; };
    window.addEventListener('mousemove', onMove);
    return () => window.removeEventListener('mousemove', onMove);
  }, []);

  // Stable render callback — deps are only refs, never changes identity
  const render = useCallback((ctx: CanvasRenderingContext2D, width: number, height: number, time: number) => {
    ctx.clearRect(0, 0, width, height);
    ctx.font = FONT;
    ctx.textBaseline = 'top';

    lastFrameRef.current = time;

    const obstacles = obstaclesRef.current ?? [];
    const env = envRef.current;
    const baseOpacity = opacityRef.current;
    const vp = viewportRef.current;

    // Read pixel mask — only re-read ImageData when mask was re-rendered
    const mask = maskRef.current;
    if (mask && mask.dirty) {
      try {
        cachedMaskDataRef.current = {
          data: mask.ctx.getImageData(0, 0, mask.width, mask.height),
          width: mask.width,
        };
        mask.dirty = false;
      } catch { /* mask unavailable */ }
    }
    const maskCache = cachedMaskDataRef.current;
    const maskData = maskCache?.data ?? null;
    const maskW = maskCache?.width ?? 0;
    const { w: CELL_W, h: CELL_H } = cellSizeRef.current;

    const cols = Math.ceil(width / CELL_W);
    const rows = Math.ceil(height / CELL_H);
    const t = time * 0.001;
    const mouse = mouseRef.current;
    const waveAmplitude = env.waveAmplitude ?? 60;
    const baseAlpha = env.opacity ?? baseOpacity;
    const transition = env.effects;
    const transitionProgress = transition?.transitionProgress ?? 0;
    const transitionFrom = transition?.transitionFrom ?? null;
    const isTransitioning = !!transitionFrom && transitionProgress > 0;
    const transitionJitter = isTransitioning ? Math.max(0, Math.min(1, (waveAmplitude - 60) / 90)) : 0;
    const transitionAlphaScale = !isTransitioning
      ? 1
      : transitionFrom === 'v2'
        ? transitionProgress
        : 1 - transitionProgress;
    const alignmentPulse = transition?.alignmentPulse;
    const alignElapsed = alignmentPulse?.active ? time - alignmentPulse.startTime : 0;
    const alignDuration = alignmentPulse?.duration ?? 600;
    const alignPhase = alignmentPulse?.active ? Math.min(1, Math.max(0, alignElapsed / alignDuration)) : 1;
    const alignP = alignmentPulse?.active ? Math.sin(alignPhase * Math.PI) : 0;

    const surgeNorm = Math.max(0, (waveAmplitude - 60) / 60);
    const effectiveWaveAmp = 60 + surgeNorm * 60;
    const effectiveWaveFreq = 0.05 * (1 + surgeNorm * 2);
    const freqMult = effectiveWaveFreq / 0.05;
    const ampMult = effectiveWaveAmp / 60;
    const hueDistort = surgeNorm * 40;

    for (let row = 0; row < rows; row++) {
      const y = row * CELL_H;

      for (let col = 0; col < cols; col++) {
        const x = col * CELL_W;
        const cx = x + CELL_W * 0.5;
        const cy = y + CELL_H * 0.5;

        // Pixel-perfect mask occlusion (primary), geometric fallback only when no mask
        // Prediction: sample mask at predicted position (where text will be next frame)
        const predX = vp.scrollVelX * 1.5;
        const predY = vp.scrollVelY * 1.5;
        let occlusion: number;
        if (maskData && maskW === vp.width) {
          const maskSample = sampleMask(maskData, maskW, cx + predX, cy + predY);
          if (maskSample > 0.5) {
            // Full text pixel — 100% cutout (complete transparency)
            occlusion = 0;
          } else if (maskSample > 0.01) {
            // Edge/partial pixel — smooth fade
            occlusion = 1 - maskSample;
          } else {
            // No text — full field alpha
            occlusion = 1;
          }
        } else {
          occlusion = getOcclusionAlpha(cx, cy, obstacles);
        }

        const dx = cx - mouse.x;
        const dy = cy - mouse.y;
        const distSq = dx * dx + dy * dy;
        const dist = Math.sqrt(distSq);
        const mouseFactor = Math.max(0, 1 - dist / 300);

        // Void core: smoothstep fade from 0.75→0.85 (hard skip above 0.85)
        if (mouseFactor > 0.85) continue;
        let voidFade = 1;
        if (mouseFactor > 0.75) {
          const t2 = (mouseFactor - 0.75) / 0.1; // 0→1 over 0.75→0.85
          voidFade = 1 - t2 * t2 * (3 - 2 * t2); // smoothstep to 0
        }

        // ── Neural data swarm: flow field + repulsion ─────────────────

        // Flow field: two crossing directional streams
        const phase = t * 0.6 * freqMult;
        const flowA = fsin(col * 0.12 + row * 0.08 + phase) + fsin(row * 0.15 - col * 0.05 + phase * 1.4);
        const flowB = fsin(col * 0.07 - row * 0.11 + phase * 0.7) + fsin((col + row) * 0.06 + phase * 1.1);

        // Mouse repulsion: push data away from cursor, leave a void
        const repulsion = mouseFactor * mouseFactor * 2;
        const flowStrength = (flowA * flowA + flowB * flowB) * 0.25 * ampMult;
        const density = Math.max(0, flowStrength - repulsion);

        // Depth layer: cells far from center are darker (3D depth effect)
        const centerDist = Math.sqrt(
          ((cx - width * 0.5) / width) * ((cx - width * 0.5) / width) +
          ((cy - height * 0.5) / height) * ((cy - height * 0.5) / height)
        );
        const depthFade = 1 - centerDist * 0.6;

        // Character selection: flow angle determines character class
        const flowAngle = (flowA + 2) * 3 + flowB; // pseudo-hash
        const charSeed = ((Math.floor(flowAngle * 7 + t * 2) % 30) + 30) % 30;
        let char: string;
        if (charSeed < 16) {
          char = HEX[charSeed]; // hex digits
        } else if (charSeed < 28) {
          char = SYNAPTIC[charSeed - 16]; // math symbols
        } else {
          char = DATA[((Math.floor(flowAngle * 3 + t * 5) % 6) + 6) % 6]; // data particles
        }

        // Alpha: void at center, ring glow at edge, normal field beyond
        // Ring function: peaks at mouseFactor≈0.5, zero at center (1.0) and far (0.0)
        // Ring glow: peaks near the void edge, narrowed to read as a crisp field boundary.
        const ringDist = mouseFactor - 0.82;
        const ringGlow = Math.exp(-ringDist * ringDist * 160) * mouseFactor * 1.8;
        // Center suppression: hard zero when deep inside void
        const voidMask = density > 0.01 ? 1 : 0;
        const rawAlpha = baseAlpha * depthFade * (
          density * (0.3 + flowStrength * 0.7) +  // normal field contribution
          ringGlow * 0.6 * voidMask                 // edge glow (only where some data exists)
        );
        const alpha = rawAlpha * occlusion * voidFade * transitionAlphaScale;
        if (alpha < 0.01) continue;

        let drawX = x;
        let drawY = y;
        if (isTransitioning && transitionFrom === 'v2') {
          const digitalNoiseA = cellNoise(col * 17 + t * 40, row * 19 - t * 30);
          const digitalNoiseB = cellNoise(col * 23 - t * 35, row * 29 + t * 45);
          drawX += digitalNoiseA * transitionJitter * 20 * (1 - alignP);
          drawY += digitalNoiseB * transitionJitter * 20 * (1 - alignP);
        }

        // Color: cyan/purple neural gradient with depth shift
        const baseHue = 200 + fsin(flowA * 0.5 + t * 0.2) * 60 + hueDistort * fsin(t * 2 + col * 0.1);
        const hue = baseHue + (280 - baseHue) * alignP * 0.15;
        const sat = 60 + mouseFactor * 20;
        const lightness = 50 + depthFade * 20 + mouseFactor * 15 + surgeNorm * 10;
        ctx.fillStyle = `hsla(${hue}, ${sat}%, ${lightness}%, ${Math.min(1, alpha)})`;
        ctx.fillText(char, drawX, drawY);
      }
    }

    if (alignP > 0.01) {
      ctx.save();
      ctx.lineWidth = 1;
      ctx.strokeStyle = `hsla(190, 100%, 50%, ${alignP * 0.1})`;
      for (let col = 0; col < cols; col += 4) {
        const x = col * CELL_W + CELL_W * 0.5;
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
        ctx.stroke();
      }
      for (let row = 0; row < rows; row += 4) {
        const y = row * CELL_H + CELL_H * 0.5;
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
      }
      ctx.restore();
    }

    // ── Diagnostic alignment lines ────────────────────────────────────
    if (env.debugAlignment) {
      ctx.lineWidth = 1;
      // Apply same prediction offset as mask sampling
      const diagPredX = vp.scrollVelX * 1.5;
      const diagPredY = vp.scrollVelY * 1.5;

      for (const obs of obstacles) {
        // AABB — cyan
        ctx.strokeStyle = 'rgba(0, 255, 255, 0.6)';
        ctx.strokeRect(obs.x + diagPredX, obs.y + diagPredY, obs.w, obs.h);

        // charRects — magenta
        if (obs.charRects) {
          ctx.strokeStyle = 'rgba(255, 0, 255, 0.5)';
          for (const cr of obs.charRects) {
            ctx.strokeRect(cr.x + diagPredX, cr.y + diagPredY, cr.w, cr.h);
          }
        }
      }
    }
  }, [obstaclesRef, maskRef, viewportRef]); // Stable — only ref identities

  const canvasRef = usePretextCanvas({ onRender: render, isAnimated: true });

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: 'absolute',
        inset: 0,
        width: '100%',
        height: '100%',
        pointerEvents: 'none',
      }}
    />
  );
};
