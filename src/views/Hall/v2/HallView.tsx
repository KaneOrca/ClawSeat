import React, { useEffect, useMemo } from 'react';
import { CHALLENGES, type Challenge } from '../../../data/mockData';
import { useArena } from '../../../context/ArenaContext';
import { usePhysicsRegistry } from '../../../context/PhysicsContext';
import { NeuralLoading } from '../../../design/VisualPrimitive';
import { useObstacle } from '../../../hooks/useObstacle';

type LayerState = 'locked' | 'unlocked' | 'active';

const MANUSCRIPT_ACTIVE_RED = '#b53021';

const romanNumerals = ['I.', 'II.', 'III.', 'IV.', 'V.', 'VI.', 'VII.', 'VIII.', 'IX.', 'X.', 'XI.', 'XII.'];

export const HallViewV2: React.FC = () => {
  const { user, setChallengeId, isLoading } = useArena();
  const { registerSoloist, unregisterSoloist } = usePhysicsRegistry();

  const completedIds = user?.completedChallenges ?? [];
  const activeChallengeId = useMemo(() => {
    return CHALLENGES.find(challenge => isChallengeUnlocked(challenge.id, completedIds) && !completedIds.includes(challenge.id))?.id
      ?? CHALLENGES.find(challenge => isChallengeUnlocked(challenge.id, completedIds))?.id
      ?? CHALLENGES[0]?.id;
  }, [completedIds]);

  const rows = useMemo(() => CHALLENGES.map((challenge, index) => ({
    challenge,
    numeral: romanNumerals[index] ?? `${index + 1}.`,
    state: getLayerState(challenge.id, completedIds, activeChallengeId),
  })), [activeChallengeId, completedIds]);

  const activeRow = rows.find(row => row.state === 'active');

  useEffect(() => {
    if (!activeRow) return;
    registerSoloist({
      id: 'hall-active',
      text: `${activeRow.numeral} ${activeRow.challenge.title}`,
      lineIndex: 8,
      color: MANUSCRIPT_ACTIVE_RED,
      opacity: 0.9,
    });
    return () => unregisterSoloist('hall-active');
  }, [activeRow, registerSoloist, unregisterSoloist]);

  if (isLoading && !user) {
    return (
      <div style={{ height: '60vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <NeuralLoading label="ACCESSING_AGENT_PROFILE" />
      </div>
    );
  }

  if (!user) return null;

  return (
    <div className="page-hall hall-v2-classical-codex" style={containerStyle}>
      <div style={profileStyle}>
        <div style={eyebrowStyle}>The Hall of Challenges</div>
        <div style={nameStyle}>{user.nickname}</div>
        <div style={metaStyle}>Layer {user.layer} / {user.score} XP</div>
      </div>

      <div className="hall-v2-list" style={listStyle}>
        {rows.map(row => (
          <LayerRow
            key={row.challenge.id}
            challenge={row.challenge}
            numeral={row.numeral}
            state={row.state}
            onSelect={setChallengeId}
          />
        ))}
      </div>

      <style>{`
        @media (max-width: 768px) {
          .hall-v2-classical-codex {
            padding: 3rem 1rem !important;
          }
          .hall-v2-list {
            width: 100% !important;
          }
        }
      `}</style>
    </div>
  );
};

const LayerRow: React.FC<{
  challenge: Challenge;
  numeral: string;
  state: LayerState;
  onSelect: (id: number) => void;
}> = ({ challenge, numeral, state, onSelect }) => {
  const isLocked = state === 'locked';
  const ref = useObstacle(!isLocked) as React.RefObject<HTMLButtonElement>;

  return (
    <button
      ref={ref as any}
      type="button"
      disabled={isLocked}
      onClick={() => !isLocked && onSelect(challenge.id)}
      style={{
        ...rowStyle,
        ...(state === 'active' ? activeRowStyle : null),
        ...(isLocked ? lockedRowStyle : null),
      }}
    >
      <span>
        <span style={chapterStyle}>{numeral}</span>
        <span>{challenge.title}</span>
      </span>
      <span style={pointsStyle}>{challenge.points}pt</span>
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
  padding: '4rem 2rem 6rem',
  color: '#1a1a1a',
  fontFamily: "'Playfair Display', 'Noto Serif SC', serif",
  position: 'relative',
};

const profileStyle: React.CSSProperties = {
  width: 'min(600px, 100%)',
  margin: '0 auto 3rem',
};

const eyebrowStyle: React.CSSProperties = {
  fontFamily: "'IBM Plex Mono', monospace",
  fontSize: '10px',
  letterSpacing: '0.28em',
  textTransform: 'uppercase',
  opacity: 0.5,
  marginBottom: '0.75rem',
};

const nameStyle: React.CSSProperties = {
  fontSize: 'clamp(2rem, 5vw, 3.5rem)',
  fontStyle: 'italic',
  lineHeight: 1,
};

const metaStyle: React.CSSProperties = {
  fontFamily: "'IBM Plex Mono', monospace",
  fontSize: '11px',
  letterSpacing: '0.14em',
  opacity: 0.55,
  marginTop: '1rem',
  textTransform: 'uppercase',
};

const listStyle: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  width: '600px',
  gap: '1.5rem',
  margin: '0 auto',
};

const rowStyle: React.CSSProperties = {
  appearance: 'none',
  background: 'transparent',
  border: 'none',
  color: 'inherit',
  cursor: 'pointer',
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'baseline',
  width: '100%',
  padding: 0,
  font: 'inherit',
  fontSize: '16px',
  textAlign: 'left',
};

const activeRowStyle: React.CSSProperties = {
  color: MANUSCRIPT_ACTIVE_RED,
  fontWeight: 700,
  fontStyle: 'italic',
  fontSize: '20px',
};

const lockedRowStyle: React.CSSProperties = {
  cursor: 'default',
  opacity: 0.22,
};

const chapterStyle: React.CSSProperties = {
  fontFamily: "'IBM Plex Mono', monospace",
  fontSize: '12px',
  marginRight: '1rem',
  opacity: 0.6,
};

const pointsStyle: React.CSSProperties = {
  fontFamily: "'IBM Plex Mono', monospace",
  fontSize: '12px',
  opacity: 0.6,
};
