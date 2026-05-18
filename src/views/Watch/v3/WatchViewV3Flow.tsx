import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useArena } from '../../../context/ArenaContext';
import { useLanguage } from '../../../context/LanguageContext';
import { api, request, requestTyped } from '../../../api/arena';
import { safeStr } from '../../../utils/safeStr';
import { tokens } from '../../../design/tokens';
import {
  ambientDrift,
  createAnimationController,
  cursorRipple,
  hitTest,
  wave,
  type AnimationController,
  type CharacterTransform,
  type Embed,
  type FlowLine,
  type FlowResult,
  type ResolvedEmbed,
} from 'pretext-flow';

type KnownFeedEventType = 'joined' | 'completed_challenge' | 'unlocked_achievement';

type ViewMode = 'feed' | 'session';
type SessionStatus = 'loading' | 'thinking' | 'solved' | 'idle' | 'error';

interface RawFeedEvent {
  id: number;
  player_nickname?: string;
  nickname?: string;
  player_id?: string;
  player_code?: string;
  event_type: KnownFeedEventType | (string & {});
  target_id?: string;
  created_at?: number | string;
}

interface WatchSessionResponse {
  id: number;
  player_code: string;
  challenge_id: number;
  status?: string;
  steps?: unknown;
}

interface FeedEmbedData {
  kind: 'feed';
  playerName: string;
  eventType: string;
  targetId: string;
  color: string;
  originalEvent: RawFeedEvent;
}

interface SessionStepEmbedData {
  kind: 'session-step';
  stepText: string;
  index: number;
  color: string;
}

interface SessionMessageEmbedData {
  kind: 'session-message';
  text: string;
  color: string;
}

interface SessionBackEmbedData {
  kind: 'session-back';
  label: string;
  color: string;
}

type WatchEmbedData = FeedEmbedData | SessionStepEmbedData | SessionMessageEmbedData | SessionBackEmbedData;

const FLOW_POLL_INTERVAL_MS = 3000;
const FLOW_PULSE_MS = 800;
const BASE_FONT_SIZE = parseInt(tokens.sizes.md, 10);
const LINE_HEIGHT = Math.round(BASE_FONT_SIZE * 1.866);
const FEED_VISIBLE_COUNT = 6;
const FEED_EMBED_W = 300;
const FEED_EMBED_H = 40;
const SESSION_EMBED_W = 300;
const SESSION_EMBED_H = 38;
const BACK_EMBED_H = 36;
const FLOW_FONT = `${BASE_FONT_SIZE}px ${tokens.fonts.mono}`;
const CANVAS_PADDING = 16;

const normalizeSessionSteps = (steps: unknown): string[] => {
  if (!Array.isArray(steps)) return [];
  return steps.map(step => safeStr(step)).filter(Boolean);
};

const eventTypeLabel = (eventType: string, t: (keyPath: string) => string) => {
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

const buildLineColor = (lineIndex: number, totalLines: number) => {
  if (totalLines <= 1) return 'hsla(220, 86%, 52%, 0.84)';
  const progress = lineIndex / (totalLines - 1);
  const hue = 200 + 60 * progress;
  const lightness = 40 + 30 * (1 - Math.abs(0.5 - progress));
  const opacity = 0.6 + 0.3 * Math.max(0, 1 - progress);
  return `hsla(${Math.round(hue)}, 86%, ${Math.round(lightness)}%, ${Math.round(opacity * 100) / 100})`;
};

const wrapText = (ctx: CanvasRenderingContext2D, text: string, maxWidth: number) => {
  if (!text) return [''];
  if (ctx.measureText(text).width <= maxWidth) return [text];

  const words = text.split(' ');
  const lines: string[] = [];
  let current = '';

  for (const word of words) {
    const next = current ? `${current} ${word}` : word;
    if (!current || ctx.measureText(next).width <= maxWidth) {
      current = next;
    } else {
      lines.push(current);
      current = word;
    }
  }
  if (current) lines.push(current);
  return lines;
};

export const WatchViewV3Flow: React.FC = () => {
  const { showToast } = useArena();
  const { t } = useLanguage();

  const [loading, setLoading] = useState(true);
  const [feed, setFeed] = useState<RawFeedEvent[]>([]);
  const [viewMode, setViewMode] = useState<ViewMode>('feed');
  const [selectedPlayerName, setSelectedPlayerName] = useState<string | null>(null);
  const [selectedPlayerCode, setSelectedPlayerCode] = useState<string | null>(null);
  const [sessionSteps, setSessionSteps] = useState<string[]>([]);
  const [sessionStatus, setSessionStatus] = useState<SessionStatus>('idle');
  const [sessionMessage, setSessionMessage] = useState<string | null>(null);
  const [waveAmplitude, setWaveAmplitude] = useState(1);
  const [hoveredEmbedId, setHoveredEmbedId] = useState<string | null>(null);
  const [viewport, setViewport] = useState({ width: 0, height: 0 });

  const surfaceRef = useRef<HTMLDivElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const controllerRef = useRef<AnimationController | null>(null);
  const resultRef = useRef<FlowResult | null>(null);
  const pollRef = useRef<number | null>(null);
  const pulseRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const seenFeedIdsRef = useRef<Set<number>>(new Set());
  const viewModeRef = useRef<ViewMode>('feed');

  useEffect(() => {
    viewModeRef.current = viewMode;
  }, [viewMode]);

  const flowText = useMemo(() => {
    const chunks = [
      safeStr(t('watch.v3.header')),
      safeStr(t('watch.title')),
      safeStr(t('watch.subtitle')),
      safeStr(t('watch.marginalia')),
      safeStr(t('watch.chorus')),
      safeStr(t('home.manifesto')),
      safeStr(t('home.chorusExplanation')),
    ];
    return `${chunks.join(' // ')} `.repeat(20);
  }, [t]);

  const feedEmbeds = useMemo(() => {
    return feed.map((rawEvent, index): Embed => {
      const event = {
        ...rawEvent,
        event_type: safeStr(rawEvent.event_type),
      };
      const eventType = safeStr(event.event_type);

      const color = eventType === 'completed_challenge'
        ? tokens.colors.aurora.purple
        : eventType === 'unlocked_achievement'
          ? tokens.colors.aurora.red
          : tokens.colors.aurora.blue;

      const data: FeedEmbedData = {
        kind: 'feed',
        playerName: getFeedPlayerName(event),
        eventType,
        targetId: safeStr(event.target_id),
        color,
        originalEvent: event,
      };

      return {
        id: `watch-feed-${event.id}`,
        shape: {
          type: 'rect',
          width: FEED_EMBED_W,
          height: FEED_EMBED_H,
        },
        position: {
          type: 'flow',
          paragraph: Math.floor(index / 2),
          progress: (index % 2) * 0.5,
          side: 'right',
        },
        margin: 12,
        data,
      };
    });
  }, [feed, t]);

  const sessionEmbeds = useMemo(() => {
    const safeName = selectedPlayerName || t('watch.session.no_trace');
    const safeCode = safeStr(selectedPlayerCode);
    const blocks: Embed[] = [
      {
        id: 'watch-session-back',
        shape: {
          type: 'rect',
          width: SESSION_EMBED_W,
          height: BACK_EMBED_H,
        },
        position: {
          type: 'flow',
          paragraph: 0,
          progress: 0,
          side: 'left',
        },
        margin: 12,
        data: {
          kind: 'session-back',
          label: `${t('watch.session.back')} // ${safeName} // ${safeCode ? `[ ${safeCode} ]` : '---'}`,
          color: tokens.colors.text.secondary,
        },
      } as Embed,
    ];

    if (sessionSteps.length === 0) {
      const message = sessionMessage ?? (sessionStatus === 'loading' ? t('watch.session.loading') : t('watch.session.no_trace'));
      blocks.push({
        id: 'watch-session-message',
        shape: {
          type: 'rect',
          width: SESSION_EMBED_W,
          height: SESSION_EMBED_H,
        },
        position: {
          type: 'flow',
          paragraph: 1,
          progress: 0,
          side: 'right',
        },
        margin: 12,
        data: {
          kind: 'session-message',
          text: safeStr(message),
          color: sessionStatus === 'error' ? tokens.colors.aurora.red : tokens.colors.aurora.cyan,
        },
      } as Embed);
      return blocks;
    }

    for (let index = 0; index < sessionSteps.length; index += 1) {
      const statusColor = sessionStatus === 'thinking'
        ? tokens.colors.aurora.cyan
        : sessionStatus === 'error'
          ? tokens.colors.aurora.red
          : tokens.colors.aurora.blue;

      blocks.push({
        id: `watch-step-${index}`,
        shape: {
          type: 'rect',
          width: SESSION_EMBED_W,
          height: SESSION_EMBED_H,
        },
        position: {
          type: 'flow',
          paragraph: Math.floor(index / 2),
          progress: (index % 2) * 0.5,
          side: index % 2 === 0 ? 'left' : 'right',
        },
        margin: 12,
        data: {
          kind: 'session-step',
          stepText: `0x${index.toString(16).padStart(2, '0')} // ${safeStr(sessionSteps[index])}`,
          index,
          color: statusColor,
        },
      } as Embed);
    }

    return blocks;
  }, [selectedPlayerCode, selectedPlayerName, sessionMessage, sessionStatus, sessionSteps, t]);

  const embeds = useMemo(() => {
    return viewMode === 'feed' ? feedEmbeds : sessionEmbeds;
  }, [feedEmbeds, sessionEmbeds, viewMode]);

  const pulseWave = useCallback(() => {
    if (pulseRef.current) {
      clearTimeout(pulseRef.current);
    }

    setWaveAmplitude(2);
    pulseRef.current = setTimeout(() => {
      setWaveAmplitude(1);
      pulseRef.current = null;
    }, FLOW_PULSE_MS);
  }, []);

  const pollFeed = useCallback(async () => {
    const data = await request<{ feed: RawFeedEvent[] }>(() => api.feed(1));
    if (!data?.feed) {
      setLoading(false);
      return;
    }

    const nextFeed = data.feed.slice(0, FEED_VISIBLE_COUNT);
    const hasIncoming = nextFeed.some(item => !seenFeedIdsRef.current.has(item.id));
    if (hasIncoming && viewModeRef.current === 'feed') {
      pulseWave();
    }

    nextFeed.forEach(item => {
      seenFeedIdsRef.current.add(item.id);
    });
    setFeed(nextFeed);
    setLoading(false);
  }, [pulseWave]);

  const returnToFeed = useCallback(() => {
    setSessionSteps([]);
    setSessionMessage(null);
    setSessionStatus('idle');
    setSelectedPlayerCode(null);
    setSelectedPlayerName(null);
    setViewMode('feed');
  }, []);

  const enterSession = useCallback(async (event: RawFeedEvent) => {
    const playerCode = getFeedPlayerCode(event);
    const playerName = getFeedPlayerName(event);

    setSelectedPlayerCode(playerCode);
    setSelectedPlayerName(playerName);
    setSessionSteps([]);
    setSessionMessage(null);
    setSessionStatus('loading');
    setViewMode('session');

    if (!playerCode) {
      const message = t('watch.session.error_generic');
      setSessionMessage(message);
      setSessionStatus('error');
      showToast(message, 'error');
      return;
    }

    const { data, error } = await requestTyped<WatchSessionResponse>(() => api.watch(playerCode));
    if (error) {
      const message = error.kind === 'client' && error.status === 404
        ? t('watch.session.error_404')
        : t('watch.session.error_generic');
      setSessionMessage(message);
      setSessionStatus('error');
      setSessionSteps([]);
      showToast(message, 'error');
      return;
    }

    const nextStatus: SessionStatus = data?.status === 'thinking'
      ? 'thinking'
      : data?.status === 'solved'
        ? 'solved'
        : data?.status === 'error'
          ? 'error'
          : 'idle';

    setSessionSteps(normalizeSessionSteps(data?.steps));
    setSessionStatus(nextStatus);
    setSessionMessage(null);
  }, [showToast, t]);

  useEffect(() => {
    void pollFeed();
    pollRef.current = window.setInterval(() => {
      void pollFeed();
    }, FLOW_POLL_INTERVAL_MS);

    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
      if (pulseRef.current) clearTimeout(pulseRef.current);
      seenFeedIdsRef.current.clear();
    };
  }, [pollFeed]);

  useEffect(() => {
    const onBack = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() === 'b' && viewModeRef.current === 'session') {
        returnToFeed();
      }
    };

    window.addEventListener('keydown', onBack);
    return () => window.removeEventListener('keydown', onBack);
  }, [returnToFeed]);

  const effects = useMemo(() => [
    ambientDrift({ amplitude: 0.3 }),
    cursorRipple({ strength: 0.8 }),
    wave({ amplitude: waveAmplitude, frequency: 0.012 }),
  ], [waveAmplitude]);

  const controllerConfig = useMemo(() => {
    return {
      text: flowText,
      font: FLOW_FONT,
      width: Math.max(320, Math.max(0, viewport.width - CANVAS_PADDING * 2)),
      lineHeight: LINE_HEIGHT,
      embeds,
      characterPositions: true,
      effects,
    };
  }, [embeds, effects, flowText, viewport.width]);

  useEffect(() => {
    if (!viewport.width || !viewport.height) return;

    if (!controllerRef.current) {
      controllerRef.current = createAnimationController(controllerConfig);
      return;
    }

    controllerRef.current.updateConfig(controllerConfig);
  }, [controllerConfig, viewport.height, viewport.width]);

  useEffect(() => {
    if (!surfaceRef.current) return;
    const updateViewport = () => {
      const rect = surfaceRef.current?.getBoundingClientRect();
      if (!rect) return;
      setViewport({
        width: Math.max(320, rect.width),
        height: Math.max(rect.height, window.innerHeight),
      });
    };

    const observer = new ResizeObserver(updateViewport);
    observer.observe(surfaceRef.current);
    window.addEventListener('resize', updateViewport);
    updateViewport();
    return () => {
      observer.disconnect();
      window.removeEventListener('resize', updateViewport);
    };
  }, []);

  const resolveEmbedData = useCallback((id: string): WatchEmbedData | null => {
    if (!resultRef.current) return null;
    const node = resultRef.current.embeds.find(item => item.id === id);
    if (!node?.embed.data) return null;
    return node.embed.data as WatchEmbedData;
  }, []);

  const renderFlowLine = (
    ctx: CanvasRenderingContext2D,
    line: FlowLine,
    lineIndex: number,
    totalLines: number,
    transforms: CharacterTransform[] = [],
  ) => {
    const lineColor = buildLineColor(lineIndex, totalLines);
    const baseX = line.x + 8;
    const baseY = line.y + 4;

    ctx.fillStyle = lineColor;
    ctx.font = `400 ${BASE_FONT_SIZE}px ${tokens.fonts.mono}`;

    if (!line.characters || line.characters.length === 0 || !transforms.length) {
      ctx.fillText(line.text, baseX, baseY);
      return;
    }

    for (let index = 0; index < line.characters.length; index += 1) {
      const char = line.characters[index];
      const transform = transforms[index] || {};
      const opacity = Math.max(0.12, Math.min(1, transform.opacity ?? 1));
      const dx = transform.dx ?? 0;
      const dy = transform.dy ?? 0;
      const scale = transform.scale ?? 1;
      const rotation = transform.rotation ?? 0;

      ctx.save();
      ctx.translate(baseX + char.x + dx, baseY + dy);
      if (rotation !== 0) ctx.rotate(rotation);
      if (scale !== 1) ctx.scale(scale, scale);
      ctx.globalAlpha = opacity;
      ctx.fillText(char.char, 0, 0);
      ctx.restore();
    }
  };

  const renderEmbedBlock = (
    ctx: CanvasRenderingContext2D,
    embed: ResolvedEmbed,
    radius = 2,
  ) => {
    const data = embed.embed.data as WatchEmbedData;
    if (!data) return;

    const width = Math.max(0, embed.rect.width);
    const height = Math.max(0, embed.rect.height);
    if (width === 0 || height === 0) return;

    const isHovered = hoveredEmbedId === embed.id;
    const rectFill = isHovered ? tokens.colors.glass.highlight : tokens.colors.glass.bg;

    let text = '';
    if (data.kind === 'feed') {
      text = `${data.playerName} // ${eventTypeLabel(data.eventType, t)} // ${t('watch.v3.ref')}_${safeStr(data.targetId) || '?'}`;
    } else if (data.kind === 'session-step') {
      text = data.stepText;
    } else if (data.kind === 'session-message') {
      text = data.text;
    } else if (data.kind === 'session-back') {
      text = data.label;
    }

    ctx.save();
    ctx.fillStyle = rectFill;
    ctx.strokeStyle = data.color;
    ctx.lineWidth = isHovered ? 1.5 : 1;

    ctx.beginPath();
    ctx.moveTo(embed.rect.x + radius, embed.rect.y);
    ctx.lineTo(embed.rect.x + width - radius, embed.rect.y);
    ctx.quadraticCurveTo(embed.rect.x + width, embed.rect.y, embed.rect.x + width, embed.rect.y + radius);
    ctx.lineTo(embed.rect.x + width, embed.rect.y + height - radius);
    ctx.quadraticCurveTo(embed.rect.x + width, embed.rect.y + height, embed.rect.x + width - radius, embed.rect.y + height);
    ctx.lineTo(embed.rect.x + radius, embed.rect.y + height);
    ctx.quadraticCurveTo(embed.rect.x, embed.rect.y + height, embed.rect.x, embed.rect.y + height - radius);
    ctx.lineTo(embed.rect.x, embed.rect.y + radius);
    ctx.quadraticCurveTo(embed.rect.x, embed.rect.y, embed.rect.x + radius, embed.rect.y);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    const lines = wrapText(ctx, safeStr(text), Math.max(4, width - 16));
    ctx.fillStyle = data.kind === 'session-back' ? tokens.colors.text.secondary : data.color;
    ctx.font = `${BASE_FONT_SIZE - 1}px ${tokens.fonts.mono}`;
    ctx.globalAlpha = 1;

    lines.forEach((lineText, lineIndex) => {
      const top = embed.rect.y + 6 + lineIndex * (LINE_HEIGHT / 2.3);
      if (top + BASE_FONT_SIZE > embed.rect.y + height) return;
      ctx.fillText(lineText, embed.rect.x + 8, top);
    });

    ctx.restore();
  };

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext('2d');
    if (!canvas || !ctx || !controllerRef.current || !viewport.width || !viewport.height) return;

    const dpr = window.devicePixelRatio || 1;
    let cancelled = false;

    const draw = (result: FlowResult) => {
      canvas.width = Math.floor(viewport.width * dpr);
      canvas.height = Math.floor(viewport.height * dpr);
      canvas.style.width = `${viewport.width}px`;
      canvas.style.height = `${viewport.height}px`;

      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, viewport.width, viewport.height);
      ctx.fillStyle = tokens.colors.base;
      ctx.fillRect(0, 0, viewport.width, viewport.height);
      ctx.textBaseline = 'top';

      for (let lineIndex = 0; lineIndex < result.lines.length; lineIndex += 1) {
        const line = result.lines[lineIndex];
        const transforms = result.characterTransforms?.[lineIndex] || [];
        renderFlowLine(ctx, line, lineIndex, result.lines.length, transforms);
      }

      for (const embed of result.embeds) {
        renderEmbedBlock(ctx, embed);
      }
    };

    const tick = (time: number) => {
      if (cancelled) return;
      const result = controllerRef.current?.tick(time);
      if (result) {
        resultRef.current = result;
        draw(result);
      }
      requestAnimationFrame(tick);
    };

    const onPointerMove = (event: PointerEvent) => {
      if (!resultRef.current) return;
      const point = { x: event.offsetX, y: event.offsetY };
      const embedId = hitTest(resultRef.current, point);
      setHoveredEmbedId(embedId);
      controllerRef.current?.setCursor(embedId ? point : null);
    };

    const onClick = (event: MouseEvent) => {
      if (!resultRef.current) return;
      const point = { x: event.offsetX, y: event.offsetY };
      const embedId = hitTest(resultRef.current, point);
      if (!embedId) return;

      const data = resolveEmbedData(embedId);
      if (viewModeRef.current === 'feed' && data?.kind === 'feed') {
        void enterSession(data.originalEvent);
      } else if (embedId === 'watch-session-back') {
        returnToFeed();
      }
    };

    const onPointerLeave = () => {
      setHoveredEmbedId(null);
      controllerRef.current?.setCursor(null);
    };

    const canvasEl = canvas;
    canvasEl.addEventListener('pointermove', onPointerMove);
    canvasEl.addEventListener('click', onClick);
    canvasEl.addEventListener('pointerleave', onPointerLeave);

    const raf = requestAnimationFrame(tick);

    return () => {
      cancelled = true;
      cancelAnimationFrame(raf);
      canvasEl.removeEventListener('pointermove', onPointerMove);
      canvasEl.removeEventListener('click', onClick);
      canvasEl.removeEventListener('pointerleave', onPointerLeave);
      setHoveredEmbedId(null);
      controllerRef.current?.setCursor(null);
    };
  }, [enterSession, returnToFeed, resolveEmbedData, viewport.height, viewport.width]);

  if (loading && feed.length === 0) {
    return <div ref={surfaceRef} style={surfaceStyle} />;
  }

  return (
    <div ref={surfaceRef} style={surfaceStyle}>
      <canvas
        ref={canvasRef}
        style={{
          width: '100%',
          height: '100%',
          display: 'block',
          cursor: hoveredEmbedId ? 'pointer' : 'default',
        }}
      />
      <style>{`
        .watch-flow-canvas {
          touch-action: none;
        }
      `}</style>
    </div>
  );
};

const surfaceStyle: React.CSSProperties = {
  position: 'relative',
  width: '100%',
  minHeight: '100vh',
  height: '100vh',
  overflow: 'hidden',
  background: tokens.colors.base,
  color: tokens.colors.text.primary,
};
