export function pct(x: number | null | undefined, digits = 0): string {
  if (x === null || x === undefined || Number.isNaN(x)) return '—';
  return `${(x * 100).toFixed(digits)}%`;
}

export function signedPct(x: number | null | undefined): string {
  if (x === null || x === undefined || Number.isNaN(x)) return '—';
  const v = Math.round(x * 100);
  return `${v > 0 ? '+' : ''}${v} pts`;
}

/** Only allow http(s) links from API data (parallels, source URLs) into href attributes. */
export function safeHref(url: string | null | undefined): string | undefined {
  if (!url) return undefined;
  try {
    const u = new URL(url);
    return u.protocol === 'https:' || u.protocol === 'http:' ? u.toString() : undefined;
  } catch {
    return undefined;
  }
}

/**
 * True only for a DHARMA edition link: the dharmalekha.info reader, or the project's TEI repositories under
 * github.com/erc-dharma (or their raw files). Only those may be labelled "DHARMA edition" and, when the API sends no
 * licence, credited as CC BY-SA 4.0 (the DHARMA licence); any other URL is just a source.
 */
export function isDharmaUrl(url: string | null | undefined): boolean {
  const href = safeHref(url);
  if (!href) return false;
  const u = new URL(href);
  const host = u.hostname.toLowerCase();
  if (host === 'dharmalekha.info' || host.endsWith('.dharmalekha.info')) return true;
  if (host === 'github.com' || host === 'www.github.com' || host === 'raw.githubusercontent.com')
    return u.pathname.toLowerCase().startsWith('/erc-dharma/');
  return false;
}

/** Render server-provided SVG through an <img> data URL so any script inside it can never run. */
export function svgDataUrl(svg: string): string {
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

/** The message key for a count: `one` for exactly 1, otherwise `many` (English and Tamil both mark only the singular). */
export function plural<K extends string>(n: number, one: K, many: K): K {
  return n === 1 ? one : many;
}
