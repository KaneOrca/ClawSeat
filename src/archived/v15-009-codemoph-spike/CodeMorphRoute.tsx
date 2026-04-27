import React, { useEffect } from 'react';
import { CodeMorphReveal } from './CodeMorphReveal';
import { BitmaskPhysic } from '../../../components/text-physics/BitmaskPhysic';
import { usePhysicsRegistry } from '../../../context/PhysicsContext';
import { tokens } from '../../../design/tokens';

const STEPS = [
  "const keywords = extract('user query');",
  "const elements = analyze(keywords);",
  'return synthesize(elements);',
];

export const CodeMorphRoute: React.FC = () => {
  const { setEnvironment } = usePhysicsRegistry();

  useEffect(() => {
    setEnvironment({ waveAmplitude: 60, opacity: 0.25 });
    return () => setEnvironment({ waveAmplitude: 60, opacity: 0.15 });
  }, [setEnvironment]);

  return (
    <div
      className="spike-code-morph-route"
      style={{
        position: 'relative',
        minHeight: '100vh',
        background: tokens.colors.base,
        color: tokens.colors.text.primary,
        overflow: 'hidden',
      }}
    >
      <div style={{ position: 'fixed', inset: 0, zIndex: 0, pointerEvents: 'none' }}>
        <BitmaskPhysic opacity={0.25} />
      </div>

      <div
        style={{
          position: 'absolute',
          top: '1.5rem',
          left: '1.5rem',
          zIndex: 2,
          fontFamily: tokens.fonts.mono,
          fontSize: tokens.sizes.small,
          color: tokens.colors.text.secondary,
          opacity: 0.5,
          letterSpacing: '0.08em',
        }}
      >
        [ V15-009 SPIKE / CODE MORPH POC ]
      </div>

      <main
        style={{
          minHeight: '100vh',
          display: 'grid',
          placeItems: 'center',
          padding: '2rem',
          position: 'relative',
          zIndex: 1,
        }}
      >
        <div style={{ width: 'clamp(400px, 50vw, 700px)', background: 'transparent' }}>
          <CodeMorphReveal steps={STEPS} />
        </div>
      </main>
    </div>
  );
};
