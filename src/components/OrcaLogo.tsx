import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useArena } from '../context/ArenaContext';
import { usePhysicsRegistry } from '../context/PhysicsContext';
import { tokens } from '../design/tokens';
import { useObstacleDetached } from '../hooks/useObstacle';

interface OrcaLogoProps {
  size?: number;
  className?: string;
}

interface OrcaPart {
  id: string;
  top: number;
  left: number;
  width: number;
  height: number;
  rotate?: number;
}

const BASE_WIDTH = 60;
const BASE_HEIGHT = 36;
const MAX_PULL = 12;
const SPRAY_INTERVAL_MS = 3500;
const SPRAY_DURATION_MS = 220;
const SPRAY_AMP = 120;
const GLINT_INTERVAL_MS = 4200;
const GLINT_DURATION_MS = 250;
const FUNCTIONAL_TEXT_SELECTOR = '[data-functional-text], [data-pretext-engine], [data-pretext-state]';

const ORCA_PARTS: OrcaPart[] = [
  { id: 'body', top: 14, left: 10, width: 36, height: 14 },
  { id: 'dorsal', top: 4, left: 24, width: 8, height: 12 },
  { id: 'tail', top: 12, left: 0, width: 14, height: 18, rotate: -20 },
  { id: 'snout', top: 18, left: 40, width: 12, height: 8 },
];

export const OrcaLogo: React.FC<OrcaLogoProps> = ({ size = 40, className }) => {
  const { variant, isZenMode } = useArena();
  const { environment, setEnvironment } = usePhysicsRegistry();
  const rootRef = useRef<HTMLSpanElement>(null);
  const environmentRef = useRef(environment);
  const [sprayAmp, setSprayAmp] = useState(0);
  const sprayAmpRef = useRef(0);
  const sprayFrameRef = useRef<number | null>(null);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const lastPointerRef = useRef({ x: 0, y: 0 });
  const hoverRef = useRef(false);
  const sprayIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const sprayTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const sprayBaseAmplitudeRef = useRef(60);
  const scale = size / BASE_HEIGHT;
  const width = BASE_WIDTH * scale;
  const eyeColor = variant === 'v3' ? tokens.colors.aurora.cyan : tokens.colors.aurora.red;
  const haloColor = variant === 'v3' ? `${tokens.colors.aurora.cyan}44` : `${tokens.colors.aurora.red}33`;
  const sprayFill = variant === 'v3' ? tokens.colors.aurora.cyan : tokens.colors.manuscript.red;
  const sprayIntensity = Math.min(1, sprayAmp / SPRAY_TARGET_AMP);
  const haloBlur = 4 + sprayIntensity * 4;

  useEffect(() => {
    environmentRef.current = environment;
  }, [environment]);

  const parts = useMemo(() => ORCA_PARTS.map(part => ({
    ...part,
    top: part.top * scale,
    left: part.left * scale,
    width: part.width * scale,
    height: part.height * scale,
  })), [scale]);

  useEffect(() => {
    const onMove = (event: MouseEvent) => {
      const rect = rootRef.current?.getBoundingClientRect();
      if (!rect) return;
      const centerX = rect.left + rect.width / 2;
      const centerY = rect.top + rect.height / 2;
      const dx = event.clientX - centerX;
      const dy = event.clientY - centerY;
      const dist = Math.hypot(dx, dy) || 1;
      const pull = Math.min(dist / 300, 1);
      const easedPull = Math.sqrt(pull);
      lastPointerRef.current = { x: event.clientX, y: event.clientY };
      setOffset({
        x: (dx / dist) * easedPull * MAX_PULL,
        y: (dy / dist) * easedPull * MAX_PULL,
      });
    };

    window.addEventListener('mousemove', onMove);
    return () => window.removeEventListener('mousemove', onMove);
  }, []);

  useEffect(() => {
    const isPointerOnFunctionalText = (x: number, y: number) => {
      return document
        .elementsFromPoint(x, y)
        .some(element => element.matches(FUNCTIONAL_TEXT_SELECTOR));
    };

    const triggerSpray = () => {
      const hoveringFunctionalText = document
        .elementsFromPoint(lastPointerRef.current.x, lastPointerRef.current.y)
        .some(element => element.hasAttribute('data-functional-text'));
      if (!hoveringFunctionalText) return;

      const prevAmp = environmentRef.current.waveAmplitude ?? 60;
      sprayBaseAmplitudeRef.current = prevAmp;
      setSprayAmp(SPRAY_TARGET_AMP);
      setEnvironment({ waveAmplitude: SPRAY_AMP });
      if (sprayTimeoutRef.current) {
        window.clearTimeout(sprayTimeoutRef.current);
      }
      sprayTimeoutRef.current = window.setTimeout(() => {
        setSprayAmp(0);
        setEnvironment({ waveAmplitude: prevAmp });
      }, SPRAY_DURATION_MS);
    };

    const stopSpray = () => {
      if (sprayIntervalRef.current) {
        window.clearInterval(sprayIntervalRef.current);
        sprayIntervalRef.current = null;
      }
      if (sprayTimeoutRef.current) {
        window.clearTimeout(sprayTimeoutRef.current);
        sprayTimeoutRef.current = null;
      }
      setSprayAmp(0);
      setEnvironment({ waveAmplitude: sprayBaseAmplitudeRef.current });
    };

    const startSpray = () => {
      if (sprayIntervalRef.current) return;
      triggerSpray();
      sprayIntervalRef.current = window.setInterval(() => {
        if (!isPointerOnFunctionalText(lastPointerRef.current.x, lastPointerRef.current.y)) {
          stopSpray();
          return;
        }
        triggerSpray();
      }, SPRAY_INTERVAL_MS);
    };

    const onPointerMove = (event: PointerEvent) => {
      const hoveringFunctional = isPointerOnFunctionalText(event.clientX, event.clientY);
      if (hoveringFunctional === hoverRef.current) return;
      hoverRef.current = hoveringFunctional;

      if (hoveringFunctional) {
        startSpray();
      } else {
        stopSpray();
      }
    };

    document.addEventListener('pointermove', onPointerMove, true);

    return () => {
      document.removeEventListener('pointermove', onPointerMove, true);
      stopSpray();
      hoverRef.current = false;
    };
  }, [setEnvironment]);

  useEffect(() => {
    const interval = window.setInterval(() => {
      setEyeGlintActive(true);
      window.setTimeout(() => setEyeGlintActive(false), GLINT_DURATION_MS);
    }, GLINT_INTERVAL_MS);
    return () => window.clearInterval(interval);
  }, []);

  useEffect(() => {
    if (!eyeGlintActive) {
      setEyeGlintSrc(null);
      return;
    }

    const canvas = document.createElement('canvas');
    const dpr = window.devicePixelRatio || 1;
    const glyphSize = Math.max(14, size * 0.5);
    canvas.width = glyphSize * dpr;
    canvas.height = glyphSize * dpr;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, glyphSize, glyphSize);
    ctx.font = variant === 'v3'
      ? `900 ${Math.max(11, size * 0.34)}px ${tokens.fonts.mono}`
      : `900 ${Math.max(12, size * 0.4)}px 'Playfair Display'`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = eyeColor;
    ctx.fillText(variant === 'v3' ? '+' : '*', glyphSize / 2, glyphSize / 2);
    setEyeGlintSrc(canvas.toDataURL('image/png'));
  }, [eyeColor, eyeGlintActive, size, variant]);

  return (
    <span
      ref={rootRef}
      className={className}
      aria-hidden="true"
      style={{
        ...rootStyle,
        width,
        height: size,
        transform: `translate(${offset.x}px, ${offset.y}px)`,
        filter: `drop-shadow(0 0 ${haloBlur}px ${haloColor})`,
      }}
    >
      {parts.map(part => (
        <OrcaObstaclePart
          key={part.id}
          part={part}
          active={!isZenMode}
        />
      ))}
      <SprayPuff active={sprayIntensity > SPRAY_VISIBLE_THRESHOLD && !isZenMode} scale={scale} intensity={sprayIntensity} fill={sprayFill} />
      {eyeGlintSrc && (
        <img
          alt=""
          src={eyeGlintSrc}
          style={{
          ...eyeGlintStyle,
          left: 36 * scale,
          top: 16 * scale,
          width: Math.max(14, size * 0.5),
          height: Math.max(14, size * 0.5),
        }}
        />
      )}
      <style>{`
        @keyframes orcaTailWag {
          0%, 100% { transform: rotate(-20deg); }
          50% { transform: rotate(-12deg); }
        }
      `}</style>
    </span>
  );
};

const OrcaObstaclePart: React.FC<{ part: OrcaPart; active: boolean }> = ({ part, active }) => {
  const ref = useObstacleDetached(active, false) as React.RefObject<HTMLSpanElement>;
  return (
    <span
      ref={ref}
      style={{
        ...partStyle,
        top: part.top,
        left: part.left,
        width: part.width,
        height: part.height,
        transform: part.rotate ? `rotate(${part.rotate}deg)` : undefined,
        animation: part.id === 'tail' ? 'orcaTailWag 3.2s ease-in-out infinite' : undefined,
      }}
    />
  );
};

const SprayPuff: React.FC<{ active: boolean; scale: number; intensity: number; fill: string }> = ({ active, scale, intensity, fill }) => {
  const ref = useObstacleDetached(active, false) as React.RefObject<HTMLSpanElement>;
  if (!active) return null;
  return (
    <span
      ref={ref}
      style={{
        ...partStyle,
        top: -10 * scale,
        left: 36 * scale,
        width: 12 * scale,
        height: 12 * scale,
        background: fill,
        opacity: 0.25 + intensity * 0.75,
        transform: `scale(${0.7 + intensity * 0.5})`,
        boxShadow: `0 0 ${8 + intensity * 16}px ${fill}`,
      }}
    />
  );
};

const rootStyle: React.CSSProperties = {
  position: 'relative',
  display: 'inline-block',
  flex: '0 0 auto',
  transition: tokens.transitions.default,
};

const partStyle: React.CSSProperties = {
  position: 'absolute',
  display: 'block',
  borderRadius: '999px',
  pointerEvents: 'none',
  transformOrigin: 'center center',
};

const eyeGlintStyle: React.CSSProperties = {
  position: 'absolute',
  transform: 'translate(-50%, -50%)',
  fontWeight: 900,
  lineHeight: 1,
  pointerEvents: 'none',
};
