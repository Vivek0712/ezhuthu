import { Link } from 'react-router-dom';
import { DharmaCredit } from '../components/Feedback';
import { EXAMPLE, exampleSnippet, Pipeline } from '../components/Pipeline';
import { Bi } from '../components/practice/Bi';
import { useI18n } from '../i18n/I18nProvider';
import { fmt, pctText } from '../practice/engine';

/** /how-it-works: the pipeline, walked through on one real TRAIN passage, then confidence, the Decider, data, limits. */
export function HowItWorksPage() {
  const { t, lang } = useI18n();
  const ex = EXAMPLE;
  const snippet = exampleSnippet(ex, 3);
  const top = ex.candidates[0];
  return (
    <>
      <header className="page-head">
        <h1>{t('how.pageTitle')}</h1>
        <p className="lede">{t('how.lede')}</p>
      </header>

      <section aria-labelledby="pipe-title" className="how-section">
        <h2 id="pipe-title">{t('pipe.title')}</h2>
        <Pipeline />
      </section>

      <section aria-labelledby="example-title" className="how-section" data-testid="worked-example">
        <h2 id="example-title">{t('how.exampleTitle')}</h2>
        <p>{fmt(t('how.exampleLede'), { title: lang === 'ta' ? ex.title_ta : ex.title_en, place: lang === 'ta' ? ex.place_ta : ex.place_en })}</p>
        <ol className="walk">
          <li>
            <h3>{t('pipe.reader')}</h3>
            <p>{t('how.step1')}</p>
            <p className="walk-line">
              <Bi ta={snippet.ta} iso={snippet.iso} taClass="script-chola" />
            </p>
          </li>
          <li>
            <h3>{t('pipe.restorer')}</h3>
            <p>{t('how.step2')}</p>
            <table className="walk-cands">
              <tbody>
                {ex.candidates.map((c) => (
                  <tr key={c.iso}>
                    <td>
                      <Bi ta={c.ta} iso={c.iso} />
                    </td>
                    <td>
                      <div className="q-bar" aria-hidden="true">
                        <span style={{ width: `${Math.round(c.confidence * 100)}%` }} />
                      </div>
                    </td>
                    <td className="num">{pctText(c.confidence)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </li>
          <li>
            <h3>{t('pipe.decider')}</h3>
            <p data-testid="walk-decider">{fmt(t('how.step3'), { c: pctText(top?.confidence ?? 0), t: ex.threshold == null ? '—' : pctText(ex.threshold) })}</p>
          </li>
          <li>
            <h3>{t('pipe.interpreter')}</h3>
            <p>{fmt(t('how.step4'), { w: ex.word.ta, wiso: ex.word.iso, m: lang === 'ta' ? ex.word.ta_meaning : ex.word.en })}</p>
            <blockquote className="walk-quote">{lang === 'ta' ? ex.why_ta : ex.why_en}</blockquote>
          </li>
          <li>
            <h3>{t('pipe.expert')}</h3>
            <p>{t('how.step5')}</p>
          </li>
        </ol>
        <p className="hint-text">
          <a href={ex.url} target="_blank" rel="noreferrer">
            {t('q.edition')} ↗
          </a>{' '}
          · {ex.licence} · {fmt(t('pipe.exampleFrom'), { title: lang === 'ta' ? ex.title_ta : ex.title_en, date: ex.recorded_on })}
        </p>
      </section>

      <div className="grid grid-2 how-grid">
        <section aria-labelledby="conf-title" className="leaf">
          <h2 id="conf-title">{t('how.confTitle')}</h2>
          <p>{t('how.conf1')}</p>
          <p>{t('how.conf2')}</p>
        </section>
        <section aria-labelledby="expert-title" className="leaf">
          <h2 id="expert-title">{t('how.expertTitle')}</h2>
          <p>{t('how.expert1')}</p>
          <p>{t('how.expert2')}</p>
        </section>
        <section aria-labelledby="decider-title" className="leaf">
          <h2 id="decider-title">{t('how.deciderTitle')}</h2>
          <p>{t('how.decider1')}</p>
          <p>{t('how.decider2')}</p>
        </section>
        <section aria-labelledby="data-title" className="leaf" data-testid="how-data">
          <h2 id="data-title">{t('how.dataTitle')}</h2>
          <p>{t('how.data1')}</p>
          <p>{t('how.data2')}</p>
          <DharmaCredit testId="how-credit" />
        </section>
      </div>

      <section aria-labelledby="limits-title" className="how-section how-limits" data-testid="how-limits">
        <h2 id="limits-title">{t('how.limitsTitle')}</h2>
        <ul>
          <li>{t('how.limit1')}</li>
          <li>{t('how.limit2')}</li>
          <li>{t('how.limit3')}</li>
          <li>{t('how.limit4')}</li>
        </ul>
        <p className="hint-text">{t('how.limitsSource')}</p>
        <div className="row">
          <Link className="btn btn-primary" to="/practice">
            {t('how.ctaPractice')}
          </Link>
          <Link className="btn btn-ghost" to="/restore">
            {t('how.ctaRestore')}
          </Link>
        </div>
      </section>

    </>
  );
}
