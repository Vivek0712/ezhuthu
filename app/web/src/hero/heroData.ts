// Typed view of hero-view.json: the real output of Ezhuthu's Reader and Restorer on one real photograph
// (scripts/hero_read.py, scripts/hero_build.py). Nothing here is invented for the animation. hero-view.json is the
// trimmed subset the page needs; the full record (models, candidates, notes) is hero-reading.json, kept out of the
// bundle and checked against this view in StoneHero.test.tsx and tests/test_hero_assets.py.
import raw from './hero-view.json';

export type Box = [number, number, number, number]; // x0, y0, x1, y1 in photo pixels

export interface HeroAkshara {
  kind: 'letter' | 'gap' | 'space';
  ta?: string;
  size?: number;
  best?: { ta: string; confidence: number } | null;
}

export interface HeroLine {
  n: string;
  iso: string;
  ta: string;
  confidence: number | null;
  aksharas: HeroAkshara[];
}

interface Raw {
  photo: { width: number; height: number; widths: number[]; commons_url: string; licence_url: string };
  boxes: Box[][];
  reading: { confidence: number; script: { label_en: string; label_ta: string }; lines: HeroLine[] };
  restore: { abstain_below: number; decisions: string[] };
}

const data = raw as unknown as Raw;

export const HERO = {
  photo: data.photo,
  boxes: data.boxes,
  lines: data.reading.lines,
  confidence: data.reading.confidence,
  script: data.reading.script,
  abstainBelow: data.restore.abstain_below,
  gaps: data.restore.decisions.length,
  fills: data.restore.decisions.filter((d) => d !== 'abstain').length,
};

/** srcset for one format of the photo, e.g. "/hero/thanjavur-480.avif 480w, ...". */
export function heroSrcSet(ext: 'avif' | 'webp' | 'jpg'): string {
  return HERO.photo.widths.map((w) => `/hero/thanjavur-${w}.${ext} ${w}w`).join(', ');
}
