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
    assert not _svg(tmp_path, '<g mask="url(#m)"><path d="M0 0H1920V1080"/></g>')


def test_transformed_artwork_is_reported_not_skipped(tmp_path):
    assert _svg(tmp_path, '<g transform="translate(10 0)"><path d="M300 300H400"/></g>')


def test_other_banners_use_a_4_percent_safe_area(tmp_path):
    assert _svg(tmp_path, '<path d="M1500 600H1558V700"/>', 1600, 900, "banners")  # old Builder header strip
    assert not _svg(tmp_path, '<path d="M110 600H1490V700"/>', 1600, 900, "banners")


def test_committed_design_passes():
    assert check_design.main() == 0
