import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Settings, Globe, Palette, X } from 'lucide-react';

interface SettingsShellProps {
  isOpen: boolean;
  onClose: () => void;
  lang: 'en' | 'zh';
  setLang: (l: 'en' | 'zh') => void;
  theme: 'dark' | 'light' | 'steampunk';
  setTheme: (t: 'dark' | 'light' | 'steampunk') => void;
}

export const SettingsShell: React.FC<SettingsShellProps> = ({
  isOpen,
  onClose,
  lang,
  setLang,
  theme,
  setTheme
}) => {
  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            style={{
              position: 'fixed',
              inset: 0,
              background: 'radial-gradient(circle at 50% 50%, rgba(20,20,20,0.4) 0%, rgba(0,0,0,0.8) 100%)',
              backdropFilter: 'blur(30px)',
              zIndex: 100
            }}
          />
          <motion.div
            className="settings-shell-panel"
            initial={{ opacity: 0, x: '-50%', y: '-48%' }}
            animate={{ opacity: 1, x: '-50%', y: '-50%' }}
            exit={{ opacity: 0, x: '-50%', y: '-48%' }}
            style={{
              position: 'fixed',
              left: '50%',
              top: '50%',
              width: '100%',
              maxWidth: '500px',
              zIndex: 101,
              background: 'none',
              padding: '4rem',
              pointerEvents: 'auto'
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '3rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <Settings size={20} color="var(--aurora-1)" />
                <h3 style={{ fontFamily: 'var(--font-display)', fontSize: '1.75rem', fontWeight: 700 }}>Core Settings</h3>
              </div>
              <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--text-tertiary)', cursor: 'pointer' }}>
                <X size={20} />
              </button>
            </div>

            <div style={{ marginBottom: '2rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1.5rem', color: 'var(--text-secondary)', fontSize: '10px', fontFamily: 'var(--font-mono)', letterSpacing: '0.1em' }}>
                <Globe size={14} /> LANGUAGE_PROTOCOL
              </div>
              <div style={{ display: 'flex', gap: '1rem' }}>
                {(['en', 'zh'] as const).map(l => (
                  <button
                    key={l}
                    onClick={() => setLang(l)}
                    style={{
                      flex: 1,
                      padding: '1rem 0',
                      background: 'none',
                      border: 'none',
                      borderBottom: lang === l ? `2px solid var(--aurora-1)` : '1px solid rgba(255,255,255,0.1)',
                      color: lang === l ? 'white' : 'rgba(255,255,255,0.3)',
                      fontFamily: 'var(--font-mono)',
                      fontWeight: 700,
                      fontSize: '11px',
                      cursor: 'pointer',
                      transition: 'all 0.3s ease'
                    }}
                  >
                    {l === 'en' ? 'ENGLISH_ENG' : 'CHINESE_ZH'}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1.5rem', color: 'var(--text-secondary)', fontSize: '10px', fontFamily: 'var(--font-mono)', letterSpacing: '0.1em' }}>
                <Palette size={14} /> NEURAL_AESTHETIC
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                {(['dark', 'light', 'steampunk'] as const).map(t => (
                  <button
                    key={t}
                    onClick={() => setTheme(t)}
                    style={{
                      padding: '0.5rem 0',
                      background: 'none',
                      border: 'none',
                      color: theme === t ? 'var(--aurora-2)' : 'rgba(255,255,255,0.3)',
                      fontFamily: 'var(--font-mono)',
                      fontWeight: 700,
                      fontSize: '12px',
                      cursor: 'pointer',
                      textAlign: 'left',
                      textTransform: 'uppercase',
                      letterSpacing: '0.2em',
                      transition: 'all 0.3s ease'
                    }}
                  >
                    {theme === t ? `> ${t}` : `  ${t}`}
                  </button>
                ))}
              </div>
            </div>

            <div style={{ marginTop: '4rem', color: 'var(--text-tertiary)', fontSize: '9px', fontFamily: 'var(--font-mono)', letterSpacing: '0.1em', opacity: 0.5 }}>
              SYSTEM_ID: OPENCLAW_ARENA_V4.9.0<br/>
              AESTHETIC_ENGINE: PRETEXT_GEMINI
            </div>
            <style>{`
              @media (max-width: 768px) {
                .settings-shell-panel {
                  max-width: calc(100vw - 2rem) !important;
                  padding: 2rem 1rem !important;
                }
              }
            `}</style>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
};
