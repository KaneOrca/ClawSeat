import React, { useLayoutEffect, useRef, useState } from 'react';
import { usePhysicsRegistry } from '../context/PhysicsContext';

interface ScrambleTextProps {
  text: string;
  as?: any;
  className?: string;
  style?: React.CSSProperties;
}

const CHARS = '!<>-_\\/[]{}—=+*^?#________';

/**
 * ScrambleText: Animated text reveal with random character scramble.
 *
 * Uses a closure-local generation flag (not a ref) to ensure only the
 * current effect generation can write state. When `text` changes, the
 * previous generation's RAF callbacks self-terminate immediately.
 */
export function ScrambleText({ text, as: Tag = 'span', className, style }: ScrambleTextProps) {
  const [displayText, setDisplayText] = useState(text);
  const { environment, setEnvironment } = usePhysicsRegistry();
  const environmentRef = useRef(environment);
  environmentRef.current = environment;

  useLayoutEffect(() => {
    // Immediately sync to target text — prevents stale display between generations
    setDisplayText(text);
    const prevAmp = environmentRef.current.waveAmplitude ?? 60;
    setEnvironment({ waveAmplitude: 85 });

    // Generation-local flag — NOT a ref, so each effect closure has its own copy
    let isCurrentGen = true;

    const queue: { to: string; start: number; end: number; char: string }[] = [];
    for (let i = 0; i < text.length; i++) {
      const start = Math.floor(Math.random() * 40);
      const end = start + Math.floor(Math.random() * 40);
      queue.push({ to: text[i], start, end, char: '' });
    }

    let frame = 0;

    const update = () => {
      if (!isCurrentGen) return;

      let output = '';
      let complete = 0;

      for (let i = 0; i < queue.length; i++) {
        const item = queue[i];
        if (frame >= item.end) {
          complete++;
          output += item.to;
        } else if (frame >= item.start) {
          if (!item.char || Math.random() < 0.28) {
            item.char = CHARS[Math.floor(Math.random() * CHARS.length)];
          }
          output += item.char;
        } else {
          // Before scramble starts for this char: show final character (constant length)
          output += item.to;
        }
      }

      setDisplayText(output);
      frame++;

      if (complete < queue.length && isCurrentGen) {
        requestAnimationFrame(update);
      } else if (isCurrentGen) {
        setEnvironment({ waveAmplitude: prevAmp });
      }
    };

    requestAnimationFrame(update);

    return () => {
      isCurrentGen = false;
      setEnvironment({ waveAmplitude: prevAmp });
    };
  }, [setEnvironment, text]);

  const Element = Tag as any;

  return (
    <Element className={className} style={style}>
      {displayText || text}
    </Element>
  );
}
