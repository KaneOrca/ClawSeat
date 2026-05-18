import React from 'react';
import { ScrambleText } from './ScrambleText';
import { Lock, CheckCircle2 } from 'lucide-react';
import { useObstacleDetached } from '../hooks/useObstacle';
import { MagneticSurface } from './MagneticSurface';
import { useWaveRipple } from '../hooks/useWaveRipple';
import { safeStr } from '../utils/safeStr';

interface ChallengeCardProps {
  id: number;
  title: string;
  points: number;
  description: string;
  difficulty: string;
  status: 'locked' | 'unlocked' | 'completed';
  isZenMode: boolean;
  onEnter?: (id: number) => void;
  /** Visual offset for staggered layout. */
  stagger: number;
}

// ── Poetic manuscript styles ────────────────────────────────────────

const containerStyle: React.CSSProperties = {
  maxWidth: '380px',
  cursor: 'pointer',
};

const serifTitleStyle: React.CSSProperties = {
  fontFamily: "'Playfair Display', 'Noto Serif SC', Georgia, serif",
  fontSize: '1.75rem',
  fontWeight: 400,
  fontStyle: 'italic',
  letterSpacing: '0.01em',
  lineHeight: 1.3,
  transition: 'letter-spacing 0.6s ease',
};

const monoMetaStyle: React.CSSProperties = {
  fontFamily: "'IBM Plex Mono', var(--font-mono), monospace",
  fontSize: '9px',
  letterSpacing: '0.15em',
  textTransform: 'uppercase',
  opacity: 0.5,
};

const descStyle: React.CSSProperties = {
  fontFamily: "'Playfair Display', Georgia, serif",
  fontSize: '0.9rem',
  lineHeight: 1.8,
  fontStyle: 'italic',
  opacity: 0.6,
  maxWidth: '320px',
};

const rewardStyle: React.CSSProperties = {
  fontFamily: "'IBM Plex Mono', var(--font-mono), monospace",
  fontSize: '10px',
  letterSpacing: '0.2em',
  opacity: 0.4,
};

// ── Component ───────────────────────────────────────────────────────

const ChallengeCardInner: React.FC<ChallengeCardProps> = ({
  id, title, points, description, difficulty, status, isZenMode, onEnter, stagger
}) => {
  const titleRef = useObstacleDetached(true, isZenMode) as React.RefObject<HTMLHeadingElement>;
  const descRef = useObstacleDetached(true, isZenMode) as React.RefObject<HTMLParagraphElement>;
  const metaRef = useObstacleDetached(true, isZenMode) as React.RefObject<HTMLSpanElement>;
  const ripple = useWaveRipple();

  const isLocked = status === 'locked';
  const isCompleted = status === 'completed';

  return (
    <div
      style={{
        ...containerStyle,
        marginTop: `${stagger}rem`,
        opacity: isLocked ? 0.25 : 1,
        cursor: isLocked ? 'not-allowed' : 'pointer',
      }}
      onClick={() => !isLocked && onEnter?.(id)}
    >
      {/* Meta line */}
      <span ref={metaRef as any} data-functional-text="true" style={monoMetaStyle}>
        {safeStr(difficulty).toUpperCase()} — {points} XP
        {isLocked && <Lock size={8} style={{ marginLeft: '0.5rem', verticalAlign: 'middle' }} />}
        {isCompleted && <CheckCircle2 size={8} style={{ marginLeft: '0.5rem', verticalAlign: 'middle', color: 'var(--aurora-5)' }} />}
      </span>

      {/* Title — serif italic with hover letter-spacing */}
      <MagneticSurface pull={0.08}>
        <h3
          ref={titleRef as any}
          data-functional-text="true"
          onPointerEnter={ripple.onPointerEnter}
          onTouchStart={ripple.onTouchStart}
          style={{
            ...serifTitleStyle,
            color: isLocked ? 'var(--text-tertiary)' : 'var(--text-primary)',
            marginTop: '0.75rem',
            marginBottom: '0.75rem',
          }}
          onMouseEnter={e => { if (!isLocked) (e.currentTarget.style.letterSpacing = '0.08em'); }}
          onMouseLeave={e => { e.currentTarget.style.letterSpacing = '0.01em'; }}
        >
          {isLocked ? <ScrambleText key="locked" text="[ encrypted ]" /> : <ScrambleText key={title} text={title} />}
        </h3>
      </MagneticSurface>

      {/* Description — poetic fragment */}
      <p ref={descRef as any} data-functional-text="true" style={{ ...descStyle, opacity: isLocked ? 0.2 : 0.6 }}>
        {description}
      </p>

      {/* Reward */}
      <div data-functional-text="true" style={{ ...rewardStyle, marginTop: '1.5rem' }}>
        {isCompleted ? '✓ CONQUERED' : isLocked ? '— SEALED —' : `LAYER ${id}`}
      </div>
    </div>
  );
};

export const ChallengeCard = React.memo(ChallengeCardInner);
