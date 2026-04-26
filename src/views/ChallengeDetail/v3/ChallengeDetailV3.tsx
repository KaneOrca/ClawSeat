import React, { useCallback, useEffect, useRef } from 'react';
import { usePhysicsRegistry } from '../../../context/PhysicsContext';
import { tokens } from '../../../design/tokens';
import { safeStr } from '../../../utils/safeStr';
import { useObstacleDetached } from '../../../hooks/useObstacle';
import { useWaveRipple } from '../../../hooks/useWaveRipple';
import { MagneticSurface } from '../../../components/MagneticSurface';
import { useChallengeSubmission } from '../../../hooks/useChallengeSubmission';
import { PretextEditorial } from '../../../components/PretextEditorial';
import { ArrowLeft } from 'lucide-react';

/**
 * ChallengeDetailV3: Atomic obstacle challenge view.
 * No region wrappers — each text element registers directly.
 */
export const ChallengeDetailV3: React.FC = () => {
  const {
    challenge, answer, setAnswer, submitting, handleSubmit,
    currentChallengeId, setChallengeId, isZenMode, locale
  } = useChallengeSubmission();

  const { registerSoloist, unregisterSoloist, setEnvironment } = usePhysicsRegistry();

  const intensityRef = useRef(1);

  const handleInput = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setAnswer(e.target.value);
    intensityRef.current = 1.5;
    setEnvironment({ waveAmplitude: 90 });
    setTimeout(() => {
      intensityRef.current = 1;
      setEnvironment({ waveAmplitude: 60 });
    }, 500);
  }, [setAnswer, setEnvironment]);

  useEffect(() => {
    const soloistText = answer ||
      (locale === 'zh-CN' ? '将你的解答传入场域...' : 'Speak your solution into the field...');
    if (!isZenMode || answer) {
      registerSoloist({
        id: 'challenge-user-input',
        text: soloistText,
        lineIndex: 11,
        color: tokens.colors.aurora.cyan,
      });
    }
    return () => unregisterSoloist('challenge-user-input');
  }, [answer, isZenMode, locale, registerSoloist, unregisterSoloist]);

  useEffect(() => {
    return () => setEnvironment({ waveAmplitude: 60, waveFrequency: 0.03 });
  }, [setEnvironment]);

  if (!currentChallengeId) return null;

  return (
    <div className="page-challenge-detail variant-v3" style={containerStyle}>
      {/* Back button — atomic */}
      <BackAtomMemo isZenMode={isZenMode} onBack={() => setChallengeId(null)} />

      {/* Resonance label — atomic */}
      <LabelAtomMemo isZenMode={isZenMode} title={challenge.title} />

      {/* Title — atomic */}
      <TitleAtomMemo isZenMode={isZenMode} title={challenge.title} />

      {/* Challenge description — PretextEditorial reveal */}
      <DescriptionAtomMemo isZenMode={isZenMode} text={challenge.description} />

      {/* Textarea — atomic */}
      <TextareaAtomMemo
        isZenMode={isZenMode}
        answer={answer}
        onInput={handleInput}
      />

      {/* Submit button — atomic */}
      <SubmitAtomMemo
        isZenMode={isZenMode}
        answer={answer}
        onSubmit={handleSubmit}
        submitting={submitting}
      />

      {/* Points — atomic */}
      <DiagAtomMemo isZenMode={isZenMode} label="POINTS" value={String(challenge.points)} />

      {/* Complexity — atomic */}
      <DiagAtomMemo isZenMode={isZenMode} label="COMPLEXITY" value={challenge.difficulty} />

      <style>{`
        @media (max-width: 768px) {
          .page-challenge-detail.variant-v3 {
            padding: 2rem 1rem !important;
          }
          .challenge-v3-diag {
            display: block !important;
            margin-right: 0 !important;
            margin-top: 1rem !important;
          }
        }
      `}</style>
    </div>
  );
};

// ── Styles ──────────────────────────────────────────────────────────

const containerStyle: React.CSSProperties = {
  minHeight: '100vh',
  color: '#fff',
  padding: '4rem 2rem',
  position: 'relative',
};

const backButtonStyle: React.CSSProperties = {
  background: 'none',
  border: 'none',
  color: tokens.colors.aurora.purple,
  cursor: 'pointer',
  display: 'inline-flex',
  alignItems: 'center',
  gap: '0.5rem',
  fontFamily: tokens.fonts.mono,
  fontSize: '12px',
};

const labelStyle: React.CSSProperties = {
  color: tokens.colors.aurora.purple,
  fontFamily: tokens.fonts.mono,
  fontSize: '12px',
  display: 'inline-block',
  marginTop: '1rem',
};

const titleStyle: React.CSSProperties = {
  fontSize: 'clamp(2.5rem, 5vw, 4rem)',
  fontWeight: 700,
  lineHeight: 1,
  letterSpacing: '-0.04em',
  marginTop: '2rem',
  display: 'inline-block',
};

const descriptionStyle: React.CSSProperties = {
  maxWidth: '760px',
  marginTop: '2rem',
  marginBottom: '1rem',
  opacity: 0.82,
};

const textareaStyle: React.CSSProperties = {
  width: '100%',
  maxWidth: '800px',
  height: '25vh',
  background: 'transparent',
  border: 'none',
  padding: '2rem 0',
  fontSize: '1.25rem',
  color: 'rgba(255,255,255,0.9)',
  caretColor: tokens.colors.aurora.cyan,
  fontFamily: "'Outfit', sans-serif",
  outline: 'none',
  resize: 'none',
  display: 'block',
  marginTop: '2rem',
};

const submitStyle: React.CSSProperties = {
  background: 'none',
  border: 'none',
  padding: '1rem 0',
  fontSize: '11px',
  fontFamily: tokens.fonts.mono,
  fontWeight: 700,
  cursor: 'pointer',
  display: 'inline-flex',
  alignItems: 'center',
  gap: '1rem',
  textTransform: 'uppercase',
  letterSpacing: '0.3em',
  transition: 'all 0.3s ease',
};

const diagLabelStyle: React.CSSProperties = {
  fontFamily: tokens.fonts.mono,
  fontSize: '9px',
  color: tokens.colors.aurora.purple,
};

const diagValueStyle: React.CSSProperties = {
  fontSize: '1.2rem',
  fontWeight: 700,
};

// ── Atom components ─────────────────────────────────────────────────

const BackAtom: React.FC<{ isZenMode: boolean; onBack: () => void }> = ({ isZenMode, onBack }) => {
  const ref = useObstacleDetached(true, isZenMode) as React.RefObject<HTMLButtonElement>;
  const { onPointerEnter, onTouchStart } = useWaveRipple();
  return (
    <MagneticSurface pull={0.2}>
      <button ref={ref as any} onClick={onBack} onPointerEnter={onPointerEnter} onTouchStart={onTouchStart}
        style={{ ...backButtonStyle, opacity: isZenMode ? 0.3 : 1, transition: 'opacity 0.6s ease' }}>
        <ArrowLeft size={16} /> [ QUIET_THE_CHORUS ]
      </button>
    </MagneticSurface>
  );
};
const BackAtomMemo = React.memo(BackAtom);

const LabelAtom: React.FC<{ isZenMode: boolean; title: string }> = ({ isZenMode, title }) => {
  const ref = useObstacleDetached(true, isZenMode) as React.RefObject<HTMLDivElement>;
  return (
    <div ref={ref} style={{ ...labelStyle, opacity: isZenMode ? 0.3 : 1, transition: 'opacity 0.6s ease' }}>
      NODE_RESONANCE: {safeStr(title).toUpperCase()}
    </div>
  );
};
const LabelAtomMemo = React.memo(LabelAtom);

const TitleAtom: React.FC<{ isZenMode: boolean; title: string }> = ({ isZenMode, title }) => {
  const ref = useObstacleDetached(true, isZenMode) as React.RefObject<HTMLHeadingElement>;
  const { onPointerEnter, onTouchStart } = useWaveRipple();
  return (
    <MagneticSurface pull={0.1}>
      <h1 ref={ref as any} onPointerEnter={onPointerEnter} onTouchStart={onTouchStart}
        style={{ ...titleStyle, opacity: isZenMode ? 0 : 0.8, transition: 'opacity 0.6s ease' }}>
        {title}
      </h1>
    </MagneticSurface>
  );
};
const TitleAtomMemo = React.memo(TitleAtom);

const DescriptionAtom: React.FC<{ isZenMode: boolean; text: string }> = ({ isZenMode, text }) => {
  return (
    <div style={{ ...descriptionStyle, opacity: isZenMode ? 0.05 : descriptionStyle.opacity }}>
      <PretextEditorial
        text={safeStr(text)}
        width={760}
        lineHeight={24}
        fontDef={`400 16px ${tokens.fonts.body}`}
        color={tokens.colors.text.secondary}
      />
    </div>
  );
};
const DescriptionAtomMemo = React.memo(DescriptionAtom);

const TextareaAtom: React.FC<{
  isZenMode: boolean;
  answer: string;
  onInput: (e: React.ChangeEvent<HTMLTextAreaElement>) => void;
}> = ({ isZenMode, answer, onInput }) => {
  const ref = useObstacleDetached(true, isZenMode) as React.RefObject<HTMLTextAreaElement>;
  return (
    <textarea ref={ref as any} autoFocus value={answer} onChange={onInput} style={textareaStyle} />
  );
};
const TextareaAtomMemo = React.memo(TextareaAtom);

const SubmitAtom: React.FC<{
  isZenMode: boolean;
  answer: string;
  onSubmit: () => void;
  submitting: boolean;
}> = ({ isZenMode, answer, onSubmit, submitting }) => {
  const ref = useObstacleDetached(true, isZenMode) as React.RefObject<HTMLButtonElement>;
  const { onPointerEnter, onTouchStart } = useWaveRipple();
  return (
    <div style={{ opacity: isZenMode && !answer.trim() ? 0 : 1, transition: 'opacity 0.6s ease' }}>
      <MagneticSurface pull={0.2}>
        <button ref={ref as any} onClick={onSubmit} onPointerEnter={onPointerEnter} onTouchStart={onTouchStart}
          disabled={submitting || !answer.trim()}
          style={{
            ...submitStyle,
            color: answer.trim() ? tokens.colors.aurora.cyan : 'rgba(255,255,255,0.2)',
            opacity: submitting ? 0.5 : 1,
          }}>
          {submitting ? 'RESONATING...' : '[ TRANSMIT_ANS ]'}
        </button>
      </MagneticSurface>
    </div>
  );
};
const SubmitAtomMemo = React.memo(SubmitAtom);

const DiagAtom: React.FC<{ isZenMode: boolean; label: string; value: string }> = ({ isZenMode, label, value }) => {
  const ref = useObstacleDetached(true, isZenMode) as React.RefObject<HTMLDivElement>;
  return (
    <div ref={ref} className="challenge-v3-diag" style={{
      display: 'inline-block',
      marginRight: '4rem',
      marginTop: '2rem',
      opacity: isZenMode ? 0.2 : 0.5,
      transition: 'opacity 0.6s ease',
    }}>
      <div style={diagLabelStyle}>{label}</div>
      <div style={diagValueStyle}>{value}</div>
    </div>
  );
};
const DiagAtomMemo = React.memo(DiagAtom);
