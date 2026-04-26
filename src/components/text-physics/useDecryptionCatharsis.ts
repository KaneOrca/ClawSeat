import { useCallback } from 'react';
import { useArena } from '../../context/ArenaContext';
import { usePhysicsRegistry } from '../../context/PhysicsContext';
import { tokens } from '../../design/tokens';

interface CatharsisInput {
  layerId: number;
}

export function useDecryptionCatharsis({ layerId }: CatharsisInput) {
  const { user } = useArena();
  const { registerSoloist, setEnvironment } = usePhysicsRegistry();

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
      registerSoloist({
        id: `signature-${layerId}-${stepId}-${timestamp}`,
        text: signature,
        lineIndex: 8 + Number(stepId.replace(/\D/g, '') || 0) * 3,
        color: tokens.colors.aurora.cyan,
        opacity: 0.95,
      });
    }, 240);

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
  }, [layerId, registerSoloist, setEnvironment, user?.nickname]);
}
