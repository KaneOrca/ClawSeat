// API Base URL: 
// 1. If VITE_API_BASE_URL is set (build-time override), use it.
// 2. Otherwise, default to empty string (runtime same-origin relative paths).
const BASE = import.meta.env.VITE_API_BASE_URL || '';

function headers(code?: string) {
  const h: Record<string, string> = { 'Content-Type': 'application/json' };
  if (code) h['X-Participant-Code'] = code;
  return h;
}

export const api = {
  // 公开 (Public)
  register: (nickname: string) => fetch(`${BASE}/api/register`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({ nickname })
  }),
  challenges: () => fetch(`${BASE}/api/challenges`),
  leaderboard: () => fetch(`${BASE}/api/leaderboard`),
  feed: (page = 1) => fetch(`${BASE}/api/feed?page=${page}`),

  // 需要认证 (Auth Required)
  status: (code: string) => fetch(`${BASE}/api/status`, { headers: headers(code) }),
  profile: (code: string) => fetch(`${BASE}/api/players/${code}`, { headers: headers(code) }),
  updateProfile: (code: string, data: object) => fetch(`${BASE}/api/players/${code}`, {
    method: 'PUT', headers: headers(code), body: JSON.stringify(data)
  }),
  chat: (code: string, content: string) => fetch(`${BASE}/api/chat/messages`, {
    method: 'POST', headers: headers(code), body: JSON.stringify({ content })
  }),
  chatSince: (since?: number) => fetch(`${BASE}/api/chat/messages${since ? `?since=${since}` : ''}`),
  notifications: (code: string) => fetch(`${BASE}/api/notifications`, { headers: headers(code) }),
  markRead: (code: string) => fetch(`${BASE}/api/notifications/read`, {
    method: 'POST', headers: headers(code)
  }),
  submit: (code: string, challengeId: number, answer: string) => fetch(`${BASE}/api/submit`, {
    method: 'POST', headers: headers(code),
    body: JSON.stringify({ challengeId, answer })
  }),
  watch: (playerCode: string) => fetch(`${BASE}/api/submissions/${encodeURIComponent(playerCode)}/session`),
  watchStep: (code: string, challengeId: number, status: string, step: string) =>
    fetch(`${BASE}/api/submissions/${code}/step`, {
      method: 'POST',
      headers: headers(code),
      body: JSON.stringify({ challenge_id: challengeId, status, step })
    }),
};

// Error types for structured error handling
export type ApiErrorKind = 'network' | 'client' | 'server' | 'abort';

export interface ApiError {
  kind: ApiErrorKind;
  status?: number;
  message: string;
}

export interface ApiResult<T> {
  data: T | null;
  error: ApiError | null;
}

/**
 * Enhanced request helper with error classification and AbortController support.
 * Returns { data, error } discriminated union.
 */
export async function requestTyped<T>(fn: () => Promise<Response>, _signal?: AbortSignal): Promise<ApiResult<T>> {
  try {
    const res = await fn();
    if (res.ok) {
      return { data: await res.json() as T, error: null };
    }
    const errorText = await res.text();
    const kind: ApiErrorKind = res.status >= 500 ? 'server' : 'client';
    return { data: null, error: { kind, status: res.status, message: errorText || res.statusText } };
  } catch (err: any) {
    if (err?.name === 'AbortError') {
      return { data: null, error: { kind: 'abort', message: 'Request aborted' } };
    }
    return { data: null, error: { kind: 'network', message: err?.message || 'Network error' } };
  }
}

/**
 * Legacy request helper — returns null on failure (backward compatible).
 */
export async function request<T = any>(fn: () => Promise<Response>, _signal?: AbortSignal): Promise<T | null> {
  const { data, error } = await requestTyped<T>(fn, _signal);
  if (error && error.kind !== 'abort') {
    console.error(`API ${error.kind} error${error.status ? ` (${error.status})` : ''}: ${error.message}`);
  }
  return data;
}
