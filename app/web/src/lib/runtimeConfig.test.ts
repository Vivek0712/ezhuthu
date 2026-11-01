import { describe, expect, it } from 'vitest';
import { applyConfig, getConfig, loadRuntimeConfig } from './runtimeConfig';

describe('runtime config', () => {
  it('applies valid fields from /config.json and ignores junk', async () => {
    const fake = (async () => new Response(JSON.stringify({ cognitoDomain: 'https://ez.auth.us-east-1.amazoncognito.com', cognitoClientId: 'abc', x: 1 }))) as typeof fetch;
    const c = await loadRuntimeConfig(fake);
    expect(c).toEqual({ cognitoDomain: 'https://ez.auth.us-east-1.amazoncognito.com', cognitoClientId: 'abc' });
    applyConfig({ cognitoDomain: 42 });
    expect(getConfig().cognitoDomain).toBe('https://ez.auth.us-east-1.amazoncognito.com');
  });
  it('keeps current values when config.json is missing', async () => {
    const before = getConfig();
    const missing = (async () => new Response('nope', { status: 404 })) as typeof fetch;
    expect(await loadRuntimeConfig(missing)).toEqual(before);
    const broken = (async () => {
      throw new Error('offline');
    }) as typeof fetch;
    expect(await loadRuntimeConfig(broken)).toEqual(before);
  });
});
