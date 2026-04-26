import React from 'react';
import { ChallengeGrid } from '../../components/ChallengeGrid';
import { useArena } from '../../context/ArenaContext';
import { NeuralLoading } from '../../design/VisualPrimitive';
import { tokens } from '../../design/tokens';
import { useObstacleDetached } from '../../hooks/useObstacle';
import { MagneticSurface } from '../../components/MagneticSurface';
import { useWaveRipple } from '../../hooks/useWaveRipple';
import type { User } from '../../context/ArenaContext';

/**
 * HallView: Pruned dashboard + challenge flow.
 * Only essential info: nickname, layer depth, score.
 */
export const HallView: React.FC = () => {
  const { user, setChallengeId, isLoading, isZenMode } = useArena();

  if (isLoading && !user) {
    return (
      <div style={{ height: '60vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <NeuralLoading label="ACCESSING_AGENT_PROFILE" />
      </div>
    );
  }

  if (!user) return null;

  return (
    <div className="page-hall">
      <ProfileIslandMemo user={user} isZenMode={isZenMode} />
      <section id="hall-challenge-plane" data-module="challenge-grid">
        <ChallengeGrid onChallengeSelect={setChallengeId} />
      </section>
    </div>
  );
};

// ── Styles ──────────────────────────────────────────────────────────

const nicknameStyle: React.CSSProperties = {
  fontFamily: tokens.fonts.display,
  fontSize: 'clamp(2rem, 4vw, 3.5rem)',
  marginBottom: '0.5rem',
};

const agentBadgeStyle: React.CSSProperties = {
  fontSize: '11px',
  fontFamily: tokens.fonts.mono,
  marginLeft: '1rem',
  verticalAlign: 'middle',
  fontWeight: 700,
  color: tokens.colors.aurora.blue,
  letterSpacing: '0.1em',
};

const depthValueStyle: React.CSSProperties = {
  fontFamily: tokens.fonts.display,
  fontSize: '3rem',
  color: tokens.colors.aurora.cyan,
  lineHeight: 1,
};

const scoreStyle: React.CSSProperties = {
  fontFamily: tokens.fonts.mono,
  fontSize: '11px',
  color: tokens.colors.text.tertiary,
  letterSpacing: '0.1em',
  marginTop: '1rem',
};

// ── Profile island: separated atoms ─────────────────────────────────

const ProfileIsland: React.FC<{ user: User; isZenMode: boolean }> = ({ user, isZenMode }) => {
  const nameRef = useObstacleDetached(true, isZenMode) as React.RefObject<HTMLHeadingElement>;
  const depthRef = useObstacleDetached(true, isZenMode) as React.RefObject<HTMLSpanElement>;
  const scoreRef = useObstacleDetached(true, isZenMode) as React.RefObject<HTMLSpanElement>;
  const { onPointerEnter, onTouchStart } = useWaveRipple();
  return (
    <div style={{ marginBottom: '4rem' }}>
      {/* Nickname — ref on h1 text, not wrapper */}
      <MagneticSurface pull={0.1}>
        <h1 ref={nameRef as any} onPointerEnter={onPointerEnter} onTouchStart={onTouchStart} style={nicknameStyle}>
          {user.nickname}
          {user.is_agent && <span style={agentBadgeStyle}>// AGENT</span>}
        </h1>
      </MagneticSurface>

      {/* Layer depth — ref on text span */}
      <MagneticSurface pull={0.15}>
        <span ref={depthRef as any} onPointerEnter={onPointerEnter} onTouchStart={onTouchStart} style={depthValueStyle}>
          Layer {user.layer}
        </span>
      </MagneticSurface>

      {/* Score — ref on text span */}
      <span ref={scoreRef as any} style={scoreStyle}>
        {user.score} XP
      </span>
    </div>
  );
};
const ProfileIslandMemo = React.memo(ProfileIsland);
