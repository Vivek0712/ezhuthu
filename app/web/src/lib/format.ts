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

/** Render server-provided SVG through an <img> data URL so any script inside it can never run. */
export function svgDataUrl(svg: string): string {
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}
