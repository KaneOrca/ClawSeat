import React, { useEffect, useMemo } from 'react';
import { CHALLENGES, type Challenge } from '../../../data/mockData';
import { useArena } from '../../../context/ArenaContext';
import { useLanguage } from '../../../context/LanguageContext';
import { usePhysicsRegistry } from '../../../context/PhysicsContext';
import { NeuralLoading } from '../../../design/VisualPrimitive';
import { tokens } from '../../../design/tokens';
import { useObstacle } from '../../../hooks/useObstacle';

type LayerState = 'locked' | 'unlocked' | 'active';

export const HallViewV3: React.FC = () => {
  const { user, setChallengeId, isLoading } = useArena();
  const { t } = useLanguage();
  const { environment, setEnvironment } = usePhysicsRegistry();
  const headerRef = useObstacle() as React.RefObject<HTMLElement>;

  const completedIds = user?.completedChallenges ?? [];
  const activeChallengeId = useMemo(() => {
    return CHALLENGES.find(challenge => isChallengeUnlocked(challenge.id, completedIds) && !completedIds.includes(challenge.id))?.id
      ?? CHALLENGES.find(challenge => isChallengeUnlocked(challenge.id, completedIds))?.id
      ?? CHALLENGES[0]?.id;
  }, [completedIds]);

  const rows = useMemo(() => CHALLENGES.map((challenge, index) => ({
    challenge,
    hex: `0x${(index + 1).toString(16).padStart(2, '0').toUpperCase()}`,
    state: getLayerState(challenge.id, completedIds, activeChallengeId),
  })), [activeChallengeId, completedIds]);

  useEffect(() => {
    if (!activeChallengeId) return;
    const prevAmp = environment.waveAmplitude ?? 60;
    setEnvironment({ waveAmplitude: 75 });
    return () => setEnvironment({ waveAmplitude: prevAmp });
  }, [activeChallengeId, setEnvironment]);

  if (isLoading && !user) {
    return (
      <div style={{ height: '60vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <NeuralLoading label="ACCESSING_AGENT_PROFILE" />
      </div>
    );
  }

  if (!user) return null;

  return (
    <div className="page-hall hall-v3-channel-carver" style={containerStyle}>
      <header ref={headerRef} style={headerStyle}>
        <div style={eyebrowStyle}>{t('hall.title')}</div>
        <div style={agentStyle}>{user.nickname} // {t('hall.layer_prefix')}_{user.layer} // {user.score}{t('hall.xp')}</div>
      </header>

      <div className="hall-v3-list" style={listStyle}>
        {rows.map(row => (
          <LayerRow
            key={row.challenge.id}
            challenge={row.challenge}
            hex={row.hex}
            state={row.state}
            onSelect={setChallengeId}
            pointsSuffix={t('hall.points_suffix').toUpperCase()}
          />
        ))}
      </div>

      <style>{`
        @media (max-width: 768px) {
          .hall-v3-channel-carver {
            padding: 5rem 0 3rem !important;
          }
          .hall-v3-row {
            padding: 0 1rem !important;
            font-size: ${tokens.sizes.small} !important;
          }
        }
      `}</style>
    </div>
  );
};

const LayerRow: React.FC<{
  challenge: Challenge;
  hex: string;
  state: LayerState;
  onSelect: (id: number) => void;
  pointsSuffix: string;
}> = ({ challenge, hex, state, onSelect, pointsSuffix }) => {
  const isLocked = state === 'locked';
  const textRef = useObstacle(!isLocked) as React.RefObject<HTMLSpanElement>;

  return (
    <button
      type="button"
      disabled={isLocked}
      className="hall-v3-row"
      onClick={() => !isLocked && onSelect(challenge.id)}
      style={{
        ...rowStyle,
        ...(state === 'active' ? activeRowStyle : null),
        ...(isLocked ? lockedRowStyle : null),
      }}
    >
      <span ref={textRef}>{'>'} {hex} // <span style={titleTransformStyle}>{challenge.title}</span></span>
      <span>{challenge.points}{pointsSuffix}</span>
    </button>
  );
};

const isChallengeUnlocked = (id: number, completedIds: number[]) => {
  return id === 1 || completedIds.includes(id) || completedIds.includes(id - 1);
};

const getLayerState = (id: number, completedIds: number[], activeChallengeId?: number): LayerState => {
  if (!isChallengeUnlocked(id, completedIds)) return 'locked';
  if (id === activeChallengeId) return 'active';
  return 'unlocked';
};

const containerStyle: React.CSSProperties = {
  minHeight: '100vh',
  padding: '6rem 0 4rem',
  color: tokens.colors.text.primary,
  fontFamily: tokens.fonts.body,
  position: 'relative',
};

const headerStyle: React.CSSProperties = {
  padding: '0 15vw 2rem',
  fontFamily: tokens.fonts.mono,
  letterSpacing: '0.16em',
  textTransform: 'uppercase',
};

const eyebrowStyle: React.CSSProperties = {
  color: tokens.colors.aurora.cyan,
  fontSize: tokens.sizes.small,
  marginBottom: '0.75rem',
};

const agentStyle: React.CSSProperties = {
  color: tokens.colors.text.tertiary,
  fontSize: tokens.sizes.micro,
};

const listStyle: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  width: '100%',
  padding: '2rem 0',
};

const rowStyle: React.CSSProperties = {
  appearance: 'none',
  background: 'transparent',
  border: 'none',
  color: tokens.colors.text.secondary,
  cursor: 'pointer',
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  height: '48px',
  width: '100%',
  padding: '0 15vw',
  fontFamily: tokens.fonts.mono,
  fontSize: '0.875rem',
  letterSpacing: '0.1em',
  transition: tokens.transitions.default,
  textAlign: 'left',
};

const activeRowStyle: React.CSSProperties = {
  color: tokens.colors.aurora.cyan,
  fontFamily: tokens.fonts.display,
  fontSize: '1.25rem',
  letterSpacing: '0.2em',
};

const lockedRowStyle: React.CSSProperties = {
  opacity: 0.1,
  cursor: 'default',
};

const titleTransformStyle: React.CSSProperties = {
  textTransform: 'uppercase',
};
