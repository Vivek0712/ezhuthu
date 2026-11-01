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
}

export const ROUTES: readonly RouteDef[] = [
  { method: 'POST', path: '/api/restore', handler: 'agent', access: 'public' },
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
