/**
 * Deploy-time settings. In production CloudFront serves /config.json, written by the EzhuthuWeb stack from the
 * Cognito outputs, so the same build works in every environment. Build-time VITE_* values are the fallback.
 */
export interface RuntimeConfig {
  cognitoDomain: string;
  cognitoClientId: string;
  /** True when /config.json describes a live deployment (it names Cognito, or says mock: false). */
  liveApi: boolean;
}

let config: RuntimeConfig = {
  cognitoDomain: (import.meta.env.VITE_COGNITO_DOMAIN as string | undefined) ?? '',
  cognitoClientId: (import.meta.env.VITE_COGNITO_CLIENT_ID as string | undefined) ?? '',
  liveApi: false,
};

export function getConfig(): RuntimeConfig {
  return config;
}

export function applyConfig(raw: unknown): RuntimeConfig {
  if (raw && typeof raw === 'object') {
    const r = raw as Record<string, unknown>;
    config = {
      cognitoDomain: typeof r.cognitoDomain === 'string' && r.cognitoDomain ? r.cognitoDomain : config.cognitoDomain,
      cognitoClientId: typeof r.cognitoClientId === 'string' && r.cognitoClientId ? r.cognitoClientId : config.cognitoClientId,
      liveApi:
        config.liveApi ||
        r.mock === false ||
        (typeof r.cognitoDomain === 'string' && !!r.cognitoDomain) ||
        (typeof r.apiBase === 'string' && !!r.apiBase),
    };
  }
  return config;
}

export async function loadRuntimeConfig(fetcher: typeof fetch = fetch): Promise<RuntimeConfig> {
  try {
    const res = await fetcher('/config.json', { cache: 'no-store' });
    if (res.ok) return applyConfig(await res.json());
  } catch {
    /* no config.json (local dev): keep build-time values */
  }
  return config;
}

/**
 * Mock mode (MSW + demo banner) only when the build asked for mocks AND no /config.json points at a live API.
 * A deployed site always serves config.json with its Cognito values, so it never shows the demo banner.
 */
export function isMockMode(): boolean {
  return import.meta.env.VITE_API_MOCK === '1' && !config.liveApi;
}
