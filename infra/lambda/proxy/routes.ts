/** Route table for the /api/* proxy. Mirrors contracts/restore-api.md. */
export type Access = 'public' | 'user' | 'expert';
export type Handler = 'agent' | 'correction' | 'queue-list' | 'queue-action';

export interface RouteDef {
  method: 'GET' | 'POST';
  /** API Gateway route path, e.g. /api/queue/{id} */
  path: string;
  handler: Handler;
  access: Access;
  /** Which request field carries the tutor session id (keeps one AgentCore session per learner). */
  sessionFrom?: 'body' | 'path';
  /** POST /api/lesson starts a session: the proxy mints its id. */
  startsSession?: boolean;
  /** Request body cap for this route (default 2 MB). */
  maxBodyBytes?: number;
}

/**
 * POST /api/read carries a photo as base64 JSON (contracts/restore-api.md). Lambda's synchronous invoke payload
 * limit is 6 MB for the whole API Gateway event, so the body is capped at 4.5 MB (a ~3.3 MB image after base64);
 * the app resizes photos to at most 2048 px / ~1.5 MB before upload, so real requests stay far below this.
 */
export const READ_MAX_BODY_BYTES = 4_500_000;

export const ROUTES: readonly RouteDef[] = [
  { method: 'POST', path: '/api/restore', handler: 'agent', access: 'public' },
  { method: 'POST', path: '/api/read', handler: 'agent', access: 'public', maxBodyBytes: READ_MAX_BODY_BYTES },
  { method: 'POST', path: '/api/lesson', handler: 'agent', access: 'public', startsSession: true },
  { method: 'POST', path: '/api/answer', handler: 'agent', access: 'public', sessionFrom: 'body' },
  { method: 'POST', path: '/api/assessment', handler: 'agent', access: 'public', sessionFrom: 'body' },
  { method: 'GET', path: '/api/progress/{session_id}', handler: 'agent', access: 'public', sessionFrom: 'path' },
  { method: 'POST', path: '/api/evaluate', handler: 'agent', access: 'user' },
  { method: 'POST', path: '/api/corrections', handler: 'correction', access: 'public' },
  { method: 'GET', path: '/api/queue', handler: 'queue-list', access: 'expert' },
  { method: 'POST', path: '/api/queue/{id}', handler: 'queue-action', access: 'expert' },
];

export interface Match {
  route: RouteDef;
  params: Record<string, string>;
}

export function matchRoute(method: string, rawPath: string): Match | null {
  const path = rawPath.replace(/\/+$/, '') || '/';
  for (const route of ROUTES) {
    if (route.method !== method.toUpperCase()) continue;
    const names: string[] = [];
    const re = new RegExp(
      '^' +
        route.path.replace(/[.*+?^$()|[\]\\]/g, '\\$&').replace(/\\?\{(\w+)\\?\}/g, (_m, n: string) => {
          names.push(n);
          return '([^/]+)';
        }) +
        '$',
    );
    const m = re.exec(path);
    if (m) {
      const params: Record<string, string> = {};
      names.forEach((n, i) => (params[n] = decodeURIComponent(m[i + 1]!)));
      return { route, params };
    }
  }
  return null;
}
