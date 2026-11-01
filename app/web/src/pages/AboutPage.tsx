import { useI18n } from '../i18n/I18nProvider';

export function AboutPage() {
  const { t } = useI18n();
  return (
    <>
      <header className="page-head">
        <h1>{t('about.title')}</h1>
        <p className="lede">{t('about.lede')}</p>
      </header>
      <div className="grid grid-3">
        <section className="leaf holes" style={{ paddingTop: 40 }}>
          <h2>{t('about.whyTitle')}</h2>
          <p>{t('about.why1')}</p>
          <p>{t('about.why2')}</p>
        </section>
        <section className="leaf holes" style={{ paddingTop: 40 }}>
          <h2>{t('about.howTitle')}</h2>
          <p>{t('about.how1')}</p>
          <p>{t('about.how2')}</p>
          <p>{t('about.how3')}</p>
        </section>
        <section className="leaf holes" style={{ paddingTop: 40 }} data-testid="credits">
          <h2>{t('about.dataTitle')}</h2>
          <p>
            {t('about.data1')}{' '}
            <a href="https://dharmalekha.info" target="_blank" rel="noreferrer">
              dharmalekha.info
            </a>{' '}
            ·{' '}
            <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noreferrer">
              CC BY 4.0
            </a>
          </p>
          <p>{t('about.data2')}</p>
          <p>{t('about.data3')}</p>
          <p>
            <strong>{t('about.builtWith')}</strong>
          </p>
        </section>
      </div>
    </>
  );
}
