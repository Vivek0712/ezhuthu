/** OAuth 2.0 authorization-code + PKCE helpers for the Cognito managed login (no SDK needed). */
export function base64url(bytes: Uint8Array): string {
  let s = '';
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

export function randomString(byteLength = 32): string {
  const bytes = new Uint8Array(byteLength);
  crypto.getRandomValues(bytes);
  return base64url(bytes);
}

export async function codeChallenge(verifier: string): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier));
  return base64url(new Uint8Array(digest));
}

export interface AuthorizeParams {
  domain: string;
  clientId: string;
  redirectUri: string;
  challenge: string;
  state: string;
  scopes?: string[];
}

export function authorizeUrl(p: AuthorizeParams): string {
  const u = new URL('/oauth2/authorize', normalizeDomain(p.domain));
  u.searchParams.set('response_type', 'code');
  u.searchParams.set('client_id', p.clientId);
  u.searchParams.set('redirect_uri', p.redirectUri);
  u.searchParams.set('scope', (p.scopes ?? ['openid', 'email', 'profile']).join(' '));
  u.searchParams.set('state', p.state);
  u.searchParams.set('code_challenge', p.challenge);
  u.searchParams.set('code_challenge_method', 'S256');
  return u.toString();
}

export function normalizeDomain(domain: string): string {
  return domain.startsWith('http') ? domain.replace(/\/$/, '') : `https://${domain.replace(/\/$/, '')}`;
}

/** Decode (not verify) a JWT payload for display; the API Gateway JWT authorizer does the verification. */
export function decodeJwt(token: string): Record<string, unknown> {
  const part = token.split('.')[1];
  if (!part) throw new Error('not a JWT');
  const b64 = part.replace(/-/g, '+').replace(/_/g, '/').padEnd(Math.ceil(part.length / 4) * 4, '=');
  const json = new TextDecoder().decode(Uint8Array.from(atob(b64), (c) => c.charCodeAt(0)));
  return JSON.parse(json) as Record<string, unknown>;
}

export function groupsFromClaims(claims: Record<string, unknown>): string[] {
  const g = claims['cognito:groups'];
  if (Array.isArray(g)) return g.map(String);
  if (typeof g === 'string') return g.replace(/^\[|\]$/g, '').split(/[\s,]+/).filter(Boolean);
  return [];
}
