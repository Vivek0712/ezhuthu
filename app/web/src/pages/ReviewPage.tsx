import { useCallback, useEffect, useState } from 'react';
import { api, ApiError, type QueueItem } from '../api/client';
import { EmptyState, ErrorNote, Skeleton } from '../components/Feedback';
import { useI18n } from '../i18n/I18nProvider';

/** A reviewed item, or one another reviewer got to first (409 Conflict: an item is reviewed once). */
type Done = QueueItem | { id: string; elsewhere: true };

function Row({ item, onDone }: { item: QueueItem; onDone: (q: Done) => void }) {
  const { t } = useI18n();
  const proposal = item.corrected_text ?? item.accepted_candidate ?? '';
  const [text, setText] = useState(proposal);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function act(action: 'approve' | 'edit' | 'reject') {
    setBusy(true);
    setError(null);
    try {
      onDone(await api.review(item.id, action === 'edit' ? { action, text } : { action }));
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        onDone({ id: item.id, elsewhere: true }); // not an error: the queue moved on without us
        return;
      }
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className="leaf queue-item" data-testid={`queue-${item.id}`}>
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <span className="badge">{item.id}</span>
        <span className="hint-text">
          {t('review.from')} {item.user} · {new Date(item.created_at).toLocaleString()}
        </span>
      </div>
      <p className="ctx">
        <span className="iso">{item.gap_ref.left}</span>
        <mark>{proposal || '[?]'}</mark>
        <span className="iso">{item.gap_ref.right}</span>
      </p>
      <label className="field">
        {t('review.proposed')}
        <input type="text" value={text} onChange={(e) => setText(e.target.value)} />
      </label>
      <div className="row">
        <button className="btn btn-primary btn-small" type="button" disabled={busy || !proposal} onClick={() => void act('approve')} data-testid={`approve-${item.id}`}>
          {t('review.approve')}
        </button>
        <button className="btn btn-ghost btn-small" type="button" disabled={busy || !text.trim()} onClick={() => void act('edit')}>
          {t('review.edit')}
        </button>
        <button className="btn btn-ghost btn-small" type="button" disabled={busy} onClick={() => void act('reject')} data-testid={`reject-${item.id}`}>
          {t('review.reject')}
        </button>
      </div>
      {error != null && <ErrorNote error={error} />}
    </article>
  );
}

export function ReviewPage() {
  const { t } = useI18n();
  const [items, setItems] = useState<QueueItem[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [done, setDone] = useState<Done[]>([]);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(() => {
    setError(null);
    api.queue().then((r) => setItems(r.items), setError);
  }, []);
  useEffect(load, [load]);

  return (
    <>
      <header className="page-head">
        <h1>{t('review.title')}</h1>
        <p className="lede">{t('review.lede')}</p>
      </header>
      {error != null && <ErrorNote error={error} onRetry={load} />}
      {!items && error == null && <Skeleton lines={4} />}
      {notice && (
        <p className="note note-unsure" role="status" data-testid="review-notice">
          {notice}
        </p>
      )}
      {items && items.length === 0 && <EmptyState title="review.empty" body="review.emptyBody" testId="review-empty" />}
      <div className="grid">
        {items?.map((q) => (
          <Row
            key={q.id}
            item={q}
            onDone={(u) => {
              setItems((xs) => xs?.filter((x) => x.id !== u.id) ?? null);
              setDone((d) => [u, ...d]);
              setNotice('elsewhere' in u ? t('review.alreadyReviewed') : null);
            }}
          />
        ))}
      </div>
      {done.length > 0 && (
        <section style={{ marginTop: 24 }}>
          <h2>{t('review.done')}</h2>
          <ul data-testid="reviewed">
            {done.map((d) => (
              <li key={d.id}>
                {'elsewhere' in d ? (
                  <>
                    {d.id}: {t('review.status.elsewhere')}
                  </>
                ) : (
                  <>
                    {d.id}: {d.status}
                    {d.final_text ? ` → ${d.final_text}` : ''}
                  </>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}
