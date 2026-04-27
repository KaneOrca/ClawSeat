import React, { useMemo } from 'react';
import { ArrowLeft, Edit3 } from 'lucide-react';
import { PretextButton } from '../../../components/PretextButton';
import { ManuscriptPhysic } from '../../../components/text-physics/ManuscriptPhysic';
import { useChallengeSubmission } from '../../../hooks/useChallengeSubmission';
import { useObstacle } from '../../../hooks/useObstacle';
import { safeStr } from '../../../utils/safeStr';
import { tokens } from '../../../design/tokens';

export const ChallengeDetailView: React.FC = () => {
  const {
    challenge, answer, setAnswer, submitting, handleSubmit,
    currentChallengeId, setChallengeId, t, locale
  } = useChallengeSubmission();
  const textareaRef = useObstacle() as React.RefObject<HTMLTextAreaElement>;

  const obstacles = useMemo(() => [
    { id: 'folio-meta', x: 750, y: 50, w: 250, h: 400 },
    { id: 'transcription', x: 0, y: 450, w: 700, h: 300 },
  ], []);

  const liveManuscriptText = useMemo(() => {
    const core = (safeStr(challenge.title).toUpperCase() + '. ' + t('challengeDetail.body') + ' ' + t('challengeDetail.marginalia') + ' ').repeat(2);
    const signature = answer ? ` [ ${t('challengeDetail.v2.signature_echo')}: ${answer} ] ` : '';
    return core + signature.repeat(3);
  }, [challenge.title, t, answer]);

  if (!currentChallengeId) return null;

  return (
    <div className="v2-challenge-detail" style={{
      minHeight: '100vh',
      background: tokens.colors.manuscript.bg,
      color: tokens.colors.manuscript.ink,
      padding: '4rem',
      fontFamily: tokens.fonts.manuscript,
      position: 'relative',
      overflowX: 'hidden'
    }}>

      {/* HEADER RAIL */}
      <div style={{ maxWidth: '1000px', margin: '0 auto', display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4rem', borderBottom: '1px solid rgba(0,0,0,0.1)', paddingBottom: '1rem' }}>
        <PretextButton
          className="challenge-v2-back"
          config={{
            label: t('challengeDetail.v2.back'),
            engine: 'labyrinth',
            physicsLineIndex: 6,
            soloistId: 'challenge-v2-back',
            color: tokens.colors.manuscript.dim,
            onTrigger: () => setChallengeId(null),
          }}
          style={{ color: tokens.colors.manuscript.dim, display: 'inline-flex', alignItems: 'center', gap: '0.5rem', fontFamily: tokens.fonts.mono, fontSize: tokens.sizes.small, textTransform: 'uppercase', transition: 'transform 180ms ease, color 180ms ease, text-shadow 180ms ease' }}
        >
          <ArrowLeft size={14} /> {t('challengeDetail.v2.back')}
        </PretextButton>
        <div style={{ fontFamily: tokens.fonts.mono, fontSize: tokens.sizes.small, color: tokens.colors.manuscript.dim }}>
          {t('challengeDetail.v2.codex_ref')}: {challenge.id} // {t('challengeDetail.v2.sec_level')}: {challenge.difficulty}
        </div>
      </div>

      <div style={{ maxWidth: '1000px', margin: '0 auto', position: 'relative' }}>
        <div style={{ position: 'relative', minHeight: '800px' }}>
          <ManuscriptPhysic
            text={liveManuscriptText}
            obstacles={obstacles}
            width={1000}
            lineHeight={locale === 'zh-CN' ? 40 : 36}
            fontDef={locale === 'zh-CN' ? `500 20px ${tokens.fonts.body}` : `500 22px ${tokens.fonts.manuscript}`}
          />

          {/* FOLIO BLOCK */}
          <div style={{
            position: 'absolute',
            left: obstacles[0].x,
            top: obstacles[0].y,
            width: obstacles[0].w,
            padding: '2rem',
            border: '1px solid rgba(0,0,0,0.1)',
            background: '#fff',
            boxShadow: '0 4px 20px rgba(0,0,0,0.05)',
            zIndex: 10
          }}>
            <h4 style={{ fontFamily: tokens.fonts.mono, fontSize: tokens.sizes.small, color: tokens.colors.manuscript.dim, marginBottom: '1rem' }}>{t('challengeDetail.v2.foliation_data')}</h4>
            <div style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '2rem' }}>{challenge.title}</div>
            <div style={{ marginBottom: '2rem' }}>
              <span style={{ fontFamily: tokens.fonts.mono, fontSize: tokens.sizes.small, color: tokens.colors.manuscript.muted }}>{t('challengeDetail.v2.xp_value')}</span>
              <div style={{ fontSize: '2rem', fontWeight: 700 }}>{challenge.points}</div>
            </div>
            <div style={{ fontSize: '0.8rem', color: '#666', lineHeight: 1.6, fontStyle: 'italic' }}>
              "{t('challengeDetail.subtitle')}"
            </div>
          </div>

          {/* TRANSCRIPTION AREA */}
          <div style={{
            position: 'absolute',
            left: obstacles[1].x,
            top: obstacles[1].y,
            width: obstacles[1].w,
            zIndex: 10,
            background: 'rgba(253, 252, 240, 0.8)',
            backdropFilter: 'blur(4px)',
            padding: '2rem',
            borderLeft: `4px solid ${tokens.colors.manuscript.ink}`
          }}>
            <h3 style={{ fontFamily: tokens.fonts.mono, fontSize: '12px', color: tokens.colors.manuscript.dim, textTransform: 'uppercase', marginBottom: '1rem' }}>{t('challengeDetail.v2.transcription_active')}</h3>
            <textarea
              ref={textareaRef}
              data-obstacle-id="challenge-v2-textarea"
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              placeholder={t('challengeDetail.v2.input_placeholder')}
              style={{
                width: '100%',
                height: '100px',
                background: 'transparent',
                border: 'none',
                fontSize: '1.5rem',
                fontFamily: tokens.fonts.body,
                padding: '0',
                outline: 'none',
                resize: 'none',
                color: tokens.colors.manuscript.ink,
                borderBottom: '1px dashed #ccc'
              }}
            />
            <PretextButton
              className="challenge-v2-submit"
              config={{
                label: submitting ? t('challengeDetail.v2.submitting') : t('challengeDetail.v2.submit'),
                engine: 'labyrinth',
                physicsLineIndex: 20,
                soloistId: 'challenge-v2-submit',
                color: tokens.colors.manuscript.ink,
                onTrigger: handleSubmit,
              }}
              data-obstacle-id="challenge-v2-submit"
              disabled={submitting || !answer.trim()}
              style={{
                marginTop: '1.5rem',
                background: tokens.colors.manuscript.ink,
                color: '#fff',
                padding: '0.75rem 2rem',
                border: 'none',
                cursor: 'pointer',
                fontFamily: tokens.fonts.body,
                display: 'flex',
                alignItems: 'center',
                gap: '0.75rem',
                opacity: submitting ? 0.5 : 1,
                fontSize: tokens.sizes.small,
                fontWeight: 700,
                letterSpacing: '0.1em',
                textTransform: 'uppercase',
                textDecoration: 'none',
                transition: 'transform 180ms ease, opacity 180ms ease, box-shadow 180ms ease'
              }}
            >
              <Edit3 size={16} /> {submitting ? t('challengeDetail.v2.submitting') : t('challengeDetail.v2.submit')}
            </PretextButton>
          </div>
        </div>
      </div>
      <style>{`
        .challenge-v2-back:hover,
        .challenge-v2-back:focus-visible {
          color: ${tokens.colors.manuscript.ink} !important;
          transform: translateX(-2px);
          text-shadow: 0 0 10px rgba(26, 26, 26, 0.18);
        }

        .challenge-v2-back:active {
          transform: translateX(-4px) scale(0.98);
        }

        .challenge-v2-submit:hover:not(:disabled),
        .challenge-v2-submit:focus-visible:not(:disabled) {
          transform: translateY(-1px);
          box-shadow: 0 8px 18px rgba(26, 26, 26, 0.18);
        }

        .challenge-v2-submit:active:not(:disabled) {
          transform: translateY(1px) scale(0.98);
        }
      `}</style>
    </div>
  );
};
