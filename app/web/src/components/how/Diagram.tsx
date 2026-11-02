import { useEffect, useState } from 'react';

/** A box on a diagram. `tone` picks its colours from the design tokens (how.css). */
export interface DNode {
  id: string;
  label: string;
  sub?: string;
  tone?: 'io' | 'agent' | 'model' | 'data' | 'branch' | 'people' | 'aws';
}
export interface DEdge {
  id: string;
  from: string;
  to: string;
  kind?: 'photo' | 'text' | 'branch' | 'plain';
  dashed?: boolean;
}
export interface DLayout {
  width: number;
  height: number;
  w: number;
  h: number;
  at: Record<string, [number, number]>;
}

/** True below `px` CSS pixels wide; re-evaluated on resize. Without matchMedia (tests) it is false. */
export function useNarrow(px = 720): boolean {
  const q = `(max-width: ${px - 1}px)`;
  const [narrow, setNarrow] = useState(() => {
    try {
      return typeof window !== 'undefined' && typeof window.matchMedia === 'function' && window.matchMedia(q).matches;
    } catch {
      return false;
    }
  });
  useEffect(() => {
    if (typeof window.matchMedia !== 'function') return;
    const mql = window.matchMedia(q);
    const on = () => setNarrow(mql.matches);
    on();
    mql.addEventListener?.('change', on);
    return () => mql.removeEventListener?.('change', on);
  }, [q]);
  return narrow;
}

const TAMIL = /[஀-௿]/;

/** Greedy word wrap with a rough width estimate (Tamil letters run wider than Latin ones at the same size). */
export function wrap(text: string, maxWidth: number, fontSize: number, maxLines = 2): string[] {
  const em = TAMIL.test(text) ? 0.62 : 0.54;
  const fits = (s: string) => s.length * em * fontSize <= maxWidth;
  const lines: string[] = [];
  let cur = '';
  for (const word of text.split(/\s+/)) {
    const next = cur ? `${cur} ${word}` : word;
    if (fits(next) || !cur) cur = next;
    else {
      lines.push(cur);
      cur = word;
    }
  }
  if (cur) lines.push(cur);
  if (lines.length > maxLines) {
    const kept = lines.slice(0, maxLines);
    kept[maxLines - 1] = `${kept[maxLines - 1]}…`;
    return kept;
  }
  return lines;
}

type Side = 'l' | 'r' | 't' | 'b';
function anchor([x, y]: [number, number], w: number, h: number, side: Side): [number, number] {
  if (side === 'l') return [x, y + h / 2];
  if (side === 'r') return [x + w, y + h / 2];
  if (side === 't') return [x + w / 2, y];
  return [x + w / 2, y + h];
}

/** A cubic path between two boxes: side to side when they are mostly beside each other, else top/bottom. */
export function edgePath(a: [number, number], b: [number, number], w: number, h: number): string {
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  if (Math.abs(dx) >= Math.abs(dy) * 0.8 && dx !== 0) {
    const [x1, y1] = anchor(a, w, h, dx > 0 ? 'r' : 'l');
    const [x2, y2] = anchor(b, w, h, dx > 0 ? 'l' : 'r');
    const c = Math.max(24, Math.abs(x2 - x1) / 2);
    const s = dx > 0 ? 1 : -1;
    return `M${x1} ${y1} C${x1 + s * c} ${y1} ${x2 - s * c} ${y2} ${x2} ${y2}`;
  }
  const [x1, y1] = anchor(a, w, h, dy > 0 ? 'b' : 't');
  const [x2, y2] = anchor(b, w, h, dy > 0 ? 't' : 'b');
  const c = Math.max(18, Math.abs(y2 - y1) / 2);
  const s = dy > 0 ? 1 : -1;
  return `M${x1} ${y1} C${x1} ${y1 + s * c} ${x2} ${y2 - s * c} ${x2} ${y2}`;
}

/**
 * An SVG box-and-arrow diagram drawn with the design tokens (colours in how.css, so light and dark both work).
 * `active` and `done` hold node and edge ids for the stepper; `focus` dims everything that is neither.
 */
export function Diagram({
  id,
  nodes,
  edges,
  layout,
  active,
  done,
  title,
  testId,
  labelLines = 1,
}: {
  id: string;
  nodes: DNode[];
  edges: DEdge[];
  layout: DLayout;
  active?: ReadonlySet<string>;
  done?: ReadonlySet<string>;
  title: string;
  testId?: string;
  labelLines?: number;
}) {
  const { w, h } = layout;
  const playing = !!active && active.size > 0;
  const state = (k: string) => (active?.has(k) ? 'is-active' : done?.has(k) ? 'is-done' : playing ? 'is-dim' : '');
  const labelSize = 15;
  const subSize = 12;
  return (
    <svg
      className="dg"
      viewBox={`0 0 ${layout.width} ${layout.height}`}
      role="img"
      aria-labelledby={`${id}-title`}
      data-testid={testId}
      preserveAspectRatio="xMidYMin meet"
    >
      <title id={`${id}-title`}>{title}</title>
      <defs>
        {(['plain', 'active', 'branch'] as const).map((m) => (
          <marker key={m} id={`${id}-arrow-${m}`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="9" markerHeight="9" markerUnits="userSpaceOnUse" orient="auto-start-reverse">
            <path d="M0 0 L10 5 L0 10 z" className={`dg-arrow dg-arrow-${m}`} />
          </marker>
        ))}
      </defs>
      <g className="dg-edges">
        {edges.map((e) => {
          const a = layout.at[e.from];
          const b = layout.at[e.to];
          if (!a || !b) return null;
          const st = state(e.id);
          const marker = st === 'is-active' ? 'active' : e.kind === 'branch' ? 'branch' : 'plain';
          return (
            <path
              key={e.id}
              d={edgePath(a, b, w, h)}
              className={`dg-edge dg-edge-${e.kind ?? 'plain'} ${e.dashed ? 'dg-dashed' : ''} ${st}`}
              markerEnd={`url(#${id}-arrow-${marker})`}
              data-edge={e.id}
            />
          );
        })}
      </g>
      <g className="dg-nodes">
        {nodes.map((n) => {
          const at = layout.at[n.id];
          if (!at) return null;
          const [x, y] = at;
          const label = wrap(n.label, w - 14, labelSize, labelLines);
          const sub = n.sub ? wrap(n.sub, w - 12, subSize, 2) : [];
          const total = label.length * (labelSize + 2) + sub.length * (subSize + 3);
          const top = y + (h - total) / 2 + labelSize - 3;
          const subTop = top + (label.length - 1) * (labelSize + 2);
          return (
            <g key={n.id} className={`dg-node dg-${n.tone ?? 'agent'} ${state(n.id)}`} data-node={n.id}>
              <rect x={x} y={y} width={w} height={h} rx={10} />
              {label.map((l, i) => (
                <text key={`l${i}`} x={x + w / 2} y={top + i * (labelSize + 2)} textAnchor="middle" className="dg-label" fontSize={labelSize}>
                  {l}
                </text>
              ))}
              {sub.map((s, i) => (
                <text key={i} x={x + w / 2} y={subTop + (i + 1) * (subSize + 3) + 1} textAnchor="middle" className="dg-sub" fontSize={subSize}>
                  {s}
                </text>
              ))}
            </g>
          );
        })}
      </g>
    </svg>
  );
}
