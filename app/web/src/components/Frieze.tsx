// A carved course of letters from four scripts. Decorative only.
const LETTERS = [
  ...'𑀓𑀦𑀢𑀫𑀬𑀭𑀮𑀯𑀅𑀷𑀵𑀶'.match(/./gu)!.map((c) => ({ c, cls: 'script-brahmi' })),
  ...'𑌕𑌨𑌤𑌮𑌯𑌰𑌲𑌵'.match(/./gu)!.map((c) => ({ c, cls: 'script-grantha' })),
  ...'கஙசஞடணதநபமயரலவழளறன'.match(/./gu)!.map((c) => ({ c, cls: 'script-chola' })),
];

export function Frieze() {
  const run = [...LETTERS, ...LETTERS];
  return (
    <div className="frieze" aria-hidden="true">
      <div className="frieze-track">
        {run.map((l, i) => (
          <span key={i} className={l.cls}>
            {l.c}
          </span>
        ))}
      </div>
    </div>
  );
}
