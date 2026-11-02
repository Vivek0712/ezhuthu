import type { CSSProperties, ReactNode } from 'react';
import { useI18n } from '../../i18n/I18nProvider';
import type { MessageKey } from '../../i18n/strings';
import { isoToTamil } from '../../lib/script';
import { fmt, pctText } from '../../practice/engine';
import { EXAMPLE, exampleSnippet } from '../Pipeline';
import { Bi } from '../practice/Bi';
import { DECIDER_EX, INTERP_EX, NUMS, READER_EX, VARI, VARI_PARALLEL, grouped } from './how-data';
import { useInView } from './useInView';

/** The agents and tools, in the order a request meets them. `anchor` is the #id the home chips link to. */
export const AGENTS = [
  { key: 'reader', anchor: 'agent-reader', kind: 'hw.kind.agent' },
  { key: 'restorer', anchor: 'agent-restorer', kind: 'hw.kind.agent' },
  { key: 'retrieval', anchor: 'agent-retrieval', kind: 'hw.kind.tool' },
  { key: 'ngram', anchor: 'agent-ngram', kind: 'hw.kind.stat' },
  { key: 'ontology', anchor: 'agent-ontology', kind: 'hw.kind.mcp' },
  { key: 'check', anchor: 'agent-check', kind: 'hw.kind.score' },
  { key: 'decider', anchor: 'agent-decider', kind: 'hw.kind.decider' },
  { key: 'interpreter', anchor: 'agent-interpreter', kind: 'hw.kind.agent' },
  { key: 'tutor', anchor: 'agent-tutor', kind: 'hw.kind.graph' },
  { key: 'review', anchor: 'agent-review', kind: 'hw.kind.people' },
] as const satisfies readonly { key: string; anchor: string; kind: MessageKey }[];

export type AgentKey = (typeof AGENTS)[number]['key'];

/** The agent's display name ("Strands Decider" is a product name, the same in both languages). */
export function useAgentName(): (k: AgentKey) => string {
  const { t } = useI18n();
  return (k) => (k === 'decider' ? 'Strands Decider' : t(`hw.${k}.name` as MessageKey));
}

/** "The agents": one card per agent or tool: what it does in one line and a real example; inputs, outputs and technique under "More". */
export function AgentCards() {
  const { t, lang } = useI18n();
  const name = useAgentName();
  const [ref, inView] = useInView<HTMLOListElement>(true);
  const snippet = exampleSnippet(EXAMPLE, 1);
  const top = EXAMPLE.candidates[0]!;
  const par = VARI_PARALLEL;
  const ngramShare = VARI.top.ngram_probability;

  // Each example is real recorded output; the comment says where it was recorded.
  const examples: Record<AgentKey, { text: string; bi?: ReactNode }> = {
    // hero/runs/read.json: the routed Reader on the Thanjavur photo (confidence 0.2, escalated to Opus).
    reader: {
      text: fmt(t('hw.reader.ex'), { script: lang === 'ta' ? READER_EX.script_ta : READER_EX.script_en, c: pctText(READER_EX.confidence) }),
      bi: <Bi ta={READER_EX.line.text_tamil} iso={READER_EX.line.text} taClass="script-chola" />,
    },
    // samples/recorded-restores.json "tiruvavaduturai-taxes-paid-in-gold" (VAL); editors' reading "p" (samples.json).
    restorer: {
      text: fmt(t('hw.restorer.ex'), { c: pctText(VARI.top.confidence) }),
      bi: <Bi ta="ஊர் இடு வரி[?1]பாடும் → ப்" iso="Ūr iṭu vari-[?1]-pāṭum → p" />,
    },
    // Same gap: its best parallel (a train line) from the recorded candidate's parallels.
    retrieval: {
      text: fmt(t('hw.retrieval.ex'), { id: par.id, line: par.line }),
      bi: <Bi ta={isoToTamil(par.iso)} iso={par.iso} />,
    },
    // Same gap: features.ngram_probability of the chosen candidate (0.9929, ngram_rank 0).
    ngram: { text: fmt(t('hw.ngram.ex'), { p: pctText(ngramShare) }), bi: <Bi ta="ப்" iso="p" /> },
    // samples/recorded-restores.json "tirunallaru-temple-office": candidate "u" with source "ontology", hint ez:title/udaiyar.
    ontology: { text: t('hw.ontology.ex'), bi: <Bi ta="[?1]டையார் → உடையார்" iso="[?1]ṭaiyār → uṭaiyār" /> },
    // practice/banks/worked-example.json: best candidate 0.1495 against threshold 0.4111.
    check: {
      text: fmt(t('hw.check.ex'), { c: pctText(top.confidence), t: EXAMPLE.threshold == null ? '—' : pctText(EXAMPLE.threshold) }),
      bi: <Bi ta={snippet.ta} iso={snippet.iso} taClass="script-chola" />,
    },
    // eval/reports/2026-11-02-deployed-config/rows/val-routed-hosted-v19.jsonl, DHARMA_INSTamilNadu00467:7:0.
    decider: {
      text: fmt(t('hw.decider.ex'), { c: pctText(DECIDER_EX.confidence), s: DECIDER_EX.seconds }),
      bi: <Bi ta={DECIDER_EX.text_tamil} iso={DECIDER_EX.text} />,
    },
    // hero/runs/interpret.json: word kuḷam "tank / pond", attested true.
    interpreter: { text: fmt(t('hw.interpreter.ex'), { m: INTERP_EX.en }), bi: <Bi ta={INTERP_EX.tamil} iso={INTERP_EX.iso} /> },
    // practice/banks/worked-example.json: word makaṉ "son".
    tutor: { text: t('hw.tutor.ex'), bi: <Bi ta={EXAMPLE.word.ta} iso={EXAMPLE.word.iso} /> },
    review: { text: t('hw.review.ex'), bi: <Bi ta={snippet.ta} iso={snippet.iso} taClass="script-chola" /> },
  };
  const howVars: Partial<Record<AgentKey, Record<string, string | number>>> = {
    retrieval: { lines: grouped(NUMS.trainLines) },
    ngram: { ms: NUMS.ngramMs },
    check: { ts: pctText(NUMS.thrSonnet), to: pctText(NUMS.thrOpus) },
  };

  return (
    <ol ref={ref} className={`agents ${inView ? 'is-in' : ''}`} data-testid="agent-cards">
      {AGENTS.map((a, i) => {
        const ex = examples[a.key];
        return (
          <li key={a.key} id={a.anchor} className="agent-card" data-testid={`agent-${a.key}`} tabIndex={-1} style={{ '--i': i } as CSSProperties}>
            <header className="agent-head">
              <h3>{name(a.key)}</h3>
              <span className="badge">{t(a.kind)}</span>
            </header>
            <p className="agent-do">{t(`hw.${a.key}.do` as MessageKey)}</p>
            <div className="agent-ex" data-testid={`agent-ex-${a.key}`}>
              {ex.bi}
              <p>{ex.text}</p>
            </div>
            <details className="how-more agent-more">
              <summary>{t('hw.more')}</summary>
              <dl className="agent-io">
                <div>
                  <dt>{t('hw.takes')}</dt>
                  <dd>{t(`hw.${a.key}.in` as MessageKey)}</dd>
                </div>
                <div>
                  <dt>{t('hw.gives')}</dt>
                  <dd>{t(`hw.${a.key}.out` as MessageKey)}</dd>
                </div>
                <div>
                  <dt>{t('hw.howItDoes')}</dt>
                  <dd>{fmt(t(`hw.${a.key}.how` as MessageKey), howVars[a.key] ?? {})}</dd>
                </div>
              </dl>
              {a.key === 'reader' && <p className="hint-text">{t('hw.reader.note')}</p>}
            </details>
          </li>
        );
      })}
    </ol>
  );
}
