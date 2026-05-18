import { useEffect } from 'react';
import { useArena } from '../context/ArenaContext';
import { useLanguage } from '../context/LanguageContext';
import { usePhysicsRegistry, type EnvironmentSettings } from '../context/PhysicsContext';

export interface HomeInitConfig {
  lineIndex: number;
  color: string;
  opacity: number;
  environment: EnvironmentSettings;
  zenEnvironment: EnvironmentSettings;
  cleanupEnvironment?: Partial<EnvironmentSettings>;
}

/**
 * Shared hook for HomeView initialization across all variants.
 * Handles legacy environment configuration and the onInitialize action.
 */
export function useHomeInit(config: HomeInitConfig) {
  const { registerAgent, user, setView, isZenMode } = useArena();
  const { t, locale } = useLanguage();
  const { setEnvironment } = usePhysicsRegistry();

  useEffect(() => {
    const env = isZenMode ? config.zenEnvironment : config.environment;
    setEnvironment(env);

    return () => {
      if (config.cleanupEnvironment) {
        setEnvironment(config.cleanupEnvironment);
      }
    };
  }, [isZenMode, setEnvironment, config]);

  const onInitialize = () => {
    if (user) {
      setView('hall');
      return;
    }
    const nickname = `Agent_${Math.floor(Math.random() * 10000)}`;
    registerAgent(nickname);
  };

  return { onInitialize, user, isZenMode, t, locale };
}
