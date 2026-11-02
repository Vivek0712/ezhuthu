import { describe, expect, it } from 'vitest';
import { isDharmaUrl, pct, plural, safeHref, signedPct, svgDataUrl } from './format';

describe('format helpers', () => {
  it('formats percentages and gains, with a dash for missing values', () => {
    expect(pct(0.784)).toBe('78%');
    expect(pct(0.784, 1)).toBe('78.4%');
    expect(pct(null)).toBe('—');
    expect(signedPct(0.3)).toBe('+30 pts');
    expect(signedPct(-0.1)).toBe('-10 pts');
    expect(signedPct(undefined)).toBe('—');
  });
  it('recognises DHARMA edition links only (dharmalekha.info, github.com/erc-dharma)', () => {
    expect(isDharmaUrl('https://dharmalekha.info')).toBe(true);
    expect(isDharmaUrl('https://www.dharmalekha.info/texts/INSPallava00012')).toBe(true);
    expect(isDharmaUrl('https://github.com/erc-dharma/tfa-pandya-epigraphy/blob/abc/xml/DHARMA_INSPandya00001.xml')).toBe(true);
    expect(isDharmaUrl('https://raw.githubusercontent.com/erc-dharma/tfa-sii-epigraphy/main/x.xml')).toBe(true);
    expect(isDharmaUrl('https://github.com/someone-else/erc-dharma-fork')).toBe(false);
    expect(isDharmaUrl('https://dharmalekha.info.evil.example/')).toBe(false);
    expect(isDharmaUrl('https://example.org/inscription/1')).toBe(false);
    expect(isDharmaUrl('javascript:alert(1)')).toBe(false);
    expect(isDharmaUrl(null)).toBe(false);
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

  it('picks the singular key only for exactly one', () => {
    expect(plural(1, 'gap', 'gaps')).toBe('gap');
    for (const n of [0, 2, 5]) expect(plural(n, 'gap', 'gaps')).toBe('gaps');
  });
});
