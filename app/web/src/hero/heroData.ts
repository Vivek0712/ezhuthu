// Typed view of hero-view.json: the real output of Ezhuthu's Reader (letter by letter), Restorer and Strands Decider
// on one real photograph (scripts/hero_read.py, scripts/hero_build.py). Nothing here is invented for the animation.
// hero-view.json is the trimmed subset the page needs; the full record (models, notes, candidates, the line-level
// reading) is hero-reading.json, kept out of the bundle and checked against this view in StoneHero.test.tsx and
// tests/test_hero_assets.py.
import raw from './hero-view.json';

export type Box = [number, number, number, number]; // x0, y0, x1, y1 in photo pixels

export interface HeroGlyph {
  /** The modern Tamil letter the Reader matched to the carved letter in this box ('' if it named none). */
  ta: string;
  /** The Reader's probability that the letter is right. */
  c: number | null;
  /** Present when the letter was under the cut-off and went to the Restorer. */
  gap?: { decision: string; best: { ta: string; c: number } | null };
}

export interface HeroRow {
  iso: string;
  /** Mean letter confidence of the row. */
  c: number;
  glyphs: HeroGlyph[];
}

interface Raw {
  photo: { width: number; height: number; widths: number[]; commons_url: string; licence_url: string };
  boxes: Box[][];
  script: { label_en: string; label_ta: string };
  rows: HeroRow[];
  featured: number;
  letters: number;
  mean: number;
  abstain_below: number;
}

const data = raw as unknown as Raw;

const gaps = data.rows.flatMap((r, ri) => r.glyphs.map((g, gi) => ({ r: ri, i: gi, g })).filter((x) => x.g.gap));

export const HERO = {
  photo: data.photo,
  boxes: data.boxes,
  script: data.script,
  rows: data.rows,
  featured: data.featured,
  letters: data.letters,
  mean: data.mean,
  abstainBelow: data.abstain_below,
  /** Letters that went to the Restorer, in reading order. */
  gaps,
  /** How many of them the Decider filled. */
  fills: gaps.filter((x) => x.g.gap!.decision !== 'abstain').length,
};

/** srcset for one format of the photo, e.g. "/hero/thanjavur-480.avif 480w, ...". */
export function heroSrcSet(ext: 'avif' | 'webp' | 'jpg'): string {
  return HERO.photo.widths.map((w) => `/hero/thanjavur-${w}.${ext} ${w}w`).join(', ');
}

/** Confidence tint class: high >= 0.7, mid >= the cut-off, low under it. */
export function confClass(c: number | null | undefined): 'sh-c-high' | 'sh-c-mid' | 'sh-c-low' {
  if (c == null) return 'sh-c-low';
  if (c >= 0.7) return 'sh-c-high';
  if (c >= HERO.abstainBelow) return 'sh-c-mid';
  return 'sh-c-low';
}

/** 0.8 -> "80%". */
export function pctLabel(c: number | null | undefined): string {
  return c == null ? '–' : `${Math.round(c * 100)}%`;
}
