/**
 * Deploy-time settings. In production CloudFront serves /config.json, written by the EzhuthuWeb stack from the
 * Cognito outputs, so the same build works in every environment. Build-time VITE_* values are the fallback.
 */
export interface RuntimeConfig {
  cognitoDomain: string;
  cognitoClientId: string;
}

let config: RuntimeConfig = {
  cognitoDomain: (import.meta.env.VITE_COGNITO_DOMAIN as string | undefined) ?? '',
  cognitoClientId: (import.meta.env.VITE_COGNITO_CLIENT_ID as string | undefined) ?? '',
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
