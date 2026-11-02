import { describe, expect, it } from 'vitest';
import { HERO } from './heroData';
import { BEATS, buildTimeline, FADE_MS, LAND_MS, LETTER_LAND } from './timeline';

const letters = HERO.lines.map((l) => l.aksharas.filter((a) => a.kind !== 'space').length);

describe('stone hero timeline: the story plays in order', () => {
  const tl = buildTimeline(letters);

  it('lands each line after the previous one, letter by letter, starting after the Decider wakes', () => {
    expect(tl.lines[0]!.start).toBeGreaterThan(BEATS.decider);
    tl.lines.forEach((l, i) => {
      const n = letters[i]!;
      // letters of one line: index 0..n-1 within the line (never a global index)
      expect(tl.landAt(i, 0)).toBe(l.start);
      expect(tl.landAt(i, n - 1) + LAND_MS).toBe(l.landed);
      if (i > 0) expect(l.start).toBeGreaterThan(tl.landAt(i - 1, letters[i - 1]! - 1));
    });
  });

  it("shows each line's transliteration only once its own last letter has landed, and before the next line lands", () => {
    tl.lines.forEach((l, i) => {
      expect(l.afterLine).toBeGreaterThanOrEqual(l.landed);
      const next = tl.lines[i + 1];
      if (next) expect(next.landed).toBeGreaterThan(l.afterLine);
    });
  });

  it('brings the verdict after the final letter and transliteration, then holds before fading', () => {
    const lastLanding = Math.max(...tl.lines.map((l) => l.landed));
    expect(tl.verdict).toBeGreaterThan(lastLanding);
    expect(tl.verdict).toBeGreaterThan(tl.lines[tl.lines.length - 1]!.afterLine);
    expect(tl.cta).toBeGreaterThan(tl.verdict);
    expect(tl.fadeOut - tl.verdict).toBeGreaterThan(2000);
    expect(tl.cycle).toBeGreaterThanOrEqual(tl.fadeOut + FADE_MS);
  });

  it('keeps one cycle under 18 s', () => {
    expect(tl.cycle).toBeLessThan(18_000);
    expect(LETTER_LAND).toBeGreaterThan(0);
  });
});
