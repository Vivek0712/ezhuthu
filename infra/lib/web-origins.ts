/**
 * Public web origins allowed as Cognito callback/logout bases and API CORS origins.
 * Trailing slashes are stripped and duplicates dropped; order is kept (first seen wins).
 */
export function webOrigins(webUrl?: string, webUrls?: readonly string[]): string[] {
  const out: string[] = [];
  for (const u of [...(webUrl ? [webUrl] : []), ...(webUrls ?? [])]) {
    const o = u.trim().replace(/\/+$/, '');
    if (o && !out.includes(o)) out.push(o);
  }
  return out;
}
