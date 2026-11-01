import createClient, { type Middleware } from 'openapi-fetch';
import type { components, paths } from './schema';

export type Schemas = components['schemas'];
export type RestoreRequest = Schemas['RestoreRequest'];
export type RestoreResponse = Schemas['RestoreResponse'];
export type Gap = Schemas['Gap'];
export type Candidate = Schemas['Candidate'];
export type LessonResponse = Schemas['LessonResponse'];
export type PracticeItem = Schemas['PracticeItem'];
export type AnswerResponse = Schemas['AnswerResponse'];
export type ProgressResponse = Schemas['ProgressResponse'];
export type EvaluateResponse = Schemas['EvaluateResponse'];
export type EvaluateBuiltinRequest = Schemas['EvaluateBuiltinRequest'];
export type QueueItem = Schemas['QueueItem'];
export type CorrectionRequest = Schemas['CorrectionRequest'];
export type Level = Schemas['Level'];

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

let tokenGetter: () => string | null = () => null;
/** The auth provider registers how to read the current Cognito access token. */
export function setTokenGetter(fn: () => string | null): void {
  tokenGetter = fn;
}

export function apiBase(): string {
  const configured = import.meta.env.VITE_API_BASE as string | undefined;
  if (configured) return configured.replace(/\/$/, '');
  return typeof window !== 'undefined' ? window.location.origin : 'http://localhost';
}

const authMiddleware: Middleware = {
  onRequest({ request }) {
    const token = tokenGetter();
    if (token) request.headers.set('Authorization', `Bearer ${token}`);
    return request;
  },
};

// Resolve fetch per call so test/dev interceptors (MSW) installed after import still apply.
export const client = createClient<paths>({ baseUrl: apiBase(), fetch: (req) => globalThis.fetch(req) });
client.use(authMiddleware);

async function toApiError(response: Response, error: unknown): Promise<ApiError> {
  const e = (error as { error?: { code?: string; message?: string } } | undefined)?.error;
  return new ApiError(response.status, e?.code ?? `http_${response.status}`, e?.message ?? response.statusText ?? 'request failed');
}

async function unwrap<T>(p: Promise<{ data?: T; error?: unknown; response: Response }>): Promise<T> {
  const { data, error, response } = await p;
  if (!response.ok || data === undefined) throw await toApiError(response, error);
  return data;
}

export const api = {
  restore: (body: RestoreRequest) => unwrap(client.POST('/api/restore', { body })),
  lesson: (body: Schemas['LessonRequest']) => unwrap(client.POST('/api/lesson', { body })),
  answer: (body: Schemas['AnswerRequest']) => unwrap(client.POST('/api/answer', { body })),
  assessment: (body: Schemas['AssessmentRequest']) => unwrap(client.POST('/api/assessment', { body })),
  progress: (sessionId: string) =>
    unwrap(client.GET('/api/progress/{session_id}', { params: { path: { session_id: sessionId } } })),
  evaluate: (body: EvaluateBuiltinRequest) => unwrap(client.POST('/api/evaluate', { body })),
  /** JSONL upload goes out as application/x-ndjson, one benchmark-item per line. */
  async evaluateUpload(jsonl: string): Promise<EvaluateResponse> {
    const headers = new Headers({ 'Content-Type': 'application/x-ndjson', Accept: 'application/json' });
    const token = tokenGetter();
    if (token) headers.set('Authorization', `Bearer ${token}`);
    const response = await fetch(`${apiBase()}/api/evaluate`, { method: 'POST', headers, body: jsonl });
    const payload: unknown = await response.json().catch(() => undefined);
    if (!response.ok) throw await toApiError(response, payload);
    return payload as EvaluateResponse;
  },
  correction: (body: CorrectionRequest) => unwrap(client.POST('/api/corrections', { body })),
  queue: () => unwrap(client.GET('/api/queue')),
  review: (id: string, body: Schemas['QueueAction']) =>
    unwrap(client.POST('/api/queue/{id}', { params: { path: { id } }, body })),
};
