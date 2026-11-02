/** Item banks built by scripts/build_practice.py from the TRAIN split (see that script's docstring). */

export type BankKind = 'letters' | 'words' | 'gaps' | 'formulas';
export type SessionKind = BankKind | 'trial' | 'guided';
export type Level = 1 | 2 | 3;

/** Tamil script and its ISO-15919 form, always shown together. */
export interface Bi {
  ta: string;
  iso: string;
}

export interface Option {
  ta: string;
  iso?: string;
  /** Fill the gap: the whole word the fill completes (Tamil `ta` shows that word). */
  word_iso?: string;
  /** Spot the formula, meaning mode: an English gloss (`ta` is the Tamil gloss). */
  en?: string;
  key?: string;
}

export interface Source {
  inscription_id: string;
  title: string;
  url: string;
  line_n?: string;
}

interface Base {
  id: string;
  level: Level;
  options: Option[];
  answer: number;
  why_en: string;
  why_ta: string;
  src?: Source;
}

export interface LetterItem extends Base {
  kind: 'letters';
  era: 'brahmi' | 'grantha' | 'vatteluttu';
  /** Unicode text, or `vatteluttu:<iso>` for a design-system drawing. */
  glyph: string;
  freq: number;
}

export interface WordItem extends Base {
  kind: 'words';
  dir: 'iso2ta' | 'ta2iso' | 'chola2modern';
  prompt: Bi;
}

export interface GapItem extends Base {
  kind: 'gaps';
  gap_chars: number;
  masked: Bi;
  restored: Bi;
  hard: boolean;
}

export interface FormulaItem extends Base {
  kind: 'formulas';
  mode: 'meaning' | 'spot';
  formula: string;
  line: { before: Bi; match: Bi; after: Bi };
  gloss: { en: string; ta: string };
}

export type Item = LetterItem | WordItem | GapItem | FormulaItem;

export interface BankMeta {
  built_by: string;
  seed: number;
  split: 'train';
  credit: string;
  ta_review: string;
}

export interface WorkedExample {
  meta: BankMeta;
  sample_id: string;
  inscription_id: string;
  split: 'train';
  title_en: string;
  title_ta: string;
  place_en: string;
  place_ta: string;
  why_en: string;
  why_ta: string;
  url: string;
  licence: string;
  recorded_on: string;
  left: Bi;
  right: Bi;
  gap_chars: number;
  decision: string;
  candidates: { iso: string; ta: string; confidence: number; model: string; sources: string[] }[];
  threshold: number | null;
  word: { iso: string; ta: string; en: string; ta_meaning: string };
}
