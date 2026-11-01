import { describe, expect, it } from 'vitest';
import { countGaps, gapContext, parseGaps } from './gaps';

describe('parseGaps', () => {
  it('splits text and both gap marker forms in order', () => {
    expect(parseGaps('kōp[?4]kēcari yāṇṭu [?] āvatu')).toEqual([
      { kind: 'text', text: 'kōp' },
      { kind: 'gap', index: 0, chars: 4, raw: '[?4]' },
      { kind: 'text', text: 'kēcari yāṇṭu ' },
      { kind: 'gap', index: 1, chars: null, raw: '[?]' },
      { kind: 'text', text: ' āvatu' },
    ]);
  });
  it('handles leading, trailing and adjacent gaps', () => {
    expect(parseGaps('[?2][?]x').map((s) => s.kind)).toEqual(['gap', 'gap', 'text']);
    expect(countGaps('no gaps here')).toBe(0);
    expect(countGaps('ஸ்ரீ கோ[?4]கேசரி')).toBe(1);
  });
  it('treats [?0] as unknown length and ignores malformed markers', () => {
    expect(parseGaps('a[?0]b')[1]).toMatchObject({ kind: 'gap', chars: null });
    expect(countGaps('a[?x]b [? ] [?')).toBe(0);
  });
});

describe('gapContext', () => {
  it('returns trimmed left/right context around a gap', () => {
    expect(gapContext('abcdef[?3]ghijkl', 0, 3)).toEqual({ left: 'def', right: 'ghi' });
  });
  it('keeps other gap markers literal in context and handles a missing index', () => {
    expect(gapContext('x[?]y[?2]z', 1)).toEqual({ left: 'x[?]y', right: 'z' });
    expect(gapContext('x[?]y', 5)).toEqual({ left: '', right: '' });
  });
});
