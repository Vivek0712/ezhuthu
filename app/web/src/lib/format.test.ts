import { describe, expect, it } from 'vitest';
import { pct, safeHref, signedPct, svgDataUrl } from './format';

describe('format helpers', () => {
  it('formats percentages and gains, with a dash for missing values', () => {
    expect(pct(0.784)).toBe('78%');
    expect(pct(0.784, 1)).toBe('78.4%');
    expect(pct(null)).toBe('—');
    expect(signedPct(0.3)).toBe('+30 pts');
    expect(signedPct(-0.1)).toBe('-10 pts');
    expect(signedPct(undefined)).toBe('—');
  });
  it('only lets http(s) links through', () => {
    expect(safeHref('https://dharmalekha.info/texts/x')).toBe('https://dharmalekha.info/texts/x');
    expect(safeHref('javascript:alert(1)')).toBeUndefined();
    expect(safeHref('data:text/html,hi')).toBeUndefined();
    expect(safeHref('not a url')).toBeUndefined();
  });
  it('encodes SVG into a data URL for <img>', () => {
    const url = svgDataUrl('<svg><script>x</script></svg>');
    expect(url.startsWith('data:image/svg+xml')).toBe(true);
    expect(url).not.toContain('<script>');
  });
});
