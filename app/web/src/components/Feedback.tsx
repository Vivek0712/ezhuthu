import { useI18n } from '../i18n/I18nProvider';
import { ApiError } from '../api/client';

export function ErrorNote({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const { t } = useI18n();
  const msg = error instanceof ApiError ? `${error.message} (${error.status})` : error instanceof Error ? error.message : String(error);
  return (
    <div className="alert" role="alert">
      <strong>{t('common.error')}</strong>: {msg}{' '}
      {onRetry && (
        <button className="btn btn-ghost btn-small" onClick={onRetry} type="button">
          {t('common.retry')}
        </button>
      )}
    </div>
  );
}

export function Busy() {
  const { t } = useI18n();
  return (
    <span className="row" role="status">
      <span className="spinner" aria-hidden="true" /> {t('common.loading')}
    </span>
  );
}
