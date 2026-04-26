import React from 'react';
import { ScrambleText } from './ScrambleText';
import { PretextEditorial } from './PretextEditorial';
import { MagneticSurface } from './MagneticSurface';
import { SpatialParallax } from './SpatialParallax';
import { HaloField } from './HaloField';
import { FlagshipCard, NeuralBadge } from '../design/VisualPrimitive';
import { tokens } from '../design/tokens';
import { Terminal, ChevronRight, Activity, Cpu, Globe, ArrowDown } from 'lucide-react';

interface HeroSectionProps {
  orbPos: { x: number; y: number; r: number };
  onInitialize?: () => void;
  buttonLabel?: string;
}

const HERO_INTEL = `The Rift is a synthetic dimension where intelligence is the only currency. As neural architectures evolve, the boundaries of standard computation dissolve into fluid logic. Arena participants must navigate these architectural voids, resolving multi-layered challenges through superior orchestration and pattern recognition. Your descent starts here.`;

const QUOTE = `Intelligence is not just about solving problems; it's about the elegance of the journey through the void.`;

export const HeroSection: React.FC<HeroSectionProps> = ({ onInitialize, buttonLabel }) => {
  return (
    <section style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', position: 'relative' }}>
      <HaloField intensity={0.3} color={tokens.colors.aurora.blue} className="w-full flex-1">
        <div className="container" style={{ padding: '10rem 0', position: 'relative', zIndex: 10 }}>
          
          <div style={{ display: 'grid', gridTemplateColumns: '1.6fr 1fr', gap: '8rem', alignItems: 'center' }}>
            
            {/* LEFT: FLAGSHIP TYPOGRAPHY */}
            <div>
              <SpatialParallax depth={0.02} direction={1}>
                <div style={{ marginBottom: '2.5rem' }}>
                  <NeuralBadge text="NEURAL_SESSION_READY" color={tokens.colors.aurora.cyan} />
                </div>
                
                <h1 style={{
                  fontFamily: tokens.fonts.display,
                  fontSize: 'clamp(5rem, 12vw, 10rem)',
                  fontWeight: 700,
                  lineHeight: 0.75,
                  letterSpacing: '-0.06em',
                  marginBottom: '5rem',
                  color: tokens.colors.text.primary
                }}>
                  <div style={{ opacity: 0.3, fontSize: '0.3em', letterSpacing: '0.2em', marginBottom: '1rem' }}>THE</div>
                  <ScrambleText text="INTELLIGENT" className="gemini-text" /><br/>
                  <ScrambleText text="RIFT" />
                </h1>

                <div style={{ maxWidth: '650px', marginBottom: '6rem' }}>
                  <PretextEditorial 
                    text={HERO_INTEL}
                    width={650}
                    lineHeight={42}
                    fontDef="400 26px Satoshi"
                    color={tokens.colors.text.secondary}
                    delay={0.4}
                  />
                </div>

                <div style={{ display: 'flex', gap: '3rem', alignItems: 'center' }}>
                  <MagneticSurface pull={0.45} padding={60}>
                    <button className="btn-gen" onClick={onInitialize} style={{ padding: '1.75rem 5rem', fontSize: '1.1rem' }}>
                      <Terminal size={24} />
                      {buttonLabel || 'Begin Descent'}
                    </button>
                  </MagneticSurface>
                  
                  <MagneticSurface pull={0.2} padding={30}>
                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '1rem',
                      color: tokens.colors.text.tertiary,
                      fontFamily: tokens.fonts.mono,
                      fontSize: '12px',
                      cursor: 'pointer',
                      transition: 'color 0.3s ease',
                      fontWeight: 700
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.color = tokens.colors.text.primary}
                    onMouseLeave={(e) => e.currentTarget.style.color = tokens.colors.text.tertiary}
                    >
                      [ ACCESS_RIFT_INTEL ] <ChevronRight size={18} />
                    </div>
                  </MagneticSurface>
                </div>
              </SpatialParallax>
            </div>

            {/* RIGHT: MULTI-LAYERED ARCHITECTURE */}
            <div style={{ position: 'relative' }}>
              <SpatialParallax depth={0.1} direction={-1} tilt>
                <FlagshipCard style={{ padding: '4rem', borderLeft: `8px solid ${tokens.colors.aurora.blue}` }}>
                  <div className="card-util" style={{ borderBottomColor: 'rgba(255,255,255,0.1)', marginBottom: '3rem' }}>
                    <span>RIFT_METADATA_STREAM</span>
                    <span>v5.1.0_LATEST</span>
                  </div>
                  
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4rem' }}>
                    {[
                      { icon: <Activity />, label: 'LIVE_NODES', value: '1,402 / 2,000', color: tokens.colors.aurora.blue },
                      { icon: <Globe />, label: 'SYNC_STABILITY', value: '99.98%', color: tokens.colors.aurora.cyan },
                      { icon: <Cpu />, label: 'COMPUTE_LOAD', value: 'OPTIMAL', color: tokens.colors.aurora.red },
                    ].map((stat, i) => (
                      <div key={i} style={{ display: 'flex', gap: '2rem', alignItems: 'center' }}>
                        <div style={{ 
                          width: '56px', 
                          height: '56px', 
                          borderRadius: '16px', 
                          background: `${stat.color}15`, 
                          display: 'flex', 
                          alignItems: 'center', 
                          justifyContent: 'center', 
                          color: stat.color,
                          border: `1px solid ${stat.color}30`
                        }}>
                          {React.cloneElement(stat.icon as React.ReactElement<any>, { size: 28 })}

                        </div>
                        <div>
                          <div style={{ color: tokens.colors.text.tertiary, fontSize: '11px', fontFamily: tokens.fonts.mono, letterSpacing: '0.1em' }}>{stat.label}</div>
                          <div style={{ fontSize: '2rem', fontWeight: 700, color: tokens.colors.text.primary }}>{stat.value}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </FlagshipCard>
              </SpatialParallax>

              {/* FLOATING PULL QUOTE */}
              <div style={{ position: 'absolute', top: '-15%', left: '-20%', width: '300px' }}>
                <SpatialParallax depth={0.15} direction={1}>
                  <div style={{ 
                    padding: '2rem', 
                    borderLeft: `2px solid ${tokens.colors.aurora.purple}`,
                    fontFamily: tokens.fonts.body,
                    fontStyle: 'italic',
                    fontSize: '1.1rem',
                    color: tokens.colors.text.tertiary,
                    background: 'rgba(0,0,0,0.2)',
                    backdropFilter: 'blur(10px)',
                    borderRadius: '0 12px 12px 0'
                  }}>
                    <PretextEditorial 
                      text={QUOTE}
                      width={260}
                      lineHeight={24}
                      fontDef="italic 400 18px Satoshi"
                      color={tokens.colors.text.tertiary}
                      delay={1.2}
                    />
                  </div>
                </SpatialParallax>
              </div>
            </div>

          </div>
        </div>

        {/* SCROLL INDICATOR */}
        <div style={{ 
          position: 'absolute', 
          bottom: '4rem', 
          left: '50%', 
          transform: 'translateX(-50%)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '1rem',
          color: tokens.colors.text.tertiary,
          fontFamily: tokens.fonts.mono,
          fontSize: '10px',
          letterSpacing: '0.2em'
        }}>
          <span className="pulse-slow">DESCEND_FOR_LEADERBOARD</span>
          <ArrowDown size={16} className="bounce" />
        </div>
      </HaloField>

      <style>{`
        .bounce {
          animation: bounce-anim 2s infinite;
        }
        @keyframes bounce-anim {
          0%, 20%, 50%, 80%, 100% { transform: translateY(0); }
          40% { transform: translateY(-10px); }
          60% { transform: translateY(-5px); }
        }
        .pulse-slow {
          animation: pulse-simple 3s infinite;
        }
        @keyframes pulse-simple {
          0% { opacity: 0.3; }
          50% { opacity: 1; }
          100% { opacity: 0.3; }
        }
      `}</style>
    </section>
  );
};
