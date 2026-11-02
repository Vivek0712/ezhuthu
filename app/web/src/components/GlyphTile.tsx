import type { PracticeItem } from '../api/client';
import { useI18n } from '../i18n/I18nProvider';
import { levelInfo } from '../lib/levels';
import { svgDataUrl } from '../lib/format';
import { glyphRef, VATTELUTTU_STROKE } from '../lib/vatteluttu';

/** Glyph card well (design/glyphs/GLYPH-CARD.md): era chip, then the letter. The label never names the answer. */
export function GlyphTile({ item, label }: { item: PracticeItem; label: string }) {
  const { lang } = useI18n();
  const info = levelInfo(item.script_level);
  const ref = glyphRef(item.glyph_svg);
  const era = `${info.id} · ${lang === 'ta' ? info.nameTa : info.nameEn}`;
  return (
    <div className="tile" data-testid="glyph-tile" data-level={item.script_level}>
      <span className="tile-era" aria-hidden="true">
        {era}
      </span>
      {ref ? (
        // A reference into the design system's drawings: drawn inline from our own paths, in the text colour.
        <svg className="tile-svg" viewBox={`0 0 ${100 * ref.length} 100`} role="img" aria-label={`${era}: ${label}`} data-testid="glyph-ref">
          <g fill="none" stroke="currentColor" strokeWidth={VATTELUTTU_STROKE} strokeLinecap="round" strokeLinejoin="round">
            {ref.map((g, i) => (
              <path key={i} transform={`translate(${100 * i} 0)`} d={g.d} />
            ))}
          </g>
        </svg>
      ) : item.glyph_svg ? (
        // Server SVG markup is rendered as an image so any embedded script can never execute.
        <img src={svgDataUrl(item.glyph_svg)} alt={`${era}: ${label}`} />
      ) : (
        <span className={`tile-glyph ${info.fontClass} ${item.type !== 'letter' ? 'word' : ''}`} aria-label={`${era}: ${label}`} role="img">
          {item.glyph_text}
        </span>
      )}
    </div>
  );
}
