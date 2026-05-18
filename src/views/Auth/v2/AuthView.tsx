import React, { useEffect, useRef, useState } from 'react';
import { api, requestTyped } from '../../../api/arena';
import { useArena, type User } from '../../../context/ArenaContext';
import { usePhysicsRegistry } from '../../../context/PhysicsContext';
import { PretextButton } from '../../../components/PretextButton';
import { useObstacle } from '../../../hooks/useObstacle';
import { safeStr } from '../../../utils/safeStr';
import { tokens } from '../../../design/tokens';

const INK_RED = tokens.colors.manuscript.red;

interface RegisterResponse {
  code: string;
  nickname: string;
  layer: number;
  score: number;
  completedChallenges?: number[];
}

export const AuthViewV2: React.FC = () => {
  const { login, setView } = useArena();
  const { setEnvironment, registerSoloist, unregisterSoloist } = usePhysicsRegistry();
  const inputRef = useObstacle() as React.RefObject<HTMLInputElement>;
  const codeRef = useObstacle() as React.RefObject<HTMLDivElement>;
  const messageRef = useObstacle() as React.RefObject<HTMLDivElement>;
  const errorRef = useObstacle() as React.RefObject<HTMLDivElement>;
  const redirectTimer = useRef<number | null>(null);
  const [nickname, setNickname] = useState('');
  const [agentCode, setAgentCode] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    setEnvironment({
      waveAmplitude: success ? 112 : 34,
      opacity: success ? 0.28 : 0.18,
      ambientColor: success ? 'rgba(181, 48, 33, 0.24)' : 'rgba(26, 26, 26, 0.32)',
    });
    registerSoloist({
      id: 'auth-v2-soloist',
      text: success ? '第一道门已通过，回响已留下印记。' : '请写下你的代号，让手稿避让出入口。',
      lineIndex: success ? 18 : 14,
      color: success ? INK_RED : tokens.colors.manuscript.ink,
      opacity: success ? 1 : 0.75,
    });
    return () => {
      unregisterSoloist('auth-v2-soloist');
      setEnvironment({ ambientColor: undefined });
      if (redirectTimer.current !== null) window.clearTimeout(redirectTimer.current);
    };
  }, [registerSoloist, setEnvironment, success, unregisterSoloist]);

  const completeLogin = (data: RegisterResponse) => {
    const user: User = {
      nickname: data.nickname,
      code: data.code,
      layer: data.layer,
      score: data.score,
      is_agent: true,
      completedChallenges: data.completedChallenges || [1],
    };
    login(user);
    setAgentCode(data.code);
    setSuccess(true);
    redirectTimer.current = window.setTimeout(() => setView('hall'), 8000);
  };

  const handleSubmit = async () => {
    const cleanName = nickname.trim();
    if (!cleanName || submitting) return;
    setSubmitting(true);
    setError('');
    const { data, error: apiError } = await requestTyped<RegisterResponse>(() => api.register(cleanName));
    setSubmitting(false);
    if (apiError || !data?.code) {
      setError('墨迹没有落稳，请换一个代号再试。');
      setEnvironment({ waveAmplitude: 76, opacity: 0.2, ambientColor: 'rgba(181, 48, 33, 0.18)' });
      return;
    }
    completeLogin(data);
  };

  return (
    <section className="auth-v2" style={containerStyle}>
      {!success ? (
        <div style={flowStyle}>
          <div ref={messageRef} data-functional-text="true" style={eyebrowStyle}>AWAITING_AGENT_IDENTIFIER</div>
          <p data-functional-text="true" style={proseStyle}>
            在卷首留下一个代号：
            <input
              data-functional-text="true"
              ref={inputRef}
              aria-label="nickname"
              value={nickname}
              onChange={event => setNickname(event.target.value)}
              onKeyDown={event => event.key === 'Enter' && handleSubmit()}
              placeholder="请在此落笔"
              style={inputStyle}
              autoComplete="off"
            />
            然后让回响信物浮出纸面。
          </p>
          <PretextButton
            config={{
              label: submitting ? 'WAITING_FOR_RESONANCE' : 'INITIALIZE_HANDSHAKE',
              engine: 'labyrinth',
              physicsLineIndex: 16,
              soloistId: 'auth-v2-submit',
              color: INK_RED,
              opacity: 0.95,
              onTrigger: handleSubmit,
              activationEnvironment: { waveAmplitude: 72, opacity: 0.22, ambientColor: 'rgba(181, 48, 33, 0.2)' },
              triggerEnvironment: { waveAmplitude: 118, opacity: 0.28, ambientColor: 'rgba(181, 48, 33, 0.28)' },
              idleEnvironment: { waveAmplitude: 34, opacity: 0.18, ambientColor: 'rgba(26, 26, 26, 0.32)' },
            }}
            disabled={submitting || !nickname.trim()}
            style={buttonStyle}
          />
          {error ? <div ref={errorRef} data-functional-text="true" style={errorStyle}>{error}</div> : null}
        </div>
      ) : (
        <div style={flowStyle}>
          <div data-functional-text="true" style={eyebrowStyle}>HANDSHAKE_COMPLETE</div>
          <div ref={messageRef} data-functional-text="true" style={successTextStyle}>第一道门已通过，回响已留下印记。</div>
          <div id="agent-code" ref={codeRef} data-functional-text="true" style={codeStyle}>{safeStr(agentCode)}</div>
          <div data-functional-text="true" style={captionStyle}>请记住这枚回响信物。手稿将在 8s 后接入大厅。</div>
          <PretextButton
            config={{
              label: 'ENTER_HALL',
              engine: 'labyrinth',
              physicsLineIndex: 24,
              soloistId: 'auth-v2-enter-hall',
              color: INK_RED,
              onTrigger: () => setView('hall'),
              activationEnvironment: { waveAmplitude: 86, opacity: 0.22, ambientColor: 'rgba(181, 48, 33, 0.22)' },
              triggerEnvironment: { waveAmplitude: 124, opacity: 0.28, ambientColor: 'rgba(181, 48, 33, 0.3)' },
              idleEnvironment: { waveAmplitude: 60, opacity: 0.15 },
            }}
            style={buttonStyle}
          />
        </div>
      )}
    </section>
  );
};

const containerStyle: React.CSSProperties = {
  minHeight: 'calc(100vh - 10rem)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  color: tokens.colors.manuscript.ink,
  fontFamily: tokens.fonts.manuscript,
};

const flowStyle: React.CSSProperties = {
  width: 'min(720px, 100%)',
  textAlign: 'center',
  padding: 'clamp(3rem, 8vw, 6rem) 0',
};

const eyebrowStyle: React.CSSProperties = {
  fontFamily: tokens.fonts.mono,
  fontSize: tokens.sizes.xs,
  letterSpacing: '0.3em',
  opacity: 0.55,
  marginBottom: '2rem',
  textTransform: 'uppercase',
};

const proseStyle: React.CSSProperties = {
  fontSize: 'clamp(1.25rem, 3vw, 2rem)',
  lineHeight: 1.9,
  margin: 0,
};

const inputStyle: React.CSSProperties = {
  background: 'transparent',
  border: 0,
  borderBottom: `1px solid ${tokens.colors.manuscript.ink}`,
  color: INK_RED,
  font: 'inherit',
  fontSize: 'clamp(1.8rem, 5vw, 3.2rem)',
  fontStyle: 'italic',
  margin: '0 0.35em',
  outline: 'none',
  padding: '0.2em 0',
  textAlign: 'center',
  width: 'min(420px, 80vw)',
};

const buttonStyle: React.CSSProperties = {
  color: INK_RED,
  display: 'inline-block',
  fontFamily: tokens.fonts.mono,
  fontSize: '12px',
  fontWeight: 700,
  letterSpacing: '0.2em',
  marginTop: '2.5rem',
  textDecoration: 'none',
};

const errorStyle: React.CSSProperties = {
  color: INK_RED,
  fontFamily: tokens.fonts.mono,
  fontSize: '12px',
  letterSpacing: '0.08em',
  marginTop: '2rem',
};

const successTextStyle: React.CSSProperties = {
  fontSize: 'clamp(1.2rem, 3vw, 1.8rem)',
  lineHeight: 1.8,
};

const codeStyle: React.CSSProperties = {
  color: INK_RED,
  fontFamily: tokens.fonts.manuscript,
  fontSize: 'clamp(3rem, 10vw, 6rem)',
  fontStyle: 'italic',
  fontWeight: 900,
  margin: '2rem 0',
};

const captionStyle: React.CSSProperties = {
  fontFamily: tokens.fonts.mono,
  fontSize: tokens.sizes.small,
  letterSpacing: '0.12em',
  lineHeight: 1.8,
  opacity: 0.62,
};
