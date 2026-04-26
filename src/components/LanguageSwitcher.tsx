import React from 'react';
import { useLanguage } from '../context/LanguageContext';
import { tokens } from '../design/tokens';

/**
 * LanguageSwitcher: Inline text-only locale toggle.
 * Designed to sit inside Navigation's NavAtom flow.
 */
export const LanguageSwitcher: React.FC = () => {
  const { locale, setLocale } = useLanguage();

  const languages = [
    { id: 'en', label: 'EN' },
    { id: 'zh-CN', label: '中文' }
  ] as const;

  return (
    <div style={containerStyle}>
      {languages.map((lang, i) => (
        <React.Fragment key={lang.id}>
          {i > 0 && <span style={separatorStyle}>/</span>}
          <span
            onClick={() => setLocale(lang.id)}
            style={locale === lang.id ? activeStyle : inactiveStyle}
          >
            {lang.label}
          </span>
        </React.Fragment>
      ))}
    </div>
  );
};

const containerStyle: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: '0.25rem',
  fontFamily: tokens.fonts.mono,
  fontSize: '10px',
  letterSpacing: '0.15em',
  userSelect: 'none',
};

const separatorStyle: React.CSSProperties = {
  color: 'rgba(255,255,255,0.2)',
};

const activeStyle: React.CSSProperties = {
  color: tokens.colors.aurora.cyan,
  fontWeight: 700,
  cursor: 'default',
};

const inactiveStyle: React.CSSProperties = {
  color: 'rgba(255,255,255,0.35)',
  cursor: 'pointer',
  transition: 'color 0.3s ease',
};
