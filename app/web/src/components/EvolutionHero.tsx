import { useI18n } from '../i18n/I18nProvider';
import { LEVELS } from '../lib/levels';
import { VATTELUTTU } from '../lib/vatteluttu';

interface Node {
  level: 'L5' | 'L3' | 'L2' | 'L1' | 'L4';
  x: number;
  y: number;
  delay: number;
}
// Main line (top): Tamil-Brahmi -> Pallava -> Chola -> modern. Vatteluttu branches off below.
const NODES: Node[] = [
  { level: 'L5', x: 70, y: 110, delay: 0.1 },
  { level: 'L3', x: 205, y: 110, delay: 0.5 },
  { level: 'L2', x: 340, y: 110, delay: 0.9 },
  { level: 'L1', x: 480, y: 110, delay: 1.3 },
  { level: 'L4', x: 270, y: 262, delay: 1.7 },
];
const T = 46; // half tile

export function EvolutionHero() {
  const { lang, t } = useI18n();
  return (
    <figure className="evo leaf evo-card" style={{ margin: 0 }}>
      <svg viewBox="0 0 560 340" role="img" aria-labelledby="evo-title" data-testid="evolution-hero">
        <title id="evo-title">{t('home.heroCaption')}</title>
        <path className="evo-line evo-draw" d={`M${70 + T} 110 H${205 - T} M${205 + T} 110 H${340 - T} M${340 + T} 110 H${480 - T}`} />
        <path className="evo-line evo-draw" d={`M70 ${110 + T} C70 230 140 262 ${270 - T} 262`} style={{ animationDelay: '1.2s' }} />
        {NODES.map((n) => {
          const info = LEVELS.find((l) => l.id === n.level)!;
          const below = n.level !== 'L4';
          return (
            <g key={n.level} className="evo-pop" style={{ animationDelay: `${n.delay}s` }}>
              <rect className="evo-tile" x={n.x - T} y={n.y - T} width={T * 2} height={T * 2} rx={16} />
              {info.sampleKa ? (
                <text
                  className={`evo-glyph ${info.fontClass}`}
                  x={n.x}
                  y={n.y + 2}
                  textAnchor="middle"
                  dominantBaseline="central"
                  fontSize={info.id === 'L5' ? 50 : 54}
                >
                  {info.sampleKa}
                </text>
              ) : (
                <g transform={`translate(${n.x - 32} ${n.y - 32}) scale(0.64)`}>
                  <path className="evo-stroke" d={VATTELUTTU.ka!.d} strokeWidth={8} strokeLinecap="round" strokeLinejoin="round" />
                </g>
              )}
              <text className="evo-era" x={below ? n.x : n.x + T + 12} y={below ? n.y + T + 20 : n.y - 6} textAnchor={below ? 'middle' : 'start'}>
                {n.level}
              </text>
              <text
                className="evo-label"
                x={below ? n.x : n.x + T + 12}
                y={below ? n.y + T + 38 : n.y + 12}
                textAnchor={below ? 'middle' : 'start'}
              >
                {lang === 'ta' ? info.shortTa : info.shortEn}
              </text>
              <text
                className="evo-label"
                x={below ? n.x : n.x + T + 12}
                y={below ? n.y + T + 54 : n.y + 28}
                textAnchor={below ? 'middle' : 'start'}
                style={{ fontSize: 11 }}
              >
                {lang === 'ta' ? info.eraTa.replace(' (ஏறத்தாழ)', '') : info.eraEn}
              </text>
            </g>
          );
        })}
      </svg>
      <figcaption>{t('home.heroCaption')}</figcaption>
    </figure>
  );
}
