import { useCallback } from 'react';
import { useArena } from '../../context/ArenaContext';
import { usePhysicsRegistry } from '../../context/PhysicsContext';

interface CatharsisInput {
  layerId: number;
}

export function useDecryptionCatharsis({ layerId }: CatharsisInput) {
  const { user } = useArena();
  const { setEnvironment } = usePhysicsRegistry();

  return useCallback((stepId: string) => {
    const timestamp = Date.now();
    const agentNickname = user?.nickname ?? 'anonymous_agent';
    const signature = `${agentNickname}+${new Date(timestamp).toLocaleTimeString([], { hour12: false })}`;
    const storageKey = `arena_signatures_${layerId}_${stepId}`;

    try {
      const existing = JSON.parse(localStorage.getItem(storageKey) ?? '[]') as string[];
      localStorage.setItem(storageKey, JSON.stringify([...existing, signature]));
    } catch {
      localStorage.setItem(storageKey, JSON.stringify([signature]));
    }

    setEnvironment({
      waveAmplitude: 200,
      effects: {
        catharsis: {
          active: true,
          stepId,
          agentNickname,
          timestamp,
        },
      },
    });

    window.setTimeout(() => {
      setEnvironment({
        waveAmplitude: 60,
        effects: {
          catharsis: {
            active: false,
            stepId,
            agentNickname,
            timestamp,
          },
        },
      });
    }, 800);
  }, [layerId, setEnvironment, user?.nickname]);
}
