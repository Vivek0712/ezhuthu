import { useState } from 'react';
import { useI18n } from '../i18n/I18nProvider';
import { SAMPLE_IMAGES, sampleImageUrl, type SampleImage } from '../samples';

export interface TrySampleImageProps {
  /** Called with the picture as a File (image/jpeg), ready for the upload/OCR flow, and its metadata. */
  onPick: (file: File, image: SampleImage) => void;
  disabled?: boolean;
  /** Defaults to every sample image (app/web/src/samples/sample-images.json). */
  images?: SampleImage[];
}

/**
 * "Try a sample image": thumbnails of the synthetic sample photos (public/samples/*.jpg). Choosing one fetches the
 * JPEG and hands it to `onPick` as a File, so the upload flow treats it exactly like a photo the person chose.
 * Agreed with the upload/OCR track over KrewHQ (EZ-29/EZ-30).
 */
export function TrySampleImage({ onPick, disabled = false, images = SAMPLE_IMAGES }: TrySampleImageProps) {
  const { lang, t } = useI18n();
  const [busy, setBusy] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  async function pick(image: SampleImage) {
    setBusy(image.id);
    setFailed(false);
    try {
      const res = await fetch(sampleImageUrl(image));
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const bytes = await res.arrayBuffer();
      const type = res.headers.get('Content-Type')?.split(';')[0]?.trim() || 'image/jpeg';
      onPick(new File([bytes], image.file.split('/').pop() ?? `${image.id}.jpg`, { type }), image);
    } catch {
      setFailed(true);
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="try-images" aria-labelledby="try-images-title" data-testid="try-sample-image">
      <h3 id="try-images-title" className="try-images-title">
        {t('sampleImage.title')}
      </h3>
      <ul className="try-images-list">
        {images.map((im) => (
          <li key={im.id}>
            <button
              type="button"
              className="try-image"
              onClick={() => void pick(im)}
              disabled={disabled || busy !== null}
              aria-busy={busy === im.id}
              data-testid={`sample-image-${im.id}`}
            >
              <img src={sampleImageUrl(im)} alt="" width={160} height={110} loading="lazy" decoding="async" />
              <span className="try-image-label">{lang === 'ta' ? im.title_ta : im.title_en}</span>
              <span className="visually-hidden">{t('sampleImage.use')}</span>
            </button>
          </li>
        ))}
      </ul>
      {busy && (
        <p className="hint-text" role="status">
          {t('sampleImage.loading')}
        </p>
      )}
      {failed && (
        <p className="note" role="alert">
          {t('sampleImage.failed')}
        </p>
      )}
      <p className="hint-text">{t('sampleImage.note')}</p>
    </section>
  );
}
