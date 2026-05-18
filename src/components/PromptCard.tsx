import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Check, Clipboard } from 'lucide-react';
import { prepareWithSegments, layoutNextLine, type LayoutCursor } from '@chenglou/pretext';
import { tokens } from '../design/tokens';
import { useObstacle } from '../hooks/useObstacle';
import { useMousePush } from '../hooks/useMousePush';
import { useWaveRipple } from '../hooks/useWaveRipple';
import { assignRefs } from '../utils/assignRefs';
import type { VariantType } from '../context/ArenaContext';

interface PromptCardProps {
  variant: VariantType;
  heading: string;
  body: string;
  copyLabel: string;
  copiedLabel: string;
  onTrigger: () => void;
  className?: string;
  style?: React.CSSProperties;
}

interface PromptLineProps {
  text: string;
  index: number;
  visible: boolean;
  fontDef: string;
  color: string;
  delayMs: number;
  lineHeight: number;
}

interface PromptHeadingProps {
  heading: string;
  visible: boolean;
  variant: VariantType;
}

interface PromptCopyButtonProps {
  label: string;
  copiedLabel: string;
  variant: VariantType;
  onCopy: (event: React.MouseEvent<HTMLButtonElement>) => Promise<void>;
  isCopied: boolean;
  isPressed: boolean;
  setIsPressed: React.Dispatch<React.SetStateAction<boolean>>;
}

const VARIANT_THEME: Record<VariantType, {
  shellBg: string;
  shellBorder: string;
  bodyColor: string;
  headingColor: string;
  buttonBg: string;
  buttonBorder: string;
  buttonColor: string;
}> = {
  v2: {
    shellBg: 'rgba(253, 252, 240, 0.8)',
    shellBorder: 'rgba(26, 26, 26, 0.16)',
    bodyColor: tokens.colors.manuscript.ink,
    headingColor: tokens.colors.manuscript.red,
    buttonBg: 'rgba(26, 26, 26, 0.04)',
    buttonBorder: 'rgba(26, 26, 26, 0.18)',
    buttonColor: tokens.colors.manuscript.ink,
  },
  v3: {
    shellBg: 'rgba(3, 7, 12, 0.56)',
    shellBorder: 'rgba(0, 240, 255, 0.28)',
    bodyColor: tokens.colors.aurora.cyan,
    headingColor: tokens.colors.aurora.blue,
    buttonBg: 'rgba(0, 240, 255, 0.06)',
    buttonBorder: 'rgba(0, 240, 255, 0.24)',
    buttonColor: tokens.colors.aurora.cyan,
  },
};

function useResizeWidth(ref: React.RefObject<HTMLElement | null>, fallbackWidth: number) {
  const [width, setWidth] = useState(fallbackWidth);

  useEffect(() => {
    const node = ref.current;
    if (!node || typeof ResizeObserver === 'undefined') return;

    const observer = new ResizeObserver(entries => {
      const entry = entries[0];
      if (!entry) return;
      setWidth(Math.max(0, Math.floor(entry.contentRect.width)));
    });

    observer.observe(node);
    return () => observer.disconnect();
  }, [ref]);

  return width;
}

export const PromptCard: React.FC<PromptCardProps> = ({
  variant,
  heading,
  body,
  copyLabel,
  copiedLabel,
  onTrigger,
  className = '',
  style,
}) => {
  const shellRef = useObstacle() as React.RefObject<HTMLElement>;
  const contentRef = useRef<HTMLDivElement>(null);
  const ripple = useWaveRipple();
  const theme = VARIANT_THEME[variant];
  const fontDef = variant === 'v2'
    ? `italic 400 16px ${tokens.fonts.manuscript}`
    : `600 15px ${tokens.fonts.display}`;
  const bodyLineHeight = variant === 'v2' ? 1.85 : 1.72;
  const fallbackWidth = variant === 'v2' ? 620 : 560;
  const contentWidth = useResizeWidth(contentRef, fallbackWidth);
  const displayBody = useMemo(() => {
    const bodyLines = body.split('\n');
    if (bodyLines[0]?.includes(heading)) {
      return bodyLines.slice(1).join('\n').replace(/^\n+/, '');
    }
    return body;
  }, [body, heading]);
  const copyText = useMemo(() => body, [body]);
  const prepared = useMemo(() => prepareWithSegments(displayBody, fontDef), [displayBody, fontDef]);
  const [lines, setLines] = useState<string[]>([]);
  const [visible, setVisible] = useState(false);
  const [copyState, setCopyState] = useState<'idle' | 'copied'>('idle');
  const [isPressed, setIsPressed] = useState(false);
  const copyTimerRef = useRef<number | null>(null);

  useEffect(() => {
    const nextLines: string[] = [];
    let cursor: LayoutCursor = { segmentIndex: 0, graphemeIndex: 0 };
    const width = Math.max(320, contentWidth);

    while (true) {
      const line = layoutNextLine(prepared, cursor, width);
      if (!line) break;
      nextLines.push(line.text);
      cursor = line.end;
      if (nextLines.length > 240) break;
    }

    setLines(nextLines.length > 0 ? nextLines : [displayBody]);
  }, [contentWidth, displayBody, prepared]);

  useEffect(() => {
    setVisible(false);
    const frame = requestAnimationFrame(() => setVisible(true));
    return () => cancelAnimationFrame(frame);
  }, [displayBody, contentWidth, variant]);

  useEffect(() => {
    return () => {
      if (copyTimerRef.current !== null) {
        window.clearTimeout(copyTimerRef.current);
      }
    };
  }, []);

  const handleTrigger = () => {
    onTrigger();
  };

  const handleCopy = async (event: React.MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();
    try {
      await navigator.clipboard.writeText(copyText);
      setCopyState('copied');
      if (copyTimerRef.current !== null) {
        window.clearTimeout(copyTimerRef.current);
      }
      copyTimerRef.current = window.setTimeout(() => {
        setCopyState('idle');
        copyTimerRef.current = null;
      }, 2000);
    } catch {
      setCopyState('idle');
    }
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLElement>) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      handleTrigger();
    }
  };

  return (
    <section
      ref={shellRef as React.RefObject<HTMLElement>}
      className={className}
      data-functional-text="true"
      data-prompt-card={variant}
      aria-label={heading}
      onClick={handleTrigger}
      onKeyDown={handleKeyDown}
      onPointerEnter={ripple.onPointerEnter}
      onTouchStart={ripple.onTouchStart}
      role="button"
      tabIndex={0}
      style={{
        boxSizing: 'border-box',
        width: '100%',
        padding: 'clamp(1rem, 2.1vw, 1.35rem)',
        border: `1px solid ${theme.shellBorder}`,
        background: theme.shellBg,
        color: theme.bodyColor,
        cursor: 'pointer',
        outline: 'none',
        transition: 'border-color 180ms ease, background 180ms ease, transform 180ms ease',
        ...style,
      }}
    >
      <div
        ref={contentRef}
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: variant === 'v2' ? '0.9rem' : '0.75rem',
          width: '100%',
        }}
      >
        <PromptHeading heading={heading} visible={visible} variant={variant} />

        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: variant === 'v2' ? '0.45rem' : '0.35rem',
          }}
        >
          {lines.map((line, index) => (
            <PromptLine
              key={`${index}-${line.slice(0, 20)}`}
              text={line}
              index={index}
              visible={visible}
              fontDef={fontDef}
              color={theme.bodyColor}
              delayMs={180 + index * 60}
              lineHeight={bodyLineHeight}
            />
          ))}
        </div>

        <PromptCopyButton
          label={copyLabel}
          copiedLabel={copiedLabel}
          variant={variant}
          onCopy={handleCopy}
          isCopied={copyState === 'copied'}
          isPressed={isPressed}
          setIsPressed={setIsPressed}
        />
      </div>
    </section>
  );
};

const PromptHeading: React.FC<PromptHeadingProps> = ({ heading, visible, variant }) => {
  const ref = useObstacle() as React.RefObject<HTMLDivElement>;
  const mousePushRef = useMousePush();
  const theme = VARIANT_THEME[variant];

  return (
    <div
      data-functional-text="true"
      ref={node => assignRefs(node, ref, mousePushRef)}
      style={{
        display: 'block',
        fontFamily: tokens.fonts.mono,
        fontSize: '10px',
        letterSpacing: '0.28em',
        textTransform: 'uppercase',
        color: theme.headingColor,
        opacity: visible ? 1 : 0,
        transform: visible ? 'translateY(0)' : 'translateY(6px)',
        transition: 'opacity 360ms cubic-bezier(0.16, 1, 0.3, 1), transform 360ms cubic-bezier(0.16, 1, 0.3, 1)',
      }}
    >
      {heading}
    </div>
  );
};

const PromptLine: React.FC<PromptLineProps> = ({
  text,
  index,
  visible,
  fontDef,
  color,
  delayMs,
  lineHeight,
}) => {
  const ref = useObstacle() as React.RefObject<HTMLDivElement>;
  const mousePushRef = useMousePush();

  return (
    <div
      data-functional-text="true"
      ref={node => assignRefs(node, ref, mousePushRef)}
      style={{
        display: 'block',
        whiteSpace: 'pre-wrap',
        font: fontDef,
        lineHeight,
        color,
        opacity: visible ? 1 : 0,
        transform: visible ? 'translateY(0)' : 'translateY(7px)',
        transition: 'opacity 420ms cubic-bezier(0.16, 1, 0.3, 1), transform 420ms cubic-bezier(0.16, 1, 0.3, 1)',
        transitionDelay: `${delayMs + index * 4}ms`,
      }}
    >
      {text || '\u00a0'}
    </div>
  );
};

const PromptCopyButton: React.FC<PromptCopyButtonProps> = ({
  label,
  copiedLabel,
  variant,
  onCopy,
  isCopied,
  isPressed,
  setIsPressed,
}) => {
  const ref = useObstacle() as React.RefObject<HTMLButtonElement>;
  const mousePushRef = useMousePush();
  const theme = VARIANT_THEME[variant];
  const Icon = isCopied ? Check : Clipboard;

  return (
    <button
      data-functional-text="true"
      ref={node => assignRefs(node, ref, mousePushRef)}
      type="button"
      aria-label={isCopied ? copiedLabel : label}
      title={isCopied ? copiedLabel : label}
      onClick={onCopy}
      onMouseDown={() => setIsPressed(true)}
      onMouseUp={() => setIsPressed(false)}
      onMouseLeave={() => setIsPressed(false)}
      onBlur={() => setIsPressed(false)}
      style={{
        alignSelf: 'flex-start',
        display: 'inline-flex',
        alignItems: 'center',
        gap: '0.55rem',
        appearance: 'none',
        padding: '0.55rem 0.8rem',
        border: `1px solid ${theme.buttonBorder}`,
        background: theme.buttonBg,
        color: theme.buttonColor,
        borderRadius: 0,
        fontFamily: tokens.fonts.mono,
        fontSize: '10px',
        letterSpacing: '0.14em',
        textTransform: 'uppercase',
        cursor: 'pointer',
        outline: 'none',
        transform: `scale(${isPressed ? 1.03 : 1})`,
        transition: 'transform 120ms ease, border-color 180ms ease, background 180ms ease, color 180ms ease',
      }}
    >
      <Icon size={13} strokeWidth={2.2} />
      <span data-functional-text="true">{isCopied ? copiedLabel : label}</span>
    </button>
  );
};
