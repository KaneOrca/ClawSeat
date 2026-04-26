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
const MAX_PULL = 4;

const ORCA_PARTS: OrcaPart[] = [
  { id: 'body', top: 14, left: 10, width: 36, height: 14 },
  { id: 'dorsal', top: 4, left: 24, width: 8, height: 12 },
  { id: 'tail', top: 12, left: 0, width: 14, height: 18, rotate: -20 },
  { id: 'snout', top: 18, left: 40, width: 12, height: 8 },
];

export const OrcaLogo: React.FC<OrcaLogoProps> = ({ size = 32, className }) => {
  const { variant, isZenMode } = useArena();
  const { setEnvironment } = usePhysicsRegistry();
  const rootRef = useRef<HTMLSpanElement>(null);
  const [sprayActive, setSprayActive] = useState(false);
  const [eyeGlintActive, setEyeGlintActive] = useState(false);
  const [eyeGlintSrc, setEyeGlintSrc] = useState<string | null>(null);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const scale = size / BASE_HEIGHT;
  const width = BASE_WIDTH * scale;
  const eyeColor = variant === 'v3' ? tokens.colors.aurora.cyan : tokens.colors.aurora.red;

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
      setOffset({
        x: (dx / dist) * pull * MAX_PULL,
        y: (dy / dist) * pull * MAX_PULL,
      });
    };

    window.addEventListener('mousemove', onMove);
    return () => window.removeEventListener('mousemove', onMove);
  }, []);

  useEffect(() => {
    const triggerSpray = () => {
      setSprayActive(true);
      setEnvironment({ waveAmplitude: 96 });
      window.setTimeout(() => {
        setSprayActive(false);
        setEnvironment({ waveAmplitude: 60 });
      }, 220);
    };

    const interval = window.setInterval(triggerSpray, 7000);
    return () => window.clearInterval(interval);
  }, [setEnvironment]);

  useEffect(() => {
    const interval = window.setInterval(() => {
      setEyeGlintActive(true);
      window.setTimeout(() => setEyeGlintActive(false), 200);
    }, 8000);
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
      }}
    >
      {parts.map(part => (
        <OrcaObstaclePart
          key={part.id}
          part={part}
          active={!isZenMode}
        />
      ))}
      <SprayPuff active={sprayActive && !isZenMode} scale={scale} />
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
      }}
    />
  );
};

const SprayPuff: React.FC<{ active: boolean; scale: number }> = ({ active, scale }) => {
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
};

const eyeGlintStyle: React.CSSProperties = {
  position: 'absolute',
  transform: 'translate(-50%, -50%)',
  fontWeight: 900,
  lineHeight: 1,
  pointerEvents: 'none',
};
