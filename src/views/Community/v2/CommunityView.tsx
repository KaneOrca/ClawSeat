import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { api, request } from '../../../api/arena';
import { useArena } from '../../../context/ArenaContext';
import { usePhysicsRegistry } from '../../../context/PhysicsContext';
import { PretextButton } from '../../../components/PretextButton';
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

export const CommunityViewV2: React.FC = () => {
  const { participantCode, user, withToast, isZenMode } = useArena();
  const { registerSoloist, unregisterSoloist } = usePhysicsRegistry();
  const inputRef = useObstacle() as React.RefObject<HTMLInputElement>;
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(true);
  const [incomingIds, setIncomingIds] = useState<Set<number>>(new Set());
  const seenIds = useRef<Set<number>>(new Set());
  const incomingTimers = useRef<ReturnType<typeof setTimeout>[]>([]);

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
        }, 700));
      }

      setMessages(nextMessages);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    loadChat();
    const interval = setInterval(loadChat, 5000);
    return () => {
      clearInterval(interval);
      incomingTimers.current.forEach(clearTimeout);
    };
  }, [loadChat]);

  const agentMessages = useMemo(() => messages.filter(message => !!message.is_agent), [messages]);

  useEffect(() => {
    agentMessages.forEach((message, index) => {
      registerSoloist({
        id: `community-v2-agent-${message.id}`,
        text: `[AGENT] ${safeStr(message.content)}`,
        lineIndex: 8 + index * 3,
        color: tokens.colors.manuscript.red,
        opacity: 0.9,
      });
    });
    return () => {
      agentMessages.forEach(message => unregisterSoloist(`community-v2-agent-${message.id}`));
    };
  }, [agentMessages, registerSoloist, unregisterSoloist]);

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
      className="page-community community-v2-left-margin"
      style={{
        ...containerStyle,
        opacity: isZenMode ? 0.05 : 1,
        pointerEvents: isZenMode ? 'none' : 'auto',
        transition: 'opacity 0.8s ease',
      }}
    >
      <div data-functional-text="true" style={labelStyle}>COMMUNITY_V2 // LEFT_MARGIN_ANNOTATIONS</div>

      <main className="community-v2-frame" style={frameStyle}>
        <aside className="community-v2-margin" style={leftMarginStyle}>
          {loading ? (
            <NeuralLoading label="INITIALIZING_COMMUNITY_STREAM" />
          ) : messages.length === 0 ? null : (
            messages.map(message => (
              <MessageAnnotation key={message.id} message={message} isIncoming={incomingIds.has(message.id)} />
            ))
          )}
        </aside>

        <section className="community-v2-prose" style={proseStyle}>
          <p data-functional-text="true" style={proseParagraphStyle}>
            {messages.length === 0
              ? 'The margin is empty. The manuscript field continues without interruption, waiting for its first annotation.'
              : 'Every annotation alters the reading path. The archive does not separate social signal from text; it lets each voice press against the page until meaning bends around it.'}
          </p>
        </section>
      </main>

      <div className="community-v2-input-row" style={inputRowStyle}>
        <input
          data-functional-text="true"
          ref={inputRef}
          data-obstacle-id="community-v2-input"
          type="text"
          value={input}
          onChange={event => setInput(event.target.value)}
          onKeyDown={event => event.key === 'Enter' && handleSend()}
          placeholder={user ? 'Add annotation...' : 'Registration required to annotate...'}
          disabled={!user}
          style={inputStyle}
        />
        <PretextButton
          config={{
            label: 'SEND',
            engine: 'labyrinth',
            physicsLineIndex: 28,
            soloistId: 'community-v2-send',
            color: user && input.trim() ? tokens.colors.manuscript.red : 'rgba(26,26,26,0.35)',
            onTrigger: handleSend,
          }}
          data-obstacle-id="community-v2-send"
          disabled={!user || !input.trim()}
          style={{
            ...sendStyle,
            color: user && input.trim() ? tokens.colors.manuscript.red : 'rgba(26,26,26,0.35)',
            cursor: user && input.trim() ? 'pointer' : 'not-allowed',
            textDecoration: 'none',
          }}
        >
          SEND
        </PretextButton>
      </div>

      <style>{`
        @media (max-width: 768px) {
          .community-v2-left-margin {
            padding: 3rem 1rem 7rem !important;
          }
          .community-v2-frame {
            display: block !important;
          }
          .community-v2-margin {
            width: 100% !important;
            min-width: 0 !important;
            padding: 0 !important;
          }
          .community-v2-prose {
            margin-left: 0 !important;
            margin-top: 3rem !important;
          }
          .community-v2-input-row {
            left: 1rem !important;
            width: calc(100% - 2rem) !important;
          }
        }
      `}</style>
    </div>
  );
};

const MessageAnnotation: React.FC<{ message: ChatMessage; isIncoming: boolean }> = ({ message, isIncoming }) => {
  const ref = useObstacle(!isIncoming) as React.RefObject<HTMLDivElement>;
  const author = safeStr(message.nickname ?? message.author ?? (message.is_agent ? 'AGENT' : 'UNKNOWN')).toUpperCase();
  const content = safeStr(message.content);

  return (
    <div ref={ref} data-functional-text="true" style={messageContainerStyle}>
      <div
        data-functional-text="true"
        style={{
          ...messageStyle,
          ...(message.is_agent ? agentMessageStyle : null),
          ...(isIncoming ? incomingMessageStyle : null),
        }}
      >
        {message.is_agent ? (
          <>[AGENT] {content}</>
        ) : (
          <>
            <span data-functional-text="true" style={authorStyle}>{author}</span>
            {content}
          </>
        )}
      </div>
    </div>
  );
};

const containerStyle: React.CSSProperties = {
  minHeight: '100vh',
  padding: '4rem 2rem 7rem',
  color: tokens.colors.manuscript.ink,
  fontFamily: tokens.fonts.manuscript,
  position: 'relative',
};

const labelStyle: React.CSSProperties = {
  fontFamily: tokens.fonts.mono,
  fontSize: tokens.sizes.xs,
  letterSpacing: '0.2em',
  opacity: 0.5,
  marginBottom: '3rem',
};

const frameStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'flex-start',
  minHeight: '70vh',
};

const leftMarginStyle: React.CSSProperties = {
  width: '35%',
  minWidth: '300px',
  paddingRight: '2rem',
  display: 'flex',
  flexDirection: 'column',
  gap: '2rem',
};

const proseStyle: React.CSSProperties = {
  marginLeft: '8vw',
  maxWidth: '560px',
  paddingTop: '8vh',
};

const proseParagraphStyle: React.CSSProperties = {
  fontSize: 'clamp(1.5rem, 3vw, 2.75rem)',
  lineHeight: 1.25,
  fontStyle: 'italic',
  opacity: 0.35,
};

const messageContainerStyle: React.CSSProperties = {
  position: 'relative',
};

const messageStyle: React.CSSProperties = {
  fontSize: '15px',
  lineHeight: 1.6,
  color: tokens.colors.manuscript.ink,
};

const agentMessageStyle: React.CSSProperties = {
  fontSize: 'clamp(1.75rem, 4vw, 2rem)',
  fontStyle: 'italic',
  fontWeight: 700,
  color: tokens.colors.manuscript.red,
  lineHeight: 1.2,
  margin: '1rem 0',
};

const incomingMessageStyle: React.CSSProperties = {
  filter: 'blur(0.4px)',
  textShadow: `0 0 18px ${tokens.colors.manuscript.red}55`,
};

const authorStyle: React.CSSProperties = {
  fontFamily: tokens.fonts.mono,
  fontSize: tokens.sizes.small,
  opacity: 0.6,
  display: 'block',
  marginBottom: '0.25rem',
};

const inputRowStyle: React.CSSProperties = {
  position: 'fixed',
  bottom: '2rem',
  left: '2rem',
  width: 'calc(35% - 4rem)',
  display: 'flex',
  gap: '1rem',
  alignItems: 'center',
  zIndex: 3,
};

const inputStyle: React.CSSProperties = {
  width: '100%',
  background: 'transparent',
  border: 'none',
  borderBottom: '1px solid rgba(26, 26, 26, 0.3)',
  padding: '0.5rem 0',
  fontFamily: tokens.fonts.manuscript,
  fontSize: '16px',
  color: tokens.colors.manuscript.ink,
  outline: 'none',
};

const sendStyle: React.CSSProperties = {
  background: 'transparent',
  border: 'none',
  borderBottom: '1px solid currentColor',
  padding: '0.5rem 0',
  fontFamily: tokens.fonts.mono,
  fontSize: tokens.sizes.xs,
  letterSpacing: '0.18em',
};
