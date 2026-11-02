import type { CSSProperties } from 'react';
import { Link } from 'react-router-dom';
import { useI18n } from '../../i18n/I18nProvider';
import { useInView } from './useInView';

/** "People in the loop": suggest -> review queue -> an epigraphist decides, as three steps that light up in turn
 * (src/ezhuthu/api/service.py add_correction -> queue; infra/lambda/proxy/queue.ts; Cognito "experts" group,
 * infra/lib/auth-stack.ts), and the validation kit, honestly not yet run (docs/expert-validation/README.md, PROTOCOL.md). */
export function PeopleSection() {
  const { t } = useI18n();
  const [ref, inView] = useInView<HTMLOListElement>(true);
  const steps = [
    { k: 'suggest', name: t('hw.pSuggest'), sub: t('hw.pSuggestS') },
    // Product names, the same in both languages.
    { k: 'queue', name: t('hw.pQueue'), sub: 'Amazon DynamoDB' },
    { k: 'expert', name: t('hw.pExpert'), sub: `${t('hw.pExpertS')} · Amazon Cognito` },
  ];
  return (
    <div className="people" data-testid="people">
      <ol ref={ref} className={`people-steps ${inView ? 'is-in' : ''}`}>
        {steps.map((s, i) => (
          <li key={s.k} className={`people-step people-${s.k}`} style={{ '--i': i } as CSSProperties}>
            <strong>{s.name}</strong>
            <span>{s.sub}</span>
          </li>
        ))}
      </ol>
      <div className="row people-row">
        <Link className="btn btn-ghost" to="/review" data-testid="people-review">
          {t('hw.peopleReview')} →
        </Link>
      </div>
      <details className="how-more" data-testid="people-kit">
        <summary>{t('hw.people3')}</summary>
        <p className="hint-text">{t('hw.peopleKit')}</p>
      </details>
    </div>
  );
}
