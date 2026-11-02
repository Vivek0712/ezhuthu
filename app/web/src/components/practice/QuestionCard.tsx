import { useEffect, useRef, type ReactNode } from 'react';
import { useI18n } from '../../i18n/I18nProvider';
import type { MessageKey } from '../../i18n/strings';
import { glyphRef, VATTELUTTU_STROKE } from '../../lib/vatteluttu';
import { fmt } from '../../practice/engine';
import type { Item, Option } from '../../practice/types';
import { CC_BY_SA } from '../Feedback';
import { Bi, BiLine } from './Bi';

const ERA_FONT = { brahmi: 'script-brahmi', grantha: 'script-grantha', vatteluttu: '' } as const;

function Glyph({ item }: { item: Extract<Item, { kind: 'letters' }> }) {
  const { t } = useI18n();
  const era = t(`q.era.${item.era}` as MessageKey);
  const ref = glyphRef(item.glyph);
  return (
    <figure className="q-glyph" data-era={item.era}>
      <span className="tile-era">{era}</span>
      {ref ? (
        <svg className="q-glyph-svg" viewBox={`0 0 ${100 * ref.length} 100`} role="img" aria-label={`${era}: ${t('q.letters')}`} data-testid="q-glyph">
          <g fill="none" stroke="currentColor" strokeWidth={VATTELUTTU_STROKE} strokeLinecap="round" strokeLinejoin="round">
            {ref.map((g, i) => (
              <path key={i} transform={`translate(${100 * i} 0)`} d={g.d} />
            ))}
          </g>
        </svg>
      ) : (
        <span className={`q-glyph-text ${ERA_FONT[item.era]}`} role="img" aria-label={`${era}: ${t('q.letters')}`} data-testid="q-glyph">
          {item.glyph}
        </span>
      )}
      {item.era === 'vatteluttu' && <figcaption className="hint-text">{t('q.drawn')}</figcaption>}
    </figure>
  );
}

/** The question text and what it is about (the part above the options). */
function Prompt({ item, answered }: { item: Item; answered: boolean }) {
  const { t, pick } = useI18n();
  switch (item.kind) {
    case 'letters':
      return (
        <>
          <h2 className="q-title" tabIndex={-1}>{t('q.letters')}</h2>
          <Glyph item={item} />
        </>
      );
    case 'words':
      return (
        <>
          <h2 className="q-title" tabIndex={-1}>{t(`q.${item.dir}` as MessageKey)}</h2>
          <p className="q-word" data-testid="q-word">
            {item.dir === 'iso2ta' ? (
              <Bi ta={item.prompt.ta} iso={item.prompt.iso} hideTa={!answered} className="bi-big" />
            ) : (
              <Bi ta={item.prompt.ta} iso={item.prompt.iso} hideIso={!answered} className="bi-big" taClass={item.dir === 'chola2modern' ? 'script-chola' : ''} />
            )}
          </p>
        </>
      );
    case 'gaps':
      return (
        <>
          <h2 className="q-title" tabIndex={-1}>{t('q.gaps')}</h2>
          <p className="q-passage" data-testid="q-passage">
            <Bi ta={item.masked.ta} iso={item.masked.iso} taClass="script-chola" />
          </p>
          <p className="hint-text">{item.gap_chars === 1 ? t('q.gapsHint1') : fmt(t('q.gapsHint'), { n: item.gap_chars })}</p>
        </>
      );
    case 'formulas':
      return (
        <>
          <h2 className="q-title" tabIndex={-1}>
            {item.mode === 'meaning' ? t('q.formulaMeaning') : fmt(t('q.formulaSpot'), { m: '' })}
            {item.mode === 'spot' && <span className="q-gloss"> “{pick(item.gloss.ta, item.gloss.en)}”</span>}
          </h2>
          <p className="q-passage" data-testid="q-passage">
            <BiLine parts={item.line} mark={item.mode === 'meaning' || answered} />
          </p>
        </>
      );
  }
}

function OptionBody({ item, o, answered }: { item: Item; o: Option; answered: boolean }): ReactNode {
  const { pick } = useI18n();
  switch (item.kind) {
    case 'letters':
      return <Bi ta={o.ta} iso={o.iso} className="bi-opt" />;
    case 'words':
      if (item.dir === 'ta2iso') return <Bi ta={o.ta} iso={o.iso} hideTa={!answered} className="bi-opt" />;
      return <Bi ta={o.ta} iso={o.iso} hideIso={!answered} className="bi-opt" />;
    case 'gaps':
      return <Bi ta={o.ta} iso={o.iso} className="bi-opt" />;
    case 'formulas':
      if (o.en) return <span className="opt-gloss">{pick(o.ta, o.en)}</span>;
      return <Bi ta={o.ta} iso={o.iso} className="bi-opt" />;
  }
}

function SourceLine({ item }: { item: Item }) {
  const { t } = useI18n();
  if (!item.src) return null;
  return (
    <p className="q-source" data-testid="q-source">
      {t('q.source')}: {item.src.title}
      {item.src.line_n ? `, ${t('q.line')} ${item.src.line_n}` : ''} ·{' '}
      <a href={item.src.url} target="_blank" rel="noreferrer">
        {t('q.edition')} ↗
      </a>{' '}
      ·{' '}
      <a href={CC_BY_SA} target="_blank" rel="noreferrer">
        CC BY-SA 4.0
      </a>
    </p>
  );
}

/**
 * One multiple-choice question. `choice` is undefined until answered, null when the clock ran out.
 * Keys 1-4 answer while `keys` is on; after an answer the parent's Next button takes focus (Enter continues).
 */
export function QuestionCard({ item, choice, onChoose, keys = true, footer, compact }: { item: Item; choice: number | null | undefined; onChoose: (i: number) => void; keys?: boolean; footer?: ReactNode; compact?: boolean }) {
  const { t, pick } = useI18n();
  const answered = choice !== undefined;
  const right = answered && choice === item.answer;
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!keys || answered) return;
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement | null;
      if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.isContentEditable)) return;
      if (e.altKey || e.ctrlKey || e.metaKey) return;
      const n = Number(e.key);
      if (n >= 1 && n <= item.options.length) {
        e.preventDefault();
        onChoose(n - 1);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [keys, answered, item, onChoose]);

  const verdict =
    choice === null
      ? t('fb.timeout')
      : item.kind === 'gaps'
        ? right
          ? t('fb.gapMatch')
          : t('fb.gapOther')
        : right
          ? t('fb.right')
          : t('fb.wrong');
  const answer = item.options[item.answer]!;

  return (
    <article className={`q-card ${compact ? 'q-compact' : ''}`} data-testid="question" data-item-id={item.id} data-kind={item.kind} data-answered={answered ? 'yes' : 'no'}>
      <Prompt item={item} answered={answered} />
      <div className="q-options" role="group" aria-label={t('q.answers')} ref={listRef}>
        {item.options.map((o, i) => {
          const state = !answered ? '' : i === item.answer ? 'is-right' : i === choice ? 'is-wrong' : 'is-dim';
          return (
            <button
              key={i}
              type="button"
              className={`q-option ${state}`}
              onClick={() => onChoose(i)}
              disabled={answered}
              aria-pressed={answered ? i === choice : undefined}
              data-testid={`option-${i}`}
              data-right={answered ? String(i === item.answer) : undefined}
            >
              <span className="q-key" aria-hidden="true">
                {i + 1}
              </span>
              <OptionBody item={item} o={o} answered={answered} />
              {answered && i === choice && <span className="visually-hidden">({t('q.youChose')})</span>}
            </button>
          );
        })}
      </div>
      {!answered && !compact && <p className="q-keys hint-text">{t('q.keys')}</p>}
      <div aria-live="polite" className="q-live">
        {answered && (
          <div className={`feedback q-feedback ${right ? 'ok' : 'no'}`} data-testid="q-feedback" data-right={String(right)}>
            <strong>
              <span className="feedback-mark" aria-hidden="true">
                {right ? '✓' : '·'}
              </span>{' '}
              {verdict}
            </strong>
            {!right && (
              <p className="q-answer">
                {t('fb.answer')}:{' '}
                {item.kind === 'formulas' && answer.en ? <strong>{pick(answer.ta, answer.en)}</strong> : <Bi ta={answer.ta} iso={answer.iso} className="bi-inline" />}
              </p>
            )}
            {item.kind === 'gaps' && (
              <p className="q-answer">
                {t('q.restored')}: <Bi ta={item.restored.ta} iso={item.restored.iso} className="bi-inline" taClass="script-chola" />
              </p>
            )}
            <p className="q-why" lang={pick('ta', 'en')}>
              {pick(item.why_ta, item.why_en)}
            </p>
            <SourceLine item={item} />
          </div>
        )}
      </div>
      {footer}
    </article>
  );
}
