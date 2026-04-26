import React, { useCallback } from 'react';
import { useArena } from '../../../context/ArenaContext';
import { useLanguage } from '../../../context/LanguageContext';
import { tokens } from '../../../design/tokens';
import { useObstacleDetached } from '../../../hooks/useObstacle';
import { MagneticSurface } from '../../../components/MagneticSurface';
import { useWaveRipple } from '../../../hooks/useWaveRipple';
import { PretextButton } from '../../../components/PretextButton';

/**
 * HomeViewV3: Ultimate atomic composition.
 * Obstacle refs on naked text spans only — positioning lives on outer wrappers.
 */
export const HomeViewV3: React.FC = () => {
  const { registerAgent, user, setView, isZenMode } = useArena();
  const { t } = useLanguage();

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
        <BrandAtomMemo isZenMode={isZenMode} text={t('home.v3.brand')} />
      </div>

      {/* Chorus — position wrapper, ref on text */}
      <div style={pos.chorus}>
        <ChorusAtomMemo isZenMode={isZenMode} text={t('home.v3.chorus')} />
      </div>

      {/* Field — position wrapper, ref on text */}
      <div style={pos.field}>
        <FieldAtomMemo isZenMode={isZenMode} text={t('home.v3.field')} />
      </div>

      {/* Description lines — position wrappers, refs on text */}
      <div style={pos.desc1}>
        <DescAtomMemo isZenMode={isZenMode} text={t('home.v3.desc_primary')} />
      </div>
      <div style={pos.desc2}>
        <DescAtomMemo isZenMode={isZenMode} text={t('home.v3.desc_secondary')} />
      </div>

      {/* Agent prompt — functional text, not a card */}
      <div style={pos.prompt}>
        <PromptAtomMemo isZenMode={isZenMode} promptLabel={t('home.v2.agent_prompt.body')} onTrigger={() => setView('auth')} />
      </div>

      {/* CTA — position wrapper, ref on button text */}
      <div style={pos.cta}>
        <CTAAtomMemo
          onInitialize={onInitialize}
          user={user}
          isZenMode={isZenMode}
          joinLabel={t('home.v3.cta_join')}
          authorizeLabel={t('home.v3.cta_authorize')}
        />
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
  prompt: { position: 'absolute', top: '65vh', left: '14vw', width: 'min(640px, 72vw)' } as React.CSSProperties,
  cta:    { position: 'absolute', top: '82vh', right: '15vw' } as React.CSSProperties,
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

const promptTextStyle: React.CSSProperties = {
  color: tokens.colors.aurora.cyan,
  display: 'block',
  fontFamily: tokens.fonts.mono,
  fontSize: 'clamp(0.9rem, 2vw, 1.15rem)',
  fontWeight: 700,
  letterSpacing: '0.08em',
  lineHeight: 2,
  textAlign: 'left',
  textDecoration: 'none',
  textShadow: '0 0 16px rgba(70, 214, 255, 0.28)',
  whiteSpace: 'pre-line',
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

const BrandAtom: React.FC<{ isZenMode: boolean; text: string }> = ({ isZenMode, text }) => {
  const ref = useObstacleDetached(true, isZenMode) as React.RefObject<HTMLSpanElement>;
  const { onPointerEnter, onTouchStart } = useWaveRipple();
  return (
    <MagneticSurface pull={0.15}>
      <span ref={ref as any} onPointerEnter={onPointerEnter} onTouchStart={onTouchStart} style={brandTextStyle}>
        {text}
      </span>
    </MagneticSurface>
  );
};
const BrandAtomMemo = React.memo(BrandAtom);

const ChorusAtom: React.FC<{ isZenMode: boolean; text: string }> = ({ isZenMode, text }) => {
  const ref = useObstacleDetached(true, isZenMode) as React.RefObject<HTMLSpanElement>;
  const { onPointerEnter, onTouchStart } = useWaveRipple();
  return (
    <MagneticSurface pull={0.1}>
      <span ref={ref as any} onPointerEnter={onPointerEnter} onTouchStart={onTouchStart} style={heroTextStyle}>
        {text}
      </span>
    </MagneticSurface>
  );
};
const ChorusAtomMemo = React.memo(ChorusAtom);

const FieldAtom: React.FC<{ isZenMode: boolean; text: string }> = ({ isZenMode, text }) => {
  const ref = useObstacleDetached(true, isZenMode) as React.RefObject<HTMLSpanElement>;
  const { onPointerEnter, onTouchStart } = useWaveRipple();
  return (
    <MagneticSurface pull={0.1}>
      <span ref={ref as any} onPointerEnter={onPointerEnter} onTouchStart={onTouchStart} style={heroTextStyle}>
        <span className="gemini-text">{text}</span>
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

const PromptAtom: React.FC<{ isZenMode: boolean; promptLabel: string; onTrigger: () => void }> = ({
  isZenMode,
  promptLabel,
  onTrigger,
}) => {
  const { onPointerEnter, onTouchStart } = useWaveRipple();
  return (
    <MagneticSurface pull={0.12}>
      <PretextButton
        config={{
          label: promptLabel,
          engine: 'bitmask',
          physicsLineIndex: 31,
          soloistId: 'home-v3-agent-prompt',
          color: tokens.colors.aurora.cyan,
          opacity: isZenMode ? 0.4 : 0.95,
          onTrigger,
          activationEnvironment: { waveAmplitude: 90, opacity: 0.22 },
          triggerEnvironment: { waveAmplitude: 120, opacity: 0.3 },
          idleEnvironment: { waveAmplitude: 60, opacity: 0.12 },
        }}
        onPointerEnter={onPointerEnter}
        onTouchStart={onTouchStart}
        style={promptTextStyle}
      />
    </MagneticSurface>
  );
};
const PromptAtomMemo = React.memo(PromptAtom);

const CTAAtom: React.FC<{
  onInitialize: () => void;
  user: any;
  isZenMode: boolean;
  joinLabel: string;
  authorizeLabel: string;
}> = ({ onInitialize, user, isZenMode, joinLabel, authorizeLabel }) => {
  const ref = useObstacleDetached(true, isZenMode) as React.RefObject<HTMLSpanElement>;
  const { onPointerEnter, onTouchStart } = useWaveRipple();
  return (
    <MagneticSurface pull={0.2}>
      <span ref={ref as any} role="button" tabIndex={0} onClick={onInitialize} onPointerEnter={onPointerEnter} onTouchStart={onTouchStart}
        onKeyDown={e => e.key === 'Enter' && onInitialize()} style={ctaTextStyle}>
        {user ? joinLabel : authorizeLabel}
      </span>
    </MagneticSurface>
  );
};
const CTAAtomMemo = React.memo(CTAAtom);
