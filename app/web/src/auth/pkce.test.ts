import { describe, expect, it } from 'vitest';
import { authorizeUrl, base64url, codeChallenge, decodeJwt, groupsFromClaims, randomString } from './pkce';

describe('PKCE', () => {
  it('derives the S256 challenge (oracle: Python hashlib + urlsafe_b64encode)', async () => {
    expect(await codeChallenge('dBjftJeZ4CVP-mJ92K9mstSvZ5EkIr-IfQBsCi-bVWo')).toBe('TE0Z0w1XtCcecaeG-AgkiZuMFgALukRaiEFXJJC-fDk');
  });
  it('produces url-safe random strings without padding', () => {
    const s = randomString(48);
    expect(s).toMatch(/^[A-Za-z0-9_-]{64}$/);
    expect(randomString()).not.toBe(randomString());
    expect(base64url(new Uint8Array([251, 255]))).toBe('-_8');
  });
  it('builds the Cognito authorize URL', () => {
    const u = new URL(authorizeUrl({ domain: 'ezhuthu.auth.us-east-1.amazoncognito.com', clientId: 'abc', redirectUri: 'https://x/auth/callback', challenge: 'ch', state: 'st' }));
    expect(u.origin).toBe('https://ezhuthu.auth.us-east-1.amazoncognito.com');
    expect(u.pathname).toBe('/oauth2/authorize');
    expect(Object.fromEntries(u.searchParams)).toMatchObject({
      response_type: 'code',
      client_id: 'abc',
      code_challenge: 'ch',
      code_challenge_method: 'S256',
      state: 'st',
      scope: 'openid email profile',
    });
  });
  it('decodes JWT claims (including unicode) and reads Cognito groups in both shapes', () => {
    const payload = base64url(new TextEncoder().encode(JSON.stringify({ name: 'கமலா', 'cognito:groups': ['experts'] })));
    const claims = decodeJwt(`h.${payload}.s`);
    expect(claims.name).toBe('கமலா');
    expect(groupsFromClaims(claims)).toEqual(['experts']);
    expect(groupsFromClaims({ 'cognito:groups': '[experts admins]' })).toEqual(['experts', 'admins']);
    expect(groupsFromClaims({})).toEqual([]);
    expect(() => decodeJwt('nope')).toThrow();
  });
});
