import React, { useCallback, useEffect, useRef, useState } from 'react';
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
import { PretextButton } from '../../../components/PretextButton';
import { CHALLENGES } from '../../../data/mockData';

type KnownFeedEventType = 'joined' | 'completed_challenge' | 'unlocked_achievement';

interface RawFeedEvent {
  id: number;
  player_nickname?: string;
  nickname?: string;
  player_id?: string;
  player_code?: string;
  event_type: KnownFeedEventType | (string & {});
  target_id: string;
  achievement_name?: string;
  created_at: number | string;
}

type ViewMode = 'feed' | 'session';
type SessionStatus = 'idle' | 'loading' | 'thinking' | 'solved' | 'error';

interface WatchSessionResponse {
  id: number;
  player_code: string;
  challenge_id: number;
  status: 'thinking' | 'solved' | (string & {});
  steps: string[];
  started_at?: string;
  updated_at?: string;
}

/**
 * WatchViewV3: Per-event atomic obstacles.
 * Each feed event line registers independently so bitmask field
 * flows between events.
 */
export const WatchViewV3: React.FC = () => {
  const { withToast, isZenMode } = useArena();
  const { t } = useLanguage();
  const { setEnvironment } = usePhysicsRegistry();

  const [feed, setFeed] = useState<RawFeedEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeAgent, setActiveAgent] = useState<any>(null);
  const [viewMode, setViewMode] = useState<ViewMode>('feed');
  const [selectedPlayerCode, setSelectedPlayerCode] = useState<string | null>(null);
  const [selectedPlayerName, setSelectedPlayerName] = useState<string | null>(null);
  const [sessionStatus, setSessionStatus] = useState<SessionStatus>('idle');
  const [watchSession, setWatchSession] = useState<WatchSessionResponse | null>(null);
  const [sessionSteps, setSessionSteps] = useState<string[]>([]);
  const [sessionMessage, setSessionMessage] = useState<string | null>(null);
  const lastFeedLength = useRef(0);
  const seenFeedIds = useRef<Set<number>>(new Set());
  const achievementPulseTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const viewModeRef = useRef<ViewMode>('feed');

  useEffect(() => {
    viewModeRef.current = viewMode;
  }, [viewMode]);

  // Keep feed and session metadata as ambient text flow via existing DOM obstacles.

  // Data polling
  useEffect(() => {
    withToast<{ leaders: any[] }>(() => api.leaderboard(), t('watch.v3.load_nodes_error')).then(data => {
      if (data && data.leaders.length > 0) setActiveAgent(data.leaders[0]);
      setLoading(false);
    });
    const triggerAchievementPulse = () => {
      if (achievementPulseTimeout.current) clearTimeout(achievementPulseTimeout.current);

      setEnvironment({
        effects: {
          alignmentPulse: {
            active: true,
            startTime: performance.now(),
            duration: 600,
          },
        },
      });

      achievementPulseTimeout.current = setTimeout(() => {
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

        if (achievementEvent && viewModeRef.current === 'feed') {
          triggerAchievementPulse();
        }
        if (feedData.feed.length > lastFeedLength.current && viewModeRef.current === 'feed') {
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

  const returnToFeed = useCallback(() => {
    setSessionSteps([]);
    setSelectedPlayerCode(null);
    setSelectedPlayerName(null);
    setWatchSession(null);
    setSessionMessage(null);
    setSessionStatus('idle');
    setViewMode('feed');
    setEnvironment({ opacity: 0.15 });
  }, [setEnvironment]);

  useEffect(() => {
    if (viewMode !== 'session') return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() === 'b') returnToFeed();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [returnToFeed, viewMode]);

  const fetchSession = useCallback(async (playerCode: string, silent = false) => {
    if (!silent) setSessionStatus('loading');
    const { data, error } = await requestTyped<WatchSessionResponse>(() => api.watch(playerCode));
    if (error) {
      setWatchSession(null);
      setSessionSteps([]);
      if (error.kind === 'client' && error.status === 404) {
        setSessionMessage(t('watch.session.no_active'));
        setSessionStatus('idle');
      } else {
        setSessionMessage(t('watch.session.error_generic'));
        setSessionStatus('error');
      }
      setEnvironment({ waveAmplitude: 90, opacity: 0.08 });
      return;
    }

    const nextStatus = data?.status === 'thinking' ? 'thinking' : 'solved';
    setWatchSession(data);
    setSessionSteps(normalizeSessionSteps(data?.steps));
    setSessionMessage(null);
    setSessionStatus(nextStatus);
    setEnvironment({
      waveAmplitude: nextStatus === 'thinking' ? 100 : 90,
      opacity: nextStatus === 'thinking' ? 0.18 : 0.08,
    });
  }, [setEnvironment, t]);

  useEffect(() => {
    if (viewMode !== 'session' || !selectedPlayerCode || sessionStatus !== 'thinking') return;
    const interval = window.setInterval(() => {
      void fetchSession(selectedPlayerCode, true);
    }, 2000);
    return () => window.clearInterval(interval);
  }, [fetchSession, selectedPlayerCode, sessionStatus, viewMode]);

  const openSession = useCallback(async (event: RawFeedEvent) => {
    const playerCode = getFeedPlayerCode(event);
    setViewMode('session');
    setSelectedPlayerCode(playerCode);
    setSelectedPlayerName(getFeedPlayerName(event));
    setWatchSession(null);
    setSessionSteps([]);
    setSessionMessage(null);
    setSessionStatus('loading');
    setEnvironment({ opacity: 0.05 });

    if (!playerCode) {
      setSessionMessage(t('watch.session.error_generic'));
      setSessionStatus('error');
      return;
    }

    await fetchSession(playerCode);
  }, [fetchSession, setEnvironment, t]);

  if (loading) return <NeuralLoading label={t('watch.status.loading').toUpperCase()} />;

  return (
    <div className="page-watch variant-v3" style={containerStyle}>
      <HeaderAtomMemo isZenMode={isZenMode} activeAgent={activeAgent} />

      {viewMode === 'session' ? (
        <SessionTraceMemo
          selectedPlayerCode={selectedPlayerCode}
          selectedPlayerName={selectedPlayerName}
          sessionStatus={sessionStatus}
          watchSession={watchSession}
          sessionSteps={sessionSteps}
          sessionMessage={sessionMessage}
          onBack={returnToFeed}
          noActiveLabel={t('watch.session.no_active')}
          loadingLabel={t('watch.session.loading')}
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

const eventTypeLabel = (eventType: RawFeedEvent['event_type'], t: (keyPath: string) => string) => {
  switch (eventType) {
    case 'joined':
      return t('watch.v3.events.joined');
    case 'completed_challenge':
      return t('watch.v3.events.completed_challenge');
    case 'unlocked_achievement':
      return t('watch.v3.events.unlocked_achievement');
    default:
      return safeStr(eventType).replace('_', ' ').toUpperCase();
  }
};

const getFeedPlayerName = (event: RawFeedEvent) => {
  return safeStr(event.player_nickname ?? event.nickname ?? event.player_code ?? event.player_id ?? 'UNKNOWN');
};

const getFeedPlayerCode = (event: RawFeedEvent) => {
  return safeStr(event.player_code ?? event.player_id ?? '');
};

const normalizeSessionSteps = (steps: unknown) => {
  if (!Array.isArray(steps)) return [];
  return steps.map(step => safeStr(step)).filter(Boolean);
};

const sessionStatusColor = (status: SessionStatus) => {
  switch (status) {
    case 'thinking':
      return tokens.colors.aurora.cyan;
    case 'solved':
      return tokens.colors.aurora.blue;
    case 'error':
      return tokens.colors.aurora.red;
    default:
      return tokens.colors.text.secondary;
  }
};

const challengeTitle = (session: WatchSessionResponse | null) => {
  if (!session) return '---';
  return safeStr(CHALLENGES.find(challenge => challenge.id === session.challenge_id)?.title ?? `Layer ${session.challenge_id}`);
};

const formatUpdatedAt = (updatedAt?: string) => {
  if (!updatedAt) return '---';
  const date = new Date(updatedAt);
  if (Number.isNaN(date.getTime())) return safeStr(updatedAt);
  return date.toLocaleString();
};

const HeaderAtom: React.FC<{ isZenMode: boolean; activeAgent: any }> = ({ isZenMode, activeAgent }) => {
  const { t } = useLanguage();
  const ref = useObstacleDetached(true, isZenMode) as React.RefObject<HTMLDivElement>;
  const { onPointerEnter, onTouchStart } = useWaveRipple();
  return (
    <div className="watch-v3-header" style={{ marginBottom: '3rem', opacity: isZenMode ? 0.3 : 0.8, transition: 'opacity 0.6s ease' }}>
      <MagneticSurface pull={0.15}>
        <div ref={ref} onPointerEnter={onPointerEnter} onTouchStart={onTouchStart} style={headerLabelStyle}>
          <Radio size={14} className="pulse" />
          {t('watch.v3.header')} // {t('watch.v3.agent')}: {safeStr(activeAgent?.nickname).toUpperCase() || '---'}
        </div>
      </MagneticSurface>
    </div>
  );
};
const HeaderAtomMemo = React.memo(HeaderAtom);

const FeedEventAtom: React.FC<{ event: RawFeedEvent; isZenMode: boolean; onSelect: (event: RawFeedEvent) => void }> = ({ event, isZenMode, onSelect }) => {
  const { t } = useLanguage();
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
          {getFeedPlayerName(event).toUpperCase()} :: {eventTypeLabel(event.event_type, t)} :: {t('watch.v3.ref')}_{safeStr(event.target_id) || '?'}
        </div>
      </MagneticSurface>
    </div>
  );
};

const SessionTrace: React.FC<{
  selectedPlayerCode: string | null;
  selectedPlayerName: string | null;
  sessionStatus: SessionStatus;
  watchSession: WatchSessionResponse | null;
  sessionSteps: string[];
  sessionMessage: string | null;
  onBack: () => void;
  noActiveLabel: string;
  loadingLabel: string;
  backLabel: string;
}> = ({
  selectedPlayerCode,
  selectedPlayerName,
  sessionStatus,
  watchSession,
  sessionSteps,
  sessionMessage,
  onBack,
  noActiveLabel,
  loadingLabel,
  backLabel,
}) => {
  return (
    <div style={sessionTraceStyle}>
      <SessionBackAtom onBack={onBack} backLabel={backLabel} selectedPlayerCode={selectedPlayerCode} />
      <SessionMetaAtom
        sessionStatus={sessionStatus}
        watchSession={watchSession}
        selectedPlayerCode={selectedPlayerCode}
        selectedPlayerName={selectedPlayerName}
      />
      {sessionSteps.length === 0 ? (
        <EmptySessionAtom
          label={sessionMessage ?? (sessionStatus === 'loading' ? loadingLabel : noActiveLabel)}
          tone={sessionStatus}
        />
      ) : (
        sessionSteps.map((step, i) => (
          <SessionStepAtom key={`${safeStr(step)}-${i}`} index={i} step={step} sessionStatus={sessionStatus} />
        ))
      )}
    </div>
  );
};
const SessionTraceMemo = React.memo(SessionTrace);

const SessionBackAtom: React.FC<{ onBack: () => void; backLabel: string; selectedPlayerCode: string | null }> = ({
  onBack,
  backLabel,
  selectedPlayerCode,
}) => {
  const { t } = useLanguage();
  const { onPointerEnter, onTouchStart } = useWaveRipple();
  return (
    <MagneticSurface pull={0.1}>
      <PretextButton
        config={{
          label: backLabel,
          engine: 'bitmask',
          soloistId: 'watch-session-back',
          color: tokens.colors.text.tertiary,
          onTrigger: onBack,
          activationEnvironment: { waveAmplitude: 92, opacity: 0.18 },
          triggerEnvironment: { waveAmplitude: 118, opacity: 0.22 },
          idleEnvironment: { opacity: 0.15 },
        }}
        onPointerEnter={onPointerEnter}
        onTouchStart={onTouchStart}
        style={backStyle}
      >
        <ArrowLeft size={12} style={{ marginRight: '0.75rem', verticalAlign: '-2px' }} />
        {backLabel} // {t('watch.v3.trace')}_{safeStr(selectedPlayerCode) || '---'}
      </PretextButton>
    </MagneticSurface>
  );
};

const SessionMetaAtom: React.FC<{
  sessionStatus: SessionStatus;
  watchSession: WatchSessionResponse | null;
  selectedPlayerCode: string | null;
  selectedPlayerName: string | null;
}> = ({ sessionStatus, watchSession, selectedPlayerCode, selectedPlayerName }) => {
  const { t } = useLanguage();
  const ref = useObstacle() as React.RefObject<HTMLDivElement>;
  return (
    <div ref={ref} style={{ ...sessionStepStyle, color: sessionStatusColor(sessionStatus), opacity: 0.85 }}>
      {safeStr(selectedPlayerName ?? selectedPlayerCode ?? '---').toUpperCase()} :: {t('watch.session.challenge')}_{challengeTitle(watchSession)}
      {' '}:: {t('watch.session.status')}_{safeStr(watchSession?.status ?? sessionStatus).toUpperCase()}
      {' '}:: {t('watch.session.updated')}_{formatUpdatedAt(watchSession?.updated_at)}
    </div>
  );
};

const SessionStepAtom: React.FC<{ index: number; step: string; sessionStatus: SessionStatus }> = ({ index, step, sessionStatus }) => {
  const ref = useObstacle() as React.RefObject<HTMLDivElement>;
  return (
    <div
      ref={ref}
      style={{
        ...sessionStepStyle,
        color: sessionStatus === 'thinking' ? tokens.colors.aurora.cyan : tokens.colors.aurora.blue,
      }}
    >
      0x{index.toString(16).padStart(2, '0')} // {safeStr(step)}
    </div>
  );
};

const EmptySessionAtom: React.FC<{ label: string; tone: SessionStatus }> = ({ label, tone }) => {
  const ref = useObstacle() as React.RefObject<HTMLDivElement>;
  return (
    <div ref={ref} style={{ ...sessionStepStyle, color: sessionStatusColor(tone) }}>
      {label}
    </div>
  );
};

const EmptyAtom: React.FC<{ isZenMode: boolean }> = ({ isZenMode }) => {
  const { t } = useLanguage();
  const ref = useObstacleDetached(true, isZenMode) as React.RefObject<HTMLDivElement>;
  return (
    <div ref={ref} style={{ fontFamily: tokens.fonts.mono, fontSize: tokens.sizes.small, opacity: 0.4 }}>
      {t('watch.v3.empty')}
    </div>
  );
};
const EmptyAtomMemo = React.memo(EmptyAtom);
