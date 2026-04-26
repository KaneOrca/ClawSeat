import React, { useMemo } from 'react';
import { NeuralBadge } from '../../../design/VisualPrimitive';
import { useObstacle } from '../../../hooks/useObstacle';
import { useHomeInit } from '../../../hooks/useHomeInit';

const V2_CONFIG = {
  soloistId: 'v2-home-title',
  lineIndex: 10,
  color: '#1a1a1a',
  opacity: 0.8,
  environment: { waveAmplitude: 0, ambientColor: 'rgba(26, 26, 26, 0.4)', opacity: 0.3 },
  zenEnvironment: { waveAmplitude: 90, ambientColor: 'rgba(26, 26, 26, 0.4)', opacity: 0.6 },
  cleanupEnvironment: { ambientColor: undefined },
} as const;

export const HomeView: React.FC = () => {
  const { onInitialize, user, isZenMode, t } = useHomeInit(V2_CONFIG);
  const obstacleRef = useObstacle();

  const obstacles = useMemo(() => [
    { id: 'annot-1', x: 800, y: 100, w: 350, h: 250 },
    { id: 'annot-2', x: 50, y: 450, w: 300, h: 200 },
  ], []);

  return (
    <div className="v2-home" style={{
      position: 'relative',
      minHeight: '100vh',
      background: 'transparent',
      color: 'inherit',
      padding: '4rem',
      fontFamily: "'Playfair Display', serif",
      overflow: 'auto'
    }}>

      <div
        style={{
          opacity: isZenMode ? 0.05 : 1,
          transition: 'opacity 0.8s ease',
          pointerEvents: isZenMode ? 'none' : 'auto'
        }}
      >
        <div
          ref={obstacleRef as any}
          style={{ position: 'relative', zIndex: 10 }}
        >
          {/* BLOCK 1 */}
          <div data-module="marginalia-01" style={{
            position: 'absolute',
            left: obstacles[0].x,
            top: obstacles[0].y,
            width: obstacles[0].w,
            padding: '1rem 0'
          }}>
            <h3 style={{ fontFamily: 'IBM Plex Mono', fontSize: '9px', textTransform: 'uppercase', marginBottom: '0.5rem', color: '#888', letterSpacing: '0.3em', fontWeight: 700 }}>{t('home.v2.marginalia_label')}</h3>
            <p style={{ fontSize: '0.9rem', lineHeight: 1.8, fontStyle: 'italic', color: '#555' }}>
              {t('home.marginalia')}
            </p>
          </div>

          {/* BLOCK 2 */}
          <div data-module="marginalia-02" style={{
            position: 'absolute',
            left: obstacles[1].x,
            top: obstacles[1].y,
            width: obstacles[1].w,
            padding: '1rem 0',
            textAlign: 'right'
          }}>
            <h3 style={{ fontFamily: 'IBM Plex Mono', fontSize: '9px', textTransform: 'uppercase', marginBottom: '0.5rem', color: '#888', letterSpacing: '0.3em', fontWeight: 700 }}>{t('home.v2.notes_label')}</h3>
            <p style={{ fontSize: '0.9rem', lineHeight: 1.8, fontStyle: 'italic', color: '#555' }}>
              {t('home.v2.notes')}
            </p>
          </div>

          {/* HERO HEADER */}
          <div data-module="home-hero" style={{
            position: 'relative',
            marginTop: '20vh',
            maxWidth: '600px',
            marginLeft: '15vw'
          }}>
            <NeuralBadge text={t('home.configs.v2')} color="#aaa" />

            <div data-module="home-title" style={{ height: '80px', pointerEvents: 'none', visibility: 'hidden' }} />

            <div style={{ marginTop: '2rem' }}>
              <button
                onClick={onInitialize}
                className="btn-manuscript"
                style={{
                  background: 'none',
                  color: 'inherit',
                  padding: '1rem 0',
                  border: 'none',
                  borderBottom: '2px solid currentColor',
                  fontSize: '0.9rem',
                  cursor: 'pointer',
                  fontFamily: 'Satoshi, sans-serif',
                  letterSpacing: '0.2em',
                  textTransform: 'uppercase',
                  fontWeight: 700,
                  transition: 'all 0.3s ease'
                }}
              >
                [ {user ? t('home.v2.cta_rejoin') : t('home.cta')} ]
              </button>
            </div>

            <div style={{ marginTop: '8vh', fontFamily: 'IBM Plex Mono', fontSize: '10px', opacity: 0.4, lineHeight: 2.2, letterSpacing: '0.05em' }}>
              {t('home.v2.status_label')}: {t('home.status.loading').toUpperCase()}<br />
              {t('home.v2.location_label')}: {t('home.v2.location_value')}<br />
              {t('home.v2.era_label')}: {t('home.v2.era_value')}
            </div>
          </div>
        </div>
      </div>

      <style>{`
        .btn-manuscript:hover {
          letter-spacing: 0.3em;
          opacity: 0.7;
        }
        @media (max-width: 768px) {
          .v2-home {
            padding: 1rem !important;
          }
          .v2-home [data-module="home-hero"] {
            order: 1;
            margin-top: 5vh !important;
            margin-left: 0 !important;
            max-width: 100% !important;
          }
          .v2-home [data-module="marginalia-01"],
          .v2-home [data-module="marginalia-02"] {
            position: static !important;
            left: auto !important;
            top: auto !important;
            width: auto !important;
            display: block;
            margin-top: 2rem;
            text-align: left !important;
            order: 2;
          }
          .v2-home [data-module="marginalia-02"] {
            order: 3;
          }
          .v2-home [data-module="home-hero"] + * {
            margin-top: 2rem;
          }
          .v2-home > div > div {
            display: flex;
            flex-direction: column;
          }
        }
      `}</style>
    </div>
  );
};
