import type { ReactNode } from 'react';

/** Tamil script with its ISO-15919 (English-letter) form underneath: the pair the app shows everywhere. */
export function Bi({ ta, iso, className, taClass, hideIso, hideTa }: { ta: string; iso?: string; className?: string; taClass?: string; hideIso?: boolean; hideTa?: boolean }) {
  return (
    <span className={`bi ${className ?? ''}`}>
      {!hideTa && (
        <span className={`bi-ta ${taClass ?? ''}`} lang="ta">
          {ta}
        </span>
      )}
      {iso && !hideIso && (
        <span className="bi-iso iso" lang="ta-Latn">
          {iso}
        </span>
      )}
    </span>
  );
}

/** A passage with one highlighted span, in both scripts. */
export function BiLine({ parts, mark }: { parts: { before: { ta: string; iso: string }; match: { ta: string; iso: string }; after: { ta: string; iso: string } }; mark: boolean }) {
  const span = (s: string, k: 'before' | 'match' | 'after'): ReactNode =>
    k === 'match' && mark ? <mark className="formula-mark">{s}</mark> : s;
  return (
    <span className="bi bi-line">
      <span className="bi-ta script-chola" lang="ta">
        {span(parts.before.ta, 'before')} {span(parts.match.ta, 'match')} {span(parts.after.ta, 'after')}
      </span>
      <span className="bi-iso iso" lang="ta-Latn">
        {span(parts.before.iso, 'before')} {span(parts.match.iso, 'match')} {span(parts.after.iso, 'after')}
      </span>
    </span>
  );
}
