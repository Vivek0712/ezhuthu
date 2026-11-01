import type { APIGatewayProxyStructuredResultV2 } from 'aws-lambda';

export class HttpError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
  ) {
    super(message);
  }
}

export function json(status: number, body: unknown, extra: Record<string, string> = {}): APIGatewayProxyStructuredResultV2 {
  return {
    statusCode: status,
    headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store', ...extra },
    body: JSON.stringify(body),
  };
}

export function errorBody(code: string, message: string) {
  return { error: { code, message } };
}

export interface Caller {
  sub: string;
  name: string;
  groups: string[];
}

/** Read the caller from the HTTP API JWT authorizer claims (absent on public routes). */
export function callerFromClaims(claims: Record<string, string | number | boolean | string[]> | undefined): Caller | null {
  if (!claims || !claims.sub) return null;
  const raw = claims['cognito:groups'];
  const groups = Array.isArray(raw)
    ? raw.map(String)
    : typeof raw === 'string'
      ? raw.replace(/^\[|\]$/g, '').split(/[\s,]+/).filter(Boolean)
      : [];
  return { sub: String(claims.sub), name: String(claims.username ?? claims['cognito:username'] ?? claims.email ?? claims.sub), groups };
}
