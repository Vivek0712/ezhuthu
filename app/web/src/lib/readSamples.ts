/**
 * Samples for POST /api/read, so a learner without a photo can try the reader (user feedback: "people won't have text
 * handy"). Photos are our own renderings of DHARMA TEST-split edition lines (python -m ezhuthu.eval.ocr synth) on a
 * procedural stone texture: derived from CC BY-SA 4.0 editions, shared under the same licence, never photographs.
 * The EpiDoc file is a DHARMA edition (CC BY-SA 4.0) unchanged.
 */
export interface ReadSample {
  id: string;
  kind: 'photo' | 'text' | 'epidoc';
  url: string;
  type: string;
  label_en: string;
  label_ta: string;
  source?: string;
}

export const READ_SAMPLES: readonly ReadSample[] = [
  {
    id: 'stone-tamil',
    kind: 'photo',
    url: '/samples/read/stone-tamil.jpg',
    type: 'image/jpeg',
    label_en: 'Temple wall, Tamil script',
    label_ta: 'கோயில் சுவர், தமிழ் எழுத்து',
  },
  {
    id: 'stone-weathered',
    kind: 'photo',
    url: '/samples/read/stone-weathered.jpg',
    type: 'image/jpeg',
    label_en: 'Weathered stone',
    label_ta: 'தேய்ந்த கல்',
  },
  {
    id: 'stone-brahmi',
    kind: 'photo',
    url: '/samples/read/stone-brahmi.jpg',
    type: 'image/jpeg',
    label_en: 'Tamil-Brahmi letters',
    label_ta: 'தமிழ்-பிராமி எழுத்துகள்',
  },
  {
    id: 'chola-txt',
    kind: 'text',
    url: '/samples/read/chola-opening.txt',
    type: 'text/plain',
    label_en: 'Chola opening lines (.txt)',
    label_ta: 'சோழர் கல்வெட்டுத் தொடக்கம் (.txt)',
  },
  {
    id: 'dharma-xml',
    kind: 'epidoc',
    url: '/samples/read/DHARMA_INSPallava00205.xml',
    type: 'application/xml',
    label_en: 'Uttiramerur grant, DHARMA EpiDoc (.xml)',
    label_ta: 'உத்திரமேரூர் கொடை, DHARMA EpiDoc (.xml)',
    source: 'https://github.com/erc-dharma/tfa-pallava-epigraphy',
  },
];
