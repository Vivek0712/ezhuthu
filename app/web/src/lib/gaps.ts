/** Parse gap markers from contracts/restore-api.md: `[?]` unknown length, `[?N]` about N Tamil letters (not ISO characters). */
export type Segment = { kind: 'text'; text: string } | { kind: 'gap'; index: number; chars: number | null; raw: string };

const GAP_RE = /\[\?(\d{1,3})?\]/g;

export function parseGaps(text: string): Segment[] {
  const out: Segment[] = [];
  let last = 0;
  let index = 0;
  for (const m of text.matchAll(GAP_RE)) {
    const at = m.index ?? 0;
    if (at > last) out.push({ kind: 'text', text: text.slice(last, at) });
    const n = m[1] ? Number.parseInt(m[1], 10) : null;
    out.push({ kind: 'gap', index: index++, chars: n && n > 0 ? n : null, raw: m[0] });
    last = at + m[0].length;
  }
  if (last < text.length) out.push({ kind: 'text', text: text.slice(last) });
  return out;
}

export function countGaps(text: string): number {
  return parseGaps(text).filter((s) => s.kind === 'gap').length;
}

/** Text immediately left/right of gap `index`, trimmed to `width` chars, for review context. */
export function gapContext(text: string, index: number, width = 24): { left: string; right: string } {
  const segs = parseGaps(text);
  const pos = segs.findIndex((s) => s.kind === 'gap' && s.index === index);
  if (pos < 0) return { left: '', right: '' };
  const flat = (xs: Segment[]) => xs.map((s) => (s.kind === 'text' ? s.text : s.raw)).join('');
  const left = flat(segs.slice(0, pos));
  const right = flat(segs.slice(pos + 1));
  return { left: left.slice(-width), right: right.slice(0, width) };
}
