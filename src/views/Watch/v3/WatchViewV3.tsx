import React, { useEffect, useRef, useState } from 'react';
import { useArena } from '../../../context/ArenaContext';
import { useLanguage } from '../../../context/LanguageContext';
import { safeStr } from '../../../utils/safeStr';
import { usePhysicsRegistry } from '../../../context/PhysicsContext';
import { api, request, requestTyped } from '../../../api/arena';
import { NeuralLoading } from '../../../design/VisualPrimitive';
import { tokens } from '../../../design/tokens';
import { useObstacle, useObstacleDetached } from '../../../hooks/useObstacle';
import { MagneticSurface } from '../../../components/MagneticSurface';
import { useWaveRipple } from '../../../hooks/useWaveRipple';
import { ArrowLeft, Radio } from 'lucide-react';

type KnownFeedEventType = 'joined' | 'completed_challenge' | 'unlocked_achievement';

interface RawFeedEvent {
  id: number;
  player_nickname: string;
  event_type: KnownFeedEventType | (string & {});
  target_id: string;
  achievement_name?: string;
  created_at: number;
}

type ViewMode = 'feed' | 'session';
type SessionStepStatus = 'started' | 'completed' | 'failed';

interface SessionStep {
  step: string;
  status: SessionStepStatus;
  timestamp: number;
  output?: string;
}

interface WatchSessionResponse {
  steps?: SessionStep[];
}

/**
 * WatchViewV3: Per-event atomic obstacles.
 * Each feed event line registers independently so bitmask field
 * flows between events.
 */
export const WatchViewV3: React.FC = () => {
  const { withToast, isZenMode, showToast } = useArena();
  const { t } = useLanguage();
  const { registerSoloist, unregisterSoloist, setEnvironment } = usePhysicsRegistry();

  const [feed, setFeed] = useState<RawFeedEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeAgent, setActiveAgent] = useState<any>(null);
  const [viewMode, setViewMode] = useState<ViewMode>('feed');
  const [selectedSubmissionId, setSelectedSubmissionId] = useState<string | null>(null);
  const [sessionSteps, setSessionSteps] = useState<SessionStep[]>([]);
  const lastFeedLength = useRef(0);
  const seenFeedIds = useRef<Set<number>>(new Set());
  const achievementPulseTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Feed soloist registration
  useEffect(() => {
    if (viewMode !== 'feed') return;
    const ids = feed.map((_, i) => `watch-event-${i}`);
    feed.forEach((event, i) => {
      registerSoloist({
        id: `watch-event-${i}`,
        text: `${safeStr(event.player_nickname).toUpperCase()} :: ${safeStr(event.event_type).replace('_', ' ').toUpperCase()} :: REF_${safeStr(event.target_id) || '?'}`,
        lineIndex: 12 + i * 4,
        color: event.event_type === 'completed_challenge' ? tokens.colors.aurora.purple : tokens.colors.aurora.blue,
      });
    });
    return () => { ids.forEach(id => unregisterSoloist(id)); };
  }, [feed, registerSoloist, unregisterSoloist, viewMode]);

  // Session trace soloist registration
  useEffect(() => {
    if (viewMode !== 'session') return;
    const ids = sessionSteps.length > 0
      ? sessionSteps.map((_, i) => `watch-step-${i}`)
      : ['watch-step-empty'];

    if (sessionSteps.length === 0) {
      registerSoloist({
        id: 'watch-step-empty',
        text: t('watch.session.no_trace'),
        lineIndex: 14,
        color: tokens.colors.aurora.cyan,
      });
    } else {
      sessionSteps.forEach((step, i) => {
        registerSoloist({
          id: `watch-step-${i}`,
          text: `0x${i.toString(16).padStart(2, '0')} // ${safeStr(step.step)}`,
          lineIndex: 12 + i * 3,
          color: statusColor(step.status),
        });
      });
    }

    return () => { ids.forEach(id => unregisterSoloist(id)); };
  }, [registerSoloist, sessionSteps, t, unregisterSoloist, viewMode]);

  // Data polling
  useEffect(() => {
    withToast<{ leaders: any[] }>(() => api.leaderboard(), 'Failed to load nodes').then(data => {
      if (data && data.leaders.length > 0) setActiveAgent(data.leaders[0]);
      setLoading(false);
    });
    const triggerAchievementPulse = (event: RawFeedEvent) => {
      if (achievementPulseTimeout.current) clearTimeout(achievementPulseTimeout.current);

      const achievementName = safeStr(event.achievement_name ?? event.target_id).toUpperCase();
      setEnvironment({
        effects: {
          alignmentPulse: {
            active: true,
            startTime: performance.now(),
            duration: 600,
          },
        },
      });
      registerSoloist({
        id: 'achievement-nickname',
        text: safeStr(event.player_nickname).toUpperCase(),
        lineIndex: 10,
        color: tokens.colors.aurora.purple,
        opacity: 1,
      });
      registerSoloist({
        id: 'achievement-name',
        text: `[ ACHIEVEMENT_UNLOCKED ] :: ${achievementName}`,
        lineIndex: 11,
        color: tokens.colors.aurora.cyan,
        opacity: 1,
      });

      achievementPulseTimeout.current = setTimeout(() => {
        unregisterSoloist('achievement-nickname');
        unregisterSoloist('achievement-name');
        setEnvironment({
          effects: {
            alignmentPulse: {
              active: false,
              startTime: 0,
              duration: 600,
            },
          },
        });
      }, 600);
    };
    const poll = async () => {
      const feedData = await request<{ feed: RawFeedEvent[] }>(() => api.feed(1));
      if (feedData && feedData.feed) {
        const newEvents = feedData.feed.filter(event => !seenFeedIds.current.has(event.id));
        const achievementEvent = newEvents.find(event => event.event_type === 'unlocked_achievement');
        newEvents.forEach(event => seenFeedIds.current.add(event.id));

        if (achievementEvent) {
          triggerAchievementPulse(achievementEvent);
        }
        if (feedData.feed.length > lastFeedLength.current) {
          setEnvironment({ waveAmplitude: 100 });
          setTimeout(() => setEnvironment({ waveAmplitude: 60 }), 800);
        }
        lastFeedLength.current = feedData.feed.length;
        setFeed(feedData.feed.slice(0, 6));
      }
    };
    poll();
    const interval = setInterval(poll, 3000);
    return () => {
      clearInterval(interval);
      if (achievementPulseTimeout.current) clearTimeout(achievementPulseTimeout.current);
      unregisterSoloist('achievement-nickname');
      unregisterSoloist('achievement-name');
      setEnvironment({
        effects: {
          alignmentPulse: {
            active: false,
            startTime: 0,
            duration: 600,
          },
        },
      });
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    return () => setEnvironment({ waveAmplitude: 60, waveFrequency: 0.03 });
  }, [setEnvironment]);

  const returnToFeed = React.useCallback(() => {
    sessionSteps.forEach((_, i) => unregisterSoloist(`watch-step-${i}`));
    unregisterSoloist('watch-step-empty');
    setSessionSteps([]);
    setSelectedSubmissionId(null);
    setViewMode('feed');
    setEnvironment({ opacity: 0.15 });
  }, [sessionSteps, setEnvironment, unregisterSoloist]);

  useEffect(() => {
    if (viewMode !== 'session') return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() === 'b') returnToFeed();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [returnToFeed, viewMode]);

  const openSession = React.useCallback(async (event: RawFeedEvent) => {
    const submissionId = String(event.id);
    setSelectedSubmissionId(submissionId);
    setViewMode('session');
    setSessionSteps([]);
    setEnvironment({ opacity: 0.05 });

    const { data, error } = await requestTyped<WatchSessionResponse>(() => api.watch(submissionId));
    if (error) {
      showToast(error.kind === 'client' && error.status === 404 ? t('watch.session.error_404') : t('watch.session.error_generic'), 'error');
      setSelectedSubmissionId(null);
      setSessionSteps([]);
      setViewMode('feed');
      setEnvironment({ opacity: 0.15 });
      return;
    }

    setSessionSteps(Array.isArray(data?.steps) ? data.steps : []);
  }, [setEnvironment, showToast]);

  if (loading) return <NeuralLoading label={t('watch.status.loading').toUpperCase()} />;

  return (
    <div className="page-watch variant-v3" style={containerStyle}>
      <HeaderAtomMemo isZenMode={isZenMode} activeAgent={activeAgent} />

      {viewMode === 'session' ? (
        <SessionTraceMemo
          isZenMode={isZenMode}
          selectedSubmissionId={selectedSubmissionId}
          sessionSteps={sessionSteps}
          onBack={returnToFeed}
          noTraceLabel={t('watch.session.no_trace')}
          backLabel={t('watch.session.back')}
        />
      ) : feed.length === 0 ? (
        <EmptyAtomMemo isZenMode={isZenMode} />
      ) : (
        feed.map(event => (
          <FeedEventAtom key={event.id} event={event} isZenMode={isZenMode} onSelect={openSession} />
        ))
      )}

      <style>{`
        @media (max-width: 768px) {
          .page-watch.variant-v3 {
            padding: 2rem 1rem !important;
          }
          .watch-v3-header {
            margin-bottom: 1rem !important;
          }
        }
      `}</style>
    </div>
  );
};

// ── Styles ──────────────────────────────────────────────────────────

const containerStyle: React.CSSProperties = {
  minHeight: '100vh',
  color: '#fff',
  padding: '4rem 2rem',
  position: 'relative',
};

const headerLabelStyle: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: '1rem',
  color: tokens.colors.aurora.purple,
  fontFamily: tokens.fonts.mono,
  fontSize: tokens.sizes.micro,
  letterSpacing: '0.2em',
};

const feedEventStyle: React.CSSProperties = {
  fontFamily: tokens.fonts.mono,
  fontSize: tokens.sizes.small,
  letterSpacing: '0.1em',
  padding: '0.5rem 0',
  display: 'inline-block',
  cursor: 'pointer',
};

const sessionTraceStyle: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: '24px',
};

const sessionStepStyle: React.CSSProperties = {
  fontFamily: tokens.fonts.mono,
  fontSize: tokens.sizes.small,
  letterSpacing: '0.1em',
  padding: '0.25rem 0',
  display: 'inline-block',
};

const backStyle: React.CSSProperties = {
  ...sessionStepStyle,
  cursor: 'pointer',
  color: tokens.colors.text.tertiary,
};

// ── Atom components ─────────────────────────────────────────────────

const HeaderAtom: React.FC<{ isZenMode: boolean; activeAgent: any }> = ({ isZenMode, activeAgent }) => {
  const ref = useObstacleDetached(true, isZenMode) as React.RefObject<HTMLDivElement>;
  const { onPointerEnter, onTouchStart } = useWaveRipple();
  return (
    <div className="watch-v3-header" style={{ marginBottom: '3rem', opacity: isZenMode ? 0.3 : 0.8, transition: 'opacity 0.6s ease' }}>
      <MagneticSurface pull={0.15}>
        <div ref={ref} onPointerEnter={onPointerEnter} onTouchStart={onTouchStart} style={headerLabelStyle}>
          <Radio size={14} className="pulse" />
          LIVE_RESONANT_CHORUS // AGENT: {safeStr(activeAgent?.nickname).toUpperCase() || '---'}
        </div>
      </MagneticSurface>
    </div>
  );
};
const HeaderAtomMemo = React.memo(HeaderAtom);

const FeedEventAtom: React.FC<{ event: RawFeedEvent; isZenMode: boolean; onSelect: (event: RawFeedEvent) => void }> = ({ event, isZenMode, onSelect }) => {
  const ref = useObstacleDetached(true, isZenMode) as React.RefObject<HTMLDivElement>;
  const { onPointerEnter, onTouchStart } = useWaveRipple();
  return (
    <div style={{ marginBottom: '0.5rem' }}>
      <MagneticSurface pull={0.1}>
        <div
          ref={ref}
          onClick={() => onSelect(event)}
          onPointerEnter={onPointerEnter}
          onTouchStart={onTouchStart}
          style={{
            ...feedEventStyle,
            color: event.event_type === 'completed_challenge' ? tokens.colors.aurora.purple : tokens.colors.aurora.blue,
          }}
        >
          {safeStr(event.player_nickname).toUpperCase()} :: {safeStr(event.event_type).replace('_', ' ').toUpperCase()} :: REF_{safeStr(event.target_id) || '?'}
        </div>
      </MagneticSurface>
    </div>
  );
};

const statusColor = (status: string) => {
  switch (safeStr(status)) {
    case 'started':
      return tokens.colors.aurora.cyan;
    case 'completed':
      return tokens.colors.aurora.blue;
    case 'failed':
      return tokens.colors.aurora.red;
    default:
      return tokens.colors.text.secondary;
  }
};

const SessionTrace: React.FC<{
  isZenMode: boolean;
  selectedSubmissionId: string | null;
  sessionSteps: SessionStep[];
  onBack: () => void;
  noTraceLabel: string;
  backLabel: string;
}> = ({ isZenMode, selectedSubmissionId, sessionSteps, onBack, noTraceLabel, backLabel }) => {
  return (
    <div style={sessionTraceStyle}>
      <SessionBackAtom isZenMode={isZenMode} onBack={onBack} backLabel={backLabel} selectedSubmissionId={selectedSubmissionId} />
      {sessionSteps.length === 0 ? (
        <EmptySessionAtom noTraceLabel={noTraceLabel} />
      ) : (
        sessionSteps.map((step, i) => (
          <SessionStepAtom key={`${safeStr(step.timestamp)}-${i}`} index={i} step={step} />
        ))
      )}
    </div>
  );
};
const SessionTraceMemo = React.memo(SessionTrace);

const SessionBackAtom: React.FC<{ isZenMode: boolean; onBack: () => void; backLabel: string; selectedSubmissionId: string | null }> = ({
  isZenMode,
  onBack,
  backLabel,
  selectedSubmissionId,
}) => {
  const ref = useObstacleDetached(true, isZenMode) as React.RefObject<HTMLDivElement>;
  const { onPointerEnter, onTouchStart } = useWaveRipple();
  return (
    <MagneticSurface pull={0.1}>
      <div
        ref={ref}
        onClick={onBack}
        onPointerEnter={onPointerEnter}
        onTouchStart={onTouchStart}
        style={backStyle}
      >
        <ArrowLeft size={12} style={{ marginRight: '0.75rem', verticalAlign: '-2px' }} />
        {backLabel} // TRACE_{safeStr(selectedSubmissionId) || '---'}
      </div>
    </MagneticSurface>
  );
};

const SessionStepAtom: React.FC<{ index: number; step: SessionStep }> = ({ index, step }) => {
  const ref = useObstacle() as React.RefObject<HTMLDivElement>;
  return (
    <div
      ref={ref}
      style={{
        ...sessionStepStyle,
        color: statusColor(step.status),
      }}
    >
      0x{index.toString(16).padStart(2, '0')} // {safeStr(step.step)}
      {step.output ? <span style={{ color: tokens.colors.text.tertiary }}> :: {safeStr(step.output)}</span> : null}
    </div>
  );
};

const EmptySessionAtom: React.FC<{ noTraceLabel: string }> = ({ noTraceLabel }) => {
  const ref = useObstacle() as React.RefObject<HTMLDivElement>;
  return (
    <div ref={ref} style={{ ...sessionStepStyle, color: tokens.colors.aurora.cyan }}>
      {noTraceLabel}
    </div>
  );
};

const EmptyAtom: React.FC<{ isZenMode: boolean }> = ({ isZenMode }) => {
  const ref = useObstacleDetached(true, isZenMode) as React.RefObject<HTMLDivElement>;
  return (
    <div ref={ref} style={{ fontFamily: tokens.fonts.mono, fontSize: tokens.sizes.small, opacity: 0.4 }}>
      AWAITING_CHORUS_EVENTS...
    </div>
  );
};
const EmptyAtomMemo = React.memo(EmptyAtom);
