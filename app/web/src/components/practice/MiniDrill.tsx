import { useCallback, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useI18n } from '../../i18n/I18nProvider';
import { isRight, shuffled } from '../../practice/engine';
import { recordAnswer } from '../../practice/progress';
import tryBank from '../../practice/banks/try.json';
import type { Item, LetterItem, WordItem } from '../../practice/types';
import { QuestionCard } from './QuestionCard';

// Easy letters first, then short words; shuffled once per visit so a returning visitor gets a different first one.
const ITEMS: Item[] = [
  ...(tryBank.letters as Omit<LetterItem, 'kind'>[]).map((i) => ({ ...i, kind: 'letters' as const })),
  ...(tryBank.words as Omit<WordItem, 'kind'>[]).map((i) => ({ ...i, kind: 'words' as const })),
];

/** "Try one now": a visitor answers a real question within seconds of landing, with no network call. */
export function MiniDrill({ seed }: { seed: number }) {
  const { t } = useI18n();
  const order = useMemo(() => {
    const letters = shuffled(ITEMS.filter((i) => i.kind === 'letters'), seed);
    const words = shuffled(ITEMS.filter((i) => i.kind === 'words'), seed + 1);
    // letter, letter, word, letter, ...
    const out: Item[] = [];
    while (letters.length || words.length) {
      for (const src of [letters, letters, words]) {
        const x = src.shift();
        if (x) out.push(x);
      }
    }
    return out;
  }, [seed]);
  const [idx, setIdx] = useState(0);
  const [choice, setChoice] = useState<number | null | undefined>(undefined);
  const item = order[idx % order.length]!;

  const choose = useCallback(
    (i: number) => {
      if (choice !== undefined) return;
      setChoice(i);
      recordAnswer(item.kind, { id: item.id, level: item.level, right: isRight(item, i) });
    },
    [choice, item],
  );

  return (
    <div className="mini-drill" data-testid="mini-drill">
      <QuestionCard
        key={`${item.id}:${idx}`}
        item={item}
        choice={choice}
        onChoose={choose}
        keys={false}
        compact
        footer={
          choice !== undefined && (
            <div className="row">
              <button
                className="btn btn-primary btn-small"
                type="button"
                autoFocus
                onClick={() => {
                  setIdx((i) => i + 1);
                  setChoice(undefined);
                }}
                data-testid="mini-next"
              >
                {t('home2.tryNext')}
              </button>
              <Link className="hero-link" to="/practice">
                {t('home2.tryAll')} →
              </Link>
            </div>
          )
        }
      />
    </div>
  );
}
