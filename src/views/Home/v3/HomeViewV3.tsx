import React, { useCallback } from 'react';
import { useArena } from '../../../context/ArenaContext';
import { tokens } from '../../../design/tokens';
import { useObstacleDetached } from '../../../hooks/useObstacle';
import { MagneticSurface } from '../../../components/MagneticSurface';
import { useWaveRipple } from '../../../hooks/useWaveRipple';

/**
 * HomeViewV3: Ultimate atomic composition.
 * Obstacle refs on naked text spans only — positioning lives on outer wrappers.
 */
export const HomeViewV3: React.FC = () => {
  const { registerAgent, user, setView, isZenMode } = useArena();

  const onInitialize = useCallback(() => {
    if (user) {
      setView('hall');
      return;
    }
    const nickname = `Agent_${Math.floor(Math.random() * 10000)}`;
    registerAgent(nickname);
  }, [user, setView, registerAgent]);

  return (
    <div className="page-home variant-v3" style={containerStyle}>
      {/* Brand — position wrapper, ref on text */}
      <div style={pos.brand}>
        <BrandAtomMemo isZenMode={isZenMode} />
      </div>

      {/* Chorus — position wrapper, ref on text */}
      <div style={pos.chorus}>
        <ChorusAtomMemo isZenMode={isZenMode} />
      </div>

      {/* Field — position wrapper, ref on text */}
      <div style={pos.field}>
        <FieldAtomMemo isZenMode={isZenMode} />
      </div>

      {/* Description lines — position wrappers, refs on text */}
      <div style={pos.desc1}>
        <DescAtomMemo isZenMode={isZenMode} text="Collective text physics and echo fields." />
      </div>
      <div style={pos.desc2}>
        <DescAtomMemo isZenMode={isZenMode} text="Live event-poem streams." />
      </div>

      {/* CTA — position wrapper, ref on button text */}
      <div style={pos.cta}>
        <CTAAtomMemo onInitialize={onInitialize} user={user} isZenMode={isZenMode} />
      </div>

      <style>{responsiveCSS}</style>
    </div>
  );
};

// ── Positioning (on wrappers only — NOT on ref'd elements) ──────────

const containerStyle: React.CSSProperties = {
  color: 'white',
  minHeight: '100vh',
  position: 'relative',
};

const pos = {
  brand:  { position: 'absolute', top: '8vh',  left: '3vw'  } as React.CSSProperties,
  chorus: { position: 'absolute', top: '28vh', left: '8vw'  } as React.CSSProperties,
  field:  { position: 'absolute', top: '42vh', left: '22vw' } as React.CSSProperties,
  desc1:  { position: 'absolute', top: '56vh', left: '12vw' } as React.CSSProperties,
  desc2:  { position: 'absolute', top: '59vh', left: '14vw' } as React.CSSProperties,
  cta:    { position: 'absolute', top: '68vh', right: '15vw' } as React.CSSProperties,
};

// ── Typography (on ref'd text elements — no positioning) ────────────

const brandTextStyle: React.CSSProperties = {
  fontFamily: tokens.fonts.mono,
  fontSize: '14px',
  fontWeight: 900,
  letterSpacing: '0.3em',
};

const heroTextStyle: React.CSSProperties = {
  fontFamily: tokens.fonts.display,
  fontSize: 'clamp(3rem, 12vw, 7rem)',
  fontWeight: 700,
  letterSpacing: '-0.02em',
  lineHeight: 0.85,
};

const descTextStyle: React.CSSProperties = {
  fontSize: '1rem',
  lineHeight: 1.8,
  color: tokens.colors.text.secondary,
};

const ctaTextStyle: React.CSSProperties = {
  background: 'none',
  color: tokens.colors.aurora.cyan,
  border: 'none',
  fontWeight: 900,
  fontFamily: tokens.fonts.mono,
  fontSize: '12px',
  letterSpacing: '0.2em',
  cursor: 'pointer',
  textTransform: 'uppercase',
};

// ── Responsive ──────────────────────────────────────────────────────

const responsiveCSS = `
  @media (max-width: 768px), (max-height: 600px) {
    .page-home.variant-v3 * {
      position: static !important;
      top: auto !important;
      left: auto !important;
      right: auto !important;
      max-width: 100% !important;
    }
    .page-home.variant-v3 {
      display: flex;
      flex-direction: column;
      padding: 2rem 1rem;
      gap: 2rem;
    }
  }
`;

// ── Atoms: ref on naked text, MagneticSurface as interaction layer ──

const BrandAtom: React.FC<{ isZenMode: boolean }> = ({ isZenMode }) => {
  const ref = useObstacleDetached(true, isZenMode) as React.RefObject<HTMLSpanElement>;
  const { onPointerEnter, onTouchStart } = useWaveRipple();
  return (
    <MagneticSurface pull={0.15}>
      <span ref={ref as any} onPointerEnter={onPointerEnter} onTouchStart={onTouchStart} style={brandTextStyle}>
        ARENA_PRETEXT
      </span>
    </MagneticSurface>
  );
};
const BrandAtomMemo = React.memo(BrandAtom);

const ChorusAtom: React.FC<{ isZenMode: boolean }> = ({ isZenMode }) => {
  const ref = useObstacleDetached(true, isZenMode) as React.RefObject<HTMLSpanElement>;
  const { onPointerEnter, onTouchStart } = useWaveRipple();
  return (
    <MagneticSurface pull={0.1}>
      <span ref={ref as any} onPointerEnter={onPointerEnter} onTouchStart={onTouchStart} style={heroTextStyle}>
        Chorus
      </span>
    </MagneticSurface>
  );
};
const ChorusAtomMemo = React.memo(ChorusAtom);

const FieldAtom: React.FC<{ isZenMode: boolean }> = ({ isZenMode }) => {
  const ref = useObstacleDetached(true, isZenMode) as React.RefObject<HTMLSpanElement>;
  const { onPointerEnter, onTouchStart } = useWaveRipple();
  return (
    <MagneticSurface pull={0.1}>
      <span ref={ref as any} onPointerEnter={onPointerEnter} onTouchStart={onTouchStart} style={heroTextStyle}>
        <span className="gemini-text">Field.</span>
      </span>
    </MagneticSurface>
  );
};
const FieldAtomMemo = React.memo(FieldAtom);

const DescAtom: React.FC<{ isZenMode: boolean; text: string }> = ({ isZenMode, text }) => {
  const ref = useObstacleDetached(true, isZenMode) as React.RefObject<HTMLSpanElement>;
  return <span ref={ref as any} style={descTextStyle}>{text}</span>;
};
const DescAtomMemo = React.memo(DescAtom);

const CTAAtom: React.FC<{ onInitialize: () => void; user: any; isZenMode: boolean }> = ({ onInitialize, user, isZenMode }) => {
  const ref = useObstacleDetached(true, isZenMode) as React.RefObject<HTMLSpanElement>;
  const { onPointerEnter, onTouchStart } = useWaveRipple();
  return (
    <MagneticSurface pull={0.2}>
      <span ref={ref as any} role="button" tabIndex={0} onClick={onInitialize} onPointerEnter={onPointerEnter} onTouchStart={onTouchStart}
        onKeyDown={e => e.key === 'Enter' && onInitialize()} style={ctaTextStyle}>
        {user ? '[ JOIN_CHORUS ]' : '[ VOICE_AUTHORIZATION ]'}
      </span>
    </MagneticSurface>
  );
};
const CTAAtomMemo = React.memo(CTAAtom);
