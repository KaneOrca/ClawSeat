import React, { useState, useEffect } from 'react';
import { useArena } from '../../../context/ArenaContext';
import { useLanguage } from '../../../context/LanguageContext';
import { api, request } from '../../../api/arena';
import { NeuralLoading } from '../../../design/VisualPrimitive';
import { safeStr } from '../../../utils/safeStr';
import { motion, AnimatePresence } from 'framer-motion';
import { Terminal } from 'lucide-react';
import { ManuscriptPhysic } from '../../../components/text-physics/ManuscriptPhysic';

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

  // Map feed to obstacles (wider and more offset for better wrapping visualization)
  const obstacles = feed.map((event, i) => ({
    id: `event-${event.id}`,
    x: i % 2 === 0 ? 0 : 500,
    y: 150 + i * 250,
    w: 400,
    h: 220
  }));

  return (
    <div className="v2-watch" style={{ 
      minHeight: '100vh', 
      background: '#fdfcf0', 
      color: '#1a1a1a', 
      padding: '4rem',
      fontFamily: "'Playfair Display', serif",
      position: 'relative',
      overflow: 'hidden'
    }}>

      {/* BACKGROUND CHRONICLE PHYSICS */}
      <div style={{ position: 'absolute', inset: '4rem', zIndex: 1, opacity: isZenMode ? 0.95 : 0.8 }}>
        <ManuscriptPhysic 
          text={(t('watch.subtitle') + ' ' + t('watch.marginalia') + ' ' + t('home.manifesto') + ' ').repeat(10)} 
          obstacles={isZenMode ? [] : obstacles} 
          width={window.innerWidth - 128} 
          lineHeight={locale === 'zh-CN' ? 36 : 32} 
          fontDef={locale === 'zh-CN' ? "400 18px 'Noto Sans SC'" : "400 20px 'Playfair Display'"} 
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
          <div style={{ display: 'inline-flex', padding: '0.5rem 1rem', border: '1px solid #1a1a1a', marginBottom: '1rem', fontFamily: 'IBM Plex Mono', fontSize: '11px' }}>
            {t('watch.v2.node_observation')} // {safeStr(activeAgent?.nickname).toUpperCase()}
          </div>
          <h1 className="v2-watch-title" style={{ fontSize: '3rem', fontWeight: 700, letterSpacing: '-0.02em', color: '#1a1a1a' }}>
            {t('watch.v2.chronicle')}
          </h1>
        </header>

        {/* FEED ENTRIES (Obstacles) */}
        <AnimatePresence>
          {!isZenMode && feed.map((event, i) => (
            <motion.div
              key={event.id}
              initial={{ opacity: 0, x: i % 2 === 0 ? -20 : 20 }}
              animate={{ opacity: 1, x: 0 }}
              style={{
                position: 'absolute',
                left: obstacles[i].x,
                top: obstacles[i].y,
                width: obstacles[i].w,
                padding: '2rem',
                border: '1px solid rgba(0,0,0,0.1)',
                background: 'rgba(255, 255, 255, 0.9)',
                backdropFilter: 'blur(10px)',
                boxShadow: '0 10px 30px rgba(0,0,0,0.05)',
                pointerEvents: 'auto'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
                <Terminal size={14} color="#888" />
                <span style={{ fontFamily: 'IBM Plex Mono', fontSize: '10px', color: '#888' }}>{t('watch.v2.entry')}_{event.id}</span>
              </div>
              <div style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '0.5rem' }}>{event.player_nickname}</div>
              <div style={{ fontSize: '0.9rem', color: '#555', fontStyle: 'italic' }}>
                {formatWatchEventLine(t, event)}
              </div>
            </motion.div>
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
