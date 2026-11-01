"""Regression tests for design/tools/check_design.py's banner safe-area check (QA finding on PR #13:
video card 01's Tamil headline ran off the 1920 px frame)."""
from __future__ import annotations

import importlib.util
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("check_design", ROOT / "design" / "tools" / "check_design.py")
check_design = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_design)


def _svg(tmp_path: Path, body: str, w: int = 1920, h: int = 1080, sub: str = "video") -> list[str]:
    d = tmp_path / sub
    d.mkdir(exist_ok=True)
    p = d / "card.svg"
    p.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}">'
                 f'<rect width="{w}" height="{h}" fill="#000"/>{body}</svg>')
    return check_design.overflow(p, ET.parse(p).getroot())


def test_headline_past_frame_fails(tmp_path):
    # the clipped 01-problem headline: outlined text from x=145 to x=2076 on a 1920 frame
    assert _svg(tmp_path, '<path d="M145 587L2076 587L2076 687Z"/>')


def test_video_card_side_margin_is_140(tmp_path):
    assert _svg(tmp_path, '<path d="M140 500H1790V600"/>')  # inside the frame but past the 140 px margin
    assert not _svg(tmp_path, '<path d="M140 500H1780V600"/>')


def test_rects_and_circles_are_checked_but_backgrounds_and_masks_are_not(tmp_path):
    assert _svg(tmp_path, '<rect x="1500" y="600" width="300" height="80"/>')
    assert _svg(tmp_path, '<circle cx="1900" cy="500" r="10"/>')
    assert not _svg(tmp_path, '<g mask="url(#fieldmask)"><path d="M0 0H1920V1080"/></g>')


def test_transformed_artwork_is_reported_not_skipped(tmp_path):
    assert _svg(tmp_path, '<g transform="translate(10 0)"><path d="M300 300H400"/></g>')


def test_other_banners_use_a_4_percent_safe_area(tmp_path):
    assert _svg(tmp_path, '<path d="M1500 600H1558V700"/>', 1600, 900, "banners")  # old Builder header strip
    assert not _svg(tmp_path, '<path d="M110 600H1490V700"/>', 1600, 900, "banners")


def test_unmeasurable_elements_are_reported_not_skipped(tmp_path):
    # QA on #20: <text x="1900"> on a 1600-wide banner used to pass silently
    assert _svg(tmp_path, '<text x="1900" y="400">Ezhuthu</text>', 1600, 900, "banners")
    assert _svg(tmp_path, '<text x="400" y="400">ok</text>', 1600, 900, "banners")  # any text: outline it
    assert _svg(tmp_path, '<use href="#x"/>', 1600, 900, "banners")


def test_lines_ellipses_polys_and_images_are_measured(tmp_path):
    for el in ('<line x1="100" y1="400" x2="1590" y2="400"/>', '<ellipse cx="1550" cy="400" rx="40" ry="10"/>',
               '<polygon points="100,400 1590,400 800,500"/>', '<polyline points="100 400 1590 400"/>',
               '<image x="1500" y="400" width="90" height="90"/>'):
        assert _svg(tmp_path, el, 1600, 900, "banners"), el
    assert not _svg(tmp_path, '<polyline points="100 400 1500 400"/>', 1600, 900, "banners")


def test_only_the_texture_mask_is_exempt(tmp_path):
    # QA on #20: any ancestor mask= used to exempt its whole subtree
    assert _svg(tmp_path, '<g mask="url(#headline)"><path d="M1000 500H2500"/></g>', 1600, 900, "banners")
    assert not _svg(tmp_path, '<g mask="url(#fieldmask)"><path d="M0 0H1600V900"/></g>', 1600, 900, "banners")


def test_percentage_lengths_resolve_against_the_viewbox(tmp_path):
    # QA on #20: width="50%" used to crash the checker with ValueError
    assert not _svg(tmp_path, '<rect x="100" y="100" width="50%" height="50%"/>', 1600, 900, "banners")
    assert _svg(tmp_path, '<rect x="900" y="100" width="50%" height="10%"/>', 1600, 900, "banners")
    assert _svg(tmp_path, '<rect x="100" y="100" width="wide" height="10"/>', 1600, 900, "banners")  # reported


def test_stroke_width_counts_toward_bounds(tmp_path):
    assert not _svg(tmp_path, '<path d="M142 880h116"/>')
    assert not _svg(tmp_path, '<path d="M142 880h116" stroke="#000" stroke-width="4"/>')
    assert _svg(tmp_path, '<path d="M140 880h120" stroke="#000" stroke-width="4"/>')  # the old video-card rule
    assert _svg(tmp_path, '<g stroke="#000" stroke-width="10"><path d="M140 880h120"/></g>')  # inherited


def test_classification_ignores_directories_above_design(tmp_path):
    # QA on #20: 'video' anywhere in the absolute path switched every banner to the 140 px rule
    root = tmp_path / "video" / "clone"
    assert check_design.design_parts(check_design.DESIGN / "brand" / "banners" / "og-image.svg") == \
        ("brand", "banners", "og-image.svg")
    assert "video" not in check_design.design_parts(root / "banners" / "og.svg")[:-1]
    assert _svg(tmp_path, '<path d="M110 600H1490V700"/>', 1600, 900, "video")  # a real video card: 140 px
    assert not _svg(tmp_path, '<path d="M110 600H1490V700"/>', 1600, 900, "banners")


def test_committed_design_passes():
    assert check_design.main() == 0
