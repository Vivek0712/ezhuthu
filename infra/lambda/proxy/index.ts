import { BedrockAgentCoreClient, InvokeAgentRuntimeCommand } from '@aws-sdk/client-bedrock-agentcore';
import { DynamoDBClient } from '@aws-sdk/client-dynamodb';
import { DynamoDBDocumentClient, GetCommand, PutCommand, QueryCommand, UpdateCommand } from '@aws-sdk/lib-dynamodb';
import type { APIGatewayProxyEventV2WithJWTAuthorizer, APIGatewayProxyStructuredResultV2 } from 'aws-lambda';
import { buildPayload, newSessionId, parseAgentResponse, parseBody, runtimeSessionId, type AgentInvoker } from './agent';
import { callerFromClaims, errorBody, HttpError, json } from './http';
import { QueueStore, type DocClient } from './queue';
import { matchRoute } from './routes';

const MAX_BODY_BYTES = 2 * 1024 * 1024;

export interface Deps {
  agent: AgentInvoker;
  store: QueueStore;
  log?: (msg: string, extra?: Record<string, unknown>) => void;
}

/** Pure request handler; `handler` below wires it to AWS clients. */
export async function handle(event: APIGatewayProxyEventV2WithJWTAuthorizer, deps: Deps): Promise<APIGatewayProxyStructuredResultV2> {
  const requestId = event.requestContext?.requestId ?? 'local';
  try {
    const method = event.requestContext.http.method;
    const match = matchRoute(method, event.rawPath);
    if (!match) return json(404, errorBody('not_found', `no route for ${method} ${event.rawPath}`));
    const { route, params } = match;

    const claims = (event.requestContext as { authorizer?: { jwt?: { claims?: Record<string, string> } } }).authorizer?.jwt?.claims;
    const caller = callerFromClaims(claims);
    // API Gateway's JWT authorizer guards these routes; the checks here are defence in depth.
    if (route.access !== 'public' && !caller) throw new HttpError(401, 'unauthorized', 'sign in required');
    if (route.access === 'expert' && !caller!.groups.includes('experts')) throw new HttpError(403, 'forbidden', 'experts group required');

    if (event.body && Buffer.byteLength(event.body) > MAX_BODY_BYTES) throw new HttpError(413, 'too_large', 'request body is larger than 2 MB');
    const headers = Object.fromEntries(Object.entries(event.headers ?? {}).map(([k, v]) => [k.toLowerCase(), v ?? '']));
    const body = method === 'GET' ? {} : parseBody(event.body, event.isBase64Encoded, headers['content-type'] ?? 'application/json');

    switch (route.handler) {
      case 'correction':
        return json(201, await deps.store.addCorrection(body, caller?.name));
      case 'queue-list':
        return json(200, { items: await deps.store.listPending() });
      case 'queue-action':
        return json(200, await deps.store.review(params.id!, body, caller!.name));
      case 'agent': {
        let sessionId: string | undefined;
        if (route.startsSession) {
          sessionId = newSessionId();
          await deps.store.touchSession(sessionId, (body as { level?: unknown }).level).catch((e: unknown) =>
            deps.log?.('session write failed', { error: String(e) }),
          );
        } else if (route.sessionFrom === 'path') sessionId = params.session_id;
        else if (route.sessionFrom === 'body') {
          const sid = (body as { session_id?: unknown }).session_id;
          if (typeof sid !== 'string' || !sid || sid.length > 128) throw new HttpError(400, 'bad_request', 'session_id is required');
          sessionId = sid;
        }
        const payload = buildPayload({ route: route.path, method, params, body, sessionId, caller, requestId });
        const t0 = Date.now();
        const text = await deps.agent.invoke(runtimeSessionId(sessionId), payload);
        const env = parseAgentResponse(text);
        deps.log?.('agent', { route: route.path, status: env.status, ms: Date.now() - t0 });
        return json(env.status, env.body);
      }
    }
  } catch (e) {
    if (e instanceof HttpError) return json(e.status, errorBody(e.code, e.message));
    const name = (e as { name?: string }).name ?? 'Error';
    deps.log?.('unhandled', { name, message: String((e as Error)?.message ?? e), requestId });
    if (name === 'ThrottlingException') return json(429, errorBody('throttled', 'the agent is busy, try again shortly'), { 'retry-after': '5' });
    if (name === 'TimeoutError' || name === 'AbortError') return json(504, errorBody('agent_timeout', 'the agent took too long'));
    return json(502, errorBody('upstream_error', 'the agent could not complete the request'));
  }
}

/* ---------------- AWS wiring ---------------- */
let deps: Deps | null = null;
function awsDeps(): Deps {
  const arn = process.env.AGENT_RUNTIME_ARN;
  const table = process.env.TABLE_NAME;
  if (!arn || !table) throw new Error('AGENT_RUNTIME_ARN and TABLE_NAME must be set');
  const agentClient = new BedrockAgentCoreClient({ requestHandler: { requestTimeout: 27_000 } });
  const doc = DynamoDBDocumentClient.from(new DynamoDBClient({}), { marshallOptions: { removeUndefinedValues: true } });
  const db: DocClient = {
    get: (i) => doc.send(new GetCommand(i)),
    put: (i) => doc.send(new PutCommand(i)),
    query: (i) => doc.send(new QueryCommand(i)),
    update: (i) => doc.send(new UpdateCommand(i)),
  };
  return {
    agent: {
      async invoke(sessionId, payload) {
        const res = await agentClient.send(
          new InvokeAgentRuntimeCommand({
            agentRuntimeArn: arn,
            qualifier: process.env.AGENT_QUALIFIER ?? 'DEFAULT',
            runtimeSessionId: sessionId,
            contentType: 'application/json',
            accept: 'application/json',
            payload: new TextEncoder().encode(JSON.stringify(payload)),
          }),
        );
        if (!res.response) throw new Error('empty agent response');
        return res.response.transformToString();
      },
    },
    store: new QueueStore(db, table),
    log: (msg, extra) => console.log(JSON.stringify({ msg, ...extra })),
  };
}

export const handler = async (event: APIGatewayProxyEventV2WithJWTAuthorizer) => handle(event, (deps ??= awsDeps()));
