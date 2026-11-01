import type { PracticeItem } from '../api/client';
import { levelInfo } from '../lib/levels';
import { svgDataUrl } from '../lib/format';

export function GlyphTile({ item, label }: { item: PracticeItem; label: string }) {
  const info = levelInfo(item.script_level);
  return (
    <div className="tile" data-testid="glyph-tile" data-level={item.script_level}>
      {item.glyph_svg ? (
        // Server SVG is rendered as an image so any embedded script can never execute.
        <img src={svgDataUrl(item.glyph_svg)} alt={label} />
      ) : (
        <span className={`tile-glyph ${info.fontClass} ${item.type !== 'letter' ? 'word' : ''}`} aria-label={label} role="img">
          {item.glyph_text}
        </span>
      )}
    </div>
  );
}
