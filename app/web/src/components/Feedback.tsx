import { useEffect, useState, type ReactNode } from 'react';
import { ApiError } from '../api/client';
import { useI18n } from '../i18n/I18nProvider';
import type { MessageKey } from '../i18n/strings';

/** What kind of failure an error is, for the copy we show (design/ux/UX.md section 6: no stack traces). */
export function errorKind(error: unknown): 'network' | 'server' | 'client' {
  if (error instanceof ApiError) return error.status >= 500 ? 'server' : 'client';
  return 'network'; // fetch rejects with a TypeError when the API cannot be reached
}

export function ErrorNote({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const { t } = useI18n();
  const kind = errorKind(error);
  const api = error instanceof ApiError ? error : null;
  const [title, body]: [string, string] =
    kind === 'network'
      ? [t('error.network'), t('error.networkBody')]
      : kind === 'server'
        ? [t('error.server'), t('error.serverBody')]
        : // A 4xx carries a message written for people by the API (e.g. "no [?] or [?N] gap in text").
          [t('common.error'), api?.message ?? ''];
  return (
    <div className="alert" role="alert" data-testid="error">
      <span className="alert-icon" aria-hidden="true">
        !
      </span>
      <div className="alert-body">
        <strong>{title}</strong>
        {body && <p>{body}</p>}
        {api && (
          <small className="alert-ref">
            {t('common.reference')}: {api.code} · HTTP {api.status}
          </small>
        )}
      </div>
      {onRetry && (
        <button className="btn btn-ghost btn-small" onClick={onRetry} type="button">
          {t('common.retry')}
        </button>
      )}
    </div>
  );
}

/** Inline "working" status with no spinner; after 2 s it says "Reading the stone…" (restorations can take a while). */
export function Busy() {
  const { t } = useI18n();
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    const id = setTimeout(() => setSlow(true), 2000);
    return () => clearTimeout(id);
  }, []);
  return (
    <span className="busy" role="status" data-testid="busy">
      <span className="busy-bar" aria-hidden="true" />
      {t(slow ? 'common.slow' : 'common.loading')}
    </span>
  );
}

/** Skeleton lines in surface-sunk for a region that is loading. */
export function Skeleton({ lines = 3, label }: { lines?: number; label?: string }) {
  const { t } = useI18n();
  return (
    <div className="skeleton" role="status" aria-label={label ?? t('common.loading')} data-testid="skeleton">
      {Array.from({ length: lines }, (_, i) => (
        <span key={i} className="skeleton-line" style={{ width: `${92 - i * 17}%` }} />
      ))}
      <Busy />
    </div>
  );
}

/** Empty state: a dashed card with the lamp triangle (the Brahmi e), a message and one action. */
export function EmptyState({ title, body, action, testId }: { title: MessageKey; body?: MessageKey; action?: ReactNode; testId?: string }) {
  const { t } = useI18n();
  return (
    <div className="empty" data-testid={testId}>
      <svg className="empty-lamp" viewBox="0 0 40 36" aria-hidden="true">
        <path d="M20 3 L37 33 H3 Z" fill="none" stroke="currentColor" strokeWidth="3" strokeLinejoin="round" />
      </svg>
      <p className="empty-title">{t(title)}</p>
      {body && <p className="empty-body">{t(body)}</p>}
      {action}
    </div>
  );
}

export const CC_BY_SA = 'https://creativecommons.org/licenses/by-sa/4.0/';

/** "Inscription texts: DHARMA, CC BY-SA 4.0" with both links (design/brand/BRAND.md, section 4). */
export function DharmaCredit({ className, testId }: { className?: string; testId?: string }) {
  const { t } = useI18n();
  return (
    <p className={className ?? 'credit'} data-testid={testId}>
      {t('credit.inscriptions').replace(/DHARMA, CC BY-SA 4\.0$/, '')}
      <a href="https://dharmalekha.info" rel="noreferrer" target="_blank">
        DHARMA
      </a>
      ,{' '}
      <a href={CC_BY_SA} rel="noreferrer" target="_blank">
        CC BY-SA 4.0
      </a>
    </p>
  );
}
