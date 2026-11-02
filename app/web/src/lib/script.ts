/**
 * ISO-15919 (DHARMA flavour) to Tamil script, in the browser. A port of the display path of
 * src/ezhuthu/corpus/script.py (iso_to_tamil_display), which also builds the try-it samples' text_tamil
 * (scripts/build_samples.py); script.test.ts checks the two agree on every sample.
 *
 * Differences from the Python module, both on purpose: numerals stay Western digits (design/ux/UX.md section 8,
 * as the samples do), and the converter keeps track of which ISO letters each Tamil letter came from, so a
 * restored line can highlight exactly the letters the system filled.
 *
 * Gap markers ([?] and [?N]) pass through untouched.
 */
import { parseGaps } from './gaps';

const CONSONANTS: Record<string, string> = {
  kh: 'க', gh: 'க', ch: 'ச', jh: 'ஜ', ṭh: 'ட', ḍh: 'ட', th: 'த', dh: 'த', ph: 'ப', bh: 'ப',
  k: 'க', g: 'க', ṅ: 'ங', c: 'ச', j: 'ஜ', ñ: 'ஞ', ṭ: 'ட', ḍ: 'ட', ṇ: 'ண',
  t: 'த', d: 'த', n: 'ந', p: 'ப', b: 'ப', m: 'ம', y: 'ய', r: 'ர', l: 'ல',
  v: 'வ', ś: 'ஶ', ṣ: 'ஷ', s: 'ஸ', h: 'ஹ', ḷ: 'ள', ḻ: 'ழ', ṟ: 'ற', ṉ: 'ன',
  f: 'ஃப', z: 'ஃஜ',
};
// vowel -> [independent letter, vowel sign]
const VOWELS: Record<string, [string, string]> = {
  ai: ['ஐ', 'ை'], au: ['ஔ', 'ௌ'],
  'r̥̄': ['ரூ', '்ரூ'], 'r̥': ['ரு', '்ரு'], 'l̥̄': ['லூ', '்லூ'], 'l̥': ['லு', '்லு'],
  ṝ: ['ரூ', '்ரூ'], ṛ: ['ரு', '்ரு'],
  ā: ['ஆ', 'ா'], ī: ['ஈ', 'ீ'], ū: ['ஊ', 'ூ'], ē: ['ஏ', 'ே'], ō: ['ஓ', 'ோ'],
  a: ['அ', ''], i: ['இ', 'ி'], u: ['உ', 'ு'], e: ['எ', 'ெ'], o: ['ஒ', 'ொ'],
  ï: ['இ', 'ி'], ü: ['உ', 'ு'],
};
const SIGNS: Record<string, string> = { ṃ: 'ம்', ṁ: 'ம்', ḥ: 'ஃ', 'm̐': 'ம்', ḵ: 'ஃ' };
const VIRAMA = '்';
const KEYS = [...Object.keys(CONSONANTS), ...Object.keys(VOWELS), ...Object.keys(SIGNS)]
  .map((k) => k.normalize('NFC'))
  .sort((a, b) => b.length - a.length);
const KEY_CHARS = new Set([...KEYS.join('')]);
const EDITORIAL = /[=‡⌈⌉⌊⌋_"“”„‘`´�]/g;
const NOTE_BRACKET = /\[(?!\?\d*\])[^\]\n]*[A-Za-z]{3,}[^\]\n]*\]/g;
const NOTE_BRACE = /\{[^}\n]*\}/g;

type Token = { kind: 'C' | 'V' | 'S' | 'O'; iso: string; independent: boolean; from: number; to: number };

function tokenize(text: string): Token[] {
  const out: Token[] = [];
  let i = 0;
  while (i < text.length) {
    const ch = text[i]!;
    const upper = /\p{Lu}/u.test(ch);
    let rest = text.slice(i, i + 4);
    if (upper) rest = rest.normalize('NFD').toLowerCase().normalize('NFC');
    const key = KEYS.find((k) => rest.startsWith(k));
    if (key) {
      const kind = key in VOWELS ? 'V' : key in CONSONANTS ? 'C' : 'S';
      out.push({ kind, iso: key, independent: upper && kind === 'V', from: i, to: i + key.length });
      i += key.length;
    } else {
      out.push({ kind: 'O', iso: ch, independent: false, from: i, to: i + 1 });
      i += 1;
    }
  }
  return out;
}

/** One written Tamil unit (a letter with its sign or puḷḷi, or one other character) and the ISO span it came from. */
export interface Unit {
  ta: string;
  from: number;
  to: number;
}

function chunkUnits(text: string, offset: number): Unit[] {
  const units: Unit[] = [];
  let prevConsonant = false;
  const last = () => units[units.length - 1]!;
  for (const tok of tokenize(text)) {
    const from = tok.from + offset;
    const to = tok.to + offset;
    if (tok.kind === 'C') {
      if (prevConsonant) last().ta += VIRAMA;
      units.push({ ta: CONSONANTS[tok.iso]!, from, to });
      prevConsonant = true;
    } else if (tok.kind === 'V') {
      const [indep, sign] = VOWELS[tok.iso]!;
      if (prevConsonant && !tok.independent) {
        last().ta += sign;
        last().to = to;
      } else {
        if (prevConsonant) last().ta += VIRAMA;
        units.push({ ta: indep, from, to });
      }
      prevConsonant = false;
    } else if (tok.kind === 'S') {
      if (prevConsonant) last().ta += VIRAMA;
      units.push({ ta: SIGNS[tok.iso]!, from, to });
      prevConsonant = false;
    } else {
      const ch = tok.iso;
      if (ch === '-' || ch === '·') continue; // hyphens are editorial word splits; '·' is an engraved puḷḷi
      if (prevConsonant) last().ta += VIRAMA;
      prevConsonant = false;
      if (ch === '’' || ch === "'") continue;
      units.push({ ta: ch, from, to });
    }
  }
  if (prevConsonant) last().ta += VIRAMA;
  return units;
}

function foldStray(text: string): string {
  return [...text]
    .map((ch) => {
      if (!/\p{L}/u.test(ch) || (ch >= '஀' && ch <= '௿') || KEY_CHARS.has(ch.toLowerCase())) return ch;
      const base = ch.normalize('NFD')[0]!;
      return KEY_CHARS.has(base.toLowerCase()) ? base : '';
    })
    .join('');
}

/** The cleaning iso_to_tamil_display does before converting (editors' notes, editorial marks, stray letters). */
function clean(text: string): string {
  return foldStray(text.replace(NOTE_BRACE, '').replace(NOTE_BRACKET, '…').normalize('NFC')).replace(EDITORIAL, '');
}

/** A piece of a line to convert: plain passage text, a letter span the system filled, or a gap still open. */
export type IsoPart = { kind: 'text'; iso: string } | { kind: 'fill'; iso: string; gap: number } | { kind: 'gap'; raw: string; gap: number };
export type TamilPiece = { kind: 'text'; ta: string } | { kind: 'fill'; ta: string; gap: number } | { kind: 'gap'; raw: string; gap: number };

/**
 * Convert a line given as parts to Tamil script. A Tamil letter built partly from filled ISO letters counts as
 * filled (e.g. ṟ + filled u = று), so highlights never split a letter.
 */
export function isoPartsToTamil(parts: IsoPart[]): TamilPiece[] {
  // One string, so letters join across part boundaries exactly as in the whole line; gaps split it into chunks.
  let s = '';
  const fills: { from: number; to: number; gap: number }[] = [];
  const gaps: { at: number; raw: string; gap: number }[] = [];
  for (const p of parts) {
    if (p.kind === 'gap') {
      gaps.push({ at: s.length, raw: p.raw, gap: p.gap });
      s += '\u0000';
    } else {
      const iso = clean(p.iso);
      if (p.kind === 'fill') fills.push({ from: s.length, to: s.length + iso.length, gap: p.gap });
      s += iso;
    }
  }
  type U = Unit & { gap?: { raw: string; gap: number } };
  const units: U[] = [];
  let pos = 0;
  for (const g of [...gaps, { at: s.length, raw: '', gap: -1 }]) {
    units.push(...chunkUnits(s.slice(pos, g.at), pos));
    if (g.gap >= 0) units.push({ ta: g.raw, from: g.at, to: g.at + 1, gap: g });
    pos = g.at + 1;
  }
  // Collapse runs of spaces and trim each row, as iso_to_tamil_display does.
  const ws = (u: U | undefined) => !!u && !u.gap && (u.ta === ' ' || u.ta === '\t');
  const kept: U[] = [];
  units.forEach((u, i) => {
    if (!ws(u)) return void kept.push(u);
    const prev = kept[kept.length - 1];
    let j = i + 1;
    while (ws(units[j])) j++;
    const next = units[j];
    if (!prev || prev.ta === '\n' || ws(prev) || !next || next.ta === '\n') return;
    kept.push(units[i + 1] && ws(units[i + 1]) ? { ...u, ta: ' ' } : u);
  });
  const out: TamilPiece[] = [];
  for (const u of kept) {
    if (u.gap) {
      out.push({ kind: 'gap', raw: u.gap.raw, gap: u.gap.gap });
      continue;
    }
    const f = fills.find((x) => u.from < x.to && u.to > x.from);
    const prev = out[out.length - 1];
    if (f) {
      if (prev?.kind === 'fill' && prev.gap === f.gap) prev.ta += u.ta;
      else out.push({ kind: 'fill', ta: u.ta, gap: f.gap });
    } else if (prev?.kind === 'text') prev.ta += u.ta;
    else out.push({ kind: 'text', ta: u.ta });
  }
  return out;
}

/** ISO-15919 text (with any gap markers) to Tamil script for display. */
export function isoToTamil(text: string): string {
  const parts: IsoPart[] = parseGaps(text).map((s) => (s.kind === 'text' ? { kind: 'text', iso: s.text } : { kind: 'gap', raw: s.raw, gap: s.index }));
  return isoPartsToTamil(parts)
    .map((p) => (p.kind === 'gap' ? p.raw : p.ta))
    .join('');
}

/** True when the text is written mainly in Tamil script (used to pick the input's script automatically). */
export function looksTamil(text: string): boolean {
  const ta = (text.match(/[஀-௿]/g) ?? []).length;
  const latin = (text.match(/\p{Script=Latin}/gu) ?? []).length;
  return ta > 0 && ta >= latin;
}
