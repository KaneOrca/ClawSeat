import React, { useCallback, useEffect, useRef } from 'react';
import { usePhysicsRegistry } from '../../../context/PhysicsContext';
import { useLanguage } from '../../../context/LanguageContext';
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
    currentChallengeId, setChallengeId, isZenMode
  } = useChallengeSubmission();
  const { t } = useLanguage();

  const { setEnvironment } = usePhysicsRegistry();

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
    return () => setEnvironment({ waveAmplitude: 60, waveFrequency: 0.03 });
  }, [setEnvironment]);

  if (!currentChallengeId) return null;

  return (
    <div className="page-challenge-detail variant-v3" style={containerStyle}>
      {/* Back button — atomic */}
      <BackAtomMemo isZenMode={isZenMode} onBack={() => setChallengeId(null)} label={t('challengeDetail.v3.back')} />

      {/* Resonance label — atomic */}
      <LabelAtomMemo isZenMode={isZenMode} title={challenge.title} label={t('challengeDetail.v3.resonance_label')} />

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
        submittingLabel={t('challengeDetail.v3.submitting')}
        submitLabel={t('challengeDetail.v3.submit')}
      />

      {/* Points — atomic */}
      <DiagAtomMemo isZenMode={isZenMode} label={t('challengeDetail.v3.points')} value={String(challenge.points)} />

      {/* Complexity — atomic */}
      <DiagAtomMemo isZenMode={isZenMode} label={t('challengeDetail.v3.complexity')} value={challenge.difficulty} />

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
  color: tokens.colors.text.primary,
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
  fontSize: tokens.sizes['2xl'],
  color: tokens.colors.text.primary,
  caretColor: tokens.colors.aurora.cyan,
  fontFamily: tokens.fonts.body,
  outline: 'none',
  resize: 'none',
  display: 'block',
  marginTop: '2rem',
};

const submitStyle: React.CSSProperties = {
  background: 'none',
  border: 'none',
  padding: '1rem 0',
  fontSize: tokens.sizes.small,
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
  fontSize: tokens.sizes.xxs,
  color: tokens.colors.aurora.purple,
};

const diagValueStyle: React.CSSProperties = {
  fontSize: '1.2rem',
  fontWeight: 700,
};

// ── Atom components ─────────────────────────────────────────────────

const BackAtom: React.FC<{ isZenMode: boolean; onBack: () => void; label: string }> = ({ isZenMode, onBack, label }) => {
  const ref = useObstacleDetached(true, isZenMode) as React.RefObject<HTMLButtonElement>;
  const ripple = useWaveRipple();
  return (
    <MagneticSurface pull={0.2}>
      <button ref={ref as any} data-functional-text="true" onClick={onBack} onPointerEnter={ripple.onPointerEnter} onTouchStart={ripple.onTouchStart}
        style={{ ...backButtonStyle, opacity: isZenMode ? 0.3 : 1, transition: 'opacity 0.6s ease' }}>
        <ArrowLeft size={16} /> {label}
      </button>
    </MagneticSurface>
  );
};
const BackAtomMemo = React.memo(BackAtom);

const LabelAtom: React.FC<{ isZenMode: boolean; title: string; label: string }> = ({ isZenMode, title, label }) => {
  const ref = useObstacleDetached(true, isZenMode) as React.RefObject<HTMLDivElement>;
  return (
    <div ref={ref} data-functional-text="true" style={{ ...labelStyle, opacity: isZenMode ? 0.3 : 1, transition: 'opacity 0.6s ease' }}>
      {label}: {safeStr(title).toUpperCase()}
    </div>
  );
};
const LabelAtomMemo = React.memo(LabelAtom);

const TitleAtom: React.FC<{ isZenMode: boolean; title: string }> = ({ isZenMode, title }) => {
  const ref = useObstacleDetached(true, isZenMode) as React.RefObject<HTMLHeadingElement>;
  const ripple = useWaveRipple();
  return (
    <MagneticSurface pull={0.1}>
      <h1 ref={ref as any} data-functional-text="true" onPointerEnter={ripple.onPointerEnter} onTouchStart={ripple.onTouchStart}
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
    <textarea data-functional-text="true" ref={ref as any} autoFocus value={answer} onChange={onInput} style={textareaStyle} />
  );
};
const TextareaAtomMemo = React.memo(TextareaAtom);

const SubmitAtom: React.FC<{
  isZenMode: boolean;
  answer: string;
  onSubmit: () => void;
  submitting: boolean;
  submittingLabel: string;
  submitLabel: string;
}> = ({ isZenMode, answer, onSubmit, submitting, submittingLabel, submitLabel }) => {
  const ref = useObstacleDetached(true, isZenMode) as React.RefObject<HTMLButtonElement>;
  const ripple = useWaveRipple();
  return (
    <div style={{ opacity: isZenMode && !answer.trim() ? 0 : 1, transition: 'opacity 0.6s ease' }}>
      <MagneticSurface pull={0.2}>
        <button ref={ref as any} data-functional-text="true" onClick={onSubmit} onPointerEnter={ripple.onPointerEnter} onTouchStart={ripple.onTouchStart}
          disabled={submitting || !answer.trim()}
          style={{
            ...submitStyle,
            color: answer.trim() ? tokens.colors.aurora.cyan : tokens.colors.text.micro,
            opacity: submitting ? 0.5 : 1,
          }}>
          {submitting ? submittingLabel : submitLabel}
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
