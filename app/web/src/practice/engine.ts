/**
 * The instant practice engine: seeded session building, answer checking, scoring and the timed trial mix.
 * Pure functions, no I/O (progress storage lives in ./progress, bank loading in ./banks).
 */
import type { BankKind, Item, Level } from './types';

export const SESSION_LENGTH = 10;
export const TRIAL_LENGTH = 10;
export const TRIAL_SECONDS = 20;

/** mulberry32: a small, fast, deterministic PRNG in [0, 1). */
export function rng(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function shuffled<T>(xs: readonly T[], seed: number): T[] {
  const out = [...xs];
  const r = rng(seed);
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(r() * (i + 1));
    [out[i], out[j]] = [out[j]!, out[i]!];
  }
  return out;
}

export function newSeed(): number {
  return Math.floor(Math.random() * 2 ** 31);
}

/** `n` items of one level, in a seeded order. Items the learner saw recently go last, so a repeat comes late. */
export function buildSession(items: readonly Item[], level: Level, seed: number, n = SESSION_LENGTH, recent: ReadonlySet<string> = new Set()): Item[] {
  const pool = shuffled(
    items.filter((i) => i.level === level),
    seed,
  );
  const fresh = pool.filter((i) => !recent.has(i.id));
  const seen = pool.filter((i) => recent.has(i.id));
  return [...fresh, ...seen].slice(0, n);
}

/** The timed trial: TRIAL_LENGTH items mixed over the four banks, levels 1 and 2, no two in a row from one bank. */
export function buildTrial(banks: Record<BankKind, readonly Item[]>, seed: number, n = TRIAL_LENGTH): Item[] {
  const kinds: BankKind[] = shuffled(['letters', 'words', 'gaps', 'formulas'] as BankKind[], seed);
  const pools = Object.fromEntries(
    kinds.map((k, i) => [k, shuffled(banks[k].filter((it) => it.level <= 2), seed + i + 1)]),
  ) as Record<BankKind, Item[]>;
  const out: Item[] = [];
  for (let i = 0; out.length < n && i < n * 4; i++) {
    const k = kinds[i % kinds.length]!;
    const next = pools[k].shift();
    if (next) out.push(next);
  }
  return out;
}

export function isRight(item: Item, choice: number | null): boolean {
  return choice !== null && choice === item.answer;
}

export interface Answer {
  id: string;
  kind: Item['kind'];
  level: Level;
  choice: number | null; // null: the clock ran out
  right: boolean;
  ms?: number;
}

export interface Score {
  right: number;
  total: number;
  /** 0..1 */
  ratio: number;
  timedOut: number;
  ms: number;
}

export function score(answers: readonly Answer[]): Score {
  const right = answers.filter((a) => a.right).length;
  const total = answers.length;
  return {
    right,
    total,
    ratio: total ? right / total : 0,
    timedOut: answers.filter((a) => a.choice === null).length,
    ms: answers.reduce((s, a) => s + (a.ms ?? 0), 0),
  };
}

/** A trial result beats another when it has more right answers, or as many in less time. */
export function betterTrial(a: { right: number; ms: number }, b: { right: number; ms: number } | null): boolean {
  if (!b) return true;
  return a.right > b.right || (a.right === b.right && a.ms < b.ms);
}

/** Problems with a bank, for tests and a dev-time guard: every item must be answerable and unambiguous. */
export function bankProblems(items: readonly Item[]): string[] {
  const problems: string[] = [];
  const ids = new Set<string>();
  for (const it of items) {
    if (ids.has(it.id)) problems.push(`${it.id}: duplicate id`);
    ids.add(it.id);
    if (it.options.length !== 4) problems.push(`${it.id}: ${it.options.length} options`);
    if (!Number.isInteger(it.answer) || it.answer < 0 || it.answer >= it.options.length) problems.push(`${it.id}: answer out of range`);
    const shown = it.options.map((o) => `${o.ta}|${o.iso ?? o.en ?? ''}`);
    if (new Set(shown).size !== shown.length) problems.push(`${it.id}: duplicate options`);
    if (!it.why_en || !it.why_ta) problems.push(`${it.id}: missing explanation`);
    if (![1, 2, 3].includes(it.level)) problems.push(`${it.id}: bad level`);
    if (it.kind !== 'letters' && !it.src?.inscription_id) problems.push(`${it.id}: no source`);
  }
  return problems;
}

/** Fill `{name}` placeholders. */
export function fmt(s: string, vars: Record<string, string | number>): string {
  return s.replace(/\{(\w+)\}/g, (m, k: string) => (k in vars ? String(vars[k]) : m));
}

export function pctText(ratio: number): string {
  return `${Math.round(ratio * 100)}%`;
}
