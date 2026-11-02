import type { APIGatewayProxyEventV2WithJWTAuthorizer } from 'aws-lambda';
import { beforeEach, describe, expect, it } from 'vitest';
import { parseAgentResponse, runtimeSessionId, type AgentPayload } from '../lambda/proxy/agent';
import { handle, type Deps } from '../lambda/proxy/index';
import { QueueStore, type DocClient } from '../lambda/proxy/queue';
import { matchRoute, READ_MAX_BODY_BYTES, ROUTES } from '../lambda/proxy/routes';
import { readFileSync } from 'node:fs';
import * as path from 'node:path';

/** In-memory DynamoDB document client implementing the subset QueueStore uses, including conditions. */
class FakeDb implements DocClient {
  rows = new Map<string, Record<string, unknown>>();
  key = (k: Record<string, unknown>) => `${k.pk}|${k.sk}`;
  async get(i: { Key: Record<string, unknown> }) {
    return { Item: this.rows.get(this.key(i.Key)) };
  }
  async put(i: { Item: Record<string, unknown>; ConditionExpression?: string }) {
    if (i.ConditionExpression?.includes('attribute_not_exists') && this.rows.has(this.key(i.Item))) throw Object.assign(new Error('x'), { name: 'ConditionalCheckFailedException' });
    this.rows.set(this.key(i.Item), structuredClone(i.Item));
    return {};
  }
  async query(i: { ExpressionAttributeValues: Record<string, unknown>; Limit: number }) {
    const want = i.ExpressionAttributeValues[':p'];
    const items = [...this.rows.values()].filter((r) => r.gsi1pk === want).sort((a, b) => String(a.gsi1sk).localeCompare(String(b.gsi1sk)));
    return { Items: items.slice(0, i.Limit) };
  }
  async update(i: { Key: Record<string, unknown>; ExpressionAttributeValues: Record<string, unknown>; UpdateExpression: string }) {
    const row = this.rows.get(this.key(i.Key));
    if (!row || row.status !== 'pending') throw Object.assign(new Error('x'), { name: 'ConditionalCheckFailedException' });
    const v = i.ExpressionAttributeValues;
    Object.assign(row, { status: v[':s'], gsi1pk: v[':g'], reviewed_by: v[':by'], reviewed_at: v[':at'] });
    if (i.UpdateExpression.includes('final_text')) row.final_text = v[':t'];
    return { Attributes: structuredClone(row) };
  }
}

function event(method: string, rawPath: string, body?: unknown, opts: { claims?: Record<string, string>; contentType?: string } = {}) {
  return {
    rawPath,
    headers: { 'Content-Type': opts.contentType ?? 'application/json' },
    body: body === undefined ? undefined : typeof body === 'string' ? body : JSON.stringify(body),
    isBase64Encoded: false,
    requestContext: { requestId: 'req-1', http: { method }, ...(opts.claims ? { authorizer: { jwt: { claims: opts.claims, scopes: [] } } } : {}) },
  } as unknown as APIGatewayProxyEventV2WithJWTAuthorizer;
}

const expert = { sub: 'u-1', username: 'kamala', 'cognito:groups': '[experts]' };
const learner = { sub: 'u-2', username: 'arun' };

let db: FakeDb;
let calls: { sid: string; payload: AgentPayload }[];
let reply: string;
let deps: Deps;
beforeEach(() => {
  db = new FakeDb();
  calls = [];
  reply = JSON.stringify({ status: 200, body: { ok: true } });
  deps = {
    agent: {
      invoke: async (sid, payload) => {
        calls.push({ sid, payload });
        return reply;
      },
    },
    store: new QueueStore(db, 'T', () => new Date('2026-11-02T00:00:00Z')),
  };
});

describe('route table', () => {
  it('covers every endpoint in contracts/restore-api.md', () => {
    const md = readFileSync(path.join(__dirname, '..', '..', 'contracts', 'restore-api.md'), 'utf8');
    const contract = [...md.matchAll(/\b(GET|POST)\s+`?(\/api\/[A-Za-z0-9_{}/-]+)/g)].map((m) => `${m[1]} ${m[2]}`);
    expect(new Set(contract)).toEqual(new Set(ROUTES.map((r) => `${r.method} ${r.path}`)));
  });
  it('matches path parameters and rejects unknown routes or methods', () => {
    expect(matchRoute('GET', '/api/progress/s-abc')).toMatchObject({ params: { session_id: 's-abc' } });
    expect(matchRoute('POST', '/api/queue/q-1/')).toMatchObject({ params: { id: 'q-1' } });
    expect(matchRoute('GET', '/api/restore')).toBeNull();
    expect(matchRoute('POST', '/api/queue/a/b')).toBeNull();
  });
});

describe('agent routes', () => {
  it('forwards restore with a fresh request session and returns the agent body', async () => {
    reply = JSON.stringify({ status: 200, body: { gaps: [], trace_id: 't' } });
    const res = await handle(event('POST', '/api/restore', { text: 'a[?]b' }), deps);
    expect(res.statusCode).toBe(200);
    expect(JSON.parse(res.body!)).toEqual({ gaps: [], trace_id: 't' });
    expect(calls[0]!.payload).toMatchObject({ version: 1, route: '/api/restore', method: 'POST', body: { text: 'a[?]b' }, user: null });
    expect(calls[0]!.sid).toMatch(/^ezhuthu-req-.{36}$/);
  });
  it('mints a session for /api/lesson, records it, and keeps the AgentCore session sticky for that learner', async () => {
    await handle(event('POST', '/api/lesson', { level: 'L2', lang: 'ta' }), deps);
    const sid = calls[0]!.payload.session_id!;
    expect(sid).toMatch(/^s-/);
    expect(db.rows.get(`SESSION#${sid}|META`)).toMatchObject({ level: 'L2' });
    await handle(event('POST', '/api/answer', { session_id: sid, item_id: 'i', answer: 'க' }), deps);
    await handle(event('GET', `/api/progress/${sid}`), deps);
    expect(new Set(calls.map((c) => c.sid)).size).toBe(1);
    expect(calls[0]!.sid.length).toBeGreaterThanOrEqual(33);
    expect(calls[2]!.payload.path_params).toEqual({ session_id: sid });
  });
  it('requires session_id on answer and assessment', async () => {
    const res = await handle(event('POST', '/api/answer', { item_id: 'i' }), deps);
    expect(res.statusCode).toBe(400);
    expect(calls).toHaveLength(0);
  });
  it('passes agent error statuses through and accepts a bare body', async () => {
    reply = JSON.stringify({ status: 422, body: { error: { code: 'no_gaps', message: 'x' } } });
    expect((await handle(event('POST', '/api/restore', { text: 'x' }), deps)).statusCode).toBe(422);
    reply = JSON.stringify({ restored_text: 'x' });
    expect(JSON.parse((await handle(event('POST', '/api/restore', { text: 'x' }), deps)).body!)).toEqual({ restored_text: 'x' });
  });
  it('maps agent failures to 502/504/429 without leaking internals', async () => {
    deps.agent.invoke = async () => 'not json';
    expect((await handle(event('POST', '/api/restore', { text: 'x' }), deps)).statusCode).toBe(502);
    deps.agent.invoke = async () => {
      throw Object.assign(new Error('secret detail'), { name: 'TimeoutError' });
    };
    const t = await handle(event('POST', '/api/restore', { text: 'x' }), deps);
    expect(t.statusCode).toBe(504);
    expect(t.body).not.toContain('secret');
    deps.agent.invoke = async () => {
      throw Object.assign(new Error('x'), { name: 'ThrottlingException' });
    };
    expect((await handle(event('POST', '/api/restore', { text: 'x' }), deps)).statusCode).toBe(429);
  });
  it('wraps a JSONL upload and forwards the signed-in user on evaluate', async () => {
    const res = await handle(event('POST', '/api/evaluate', '{"id":"a"}\n{"id":"b"}\n', { claims: learner, contentType: 'application/x-ndjson' }), deps);
    expect(res.statusCode).toBe(200);
    expect(calls[0]!.payload.body).toEqual({ jsonl: '{"id":"a"}\n{"id":"b"}\n' });
    expect(calls[0]!.payload.user).toEqual({ sub: 'u-2', name: 'arun', groups: [] });
  });
  it('forwards /api/read photos up to the route cap and refuses larger bodies before invoking the agent', async () => {
    reply = JSON.stringify({ status: 200, body: { lines: [], source: 'image' } });
    const b64 = 'A'.repeat(3_000_000);
    const ok = await handle(event('POST', '/api/read', { image_base64: b64 }), deps);
    expect(ok.statusCode).toBe(200);
    expect(calls[0]!.payload).toMatchObject({ route: '/api/read', body: { image_base64: b64 } });
    expect(calls[0]!.sid).toMatch(/^ezhuthu-req-/);
    const big = await handle(event('POST', '/api/read', { image_base64: 'A'.repeat(READ_MAX_BODY_BYTES) }), deps);
    expect(big.statusCode).toBe(413);
    expect(calls).toHaveLength(1);
    // other routes keep the 2 MB cap
    expect((await handle(event('POST', '/api/restore', { text: 'A'.repeat(2_200_000) }), deps)).statusCode).toBe(413);
  });
  it('passes reader error codes through (413/415/503)', async () => {
    reply = JSON.stringify({ status: 503, body: { error: { code: 'reader_unavailable', message: 'no live model' } } });
    const res = await handle(event('POST', '/api/read', { image_base64: 'QQ==' }), deps);
    expect(res.statusCode).toBe(503);
    expect(JSON.parse(res.body!)).toEqual({ error: { code: 'reader_unavailable', message: 'no live model' } });
  });
  it('rejects evaluate without a token and bad JSON', async () => {
    expect((await handle(event('POST', '/api/evaluate', { benchmark: 'test-hard' }), deps)).statusCode).toBe(401);
    expect((await handle(event('POST', '/api/restore', '{nope'), deps)).statusCode).toBe(400);
  });
});

describe('corrections and review queue (DynamoDB)', () => {
  const correction = { gap_ref: { trace_id: 't-1', gap_index: 0, left: 'kōp', right: 'kēcari', gap_chars: 4 }, accepted_candidate: 'para', user: 'guide' };

  it('queues a public correction, marking a self-declared name unverified', async () => {
    const res = await handle(event('POST', '/api/corrections', correction), deps);
    expect(res.statusCode).toBe(201);
    const item = JSON.parse(res.body!);
    expect(item).toMatchObject({ status: 'pending', user: 'guide (unverified)', accepted_candidate: 'para', created_at: '2026-11-02T00:00:00.000Z' });
    expect(item).not.toHaveProperty('pk');
  });
  it('validates correction bodies', async () => {
    for (const bad of [{}, { ...correction, gap_ref: { trace_id: 't', gap_index: -1 } }, { gap_ref: correction.gap_ref, user: 'x' }, { ...correction, corrected_text: 'x'.repeat(201) }]) {
      expect((await handle(event('POST', '/api/corrections', bad), deps)).statusCode).toBe(400);
    }
  });
  it('lets only experts list and review, and refuses double review', async () => {
    const created = JSON.parse((await handle(event('POST', '/api/corrections', correction), deps)).body!);
    expect((await handle(event('GET', '/api/queue'), deps)).statusCode).toBe(401);
    expect((await handle(event('GET', '/api/queue', undefined, { claims: learner }), deps)).statusCode).toBe(403);
    const list = JSON.parse((await handle(event('GET', '/api/queue', undefined, { claims: expert }), deps)).body!);
    expect(list.items.map((i: { id: string }) => i.id)).toEqual([created.id]);
    const ok = await handle(event('POST', `/api/queue/${created.id}`, { action: 'approve' }, { claims: expert }), deps);
    expect(JSON.parse(ok.body!)).toMatchObject({ status: 'approved', final_text: 'para', reviewed_by: 'kamala' });
    expect((await handle(event('POST', `/api/queue/${created.id}`, { action: 'reject' }, { claims: expert }), deps)).statusCode).toBe(409);
    const after = JSON.parse((await handle(event('GET', '/api/queue', undefined, { claims: expert }), deps)).body!);
    expect(after.items).toEqual([]);
  });
  it('requires text for edit and a proposal for approve', async () => {
    const abst = { gap_ref: { trace_id: 't', gap_index: 1 }, corrected_text: 'x', user: 'u' };
    const created = JSON.parse((await handle(event('POST', '/api/corrections', abst), deps)).body!);
    expect((await handle(event('POST', `/api/queue/${created.id}`, { action: 'edit' }, { claims: expert }), deps)).statusCode).toBe(400);
    const edited = await handle(event('POST', `/api/queue/${created.id}`, { action: 'edit', text: 'paṉṉiraṇṭu' }, { claims: expert }), deps);
    expect(JSON.parse(edited.body!)).toMatchObject({ status: 'edited', final_text: 'paṉṉiraṇṭu' });
    expect((await handle(event('POST', '/api/queue/not-an-id', { action: 'approve' }, { claims: expert }), deps)).statusCode).toBe(404);
  });
});

describe('helpers', () => {
  it('derives a stable runtime session id of valid length', () => {
    expect(runtimeSessionId('s-1')).toBe(runtimeSessionId('s-1'));
    expect(runtimeSessionId('s-1')).not.toBe(runtimeSessionId('s-2'));
    expect(runtimeSessionId('s-1').length).toBeGreaterThanOrEqual(33);
  });
  it('rejects envelopes with invalid status', () => {
    expect(() => parseAgentResponse('{"status": 99, "body": {}}')).toThrow();
  });
});
