import { useRef, useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { api } from '../api/arena';
import { useArena } from '../context/ArenaContext';
import { Layers, Trophy, Bot } from 'lucide-react';
import { NeuralLoading } from '../design/VisualPrimitive';
import { tokens } from '../design/tokens';

interface LeaderboardEntry {
  rank: number;
  nickname: string;
  layer: number;
  score: number;
  is_agent: boolean;
  time: string;
  id: string;
}

export function PretextLeaderboard() {
  const { withToast } = useArena();
  const containerRef = useRef<HTMLDivElement>(null);
  const [leaders, setLeaders] = useState<LeaderboardEntry[]>([]);
  const [loading, setLoading] = useState(true);
  
  const ROW_HEIGHT = 85;

  useEffect(() => {
    withToast<{ leaders: LeaderboardEntry[] }>(() => api.leaderboard(), 'Failed to load leaderboard').then(data => {
      if (data && data.leaders) {
        setLeaders(data.leaders);
      }
      setLoading(false);
    });
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
            
            return (
              <motion.div
                key={agent.id}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0, y: yPos }}
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
                  paddingBottom: '1.25rem',
                  paddingTop: '1.25rem'
                }}
              >
                <div 
                  style={{
                    fontFamily: tokens.fonts.display,
                    fontSize: rank <= 3 ? '3rem' : '2.25rem',
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
                <div style={{ fontSize: '1.25rem', fontWeight: 500, flexGrow: 1, display: 'flex', alignItems: 'center', gap: '1rem' }}>
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
