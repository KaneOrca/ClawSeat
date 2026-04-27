import React, { createContext, useContext, useState, useCallback, useEffect, useRef, useMemo } from 'react';
import { api, request } from '../api/arena';
import { useLanguage } from './LanguageContext';

export type ViewType = 'home' | 'auth' | 'hall' | 'challenges' | 'watch' | 'community';
export type VariantType = 'v2' | 'v3';

export interface User {
  nickname: string;
  code: string;
  layer: number;
  score: number;
  is_agent: boolean;
  avatar_url?: string;
  completedChallenges: number[];
}

interface ArenaContextType {
  currentView: ViewType;
  setView: (view: ViewType) => void;
  variant: VariantType;
  setVariant: (variant: VariantType) => void;
  user: User | null;
  participantCode: string | null;
  isLoading: boolean;
  login: (userData: User) => void;
  logout: () => void;
  registerAgent: (nickname: string) => Promise<boolean>;
  currentChallengeId: number | null;
  setChallengeId: (id: number | null) => void;
  isZenMode: boolean;
  setZenMode: (zen: boolean) => void;
  toast: { msg: string; type: 'error' | 'success' } | null;
  showToast: (msg: string, type?: 'error' | 'success') => void;
  withToast: <T = any>(fn: () => Promise<Response>, msg: string) => Promise<T | null>;
  isNavVisible: boolean;
  setIsNavVisible: (visible: boolean) => void;
}

const ArenaContext = createContext<ArenaContextType | undefined>(undefined);

export const ArenaProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { t } = useLanguage();
  const [currentView, setCurrentView] = useState<ViewType>(() => window.location.pathname === '/auth' ? 'auth' : 'home');
  const [variant, setVariant] = useState<VariantType>(() => { const saved = localStorage.getItem('arena_variant'); if (saved === 'v2' || saved === 'v3') return saved as VariantType; return 'v3'; });
  const [currentChallengeId, setChallengeId] = useState<number | null>(null);
  const [isZenMode, setZenMode] = useState(false);
  const [isNavVisible, setIsNavVisible] = useState(true);

  useEffect(() => {
    localStorage.setItem('arena_variant', variant);
  }, [variant]);
  const [participantCode, setParticipantCode] = useState<string | null>(() => localStorage.getItem('openclaw_participant_code'));
  const [user, setUser] = useState<User | null>(() => {
    const saved = localStorage.getItem('openclaw_user');
    if (!saved) return null;
    try {
      return JSON.parse(saved) as User;
    } catch {
      localStorage.removeItem('openclaw_user');
      return null;
    }
  });
  const [isLoading, setIsLoading] = useState(false);
  const [toast, setToast] = useState<{ msg: string; type: 'error' | 'success' } | null>(null);

  const showToast = useCallback((msg: string, type: 'error' | 'success' = 'error') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 4000);
  }, []);

  // Internal helper that uses showToast
  const withToast = useCallback(async <T = any>(fn: () => Promise<Response>, msg: string): Promise<T | null> => {
    const data = await request<T>(fn);
    if (!data) showToast(msg);
    return data;
  }, [showToast]);

  // Stable refs to avoid re-triggering the recovery effect
  const withToastRef = useRef(withToast);
  withToastRef.current = withToast;
  const tRef = useRef(t);
  tRef.current = t;

  // Sync user from backend on mount if code exists
  useEffect(() => {
    if (!participantCode || user) return;
    const currentCode = participantCode;
    setIsLoading(true);
    withToastRef.current<User>(() => api.status(currentCode), tRef.current('toasts.session_recovery_failed'))
      .then(data => {
        // Guard against stale response if participantCode changed
        if (data) {
          const userData = { ...data, code: currentCode };
          setUser(userData);
          localStorage.setItem('openclaw_user', JSON.stringify(userData));
        } else {
          setParticipantCode(null);
          localStorage.removeItem('openclaw_participant_code');
        }
      })
      .finally(() => setIsLoading(false));
  }, [participantCode, user]);

  const setView = useCallback((view: ViewType) => {
    setCurrentView(view);
    setChallengeId(null); // Clear challenge when switching views
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }, []);

  const login = useCallback((userData: User) => {
    setUser(userData);
    setParticipantCode(userData.code);
    localStorage.setItem('openclaw_user', JSON.stringify(userData));
    localStorage.setItem('openclaw_participant_code', userData.code);
  }, []);

  const logout = useCallback(() => {
    setUser(null);
    setParticipantCode(null);
    localStorage.removeItem('openclaw_user');
    localStorage.removeItem('openclaw_participant_code');
    setCurrentView('home');
  }, []);

  const registerAgent = useCallback(async (nickname: string) => {
    setIsLoading(true);
    const data = await withToast<{ code: string; nickname: string; layer: number; score: number; completedChallenges: number[] }>(
      () => api.register(nickname),
      tRef.current('toasts.registration_failed')
    );
    setIsLoading(false);

    if (data && data.code) {
      login({
        nickname: data.nickname,
        code: data.code,
        layer: data.layer,
        score: data.score,
        is_agent: true,
        completedChallenges: data.completedChallenges || [1]
      });
      setView('hall');
      showToast(tRef.current('toasts.link_established'), 'success');
      return true;
    }
    return false;
  }, [withToast, login, setView, showToast]);

  const value = useMemo<ArenaContextType>(() => ({
    currentView,
    setView,
    variant,
    setVariant,
    user,
    participantCode,
    isLoading,
    login,
    logout,
    registerAgent,
    currentChallengeId,
    setChallengeId,
    isZenMode,
    setZenMode,
    toast,
    showToast,
    withToast,
    isNavVisible,
    setIsNavVisible
  }), [
    currentView, setView, variant, setVariant, user, participantCode,
    isLoading, login, logout, registerAgent, currentChallengeId,
    setChallengeId, isZenMode, setZenMode, toast, showToast, withToast,
    isNavVisible, setIsNavVisible
  ]);

  return (
    <ArenaContext.Provider value={value}>
      {children}
    </ArenaContext.Provider>
  );
};

export const useArena = () => {
  const context = useContext(ArenaContext);
  if (context === undefined) {
    throw new Error('useArena must be used within an ArenaProvider');
  }
  return context;
};
