// The stone hero's clock (StoneHero.tsx), derived from the reading so the story always plays in order:
// letters light up -> fly into the pipeline -> land line by line -> each line's transliteration -> the verdict.
// Pure data, so the order can be unit-tested without a browser (timeline.test.ts).

/** Fixed beats, in ms from the start of a cycle. */
export const BEATS = {
  photoIn: 1100, // first cycle only: the stone fades in
  rake: 500,
  beam: 1500,
  boxes: 1800, // + row * ROW_BOX + i * LETTER_BOX
  lift: 4600, // + row * ROW_LIFT + i * LETTER_LIFT
  reader: 4900,
  restorer: 6700,
  decider: 7500,
  land: 8500, // the first letter of line 1 leaves the Decider
} as const;
export const ROW_BOX = 600;
export const LETTER_BOX = 45;
export const ROW_LIFT = 330;
export const LETTER_LIFT = 32;
/** One letter's landing (out of the Decider into its place). */
export const LAND_MS = 760;
/** Stagger between letters of one line, and the pause between a line's last letter and the next line's first. */
export const LETTER_LAND = 60;
export const LINE_GAP = 400;
/** Each line's transliteration rises once its last letter has landed. */
export const AFTER_LINE_MS = 500;
export const VERDICT_STAGGER = 380;
export const VERDICT_MS = 600;
/** How long the finished reading is held before everything fades. */
export const HOLD_MS = 2000;
export const FADE_MS = 700;
/** Dark pause between the fade and the next cycle. */
export const REST_MS = 300;

export interface LineTimes {
  /** When the line's first letter leaves the Decider. */
  start: number;
  /** When the line's last letter has landed. */
  landed: number;
  /** When the transliteration and line confidence begin to appear. */
  afterLine: number;
}

export interface Timeline {
  lines: LineTimes[];
  /** Landing start of letter k (0-based within its line) of line `line`. */
  landAt: (line: number, k: number) => number;
  verdict: number;
  verdictItems: number;
  cta: number;
  fadeOut: number;
  cycle: number;
}

/** Build the clock for lines with `letters[l]` landing elements each (letters and gap tiles). */
export function buildTimeline(letters: number[], verdictItems = 3): Timeline {
  const lines: LineTimes[] = [];
  let t = BEATS.land;
  for (const n of letters) {
    const last = t + Math.max(0, n - 1) * LETTER_LAND;
    lines.push({ start: t, landed: last + LAND_MS, afterLine: last + LAND_MS });
    t = last + LINE_GAP;
  }
  const finalLanding = lines.length ? Math.max(...lines.map((l) => l.landed)) : BEATS.land;
  const lastAfter = lines.length ? lines[lines.length - 1]!.afterLine + AFTER_LINE_MS : finalLanding;
  const verdict = Math.max(finalLanding, lastAfter - 300) + 150;
  const verdictEnd = verdict + (verdictItems - 1) * VERDICT_STAGGER + VERDICT_MS;
  const fadeOut = verdictEnd + HOLD_MS;
  return {
    lines,
    landAt: (line, k) => (lines[line]?.start ?? BEATS.land) + k * LETTER_LAND,
    verdict,
    verdictItems,
    cta: verdict + 600,
    fadeOut,
    cycle: fadeOut + FADE_MS + REST_MS,
  };
}
