// The stone hero's clock (StoneHero.tsx), derived from the reading so the story always plays in order:
// the stone and the scan -> letters light up row by row -> MATCH: the first few letters one at a time in a full card
// (carved glyph -> modern Tamil letter, confidence ring), then a fast cascade of small badges over the rest -> the gap
// stage (Restorer proposes, Strands Decider fills or abstains) -> the letters fly through the pipeline and assemble
// into the reading, row by row -> WORDS: the run-on letters slide apart into words -> PHRASE: the words, arranged in
// today's Tamil, replace the letter rows -> MEANING (English, then Tamil) -> the verdict -> hold -> everything but the
// photo and the meaning fades; the meaning crossfades out as the next cycle's scan begins.
// Pure data, so the order and the loop can be unit-tested without a browser (timeline.test.ts).

/** Fixed beats, in ms from the start of a cycle. */
export const BEATS = {
  photoIn: 1000, // first cycle only: the stone fades in (later cycles keep it on screen)
  rake: 300,
  beam: 1100,
  beamMs: 2200,
} as const;
/** Boxes light up while the beam passes their row. */
export const ROW_BOX = 470;
export const LETTER_BOX = 22;
/** The first featured cards are slow enough to read; they speed up into the cascade. */
export const FEATURE_MS = [1250, 900, 680, 520, 420] as const;
/** Stagger of the small badges in the cascade (reading order). */
export const CASCADE_STAGGER = 36;
/** One badge pops in this long. */
export const BADGE_MS = 300;
/** The gap stage: Restorer proposes, Decider decides, the gap's badge turns to "?" (or to the fill). */
export const GAP_STAGE_MS = 2000;
export const NO_GAP_STAGE_MS = 900;
/** One letter's flight from its box, past the pipeline, into its place in the reading. */
export const FLY_MS = 820;
/** Stagger between letters of one row, and the overlap step from one row's start to the next. */
export const LETTER_FLY = 38;
export const ROW_STEP = 300;
export const CHIP_MS = 420;
export const VERDICT_STAGGER = 320;
export const VERDICT_MS = 560;
/** WORDS: the letters slide apart into word groups, then each word's underline (and gloss) draws in. */
export const WORDS_MS = 800;
export const WORD_STAGGER = 70;
export const WORD_LINE_MS = 320;
/** PHRASE: the letter rows give way to the phrase, whose words rise one by one. */
export const PANE_MS = 520;
export const TOKEN_STAGGER = 170;
export const TOKEN_MS = 420;
/** MEANING: English, then Tamil. */
export const MEANING_MS = 600;
export const MEANING_STAGGER = 400;
/** How long the finished frame (stone | phrase and meaning) is held before it fades. */
export const HOLD_MS = 3000;
/** Next cycle: the meaning carried over from the last cycle fades out during the scan. */
export const CARRY_OUT = [700, 1500] as const;
export const FADE_MS = 700;
/** Pause between the fade and the next cycle (the photo stays). */
export const REST_MS = 300;

export interface Card {
  /** Reading-order index of the featured letter. */
  idx: number;
  /** Card pops in. */
  in: number;
  /** Confidence ring starts / finishes filling. */
  ringFrom: number;
  ringTo: number;
  /** Card leaves (shrinks into its badge). */
  out: number;
  end: number;
}

export interface RowTimes {
  /** When the row's first letter takes off. */
  start: number;
  /** When the row's last letter has landed. */
  landed: number;
}

export interface Timeline {
  /** Box (row r, letter i) lights up. */
  boxOn: (r: number, i: number) => number;
  /** When the Reader starts matching (first card). */
  match: number;
  cards: Card[];
  /** When the badge of the letter at reading-order index `idx` appears. */
  badgeAt: (idx: number) => number;
  cascadeEnd: number;
  gap: { start: number; restorer: number; restorerOut: number; decider: number; deciderOut: number; resolve: number; end: number };
  rows: RowTimes[];
  /** Take-off time of letter i of row r (letters are indexed within their own row). */
  flyAt: (r: number, i: number) => number;
  /** Letters slide into words; word w's underline draws at wordAt(w). */
  words: { start: number; slid: number; end: number };
  wordAt: (w: number) => number;
  /** The letter rows give way to the phrase pane; phrase token k rises at tokenAt(k). */
  phrase: { start: number; paneIn: number; end: number };
  tokenAt: (k: number) => number;
  /** English meaning, then Tamil. The finished frame is held HOLD_MS from meaning.end. */
  meaning: { en: number; ta: number; end: number };
  verdict: number;
  verdictItems: number;
  cta: number;
  fadeOut: number;
  cycle: number;
}

/**
 * Build the clock for rows with `letters[r]` letters each, `featured` of them shown in full cards first.
 * `gaps` is how many letters go to the Restorer (0 skips most of the gap stage).
 */
export function buildTimeline(letters: number[], featured = 4, gaps = 1, verdictItems = 2, nWords = 0, nTokens = 0): Timeline {
  const total = letters.reduce((a, b) => a + b, 0);
  const boxOn = (r: number, i: number) => BEATS.beam + 220 + r * ROW_BOX + i * LETTER_BOX;
  const lastBox = letters.length ? boxOn(letters.length - 1, Math.max(0, letters[letters.length - 1]! - 1)) : BEATS.beam;
  const match = Math.max(lastBox + 380, BEATS.beam + BEATS.beamMs);

  const nf = Math.min(featured, total);
  const cards: Card[] = [];
  let t = match;
  for (let k = 0; k < nf; k++) {
    const d = FEATURE_MS[Math.min(k, FEATURE_MS.length - 1)]!;
    cards.push({ idx: k, in: t, ringFrom: t + d * 0.2, ringTo: t + d * 0.62, out: t + d * 0.84, end: t + d });
    t += d;
  }
  const cascade = t + 60;
  const badgeAt = (idx: number) => (idx < nf ? cards[idx]!.out : cascade + (idx - nf) * CASCADE_STAGGER);
  const cascadeEnd = (total > nf ? badgeAt(total - 1) : t) + BADGE_MS;

  const gs = cascadeEnd + 150;
  const gap = gaps > 0
    ? { start: gs, restorer: gs + 150, restorerOut: gs + 650, decider: gs + 900, deciderOut: gs + 1350, resolve: gs + 1500, end: gs + GAP_STAGE_MS }
    : { start: gs, restorer: gs, restorerOut: gs + 250, decider: gs + 350, deciderOut: gs + 600, resolve: gs + 600, end: gs + NO_GAP_STAGE_MS };

  const rows: RowTimes[] = [];
  let s = gap.end;
  for (const n of letters) {
    const last = s + Math.max(0, n - 1) * LETTER_FLY;
    rows.push({ start: s, landed: last + FLY_MS });
    s = last + ROW_STEP;
  }
  const finalLanding = rows.length ? Math.max(...rows.map((r) => r.landed)) : gap.end;
  const ws = finalLanding + CHIP_MS - 150;
  const slid = ws + WORDS_MS;
  const wordAt = (w: number) => slid - 200 + w * WORD_STAGGER;
  const words = { start: ws, slid, end: nWords ? wordAt(nWords - 1) + WORD_LINE_MS + 300 : slid };
  const ps = words.end + 150;
  const tokenAt = (k: number) => ps + PANE_MS * 0.6 + k * TOKEN_STAGGER;
  const phrase = { start: ps, paneIn: ps + PANE_MS, end: nTokens ? tokenAt(nTokens - 1) + TOKEN_MS : ps + PANE_MS };
  const en = phrase.end + 200;
  const meaning = { en, ta: en + MEANING_STAGGER, end: en + MEANING_STAGGER + MEANING_MS };
  // The verdict on the letters comes as soon as they have all landed (the bottom strip is never empty for long); the
  // hold starts once the meaning is in.
  const verdict = finalLanding + CHIP_MS + 120;
  const verdictEnd = verdict + (verdictItems - 1) * VERDICT_STAGGER + VERDICT_MS;
  const fadeOut = Math.max(verdictEnd, meaning.end) + HOLD_MS;
  return {
    boxOn,
    match,
    cards,
    badgeAt,
    cascadeEnd,
    gap,
    rows,
    flyAt: (r, i) => (rows[r]?.start ?? gap.end) + i * LETTER_FLY,
    words,
    wordAt,
    phrase,
    tokenAt,
    meaning,
    verdict,
    verdictItems,
    cta: verdict + 500,
    fadeOut,
    cycle: fadeOut + FADE_MS + REST_MS,
  };
}

/** Reading-order index of letter i of row r. */
export function readingIndex(letters: number[], r: number, i: number): number {
  let n = 0;
  for (let k = 0; k < r; k++) n += letters[k]!;
  return n + i;
}

// ---- keyframe tracks: one animation per element over the whole cycle ----
// Every animated element gets exactly one animation of length `cycle`, built from timed stops. An element's state at
// the end of the cycle is therefore explicit (no two animations composite over each other, nothing flashes from a
// stale fill), and the loop seam can be tested: the last stop of each track equals what the next cycle's first stop
// expects.

export type Props = Record<string, string | number>;
export type Stop = [t: number, props: Props, easing?: string];

/** WAAPI keyframes from timed stops (clamped into [0, cycle], sorted, with the end points filled in). */
export function trackKeyframes(stops: Stop[], cycle: number): Keyframe[] {
  const sorted = stops
    .map(([t, p, e]) => [Math.min(cycle, Math.max(0, t)), p, e] as Stop)
    .sort((a, b) => a[0] - b[0]);
  if (!sorted.length) return [];
  if (sorted[0]![0] > 0) sorted.unshift([0, sorted[0]![1]]);
  if (sorted[sorted.length - 1]![0] < cycle) sorted.push([cycle, sorted[sorted.length - 1]![1]]);
  return sorted.map(([t, p, e]) => ({ ...p, offset: t / cycle, ...(e ? { easing: e } : {}) }));
}

export const HIDDEN: Props = { opacity: 0, transform: 'none' };
export const SHOWN: Props = { opacity: 1, transform: 'none' };

// ---- the photo's slow Ken Burns drift ----
/** Scale and translate (fractions of the photo) at the wide end; reached at KB_END of the cycle and held. Even cycles
 * drift from wide to none, odd cycles back, so consecutive cycles meet without a jump. */
export const KB = { s: 1.04, tx: -0.01, ty: 0.006 } as const;
export const KB_END = 0.9;
/** The drift at time t (ms into a cycle of `cycle` ms). `out`: this cycle drifts from wide to none. */
export function kbAt(t: number, cycle: number, out: boolean) {
  const p0 = Math.min(1, Math.max(0, t / (cycle * KB_END)));
  const p = out ? p0 : 1 - p0;
  return { s: KB.s + (1 - KB.s) * p, tx: KB.tx * (1 - p), ty: KB.ty * (1 - p) };
}
export const kbTransform = ({ s, tx, ty }: { s: number; tx: number; ty: number }) =>
  `scale(${s.toFixed(4)}) translate(${(tx * 100).toFixed(3)}%, ${(ty * 100).toFixed(3)}%)`;
