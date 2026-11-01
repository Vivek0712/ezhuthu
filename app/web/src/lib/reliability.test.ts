import { describe, expect, it } from 'vitest';
import { expectedCalibrationError, reliabilityBins } from './reliability';

describe('reliabilityBins', () => {
  it('bins by confidence, ignores abstentions and clamps 1.0 into the top bin', () => {
    const bins = reliabilityBins(
      [
        { confidence: 0.95, correct: true },
        { confidence: 1.0, correct: false },
        { confidence: 0.05, correct: false },
        { confidence: 0.55, correct: true, abstained: true },
      ],
      10,
    );
    expect(bins).toHaveLength(10);
    expect(bins[9]).toMatchObject({ count: 2, accuracy: 0.5 });
    expect(bins[9]!.meanConfidence).toBeCloseTo(0.975);
    expect(bins[0]).toMatchObject({ count: 1, accuracy: 0 });
    expect(bins[5]!.count).toBe(0);
  });
  it('rejects a bad bin count', () => {
    expect(() => reliabilityBins([], 0)).toThrow();
  });
});

describe('expectedCalibrationError', () => {
  it('is 0 for perfectly calibrated bins and |acc-conf| otherwise', () => {
    const perfect = [
      { confidence: 0.5, correct: true },
      { confidence: 0.5, correct: false },
    ];
    expect(expectedCalibrationError(perfect, 10)).toBeCloseTo(0);
    expect(expectedCalibrationError([{ confidence: 0.9, correct: false }], 10)).toBeCloseTo(0.9);
    expect(expectedCalibrationError([], 10)).toBe(0);
  });
});
