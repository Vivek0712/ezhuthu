import { useCallback } from 'react';
import { useI18n } from './I18nProvider';

// Strings for the home hero header and the stone hero (HomePage.tsx, StoneHero.tsx). Kept in their own module and
// looked up with useHeroT(), so the hero copy can change without touching the shared strings.ts.
// Placeholders such as {n} are filled by the caller. Numbers are never written here: they come from
// src/hero/hero-view.json (scripts/hero_build.py), and tests/test_hero_assets.py checks that against the runs.

export const enHero = {
  'hero.kicker': 'Old Tamil stones, letter by letter',
  'hero.title': 'Learn to read old Tamil inscriptions.',
  'hero.sub':
    'Practise on real inscriptions, from single letters to whole lines. Or upload a photo: Ezhuthu reads the letters, suggests worn-away ones and shows how sure it is.',

  // Truthful captions for the stone hero (user request 2026-11-02: verify the animation is accurate).
  'sh.boxes': 'Letter boxes marked by hand; the Reader names each letter.',
  'sh.legendNote': '%: the Reader’s own confidence, not a measured accuracy',
  'sh.check': 'Confidence check',
  'sh.checkSub': 'fill or leave open',
  'sh.leftOpen': 'left open',
  'sh.filled': 'filled',
  'sh.cardReader': 'Reader {c} < {cut}',
  'sh.cardFootOpen': 'best fill {fill} {fc} < {thr} · left open',
  'sh.cardFootFilled': 'best fill {fill} {fc} ≥ {thr} · filled',
  'sh.gapOpen':
    'Line {r}: one letter is too worn to be sure ({c}). The best fill scored {fc}, under the {thr} needed, so rather than guess, Ezhuthu marks it ? for an expert.',
  'sh.gapFilled': 'Line {r}: one letter is too worn to be sure ({c}). The best fill, {fill}, scored {fc}, over the {thr} needed, so Ezhuthu filled it.',
  'sh.verdictLetters': '{n} carved letters named in modern Tamil',
  'sh.verdictMean': 'the Reader’s mean confidence ',
} as const;

export type HeroKey = keyof typeof enHero;

// Every Tamil string below is PENDING a native-speaker check.
export const taHero: Record<HeroKey, string> = {
  'hero.kicker': 'பழந்தமிழ்க் கல்வெட்டுகள், எழுத்து எழுத்தாக',
  'hero.title': 'பழைய தமிழ்க் கல்வெட்டுகளைப் படிக்கக் கற்றுக்கொள்ளுங்கள்.',
  'hero.sub':
    'உண்மையான கல்வெட்டுகளில், தனி எழுத்துகள் முதல் முழு வரிகள் வரை பயிற்சி செய்யுங்கள். அல்லது ஒரு ஒளிப்படத்தைப் பதிவேற்றுங்கள்: எழுத்து அதன் எழுத்துகளைப் படித்து, தேய்ந்தவற்றை முன்மொழிந்து, எவ்வளவு உறுதி என்று காட்டுகிறது.',
  'sh.boxes': 'எழுத்துப் பெட்டிகள் கையால் குறிக்கப்பட்டவை; ஒவ்வொரு எழுத்தையும் வாசிப்பாளர் பெயரிடுகிறது.',
  'sh.legendNote': '%: வாசிப்பாளரின் சொந்த நம்பகம்; அளந்த துல்லியம் அல்ல',
  'sh.check': 'நம்பகச் சரிபார்ப்பு',
  'sh.checkSub': 'நிரப்பவா, விடவா',
  'sh.leftOpen': 'நிரப்பப்படவில்லை',
  'sh.filled': 'நிரப்பப்பட்டது',
  'sh.cardReader': 'வாசிப்பாளர் {c} < {cut}',
  'sh.cardFootOpen': 'சிறந்த நிரப்பு {fill} {fc} < {thr} · நிரப்பப்படவில்லை',
  'sh.cardFootFilled': 'சிறந்த நிரப்பு {fill} {fc} ≥ {thr} · நிரப்பப்பட்டது',
  'sh.gapOpen':
    'வரி {r}: ஓர் எழுத்து உறுதியாகச் சொல்ல முடியாத அளவுக்குத் தேய்ந்துள்ளது ({c}). சிறந்த நிரப்பு {fc} மட்டுமே பெற்றது; தேவை {thr}. ஊகிப்பதற்குப் பதிலாக, எழுத்து அதை ஒரு வல்லுநருக்காக ? எனக் குறிக்கிறது.',
  'sh.gapFilled':
    'வரி {r}: ஓர் எழுத்து உறுதியாகச் சொல்ல முடியாத அளவுக்குத் தேய்ந்துள்ளது ({c}). சிறந்த நிரப்பு {fill} {fc} பெற்றது; தேவை {thr}. அதனால் எழுத்து அதை நிரப்பியது.',
  'sh.verdictLetters': '{n} செதுக்கிய எழுத்துகள் தற்காலத் தமிழில் பெயரிடப்பட்டன',
  'sh.verdictMean': 'வாசிப்பாளரின் சராசரி நம்பகம் ',
};

/** Look up a hero string in the current UI language. */
export function useHeroT(): (k: HeroKey) => string {
  const { lang } = useI18n();
  return useCallback((k: HeroKey) => (lang === 'ta' ? taHero : enHero)[k], [lang]);
}
