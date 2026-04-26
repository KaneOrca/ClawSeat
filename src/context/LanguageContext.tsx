import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { getContent } from '../content';
import type { Language } from '../content';

interface LanguageContextType {
  locale: Language;
  setLocale: (lang: Language) => void;
  t: (keyPath: string) => string;
  content: any;
}

const LanguageContext = createContext<LanguageContextType | undefined>(undefined);

export const LanguageProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [locale, setLocaleState] = useState<Language>(() => {
    const saved = localStorage.getItem('arena_locale') as Language;
    if (saved === 'en' || saved === 'zh-CN') return saved;
    
    // Default to browser language or 'zh-CN'
    const browserLang = navigator.language;
    return browserLang.startsWith('en') ? 'en' : 'zh-CN';
  });

  const [content, setContent] = useState(getContent(locale));

  useEffect(() => {
    localStorage.setItem('arena_locale', locale);
    setContent(getContent(locale));
    document.documentElement.lang = locale;
  }, [locale]);

  const setLocale = useCallback((lang: Language) => {
    setLocaleState(lang);
  }, []);

  const t = useCallback((keyPath: string): string => {
    const keys = keyPath.split('.');
    let value: any = content;
    
    for (const key of keys) {
      if (value && typeof value === 'object' && key in value) {
        value = value[key];
      } else {
        console.warn(`i18n: Key path "${keyPath}" not found in ${locale} locale.`);
        return keyPath;
      }
    }
    
    return typeof value === 'string' ? value : keyPath;
  }, [content, locale]);

  return (
    <LanguageContext.Provider value={{ locale, setLocale, t, content }}>
      {children}
    </LanguageContext.Provider>
  );
};

export const useLanguage = () => {
  const context = useContext(LanguageContext);
  if (context === undefined) {
    throw new Error('useLanguage must be used within a LanguageProvider');
  }
  return context;
};
