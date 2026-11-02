import { useState, type KeyboardEvent } from 'react';
import { Link } from 'react-router-dom';
import { useI18n } from '../../i18n/I18nProvider';
import type { MessageKey } from '../../i18n/strings';
import { fmt, pctText } from '../../practice/engine';
import { Bi } from '../practice/Bi';
import { wrap, useNarrow } from './Diagram';
import { NUMS, SLICE, UTAIYAR, VARI, grouped, type SliceEdge, type SliceNode } from './how-data';

const GROUP: Record<string, 'royal' | 'place' | 'value' | 'other'> = {
  ruler: 'royal',
  dynasty: 'royal',
  title: 'royal',
  formula: 'royal',
  place: 'place',
  admin_unit: 'place',
  temple: 'place',
  measure: 'value',
  coin: 'value',
  tax: 'value',
};

const byId = new Map(SLICE.nodes.map((n) => [n.id, n]));
const center = byId.get(SLICE.center)!;
const around = SLICE.nodes.filter((n) => n.id !== SLICE.center);
/** The edge that ties a node to the king (direct OWL relation or "named on the same stone"). */
function linkToCenter(id: string): SliceEdge | undefined {
  return SLICE.edges.find((e) => (e.from === id && e.to === SLICE.center) || (e.to === id && e.from === SLICE.center));
}
const extra = SLICE.edges.filter((e) => e.from !== SLICE.center && e.to !== SLICE.center);

function Detail({ node }: { node: SliceNode }) {
  const { t } = useI18n();
  const edge = linkToCenter(node.id);
  const other = extra.find((e) => e.from === node.id);
  return (
    <div className="onto-detail" aria-live="polite" data-testid="onto-detail">
      <Bi ta={node.label_ta ?? node.label_iso} iso={node.label_ta ? node.label_iso : undefined} className="onto-detail-name" />
      {node.label_en && <p className="onto-gloss">{node.label_en}</p>}
      {node.era && <p className="onto-gloss">{node.era}</p>}
      {edge && (
        <p>
          <strong>{t(`hw.rel.${edge.rel}` as MessageKey)}</strong>
          {edge.n ? ` · ${fmt(t('hw.ontoStones'), { n: edge.n })}` : ''}
        </p>
      )}
      {other && (
        <p>
          {t(`hw.rel.${other.rel}` as MessageKey)}: <span lang="ta-Latn">{byId.get(other.to)?.label_iso}</span>
        </p>
      )}
      {node.id === SLICE.center && node.inscriptions != null && <p>{fmt(t('hw.ontoInscriptions'), { n: node.inscriptions })}</p>}
      <p className="hint-text">
        <code>{node.id}</code>
        {node.wikidata && (
          <>
            {' · '}
            <a href={`https://www.wikidata.org/wiki/${node.wikidata}`} target="_blank" rel="noreferrer">
              Wikidata {node.wikidata} ↗
            </a>
          </>
        )}
        {edge?.evidence?.[0] && (
          <>
            {' · '}
            {t('hw.ontoReadOne')}{' '}
            <a href={`https://dharmalekha.info/texts/${edge.evidence[0]}`} target="_blank" rel="noreferrer">
              {edge.evidence[0]} ↗
            </a>
          </>
        )}
      </p>
    </div>
  );
}

const VB_W = 820;
const VB_H = 470;
const CX = VB_W / 2;
const CY = VB_H / 2;
function place(i: number, n: number): [number, number] {
  const a = -Math.PI / 2 + (2 * Math.PI * i) / n;
  return [CX + 245 * Math.cos(a), CY + 175 * Math.sin(a)];
}

/** A radial view of the slice (wide screens) or a grouped list (phones); both select into the same detail panel. */
function SliceView() {
  const { t, lang } = useI18n();
  const narrow = useNarrow();
  const [sel, setSel] = useState(SLICE.center);
  const pos = new Map<string, [number, number]>(around.map((n, i) => [n.id, place(i, around.length)]));
  pos.set(SLICE.center, [CX, CY]);
  const label = (n: SliceNode) => (lang === 'ta' && n.label_ta ? n.label_ta : n.label_iso);
  const onKey = (id: string) => (e: KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      setSel(id);
    }
  };
  const selected = byId.get(sel)!;

  return (
    <div className="onto-slice" data-testid="onto-slice">
      {narrow ? (
        <ul className="onto-list" aria-label={t('hw.ontoPick')}>
          {[center, ...around].map((n) => (
            <li key={n.id}>
              <button
                type="button"
                className={`onto-chip onto-${GROUP[n.kind] ?? 'other'}`}
                aria-pressed={sel === n.id}
                onClick={() => setSel(n.id)}
                data-testid={`onto-node-${n.id}`}
              >
                <Bi ta={n.label_ta ?? n.label_iso} iso={n.label_ta ? n.label_iso : undefined} />
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <svg className="onto-svg" viewBox={`0 0 ${VB_W} ${VB_H}`} role="group" aria-label={t('hw.ontoPick')} data-testid="onto-svg">
          {SLICE.edges.map((e, i) => {
            const a = pos.get(e.from);
            const b = pos.get(e.to);
            if (!a || !b) return null;
            const on = e.from === sel || e.to === sel;
            return <line key={i} x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} className={`onto-edge ${e.rel === 'sameStone' ? 'onto-co' : 'onto-direct'} ${on ? 'is-on' : ''}`} />;
          })}
          {[center, ...around].map((n) => {
            const [x, y] = pos.get(n.id)!;
            const isCenter = n.id === SLICE.center;
            const right = x > CX + 20;
            const left = x < CX - 20;
            const anchor = isCenter ? 'middle' : right ? 'start' : left ? 'end' : 'middle';
            const dx = isCenter ? 0 : right ? 14 : left ? -14 : 0;
            const below = !isCenter && !left && !right && y > CY;
            const lines = wrap(label(n), 150, 14, 2);
            const ly = isCenter ? y + 40 : below ? y + 26 : !left && !right ? y - 18 - (lines.length - 1) * 16 : y - (lines.length - 1) * 8 + 5;
            return (
              <g
                key={n.id}
                className={`onto-node onto-${GROUP[n.kind] ?? 'other'} ${sel === n.id ? 'is-sel' : ''}`}
                role="button"
                tabIndex={0}
                aria-pressed={sel === n.id}
                aria-label={`${n.label_ta ?? ''} ${n.label_iso}`.trim()}
                onClick={() => setSel(n.id)}
                onKeyDown={onKey(n.id)}
                data-testid={`onto-node-${n.id}`}
              >
                <circle cx={x} cy={y} r={isCenter ? 22 : 10} />
                {lines.map((l, i) => (
                  <text key={i} x={x + dx} y={ly + i * 16} textAnchor={anchor} className={isCenter ? 'onto-label onto-label-c' : 'onto-label'}>
                    {l}
                  </text>
                ))}
              </g>
            );
          })}
        </svg>
      )}
      <Detail node={selected} />
    </div>
  );
}

/** "The ontology": what it is, a real slice, counts by kind, storage and serving, hints in a restoration, measured effect. */
export function OntologySection() {
  const { t, lang } = useI18n();
  const kinds = Object.entries(SLICE.counts);
  return (
    <div className="onto" data-testid="onto">
      <p className="lede">{t('hw.ontoWhat')}</p>

      <h3>{fmt(t('hw.ontoSliceTitle'), { name: lang === 'ta' && center.label_ta ? center.label_ta : center.label_iso })}</h3>
      <p className="hint-text">{t('hw.ontoSliceLede')}</p>
      <SliceView />

      <div className="grid grid-2 onto-grid">
        <section className="leaf" data-testid="onto-counts">
          <h3>{t('hw.ontoCountsTitle')}</h3>
          {/* ontology/coverage.json (entities_per_kind, wikidata, corpus), copied into the slice by the generator. */}
          <p className="hint-text">{fmt(t('hw.ontoCountsLede'), { n: grouped(SLICE.corpus.inscriptions), lines: grouped(SLICE.corpus.lines), c: SLICE.corpus.collections })}</p>
          <table className="onto-counts">
            <tbody>
              {kinds.map(([k, n]) => (
                <tr key={k} data-testid={`onto-count-${k}`}>
                  <th scope="row">{t(`hw.k.${k}` as MessageKey)}</th>
                  <td className="num">{grouped(n)}</td>
                  <td className="hint-text">{SLICE.wikidata[k] ? fmt(t('hw.ontoQid'), { n: SLICE.wikidata[k]!.with_qid }) : ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
        <section className="leaf" data-testid="onto-store">
          <h3>{t('hw.ontoStoreTitle')}</h3>
          {/* Counts computed from ontology/ezhuthu.ttl by scripts/build_how_ontology_slice.py (ontology/README.md: 27 classes, 21 object properties, 1,958 named individuals). */}
          <p>{fmt(t('hw.ontoStore1'), { classes: SLICE.owl.classes, props: SLICE.owl.object_properties, ind: grouped(SLICE.owl.named_individuals) })}</p>
          {/* ontology/COA.md section 3; src/ezhuthu/agent/ontology_mcp.py; infra/lib/agent-stack.ts EZHUTHU_ONTOLOGY=mcp. */}
          <p>{t('hw.ontoStore2')}</p>
          {/* ontology/COA.md: "COA was not run"; bucket ezhuthu-coa-vectors + FalkorDB patch prepared only. */}
          <p>{t('hw.ontoStore3')}</p>
          {/* ontology/README.md "Train split only": 862 of 1,193 editions. */}
          <p>{fmt(t('hw.ontoTrain'), { used: grouped(NUMS.editionsUsed), total: grouped(NUMS.editionsTotal) })}</p>
        </section>
      </div>

      <section className="onto-hints" data-testid="onto-hints">
        <h3>{t('hw.ontoHintTitle')}</h3>
        <div className="grid grid-2">
          <div className="onto-hint">
            {/* samples/recorded-restores.json tirunallaru-temple-office: fill "u" 0.5988, sources include "ontology". */}
            <Bi ta="[?1]டையார் → உடையார்" iso="[?1]ṭaiyār → uṭaiyār" />
            <p className="hint-chip">
              {UTAIYAR.top.ontology_hints
                .filter((h) => h.id === 'ez:title/udaiyar')
                .map((h) => (
                  <span key={h.id} className="badge accent">
                    {h.kind}: {h.label}
                  </span>
                ))}
            </p>
            <p>{fmt(t('hw.ontoHint1'), { c: pctText(UTAIYAR.top.confidence) })}</p>
            <Link to="/restore?sample=tirunallaru-temple-office">{t('hw.ontoHintOpen')} →</Link>
          </div>
          <div className="onto-hint">
            {/* samples/recorded-restores.json tiruvavaduturai-taxes-paid-in-gold: hint ez:tax/vari (kind "measure"). */}
            <Bi ta="வரி[?1]பாடும் → வரிப்பாடும்" iso="vari-[?1]-pāṭum → vari-p-pāṭum" />
            <p className="hint-chip">
              {VARI.top.ontology_hints.map((h) => (
                <span key={h.id} className="badge">
                  {h.kind}: {h.label}
                </span>
              ))}
            </p>
            <p>{t('hw.ontoHint2')}</p>
            <Link to="/restore?sample=tiruvavaduturai-taxes-paid-in-gold">{t('hw.ontoHintOpen')} →</Link>
          </div>
        </div>
      </section>

      <section className="leaf onto-effect" data-testid="onto-effect">
        <h3>{t('hw.ontoEffectTitle')}</h3>
        {/* eval/reports/2026-11-02-test-eval.md "Ontology ablation": 88 of 413 hinted; 3 vs 3 discordant, p = 1.0. */}
        <p>{t('hw.ontoEffect1')}</p>
        {/* ontology/hint_eval.json held_out: test 16/253, val 16/345 (hit@5). */}
        <p>
          {fmt(t('hw.ontoEffect2'), {
            test: `${((100 * NUMS.hintTestHits) / NUMS.hintTestN).toFixed(1)}%`,
            th: NUMS.hintTestHits,
            tn: NUMS.hintTestN,
            val: `${((100 * NUMS.hintValHits) / NUMS.hintValN).toFixed(1)}%`,
            vh: NUMS.hintValHits,
            vn: NUMS.hintValN,
          })}
        </p>
      </section>
      <p className="credit" data-testid="onto-credit">
        {t('hw.ontoCredit')}{' '}
        <a href="https://dharmalekha.info" target="_blank" rel="noreferrer">
          DHARMA
        </a>{' '}
        ·{' '}
        <a href="https://creativecommons.org/licenses/by-sa/4.0/" target="_blank" rel="noreferrer">
          CC BY-SA 4.0
        </a>{' '}
        ·{' '}
        <a href="https://www.wikidata.org" target="_blank" rel="noreferrer">
          Wikidata
        </a>{' '}
        ·{' '}
        <a href="https://creativecommons.org/publicdomain/zero/1.0/" target="_blank" rel="noreferrer">
          CC0
        </a>
      </p>
    </div>
  );
}
