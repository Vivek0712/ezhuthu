/**
 * Horizontal bar chart in plain HTML (labels stay readable at phone width, colours come from the design tokens).
 * One series: the highlighted row (the deployed system) wears the accent, the others a neutral ink. An optional
 * 95% interval is drawn as a whisker with end caps. Values are printed next to each row, so the chart never relies
 * on colour alone, and each row has a hover title with the exact numbers.
 */
export interface BarDatum {
  key: string;
  label: string;
  sub?: string;
  value: number;
  valueText: string;
  ci?: [number, number] | null;
  highlight?: boolean;
  note?: string;
}

export function BarChart({ data, title, max = 1, testId }: { data: readonly BarDatum[]; title: string; max?: number; testId?: string }) {
  const pc = (v: number) => `${Math.max(0, Math.min(100, (v / max) * 100))}%`;
  return (
    <figure className="hbar" aria-label={title} data-testid={testId}>
      <ul className="hbar-rows">
        {data.map((d) => (
          <li key={d.key} className={`hbar-row${d.highlight ? ' hi' : ''}`} data-testid={testId ? `${testId}-${d.key}` : undefined}>
            <div className="hbar-label">
              <span className="hbar-name">{d.label}</span>
              {d.sub && <span className="hbar-sub">{d.sub}</span>}
            </div>
            <div className="hbar-plot" title={`${d.label}: ${d.valueText}${d.ci ? ` [${d.ci[0]}–${d.ci[1]}]` : ''}`}>
              <div className="hbar-track" aria-hidden="true">
                <div className="hbar-fill" style={{ width: pc(d.value) }} />
                {d.ci && (
                  <div className="hbar-ci" style={{ left: pc(d.ci[0]), width: `calc(${pc(d.ci[1])} - ${pc(d.ci[0])})` }} />
                )}
              </div>
              <span className="hbar-value">
                {d.valueText}
                {d.ci && <span className="hbar-civ"> [{d.ci[0]}–{d.ci[1]}]</span>}
              </span>
            </div>
            {d.note && <div className="hbar-note">{d.note}</div>}
          </li>
        ))}
      </ul>
      <div className="hbar-row hbar-axisrow" aria-hidden="true">
        <div className="hbar-label" />
        <div className="hbar-plot">
          <div className="hbar-axis">
            {[0, 0.25, 0.5, 0.75, 1].map((g) => (
              <span key={g} style={{ left: `${g * 100}%` }}>
                {Math.round(g * max * 100) / 100}
              </span>
            ))}
          </div>
          <span className="hbar-value" />
        </div>
      </div>
    </figure>
  );
}
