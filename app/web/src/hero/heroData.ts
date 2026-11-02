// Typed view of hero-view.json: the real output of Ezhuthu's Reader (letter by letter), Restorer (deployed config: calibrated pre-rank, no decider) and
// Interpreter (words, modern Tamil phrase, meaning) on one real photograph (scripts/hero_read.py, scripts/hero_build.py). Nothing here is invented for the animation.
// hero-view.json is the trimmed subset the page needs; the full record (models, notes, candidates, the line-level
// reading) is hero-reading.json, kept out of the bundle and checked against this view in StoneHero.test.tsx and
// tests/test_hero_assets.py.
import raw from './hero-view.json';

export type Box = [number, number, number, number]; // x0, y0, x1, y1 in photo pixels

export interface HeroGlyph {
  /** The modern Tamil letter the Reader matched to the carved letter in this box ('' if it named none). */
  ta: string;
  /** The Reader's own (self-reported, uncalibrated) probability that the letter is right. */
  c: number | null;
  /** Present when the letter was under the cut-off and went to the Restorer. */
  /** Present when the letter was under the cut-off and went to the Restorer: its decision, the calibrated threshold
   * the best fill was held to (`below`), and the best fill with its calibrated confidence. */
  gap?: { decision: string; below: number; best: { ta: string; c: number } | null };
}

export interface HeroRow {
  /** Mean letter confidence of the row. */
  c: number;
  glyphs: HeroGlyph[];
}

export interface HeroWord {
  /** The word in today's Tamil spelling. */
  ta: string;
  /** Short English gloss. */
  en: string | null;
  /** The Interpreter's probability that the word is right. */
  c: number | null;
  /** [row, letter] of each letter of the word, in reading order (a word may run on to the next row). */
  at: [number, number][];
}

interface Raw {
  photo: { width: number; height: number; widths: number[]; commons_url: string; licence_url: string };
  boxes: Box[][];
  script: { label_en: string; label_ta: string };
  rows: HeroRow[];
  featured: number;
  letters: number;
  mean: number;
  letter_cut: number;
  words: HeroWord[];
  phrase: { ta: string; iso: string };
  meaning: { en: string; ta: string };
  meaning_c: number | null;
}

const data = raw as unknown as Raw;

const gaps = data.rows.flatMap((r, ri) => r.glyphs.map((g, gi) => ({ r: ri, i: gi, g })).filter((x) => x.g.gap));

/** Word index of each letter, by row: wordOf[r][i] (-1 for a letter in no word). */
const wordOf = data.rows.map((r) => r.glyphs.map(() => -1));
data.words.forEach((w, k) => w.at.forEach(([r, i]) => (wordOf[r]![i] = k)));

export const HERO = {
  photo: data.photo,
  boxes: data.boxes,
  script: data.script,
  rows: data.rows,
  featured: data.featured,
  letters: data.letters,
  mean: data.mean,
  /** Letters the Reader named under this (its own confidence) went to the Restorer; also the legend's low band. */
  letterCut: data.letter_cut,
  /** Letters that went to the Restorer, in reading order. */
  gaps,
  /** How many of them the Restorer filled (its calibrated confidence reached the calibrated threshold). */
  fills: gaps.filter((x) => x.g.gap!.decision !== 'abstain').length,
  words: data.words,
  wordOf,
  phrase: data.phrase,
  /** The phrase split into its words (and "…" for unreadable stretches), in order. */
  phraseTokens: data.phrase.ta.split(/\s+/).filter(Boolean),
  meaning: data.meaning,
  meaningC: data.meaning_c,
};

/** Consecutive runs of letters of one row that belong to the same word: [word index, first letter, last letter]. */
export function wordRuns(r: number): [number, number, number][] {
  const out: [number, number, number][] = [];
  wordOf[r]!.forEach((w, i) => {
    const last = out[out.length - 1];
    if (last && last[0] === w && w !== -1) last[2] = i;
    else out.push([w, i, i]);
  });
  return out;
}

/** srcset for one format of the photo, e.g. "/hero/thanjavur-480.avif 480w, ...". */
export function heroSrcSet(ext: 'avif' | 'webp' | 'jpg'): string {
  return HERO.photo.widths.map((w) => `/hero/thanjavur-${w}.${ext} ${w}w`).join(', ');
}

/** Confidence tint class: high >= 0.7, mid >= the cut-off, low under it. */
export function confClass(c: number | null | undefined): 'sh-c-high' | 'sh-c-mid' | 'sh-c-low' {
  if (c == null) return 'sh-c-low';
  if (c >= 0.7) return 'sh-c-high';
  if (c >= HERO.letterCut) return 'sh-c-mid';
  return 'sh-c-low';
}

/** 0.8 -> "80%". */
export function pctLabel(c: number | null | undefined): string {
  return c == null ? '–' : `${Math.round(c * 100)}%`;
}

/** Where a letter's badge is centred, in photo pixels: on the bottom edge of its box, unless that would push the badge
 * past the edge of the photo (the last carved line sits right at the crop's bottom; the first and last letters of a
 * line at its sides). Then it is moved in just far enough that all of it stays inside the frame, also while the slow
 * drift has the photo zoomed in. Badges are sized in cqw with an 8 px floor, so relative to the photo's width they are
 * largest on a 375 px phone: there a badge reaches at most BADGE_HALF_H below its centre and (wide letters such as ண
 * included) BADGE_HALF_W to either side; e2e/stone-hero.spec.ts checks every badge against the frame. */
export const BADGE_HALF_H = 0.034;
export const BADGE_HALF_W = 0.036;
/** Room for the drift (the zoom and pan crop at most this much of the photo's width off an edge while badges show). */
export const BADGE_EDGE_Y = 0.012;
export const BADGE_EDGE_X = 0.02;
export function badgeAnchor(box: Box): { x: number; y: number } {
  const { width: W, height: H } = HERO.photo;
  const [x0, , x1, y1] = box;
  const side = (BADGE_HALF_W + BADGE_EDGE_X) * W;
  return {
    x: Math.min(W - side, Math.max(side, (x0 + x1) / 2)),
    y: Math.min(y1, H - (BADGE_HALF_H + BADGE_EDGE_Y) * W),
  };
}
