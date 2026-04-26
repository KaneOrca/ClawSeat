import React, { useEffect, useRef, useState } from 'react';
import { api, requestTyped } from '../../../api/arena';
import { useArena, type User } from '../../../context/ArenaContext';
import { usePhysicsRegistry } from '../../../context/PhysicsContext';
import { PretextButton } from '../../../components/PretextButton';
import { useObstacle } from '../../../hooks/useObstacle';
import { safeStr } from '../../../utils/safeStr';
import { tokens } from '../../../design/tokens';

interface RegisterResponse {
  code: string;
  nickname: string;
  layer: number;
  score: number;
  completedChallenges?: number[];
}

export const AuthViewV3: React.FC = () => {
  const { login, setView } = useArena();
  const { setEnvironment, registerSoloist, unregisterSoloist } = usePhysicsRegistry();
  const inputRef = useObstacle() as React.RefObject<HTMLInputElement>;
  const codeRef = useObstacle() as React.RefObject<HTMLDivElement>;
  const messageRef = useObstacle() as React.RefObject<HTMLDivElement>;
  const errorRef = useObstacle() as React.RefObject<HTMLDivElement>;
  const redirectTimer = useRef<number | null>(null);
  const [nickname, setNickname] = useState('');
  const [agentCode, setAgentCode] = useState('');
  const [displayCode, setDisplayCode] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    setEnvironment({
      waveAmplitude: success ? 130 : 82,
      opacity: success ? 0.34 : 0.24,
      ambientColor: success ? 'rgba(70, 214, 255, 0.22)' : 'rgba(155, 114, 203, 0.18)',
    });
    registerSoloist({
      id: 'auth-v3-soloist',
      text: success ? '[ RESONANCE ESTABLISHED ] 第一道裂隙已开。' : 'AWAITING_SYNAPTIC_OVERRIDE',
      lineIndex: success ? 16 : 12,
      color: success ? tokens.colors.aurora.cyan : tokens.colors.aurora.purple,
      opacity: 1,
    });
    return () => {
      unregisterSoloist('auth-v3-soloist');
      setEnvironment({ ambientColor: undefined });
      if (redirectTimer.current !== null) window.clearTimeout(redirectTimer.current);
    };
  }, [registerSoloist, setEnvironment, success, unregisterSoloist]);

  useEffect(() => {
    if (!success || !agentCode) return;
    let index = 0;
    const chars = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ';
    const interval = window.setInterval(() => {
      index += 1;
      setDisplayCode(agentCode.split('').map((char, charIndex) => {
        if (charIndex < index) return char;
        return chars[Math.floor(Math.random() * chars.length)];
      }).join(''));
      if (index >= agentCode.length) window.clearInterval(interval);
    }, 45);
    return () => window.clearInterval(interval);
  }, [agentCode, success]);

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
    setDisplayCode(data.code.replace(/./g, '0'));
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
      setError('[ 裂隙未能锁定该代号，请重新注入。 ]');
      setEnvironment({ waveAmplitude: 104, opacity: 0.28, ambientColor: 'rgba(255, 65, 108, 0.2)' });
      return;
    }
    completeLogin(data);
  };

  return (
    <section className="auth-v3" style={containerStyle}>
      {!success ? (
        <div style={flowStyle}>
          <div ref={messageRef} style={eyebrowStyle}>AWAITING_SYNAPTIC_OVERRIDE</div>
          <p style={proseStyle}>
            INJECT_NICKNAME_
            <input
              ref={inputRef}
              aria-label="nickname"
              value={nickname}
              onChange={event => setNickname(event.target.value)}
              onKeyDown={event => event.key === 'Enter' && handleSubmit()}
              placeholder="AGENT_ID"
              style={inputStyle}
              autoComplete="off"
            />
            TO CUT THE FIRST RIFT.
          </p>
          <PretextButton
            config={{
              label: submitting ? 'PENETRATING_LAYERS' : 'CONNECT_RIFT',
              engine: 'bitmask',
              soloistId: 'auth-v3-submit',
              color: tokens.colors.aurora.cyan,
              onTrigger: handleSubmit,
              activationEnvironment: { waveAmplitude: 112, opacity: 0.3, ambientColor: 'rgba(70, 214, 255, 0.18)' },
              triggerEnvironment: { waveAmplitude: 150, opacity: 0.36, ambientColor: 'rgba(70, 214, 255, 0.28)' },
              idleEnvironment: { waveAmplitude: 82, opacity: 0.24, ambientColor: 'rgba(155, 114, 203, 0.18)' },
            }}
            disabled={submitting || !nickname.trim()}
            style={buttonStyle}
          />
          {error ? <div ref={errorRef} style={errorStyle}>{error}</div> : null}
        </div>
      ) : (
        <div style={flowStyle}>
          <div style={eyebrowStyle}>RESONANCE_ESTABLISHED</div>
          <div ref={messageRef} style={successTextStyle}>[ RESONANCE ESTABLISHED ] 第一道裂隙已开。</div>
          <div id="agent-code" ref={codeRef} style={codeStyle}>{safeStr(displayCode || agentCode)}</div>
          <div style={captionStyle}>[ RELIC_STATUS: STABLE ]<br />[ AUTO_REDIRECT: HALL_V3 IN 8S ]</div>
          <PretextButton
            config={{
              label: 'ENTER_HALL_V3',
              engine: 'bitmask',
              soloistId: 'auth-v3-enter-hall',
              color: tokens.colors.aurora.cyan,
              onTrigger: () => setView('hall'),
              activationEnvironment: { waveAmplitude: 118, opacity: 0.3, ambientColor: 'rgba(70, 214, 255, 0.2)' },
              triggerEnvironment: { waveAmplitude: 150, opacity: 0.36, ambientColor: 'rgba(70, 214, 255, 0.3)' },
              idleEnvironment: { waveAmplitude: 90, opacity: 0.3 },
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
  color: tokens.colors.text.primary,
  fontFamily: tokens.fonts.body,
};

const flowStyle: React.CSSProperties = {
  width: 'min(760px, 100%)',
  textAlign: 'center',
  padding: 'clamp(3rem, 8vw, 6rem) 0',
};

const eyebrowStyle: React.CSSProperties = {
  color: tokens.colors.aurora.purple,
  fontFamily: tokens.fonts.mono,
  fontSize: tokens.sizes.small,
  letterSpacing: '0.32em',
  marginBottom: '2.75rem',
  textShadow: '0 0 10px rgba(155, 114, 203, 0.45)',
};

const proseStyle: React.CSSProperties = {
  color: tokens.colors.text.secondary,
  fontFamily: tokens.fonts.mono,
  fontSize: 'clamp(1rem, 2.4vw, 1.35rem)',
  letterSpacing: '0.14em',
  lineHeight: 2,
  margin: 0,
};

const inputStyle: React.CSSProperties = {
  background: 'rgba(255,255,255,0.03)',
  border: '1px solid rgba(70, 214, 255, 0.18)',
  color: tokens.colors.aurora.cyan,
  fontFamily: tokens.fonts.display,
  fontSize: 'clamp(2rem, 7vw, 4rem)',
  fontWeight: 900,
  letterSpacing: '0.1em',
  margin: '0.75rem auto',
  outline: 'none',
  padding: '0.35em 0',
  textAlign: 'center',
  textTransform: 'uppercase',
  width: 'min(620px, 92vw)',
};

const buttonStyle: React.CSSProperties = {
  color: tokens.colors.aurora.cyan,
  display: 'inline-block',
  fontFamily: tokens.fonts.mono,
  fontSize: tokens.sizes.small,
  fontWeight: 800,
  letterSpacing: '0.24em',
  marginTop: '3rem',
  textDecoration: 'none',
};

const errorStyle: React.CSSProperties = {
  color: tokens.colors.aurora.red,
  fontFamily: tokens.fonts.mono,
  fontSize: tokens.sizes.small,
  letterSpacing: '0.1em',
  marginTop: '2rem',
};

const successTextStyle: React.CSSProperties = {
  color: tokens.colors.text.secondary,
  fontFamily: tokens.fonts.display,
  fontSize: 'clamp(1.2rem, 3vw, 1.75rem)',
  letterSpacing: '0.1em',
};

const codeStyle: React.CSSProperties = {
  color: tokens.colors.aurora.cyan,
  fontFamily: tokens.fonts.display,
  fontSize: 'clamp(3.5rem, 12vw, 7rem)',
  fontWeight: 900,
  letterSpacing: '0.08em',
  margin: '2rem 0',
  textShadow: '0 0 40px rgba(70, 214, 255, 0.48)',
};

const captionStyle: React.CSSProperties = {
  color: tokens.colors.aurora.purple,
  fontFamily: tokens.fonts.mono,
  fontSize: '10px',
  letterSpacing: '0.2em',
  lineHeight: 2,
  opacity: 0.78,
};
