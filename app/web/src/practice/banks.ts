/**
 * Lazy loaders for the item banks: each bank is its own chunk, fetched when a session needs it, so the home page
 * stays light. The home mini-drill uses the small `try.json`, bundled with the page.
 */
import { useEffect, useState } from 'react';
import summary from './banks/summary.json';
import type { BankKind, FormulaItem, GapItem, Item, LetterItem, WordItem } from './types';

type Raw<T> = Omit<T, 'kind'>;

const loaders: Record<BankKind, () => Promise<Item[]>> = {
  letters: () => import('./banks/letters.json').then((m) => (m.default.items as Raw<LetterItem>[]).map((i) => ({ ...i, kind: 'letters' as const }))),
  words: () => import('./banks/words.json').then((m) => (m.default.items as Raw<WordItem>[]).map((i) => ({ ...i, kind: 'words' as const }))),
  gaps: () => import('./banks/gaps.json').then((m) => (m.default.items as Raw<GapItem>[]).map((i) => ({ ...i, kind: 'gaps' as const }))),
  formulas: () => import('./banks/formulas.json').then((m) => (m.default.items as Raw<FormulaItem>[]).map((i) => ({ ...i, kind: 'formulas' as const }))),
};

const cache = new Map<BankKind, Promise<Item[]>>();

export function loadBank(kind: BankKind): Promise<Item[]> {
  let p = cache.get(kind);
  if (!p) {
    p = loaders[kind]();
    cache.set(kind, p);
    p.catch(() => cache.delete(kind)); // a failed chunk load can be retried
  }
  return p;
}

export async function loadAllBanks(): Promise<Record<BankKind, Item[]>> {
  const [letters, words, gaps, formulas] = await Promise.all((['letters', 'words', 'gaps', 'formulas'] as const).map(loadBank));
  return { letters: letters!, words: words!, gaps: gaps!, formulas: formulas! };
}

export function useBank(kind: BankKind | null): { items: Item[] | null; error: unknown } {
  const [state, setState] = useState<{ kind: BankKind | null; items: Item[] | null; error: unknown }>({ kind, items: null, error: null });
  useEffect(() => {
    if (!kind) return;
    let live = true;
    loadBank(kind).then(
      (items) => live && setState({ kind, items, error: null }),
      (error: unknown) => live && setState({ kind, items: null, error }),
    );
    return () => {
      live = false;
    };
  }, [kind]);
  return state.kind === kind ? { items: state.items, error: state.error } : { items: null, error: null };
}

/** Bank sizes per level (for the hub cards), written by the build script next to the banks. */
export const BANK_SIZES = summary.counts as Record<BankKind, Record<'1' | '2' | '3', number>>;
