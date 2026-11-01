import { afterEach, describe, expect, it, vi } from 'vitest';
import { applyConfig, getConfig, isMockMode, loadRuntimeConfig } from './runtimeConfig';

describe('runtime config', () => {
  afterEach(() => vi.unstubAllEnvs());
  it('runs on mocks only while no /config.json points at a live API', () => {
    vi.stubEnv('VITE_API_MOCK', '1');
    expect(isMockMode()).toBe(true);
    applyConfig({ x: 1 });
    expect(isMockMode()).toBe(true);
    vi.stubEnv('VITE_API_MOCK', '');
    expect(isMockMode()).toBe(false);
  });
  it('applies valid fields from /config.json and ignores junk', async () => {
    const fake = (async () => new Response(JSON.stringify({ cognitoDomain: 'https://ez.auth.us-east-1.amazoncognito.com', cognitoClientId: 'abc', x: 1 }))) as typeof fetch;
    const c = await loadRuntimeConfig(fake);
    expect(c).toEqual({ cognitoDomain: 'https://ez.auth.us-east-1.amazoncognito.com', cognitoClientId: 'abc', liveApi: true });
    vi.stubEnv('VITE_API_MOCK', '1');
    expect(isMockMode()).toBe(false); // a deployed config.json turns the demo banner off
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
