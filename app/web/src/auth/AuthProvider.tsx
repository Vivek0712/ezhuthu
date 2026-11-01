import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';
import { setTokenGetter } from '../api/client';
import { authorizeUrl, codeChallenge, decodeJwt, groupsFromClaims, normalizeDomain, randomString } from './pkce';

export interface User {
  name: string;
  groups: string[];
}
interface Session {
  user: User;
  accessToken: string;
  expiresAt: number;
}
interface Auth {
  user: User | null;
  isExpert: boolean;
  mock: boolean;
  configured: boolean;
  signIn: (returnTo?: string) => Promise<void>;
  signOut: () => void;
  completeSignIn: (code: string, state: string) => Promise<string>;
}

const KEY = 'ezhuthu.session';
const PKCE_KEY = 'ezhuthu.pkce';
const MOCK = import.meta.env.VITE_API_MOCK === '1';
const DOMAIN = (import.meta.env.VITE_COGNITO_DOMAIN as string | undefined) ?? '';
const CLIENT_ID = (import.meta.env.VITE_COGNITO_CLIENT_ID as string | undefined) ?? '';

function redirectUri(): string {
  return `${window.location.origin}/auth/callback`;
}

function load(): Session | null {
  try {
    const raw = window.sessionStorage.getItem(KEY);
    if (!raw) return null;
    const s = JSON.parse(raw) as Session;
    return s.expiresAt > Date.now() ? s : null;
  } catch {
    return null;
  }
}
function save(s: Session | null) {
  try {
    if (s) window.sessionStorage.setItem(KEY, JSON.stringify(s));
    else window.sessionStorage.removeItem(KEY);
  } catch {
    /* storage blocked: the session lives only in memory */
  }
}

const Ctx = createContext<Auth | null>(null);

let current: Session | null = null;
setTokenGetter(() => (current && current.expiresAt > Date.now() ? current.accessToken : null));

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSessionState] = useState<Session | null>(() => {
    const s = load();
    current = s;
    return s;
  });
  // The token store is updated synchronously so child effects that fire right after sign-in
  // (which run before this provider's effects) already send the new token.
  const setSession = useCallback((s: Session | null) => {
    current = s;
    save(s);
    setSessionState(s);
  }, []);

  const signIn = useCallback(async (returnTo = window.location.pathname) => {
    if (MOCK) {
      // Demo identity for mock mode only; the mock API accepts this token.
      setSession({
        user: { name: 'demo-expert', groups: ['experts'] },
        accessToken: 'mock-access-token',
        expiresAt: Date.now() + 3600_000,
      });
      return;
    }
    if (!DOMAIN || !CLIENT_ID) throw new Error('Cognito is not configured (VITE_COGNITO_DOMAIN / VITE_COGNITO_CLIENT_ID)');
    const verifier = randomString(48);
    const state = randomString(16);
    window.sessionStorage.setItem(PKCE_KEY, JSON.stringify({ verifier, state, returnTo }));
    window.location.assign(
      authorizeUrl({ domain: DOMAIN, clientId: CLIENT_ID, redirectUri: redirectUri(), challenge: await codeChallenge(verifier), state }),
    );
  }, [setSession]);

  const completeSignIn = useCallback(async (code: string, state: string) => {
    const raw = window.sessionStorage.getItem(PKCE_KEY);
    window.sessionStorage.removeItem(PKCE_KEY);
    if (!raw) throw new Error('sign-in was not started from this browser tab');
    const pkce = JSON.parse(raw) as { verifier: string; state: string; returnTo: string };
    if (pkce.state !== state) throw new Error('sign-in state mismatch');
    const res = await fetch(`${normalizeDomain(DOMAIN)}/oauth2/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({
        grant_type: 'authorization_code',
        client_id: CLIENT_ID,
        code,
        redirect_uri: redirectUri(),
        code_verifier: pkce.verifier,
      }),
    });
    if (!res.ok) throw new Error(`token exchange failed (${res.status})`);
    const tok = (await res.json()) as { access_token: string; id_token: string; expires_in: number };
    const id = decodeJwt(tok.id_token);
    setSession({
      user: {
        name: String(id['preferred_username'] ?? id['email'] ?? id['cognito:username'] ?? 'learner'),
        groups: groupsFromClaims(id),
      },
      accessToken: tok.access_token,
      expiresAt: Date.now() + tok.expires_in * 1000,
    });
    return pkce.returnTo || '/';
  }, [setSession]);

  const signOut = useCallback(() => {
    setSession(null);
    if (!MOCK && DOMAIN && CLIENT_ID) {
      const u = new URL('/logout', normalizeDomain(DOMAIN));
      u.searchParams.set('client_id', CLIENT_ID);
      u.searchParams.set('logout_uri', `${window.location.origin}/`);
      window.location.assign(u.toString());
    }
  }, [setSession]);

  const value = useMemo<Auth>(
    () => ({
      user: session?.user ?? null,
      isExpert: !!session?.user.groups.includes('experts'),
      mock: MOCK,
      configured: MOCK || (!!DOMAIN && !!CLIENT_ID),
      signIn,
      signOut,
      completeSignIn,
    }),
    [session, signIn, signOut, completeSignIn],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): Auth {
  const v = useContext(Ctx);
  if (!v) throw new Error('useAuth outside AuthProvider');
  return v;
}
