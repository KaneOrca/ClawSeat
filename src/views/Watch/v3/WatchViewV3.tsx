import React, { useEffect, useRef, useState } from 'react';
import { useArena } from '../../../context/ArenaContext';
import { useLanguage } from '../../../context/LanguageContext';
import { safeStr } from '../../../utils/safeStr';
import { usePhysicsRegistry } from '../../../context/PhysicsContext';
import { api, request } from '../../../api/arena';
import { NeuralLoading } from '../../../design/VisualPrimitive';
import { tokens } from '../../../design/tokens';
import { useObstacleDetached } from '../../../hooks/useObstacle';
import { MagneticSurface } from '../../../components/MagneticSurface';
import { useWaveRipple } from '../../../hooks/useWaveRipple';
import { Radio } from 'lucide-react';

interface RawFeedEvent {
  id: number;
  player_nickname: string;
  event_type: string;
  target_id: string;
  created_at: number;
}

/**
 * WatchViewV3: Per-event atomic obstacles.
 * Each feed event line registers independently so bitmask field
 * flows between events.
 */
export const WatchViewV3: React.FC = () => {
  const { withToast, isZenMode } = useArena();
  const { t } = useLanguage();
  const { registerSoloist, unregisterSoloist, setEnvironment } = usePhysicsRegistry();

  const [feed, setFeed] = useState<RawFeedEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeAgent, setActiveAgent] = useState<any>(null);
  const lastFeedLength = useRef(0);

  // Soloist registration
  useEffect(() => {
    const ids = feed.map((_, i) => `watch-event-${i}`);
    feed.forEach((event, i) => {
      registerSoloist({
        id: `watch-event-${i}`,
        text: `${safeStr(event.player_nickname).toUpperCase()} :: ${safeStr(event.event_type).replace('_', ' ').toUpperCase()} :: REF_${event.target_id ?? '?'}`,
        lineIndex: 12 + i * 4,
        color: event.event_type === 'success' ? tokens.colors.aurora.purple : tokens.colors.aurora.blue,
      });
    });
    return () => { ids.forEach(id => unregisterSoloist(id)); };
  }, [feed, registerSoloist, unregisterSoloist]);

  // Data polling
  useEffect(() => {
    withToast<{ leaders: any[] }>(() => api.leaderboard(), 'Failed to load nodes').then(data => {
      if (data && data.leaders.length > 0) setActiveAgent(data.leaders[0]);
      setLoading(false);
    });
    const poll = async () => {
      const feedData = await request<{ feed: RawFeedEvent[] }>(() => api.feed(1));
      if (feedData && feedData.feed) {
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
    return () => clearInterval(interval);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    return () => setEnvironment({ waveAmplitude: 60, waveFrequency: 0.03 });
  }, [setEnvironment]);

  if (loading) return <NeuralLoading label={t('watch.status.loading').toUpperCase()} />;

  return (
    <div className="page-watch variant-v3" style={containerStyle}>
      <HeaderAtomMemo isZenMode={isZenMode} activeAgent={activeAgent} />

      {feed.length === 0 ? (
        <EmptyAtomMemo isZenMode={isZenMode} />
      ) : (
        feed.map(event => (
          <FeedEventAtom key={event.id} event={event} isZenMode={isZenMode} />
        ))
      )}
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
  fontSize: '10px',
  letterSpacing: '0.2em',
};

const feedEventStyle: React.CSSProperties = {
  fontFamily: tokens.fonts.mono,
  fontSize: '11px',
  letterSpacing: '0.1em',
  padding: '0.5rem 0',
  display: 'inline-block',
};

// ── Atom components ─────────────────────────────────────────────────

const HeaderAtom: React.FC<{ isZenMode: boolean; activeAgent: any }> = ({ isZenMode, activeAgent }) => {
  const ref = useObstacleDetached(true, isZenMode) as React.RefObject<HTMLDivElement>;
  const { onPointerEnter, onTouchStart } = useWaveRipple();
  return (
    <div style={{ marginBottom: '3rem', opacity: isZenMode ? 0.3 : 0.8, transition: 'opacity 0.6s ease' }}>
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

const FeedEventAtom: React.FC<{ event: RawFeedEvent; isZenMode: boolean }> = ({ event, isZenMode }) => {
  const ref = useObstacleDetached(true, isZenMode) as React.RefObject<HTMLDivElement>;
  const { onPointerEnter, onTouchStart } = useWaveRipple();
  return (
    <div style={{ marginBottom: '0.5rem' }}>
      <MagneticSurface pull={0.1}>
        <div
          ref={ref}
          onPointerEnter={onPointerEnter}
          onTouchStart={onTouchStart}
          style={{
            ...feedEventStyle,
            color: event.event_type === 'success' ? tokens.colors.aurora.purple : tokens.colors.aurora.blue,
          }}
        >
          {safeStr(event.player_nickname).toUpperCase()} :: {safeStr(event.event_type).replace('_', ' ').toUpperCase()} :: REF_{event.target_id ?? '?'}
        </div>
      </MagneticSurface>
    </div>
  );
};

const EmptyAtom: React.FC<{ isZenMode: boolean }> = ({ isZenMode }) => {
  const ref = useObstacleDetached(true, isZenMode) as React.RefObject<HTMLDivElement>;
  return (
    <div ref={ref} style={{ fontFamily: tokens.fonts.mono, fontSize: '11px', opacity: 0.4 }}>
      AWAITING_CHORUS_EVENTS...
    </div>
  );
};
const EmptyAtomMemo = React.memo(EmptyAtom);
