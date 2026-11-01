import { describe, expect, it } from 'vitest';
import { validateJsonl, validateRecord } from './jsonl';

const good = {
  id: 'DHARMA_X:1:0',
  inscription_id: 'DHARMA_X',
  collection: 'tfa-pallava-epigraphy',
  dynasty: 'Pallava',
  age_set: true,
  split: 'test',
  line_n: '1',
  left: 'kō vicaiya ',
  right: 'parumaṟku',
  target: 'nantivikkirama',
  gap_chars: 14,
  hard: false,
  source_url: 'https://dharmalekha.info/texts/DHARMA_X',
};

describe('benchmark JSONL validation (driven by contracts/benchmark-item.schema.json)', () => {
  it('accepts a contract-valid record', () => {
    expect(validateRecord(good)).toEqual([]);
  });
  it('reports missing required keys, wrong types and enum violations', () => {
    const missing: Record<string, unknown> = { ...good };
    delete missing.target;
    expect(validateRecord(missing)).toContain('missing "target"');
    expect(validateRecord({ ...good, gap_chars: 2.5 }).join()).toMatch(/gap_chars/);
    expect(validateRecord({ ...good, split: 'dev' }).join()).toMatch(/split/);
    expect(validateRecord({ ...good, gap_chars: 0 }).join()).toMatch(/>= 1/);
    expect(validateRecord({ ...good, dynasty: null })).toEqual([]);
    expect(validateRecord([1])).toEqual(['not a JSON object']);
  });
  it('validates line by line, skips blanks and reports 1-based line numbers', () => {
    const text = [JSON.stringify(good), '', '{nope', JSON.stringify({ ...good, hard: 'no' })].join('\n');
    const r = validateJsonl(text);
    expect(r.valid).toBe(1);
    expect(r.errors.map((e) => e.line)).toEqual([3, 4]);
  });
});
