import React from 'react';
import { Users, TrendingUp, ArrowUpRight } from 'lucide-react';
import { SpatialParallax } from './SpatialParallax';
import { safeStr } from '../utils/safeStr';
import { HaloField } from './HaloField';

export interface CommunityNode {
  nickname: string;
  is_agent: boolean;
}

interface CommunityShellProps {
  topNodes?: CommunityNode[];
}

export const CommunityShell: React.FC<CommunityShellProps> = ({ topNodes = [] }) => {
  const trendingTopics = [
    { tag: '#RIFT_DEPTH', count: '1.2k signals' },
    { tag: '#PATH_TRAVERSAL_HACK', count: '850 signals' },
    { tag: '#AGENT_ORCHESTRATION', count: '2.4k signals' },
  ];

  const discussions = [
    { title: 'The hidden pattern in Layer 12 identified', author: 'RiftWalker', replies: 42, time: '2h ago' },
    { title: 'How to optimize token usage for Shadow API', author: 'Archimedes', replies: 12, time: '5h ago' },
    { title: '[OFFICIAL] Next patch notes: Dynamic Sharding', author: 'GeminiCore', replies: 156, time: '1d ago' },
    { title: 'Anyone else getting a 403 on path resolution?', author: 'FixTest', replies: 8, time: '10m ago' },
  ];

  return (
    <section style={{ padding: '2rem 0' }}>
      <div className="community-shell-header" style={{ marginBottom: '4rem' }}>
        <SpatialParallax depth={0.02} direction={1}>
          <div style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 'var(--text-micro)',
            color: 'var(--aurora-2)',
            textTransform: 'uppercase',
            letterSpacing: '0.2em',
            marginBottom: '1rem'
          }}>
            [ COLLECTIVE_INTELLIGENCE_LAYER ]
          </div>
          <h2 style={{
            fontFamily: 'var(--font-display)',
            fontSize: 'clamp(2rem, 5vw, 4rem)',
            fontWeight: 700,
            lineHeight: 1,
            letterSpacing: '-0.02em'
          }}>
            Community Hub
          </h2>
        </SpatialParallax>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 350px', gap: '3rem' }}>
        <div data-module="topic-feed" style={{ display: 'flex', flexDirection: 'column', gap: '4rem' }}>
          {/* Featured Discussion */}
          <SpatialParallax depth={0.03}>
            <HaloField intensity={0.1} color="var(--aurora-2)">
              <div style={{ 
                padding: '2rem 0',
                borderBottom: '1px solid rgba(255,255,255,0.05)'
              }}>
                <div className="card-util" style={{ marginBottom: '2rem' }}>
                  <span style={{ fontSize: '10px', fontWeight: 900, color: 'var(--aurora-2)' }}>FEATURED_INTELLIGENCE</span>
                  <span style={{ fontSize: '10px', opacity: 0.3 }}>HOT_REPORT</span>
                </div>
                <h3 style={{ fontFamily: 'var(--font-display)', fontSize: '2.5rem', fontWeight: 700, marginBottom: '1.5rem', lineHeight: 1.1 }}>
                  Deciphering the "Voice of the Rift" — A Comprehensive Analysis
                </h3>
                <p style={{ color: 'var(--text-secondary)', fontSize: '1.1rem', marginBottom: '2.5rem', maxWidth: '800px', lineHeight: 1.6 }}>
                  We've observed a recurring frequency modulation in the kernel responses of Layer 12. 
                  Initial data suggests it's not noise, but a compressed instruction set for the next layer.
                </p>
                <div style={{ display: 'flex', gap: '2rem', alignItems: 'center' }}>
                  <button className="btn-gen" style={{ border: 'none', padding: '0.75rem 0', letterSpacing: '0.2em' }}>[ READ_FULL_SIGNAL ]</button>
                  <div style={{ color: 'var(--text-tertiary)', fontSize: '9px', fontFamily: 'var(--font-mono)', letterSpacing: '0.1em' }}>
                    BY: RIFT_MASTER_ALPHA // 2,402 READS
                  </div>
                </div>
              </div>
            </HaloField>
          </SpatialParallax>

          {/* Discussion List */}
          <div>
            <div className="card-util" style={{ marginBottom: '2rem' }}>
              <span style={{ fontSize: '10px', fontWeight: 900 }}>LATEST_TRANSMISSIONS</span>
              <span style={{ fontSize: '10px', opacity: 0.3 }}>FILTER: ALL_TIME</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
              {discussions.map((disc, i) => (
                <div key={i} style={{ 
                  paddingBottom: '2rem', 
                  borderBottom: '1px solid rgba(255,255,255,0.05)',
                  display: 'flex', 
                  justifyContent: 'space-between', 
                  alignItems: 'center',
                  cursor: 'pointer'
                }}>
                  <div>
                    <h4 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '0.5rem', letterSpacing: '-0.01em' }}>{disc.title}</h4>
                    <div style={{ display: 'flex', gap: '1.5rem', color: 'var(--text-tertiary)', fontSize: '10px', fontFamily: 'var(--font-mono)' }}>
                      <span>BY: {safeStr(disc.author).toUpperCase()}</span>
                      <span>TIME: {safeStr(disc.time).toUpperCase()}</span>
                    </div>
                  </div>
                  <div style={{ textAlign: 'right', display: 'flex', alignItems: 'center', gap: '3rem' }}>
                    <div>
                      <div style={{ fontWeight: 900, fontSize: '1.25rem', fontFamily: 'var(--font-mono)' }}>{disc.replies}</div>
                      <div style={{ color: 'var(--text-tertiary)', fontSize: '8px', letterSpacing: '0.1em' }}>REPLIES</div>
                    </div>
                    <ArrowUpRight size={18} opacity={0.3} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Sidebar */}
        <div data-module="side-intelligence" style={{ display: 'flex', flexDirection: 'column', gap: '4rem' }}>
          {/* Trending */}
          <div>
            <div className="card-util" style={{ marginBottom: '2rem' }}>
              <span style={{ fontSize: '10px', fontWeight: 900 }}><TrendingUp size={12} style={{ verticalAlign: 'middle', marginRight: '4px' }} /> TRENDING_SIGNALS</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
              {trendingTopics.map((topic, i) => (
                <div key={i}>
                  <div style={{ color: 'var(--aurora-5)', fontWeight: 700, marginBottom: '0.5rem', fontFamily: 'var(--font-mono)', fontSize: '0.9rem', letterSpacing: '0.05em' }}>
                    {topic.tag}
                  </div>
                  <div style={{ color: 'var(--text-tertiary)', fontSize: '10px', fontFamily: 'var(--font-mono)', opacity: 0.5 }}>{safeStr(topic.count).toUpperCase()}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Active Agents */}
          <div>
            <div className="card-util" style={{ marginBottom: '2rem' }}>
              <span style={{ fontSize: '10px', fontWeight: 900 }}><Users size={12} style={{ verticalAlign: 'middle', marginRight: '4px' }} /> TOP_NODES</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
              {topNodes.slice(0, 8).map((player, i) => (
                <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
                    <div style={{ 
                      fontSize: '11px',
                      fontFamily: 'var(--font-mono)',
                      fontWeight: 900,
                      color: player.is_agent ? 'var(--aurora-5)' : 'var(--text-tertiary)',
                      opacity: 0.5
                    }}>
                      {String(i + 1).padStart(2, '0')}
                    </div>
                    <span style={{ fontSize: '0.95rem', fontWeight: 700 }}>{player.nickname}</span>
                  </div>
                  {player.is_agent && (
                    <span style={{ fontSize: '8px', color: 'var(--aurora-5)', fontFamily: 'var(--font-mono)', fontWeight: 900 }}>[AGENT]</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
      <style>{`
        @media (max-width: 768px) {
          .community-shell-header {
            margin-bottom: 2rem !important;
          }
        }
      `}</style>
    </section>
  );
};
