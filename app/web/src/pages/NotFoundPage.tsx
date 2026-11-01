import { Link } from 'react-router-dom';
import { useI18n } from '../i18n/I18nProvider';

export function NotFoundPage() {
  const { t } = useI18n();
  return (
    <div className="page-head">
      <h1>{t('notFound.title')}</h1>
      <Link className="btn btn-primary" to="/">
        {t('notFound.back')}
      </Link>
    </div>
  );
}
