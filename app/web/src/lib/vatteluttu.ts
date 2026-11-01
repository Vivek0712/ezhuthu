/**
 * Stylised Vatteluttu letterforms. Vatteluttu has no Unicode encoding, so the app draws it.
 * These are simplified drawings for teaching, pending expert review (stated on the About page).
 * Each path is drawn on a 100x100 grid with a round stroke; ISO-15919 value alongside.
 */
export interface VGlyph {
  iso: string;
  tamil: string;
  d: string;
}

export const VATTELUTTU: Record<string, VGlyph> = {
  ka: { iso: 'ka', tamil: 'க', d: 'M50 12 V88 M18 50 C18 30 34 30 50 50 C66 70 82 70 82 50' },
  ta: { iso: 'ta', tamil: 'த', d: 'M22 30 C22 14 52 14 52 34 C52 54 22 56 26 76 C30 92 74 92 78 70' },
  pa: { iso: 'pa', tamil: 'ப', d: 'M24 18 V62 C24 86 76 86 76 62 V18' },
  ma: { iso: 'ma', tamil: 'ம', d: 'M20 70 C20 30 48 30 48 56 C48 30 80 30 80 56 C80 82 52 86 46 72' },
  na: { iso: 'ṉa', tamil: 'ன', d: 'M18 28 C40 12 40 52 30 62 C20 72 40 90 54 74 C68 58 82 74 82 88' },
};

export function vatteluttuSvg(key: keyof typeof VATTELUTTU | string, opts: { stroke?: string; size?: number } = {}): string {
  const g = VATTELUTTU[key];
  if (!g) throw new Error(`no Vatteluttu glyph for ${key}`);
  const size = opts.size ?? 120;
  const stroke = opts.stroke ?? '#2a1e14';
  return (
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="${size}" height="${size}" role="img" aria-label="Vatteluttu ${g.iso}">` +
    `<path d="${g.d}" fill="none" stroke="${stroke}" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/></svg>`
  );
}
