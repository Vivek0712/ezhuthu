import { randomUUID } from 'node:crypto';
import { HttpError } from './http';

/** Minimal document-client surface so the logic is testable without AWS. */
export interface DocClient {
  get(input: { TableName: string; Key: Record<string, unknown>; ConsistentRead: boolean }): Promise<{ Item?: Record<string, unknown> }>;
  put(input: { TableName: string; Item: Record<string, unknown>; ConditionExpression?: string }): Promise<unknown>;
  query(input: {
    TableName: string;
    IndexName: string;
    KeyConditionExpression: string;
    ExpressionAttributeValues: Record<string, unknown>;
    Limit: number;
    ScanIndexForward: boolean;
  }): Promise<{ Items?: Record<string, unknown>[] }>;
  update(input: {
    TableName: string;
    Key: Record<string, unknown>;
    UpdateExpression: string;
    ConditionExpression: string;
    ExpressionAttributeNames: Record<string, string>;
    ExpressionAttributeValues: Record<string, unknown>;
    ReturnValues: 'ALL_NEW';
  }): Promise<{ Attributes?: Record<string, unknown> }>;
}

export interface GapRef {
  trace_id: string;
  gap_index: number;
  left?: string;
  right?: string;
  gap_chars?: number | null;
  inscription_id?: string;
}

export interface QueueItem {
  id: string;
  gap_ref: GapRef;
  accepted_candidate?: string;
  corrected_text?: string;
  user: string;
  status: 'pending' | 'approved' | 'edited' | 'rejected';
  created_at: string;
  reviewed_by?: string;
  reviewed_at?: string;
  final_text?: string;
}

const str = (v: unknown, max: number, field: string, required = false): string | undefined => {
  if (v === undefined || v === null || v === '') {
    if (required) throw new HttpError(400, 'bad_request', `${field} is required`);
    return undefined;
  }
  if (typeof v !== 'string') throw new HttpError(400, 'bad_request', `${field} must be a string`);
  const t = v.trim();
  if (t.length > max) throw new HttpError(400, 'bad_request', `${field} is longer than ${max} characters`);
  return t || undefined;
};

export function validateCorrection(body: unknown): Omit<QueueItem, 'id' | 'status' | 'created_at'> {
  if (!body || typeof body !== 'object') throw new HttpError(400, 'bad_request', 'JSON object expected');
  const b = body as Record<string, unknown>;
  const g = b.gap_ref as Record<string, unknown> | undefined;
  if (!g || typeof g !== 'object') throw new HttpError(400, 'bad_request', 'gap_ref is required');
  const gapIndex = g.gap_index;
  if (!Number.isInteger(gapIndex) || (gapIndex as number) < 0 || (gapIndex as number) > 500)
    throw new HttpError(400, 'bad_request', 'gap_ref.gap_index must be a non-negative integer');
  const gapChars = g.gap_chars;
  if (gapChars !== undefined && gapChars !== null && !(Number.isInteger(gapChars) && (gapChars as number) > 0))
    throw new HttpError(400, 'bad_request', 'gap_ref.gap_chars must be a positive integer or null');
  const gap_ref: GapRef = {
    trace_id: str(g.trace_id, 128, 'gap_ref.trace_id', true)!,
    gap_index: gapIndex as number,
  };
  const left = str(g.left, 400, 'gap_ref.left');
  const right = str(g.right, 400, 'gap_ref.right');
  const insc = str(g.inscription_id, 128, 'gap_ref.inscription_id');
  if (left) gap_ref.left = left;
  if (right) gap_ref.right = right;
  if (insc) gap_ref.inscription_id = insc;
  if (gapChars !== undefined) gap_ref.gap_chars = gapChars as number | null;
  const accepted = str(b.accepted_candidate, 200, 'accepted_candidate');
  const corrected = str(b.corrected_text, 200, 'corrected_text');
  if (!accepted && !corrected) throw new HttpError(400, 'bad_request', 'accepted_candidate or corrected_text is required');
  return {
    gap_ref,
    ...(accepted ? { accepted_candidate: accepted } : {}),
    ...(corrected ? { corrected_text: corrected } : {}),
    user: str(b.user, 64, 'user') ?? 'anonymous',
  };
}

function toItem(row: Record<string, unknown>): QueueItem {
  const { pk: _pk, sk: _sk, gsi1pk: _g1, gsi1sk: _g2, ttl: _ttl, ...rest } = row;
  return rest as unknown as QueueItem;
}

export class QueueStore {
  constructor(
    private readonly db: DocClient,
    private readonly table: string,
    private readonly now: () => Date = () => new Date(),
  ) {}

  async addCorrection(body: unknown, signedInUser?: string): Promise<QueueItem> {
    const c = validateCorrection(body);
    const item: QueueItem = {
      id: `q-${randomUUID()}`,
      ...c,
      // A signed-in caller is recorded as themselves; anonymous names are kept but marked unverified.
      user: signedInUser ?? `${c.user} (unverified)`,
      status: 'pending',
      created_at: this.now().toISOString(),
    };
    await this.db.put({
      TableName: this.table,
      Item: { pk: `QUEUE#${item.id}`, sk: 'ITEM', gsi1pk: 'STATUS#pending', gsi1sk: item.created_at, ...item },
      ConditionExpression: 'attribute_not_exists(pk)',
    });
    return item;
  }

  async listPending(limit = 50): Promise<QueueItem[]> {
    const res = await this.db.query({
      TableName: this.table,
      IndexName: 'gsi1',
      KeyConditionExpression: 'gsi1pk = :p',
      ExpressionAttributeValues: { ':p': 'STATUS#pending' },
      Limit: Math.min(Math.max(limit, 1), 100),
      ScanIndexForward: true,
    });
    return (res.Items ?? []).map(toItem);
  }

  async review(id: string, body: unknown, reviewer: string): Promise<QueueItem> {
    if (!/^q-[0-9a-f-]{36}$/.test(id)) throw new HttpError(404, 'not_found', 'unknown queue item');
    const b = (body ?? {}) as Record<string, unknown>;
    const action = b.action;
    if (action !== 'approve' && action !== 'edit' && action !== 'reject')
      throw new HttpError(400, 'bad_request', 'action must be approve, edit or reject');
    const text = str(b.text, 200, 'text', action === 'edit');
    const status = action === 'approve' ? 'approved' : action === 'edit' ? 'edited' : 'rejected';
    const at = this.now().toISOString();
    const names: Record<string, string> = { '#s': 'status' };
    const values: Record<string, unknown> = {
      ':s': status,
      ':g': `STATUS#${status}`,
      ':by': reviewer,
      ':at': at,
      ':pending': 'pending',
    };
    let expr = 'SET #s = :s, gsi1pk = :g, reviewed_by = :by, reviewed_at = :at';
    if (action === 'edit') {
      expr += ', final_text = :t';
      values[':t'] = text;
    } else if (action === 'approve') {
      // Approve keeps the proposer's reading as the final text; an abstention has none, so it needs "edit".
      const cur = await this.db.get({ TableName: this.table, Key: { pk: `QUEUE#${id}`, sk: 'ITEM' }, ConsistentRead: true });
      if (!cur.Item) throw new HttpError(404, 'not_found', 'unknown queue item');
      const proposal = (cur.Item.corrected_text ?? cur.Item.accepted_candidate) as string | undefined;
      if (!proposal) throw new HttpError(400, 'bad_request', 'nothing to approve; use edit with a reading');
      expr += ', final_text = :t';
      values[':t'] = proposal;
    }
    try {
      const res = await this.db.update({
        TableName: this.table,
        Key: { pk: `QUEUE#${id}`, sk: 'ITEM' },
        UpdateExpression: expr,
        ConditionExpression: 'attribute_exists(pk) AND #s = :pending',
        ExpressionAttributeNames: names,
        ExpressionAttributeValues: values,
        ReturnValues: 'ALL_NEW',
      });
      return toItem(res.Attributes ?? {});
    } catch (e) {
      if ((e as { name?: string }).name === 'ConditionalCheckFailedException')
        throw new HttpError(409, 'conflict', 'item does not exist or was already reviewed');
      throw e;
    }
  }

  async touchSession(sessionId: string, level: unknown): Promise<void> {
    const now = this.now();
    await this.db.put({
      TableName: this.table,
      Item: {
        pk: `SESSION#${sessionId}`,
        sk: 'META',
        created_at: now.toISOString(),
        level: typeof level === 'string' ? level : null,
        ttl: Math.floor(now.getTime() / 1000) + 90 * 24 * 3600,
      },
    });
  }
}
