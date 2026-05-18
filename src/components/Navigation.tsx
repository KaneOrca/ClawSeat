import React from 'react';
import { Settings } from 'lucide-react';
import { MagneticSurface } from './MagneticSurface';
import { LanguageSwitcher } from './LanguageSwitcher';
import { OrcaLogo } from './OrcaLogo';
import { useLanguage } from '../context/LanguageContext';
import type { ViewType } from '../context/ArenaContext';
import { tokens } from '../design/tokens';
import { useObstacle } from '../hooks/useObstacle';
import { useMousePush } from '../hooks/useMousePush';
import { assignRefs } from '../utils/assignRefs';

interface NavigationProps {
  currentView: ViewType;
  onViewChange: (view: ViewType) => void;
  onOpenSettings: () => void;
}

/**
 * Navigation: Fully atomic — no strip container.
 * Each element floats independently so background text flows between items.
 */
export const Navigation: React.FC<NavigationProps> = ({ currentView, onViewChange, onOpenSettings }) => {
  const { t } = useLanguage();

  const navItems: Array<{ id: ViewType; label: string; seq: string }> = [
    { id: 'home', label: t('common.nav.home'), seq: '01' },
    { id: 'hall', label: t('common.nav.hall'), seq: '02' },
    { id: 'watch', label: t('common.nav.watch'), seq: '03' },
    { id: 'community', label: t('common.nav.community'), seq: '04' },
  ];

  return (
    <div data-module="nav" style={navScatterStyle}>
      {/* Logo */}
      <NavAtom obstacle={false}>
        <MagneticSurface pull={0.2} padding={15}>
          <div
            onClick={() => onViewChange('home')}
            style={logoStyle}
          >
            <OrcaLogo size={28} />
            {t('common.nav.brand')}
          </div>
        </MagneticSurface>
      </NavAtom>

      {/* Nav links — each independently positioned */}
      {navItems.map((item) => (
        <NavAtom key={item.id}>
          <MagneticSurface pull={0.3} padding={10}>
            <span
              onClick={() => onViewChange(item.id)}
              style={{
                ...linkStyle,
                color: currentView === item.id ? tokens.colors.aurora.blue : tokens.colors.text.secondary,
                fontWeight: currentView === item.id ? 700 : 400,
              }}
            >
              [ {item.seq} ] {item.label}
            </span>
          </MagneticSurface>
        </NavAtom>
      ))}

      {/* Settings */}
      <NavAtom>
        <MagneticSurface pull={0.4} padding={15}>
          <div
            onClick={onOpenSettings}
            style={settingsStyle}
            onMouseEnter={(e) => (e.currentTarget.style.color = tokens.colors.text.primary)}
            onMouseLeave={(e) => (e.currentTarget.style.color = tokens.colors.text.tertiary)}
          >
            <Settings size={18} />
            <span style={{ fontFamily: tokens.fonts.mono, fontSize: '10px', letterSpacing: '0.1em' }}>
              {t('common.nav.config')}
            </span>
          </div>
        </MagneticSurface>
      </NavAtom>

      {/* Sync status */}
      <NavAtom>
        <div style={syncStyle}>
          <div style={syncDotStyle} />
          <span style={syncLabelStyle}>{t('common.nav.sync_active')}</span>
        </div>
      </NavAtom>

      {/* Language */}
      <NavAtom>
        <LanguageSwitcher />
      </NavAtom>
    </div>
  );
};

// ── Styles ──────────────────────────────────────────────────────────

const navScatterStyle: React.CSSProperties = {
  display: 'flex',
  flexWrap: 'wrap',
  alignItems: 'center',
  gap: '1rem',
  padding: '1rem 0',
  position: 'relative',
  zIndex: 10,
};

const logoStyle: React.CSSProperties = {
  fontFamily: tokens.fonts.display,
  fontWeight: 700,
  fontSize: '1.5rem',
  letterSpacing: '-0.02em',
  display: 'flex',
  alignItems: 'center',
  gap: '0.75rem',
  cursor: 'pointer',
  color: tokens.colors.text.primary,
};

const linkStyle: React.CSSProperties = {
  cursor: 'pointer',
  transition: 'color 0.3s ease',
  fontFamily: tokens.fonts.mono,
  fontSize: '11px',
  textTransform: 'uppercase',
  letterSpacing: '0.15em',
  padding: '0.5rem',
};

const settingsStyle: React.CSSProperties = {
  cursor: 'pointer',
  color: tokens.colors.text.tertiary,
  display: 'flex',
  alignItems: 'center',
  gap: '0.75rem',
  transition: 'color 0.3s ease',
};

const syncStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: '0.75rem',
};

const syncDotStyle: React.CSSProperties = {
  width: '8px',
  height: '8px',
  borderRadius: '50%',
  background: tokens.colors.aurora.cyan,
};

const syncLabelStyle: React.CSSProperties = {
  fontFamily: tokens.fonts.mono,
  fontSize: '10px',
  color: tokens.colors.text.tertiary,
  letterSpacing: '0.05em',
};

// ── NavAtom ─────────────────────────────────────────────────────────

const NavAtom: React.FC<{
  children: React.ReactNode;
  obstacle?: boolean;
}> = ({ children, obstacle = true }) => {
  const ref = useObstacle(obstacle) as React.RefObject<HTMLSpanElement>;
  const mousePushRef = useMousePush();
  return (
    <span
      ref={node => assignRefs(node, ref, mousePushRef)}
      data-functional-text="true"
      style={{ display: 'inline-flex' }}
    >
      {children}
    </span>
  );
};
