import { useId, useState, type CSSProperties } from 'react';
import { Link } from 'react-router-dom';
import { useI18n } from '../i18n/I18nProvider';
import { plural } from '../lib/format';
import { parseGaps } from '../lib/gaps';
import { ERAS, learnHref, restoreHref, useSamples, type Era, type Sample, type SampleGroup } from '../samples';

/**
 * A card-sized excerpt that always shows the first gap: about `width` characters, starting a little before it,
 * cut at spaces and marked with "…". Short passages are returned whole.
 */
export function excerptAroundGap(text: string, width = 230): string {
  if (text.length <= width) return text;
  const gap = Math.max(0, text.indexOf('[?'));
  let start = Math.max(0, Math.min(gap - Math.floor(width / 2), text.length - width));
  if (start > 0) start = text.indexOf(' ', start) + 1 || start;
  let end = Math.min(text.length, start + width);
  if (end < text.length) end = text.lastIndexOf(' ', end) > gap ? text.lastIndexOf(' ', end) : end;
  return `${start > 0 ? '… ' : ''}${text.slice(start, end).trim()}${end < text.length ? ' …' : ''}`;
}

/** Inscription text with its gap markers drawn as lacunae (still read out as "[?N]" to screen readers). */
export function GappedText({ text, lang }: { text: string; lang?: string }) {
  return (
    <span lang={lang}>
      {parseGaps(text).map((s, i) =>
        s.kind === 'text' ? (
          <span key={i}>{s.text}</span>
        ) : (
          <mark key={i} className="lacuna" title={s.raw}>
            {s.raw}
          </mark>
        ),
      )}
    </span>
  );
}

function SampleCard({ s, i }: { s: Sample; i: number }) {
  const { lang, t } = useI18n();
  const ta = lang === 'ta';
  const titleId = useId();
  return (
    <article className="sample-card" aria-labelledby={titleId} data-testid={`sample-${s.id}`} data-era={s.era} style={{ '--i': i } as CSSProperties}>
      <header className="sample-head">
        <span className={`era-chip era-${s.era}`}>{ta ? s.era_ta : s.era_en}</span>
        <span className="sample-gaps">
          <span>
            {s.gaps} {t(plural(s.gaps, 'samples.gap', 'samples.gaps'))}
          </span>
          {' · '}
          <span className="sample-badge" data-testid={`badge-${s.id}`}>
            {t(s.group === 'masked' ? 'samples.badgeMasked' : 'samples.badgeUnsolved')}
          </span>
        </span>
      </header>
      <h3 id={titleId} className="sample-title">
        <span lang="ta">{s.title_ta}</span>
        <span className="sample-title-en" lang="en">
          {s.title_en}
        </span>
      </h3>
      <p className="sample-place">{ta ? s.place_ta : s.place_en}</p>
      <p className="sample-edition" lang="en">
        {t('samples.edition')}: {s.edition_title}
      </p>
      <p className="sample-text">
        <GappedText text={excerptAroundGap(ta ? s.text_tamil : s.text_iso)} lang={ta ? 'ta' : 'ta-Latn'} />
      </p>
      <p className="sample-why">{ta ? s.why_ta : s.why_en}</p>
      <p className="sample-credit">
        <a href={s.dharma_url} target="_blank" rel="noreferrer">
          DHARMA {s.inscription_id.replace('DHARMA_INS', '')} ↗
        </a>{' '}
        · {s.lines[0] === s.lines[1] ? `${t('samples.line')} ${s.lines[0]}` : `${t('samples.lines')} ${s.lines[0]}–${s.lines[1]}`} ·{' '}
        <a href={s.licence_url} target="_blank" rel="noreferrer license">
          {s.licence}
        </a>
      </p>
      <div className="sample-actions">
        <Link className="btn btn-primary btn-small" to={restoreHref(s)} data-testid={`restore-${s.id}`}>
          {t('samples.restore')}
        </Link>
        <Link className="btn btn-ghost btn-small" to={learnHref(s)} data-testid={`learn-${s.id}`}>
          {t('samples.learn')}
        </Link>
      </div>
    </article>
  );
}

/** Live counts for the masked group, from each sample's recorded run (scripts/record_sample_restores.py). */
function MaskedStats({ samples }: { samples: Sample[] }) {
  const { t } = useI18n();
  const gaps = samples.flatMap((s) => s.recorded?.gaps ?? []);
  const date = samples.find((s) => s.recorded)?.recorded?.date;
  if (!gaps.length || !date) return null;
  const filled = gaps.filter((g) => g.decision === 'fill').length;
  const matched = gaps.filter((g) => g.outcome === 'match').length;
  return (
    <p className="hint-text" data-testid="masked-stats">
      {t('samples.recordedOn')} {date}: {filled}/{gaps.length} {t('samples.statFilled')} · {matched}/{filled} {t('samples.statMatch')} ·{' '}
      {gaps.length - filled} {t('samples.statOpen')}
    </p>
  );
}

const GROUPS: { group: SampleGroup; title: 'samples.maskedTitle' | 'samples.unsolvedTitle'; lede: 'samples.maskedLede' | 'samples.unsolvedLede' }[] = [
  { group: 'masked', title: 'samples.maskedTitle', lede: 'samples.maskedLede' },
  { group: 'unsolved', title: 'samples.unsolvedTitle', lede: 'samples.unsolvedLede' },
];

/**
 * The try-it gallery on the home page, filterable by period, in two groups: passages with a hidden span whose
 * edition reading is known (compare after restoring), and gaps the editors left blank. Loads them on demand.
 */
export function SampleGallery({ samples: given }: { samples?: Sample[] }) {
  const { lang, t } = useI18n();
  const loaded = useSamples(!given);
  const samples = given ?? loaded ?? [];
  const [era, setEra] = useState<Era | 'all'>('all');
  const shown = era === 'all' ? samples : samples.filter((s) => s.era === era);
  const eras = ERAS.filter((e) => samples.some((s) => s.era === e));
  const label = (e: Era) => {
    const s = samples.find((x) => x.era === e)!;
    return lang === 'ta' ? s.era_ta : s.era_en;
  };
  return (
    <section id="samples" className="samples" aria-labelledby="samples-title" data-testid="sample-gallery">
      <p className="kicker">{t('samples.kicker')}</p>
      <h2 id="samples-title" tabIndex={-1}>{t('samples.title')}</h2>
      <p className="lede">{t('samples.lede')}</p>
      <div className="era-filter" role="group" aria-label={t('samples.filter')}>
        {(['all', ...eras] as const).map((e) => (
          <button
            key={e}
            type="button"
            className={`chip-btn ${era === e ? 'on' : ''}`}
            aria-pressed={era === e}
            onClick={() => setEra(e)}
            data-testid={`era-${e}`}
          >
            {e === 'all' ? t('samples.all') : label(e)}
          </button>
        ))}
      </div>
      <p className="visually-hidden" aria-live="polite">
        {shown.length} {t('samples.showing')}
      </p>
      {samples.length === 0 ? (
        <div className="sample-grid" aria-busy="true" data-testid="sample-grid">
          {[0, 1, 2].map((i) => (
            <div key={i} className="sample-card sample-card-skeleton" aria-hidden="true" />
          ))}
        </div>
      ) : (
        GROUPS.map(({ group, title, lede }) => {
          const inGroup = shown.filter((s) => s.group === group);
          if (!inGroup.length) return null;
          return (
            <div key={group} className="sample-group" data-testid={`sample-group-${group}`}>
              <h3>{t(title)}</h3>
              <p className="note">{t(lede)}</p>
              {group === 'masked' && <MaskedStats samples={samples.filter((s) => s.group === 'masked')} />}
              <div className="sample-grid" key={era} data-testid="sample-grid">
                {inGroup.map((s, i) => (
                  <SampleCard key={s.id} s={s} i={i} />
                ))}
              </div>
            </div>
          );
        })
      )}
      <p className="note">{t('samples.normalised')}</p>
      <p className="note">{t('samples.noBrahmi')}</p>
    </section>
  );
}
