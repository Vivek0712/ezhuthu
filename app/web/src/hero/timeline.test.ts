import { describe, expect, it } from 'vitest';
import { HERO } from './heroData';
import { buildTimeline, FEATURE_MS, FLY_MS, HOLD_MS, kbAt, kbTransform, readingIndex, trackKeyframes, type Stop } from './timeline';

const letters = HERO.rows.map((r) => r.glyphs.length);
const total = letters.reduce((a, b) => a + b, 0);

describe('stone hero timeline: the story plays in order', () => {
  const tl = buildTimeline(letters, HERO.featured, HERO.gaps.length);

  it('lights every box before the Reader starts matching', () => {
    letters.forEach((n, r) => {
      for (let i = 0; i < n; i++) expect(tl.boxOn(r, i)).toBeLessThan(tl.match);
      if (r > 0) expect(tl.boxOn(r, 0)).toBeGreaterThan(tl.boxOn(r - 1, letters[r - 1]! - 1));
    });
  });

  it('features the first letters one card at a time, slow first, then cascades the rest in reading order', () => {
    expect(tl.cards).toHaveLength(HERO.featured);
    tl.cards.forEach((c, k) => {
      expect(c.idx).toBe(k);
      expect(c.in).toBeLessThan(c.ringFrom);
      expect(c.ringFrom).toBeLessThan(c.ringTo);
      expect(c.ringTo).toBeLessThan(c.out);
      expect(c.out).toBeLessThan(c.end);
      if (k > 0) {
        expect(c.in).toBeGreaterThanOrEqual(tl.cards[k - 1]!.end); // one at a time
        expect(c.end - c.in).toBeLessThanOrEqual(tl.cards[k - 1]!.end - tl.cards[k - 1]!.in); // accelerating
      }
      expect(c.end - c.in).toBeGreaterThanOrEqual(Math.min(...FEATURE_MS));
    });
    // Featured letters get their badge as their card leaves; the cascade follows the last card, in reading order.
    tl.cards.forEach((c) => expect(tl.badgeAt(c.idx)).toBe(c.out));
    const lastCard = tl.cards[tl.cards.length - 1]!;
    for (let idx = HERO.featured; idx < total; idx++) {
      expect(tl.badgeAt(idx)).toBeGreaterThan(lastCard.end);
      if (idx > HERO.featured) expect(tl.badgeAt(idx)).toBeGreaterThan(tl.badgeAt(idx - 1));
    }
    expect(tl.cascadeEnd).toBeGreaterThan(tl.badgeAt(total - 1));
  });

  it('runs the gap stage (Restorer, then Decider) after the match and before any letter flies', () => {
    const g = tl.gap;
    expect(g.start).toBeGreaterThan(tl.cascadeEnd);
    expect(g.restorer).toBeLessThan(g.restorerOut);
    expect(g.restorerOut).toBeLessThan(g.decider);
    expect(g.decider).toBeLessThan(g.deciderOut);
    expect(g.resolve).toBeGreaterThanOrEqual(g.deciderOut);
    expect(g.end).toBeGreaterThan(g.resolve);
    expect(tl.flyAt(0, 0)).toBeGreaterThanOrEqual(g.end);
  });

  it('assembles the reading row by row, each letter of a row after the one before (indices are per row)', () => {
    tl.rows.forEach((row, r) => {
      const n = letters[r]!;
      expect(tl.flyAt(r, 0)).toBe(row.start);
      expect(tl.flyAt(r, n - 1) + FLY_MS).toBe(row.landed);
      for (let i = 1; i < n; i++) expect(tl.flyAt(r, i)).toBeGreaterThan(tl.flyAt(r, i - 1));
      if (r > 0) {
        // The next row starts after this row's last letter has taken off, and lands after it.
        expect(row.start).toBeGreaterThan(tl.flyAt(r - 1, letters[r - 1]! - 1));
        expect(row.landed).toBeGreaterThan(tl.rows[r - 1]!.landed);
      }
    });
  });

  it('brings the verdict after the last letter, holds, fades and rests within one cycle', () => {
    const last = Math.max(...tl.rows.map((r) => r.landed));
    expect(tl.verdict).toBeGreaterThan(last);
    expect(tl.cta).toBeGreaterThan(tl.verdict);
    expect(tl.fadeOut - tl.verdict).toBeGreaterThanOrEqual(HOLD_MS);
    expect(tl.cycle).toBeGreaterThan(tl.fadeOut);
    expect(tl.cycle).toBeLessThan(24_000);
  });

  it('maps (row, letter) to reading order', () => {
    expect(readingIndex(letters, 0, 0)).toBe(0);
    expect(readingIndex(letters, 1, 0)).toBe(letters[0]);
    expect(readingIndex(letters, letters.length - 1, letters[letters.length - 1]! - 1)).toBe(total - 1);
  });

  it('still plays in order with no gaps', () => {
    const t0 = buildTimeline(letters, HERO.featured, 0);
    expect(t0.gap.end).toBeGreaterThan(t0.cascadeEnd);
    expect(t0.gap.end - t0.gap.start).toBeLessThan(tl.gap.end - tl.gap.start);
  });
});

describe('stone hero loop: consecutive cycles meet without a jump', () => {
  const C = 20_000;
  it('the Ken Burns drift ends each cycle where the next one starts (alternating direction)', () => {
    expect(kbTransform(kbAt(C, C, true))).toBe(kbTransform(kbAt(0, C, false)));
    expect(kbTransform(kbAt(C, C, false))).toBe(kbTransform(kbAt(0, C, true)));
    expect(kbAt(0, C, true).s).toBeGreaterThan(1);
    expect(kbAt(C, C, true).s).toBe(1);
  });

  it('a track spans the whole cycle and holds its first and last stops to the ends', () => {
    const stops: Stop[] = [
      [5000, { opacity: 0, transform: 'scale(.5)' }],
      [6000, { opacity: 1, transform: 'none' }],
      [18_000, { opacity: 1, transform: 'none' }],
      [18_700, { opacity: 0, transform: 'none' }],
    ];
    const kf = trackKeyframes(stops, C);
    expect(kf[0]).toMatchObject({ offset: 0, opacity: 0, transform: 'scale(.5)' });
    expect(kf[kf.length - 1]).toMatchObject({ offset: 1, opacity: 0 });
    const offs = kf.map((k) => k.offset as number);
    expect(offs).toEqual([...offs].sort((a, b) => a - b));
    // Stops outside the cycle are clamped, never dropped or out of range.
    const clamped = trackKeyframes([[-50, { opacity: 0 }], [C + 500, { opacity: 1 }]], C);
    expect(clamped.map((k) => k.offset)).toEqual([0, 1]);
  });
});
