/** Reliability diagram helpers: bin predictions by confidence and compare to observed accuracy. */
export interface Scored {
  confidence: number;
  correct: boolean;
  abstained?: boolean;
}

export interface Bin {
  lo: number;
  hi: number;
  count: number;
  meanConfidence: number;
  accuracy: number;
}

export function reliabilityBins(items: readonly Scored[], nBins = 10): Bin[] {
  if (!Number.isInteger(nBins) || nBins < 1) throw new Error('nBins must be a positive integer');
  const bins = Array.from({ length: nBins }, (_, i) => ({ lo: i / nBins, hi: (i + 1) / nBins, n: 0, conf: 0, ok: 0 }));
  for (const it of items) {
    if (it.abstained) continue;
    const c = Math.min(1, Math.max(0, it.confidence));
    const b = bins[Math.min(nBins - 1, Math.floor(c * nBins))]!;
    b.n += 1;
    b.conf += c;
    b.ok += it.correct ? 1 : 0;
  }
  return bins.map((b) => ({
    lo: b.lo,
    hi: b.hi,
    count: b.n,
    meanConfidence: b.n ? b.conf / b.n : 0,
    accuracy: b.n ? b.ok / b.n : 0,
  }));
}

/** Expected calibration error over the same bins (weighted |accuracy - confidence|). */
export function expectedCalibrationError(items: readonly Scored[], nBins = 10): number {
  const bins = reliabilityBins(items, nBins);
  const total = bins.reduce((s, b) => s + b.count, 0);
  if (!total) return 0;
  return bins.reduce((s, b) => s + (b.count / total) * Math.abs(b.accuracy - b.meanConfidence), 0);
}
