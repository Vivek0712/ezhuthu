import { useI18n } from '../i18n/I18nProvider';
import { LEVELS, type Level } from '../lib/levels';
import { svgDataUrl } from '../lib/format';
import { vatteluttuSvg } from '../lib/vatteluttu';

export function LevelPicker({ value, onChange }: { value: Level; onChange: (l: Level) => void }) {
  const { lang, t } = useI18n();
  return (
    <fieldset className="levels" aria-label={t('learn.pickLevel')}>
      <legend className="visually-hidden">{t('learn.pickLevel')}</legend>
      {LEVELS.map((l) => (
        <label key={l.id} className="level" data-testid={`level-${l.id}`}>
          <input type="radio" name="level" value={l.id} checked={value === l.id} onChange={() => onChange(l.id)} />
          <span className="level-id">{l.id}</span>
          <span className={`level-ka ${l.fontClass}`} aria-hidden="true">
            {l.sampleKa ?? <img src={svgDataUrl(vatteluttuSvg('ka', { size: 48 }))} alt="" />}
          </span>
          <span className="level-name">{lang === 'ta' ? l.nameTa : l.nameEn}</span>
          <span className="level-era">{lang === 'ta' ? l.eraTa : l.eraEn}</span>
        </label>
      ))}
    </fieldset>
  );
}
