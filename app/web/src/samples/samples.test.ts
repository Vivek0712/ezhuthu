import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join, relative, resolve, sep } from 'node:path';
import { describe, expect, it } from 'vitest';
import { countGaps } from '../lib/gaps';
import { isLevel } from '../lib/levels';
import { ERAS, learnHref, loadSamples, restoreHref, SAMPLE_IMAGES, sampleById, sampleByInscription } from '.';
import { SAMPLES } from './data';

const REPO = resolve(__dirname, '../../../..');
const jsonl = (name: string) =>
  readFileSync(resolve(REPO, 'benchmark', name), 'utf8')
    .split('\n')
    .filter((l) => l.trim())
    .map((l) => JSON.parse(l) as Record<string, unknown>);

describe('try-it samples', () => {
  it('never come from a val or test inscription (benchmark leakage rule)', () => {
    const split = new Map(jsonl('inscriptions.jsonl').map((r) => [r.id as string, r.split as string]));
    const heldOut = new Set<string>();
    for (const [id, s] of split) if (s !== 'train') heldOut.add(id);
    for (const f of ['items.val.jsonl', 'items.test.jsonl', 'items.test-hard.jsonl', 'items.test-age.jsonl'])
      for (const r of jsonl(f)) heldOut.add(r.inscription_id as string);
    expect(heldOut.size).toBeGreaterThan(200);
    for (const s of SAMPLES) {
      expect(split.get(s.inscription_id), s.id).toBe('train');
      expect(heldOut.has(s.inscription_id), s.id).toBe(false);
    }
    for (const im of SAMPLE_IMAGES) expect(heldOut.has(im.inscription_id), im.id).toBe(false);
  });

  it('are 10 to 14 passages across at least four periods, each with real gaps and a DHARMA credit', () => {
    expect(SAMPLES.length).toBeGreaterThanOrEqual(10);
    expect(SAMPLES.length).toBeLessThanOrEqual(14);
    expect(new Set(SAMPLES.map((s) => s.era)).size).toBeGreaterThanOrEqual(4);
    expect(new Set(SAMPLES.map((s) => s.id)).size).toBe(SAMPLES.length);
    for (const s of SAMPLES) {
      expect(ERAS).toContain(s.era);
      expect(isLevel(s.learn_level)).toBe(true);
      expect(countGaps(s.text_iso)).toBe(s.gaps);
      expect(countGaps(s.text_tamil)).toBe(s.gaps);
      expect(s.gaps).toBeGreaterThan(0);
      expect(s.gaps).toBeLessThanOrEqual(5); // the API's per-request limit
      expect(s.blank_ids).toHaveLength(s.gaps);
      expect(s.licence).toBe('CC BY-SA 4.0');
      expect(new URL(s.dharma_url).hostname).toBe('dharmalekha.info');
      expect(s.title_ta).toMatch(/[஀-௿]/);
      expect(s.why_ta).toMatch(/[஀-௿]/);
    }
  });

  it('link to Restore and Learn with the right parameters', () => {
    const s = SAMPLES[0]!;
    expect(restoreHref(s)).toBe(`/restore?sample=${s.id}`);
    const u = new URL(learnHref(s), 'http://x');
    expect(u.pathname).toBe('/learn');
    expect(u.searchParams.get('inscription')).toBe(s.inscription_id);
    expect(u.searchParams.get('level')).toBe(s.learn_level);
    expect(sampleById(SAMPLES, s.id)).toBe(s);
    expect(sampleByInscription(SAMPLES, s.inscription_id)).toBe(s);
    expect(sampleById(SAMPLES, 'nope')).toBeUndefined();
    expect(sampleById(null, s.id)).toBeUndefined();
  });

  it('ships every sample image under public/ with attribution', () => {
    const attribution = readFileSync(resolve(__dirname, '../../public/samples/ATTRIBUTION.md'), 'utf8');
    expect(SAMPLE_IMAGES.length).toBeGreaterThanOrEqual(3);
    for (const im of SAMPLE_IMAGES) {
      expect(existsSync(resolve(__dirname, '../../public', im.file)), im.file).toBe(true);
      expect(attribution).toContain(im.file.split('/').pop()!);
      expect(sampleById(SAMPLES, im.sample)).toBeDefined();
      expect(im.expected_text).toBe(im.lines.join('\n'));
    }
  });

  it('load on demand: loadSamples() resolves to the same passages, once', async () => {
    const a = await loadSamples();
    expect(a).toBe(SAMPLES);
    expect(await loadSamples()).toBe(a);
  });

  it('stay out of the main bundle: only data.ts, tests and the mock API import the JSON statically', () => {
    const src = resolve(__dirname, '..');
    const offenders: string[] = [];
    const walk = (dir: string) => {
      for (const e of readdirSync(dir, { withFileTypes: true })) {
        const f = resolve(dir, e.name);
        if (e.isDirectory()) walk(f);
        else if (/\.tsx?$/.test(e.name) && !/\.test\.tsx?$/.test(e.name)) {
          const rel = relative(src, f);
          if (rel === join('samples', 'data.ts') || rel.startsWith(`mocks${sep}`)) continue;
          const code = readFileSync(f, 'utf8');
          if (/^import[^;]*from\s+'[^']*(samples\.json|samples\/data|\.\/data)'/m.test(code)) offenders.push(rel);
        }
      }
    };
    walk(src);
    expect(offenders).toEqual([]);
  });
});
