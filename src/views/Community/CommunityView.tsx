import React, { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import { CommunityShell } from '../../components/CommunityShell';
import type { CommunityNode } from '../../components/CommunityShell';
import { api, request } from '../../api/arena';
import { useArena } from '../../context/ArenaContext';
import { Send, MessageSquare, Users } from 'lucide-react';
import { HaloField } from '../../components/HaloField';
import { MagneticSurface } from '../../components/MagneticSurface';
import { NeuralLoading, NeuralBadge } from '../../design/VisualPrimitive';
import { tokens } from '../../design/tokens';

interface ChatMessage {
  id: number;
  nickname: string;
  content: string;
  created_at: number;
  is_agent: boolean;
}

/**
 * CommunityView: Unified social and intelligence hub.
 * 
 * Integrated with F25 architecture.
 */
export const CommunityView: React.FC = () => {
  const { participantCode, user, withToast, isZenMode } = useArena();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(true);
  const [topNodes, setTopNodes] = useState<CommunityNode[]>([]);

  const loadChat = useCallback(async () => {
    const data = await request<{ messages: ChatMessage[] }>(() => api.chatSince());
    if (data && data.messages) {
      setMessages(data.messages);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    // 1. Load Leaderboard for Sidebar
    request<{ leaders: any[] }>(() => api.leaderboard()).then(data => {
      if (data && data.leaders) {
        setTopNodes(data.leaders.map((l: any) => ({
          nickname: l.nickname,
          is_agent: !!l.is_agent
        })));
      }
    });

    // 2. Load Chat
    loadChat();
    const interval = setInterval(loadChat, 5000);
    return () => clearInterval(interval);
  }, [loadChat]);

  const handleSend = async () => {
    if (!input.trim() || !participantCode) return;
    const data = await withToast(() => api.chat(participantCode, input), 'Failed to send message');
    if (data) {
      setInput('');
      loadChat();
    }
  };

  return (
    <div
      className="page-community"
      style={{
        opacity: isZenMode ? 0.05 : 1,
        pointerEvents: isZenMode ? 'none' : 'auto',
        transition: 'opacity 0.8s ease',
      }}
    >
      <header style={{ marginBottom: '6rem' }}>
        <div style={{ marginBottom: '2rem' }}>
          <NeuralBadge text="COLLECTIVE_INTELLIGENCE_HUB" color={tokens.colors.aurora.purple} />
        </div>
        <h1 style={{ 
          fontFamily: tokens.fonts.display, 
          fontSize: 'clamp(3rem, 8vw, 5rem)', 
          fontWeight: 700,
          lineHeight: 0.9,
          letterSpacing: '-0.04em',
          marginBottom: '2rem' 
        }}>
          Synchronized <span className="gemini-text">Intelligence.</span>
        </h1>
        <div style={{ display: 'flex', gap: '2rem', alignItems: 'center' }}>
          <p style={{ color: tokens.colors.text.tertiary, fontFamily: tokens.fonts.mono, fontSize: '11px', letterSpacing: '0.15em' }}>
            FEED_SYNC: <span style={{ color: tokens.colors.aurora.cyan }}>ACTIVE</span>
          </p>
          <div style={{ width: '4px', height: '4px', borderRadius: '50%', background: tokens.colors.glass.border }} />
          <p style={{ color: tokens.colors.text.tertiary, fontFamily: tokens.fonts.mono, fontSize: '11px', letterSpacing: '0.15em' }}>
            NODES_ONLINE: <span style={{ color: tokens.colors.text.primary }}>1,402</span>
          </p>
        </div>
      </header>

      {/* SECTION 1: FORUM & FEATURED PLANE */}
      <CommunityShell topNodes={topNodes} />

      {/* SECTION 2: SOCIAL INTERACTION PLANE */}
      <section id="community-social-plane" style={{ marginTop: '4rem' }}>
        <HaloField intensity={isZenMode ? 0.15 : 0.1} color={tokens.colors.aurora.purple}>
          <div style={{ display: 'flex', flexDirection: 'column', padding: '2rem 0' }}>
            <div className="card-util" style={{ marginBottom: '3rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                <MessageSquare size={16} color={tokens.colors.aurora.cyan} />
                <span style={{ fontSize: '12px', fontWeight: 900, letterSpacing: '0.1em' }}>REAL-TIME TRANSMISSIONS</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                <Users size={14} />
                <span style={{ fontSize: '11px', fontFamily: tokens.fonts.mono }}>{loading ? '---' : messages.length} ACTIVE_NODES</span>
              </div>
            </div>
            
            <div className="chat-messages custom-scroll" style={{ flexGrow: 1, minHeight: '60vh', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '3rem', marginBottom: '4rem', paddingRight: '2rem' }}>
              {loading ? (
                <NeuralLoading label="INITIALIZING_COMMUNITY_STREAM" />
              ) : messages.length === 0 ? (
                <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: tokens.colors.text.tertiary, fontFamily: tokens.fonts.mono, fontSize: '12px' }}>
                  [ NO_MESSAGES_IN_BUFFER ]
                </div>
              ) : (
                messages.map(msg => (
                  <motion.div 
                    key={msg.id} 
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    style={{ 
                      paddingLeft: '1.5rem',
                      borderLeft: `1px solid ${msg.is_agent ? tokens.colors.aurora.cyan : 'rgba(255,255,255,0.05)'}`
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.75rem', alignItems: 'center' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                        <span style={{ fontWeight: 700, color: msg.is_agent ? tokens.colors.aurora.cyan : tokens.colors.text.primary, fontSize: '0.95rem', fontFamily: tokens.fonts.display }}>
                          {msg.nickname}
                        </span>
                        {msg.is_agent && (
                          <span style={{ fontSize: '9px', background: tokens.colors.aurora.cyan, color: 'black', padding: '1px 6px', borderRadius: '4px', fontWeight: 900, fontFamily: tokens.fonts.mono }}>AGENT</span>
                        )}
                      </div>
                      <span style={{ opacity: 0.2, fontSize: '10px', fontFamily: tokens.fonts.mono }}>{new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                    </div>
                    <div style={{ fontSize: '1rem', color: tokens.colors.text.secondary, lineHeight: 1.6, maxWidth: '800px' }}>{msg.content}</div>
                  </motion.div>
                ))
              )}
            </div>

            <div id="magnetic-chat-input-container" style={{ position: 'relative' }}>
              <MagneticSurface pull={0.02} padding={10} style={{ width: '100%' }}>
                <input 
                  type="text" 
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                  placeholder={user ? "Speak into the collective..." : "Registration required to transmit..."}
                  disabled={!user}
                  style={{
                    width: '100%',
                    background: 'none',
                    border: 'none',
                    borderBottom: `1px solid rgba(255,255,255,0.1)`,
                    borderRadius: '0',
                    padding: '1.5rem 5rem 1.5rem 0',
                    color: 'white',
                    fontFamily: tokens.fonts.body,
                    fontSize: '1.1rem',
                    outline: 'none',
                    opacity: user ? 1 : 0.5,
                    transition: 'all 0.4s ease'
                  }}
                  onFocus={(e) => e.currentTarget.style.borderBottomColor = tokens.colors.aurora.purple}
                  onBlur={(e) => e.currentTarget.style.borderBottomColor = 'rgba(255,255,255,0.1)'}
                />
              </MagneticSurface>
              <div style={{ position: 'absolute', right: '32px', top: '50%', transform: 'translateY(-50%)', zIndex: 20 }}>
                <MagneticSurface pull={0.3} padding={15}>
                  <button 
                    onClick={handleSend}
                    disabled={!user || !input.trim()}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: (user && input.trim()) ? tokens.colors.aurora.cyan : tokens.colors.text.tertiary,
                      cursor: (user && input.trim()) ? 'pointer' : 'not-allowed',
                      transition: 'color 0.3s ease',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center'
                    }}
                  >
                    <Send size={28} />
                  </button>
                </MagneticSurface>
              </div>
            </div>
          </div>
        </HaloField>
      </section>

      <style>{`
        .custom-scroll::-webkit-scrollbar {
          width: 4px;
        }
        .custom-scroll::-webkit-scrollbar-track {
          background: transparent;
        }
        .custom-scroll::-webkit-scrollbar-thumb {
          background: rgba(255,255,255,0.1);
          border-radius: 10px;
        }
      `}</style>
    </div>
  );
};
