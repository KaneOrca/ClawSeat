import React, { useMemo } from 'react';
import { ArrowLeft, Edit3 } from 'lucide-react';
import { PretextButton } from '../../../components/PretextButton';
import { ManuscriptPhysic } from '../../../components/text-physics/ManuscriptPhysic';
import { useChallengeSubmission } from '../../../hooks/useChallengeSubmission';
import { safeStr } from '../../../utils/safeStr';

export const ChallengeDetailView: React.FC = () => {
  const {
    challenge, answer, setAnswer, submitting, handleSubmit,
    currentChallengeId, setChallengeId, t, locale
  } = useChallengeSubmission();

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
      background: '#fdfcf0',
      color: '#1a1a1a',
      padding: '4rem',
      fontFamily: "'Playfair Display', serif",
      position: 'relative',
      overflowX: 'hidden'
    }}>

      {/* HEADER RAIL */}
      <div style={{ maxWidth: '1000px', margin: '0 auto', display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4rem', borderBottom: '1px solid rgba(0,0,0,0.1)', paddingBottom: '1rem' }}>
        <PretextButton
          config={{
            label: t('challengeDetail.v2.back'),
            engine: 'labyrinth',
            physicsLineIndex: 6,
            soloistId: 'challenge-v2-back',
            color: '#888',
            onTrigger: () => setChallengeId(null),
          }}
          style={{ color: '#888', display: 'inline-flex', alignItems: 'center', gap: '0.5rem', fontFamily: 'IBM Plex Mono', fontSize: '11px', textTransform: 'uppercase' }}
        >
          <ArrowLeft size={14} /> {t('challengeDetail.v2.back')}
        </PretextButton>
        <div style={{ fontFamily: 'IBM Plex Mono', fontSize: '11px', color: '#888' }}>
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
            fontDef={locale === 'zh-CN' ? "500 20px 'Noto Sans SC'" : "500 22px 'Playfair Display'"}
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
            <h4 style={{ fontFamily: 'IBM Plex Mono', fontSize: '11px', color: '#888', marginBottom: '1rem' }}>{t('challengeDetail.v2.foliation_data')}</h4>
            <div style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '2rem' }}>{challenge.title}</div>
            <div style={{ marginBottom: '2rem' }}>
              <span style={{ fontFamily: 'IBM Plex Mono', fontSize: '11px', color: '#aaa' }}>{t('challengeDetail.v2.xp_value')}</span>
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
            borderLeft: '4px solid #1a1a1a'
          }}>
            <h3 style={{ fontFamily: 'IBM Plex Mono', fontSize: '12px', color: '#888', textTransform: 'uppercase', marginBottom: '1rem' }}>{t('challengeDetail.v2.transcription_active')}</h3>
            <textarea
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              placeholder={t('challengeDetail.v2.input_placeholder')}
              style={{
                width: '100%',
                height: '100px',
                background: 'transparent',
                border: 'none',
                fontSize: '1.5rem',
                fontFamily: 'Satoshi, sans-serif',
                padding: '0',
                outline: 'none',
                resize: 'none',
                color: '#1a1a1a',
                borderBottom: '1px dashed #ccc'
              }}
            />
            <button
              onClick={handleSubmit}
              disabled={submitting || !answer.trim()}
              style={{
                marginTop: '1.5rem',
                background: '#1a1a1a',
                color: '#fff',
                padding: '0.75rem 2rem',
                border: 'none',
                cursor: 'pointer',
                fontFamily: 'Satoshi, sans-serif',
                display: 'flex',
                alignItems: 'center',
                gap: '0.75rem',
                opacity: submitting ? 0.5 : 1,
                fontSize: '11px',
                fontWeight: 700,
                letterSpacing: '0.1em',
                textTransform: 'uppercase'
              }}
            >
              <Edit3 size={16} /> {submitting ? t('challengeDetail.v2.submitting') : t('challengeDetail.v2.submit')}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
