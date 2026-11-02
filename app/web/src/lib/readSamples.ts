/**
 * Samples for POST /api/read, so a learner without a photo or a file can try the reader (user feedback: "people won't
 * have text handy").
 *
 * Every sample comes from a TRAIN-split DHARMA inscription (benchmark/DATA_CARD.md, leakage rule 2): the samples are
 * public and invite the learner to restore their gaps, so they never carry val/test text or expert fills.
 * public/samples/read/SOURCES.json is the manifest, and tests/agent/test_app_samples.py enforces it.
 *
 * The "plates" are our own renderings (python -m ezhuthu.eval.ocr samples): edition lines drawn in a modern font on a
 * procedural stone texture. They are not photographs, and their labels say so. Text CC BY-SA 4.0, DHARMA project.
 */
export interface ReadSample {
  id: string;
  kind: 'photo' | 'text' | 'epidoc';
  url: string;
  /** Cropped preview for the sample button (plates only). */
  thumb?: string;
  type: string;
  label_en: string;
  label_ta: string;
  /** The DHARMA edition the sample comes from (TRAIN split). */
  inscription_id: string;
  source: string;
}

const dharma = (id: string) => `https://dharmalekha.info/texts/${id}`;

export const READ_SAMPLES: readonly ReadSample[] = [
  {
    id: 'stone-tamil',
    kind: 'photo',
    url: '/samples/read/stone-tamil.jpg',
    thumb: '/samples/read/stone-tamil.thumb.jpg',
    type: 'image/jpeg',
    label_en: 'Rendered plate: Tamil letters',
    label_ta: 'உருவாக்கிய தகடு: தமிழ் எழுத்து',
    inscription_id: 'DHARMA_INSPallava00042',
    source: dharma('DHARMA_INSPallava00042'),
  },
  {
    id: 'stone-weathered',
    kind: 'photo',
    url: '/samples/read/stone-weathered.jpg',
    thumb: '/samples/read/stone-weathered.thumb.jpg',
    type: 'image/jpeg',
    label_en: 'Rendered plate: worn stone',
    label_ta: 'உருவாக்கிய தகடு: தேய்ந்த கல்',
    inscription_id: 'DHARMA_INSTamilNadu00120',
    source: dharma('DHARMA_INSTamilNadu00120'),
  },
  {
    id: 'stone-brahmi',
    kind: 'photo',
    url: '/samples/read/stone-brahmi.jpg',
    thumb: '/samples/read/stone-brahmi.thumb.jpg',
    type: 'image/jpeg',
    label_en: 'Rendered plate: Tamil-Brahmi letters',
    label_ta: 'உருவாக்கிய தகடு: தமிழ்-பிராமி எழுத்து',
    inscription_id: 'DHARMA_INSPallava00042',
    source: dharma('DHARMA_INSPallava00042'),
  },
  {
    id: 'chola-txt',
    kind: 'text',
    url: '/samples/read/chola-opening.txt',
    type: 'text/plain',
    label_en: 'Chola opening lines (.txt)',
    label_ta: 'சோழர் கல்வெட்டுத் தொடக்கம் (.txt)',
    inscription_id: 'DHARMA_INSCempiyanMahadevi00001',
    source: dharma('DHARMA_INSCempiyanMahadevi00001'),
  },
  {
    id: 'dharma-xml',
    kind: 'epidoc',
    url: '/samples/read/DHARMA_INSUttiramerur00001.xml',
    type: 'application/xml',
    label_en: 'Uttiramerur assembly, DHARMA EpiDoc (.xml)',
    label_ta: 'உத்திரமேரூர் சபை, DHARMA EpiDoc (.xml)',
    inscription_id: 'DHARMA_INSUttiramerur00001',
    source: dharma('DHARMA_INSUttiramerur00001'),
  },
];
