import React from 'react';
import { tokens } from '../../../design/tokens';

/**
 * WatchViewV2: Manuscript Marginalia
 * Keywords: narrative side voice, editorial events, observer notes.
 */
export const WatchViewV2: React.FC = () => {
  return (
    <div className="page-watch variant-v2" style={{ padding: '4rem', color: 'white' }}>
      <div style={{ maxWidth: '1000px', margin: '0 auto' }}>
        <h1 style={{ fontFamily: tokens.fonts.display, fontSize: '3rem', marginBottom: '4rem' }}>Observer's Log</h1>
        
        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '4rem' }}>
          <div>
            <div style={{ borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '1rem', marginBottom: '2rem', fontSize: '12px', opacity: 0.5 }}>
              [ CHRONOLOGICAL_FEED ]
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
              <p style={{ fontSize: '1.25rem', color: tokens.colors.text.secondary }}>
                <span style={{ color: tokens.colors.aurora.blue }}>[12:04]</span> Agent_492 has breached Layer 04. The neural patterns suggest a recursive strategy.
              </p>
              <p style={{ fontSize: '1.25rem', color: tokens.colors.text.secondary }}>
                <span style={{ color: tokens.colors.aurora.blue }}>[12:02]</span> System reported a minor fluctuation in the rift's stability.
              </p>
            </div>
          </div>

          <div style={{ background: 'rgba(255,255,255,0.02)', padding: '2rem', borderRadius: '16px' }}>
            <h3 style={{ fontSize: '14px', marginBottom: '2rem', opacity: 0.6 }}>[OBSERVER_NOTES]</h3>
            <p style={{ fontSize: '13px', lineHeight: 1.6, fontStyle: 'italic', color: tokens.colors.text.tertiary }}>
              The Descent continues. Many agents are stalling at the pattern-matching phase of Layer 03.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
