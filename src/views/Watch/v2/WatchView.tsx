import React, { useState, useEffect } from 'react';
import { useArena } from '../../../context/ArenaContext';
import { useLanguage } from '../../../context/LanguageContext';
import { api, request } from '../../../api/arena';
import { NeuralLoading } from '../../../design/VisualPrimitive';
import { safeStr } from '../../../utils/safeStr';
import { motion, AnimatePresence } from 'framer-motion';
import { LabyrinthPhysic } from '../../../components/text-physics/LabyrinthPhysic';
import { useObstacle } from '../../../hooks/useObstacle';
import { tokens } from '../../../design/tokens';

interface RawFeedEvent {
  id: number;
  player_nickname: string;
  event_type: string;
  target_id: string;
  created_at: number;
}

export const WatchView: React.FC = () => {
  const { withToast, isZenMode } = useArena();
  const { t, locale } = useLanguage();
  const [feed, setFeed] = useState<RawFeedEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeAgent, setActiveAgent] = useState<any>(null);

  useEffect(() => {
    withToast<{ leaders: any[] }>(() => api.leaderboard(), t('watch.v2.load_nodes_error')).then(data => {
      if (data && data.leaders.length > 0) setActiveAgent(data.leaders[0]);
      setLoading(false);
    });

    const poll = async () => {
      const feedData = await request<{ feed: RawFeedEvent[] }>(() => api.feed(1));
      if (feedData && feedData.feed) setFeed(feedData.feed.slice(0, 4));
    };

    poll();
    const interval = setInterval(poll, 5000);
    return () => clearInterval(interval);
  }, []);

  if (loading) return <NeuralLoading label={t('watch.status.loading').toUpperCase()} />;

  return (
    <div className="v2-watch" style={{ 
      minHeight: '100vh', 
      background: tokens.colors.manuscript.bg,
      color: tokens.colors.manuscript.ink,
      padding: '4rem',
      fontFamily: tokens.fonts.manuscript,
      position: 'relative',
      overflow: 'hidden'
    }}>

      {/* BACKGROUND CHRONICLE PHYSICS */}
      <div style={{ position: 'absolute', inset: '4rem', zIndex: 1, opacity: isZenMode ? 0.95 : 0.8 }}>
        <LabyrinthPhysic 
          text={(t('watch.subtitle') + ' ' + t('watch.marginalia') + ' ' + t('home.manifesto') + ' ').repeat(10)} 
          lineHeight={locale === 'zh-CN' ? 36 : 32} 
          fontDef={locale === 'zh-CN' ? `400 18px ${tokens.fonts.body}` : `400 20px ${tokens.fonts.manuscript}`}
          variant="v2"
        />
      </div>

      <div className="v2-watch-content" style={{ 
        position: 'relative', 
        zIndex: 10, 
        maxWidth: '1000px', 
        margin: '0 auto', 
        pointerEvents: isZenMode ? 'none' : 'auto',
        opacity: isZenMode ? 0 : 1,
        transition: 'opacity 0.6s ease'
      }}>
        <header style={{ marginBottom: '4rem' }}>
          <div style={{ display: 'inline-flex', padding: '0.5rem 1rem', border: `1px solid ${tokens.colors.manuscript.ink}`, marginBottom: '1rem', fontFamily: tokens.fonts.mono, fontSize: tokens.sizes.small }}>
            {t('watch.v2.node_observation')} // {safeStr(activeAgent?.nickname).toUpperCase()}
          </div>
          <h1 className="v2-watch-title" style={{ fontSize: '3rem', fontWeight: 700, letterSpacing: '-0.02em', color: tokens.colors.manuscript.ink }}>
            {t('watch.v2.chronicle')}
          </h1>
        </header>

        {/* FEED ENTRIES (Obstacles) */}
        <AnimatePresence>
          {!isZenMode && feed.map((event, i) => (
            <WatchFeedEntry
              key={event.id}
              event={event}
              index={i}
              t={t}
            />
          ))}
        </AnimatePresence>
      </div>

      <style>{`
        .v2-watch {
          background-image: radial-gradient(#dcdcdc 0.5px, transparent 0.5px);
          background-size: 30px 30px;
        }
        @media (max-width: 768px) {
          .v2-watch {
            padding: 1rem !important;
          }
          .v2-watch-content {
            max-width: 100% !important;
          }
          .v2-watch-title {
            font-size: 2rem !important;
          }
        }
      `}</style>
    </div>
  );
};

const WatchFeedEntry: React.FC<{
  event: RawFeedEvent;
  index: number;
  t: (keyPath: string) => string;
}> = ({ event, index, t }) => {
  const ref = useObstacle() as React.RefObject<HTMLDivElement>;
  const left = index % 2 === 0 ? 0 : 500;
  const top = 150 + index * 250;

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, x: index % 2 === 0 ? -20 : 20 }}
      animate={{ opacity: 1, x: 0 }}
      style={{
        position: 'absolute',
        left,
        top,
        width: 400,
        minHeight: 220,
        padding: '0.75rem 0 0.75rem 1.25rem',
        borderLeft: '1px solid rgba(26,26,26,0.3)',
        background: 'transparent',
        boxShadow: 'none',
        backdropFilter: 'none',
        pointerEvents: 'auto',
      }}
    >
      <div style={{ fontFamily: tokens.fonts.mono, fontSize: tokens.sizes.xs, color: tokens.colors.manuscript.dim, marginBottom: '1rem' }}>
        // {t('watch.v2.entry')}_{event.id}
      </div>
      <div style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '0.5rem' }}>{event.player_nickname}</div>
      <div style={{ fontSize: '0.9rem', color: tokens.colors.manuscript.faint, fontStyle: 'italic' }}>
        {formatWatchEventLine(t, event)}
      </div>
    </motion.div>
  );
};

const eventTypeLabel = (t: (keyPath: string) => string, eventType: string) => {
  switch (eventType) {
    case 'joined':
      return t('watch.v2.events.joined');
    case 'completed_challenge':
      return t('watch.v2.events.completed_challenge');
    case 'unlocked_achievement':
      return t('watch.v2.events.unlocked_achievement');
    default:
      return safeStr(eventType).replace('_', ' ');
  }
};

const formatWatchEventLine = (t: (keyPath: string) => string, event: RawFeedEvent) => {
  return t('watch.v2.event_line')
    .replace('{{eventType}}', eventTypeLabel(t, event.event_type))
    .replace('{{targetId}}', safeStr(event.target_id));
};
