import { pct } from '../lib/format';

export function ConfidenceMeter({ value, label }: { value: number; label: string }) {
  const v = Math.max(0, Math.min(1, value));
  return (
    <div className="meter-row">
      <div className="meter" role="meter" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(v * 100)}>
        <span style={{ width: `${v * 100}%` }} />
      </div>
      <span>{pct(v)}</span>
    </div>
  );
}
