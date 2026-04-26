import React from 'react';
import { useArena } from '../../../context/ArenaContext';
import { tokens } from '../../../design/tokens';

/**
 * ChallengeDetailV2: Manuscript Marginalia
 * Keywords: editorial body, margin notes, text-responsive action zone.
 */
export const ChallengeDetailV2: React.FC = () => {
  const { currentChallengeId, setChallengeId } = useArena();

  return (
    <div className="page-challenge-detail variant-v2" style={{ padding: '4rem', color: 'white' }}>
      <button onClick={() => setChallengeId(null)} style={{ background: 'none', border: 'none', color: tokens.colors.text.tertiary, cursor: 'pointer', marginBottom: '4rem' }}>
        [ BACK_TO_MANUSCRIPT ]
      </button>

      <div className="v2-challenge-detail-grid" style={{ maxWidth: '900px', margin: '0 auto', display: 'grid', gridTemplateColumns: '3fr 1fr', gap: '4rem' }}>
        <div style={{ borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '2rem' }}>
          <h1 style={{ fontFamily: tokens.fonts.display, fontSize: '3rem', marginBottom: '2rem' }}>Layer {currentChallengeId}: Inscription</h1>
          <div style={{ fontSize: '1.25rem', lineHeight: 1.8, color: tokens.colors.text.secondary }}>
            <p>This is the V2 Challenge Detail view. It focuses on editorial layout where the challenge description is treated as body text, and metadata or hints are margin notes.</p>
          </div>
        </div>

        <div style={{ fontSize: '12px', opacity: 0.5, fontFamily: tokens.fonts.mono }}>
          <div style={{ marginBottom: '2rem' }}>
            [META_INFO]<br/>
            DIFFICULTY: HIGH<br/>
            DECRYPT_RATE: 14%
          </div>
          <div>
            [ANNOTATION]<br/>
            "Observe the white space between characters for hidden signals."
          </div>
        </div>
      </div>

      <style>{`
        @media (max-width: 768px) {
          .page-challenge-detail.variant-v2 {
            padding: 1rem !important;
          }
          .v2-challenge-detail-grid {
            grid-template-columns: 1fr !important;
            gap: 1.5rem !important;
            max-width: 100% !important;
          }
        }
      `}</style>
    </div>
  );
};
