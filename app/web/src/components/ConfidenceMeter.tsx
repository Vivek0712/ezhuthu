import { pct } from '../lib/format';

/**
 * Ten 8 px segments filled in accent (design/ux/UX.md section 5). The API does not send the decider's fill
 * threshold, so no high/medium/low word is derived here (the UX spec forbids hard-coding it); the meter shows
 * the stated confidence as a number.
 */
export function ConfidenceMeter({ value, label }: { value: number; label: string }) {
  const v = Math.max(0, Math.min(1, value));
  const lit = Math.round(v * 10);
  return (
    <div className="meter-row">
      <div className="meter" role="meter" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(v * 100)} aria-valuetext={pct(v)}>
        {Array.from({ length: 10 }, (_, i) => (
          <span key={i} className={i < lit ? 'seg on' : 'seg'} />
        ))}
      </div>
      <span className="meter-val">{pct(v)}</span>
    </div>
  );
}
