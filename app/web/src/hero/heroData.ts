// Typed view of hero-reading.json: the real output of Ezhuthu's Reader and Restorer on one real photograph
// (scripts/hero_read.py, scripts/hero_build.py). Nothing here is invented for the animation.
import raw from './hero-reading.json';

export type Box = [number, number, number, number]; // x0, y0, x1, y1 in photo pixels

export interface HeroAkshara {
  kind: 'letter' | 'gap' | 'space';
  ta?: string;
  size?: number;
  decision?: string;
  best?: { ta: string; iso: string; confidence: number } | null;
}

export interface HeroLine {
  n: string;
  iso: string;
  ta: string;
  confidence: number | null;
  aksharas: HeroAkshara[];
}

interface Raw {
  photo: { width: number; height: number; widths: number[]; commons_url: string; author_url: string; licence_url: string };
  boxes: Box[][];
  reading: {
    final: { confidence: number; script: { label_en: string; label_ta: string; confidence: number } };
    first_pass: { confidence: number | null };
    lines: HeroLine[];
  };
  restore: { abstain_below: number; decisions: string[] };
}

const data = raw as unknown as Raw;

export const HERO = {
  photo: data.photo,
  boxes: data.boxes,
  lines: data.reading.lines,
  confidence: data.reading.final.confidence,
  firstPassConfidence: data.reading.first_pass.confidence,
  script: data.reading.final.script,
  abstainBelow: data.restore.abstain_below,
  gaps: data.restore.decisions.length,
  fills: data.restore.decisions.filter((d) => d !== 'abstain').length,
};

/** srcset for one format of the photo, e.g. "/hero/thanjavur-480.avif 480w, ...". */
export function heroSrcSet(ext: 'avif' | 'webp' | 'jpg'): string {
  return HERO.photo.widths.map((w) => `/hero/thanjavur-${w}.${ext} ${w}w`).join(', ');
}
