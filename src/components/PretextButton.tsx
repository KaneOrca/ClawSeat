import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { usePhysicsRegistry, type EnvironmentSettings } from '../context/PhysicsContext';
import { useObstacle } from '../hooks/useObstacle';

export type FunctionalTextEngine = 'labyrinth' | 'bitmask' | 'manuscript' | 'chorus';
export type FunctionalTextState = 'FIELD_IDLE' | 'TERM_SOLOIST_ACTIVE' | 'SOLOIST_PULSE_NAV';

export interface FunctionalTextConfig {
  /** Literal visible text. The same string is measured as an obstacle and may become Soloist text. */
  label: string;
  /** Physics engine contract this text is meant to participate in. */
  engine: FunctionalTextEngine;
  /** Hover/focus activation side effect, usually route preview or analytics. */
  onActivate?: () => void;
  /** Hover/focus exit side effect. */
  onDeactivate?: () => void;
  /** Click/keyboard trigger side effect, usually route navigation. */
  onTrigger?: () => void;
  /** Labyrinth/Chorus insertion row. Retained for compatibility; no-op now. */
  physicsLineIndex?: number;
  /** Reserved for callers with a known rect; current implementation prefers live DOM measurement. */
  obstacleRect?: DOMRect;
  /** Stable Soloist id for backward-compat configs. */
  soloistId?: string;
  /** Soloist foreground color. */
  color?: string;
  /** Soloist opacity. */
  opacity?: number;
  /** Disable DOM rect obstacle registration while preserving normal button behavior. */
  obstacle?: boolean;
  /** Environment patch while hovered/focused. */
  activationEnvironment?: Partial<EnvironmentSettings>;
  /** Environment patch while clicked/triggered. */
  triggerEnvironment?: Partial<EnvironmentSettings>;
  /** Environment patch after deactivate or pulse decay. */
  idleEnvironment?: Partial<EnvironmentSettings>;
  /** How long trigger state remains visible before returning to idle. */
  pulseDurationMs?: number;
}

export interface UseFunctionalTextObstacleResult {
  ref: React.RefObject<HTMLElement>;
  state: FunctionalTextState;
  active: boolean;
  eventHandlers: {
    onMouseEnter: () => void;
    onMouseLeave: () => void;
    onFocus: () => void;
    onBlur: () => void;
    onClick: () => void;
  };
  dataAttributes: {
    'data-pretext-engine': FunctionalTextEngine;
    'data-pretext-state': FunctionalTextState;
  };
}

const DEFAULT_ACTIVE_ENVIRONMENT: Partial<EnvironmentSettings> = {
  waveAmplitude: 90,
  opacity: 0.22,
};

const DEFAULT_TRIGGER_ENVIRONMENT: Partial<EnvironmentSettings> = {
  waveAmplitude: 120,
  opacity: 0.28,
};

const DEFAULT_IDLE_ENVIRONMENT: Partial<EnvironmentSettings> = {
  waveAmplitude: 60,
  opacity: 0.15,
};

export function useFunctionalTextObstacle(config: FunctionalTextConfig): UseFunctionalTextObstacleResult {
  const obstacleRef = useObstacle(config.obstacle !== false) as React.RefObject<HTMLElement>;
  const { setEnvironment } = usePhysicsRegistry();
  const [state, setState] = useState<FunctionalTextState>('FIELD_IDLE');
  const pulseTimerRef = useRef<number | null>(null);

  const clearPulseTimer = useCallback(() => {
    if (pulseTimerRef.current !== null) {
      window.clearTimeout(pulseTimerRef.current);
      pulseTimerRef.current = null;
    }
  }, []);

  useEffect(() => {
    return () => {
      clearPulseTimer();
    };
  }, [clearPulseTimer]);

  const activate = useCallback(() => {
    clearPulseTimer();
    setState('TERM_SOLOIST_ACTIVE');
    setEnvironment(config.activationEnvironment ?? DEFAULT_ACTIVE_ENVIRONMENT);
    config.onActivate?.();
  }, [clearPulseTimer, config, setEnvironment]);

  const deactivate = useCallback(() => {
    if (state === 'SOLOIST_PULSE_NAV') return;
    setState('FIELD_IDLE');
    setEnvironment(config.idleEnvironment ?? DEFAULT_IDLE_ENVIRONMENT);
    config.onDeactivate?.();
  }, [config, setEnvironment, state]);

  const trigger = useCallback(() => {
    clearPulseTimer();
    setState('SOLOIST_PULSE_NAV');
    setEnvironment(config.triggerEnvironment ?? DEFAULT_TRIGGER_ENVIRONMENT);
    config.onTrigger?.();

    pulseTimerRef.current = window.setTimeout(() => {
      setState('FIELD_IDLE');
      setEnvironment(config.idleEnvironment ?? DEFAULT_IDLE_ENVIRONMENT);
      pulseTimerRef.current = null;
    }, config.pulseDurationMs ?? 320);
  }, [clearPulseTimer, config, setEnvironment]);

  return useMemo(() => ({
    ref: obstacleRef,
    state,
    active: state !== 'FIELD_IDLE',
    eventHandlers: {
      onMouseEnter: activate,
      onMouseLeave: deactivate,
      onFocus: activate,
      onBlur: deactivate,
      onClick: trigger,
    },
    dataAttributes: {
      'data-pretext-engine': config.engine,
      'data-pretext-state': state,
    },
  }), [activate, config.engine, deactivate, obstacleRef, state, trigger]);
}

export type PretextButtonProps = Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, 'children' | 'onClick'> & {
  config: FunctionalTextConfig;
  children?: React.ReactNode;
};

export const PretextButton: React.FC<PretextButtonProps> = ({
  config,
  children,
  onMouseEnter,
  onMouseLeave,
  onFocus,
  onBlur,
  style,
  type = 'button',
  ...rest
}) => {
  const functional = useFunctionalTextObstacle(config);

  return (
    <button
      {...rest}
      {...functional.dataAttributes}
      ref={functional.ref as React.RefObject<HTMLButtonElement>}
      onMouseEnter={(event) => {
        functional.eventHandlers.onMouseEnter();
        onMouseEnter?.(event);
      }}
      onMouseLeave={(event) => {
        functional.eventHandlers.onMouseLeave();
        onMouseLeave?.(event);
      }}
      onFocus={(event) => {
        functional.eventHandlers.onFocus();
        onFocus?.(event);
      }}
      onBlur={(event) => {
        functional.eventHandlers.onBlur();
        onBlur?.(event);
      }}
      onClick={functional.eventHandlers.onClick}
      style={{
        appearance: 'none',
        background: 'none',
        border: 0,
        borderRadius: 0,
        color: config.color ?? 'currentColor',
        cursor: 'pointer',
        display: 'inline',
        font: 'inherit',
        padding: 0,
        position: 'relative',
        textDecoration: 'underline',
        textDecorationThickness: '1px',
        textUnderlineOffset: '0.25em',
        ...style,
      }}
      type={type}
    >
      {children ?? config.label}
    </button>
  );
};
