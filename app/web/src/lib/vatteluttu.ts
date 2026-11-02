/**
 * Vatteluttu letterforms. Vatteluttu has no Unicode encoding, so the app draws it. The drawings come from the
 * design system (design/glyphs/vatteluttu.json, keyed by ISO-15919), which supersedes the app's first sketches of
 * ka, ta, pa and ma and adds a, e and ḻa. ṉa is still the app's own sketch until the design team reviews it.
 * All are simplified teaching drawings pending epigrapher review (stated on the About page).
 * Paths are centre lines on a 100x100 grid, stroked with round caps and joins.
 */
import design from '../../../../design/glyphs/vatteluttu.json';

export interface VGlyph {
  iso: string;
  tamil: string;
  d: string;
}

/** Stroke width on the 100-unit grid (design/glyphs/GLYPH-CARD.md). */
export const VATTELUTTU_STROKE: number = design.stroke;

const fromDesign: Record<string, VGlyph> = Object.fromEntries(
  Object.entries(design.glyphs as Record<string, { tamil: string; d: string }>).map(([iso, g]) => [iso, { iso, tamil: g.tamil, d: g.d }]),
);

/** Keyed by ISO-15919. `na` is kept as an ASCII alias of `ṉa` for older call sites. */
export const VATTELUTTU: Record<string, VGlyph> = {
  ...fromDesign,
  ṉa: { iso: 'ṉa', tamil: 'ன', d: 'M18 28 C40 12 40 52 30 62 C20 72 40 90 54 74 C68 58 82 74 82 88' },
};
VATTELUTTU.na = VATTELUTTU['ṉa']!;

export function vatteluttuSvg(key: string, opts: { stroke?: string; size?: number } = {}): string {
  const g = VATTELUTTU[key.normalize('NFC')];
  if (!g) throw new Error(`no Vatteluttu glyph for ${key}`);
  const size = opts.size ?? 120;
  const stroke = opts.stroke ?? '#1D1611';
  return (
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="${size}" height="${size}" role="img" aria-label="Vatteluttu">` +
    `<path d="${g.d}" fill="none" stroke="${stroke}" stroke-width="${VATTELUTTU_STROKE}" stroke-linecap="round" stroke-linejoin="round"/></svg>`
  );
}

/**
 * `glyph_svg` may be a reference (`"vatteluttu:<iso>"`, one or more aksharas joined by `+`) instead of markup.
 * Returns the drawings to render, or null when it is not a reference or a letter has no drawing.
 */
export function glyphRef(glyphSvg: string | undefined | null): VGlyph[] | null {
  const m = /^vatteluttu:(.+)$/.exec((glyphSvg ?? '').trim());
  if (!m) return null;
  const parts = m[1]!.split('+').map((p) => VATTELUTTU[p.trim().normalize('NFC')]);
  return parts.length && parts.every(Boolean) ? (parts as VGlyph[]) : null;
}
