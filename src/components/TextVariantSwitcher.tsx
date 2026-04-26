import React from 'react';
import type { VariantType } from '../context/ArenaContext';
import { useObstacleDetached } from '../hooks/useObstacle';
import { tokens } from '../design/tokens';

/**
 * TextVariantSwitcher: Minimal text-only variant toggle.
 *
 * Renders as a small transparent island (e.g. `[ V2 / V3_FIELD ]`)
 * that registers as a physics obstacle so background text wraps around it.
 */

const VARIANTS: { id: VariantType; label: string }[] = [
  { id: 'v2', label: 'V2' },
  { id: 'v3', label: 'V3_FIELD' },
];

// ── Stable styles ───────────────────────────────────────────────────

const containerStyle: React.CSSProperties = {
  position: 'fixed',
  bottom: '2rem',
  right: '2rem',
  zIndex: 2000,
  pointerEvents: 'auto',
};

const islandStyle: React.CSSProperties = {
  padding: '0.5rem 1rem',
  display: 'flex',
  alignItems: 'center',
  gap: '0.25rem',
  fontFamily: tokens.fonts.mono,
  fontSize: '10px',
  letterSpacing: '0.15em',
  color: 'rgba(255,255,255,0.35)',
  userSelect: 'none',
};

const separatorStyle: React.CSSProperties = {
  opacity: 0.3,
};

const activeStyle: React.CSSProperties = {
  color: tokens.colors.aurora.cyan,
  fontWeight: 700,
  cursor: 'default',
};

const inactiveStyle: React.CSSProperties = {
  cursor: 'pointer',
  transition: 'color 0.3s ease',
};

// ── Component ───────────────────────────────────────────────────────

interface TextVariantSwitcherProps {
  isZenMode: boolean;
  variant: VariantType;
  onVariantChange: (v: VariantType) => void;
}

const TextVariantSwitcherInner: React.FC<TextVariantSwitcherProps> = ({ isZenMode, variant, onVariantChange }) => {
  const ref = useObstacleDetached(true, isZenMode) as React.RefObject<HTMLDivElement>;

  return (
    <div style={containerStyle}>
      <div ref={ref} style={islandStyle}>
        <span style={separatorStyle}>[</span>
        {VARIANTS.map((v, i) => (
          <React.Fragment key={v.id}>
            {i > 0 && <span style={separatorStyle}>/</span>}
            <span
              onClick={variant !== v.id ? () => onVariantChange(v.id) : undefined}
              style={variant === v.id ? activeStyle : inactiveStyle}
            >
              {v.label}
            </span>
          </React.Fragment>
        ))}
        <span style={separatorStyle}>]</span>
      </div>
    </div>
  );
};

export const TextVariantSwitcher = React.memo(TextVariantSwitcherInner);
