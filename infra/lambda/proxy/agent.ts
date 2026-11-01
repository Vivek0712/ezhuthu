import { createHash, randomUUID } from 'node:crypto';
import { HttpError, type Caller } from './http';

/** What the proxy sends to the AgentCore Runtime entrypoint (src/ezhuthu/agentcore_app.py). */
export interface AgentPayload {
  version: 1;
  route: string;
  method: string;
  path_params: Record<string, string>;
  /** Parsed JSON body; for a JSONL upload, `{ "jsonl": "<raw text>" }`. */
  body: unknown;
  /** Present on tutor routes: the learner session this request belongs to. */
  session_id?: string;
  user: { sub: string; name: string; groups: string[] } | null;
  request_id: string;
}

/** What the entrypoint returns. A bare contract body (no envelope) is accepted as status 200. */
export interface AgentEnvelope {
  status: number;
  body: unknown;
}

/** AgentCore runtimeSessionId must be at least 33 characters; derive it deterministically from the session. */
export function runtimeSessionId(sessionId: string | undefined): string {
  if (!sessionId) return `ezhuthu-req-${randomUUID()}`;
  return `ezhuthu-sess-${createHash('sha256').update(sessionId).digest('hex')}`;
}

export function newSessionId(): string {
  return `s-${randomUUID()}`;
}

export function parseBody(raw: string | undefined, isBase64: boolean, contentType: string): unknown {
  const text = raw ? (isBase64 ? Buffer.from(raw, 'base64').toString('utf8') : raw) : '';
  if (contentType.includes('ndjson') || contentType.includes('jsonl')) return { jsonl: text };
  if (!text) return {};
  try {
    return JSON.parse(text);
  } catch {
    throw new HttpError(400, 'bad_json', 'request body is not valid JSON');
  }
}

export function buildPayload(args: {
  route: string;
  method: string;
  params: Record<string, string>;
  body: unknown;
  sessionId?: string;
  caller: Caller | null;
  requestId: string;
}): AgentPayload {
  return {
    version: 1,
    route: args.route,
    method: args.method,
    path_params: args.params,
    body: args.body,
    ...(args.sessionId ? { session_id: args.sessionId } : {}),
    user: args.caller ? { sub: args.caller.sub, name: args.caller.name, groups: args.caller.groups } : null,
    request_id: args.requestId,
  };
}

export function parseAgentResponse(text: string): AgentEnvelope {
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    throw new HttpError(502, 'agent_bad_response', 'agent returned non-JSON');
  }
  if (parsed && typeof parsed === 'object' && 'status' in parsed && 'body' in parsed) {
    const env = parsed as { status: unknown; body: unknown };
    const status = Number(env.status);
    if (!Number.isInteger(status) || status < 200 || status > 599) throw new HttpError(502, 'agent_bad_status', 'agent returned an invalid status');
    return { status, body: env.body };
  }
  return { status: 200, body: parsed };
}

export interface AgentInvoker {
  invoke(runtimeSessionId: string, payload: AgentPayload): Promise<string>;
}
