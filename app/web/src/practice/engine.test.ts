import { readFileSync } from 'node:fs';
import * as path from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import formulas from './banks/formulas.json';
import gaps from './banks/gaps.json';
import letters from './banks/letters.json';
import summary from './banks/summary.json';
import tryBank from './banks/try.json';
import words from './banks/words.json';
import worked from './banks/worked-example.json';
import { loadAllBanks } from './banks';
import { bankProblems, betterTrial, buildSession, buildTrial, fmt, isRight, rng, score, shuffled, SESSION_LENGTH, TRIAL_LENGTH, type Answer } from './engine';
import { _resetProgressMemory, clearProgress, loadProgress, PROGRESS_KEY, recordAnswer, recordSession, recordTrial, storageAvailable } from './progress';
import type { BankKind, Item } from './types';

const repo = (p: string) => path.resolve(process.cwd(), '..', '..', p);
const jsonl = (p: string) =>
  readFileSync(repo(p), 'utf8')
    .split('\n')
    .filter(Boolean)
    .map((l) => JSON.parse(l) as Record<string, unknown>);

const RAW = { letters, words, gaps, formulas } as const;

describe('seeded randomness', () => {
  it('is deterministic for a seed and differs between seeds', () => {
    const a = rng(7);
    const b = rng(7);
    const xs = Array.from({ length: 5 }, () => a());
    expect(Array.from({ length: 5 }, () => b())).toEqual(xs);
    expect(xs.every((x) => x >= 0 && x < 1)).toBe(true);
    expect(shuffled([1, 2, 3, 4, 5, 6], 1)).not.toEqual(shuffled([1, 2, 3, 4, 5, 6], 2));
    expect([...shuffled([1, 2, 3, 4, 5, 6], 3)].sort()).toEqual([1, 2, 3, 4, 5, 6]);
  });
});

describe('practice engine', () => {
  let banks: Record<BankKind, Item[]>;
  beforeEach(async () => {
    banks = await loadAllBanks();
  });

  it('builds a session of ten items of one level, same seed same order', () => {
    const s1 = buildSession(banks.words, 2, 42);
    expect(s1).toHaveLength(SESSION_LENGTH);
    expect(s1.every((i) => i.level === 2)).toBe(true);
    expect(buildSession(banks.words, 2, 42).map((i) => i.id)).toEqual(s1.map((i) => i.id));
    expect(new Set(s1.map((i) => i.id)).size).toBe(SESSION_LENGTH);
  });

  it('puts recently seen items last', () => {
    const first = buildSession(banks.gaps, 1, 5);
    const again = buildSession(banks.gaps, 1, 5, SESSION_LENGTH, new Set(first.map((i) => i.id)));
    expect(again.some((i) => first.some((f) => f.id === i.id))).toBe(false);
  });

  it('mixes the timed trial over all four banks, never two in a row from one bank, levels 1-2 only', () => {
    const trial = buildTrial(banks, 99);
    expect(trial).toHaveLength(TRIAL_LENGTH);
    expect(new Set(trial.map((i) => i.kind))).toEqual(new Set(['letters', 'words', 'gaps', 'formulas']));
    for (let i = 1; i < trial.length; i++) expect(trial[i]!.kind).not.toBe(trial[i - 1]!.kind);
    expect(trial.every((i) => i.level <= 2)).toBe(true);
  });

  it('scores answers, counting a timeout as not right', () => {
    const item = banks.letters[0]!;
    expect(isRight(item, item.answer)).toBe(true);
    expect(isRight(item, (item.answer + 1) % 4)).toBe(false);
    expect(isRight(item, null)).toBe(false);
    const a = (right: boolean, choice: number | null = 0, ms = 1000): Answer => ({ id: 'x', kind: 'letters', level: 1, choice, right, ms });
    const s = score([a(true), a(false), a(false, null, 20000), a(true)]);
    expect(s).toEqual({ right: 2, total: 4, ratio: 0.5, timedOut: 1, ms: 23000 });
    expect(score([]).ratio).toBe(0);
  });

  it('ranks trials by right answers, then time', () => {
    expect(betterTrial({ right: 7, ms: 90000 }, null)).toBe(true);
    expect(betterTrial({ right: 8, ms: 90000 }, { right: 7, ms: 10000 })).toBe(true);
    expect(betterTrial({ right: 7, ms: 50000 }, { right: 7, ms: 60000 })).toBe(true);
    expect(betterTrial({ right: 7, ms: 70000 }, { right: 7, ms: 60000 })).toBe(false);
  });

  it('fills placeholders', () => {
    expect(fmt('Question {i} of {n}', { i: 3, n: 10 })).toBe('Question 3 of 10');
    expect(fmt('{missing}', {})).toBe('{missing}');
  });
});

describe('item banks', () => {
  it.each(Object.keys(RAW) as BankKind[])('%s: every item is answerable, unambiguous and explained', async (kind) => {
    const items = (await loadAllBanks())[kind];
    expect(bankProblems(items)).toEqual([]);
  });

  it('holds hundreds of items, at every level, and the summary counts match', () => {
    let total = 0;
    for (const kind of Object.keys(RAW) as BankKind[]) {
      const items = RAW[kind].items as { level: number }[];
      total += items.length;
      for (const lv of [1, 2, 3]) {
        const n = items.filter((i) => i.level === lv).length;
        expect(n, `${kind} level ${lv}`).toBeGreaterThanOrEqual(SESSION_LENGTH);
        expect(summary.counts[kind][String(lv) as '1' | '2' | '3']).toBe(n);
      }
    }
    expect(total).toBeGreaterThan(1000);
  });

  it('uses TRAIN inscriptions only: no VAL or TEST inscription, item or shared stone', () => {
    const ins = jsonl('benchmark/inscriptions.jsonl') as { id: string; split: string; same_stone_as?: string[] }[];
    const held = new Set(ins.filter((r) => r.split !== 'train').map((r) => r.id));
    for (const f of ['items.val.jsonl', 'items.test.jsonl', 'items.test-hard.jsonl', 'items.test-age.jsonl'])
      for (const r of jsonl(`benchmark/${f}`)) held.add(r.inscription_id as string);
    const heldItems = new Set(
      ['items.val.jsonl', 'items.test.jsonl', 'items.test-hard.jsonl', 'items.test-age.jsonl'].flatMap((f) => jsonl(`benchmark/${f}`).map((r) => r.id as string)),
    );
    const split = new Map(ins.map((r) => [r.id, r.split]));
    const used = new Set<string>();
    for (const kind of ['words', 'gaps', 'formulas'] as const)
      for (const it of RAW[kind].items as { id: string; src: { inscription_id: string } }[]) {
        used.add(it.src.inscription_id);
        if (kind === 'gaps') expect(heldItems.has(it.id.replace(/^gap:/, '')), it.id).toBe(false);
      }
    used.add(worked.inscription_id);
    for (const id of used) {
      expect(split.get(id), id).toBe('train');
      expect(held.has(id), id).toBe(false);
    }
    expect(used.size).toBeGreaterThan(100);
    for (const b of [letters, words, gaps, formulas, tryBank, worked]) expect(b.meta.split).toBe('train');
  });

  it('credits DHARMA under CC BY-SA 4.0 and links every source to its edition', () => {
    for (const b of [words, gaps, formulas]) {
      expect(b.meta.credit).toMatch(/DHARMA.*CC BY-SA 4\.0/);
      for (const it of b.items as { src: { url: string } }[]) expect(it.src.url).toMatch(/^https:\/\/dharmalekha\.info\/texts\/DHARMA_/);
    }
    expect(Object.keys(letters.meta.licences)).toEqual(expect.arrayContaining(['brahmi', 'grantha', 'vatteluttu']));
  });

  it('shows Tamil script and the ISO form for every option that is a reading', () => {
    for (const kind of ['letters', 'words', 'gaps'] as const)
      for (const it of RAW[kind].items as { id: string; options: { ta: string; iso?: string }[] }[])
        for (const o of it.options) {
          expect(o.ta, it.id).toMatch(/[஀-௿]/);
          expect(o.iso, it.id).toBeTruthy();
        }
  });

  it('phrases gap feedback as matching the editors’ restoration, never as correct', () => {
    for (const it of gaps.items) {
      expect(it.why_en).toMatch(/editors restored/);
      expect(`${it.why_en} ${it.why_ta}`).not.toMatch(/\bcorrect\b/i);
    }
  });
});

describe('local progress', () => {
  beforeEach(() => {
    window.localStorage.clear();
    _resetProgressMemory();
  });
  afterEach(() => vi.restoreAllMocks());

  it('records answers, sessions and trials in localStorage', () => {
    recordAnswer('letters', { id: 'a', level: 1, right: true });
    recordAnswer('letters', { id: 'b', level: 2, right: false });
    recordSession('letters', 7, 10);
    recordSession('letters', 5, 10);
    const p = loadProgress();
    expect(p.kinds.letters).toMatchObject({ answered: 2, right: 1, sessions: 2, best: 0.7 });
    expect(p.kinds.letters!.byLevel[1]).toEqual({ answered: 1, right: 1 });
    expect(p.recent.slice(0, 2)).toEqual(['b', 'a']);
    expect(recordTrial(0, 10, 1000).newBest).toBe(false);
    expect(recordTrial(6, 10, 80000).newBest).toBe(true);
    expect(recordTrial(6, 10, 90000).newBest).toBe(false);
    expect(loadProgress().trial).toEqual({ runs: 3, best: { right: 6, total: 10, ms: 80000 } });
    expect(JSON.parse(window.localStorage.getItem(PROGRESS_KEY)!).v).toBe(1);
    clearProgress();
    expect(loadProgress().kinds).toEqual({});
  });

  it('keeps working in memory when storage throws', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    expect(() => recordAnswer('words', { id: 'w', level: 1, right: true })).not.toThrow();
    expect(storageAvailable()).toBe(false);
    expect(loadProgress().kinds.words?.answered).toBe(1);
  });

  it('ignores a corrupt stored value', () => {
    window.localStorage.setItem(PROGRESS_KEY, '{not json');
    expect(loadProgress()).toEqual({ v: 1, kinds: {}, trial: { runs: 0, best: null }, recent: [] });
  });
});
