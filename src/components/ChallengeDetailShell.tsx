import React, { useMemo } from 'react';
import { motion } from 'framer-motion';
import { ScrambleText } from './ScrambleText';
import { safeStr } from '../utils/safeStr';
import { PretextEditorial } from './PretextEditorial';
import { MagneticSurface } from './MagneticSurface';
import { SpatialParallax } from './SpatialParallax';
import { HaloField } from './HaloField';
import { NeuralBadge } from '../design/VisualPrimitive';
import { tokens } from '../design/tokens';
import { GeminiSparkle } from './GeminiSparkle';
import { ArrowLeft, Terminal, Cpu, Database, Network, CheckCircle2, Lock, Info } from 'lucide-react';
import { CHALLENGES } from '../data/mockData';

interface ChallengeDetailShellProps {
  challengeId: number;
  onBack?: () => void;
  onAction?: () => void;
  isActionLoading?: boolean;
}

export const ChallengeDetailShell: React.FC<ChallengeDetailShellProps> = ({ 
  challengeId,
  onBack,
  onAction,
  isActionLoading = false
}) => {
  const challenge = useMemo(() => {
    const base = CHALLENGES.find(c => c.id === challengeId) || CHALLENGES[0];
    return {
      ...base,
      layer: `Layer ${String(base.id).padStart(2, '0')}`,
      story: `The rift's architecture is self-referential at this depth. To descend further, you must navigate the cognitive voids that bind the neural structures together. The signal for ${base.title} is fragmented, scattered across layers that demand specialized orchestration.`,
      objective: `Locate and resolve the core logic of ${base.title}. This challenge worth ${base.points} XP represents a significant leap in cognitive depth.`,
      requirements: [
        'Pattern recognition sync',
        'Logic gate orchestration',
        'Neural weight validation'
      ]
    };
  }, [challengeId]);

  const isCompleted = challenge.status === 'completed';
  const isLocked = challenge.status === 'locked';

  return (
    <motion.div 
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      style={{ position: 'relative', minHeight: '100vh', padding: '4rem 0' }}
    >
      <HaloField intensity={0.15} color={isCompleted ? tokens.colors.aurora.cyan : tokens.colors.aurora.red}>
        
        {/* BACK NAVIGATION */}
        <div style={{ marginBottom: '4rem' }}>
          <MagneticSurface pull={0.15} padding={20}>
            <button 
              onClick={onBack}
              style={{
                background: 'transparent',
                border: 'none',
                color: tokens.colors.text.tertiary,
                display: 'flex',
                alignItems: 'center',
                gap: '1rem',
                cursor: 'pointer',
                fontFamily: tokens.fonts.mono,
                fontSize: '11px',
                textTransform: 'uppercase',
                letterSpacing: '0.15em',
                transition: 'color 0.3s ease'
              }}
              onMouseEnter={(e) => e.currentTarget.style.color = tokens.colors.text.primary}
              onMouseLeave={(e) => e.currentTarget.style.color = tokens.colors.text.tertiary}
            >
              <ArrowLeft size={16} />
              [ RETURN_TO_RIFT_HALL ]
            </button>
          </MagneticSurface>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '10rem', alignItems: 'start' }}>
          
          {/* NARRATIVE COLUMN */}
          <SpatialParallax depth={0.02} direction={1}>
            <div data-module="narrative-column">
              <div style={{ marginBottom: '2.5rem' }}>
                <NeuralBadge 
                  text={`${challenge.layer} // COGNITIVE_VECTOR`} 
                  color={isCompleted ? tokens.colors.aurora.cyan : isLocked ? tokens.colors.text.tertiary : tokens.colors.aurora.blue} 
                />
              </div>

              <h1 style={{
                fontFamily: tokens.fonts.display,
                fontSize: 'clamp(4rem, 8vw, 6rem)',
                fontWeight: 700,
                lineHeight: 0.85,
                letterSpacing: '-0.05em',
                marginBottom: '5rem',
                color: tokens.colors.text.primary
              }}>
                <ScrambleText text={challenge.title} />
              </h1>

              <div style={{ 
                padding: '0 0 4rem 0', 
                marginBottom: '4rem', 
                borderLeft: `2px solid ${isCompleted ? tokens.colors.aurora.cyan : isLocked ? tokens.colors.glass.border : tokens.colors.aurora.blue}`,
                paddingLeft: '3rem'
              }}>
                <div className="card-util" style={{ marginBottom: '3rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    <Info size={14} color={tokens.colors.aurora.blue} />
                    <span style={{ fontWeight: 900, fontSize: '10px' }}>NARRATIVE_LOG</span>
                  </div>
                  <span style={{ fontSize: '9px', opacity: 0.3 }}>SEQ_SYNC_OK</span>
                </div>
                <PretextEditorial 
                  text={isLocked ? 'This cognitive layer is currently encrypted. Resolve higher-level rifts to access this data stream.' : challenge.story}
                  width={600}
                  lineHeight={38}
                  fontDef="italic 400 24px Satoshi"
                  color={isLocked ? tokens.colors.text.tertiary : tokens.colors.text.primary}
                  delay={0.3}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2.5rem' }}>
                <div style={{ padding: '0' }}>
                  <div style={{ color: tokens.colors.text.tertiary, fontSize: '9px', fontFamily: tokens.fonts.mono, marginBottom: '1rem', letterSpacing: '0.2em', fontWeight: 900 }}>XP_YIELD</div>
                  <div style={{ fontSize: '3.5rem', fontWeight: 700, color: tokens.colors.aurora.purple, fontFamily: tokens.fonts.display, lineHeight: 1 }}>{challenge.points}</div>
                </div>
                <div style={{ padding: '0' }}>
                  <div style={{ color: tokens.colors.text.tertiary, fontSize: '9px', fontFamily: tokens.fonts.mono, marginBottom: '1rem', letterSpacing: '0.2em', fontWeight: 900 }}>DEPTH_INTENSITY</div>
                  <div style={{ fontSize: '3.5rem', fontWeight: 700, color: tokens.colors.aurora.red, fontFamily: tokens.fonts.display, lineHeight: 1 }}>{challenge.difficulty}</div>
                </div>
              </div>
            </div>
          </SpatialParallax>

          {/* ACTION COLUMN */}
          <SpatialParallax depth={0.06} direction={-1} tilt>
            <div data-module="operational-directive" style={{ 
              padding: '0'
            }}>
              <div className="card-util" style={{ borderBottomColor: 'rgba(255,255,255,0.1)', marginBottom: '4rem' }}>
                <span style={{ fontWeight: 900, fontSize: '10px' }}>OPERATIONAL_DIRECTIVE</span>
                <span style={{ color: isCompleted ? tokens.colors.aurora.cyan : tokens.colors.text.tertiary, fontSize: '9px', fontWeight: 900 }}>STATUS: {safeStr(challenge.status).toUpperCase()}</span>
              </div>
              
              <div style={{ marginBottom: '5rem' }}>
                <h3 style={{ fontFamily: tokens.fonts.mono, fontSize: '11px', color: tokens.colors.aurora.blue, marginBottom: '2rem', letterSpacing: '0.2em', fontWeight: 900 }}>
                  // PRIMARY_OBJECTIVE
                </h3>
                <div style={{ minHeight: '100px' }}>
                  <PretextEditorial 
                    text={isLocked ? '[ UNAUTHORIZED_DEPTH_ACCESS_DENIED ]' : challenge.objective}
                    width={400}
                    lineHeight={32}
                    fontDef="500 22px Satoshi"
                    color={isLocked ? tokens.colors.text.tertiary : tokens.colors.text.primary}
                    delay={0.6}
                  />
                </div>
              </div>

              <div style={{ marginBottom: '6rem' }}>
                <h3 style={{ fontFamily: tokens.fonts.mono, fontSize: '11px', color: tokens.colors.aurora.blue, marginBottom: '2rem', letterSpacing: '0.2em', fontWeight: 900 }}>
                  // SYSTEM_REQUIREMENTS
                </h3>
                <ul style={{ listStyle: 'none', padding: 0 }}>
                  {challenge.requirements.map((req, i) => (
                    <li key={i} style={{ 
                      display: 'flex', 
                      alignItems: 'center', 
                      gap: '1.5rem', 
                      marginBottom: '1.5rem',
                      color: isLocked ? tokens.colors.text.tertiary : tokens.colors.text.secondary,
                      fontSize: '1rem',
                      fontWeight: 500
                    }}>
                      {isCompleted ? <CheckCircle2 size={16} style={{ color: tokens.colors.aurora.cyan }} /> : <Terminal size={14} style={{ opacity: 0.3 }} />}
                      {safeStr(req).toUpperCase()}
                    </li>
                  ))}
                </ul>
              </div>

              <div style={{ 
                padding: '4rem 0',
                textAlign: 'center',
                position: 'relative',
                overflow: 'hidden'
              }}>
                <div style={{ position: 'relative', zIndex: 2 }}>
                  <div style={{ marginBottom: '3rem' }}>
                    {isLocked ? (
                      <Lock size={48} style={{ color: tokens.colors.text.tertiary, marginBottom: '2rem', opacity: 0.1 }} />
                    ) : (
                      <Cpu size={48} style={{ color: isCompleted ? tokens.colors.aurora.cyan : tokens.colors.aurora.red, marginBottom: '2rem' }} className="pulse-slow" />
                    )}
                    <div style={{ color: tokens.colors.text.tertiary, fontSize: '10px', fontFamily: tokens.fonts.mono, letterSpacing: '0.2em', fontWeight: 900 }}>
                      {isCompleted ? 'RIFT_SYNC_VERIFIED' : isLocked ? 'SIGNAL_BLOCK_ACTIVE' : 'AWAITING_NEURAL_LINK...'}
                    </div>
                  </div>
                  
                  <MagneticSurface pull={0.5} padding={50}>
                    <button 
                      className="btn-gen" 
                      disabled={isLocked || isActionLoading}
                      onClick={onAction}
                      style={{ 
                        width: '100%', 
                        justifyContent: 'center',
                        padding: '1.5rem 0',
                        fontSize: '1rem',
                        opacity: (isLocked || isActionLoading) ? 0.2 : 1,
                        background: 'none',
                        border: 'none',
                        borderBottom: `2px solid ${isCompleted ? tokens.colors.aurora.cyan : tokens.colors.text.primary}`,
                        fontWeight: 900,
                        letterSpacing: '0.3em'
                      }}
                    >
                      {isActionLoading ? (
                        <>
                          <Terminal size={20} className="spin" />
                          [ PROCESSING... ]
                        </>
                      ) : isCompleted ? (
                        <>
                          <CheckCircle2 size={18} />
                          [ RE-VERIFY WEIGHTS ]
                        </>
                      ) : isLocked ? (
                        <>
                          <Lock size={18} />
                          [ ENCRYPTED ]
                        </>
                      ) : (
                        <>
                          [ <GeminiSparkle size={18} /> INITIALIZE RIFT ]
                        </>
                      )}
                    </button>
                  </MagneticSurface>
                </div>
                
                {/* Decorative background for the button box - modified to be atmospheric only */}
                <div style={{ 
                  position: 'absolute', 
                  inset: 0, 
                  background: `radial-gradient(circle at 50% 50%, ${isCompleted ? tokens.colors.aurora.cyan : tokens.colors.aurora.red}05 0%, transparent 80%)` 
                }} />
              </div>

              <div style={{ 
                marginTop: '4rem', 
                display: 'flex', 
                gap: '3rem',
                justifyContent: 'center'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', color: tokens.colors.text.tertiary, fontSize: '9px', fontFamily: tokens.fonts.mono, fontWeight: 900 }}>
                  <Database size={12} /> {isLocked ? 'OFFLINE' : 'SYNC_OK'}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', color: tokens.colors.text.tertiary, fontSize: '9px', fontFamily: tokens.fonts.mono, fontWeight: 900 }}>
                  <Network size={12} /> {isLocked ? 'SECURED' : 'P2P_ACTIVE'}
                </div>
              </div>
            </div>
          </SpatialParallax>

        </div>
      </HaloField>

      <style>{`
        .pulse-slow {
          animation: pulse-op 4s infinite;
        }
        @keyframes pulse-op {
          0% { opacity: 0.3; transform: scale(0.95); }
          50% { opacity: 1; transform: scale(1.05); }
          100% { opacity: 0.3; transform: scale(0.95); }
        }
        .spin {
          animation: spin 1s linear infinite;
        }
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </motion.div>
  );
};
