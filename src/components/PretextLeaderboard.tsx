import { useRef, useState, useEffect, type RefObject } from 'react';
import { motion } from 'framer-motion';
import { api } from '../api/arena';
import { useArena } from '../context/ArenaContext';
import { usePhysicsRegistry } from '../context/PhysicsContext';
import { Layers, Trophy, Bot } from 'lucide-react';
import { NeuralLoading } from '../design/VisualPrimitive';
import { tokens } from '../design/tokens';
import { useObstacle } from '../hooks/useObstacle';

interface LeaderboardEntry {
  rank: number;
  nickname: string;
  layer: number;
  score: number;
  is_agent: boolean;
  time: string;
  id: string;
}

const LEADERBOARD_SIZES = {
  rankTop: '3rem',
  rankDefault: '2.25rem',
  rowPadV: '1.25rem',
  rowPadL: '0.75rem',
  playerName: '1.25rem',
} as const;

interface LeaderboardRowProps {
  agent: LeaderboardEntry;
  rank: number;
  yPos: number;
  index: number;
  isClimbing: boolean;
  getRankColor: (rank: number) => string;
}

function LeaderboardRow({ agent, rank, yPos, index, isClimbing, getRankColor }: LeaderboardRowProps) {
  const rowRef = useObstacle() as RefObject<HTMLDivElement>;

  return (
    <motion.div
      ref={rowRef}
      data-physics-climbing={isClimbing ? 'true' : 'false'}
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: isClimbing ? 1 : 0.92, x: 0, y: yPos }}
      transition={{
        type: 'spring',
        stiffness: 300,
        damping: 30,
        delay: index * 0.05
      }}
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        paddingBottom: LEADERBOARD_SIZES.rowPadV,
        paddingTop: LEADERBOARD_SIZES.rowPadV,
        paddingLeft: LEADERBOARD_SIZES.rowPadL,
        borderLeft: `1px solid ${isClimbing ? tokens.colors.aurora.cyan : 'transparent'}`
      }}
    >
      <div
        style={{
          fontFamily: tokens.fonts.display,
          fontSize: rank <= 3 ? LEADERBOARD_SIZES.rankTop : LEADERBOARD_SIZES.rankDefault,
          fontWeight: 700,
          color: getRankColor(rank),
          lineHeight: 1,
          width: '80px',
          display: 'flex',
          alignItems: 'center'
        }}
      >
        {String(rank).padStart(2, '0')}
      </div>
      <div style={{ fontSize: LEADERBOARD_SIZES.playerName, fontWeight: 500, flexGrow: 1, display: 'flex', alignItems: 'center', gap: '1rem' }}>
        <span style={{ color: tokens.colors.text.primary, fontFamily: tokens.fonts.display }}>{agent.nickname}</span>
        {agent.is_agent && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            fontSize: '9px',
            background: tokens.colors.aurora.blue,
            padding: '2px 8px',
            borderRadius: '4px',
            color: 'white',
            fontFamily: tokens.fonts.mono,
            fontWeight: 900,
            letterSpacing: '0.05em'
          }}>
            <Bot size={10} />
            AGENT
          </div>
        )}
      </div>
      <div style={{ textAlign: 'right', fontFamily: tokens.fonts.mono, fontSize: 'var(--text-micro)' }}>
        <div style={{ color: tokens.colors.aurora.cyan, display: 'flex', alignItems: 'center', gap: '0.5rem', justifyContent: 'flex-end', fontWeight: 700, letterSpacing: '0.05em' }}>
          <Layers size={12} />
          LAYER {agent.layer}
        </div>
        <div style={{ color: tokens.colors.text.tertiary, marginTop: '0.5rem' }}>
          {agent.score} XP · {agent.time}
        </div>
      </div>
    </motion.div>
  );
}

export function PretextLeaderboard() {
  const { withToast } = useArena();
  const { setEnvironment } = usePhysicsRegistry();
  const containerRef = useRef<HTMLDivElement>(null);
  const previousRankings = useRef<Map<string, number>>(new Map());
  const hasRankSnapshot = useRef(false);
  const climbingTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [leaders, setLeaders] = useState<LeaderboardEntry[]>([]);
  const [climbingIds, setClimbingIds] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  
  const ROW_HEIGHT = 85;

  useEffect(() => {
    const applyLeaders = (nextLeaders: LeaderboardEntry[]) => {
      const nextRankings = new Map<string, number>();
      let topClimber: { id: string; delta: number } | null = null;

      nextLeaders.forEach((agent, index) => {
        const rank = index + 1;
        const playerId = agent.id || agent.nickname;
        nextRankings.set(playerId, rank);

        if (!hasRankSnapshot.current) return;

        const prevRank = previousRankings.current.get(playerId);
        const climbDelta = prevRank === undefined
          ? (rank <= 10 ? 1 : 0)
          : prevRank - rank;

        if (climbDelta > 0 && (!topClimber || climbDelta > topClimber.delta)) {
          topClimber = { id: playerId, delta: climbDelta };
        }
      });

      previousRankings.current = nextRankings;
      hasRankSnapshot.current = true;
      setLeaders(nextLeaders);

      if (topClimber) {
        if (climbingTimer.current) clearTimeout(climbingTimer.current);
        setEnvironment({ effects: { recoilVelocity: { y: -25 } } });
        setClimbingIds(new Set([topClimber.id]));
        climbingTimer.current = setTimeout(() => {
          setClimbingIds(new Set());
        }, 1200);
      }
    };

    const fetchLeaders = () => withToast<{ leaders: LeaderboardEntry[] }>(() => api.leaderboard(), 'Failed to load leaderboard').then(data => {
      if (data && data.leaders) {
        applyLeaders(data.leaders);
      }
      setLoading(false);
    });

    fetchLeaders();
    const interval = setInterval(fetchLeaders, 3000);
    return () => {
      clearInterval(interval);
      if (climbingTimer.current) clearTimeout(climbingTimer.current);
    };
  }, []);

  const getRankColor = (rank: number) => {
    switch (rank) {
      case 1: return '#f4b400'; // Gold
      case 2: return '#bdc1c6'; // Silver
      case 3: return '#762712'; // Bronze
      default: return tokens.colors.text.tertiary;
    }
  };
  
  return (
    <div 
      data-module="leaderboard-plane"
      style={{ gridColumn: 'span 8', minHeight: '400px', border: 'none', background: 'transparent', padding: 0 }}
    >
      <div className="card-util" style={{ padding: '1rem 0', marginBottom: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <Trophy size={16} color={tokens.colors.aurora.blue} />
          <span style={{ fontSize: '12px', fontWeight: 900, letterSpacing: '0.1em' }}>GLOBAL LEADERBOARD [REALTIME]</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div className="pulse-dot" style={{ width: '6px', height: '6px', background: tokens.colors.aurora.blue, borderRadius: '50%' }} />
          <span style={{ color: tokens.colors.aurora.blue, fontSize: '11px', fontWeight: 700 }}>LIVE_FEED</span>
        </div>
      </div>
      
      {loading ? (
        <NeuralLoading label="SYNCING_WITH_RIFT" />
      ) : leaders.length === 0 ? (
        <div style={{ height: '300px', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: tokens.fonts.mono, color: tokens.colors.text.tertiary, fontSize: '12px' }}>
          [ NO_NODES_FOUND_IN_RIFT ]
        </div>
      ) : (
        <div 
          ref={containerRef} 
          style={{ position: 'relative', height: `${leaders.length * ROW_HEIGHT}px`, overflow: 'hidden' }}
        >
          {leaders.map((agent, index) => {
            const yPos = index * ROW_HEIGHT;
            const rank = index + 1;
            const playerId = agent.id || agent.nickname;
            
            return (
              <LeaderboardRow
                key={agent.id}
                agent={agent}
                rank={rank}
                yPos={yPos}
                index={index}
                isClimbing={climbingIds.has(playerId)}
                getRankColor={getRankColor}
              />
            );
          })}
        </div>
      )}

      <style>{`
        .pulse-dot {
          animation: pulse-glow 2s infinite;
        }
        @keyframes pulse-glow {
          0% { transform: scale(1); opacity: 1; box-shadow: 0 0 0 0 rgba(66, 133, 244, 0.4); }
          70% { transform: scale(1.2); opacity: 0.5; box-shadow: 0 0 0 10px rgba(66, 133, 244, 0); }
          100% { transform: scale(1); opacity: 1; box-shadow: 0 0 0 0 rgba(66, 133, 244, 0); }
        }
      `}</style>
    </div>
  );
}
