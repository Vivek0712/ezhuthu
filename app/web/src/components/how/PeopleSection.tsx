import { Link } from 'react-router-dom';
import { useI18n } from '../../i18n/I18nProvider';

/** "People in the loop": the review queue (src/ezhuthu/api/service.py add_correction -> queue; infra/lambda/proxy/queue.ts;
 * Cognito "experts" group, infra/lib/auth-stack.ts) and the validation kit (docs/expert-validation/README.md, PROTOCOL.md). */
export function PeopleSection() {
  const { t } = useI18n();
  return (
    <div className="grid grid-2 people" data-testid="people">
      <div className="leaf">
        <p>{t('hw.people1')}</p>
        <p>{t('hw.people2')}</p>
        <Link className="btn btn-ghost" to="/review" data-testid="people-review">
          {t('hw.peopleReview')} →
        </Link>
      </div>
      <div className="leaf">
        {/* docs/expert-validation/README.md: Study A blind 1-4 rating with Fleiss' and Cohen's kappa; Study B with/without AI.
            about.limit3 / ux limits: the expert studies have not run. */}
        <p>{t('hw.people3')}</p>
        <p className="hint-text">{t('hw.peopleKit')}</p>
      </div>
    </div>
  );
}
