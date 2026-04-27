import React, { useCallback, useEffect, useMemo, useRef } from 'react';
import { Navigation } from '../components/Navigation';
import { AuroraEngine } from '../components/AuroraEngine';
import { useArena } from '../context/ArenaContext';
import { useLanguage } from '../context/LanguageContext';
import { motion, AnimatePresence } from 'framer-motion';
import { tokens } from '../design/tokens';

interface MainLayoutProps {
  children: React.ReactNode;
}

import { LabyrinthPhysic } from '../components/text-physics/LabyrinthPhysic';
import { BitmaskPhysic } from '../components/text-physics/BitmaskPhysic';
import { TextVariantSwitcher } from '../components/TextVariantSwitcher';
import { usePhysicsRegistry } from '../context/PhysicsContext';

/**
 * MainLayout: The product architectural master.
 */
export const MainLayout: React.FC<MainLayoutProps> = ({ children }) => {
  const { currentView, setView, isLoading, toast, variant, setVariant, isZenMode, setZenMode, showToast, isNavVisible } = useArena();
  const { t, locale } = useLanguage();
  const { environment, setEnvironment } = usePhysicsRegistry();
  const [isBlueprintMode, setBlueprintMode] = React.useState(false);
  const [isAlignmentMode, setAlignmentMode] = React.useState(false);
  const variantRef = useRef(variant);
  const transitionFrameRef = useRef<number | null>(null);

  useEffect(() => {
    variantRef.current = variant;
  }, [variant]);

  useEffect(() => {
    return () => {
      if (transitionFrameRef.current !== null) cancelAnimationFrame(transitionFrameRef.current);
    };
  }, []);

  const handleOpenSettings = () => {
  };

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.repeat) return;
      const target = e.target as HTMLElement;
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable) {
        return;
      }

      if (e.key.toLowerCase() === 'z') {
        const next = !isZenMode;
        setZenMode(next);
        setEnvironment(next ? { waveAmplitude: 90, opacity: 0.3 } : { waveAmplitude: 60, opacity: 0.15 });
        showToast(next ? 'ZEN_MODE_ACTIVATED' : 'UI_RESTORED', 'success');
      }
      if (e.key.toLowerCase() === 'd') {
        const nextBlueprintMode = !isBlueprintMode;
        setBlueprintMode(nextBlueprintMode);
        showToast(nextBlueprintMode ? 'BLUEPRINT_MODE_ACTIVE' : 'BLUEPRINT_MODE_DISABLED', 'success');
      }
      if (e.key.toLowerCase() === 'l') {
        const next = !isAlignmentMode;
        setAlignmentMode(next);
        setEnvironment({ debugAlignment: next });
        showToast(next ? 'ALIGNMENT_LINES_ON' : 'ALIGNMENT_LINES_OFF', 'success');
      }
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [isZenMode, isBlueprintMode, isAlignmentMode, setZenMode, setEnvironment, showToast]);

  const labyrinthText = useMemo(() => {
    const source = variant === 'v2'
      ? t('home.v2.background_field')
      : `${t('home.manifesto')} ${t('watch.chorus')}`;
    return `${source} `.repeat(10);
  }, [t, variant]);

  const themeColors = useMemo(() => {
    if (variant === 'v2') {
      return {
        base: '#fdfcf0',
        text: '#1a1a1a',
        accent: tokens.colors.aurora.purple
      };
    }
    return {
      base: tokens.colors.base,
      text: tokens.colors.text.primary,
      accent: tokens.colors.aurora.blue
    };
  }, [variant]);

  const handleVariantChange = useCallback((nextVariant: typeof variant) => {
    const fromVariant = variantRef.current;
    if (fromVariant === nextVariant) return;

    if (transitionFrameRef.current !== null) {
      cancelAnimationFrame(transitionFrameRef.current);
      transitionFrameRef.current = null;
    }

    const duration = 1500;
    const startedAt = performance.now();
    setEnvironment({
      waveAmplitude: 150,
      effects: {
        transitionFrom: fromVariant,
        transitionProgress: 0,
      },
    });
    setVariant(nextVariant);

    const step = (now: number) => {
      const p = Math.min(1, (now - startedAt) / duration);
      setEnvironment({
        waveAmplitude: 150 - p * 90,
        effects: {
          transitionFrom: p >= 1 ? null : fromVariant,
          transitionProgress: p >= 1 ? 0 : p,
        },
      });

      if (p < 1) {
        transitionFrameRef.current = requestAnimationFrame(step);
      } else {
        transitionFrameRef.current = null;
      }
    };

    transitionFrameRef.current = requestAnimationFrame(step);
  }, [setEnvironment, setVariant, variant]);

  const transition = environment.effects;
  const isTransitioning = !!transition?.transitionFrom && (transition.transitionProgress ?? 0) > 0;
  const showBitmask = variant === 'v3' || (isTransitioning && transition?.transitionFrom === 'v3');
  const showLabyrinth = variant === 'v2' || (isTransitioning && transition?.transitionFrom === 'v2');
  const labyrinthVariant = variant === 'v2' ? 'v2' : (transition?.transitionFrom === 'v2' ? 'v2' : variant);

  return (
    <div className={`product-root ${isBlueprintMode ? 'blueprint-mode' : ''}`} style={{ 
      position: 'relative', 
      minHeight: '100vh', 
      overflow: 'hidden', 
      background: themeColors.base,
      color: themeColors.text,
      transition: `background 1.5s ${tokens.transitions.easing}, color 1.5s ${tokens.transitions.easing}`
    }}>
      
      {/* PLANE 0: BACKGROUND (aurora + noise) */}
      <div className="plane-background" style={{ position: 'fixed', inset: 0, zIndex: 0 }}>
        <AuroraEngine />
        <div className="pointer-events-none absolute inset-0 z-0 opacity-[0.02] mix-blend-overlay"
             style={{ backgroundImage: tokens.effects.noise }} />
      </div>

      {/* PLANE 1: PHYSICS FIELD (above background, below content) */}
      <div className="plane-physics" style={{ position: 'fixed', inset: 0, zIndex: 1, pointerEvents: 'none' }}>
        {showBitmask && (
          <BitmaskPhysic opacity={isZenMode ? 0.3 : 0.25} />
        )}
        {showLabyrinth && (
          <LabyrinthPhysic
            text={labyrinthText}
            fontDef={locale === 'zh-CN' ? "400 8px 'Noto Sans SC'" : "400 9px Satoshi"}
            lineHeight={locale === 'zh-CN' ? 12 : 10}
            opacity={isZenMode ? 0.12 : 0.06}
            variant={labyrinthVariant}
          />
        )}
      </div>

      {/* PLANE 1.5: INTERACTION (ENGINEER E STAGE) */}
      <div
        className="plane-interaction"
        id="global-interaction-plane"
        style={{ position: 'fixed', inset: 0, zIndex: 1, pointerEvents: 'none' }}
      ></div>

      {/* PLANE 3: CONTENT */}
      <main className="plane-content" style={{
        position: 'relative',
        zIndex: 2,
        paddingTop: '1rem',
        paddingLeft: variant === 'v3' ? 0 : '4rem',
        paddingRight: variant === 'v3' ? 0 : '4rem',
        opacity: isZenMode ? 0.05 : 1,
        transition: `opacity 0.8s ${tokens.transitions.easing}`,
        pointerEvents: isZenMode ? 'none' : 'auto',
        background: 'transparent'
      }}>
        <div style={{ opacity: isZenMode ? 0 : 1, transition: 'opacity 0.5s ease' }}>
          {isNavVisible && (
            <Navigation 
              currentView={currentView} 
              onViewChange={setView} 
              onOpenSettings={handleOpenSettings}
            />
          )}
        </div>
        
        <AnimatePresence>
          {isLoading && (
            <motion.div 
              className="layout-loading-chip"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              style={{
                position: 'fixed',
                bottom: '3rem',
                right: '3rem',
                zIndex: 100,
                background: 'none',
                padding: '0.6rem 1.25rem',
                display: 'flex',
                alignItems: 'center',
                gap: '1rem'
              }}
            >
              <span style={{ 
                fontFamily: tokens.fonts.mono, 
                fontSize: '10px', 
                color: tokens.colors.aurora.blue,
                letterSpacing: '0.15em',
                fontWeight: 700
              }}>
                [ SYNCING_RIFT ]
              </span>
            </motion.div>
          )}
        </AnimatePresence>
 
        <div id="view-mount" className="view-transition-wrapper" data-module="content-stage">
          {children}
        </div>
 
        <footer data-module="footer" style={{ 
          marginTop: '10rem', 
          padding: '4rem 0', 
          textAlign: 'center', 
          color: tokens.colors.text.tertiary, 
          fontFamily: tokens.fonts.mono, 
          fontSize: '9px', 
          letterSpacing: '0.4em',
          opacity: 0.2
        }}>
          {t('common.footer.copyright')}
        </footer>
      </main>

      {/* PLANE 4: OVERLAY (Toasts, TextVariantSwitcher) */}
      <div className="plane-overlay" style={{ position: 'fixed', inset: 0, zIndex: 10, pointerEvents: 'none' }}>
        <TextVariantSwitcher isZenMode={isZenMode} variant={variant} onVariantChange={handleVariantChange} />
        
        <AnimatePresence>
          {toast && (
            <motion.div
              className="layout-toast"
              initial={{ opacity: 0, y: 30, x: '-50%' }}
              animate={{ opacity: 1, y: 0, x: '-50%' }}
              exit={{ opacity: 0, y: -20, x: '-50%' }}
              style={{
                position: 'fixed',
                bottom: '100px',
                left: '50%',
                zIndex: 1000,
                pointerEvents: 'auto',
                color: 'white',
                fontFamily: tokens.fonts.mono,
                fontSize: '11px',
                fontWeight: 900,
                letterSpacing: '0.2em',
                textTransform: 'uppercase'
              }}
            >
              <div style={{ 
                maxWidth: '100%',
                display: 'flex', 
                alignItems: 'center', 
                gap: '1.5rem', 
                padding: '1rem 2rem',
                borderBottom: `2px solid ${toast.type === 'error' ? tokens.colors.aurora.red : tokens.colors.aurora.cyan}`
              }}>
                <div style={{ width: '4px', height: '4px', borderRadius: '50%', background: 'white' }} className="pulse-slow" />
                <span>[ {toast.type.toUpperCase()} ] {toast.msg}</span>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <style>{`
        .view-transition-wrapper {
          animation: page-slide-up 1.2s ${tokens.transitions.easing};
        }
        @keyframes page-slide-up {
          from { opacity: 0; transform: translateY(30px); filter: blur(20px); }
          to { opacity: 1; transform: translateY(0); filter: blur(0); }
        }
        
        .pulse-slow {
          animation: pulse-op 3s infinite;
        }
        @keyframes pulse-op {
          0% { opacity: 0.4; }
          50% { opacity: 1; }
          100% { opacity: 0.4; }
        }

        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 10px; }
        ::-webkit-scrollbar-thumb:hover { background: ${tokens.colors.aurora.blue}; }

        @media (max-width: 768px) {
          .plane-content {
            padding-left: 1rem !important;
            padding-right: 1rem !important;
          }
          .layout-loading-chip {
            bottom: 1rem !important;
            right: 1rem !important;
          }
          footer[data-module="footer"] {
            margin-top: 4rem !important;
            padding: 2rem 0 !important;
          }
          .layout-toast {
            max-width: calc(100vw - 2rem) !important;
            width: max-content;
            letter-spacing: 0.08em !important;
          }
          .layout-toast > div {
            gap: 0.75rem !important;
            padding: 0.75rem 1rem !important;
          }
        }
      `}</style>
    </div>
  );
};
