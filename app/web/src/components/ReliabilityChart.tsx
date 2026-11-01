import { reliabilityBins, type Scored } from '../lib/reliability';

/** Reliability diagram: observed accuracy per confidence bin against the perfect-calibration diagonal. */
export function ReliabilityChart({ items, title, bins = 10 }: { items: readonly Scored[]; title: string; bins?: number }) {
  const data = reliabilityBins(items, bins);
  const W = 320;
  const H = 240;
  const P = { l: 36, r: 10, t: 12, b: 30 };
  const iw = W - P.l - P.r;
  const ih = H - P.t - P.b;
  const x = (v: number) => P.l + v * iw;
  const y = (v: number) => P.t + (1 - v) * ih;
  const bw = iw / bins;
  return (
    <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={title} data-testid="reliability-chart">
      <title>{title}</title>
      {[0, 0.25, 0.5, 0.75, 1].map((g) => (
        <g key={g}>
          <line className="axis" x1={P.l} x2={W - P.r} y1={y(g)} y2={y(g)} />
          <text x={P.l - 6} y={y(g) + 4} textAnchor="end">
            {g * 100}
          </text>
          <text x={x(g)} y={H - 10} textAnchor="middle">
            {g * 100}
          </text>
        </g>
      ))}
      {data.map((b, i) =>
        b.count ? (
          <g key={i}>
            <rect className="gapbar" x={x(b.lo) + 2} width={bw - 4} y={y(Math.max(b.accuracy, b.meanConfidence))} height={Math.abs(y(b.accuracy) - y(b.meanConfidence))} />
            <rect className="bar" x={x(b.lo) + 2} width={bw - 4} y={y(b.accuracy)} height={ih - (y(b.accuracy) - P.t)} opacity={0.9}>
              <title>{`${Math.round(b.lo * 100)}–${Math.round(b.hi * 100)}%: ${b.count} items, ${Math.round(b.accuracy * 100)}% match`}</title>
            </rect>
          </g>
        ) : null,
      )}
      <line className="diag" x1={x(0)} y1={y(0)} x2={x(1)} y2={y(1)} />
    </svg>
  );
}
