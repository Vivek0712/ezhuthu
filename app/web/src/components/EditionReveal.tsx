import type { RestoreResponse } from '../api/client';
import { useI18n } from '../i18n/I18nProvider';
import { compareWithEdition, normForMatch, type Sample } from '../samples';

/**
 * Shown under a Restore result that came from a try-it sample (eval/reports/2026-11-02-samples.md).
 * Masked sample: what the published edition reads in the hidden gap, and whether the system's fill matches the
 * editors' restoration, differs from it, or was left open. Unsolved sample: why there is nothing to compare with.
 * Wording: "matches the editors' restoration", never "correct".
 */
export function EditionReveal({ sample, data }: { sample: Sample; data: RestoreResponse }) {
  const { t, lang } = useI18n();
  const credit = (
    <p className="reveal-credit" data-testid="reveal-credit">
      {t('samples.edition')}: <span lang="en">{sample.edition_title}</span> ·{' '}
      <a href={sample.dharma_url} target="_blank" rel="noreferrer">
        DHARMA {sample.inscription_id.replace('DHARMA_INS', '')} ↗
      </a>{' '}
      ·{' '}
      <a href={sample.licence_url} target="_blank" rel="noreferrer license">
        {sample.licence}
      </a>
    </p>
  );
  if (sample.group === 'unsolved' || !sample.edition_reading) {
    return (
      <section className="edition-reveal leaf" data-testid="edition-reveal" data-state="unsolved" aria-labelledby="reveal-title">
        <h3 id="reveal-title">{t('reveal.unsolvedTitle')}</h3>
        <p>{t('reveal.unsolvedBody')}</p>
        {credit}
      </section>
    );
  }
  const ed = sample.edition_reading;
  const gap = data.gaps.length === 1 ? data.gaps[0] : undefined;
  if (!gap) return null;
  const chosen = gap.decision === 'fill' && gap.chosen !== null ? gap.candidates[gap.chosen] : undefined;
  const state = compareWithEdition(chosen?.text, ed);
  const top = gap.candidates[0];
  const topMatches = !chosen && !!top && normForMatch(top.text) === ed.norm;
  const anyMatches = !chosen && !topMatches && gap.candidates.some((c) => normForMatch(c.text) === ed.norm);
  const ta = lang === 'ta';
  const reading = (iso: string, tamil: string) => (
    <>
      <span lang="ta">{ta ? tamil : iso}</span> <span className="iso">{ta ? iso : tamil}</span>
    </>
  );
  return (
    <section className="edition-reveal leaf" data-testid="edition-reveal" data-state={state} aria-labelledby="reveal-title">
      <h3 id="reveal-title">{t('reveal.title')}</h3>
      <p className="hint-text">{t('reveal.hidden')}</p>
      <dl className="reveal-pair">
        <div>
          <dt>{t('reveal.system')}</dt>
          <dd data-testid="reveal-system">{chosen ? reading(chosen.text, chosen.text_tamil) : '…?…'}</dd>
        </div>
        <div>
          <dt>{t('reveal.reads')}</dt>
          <dd data-testid="reveal-edition">{reading(ed.text_iso, ed.text_tamil)}</dd>
        </div>
      </dl>
      <p className={`reveal-state reveal-${state}`} data-testid="reveal-state">
        {t(state === 'match' ? 'reveal.match' : state === 'differs' ? 'reveal.differs' : 'reveal.open')}
      </p>
      {topMatches && <p data-testid="reveal-top">{t('reveal.openTop')}</p>}
      {anyMatches && <p data-testid="reveal-any">{t('reveal.openAny')}</p>}
      {credit}
    </section>
  );
}
