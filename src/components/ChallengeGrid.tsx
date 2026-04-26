import React from 'react';
import { ChallengeCard } from './ChallengeCard';
import { CHALLENGES } from '../data/mockData';
import { useArena } from '../context/ArenaContext';
import { NeuralEmpty } from '../design/VisualPrimitive';
import { useObstacleDetached } from '../hooks/useObstacle';

interface ChallengeGridProps {
  onChallengeSelect?: (id: number) => void;
}

// ── Stagger offsets: creates non-uniform vertical rhythm ────────────
const STAGGER = [0, 4, 1.5, 6, 2, 5, 0.5, 3.5, 7, 1, 4.5, 2.5];

// ── Styles ──────────────────────────────────────────────────────────

const sectionStyle: React.CSSProperties = {
  padding: '6rem 0',
};

const headerLabelStyle: React.CSSProperties = {
  fontFamily: "'IBM Plex Mono', var(--font-mono), monospace",
  fontSize: '9px',
  color: 'var(--aurora-1)',
  textTransform: 'uppercase',
  letterSpacing: '0.3em',
  opacity: 0.5,
};

const headerTitleStyle: React.CSSProperties = {
  fontFamily: "'Playfair Display', 'Noto Serif SC', Georgia, serif",
  fontSize: 'clamp(2.5rem, 5vw, 4rem)',
  fontWeight: 400,
  fontStyle: 'italic',
  lineHeight: 1.1,
  letterSpacing: '0.01em',
  color: 'var(--text-primary)',
  marginTop: '0.5rem',
};

const scatterStyle: React.CSSProperties = {
  display: 'flex',
  flexWrap: 'wrap',
  gap: '4rem 5rem',
  alignItems: 'flex-start',
  marginTop: '4rem',
};

const footerStyle: React.CSSProperties = {
  marginTop: '8rem',
  opacity: 0.2,
  fontFamily: "'Playfair Display', Georgia, serif",
  fontStyle: 'italic',
  fontSize: '0.9rem',
  lineHeight: 1.8,
  maxWidth: '500px',
};

// ── Header ──────────────────────────────────────────────────────────

const GridHeader: React.FC<{ isZenMode: boolean }> = ({ isZenMode }) => {
  const labelRef = useObstacleDetached(true, isZenMode) as React.RefObject<HTMLDivElement>;
  const titleRef = useObstacleDetached(true, isZenMode) as React.RefObject<HTMLHeadingElement>;
  return (
    <div style={{ marginBottom: '2rem' }}>
      <div ref={labelRef} style={headerLabelStyle}>[ SELECT_COGNITIVE_VECTOR ]</div>
      <h2 ref={titleRef as any} style={headerTitleStyle}>The Hall of Challenges</h2>
    </div>
  );
};
const GridHeaderMemo = React.memo(GridHeader);

// ── Main component ──────────────────────────────────────────────────

export const ChallengeGrid: React.FC<ChallengeGridProps> = ({ onChallengeSelect }) => {
  const { user, isZenMode } = useArena();
  const completedIds = user?.completedChallenges || [];

  return (
    <section style={sectionStyle}>
      {CHALLENGES.length === 0 ? (
        <NeuralEmpty label="NO_CHALLENGES_FOUND" sublabel="The challenge matrix is currently being recalculated. Check back soon." />
      ) : (
        <>
          <GridHeaderMemo isZenMode={isZenMode} />

          <div style={scatterStyle}>
            {CHALLENGES.map((challenge, i) => {
              const isCompleted = completedIds.includes(challenge.id);
              const isUnlocked = challenge.id === 1 || completedIds.includes(challenge.id - 1) || isCompleted;
              const status = isCompleted ? 'completed' : isUnlocked ? 'unlocked' : 'locked';

              return (
                <ChallengeCard
                  key={challenge.id}
                  id={challenge.id}
                  title={challenge.title}
                  points={challenge.points}
                  description={challenge.description}
                  difficulty={challenge.difficulty}
                  status={status}
                  isZenMode={isZenMode}
                  onEnter={onChallengeSelect}
                  stagger={STAGGER[i % STAGGER.length]}
                />
              );
            })}
          </div>
        </>
      )}

      <div style={footerStyle}>
        New neural layers are being generated in real-time.
        Complete existing challenges to unlock deeper architectural voids.
      </div>
    </section>
  );
};
