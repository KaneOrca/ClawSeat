import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { NeuralBadge } from '../../../design/VisualPrimitive';
import { useArena, type ViewType } from '../../../context/ArenaContext';
import { usePhysicsRegistry } from '../../../context/PhysicsContext';
import { useObstacle } from '../../../hooks/useObstacle';
import { useHomeInit } from '../../../hooks/useHomeInit';
import { PretextButton } from '../../../components/PretextButton';
import { tokens } from '../../../design/tokens';

const MANUSCRIPT_ACTIVE_RED = tokens.colors.manuscript.red;

const V2_CONFIG = {
  soloistId: 'v2-home-title',
  lineIndex: 10,
  color: tokens.colors.manuscript.ink,
  opacity: 0.8,
  environment: { waveAmplitude: 0, ambientColor: 'rgba(26, 26, 26, 0.4)', opacity: 0.3 },
  zenEnvironment: { waveAmplitude: 90, ambientColor: 'rgba(26, 26, 26, 0.4)', opacity: 0.6 },
  cleanupEnvironment: { ambientColor: undefined },
} as const;

const TERM_NAV = [
  { id: 'neural-rift', labelKey: 'home.v2.term_neural_rift', lineIndex: 17, view: 'watch', route: '/watch' },
  { id: 'explore', labelKey: 'home.v2.term_explore', lineIndex: 21, view: 'hall', route: '/hall' },
  { id: 'join', labelKey: 'home.v2.term_join', lineIndex: 25, route: '/auth' },
] as const;

type HomeTerm = typeof TERM_NAV[number];
type FieldState = 'FIELD_IDLE' | 'TERM_SOLOIST_ACTIVE' | 'SOLOIST_PULSE_NAV';

export const HomeView: React.FC = () => {
  const { onInitialize, user, isZenMode, t } = useHomeInit(V2_CONFIG);
  const { setView, showToast } = useArena();
  const { setEnvironment } = usePhysicsRegistry();
  const marginalia01Ref = useObstacle() as React.RefObject<HTMLDivElement>;
  const marginalia02Ref = useObstacle() as React.RefObject<HTMLDivElement>;
  const introProseRef = useObstacle() as React.RefObject<HTMLParagraphElement>;
  const timeoutRef = useRef<number | null>(null);
  const [fieldState, setFieldState] = useState<FieldState>('FIELD_IDLE');
  const [activeTermId, setActiveTermId] = useState<HomeTerm['id'] | null>(null);

  const resetHomeEnvironment = useCallback(() => {
    const env = isZenMode ? V2_CONFIG.zenEnvironment : V2_CONFIG.environment;
    setEnvironment(env);
  }, [isZenMode, setEnvironment]);

  const unregisterTerms = useCallback(() => {
    // legacy soloist cleanup was removed; keep env-level cleanup centralized
  }, []);

  useEffect(() => {
    return () => {
      if (timeoutRef.current !== null) window.clearTimeout(timeoutRef.current);
      unregisterTerms();
    };
  }, [unregisterTerms]);

  const handleTermEnter = useCallback((term: HomeTerm) => {
    unregisterTerms();
    setActiveTermId(term.id);
    setFieldState('TERM_SOLOIST_ACTIVE');
    setEnvironment({
      waveAmplitude: 92,
      opacity: 0.22,
      ambientColor: 'rgba(181, 48, 33, 0.24)',
    });
  }, [setEnvironment, unregisterTerms]);

  const handleTermLeave = useCallback(() => {
    if (fieldState === 'SOLOIST_PULSE_NAV') return;
    setActiveTermId(null);
    setFieldState('FIELD_IDLE');
    resetHomeEnvironment();
  }, [fieldState, resetHomeEnvironment]);

  const handleTermClick = useCallback((term: HomeTerm) => {
    if (timeoutRef.current !== null) window.clearTimeout(timeoutRef.current);
    setActiveTermId(term.id);
    setFieldState('SOLOIST_PULSE_NAV');
    setEnvironment({
      waveAmplitude: 124,
      opacity: 0.28,
      ambientColor: 'rgba(181, 48, 33, 0.3)',
    });
    showToast(`[ SOLOIST_PULSE_NAV :: ${term.route} ]`, 'success');

    timeoutRef.current = window.setTimeout(() => {
      if ('view' in term && (term.view !== 'hall' || user)) {
        setView(term.view as ViewType);
      } else {
        onInitialize();
      }
      setFieldState('FIELD_IDLE');
      setActiveTermId(null);
      unregisterTerms();
      resetHomeEnvironment();
    }, 320);
  }, [onInitialize, resetHomeEnvironment, setEnvironment, setView, showToast, unregisterTerms, user]);

  const termsById = useMemo(() => {
    return TERM_NAV.reduce<Record<HomeTerm['id'], HomeTerm>>((acc, term) => {
      acc[term.id] = term;
      return acc;
    }, {} as Record<HomeTerm['id'], HomeTerm>);
  }, []);

  return (
    <div className="v2-home" style={{
      position: 'relative',
      minHeight: 'calc(100vh - 2rem)',
      background: 'transparent',
      color: 'inherit',
      padding: 'clamp(1.5rem, 6vw, 5rem) 0',
      fontFamily: tokens.fonts.manuscript,
      overflow: 'auto'
    }}>

      <div
        style={{
          opacity: isZenMode ? 0.05 : 1,
          transition: 'opacity 0.8s ease',
          pointerEvents: isZenMode ? 'none' : 'auto'
        }}
      >
        <div style={{ position: 'relative', zIndex: 10 }}>
          {/* BLOCK 1 */}
          <div ref={marginalia01Ref} data-module="home-marginalia-01" style={{
            position: 'absolute',
            left: 'min(58vw, 760px)',
            top: 'clamp(3rem, 8vw, 7rem)',
            width: 'min(30vw, 340px)',
            padding: '1rem 0'
          }}>
            <h3 style={{ fontFamily: tokens.fonts.mono, fontSize: '9px', textTransform: 'uppercase', marginBottom: '0.5rem', color: tokens.colors.manuscript.dim, letterSpacing: '0.3em', fontWeight: 700 }}>{t('home.v2.marginalia_label')}</h3>
            <p style={{ fontSize: '0.9rem', lineHeight: 1.8, fontStyle: 'italic', color: tokens.colors.manuscript.faint }}>
              {t('home.marginalia')}
            </p>
          </div>

          {/* BLOCK 2 */}
          <div ref={marginalia02Ref} data-module="home-marginalia-02" style={{
            position: 'absolute',
            left: 0,
            top: 'clamp(26rem, 52vw, 34rem)',
            width: 'min(28vw, 300px)',
            padding: '1rem 0',
            textAlign: 'right'
          }}>
            <h3 style={{ fontFamily: tokens.fonts.mono, fontSize: '9px', textTransform: 'uppercase', marginBottom: '0.5rem', color: tokens.colors.manuscript.dim, letterSpacing: '0.3em', fontWeight: 700 }}>{t('home.v2.notes_label')}</h3>
            <p style={{ fontSize: '0.9rem', lineHeight: 1.8, fontStyle: 'italic', color: tokens.colors.manuscript.faint }}>
              {t('home.v2.notes')}
            </p>
          </div>

          {/* HERO HEADER */}
          <div data-module="home-hero" style={{
            position: 'relative',
            marginTop: 'clamp(4rem, 14vh, 9rem)',
            maxWidth: '780px',
            marginLeft: 'clamp(0rem, 14vw, 14rem)'
          }}>
            <NeuralBadge text={t('home.configs.v2')} color={tokens.colors.manuscript.muted} />

            <div data-module="home-title" style={{ height: '80px', pointerEvents: 'none', visibility: 'hidden' }} />

            <p
              ref={introProseRef}
              data-module="home-intro-prose"
              style={{
                margin: '2rem 0 0',
                fontSize: 'clamp(1.1rem, 2.4vw, 1.5rem)',
                lineHeight: 1.85,
                textAlign: 'justify',
                color: tokens.colors.manuscript.ink,
                maxWidth: '100%'
              }}
            >
              {t('home.v2.intro_before_rift')}
              <HomeKeyTerm
                active={activeTermId === 'neural-rift'}
                label={t(termsById['neural-rift'].labelKey)}
                term={termsById['neural-rift']}
                onEnter={handleTermEnter}
                onLeave={handleTermLeave}
                onClick={handleTermClick}
              />
              {t('home.v2.intro_after_rift')}
              <HomeKeyTerm
                active={activeTermId === 'explore'}
                label={t(termsById.explore.labelKey)}
                term={termsById.explore}
                onEnter={handleTermEnter}
                onLeave={handleTermLeave}
                onClick={handleTermClick}
              />
              {t('home.v2.intro_after_explore')}
              <HomeKeyTerm
                active={activeTermId === 'join'}
                label={t(termsById.join.labelKey)}
                term={termsById.join}
                onEnter={handleTermEnter}
                onLeave={handleTermLeave}
                onClick={handleTermClick}
              />
              {t('home.v2.intro_after_join')}
            </p>

            <PretextButton
              className="home-agent-prompt"
              config={{
                label: t('home.v2.agent_prompt.body'),
                engine: 'labyrinth',
                physicsLineIndex: 29,
                soloistId: 'v2-home-agent-prompt',
                color: MANUSCRIPT_ACTIVE_RED,
                opacity: 0.95,
                onTrigger: () => setView('auth'),
                activationEnvironment: {
                  waveAmplitude: 92,
                  opacity: 0.22,
                  ambientColor: 'rgba(181, 48, 33, 0.24)',
                },
                triggerEnvironment: {
                  waveAmplitude: 124,
                  opacity: 0.28,
                  ambientColor: 'rgba(181, 48, 33, 0.3)',
                },
                idleEnvironment: isZenMode ? V2_CONFIG.zenEnvironment : V2_CONFIG.environment,
              }}
              style={{
                display: 'block',
                marginTop: 'clamp(2.5rem, 6vh, 4.5rem)',
                maxWidth: 'min(680px, 100%)',
                color: MANUSCRIPT_ACTIVE_RED,
                fontFamily: tokens.fonts.manuscript,
                fontSize: 'clamp(1rem, 2.1vw, 1.35rem)',
                fontStyle: 'italic',
                fontWeight: 500,
                lineHeight: 2.05,
                textAlign: 'left',
                textDecoration: 'none',
                whiteSpace: 'pre-line',
              }}
            />

            <div style={{ marginTop: '8vh', fontFamily: tokens.fonts.mono, fontSize: tokens.sizes.xs, opacity: 0.4, lineHeight: 2.2, letterSpacing: '0.05em' }}>
              {t('home.v2.status_label')}: {fieldState}<br />
              {t('home.v2.route_label')}: {activeTermId ? TERM_NAV.find(term => term.id === activeTermId)?.route : '--'}<br />
              {t('home.v2.location_label')}: {t('home.v2.location_value')}<br />
              {t('home.v2.era_label')}: {t('home.v2.era_value')}
            </div>
          </div>
        </div>
      </div>

      <style>{`
        .home-key-term {
          color: ${MANUSCRIPT_ACTIVE_RED};
          cursor: pointer;
          display: inline-block;
          font-weight: 700;
          text-decoration: underline;
          text-decoration-thickness: 1px;
          text-underline-offset: 4px;
          transition: color 0.3s ease, transform 0.3s cubic-bezier(0.16, 1, 0.3, 1), text-shadow 0.3s ease;
        }
        .home-key-term:hover,
        .home-key-term[data-active="true"] {
          transform: scale(1.08);
          text-shadow: 0 0 10px rgba(181, 48, 33, 0.32);
        }
        @media (max-width: 768px) {
          .v2-home {
            padding: 1rem 0 !important;
          }
          .v2-home [data-module="home-hero"] {
            order: 1;
            margin-top: 5vh !important;
            margin-left: 0 !important;
            max-width: 100% !important;
          }
          .v2-home [data-module="home-marginalia-01"],
          .v2-home [data-module="home-marginalia-02"] {
            position: static !important;
            left: auto !important;
            top: auto !important;
            width: auto !important;
            display: block;
            margin-top: 2rem;
            text-align: left !important;
            order: 2;
          }
          .v2-home [data-module="home-marginalia-02"] {
            order: 3;
          }
          .v2-home [data-module="home-hero"] + * {
            margin-top: 2rem;
          }
          .v2-home [data-module="home-intro-prose"] {
            font-size: 18px !important;
            line-height: 1.65 !important;
            text-align: left !important;
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

const HomeKeyTerm: React.FC<{
  active: boolean;
  label: string;
  term: HomeTerm;
  onEnter: (term: HomeTerm) => void;
  onLeave: () => void;
  onClick: (term: HomeTerm) => void;
}> = ({ active, label, term, onEnter, onLeave, onClick }) => {
  const termRef = useObstacle() as React.RefObject<HTMLButtonElement>;

  return (
    <button
      ref={termRef}
      className="home-key-term"
      data-nav={term.id}
      data-active={active}
      onMouseEnter={() => onEnter(term)}
      onMouseLeave={onLeave}
      onFocus={() => onEnter(term)}
      onBlur={onLeave}
      onClick={() => onClick(term)}
      style={{
        appearance: 'none',
        background: 'none',
        border: 0,
        borderRadius: 0,
        color: MANUSCRIPT_ACTIVE_RED,
        font: 'inherit',
        padding: '0 0.08em',
      }}
      type="button"
    >
      {label}
    </button>
  );
};
