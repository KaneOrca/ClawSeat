import { useEffect } from 'react';
import { useArena } from '../context/ArenaContext';
import { useLanguage } from '../context/LanguageContext';
import { usePhysicsRegistry, type Soloist, type EnvironmentSettings } from '../context/PhysicsContext';

export interface HomeInitConfig {
  soloistId: string;
  lineIndex: number;
  color: string;
  opacity: number;
  environment: EnvironmentSettings;
  zenEnvironment: EnvironmentSettings;
  cleanupEnvironment?: Partial<EnvironmentSettings>;
}

/**
 * Shared hook for HomeView initialization across all variants.
 * Handles soloist registration, environment configuration, and the onInitialize action.
 */
export function useHomeInit(config: HomeInitConfig) {
  const { registerAgent, user, setView, isZenMode } = useArena();
  const { t, locale } = useLanguage();
  const { registerSoloist, unregisterSoloist, setEnvironment } = usePhysicsRegistry();

  useEffect(() => {
    const titleSoloist: Soloist = {
      id: config.soloistId,
      text: t('home.title').toUpperCase(),
      lineIndex: config.lineIndex,
      color: config.color,
      opacity: config.opacity
    };
    registerSoloist(titleSoloist);

    const env = isZenMode ? config.zenEnvironment : config.environment;
    setEnvironment(env);

    return () => {
      unregisterSoloist(config.soloistId);
      if (config.cleanupEnvironment) {
        setEnvironment(config.cleanupEnvironment);
      }
    };
  }, [t, registerSoloist, unregisterSoloist, setEnvironment, isZenMode, config]);

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
