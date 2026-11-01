/**
 * Mock fixtures for local development and tests. Every inscription id starts with "mock:" and every
 * number here is demo data produced by the mock, never a measured result. Real lessons, restorations
 * and scores come from the agent team's API (contracts/restore-api.md).
 */
import type { Schemas } from '../api/client';
import { vatteluttuSvg } from '../lib/vatteluttu';

type Level = Schemas['Level'];
type PracticeItem = Schemas['PracticeItem'];
export interface MockItem extends PracticeItem {
  answers: string[];
  hint_ta: string;
  hint_en: string;
}
export interface MockLesson {
  inscription: Schemas['Inscription'];
  context: Schemas['LessonContext'];
  items: MockItem[];
}

const DHARMA = 'https://dharmalekha.info';

function letter(
  id: string,
  level: Level,
  glyph: { text?: string; svg?: string },
  answers: string[],
  hint_ta: string,
  hint_en: string,
): MockItem {
  return {
    item_id: id,
    type: 'letter',
    prompt_ta: 'இந்த எழுத்தை இன்றைய தமிழில் எழுதுக',
    prompt_en: 'Write this letter in modern Tamil',
    ...(glyph.svg ? { glyph_svg: glyph.svg } : { glyph_text: glyph.text ?? '' }),
    script_level: level,
    answer_hidden: true,
    answers,
    hint_ta,
    hint_en,
  };
}

const uttiramerur = {
  id: 'mock:uttiramerur-sabha',
  title: 'Uttiramerur sabha resolution (Parantaka I)',
  dynasty: 'Chola',
  approx_date: 'c. 920 CE',
  source_url: DHARMA,
  restored_text: 'svasti śrī matiraikoṇṭa kōpparakēcaripaṉmaṟku yāṇṭu paṉṉiraṇṭāvatu',
  restored_text_tamil: 'ஸ்வஸ்தி ஸ்ரீ மதிரைகொண்ட கோப்பரகேசரிபன்மற்கு யாண்டு பன்னிரண்டாவது',
};
const uttiramerurContext: Schemas['LessonContext'] = {
  ruler: 'Parantaka I (Maturaikonda Parakesarivarman)',
  temple: 'Vaikuntha Perumal temple, Uttiramerur',
  grant: 'Sabha resolution on electing village committees',
  explain_ta:
    'இது பராந்தக சோழனின் பன்னிரண்டாம் ஆட்சியாண்டுக் கல்வெட்டின் தொடக்கம். “மதிரைகொண்ட” என்றால் மதுரையை வென்ற. ஊர்ச் சபை தன் குழுக்களைக் குடவோலை முறையில் தேர்ந்தெடுத்த விதியைப் பதிவு செய்கிறது.',
  explain_en:
    'The opening of an inscription from the 12th regnal year of Parantaka I. "Matiraikonda" means "who took Madurai". The village assembly records how it chose its committees by lot (kudavolai).',
};

export const LESSONS: Record<Level, MockLesson> = {
  L1: {
    inscription: uttiramerur,
    context: uttiramerurContext,
    items: [
      letter('L1-1', 'L1', { text: 'க' }, ['க', 'ka'], 'கல் என்ற சொல்லின் முதல் எழுத்து.', 'First letter of kal, "stone".'),
      letter('L1-2', 'L1', { text: 'ம' }, ['ம', 'ma'], 'மதிரை என்பதன் முதல் எழுத்து.', 'First letter of Matirai.'),
      letter('L1-3', 'L1', { text: 'ண்' }, ['ண்', 'ṇ', 'n'], 'புள்ளி வைத்த மெய் எழுத்து; “கொண்ட” என்பதில் வருகிறது.', 'A dotted consonant, as in koṇṭa.'),
      {
        item_id: 'L1-4',
        type: 'word',
        prompt_ta: 'இந்தச் சொல்லைப் படியுங்கள்',
        prompt_en: 'Read this word',
        glyph_text: 'யாண்டு',
        script_level: 'L1',
        answer_hidden: true,
        answers: ['யாண்டு', 'yāṇṭu', 'yantu'],
        hint_ta: 'ஆண்டு என்பதன் பழைய வடிவம்.',
        hint_en: 'An older form of āṇṭu, "year".',
      },
    ],
  },
  L2: {
    inscription: uttiramerur,
    context: uttiramerurContext,
    items: [
      letter('L2-1', 'L2', { text: 'க' }, ['க', 'ka'], 'மேல் கோடு சற்று வளைந்த “க”.', 'A ka with a slightly curved top stroke.'),
      letter('L2-2', 'L2', { text: 'ட' }, ['ட', 'ṭa'], 'கீழே திறந்த ஒரு கோணம்.', 'An angle open at the bottom.'),
      letter('L2-3', 'L2', { text: 'ப' }, ['ப', 'pa'], 'கோப்பரகேசரி என்பதில் வருகிறது.', 'As in kōpparakēcari.'),
      {
        item_id: 'L2-4',
        type: 'word',
        prompt_ta: 'புள்ளி இல்லாத இந்தச் சொல்லைப் படியுங்கள்',
        prompt_en: 'Read this word, written without pulli dots',
        glyph_text: 'யாணடு',
        script_level: 'L2',
        answer_hidden: true,
        answers: ['யாண்டு', 'yāṇṭu', 'yantu'],
        hint_ta: 'சோழர் கல்வெட்டுகளில் புள்ளி எழுதப்படுவதில்லை; ண என்பதை ண் எனப் படிக்கவும்.',
        hint_en: 'Chola inscriptions omit the pulli; read ண as ண்.',
      },
    ],
  },
  L3: {
    inscription: {
      id: 'mock:pallava-nandivarman',
      title: 'Pallava-period temple inscription (Nandivarman II)',
      dynasty: 'Pallava',
      approx_date: 'c. 8th c. CE',
      source_url: DHARMA,
      restored_text: 'kō vicaiya nantivikkiramaparumaṟku yāṇṭu',
      restored_text_tamil: 'கோ விசைய நந்திவிக்கிரமபருமற்கு யாண்டு',
    },
    context: {
      ruler: 'Nandivarman II Pallavamalla',
      explain_ta: 'பல்லவர் தமிழ்க் கல்வெட்டுகள் “கோ விசைய” என அரசன் பெயரோடு ஆட்சியாண்டைத் தொடங்குகின்றன.',
      explain_en: 'Pallava Tamil inscriptions open with "kō vicaiya" and the king’s name before the regnal year.',
    },
    items: [
      letter('L3-1', 'L3', { text: '\u{11315}' }, ['க', 'ka'], 'மேலே ஒரு கொக்கி, கீழே ஒரு வளையம்.', 'A hook on top and a loop below.'),
      letter('L3-2', 'L3', { text: '\u{11328}' }, ['ந', 'na'], 'நந்தி என்பதன் முதல் எழுத்து.', 'First letter of Nanti.'),
      letter('L3-3', 'L3', { text: '\u{1132E}' }, ['ம', 'ma'], 'பருமற்கு என்பதில் வருகிறது.', 'As in parumaṟku.'),
      letter('L3-4', 'L3', { text: '\u{1132F}' }, ['ய', 'ya'], 'யாண்டு என்பதன் முதல் எழுத்து.', 'First letter of yāṇṭu.'),
    ],
  },
  L4: {
    inscription: {
      id: 'mock:vatteluttu-herostone',
      title: 'Vatteluttu hero-stone (natukal)',
      dynasty: null,
      approx_date: 'c. 8th c. CE',
      source_url: DHARMA,
      restored_text: 'paṭṭāṉ kal',
      restored_text_tamil: 'பட்டான் கல்',
    },
    context: {
      explain_ta: 'நடுகற்கள் போரில் வீழ்ந்த வீரருக்காக நடப்பட்டவை. “பட்டான் கல்” என்றால் வீழ்ந்தவனின் கல்.',
      explain_en: 'Hero stones were raised for warriors who fell in battle. "paṭṭāṉ kal" means "the stone of the one who fell".',
    },
    items: [
      letter('L4-1', 'L4', { svg: vatteluttuSvg('ka') }, ['க', 'ka'], 'கல் என்பதன் முதல் எழுத்து.', 'First letter of kal.'),
      letter('L4-2', 'L4', { svg: vatteluttuSvg('pa') }, ['ப', 'pa'], 'கீழே வட்டமான ஒரு கிண்ணம்.', 'A rounded cup.'),
      letter('L4-3', 'L4', { svg: vatteluttuSvg('ta') }, ['த', 'ta'], 'மேலே ஒரு சுருள்.', 'A curl on top.'),
      letter('L4-4', 'L4', { svg: vatteluttuSvg('na') }, ['ன', 'ṉa', 'na'], 'பட்டான் என்பதன் கடைசி எழுத்து.', 'Last letter of paṭṭāṉ.'),
    ],
  },
  L5: {
    inscription: {
      id: 'mock:mangulam-cave',
      title: 'Mangulam cave inscription (near Madurai)',
      dynasty: 'Pandya',
      approx_date: 'c. 2nd c. BCE',
      source_url: DHARMA,
      restored_text: 'kaṇiy nanta asiriy',
      restored_text_tamil: 'கணிய் நந்த அசிரிய்',
    },
    context: {
      ruler: 'Neṭuñceḻiyaṉ (Pandya)',
      explain_ta: 'மாங்குளம் குகையில் சமணத் துறவிகளுக்குக் கற்படுக்கைகள் கொடையாக வெட்டப்பட்டன. இது தமிழ்-பிராமியின் தொடக்ககாலச் சான்றுகளில் ஒன்று.',
      explain_en: 'Stone beds were cut for Jain monks in the Mangulam caves. It is among the earliest evidence of Tamil-Brahmi.',
    },
    items: [
      letter('L5-1', 'L5', { text: '\u{11013}' }, ['க', 'ka'], 'ஒரு கூட்டல் குறி போல.', 'Looks like a plus sign.'),
      letter('L5-2', 'L5', { text: '\u{11026}' }, ['ந', 'na'], 'நந்த என்பதன் முதல் எழுத்து.', 'First letter of nanta.'),
      letter('L5-3', 'L5', { text: '\u{11005}' }, ['அ', 'a'], 'முதல் உயிர் எழுத்து.', 'The first vowel.'),
      letter('L5-4', 'L5', { text: '\u{11037}' }, ['ன', 'ṉa', 'na'], 'தமிழுக்கென்றே சேர்க்கப்பட்ட பிராமி எழுத்து.', 'A Brahmi letter added for Tamil.'),
    ],
  },
};

/** Ten era letters, two per level, for the pre/post assessment. */
export const ASSESSMENT: MockItem[] = (['L1', 'L2', 'L3', 'L4', 'L5'] as Level[]).flatMap((lv) =>
  LESSONS[lv].items
    .filter((i) => i.type === 'letter')
    .slice(0, 2)
    .map((i) => ({ ...i, item_id: `A-${i.item_id}` })),
);

export { SAMPLE_RESTORE_ISO, SAMPLE_RESTORE_TAMIL } from '../lib/samples';

export const SEED_QUEUE: Schemas['QueueItem'][] = [
  {
    id: 'q-0001',
    gap_ref: { trace_id: 'mock-trace-seed-1', gap_index: 1, left: 'kēcaripaṉmaṟku yāṇṭu ', right: ' āvatu', gap_chars: null, inscription_id: 'mock:uttiramerur-sabha' },
    user: 'restorer-agent (abstained)',
    status: 'pending',
    created_at: '2026-11-01T09:12:00Z',
  },
  {
    id: 'q-0002',
    gap_ref: { trace_id: 'mock-trace-seed-2', gap_index: 0, left: 'svasti śrī matiraikoṇṭa kōp', right: 'kēcaripaṉmaṟku', gap_chars: 4 },
    accepted_candidate: 'para',
    user: 'guide-kanchipuram',
    status: 'pending',
    created_at: '2026-11-01T10:40:00Z',
  },
  {
    id: 'q-0003',
    gap_ref: { trace_id: 'mock-trace-seed-3', gap_index: 0, left: 'kō vicaiya nanti', right: 'parumaṟku', gap_chars: 7 },
    corrected_text: 'vikkirama',
    user: 'student-madurai',
    status: 'pending',
    created_at: '2026-11-01T11:05:00Z',
  },
];
