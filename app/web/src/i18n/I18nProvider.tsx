import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { en, ta, type MessageKey } from './strings';

export type Lang = 'ta' | 'en';
// v2: the default changed from Tamil to English, so a value stored under the old key (written on
// every first visit, not only by an explicit choice) must not keep returning visitors in Tamil.
const STORAGE_KEY = 'ezhuthu.lang.v2';

function readStoredLang(): Lang {
  try {
    const v = window.localStorage.getItem(STORAGE_KEY);
    return v === 'en' || v === 'ta' ? v : 'en';
  } catch {
    return 'en';
  }
}

interface I18n {
  lang: Lang;
  setLang: (l: Lang) => void;
  toggle: () => void;
  t: (key: MessageKey) => string;
  /** Pick between a Tamil and an English value that came from the API. */
  pick: (taText: string | undefined | null, enText: string | undefined | null) => string;
}

const Ctx = createContext<I18n | null>(null);

export function I18nProvider({ children, initial }: { children: ReactNode; initial?: Lang }) {
  const [lang, setLangState] = useState<Lang>(() => initial ?? readStoredLang());

  useEffect(() => {
    document.documentElement.lang = lang;
    try {
      window.localStorage.setItem(STORAGE_KEY, lang);
    } catch {
      /* storage blocked: the toggle still works for this page view */
    }
  }, [lang]);

  const setLang = useCallback((l: Lang) => setLangState(l), []);
  const toggle = useCallback(() => setLangState((l) => (l === 'ta' ? 'en' : 'ta')), []);
  const value = useMemo<I18n>(() => {
    const dict = lang === 'ta' ? ta : en;
    return {
      lang,
      setLang,
      toggle,
      t: (key) => dict[key],
      pick: (taText, enText) => (lang === 'ta' ? taText || enText || '' : enText || taText || ''),
    };
  }, [lang, setLang, toggle]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useI18n(): I18n {
  const v = useContext(Ctx);
  if (!v) throw new Error('useI18n outside I18nProvider');
  return v;
}
