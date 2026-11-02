import { describe, expect, it } from 'vitest';
import recordedJson from '../samples/recorded-restores.json';
import { SAMPLES } from '../samples/data';
import { isoPartsToTamil, isoToTamil, looksTamil } from './script';

type Rec = { samples: Record<string, { response: { gaps: { candidates: { text: string; text_tamil: string }[] }[] } }> };

describe('isoToTamil (port of ezhuthu.corpus.script.iso_to_tamil_display)', () => {
  it('gives every sample exactly the Tamil text the corpus converter gave it, gap markers included', () => {
    for (const s of SAMPLES) expect(isoToTamil(s.text_iso), s.id).toBe(s.text_tamil);
  });
  it('agrees with the server on edition readings and recorded candidates (the server keeps hyphens in candidates)', () => {
    for (const s of SAMPLES) if (s.edition_reading) expect(isoToTamil(s.edition_reading.text_iso)).toBe(s.edition_reading.text_tamil);
    const rec = recordedJson as unknown as Rec;
    for (const r of Object.values(rec.samples))
      for (const g of r.response.gaps) for (const c of g.candidates) if (!c.text.includes('-')) expect(isoToTamil(c.text).trim(), c.text).toBe(c.text_tamil.trim());
  });
  it('handles the DHARMA conventions: upper-case independent vowels, hyphens, puḷḷi', () => {
    expect(isoToTamil('vari-p-pāṭum')).toBe('வரிப்பாடும்');
    expect(isoToTamil('Ūr iṭu')).toBe('ஊர் இடு');
    expect(isoToTamil('kōp[?4]kēcari')).toBe('கோப்[?4]கேசரி');
  });
});

describe('isoPartsToTamil', () => {
  it('marks the Tamil letters made from a fill, without splitting a letter', () => {
    expect(isoPartsToTamil([{ kind: 'text', iso: 'vari-' }, { kind: 'fill', iso: 'p', gap: 0 }, { kind: 'text', iso: '-pāṭum' }])).toEqual([
      { kind: 'text', ta: 'வரி' },
      { kind: 'fill', ta: 'ப்', gap: 0 },
      { kind: 'text', ta: 'பாடும்' },
    ]);
    // ṟ + filled u is one letter, று: the whole letter is marked.
    expect(isoPartsToTamil([{ kind: 'text', iso: 'naḷḷāṟ' }, { kind: 'fill', iso: 'u', gap: 0 }])).toEqual([
      { kind: 'text', ta: 'நள்ளா' },
      { kind: 'fill', ta: 'று', gap: 0 },
    ]);
    expect(isoPartsToTamil([{ kind: 'text', iso: 'yāṇṭu ' }, { kind: 'gap', raw: '[?]', gap: 1 }, { kind: 'text', iso: ' āvatu' }])).toEqual([
      { kind: 'text', ta: 'யாண்டு ' },
      { kind: 'gap', raw: '[?]', gap: 1 },
      { kind: 'text', ta: ' ஆவது' },
    ]);
  });
});

describe('looksTamil', () => {
  it('tells Tamil script from ISO-15919', () => {
    expect(looksTamil('கோப்[?4]கேசரி')).toBe(true);
    expect(looksTamil('kōp[?4]kēcari')).toBe(false);
    expect(looksTamil('')).toBe(false);
  });
});
