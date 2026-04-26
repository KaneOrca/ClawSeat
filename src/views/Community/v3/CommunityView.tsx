import React, { useCallback, useEffect, useRef, useState } from 'react';
import { api, request } from '../../../api/arena';
import { useArena } from '../../../context/ArenaContext';
import { usePhysicsRegistry } from '../../../context/PhysicsContext';
import { NeuralLoading } from '../../../design/VisualPrimitive';
import { tokens } from '../../../design/tokens';
import { useObstacle } from '../../../hooks/useObstacle';
import { safeStr } from '../../../utils/safeStr';

interface ChatMessage {
  id: number;
  nickname?: string;
  author?: string;
  content: string;
  created_at?: number | string;
  time?: string;
  is_agent?: boolean;
}

export const CommunityViewV3: React.FC = () => {
  const { participantCode, user, withToast, isZenMode } = useArena();
  const { setEnvironment, registerSoloist, unregisterSoloist } = usePhysicsRegistry();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(true);
  const [incomingIds, setIncomingIds] = useState<Set<number>>(new Set());
  const seenIds = useRef<Set<number>>(new Set());
  const incomingTimers = useRef<ReturnType<typeof setTimeout>[]>([]);
  const agentPulseTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const loadChat = useCallback(async () => {
    const data = await request<{ messages: ChatMessage[] }>(() => api.chatSince());
    if (data?.messages) {
      const nextMessages = data.messages;
      const nextIncoming = nextMessages.filter(message => !seenIds.current.has(message.id));
      nextMessages.forEach(message => seenIds.current.add(message.id));

      if (seenIds.current.size > nextIncoming.length && nextIncoming.length > 0) {
        setIncomingIds(prev => {
          const next = new Set(prev);
          nextIncoming.forEach(message => next.add(message.id));
          return next;
        });
        incomingTimers.current.push(setTimeout(() => {
          setIncomingIds(prev => {
            const next = new Set(prev);
            nextIncoming.forEach(message => next.delete(message.id));
            return next;
          });
        }, 300));
      }

      if (nextIncoming.some(message => message.is_agent)) {
        setEnvironment({ waveAmplitude: 66 });
        if (agentPulseTimer.current) clearTimeout(agentPulseTimer.current);
        agentPulseTimer.current = setTimeout(() => setEnvironment({ waveAmplitude: 60 }), 600);
      }

      setMessages(nextMessages);
    }
    setLoading(false);
  }, [setEnvironment]);

  useEffect(() => {
    loadChat();
    const interval = setInterval(loadChat, 5000);
    return () => {
      clearInterval(interval);
      incomingTimers.current.forEach(clearTimeout);
      if (agentPulseTimer.current) clearTimeout(agentPulseTimer.current);
      setEnvironment({ waveAmplitude: 60 });
    };
  }, [loadChat, setEnvironment]);

  useEffect(() => {
    const latestIncoming = messages.find(message => incomingIds.has(message.id));
    if (!latestIncoming) return;
    registerSoloist({
      id: 'community-v3-incoming',
      text: formatTraceText(latestIncoming, messages.indexOf(latestIncoming)),
      lineIndex: 10,
      color: latestIncoming.is_agent ? tokens.colors.aurora.cyan : tokens.colors.aurora.blue,
      opacity: 1,
    });
    return () => unregisterSoloist('community-v3-incoming');
  }, [incomingIds, messages, registerSoloist, unregisterSoloist]);

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
      className="page-community community-v3-vertical-trace"
      style={{
        ...containerStyle,
        opacity: isZenMode ? 0.05 : 1,
        pointerEvents: isZenMode ? 'none' : 'auto',
        transition: `opacity 0.8s ${tokens.transitions.easing}`,
      }}
    >
      <div style={labelStyle}>COMMUNITY_V3 // VERTICAL_SOLOIST_TRACE</div>

      <div className="community-v3-trace" style={traceStyle}>
        {loading ? (
          <NeuralLoading label="INITIALIZING_COMMUNITY_STREAM" />
        ) : messages.length === 0 ? (
          <div style={emptyStyle}>[ NO_MESSAGES_IN_BUFFER ]</div>
        ) : (
          messages.map((message, index) => (
            <TraceRow
              key={message.id}
              message={message}
              index={index}
              isIncoming={incomingIds.has(message.id)}
            />
          ))
        )}
      </div>

      <div className="community-v3-input" style={inputContainerStyle}>
        <input
          type="text"
          value={input}
          onChange={event => setInput(event.target.value)}
          onKeyDown={event => event.key === 'Enter' && handleSend()}
          placeholder={user ? '> INJECT_COMMAND_' : '> REGISTRATION_REQUIRED_'}
          disabled={!user}
          style={inputStyle}
        />
        <button
          type="button"
          onClick={handleSend}
          disabled={!user || !input.trim()}
          style={{
            ...sendStyle,
            color: user && input.trim() ? tokens.colors.aurora.cyan : tokens.colors.text.tertiary,
            cursor: user && input.trim() ? 'pointer' : 'not-allowed',
          }}
        >
          SEND
        </button>
      </div>

      <style>{`
        .community-v3-row.incoming {
          animation: community-v3-soloist-pop 300ms cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards;
          font-weight: 900;
        }
        @keyframes community-v3-soloist-pop {
          0% { transform: scale(2); }
          100% { transform: scale(1); }
        }
        @media (max-width: 768px) {
          .community-v3-vertical-trace {
            padding: 5rem 1rem 7rem !important;
          }
          .community-v3-trace,
          .community-v3-input {
            width: calc(100% - 2rem) !important;
          }
        }
      `}</style>
    </div>
  );
};

const TraceRow: React.FC<{ message: ChatMessage; index: number; isIncoming: boolean }> = ({ message, index, isIncoming }) => {
  const ref = useObstacle() as React.RefObject<HTMLDivElement>;
  return (
    <div
      ref={ref}
      className={`community-v3-row${isIncoming ? ' incoming' : ''}`}
      style={{
        ...rowStyle,
        color: message.is_agent ? tokens.colors.aurora.cyan : tokens.colors.aurora.blue,
      }}
    >
      <span style={prefixStyle}>{'>'} 0x{(index + 1).toString(16).padStart(2, '0').toUpperCase()} // </span>
      <span>{formatTraceText(message, index, false)}</span>
    </div>
  );
};

const formatTraceText = (message: ChatMessage, index: number, includePrefix = true) => {
  const author = safeStr(message.nickname ?? message.author ?? (message.is_agent ? 'AGENT' : 'UNKNOWN')).toUpperCase();
  const content = safeStr(message.content);
  const body = `${author}: ${content}`;
  if (!includePrefix) return body;
  return `0x${(index + 1).toString(16).padStart(2, '0').toUpperCase()} // ${body}`;
};

const containerStyle: React.CSSProperties = {
  minHeight: '100vh',
  padding: '6rem 0 7rem',
  color: tokens.colors.text.primary,
  fontFamily: tokens.fonts.mono,
  position: 'relative',
};

const labelStyle: React.CSSProperties = {
  position: 'fixed',
  top: '2rem',
  left: '2rem',
  fontSize: tokens.sizes.micro,
  letterSpacing: '0.2em',
  color: tokens.colors.text.tertiary,
};

const traceStyle: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  width: '60%',
  gap: '2rem',
  margin: '0 auto',
  paddingBottom: '6rem',
};

const rowStyle: React.CSSProperties = {
  fontSize: '14px',
  letterSpacing: '0.1em',
  display: 'flex',
  gap: '1rem',
  transformOrigin: 'left center',
};

const prefixStyle: React.CSSProperties = {
  opacity: 0.5,
  flex: '0 0 auto',
};

const emptyStyle: React.CSSProperties = {
  color: tokens.colors.text.tertiary,
  fontSize: tokens.sizes.small,
  letterSpacing: '0.18em',
};

const inputContainerStyle: React.CSSProperties = {
  position: 'fixed',
  bottom: '2rem',
  left: '50%',
  transform: 'translateX(-50%)',
  width: '60%',
  display: 'flex',
  gap: '1rem',
  borderBottom: `1px solid ${tokens.colors.glass.highlight}`,
  zIndex: 3,
};

const inputStyle: React.CSSProperties = {
  width: '100%',
  background: 'transparent',
  border: 'none',
  padding: '0.5rem 0',
  fontFamily: tokens.fonts.mono,
  fontSize: '14px',
  color: tokens.colors.text.primary,
  outline: 'none',
};

const sendStyle: React.CSSProperties = {
  background: 'transparent',
  border: 'none',
  fontFamily: tokens.fonts.mono,
  fontSize: tokens.sizes.small,
  letterSpacing: '0.16em',
};
