import type { ReactNode } from 'react';
import { useAuth } from '../auth/AuthProvider';
import { useI18n } from '../i18n/I18nProvider';

export function RequireAuth({ children, expert = false }: { children: ReactNode; expert?: boolean }) {
  const auth = useAuth();
  const { t } = useI18n();
  if (!auth.user)
    return (
      <div className="leaf" data-testid="auth-gate">
        <p>{t('auth.required')}</p>
        {auth.mock && <p className="note">{t('auth.mockNote')}</p>}
        <button className="btn btn-primary" type="button" onClick={() => void auth.signIn()} disabled={!auth.configured}>
          {t('auth.signIn')}
        </button>
      </div>
    );
  if (expert && !auth.isExpert)
    return (
      <div className="leaf" role="alert">
        {t('auth.expertRequired')}
      </div>
    );
  return <>{children}</>;
}
