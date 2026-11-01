import type { components } from '../api/schema';

export type Level = components['schemas']['Level'];

export interface LevelInfo {
  id: Level;
  nameTa: string;
  nameEn: string;
  /** Short labels for the hero diagram. */
  shortTa: string;
  shortEn: string;
  /** Approximate period, deliberately written with "c." */
  eraTa: string;
  eraEn: string;
  /** CSS class selecting the web font used for this script stage. */
  fontClass: string;
  /** Sample letter "ka" in this stage; null when the stage has no Unicode (Vatteluttu uses SVG). */
  sampleKa: string | null;
  noteEn: string;
  noteTa: string;
}

// L1 is the easiest (closest to today), L5 the oldest. Ordering follows contracts/restore-api.md.
export const LEVELS: readonly LevelInfo[] = [
  {
    id: 'L1',
    shortTa: 'இன்று',
    shortEn: 'Today',
    nameTa: 'இன்றைய தமிழ்',
    nameEn: 'Modern Tamil',
    eraTa: 'இன்று',
    eraEn: 'today',
    fontClass: 'script-tamil',
    sampleKa: 'க',
    noteEn: 'The letters you already read.',
    noteTa: 'நீங்கள் ஏற்கனவே படிக்கும் எழுத்துகள்.',
  },
  {
    id: 'L2',
    shortTa: 'சோழர்',
    shortEn: 'Chola',
    nameTa: 'சோழர் காலத் தமிழ்',
    nameEn: 'Chola Tamil',
    eraTa: 'கி.பி. 9–13 நூ. (ஏறத்தாழ)',
    eraEn: 'c. 9th–13th c. CE',
    fontClass: 'script-chola',
    sampleKa: 'க',
    noteEn: 'Temple walls across the Kaveri delta. No pulli dots, older vowel signs.',
    noteTa: 'காவிரிக் கரைக் கோயில் சுவர்கள். புள்ளி இல்லை, பழைய உயிர்க்குறிகள்.',
  },
  {
    id: 'L3',
    shortTa: 'பல்லவர்',
    shortEn: 'Pallava',
    nameTa: 'பல்லவர் காலத் தமிழ்',
    nameEn: 'Pallava Tamil',
    eraTa: 'கி.பி. 6–9 நூ. (ஏறத்தாழ)',
    eraEn: 'c. 6th–9th c. CE',
    fontClass: 'script-grantha',
    sampleKa: '\u{11315}',
    noteEn: 'Shown with the Grantha web font, the closest Unicode relative of Pallava letterforms.',
    noteTa: 'பல்லவ எழுத்துருவுக்கு நெருக்கமான கிரந்த எழுத்துருவில் காட்டப்படுகிறது.',
  },
  {
    id: 'L4',
    shortTa: 'வட்டெழுத்து',
    shortEn: 'Vatteluttu',
    nameTa: 'வட்டெழுத்து',
    nameEn: 'Vatteluttu',
    eraTa: 'கி.பி. 6–11 நூ. (ஏறத்தாழ)',
    eraEn: 'c. 6th–11th c. CE',
    fontClass: 'script-vatteluttu',
    sampleKa: null,
    noteEn: 'Rounded "circle script". Not in Unicode, so letters are drawn as SVG.',
    noteTa: 'வட்ட வடிவ எழுத்து. யூனிகோடில் இல்லை; ஆகவே SVG ஆக வரையப்படுகிறது.',
  },
  {
    id: 'L5',
    shortTa: 'தமிழ்-பிராமி',
    shortEn: 'Tamil-Brahmi',
    nameTa: 'தமிழ்-பிராமி',
    nameEn: 'Tamil-Brahmi',
    eraTa: 'கி.மு. 3 நூ. முதல் (ஏறத்தாழ)',
    eraEn: 'from c. 3rd c. BCE',
    fontClass: 'script-brahmi',
    sampleKa: '\u{11013}',
    noteEn: 'Cave beds near Madurai. The oldest written Tamil.',
    noteTa: 'மதுரை அருகே குகைப் படுக்கைகள். எழுதப்பட்ட தமிழின் தொடக்கம்.',
  },
] as const;

export function levelInfo(id: Level): LevelInfo {
  const found = LEVELS.find((l) => l.id === id);
  if (!found) throw new Error(`unknown level ${id}`);
  return found;
}

export function isLevel(v: unknown): v is Level {
  return typeof v === 'string' && LEVELS.some((l) => l.id === v);
}
