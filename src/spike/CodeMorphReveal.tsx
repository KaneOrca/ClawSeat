import React, { useEffect, useMemo, useState } from 'react';
import { createHighlighter } from 'shiki';
import type { HighlighterCore } from 'shiki/core';
import { ShikiMagicMove } from 'shiki-magic-move/react';
import 'shiki-magic-move/dist/style.css';
import { useObstacle } from '../hooks/useObstacle';
import { tokens } from '../design/tokens';

interface CodeMorphRevealProps {
  steps: string[];
  autoAdvanceMs?: number;
  stepIndex?: number;
}

const THEME = 'github-dark';
const LANG = 'typescript';

export const CodeMorphReveal: React.FC<CodeMorphRevealProps> = ({
  steps,
  autoAdvanceMs = 1500,
  stepIndex,
}) => {
  const obstacleRef = useObstacle() as React.RefObject<HTMLDivElement>;
  const [highlighter, setHighlighter] = useState<HighlighterCore | null>(null);
  const [internalStep, setInternalStep] = useState(0);

  useEffect(() => {
    let alive = true;

    createHighlighter({
      themes: [THEME],
      langs: [LANG],
    }).then(nextHighlighter => {
      if (alive) setHighlighter(nextHighlighter);
    });

    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    if (stepIndex !== undefined || steps.length <= 1) return;

    const interval = window.setInterval(() => {
      setInternalStep(current => (current + 1) % steps.length);
    }, autoAdvanceMs);

    return () => window.clearInterval(interval);
  }, [autoAdvanceMs, stepIndex, steps.length]);

  const activeStep = useMemo(() => {
    if (steps.length === 0) return '';
    const requestedStep = stepIndex ?? internalStep;
    const boundedStep = ((requestedStep % steps.length) + steps.length) % steps.length;
    return steps[boundedStep];
  }, [internalStep, stepIndex, steps]);

  return (
    <>
      <div
        ref={obstacleRef}
        className="code-morph-obstacle"
        style={{
          width: '100%',
          background: 'transparent',
          color: tokens.colors.text.primary,
          fontFamily: tokens.fonts.mono,
          fontSize: tokens.sizes.small,
          lineHeight: 1.8,
        }}
      >
        {highlighter ? (
          <ShikiMagicMove
            highlighter={highlighter}
            lang={LANG}
            theme={THEME}
            code={activeStep}
            options={{ duration: 800, stagger: 0.25, lineNumbers: false }}
            className="code-morph-reveal"
          />
        ) : (
          <pre style={{ margin: 0, color: tokens.colors.text.tertiary }}>{activeStep}</pre>
        )}
      </div>
      <style>{`
        .code-morph-reveal {
          background: transparent !important;
          overflow: visible !important;
        }
        .code-morph-reveal pre,
        .code-morph-reveal code {
          background: transparent !important;
          font-family: ${tokens.fonts.mono} !important;
          white-space: pre-wrap !important;
        }
      `}</style>
    </>
  );
};

export const codeMorphSpikeMeta = {
  theme: THEME,
  lang: LANG,
} as const;
