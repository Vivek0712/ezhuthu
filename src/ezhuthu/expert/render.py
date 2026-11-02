"""Printable bilingual HTML sheets (Tamil first, English second). Print to PDF from any browser, or use
``python -m ezhuthu.expert generate --pdf`` (headless Chrome, which shapes Tamil correctly)."""

from __future__ import annotations

import html
import shutil
import subprocess
from pathlib import Path
from typing import Any

SCALE_TEXT = [
    ("4", "மிகவும் பொருந்தும்: பதிப்பில் ஏற்கத்தக்க வாசிப்பு",
     "Highly plausible: I would accept this reading in an edition"),
    ("3", "பொருந்தும்: சூழலுக்கு ஒத்துவருகிறது; வேறு வாசிப்புகளும் சம அளவில் சாத்தியம்",
     "Plausible: fits the context; other readings are about as likely"),
    ("2", "சாத்தியம் குறைவு: மொழி, நீளம் அல்லது வழக்கமான சொற்றொடரில் சிக்கல் உண்டு",
     "Unlikely: possible only with problems of language, length or formula"),
    ("1", "பொருந்தாது: எழுத்து, மொழி, நீளம் அல்லது சூழல் இதை விலக்குகிறது",
     "Implausible: ruled out by script, language, length or context"),
    ("?", "மதிப்பிட முடியவில்லை (cannot_judge_y = y)", "Cannot judge (write y in cannot_judge_y)"),
]

CSS = """
:root { --ink: #1d1a16; --muted: #5b544a; --line: #c9bfae; --mark: #f3e3b5; --bg: #ffffff; }
* { box-sizing: border-box; }
body { margin: 0; padding: 16px; background: var(--bg); color: var(--ink);
  font: 15px/1.55 "Noto Sans Tamil", "Tamil Sangam MN", "Latha", "Nirmala UI", system-ui, sans-serif; }
main { max-width: 860px; margin: 0 auto; }
h1 { font-size: 1.35rem; margin: 0 0 .25rem; }
h2 { font-size: 1.05rem; margin: 1.2rem 0 .4rem; }
.en { color: var(--muted); }
.iso { font-family: "Noto Sans", "Gentium Plus", "Charis SIL", Georgia, serif; overflow-wrap: anywhere; }
.item { border: 1px solid var(--line); border-radius: 6px; padding: 12px; margin: 14px 0; break-inside: avoid; }
.item header { display: flex; justify-content: space-between; gap: 8px; flex-wrap: wrap; font-weight: 600; }
.ctx { font-size: 1.1rem; margin: .4rem 0 .2rem; overflow-wrap: anywhere; }
.gap { background: var(--mark); padding: 0 .2em; border-radius: 3px; }
table { width: 100%; border-collapse: collapse; margin-top: .4rem; }
th, td { border-top: 1px solid var(--line); padding: 6px 4px; text-align: left; vertical-align: top; }
td.box { width: 7.5rem; white-space: nowrap; }
td.box span { display: inline-block; width: 1.4rem; height: 1.4rem; border: 1px solid var(--ink);
  margin-right: 2px; text-align: center; font-size: .8rem; line-height: 1.35rem; }
.answer { border-bottom: 1px solid var(--ink); min-height: 2rem; margin: .4rem 0; }
.small { font-size: .85rem; }
a { color: inherit; overflow-wrap: anywhere; }
@media print { body { padding: 0; font-size: 12.5px; } .item { page-break-inside: avoid; } a { text-decoration: none; } }
"""


def _e(s: Any) -> str:
    return html.escape(str(s), quote=True)


def _page(title: str, body: str) -> str:
    return (f'<!doctype html>\n<html lang="ta"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f"<title>{_e(title)}</title><style>{CSS}</style></head><body><main>{body}</main></body></html>\n")


def _ctx_html(text: str) -> str:
    return _e(text).replace("⟦", '<span class="gap">⟦').replace("⟧", "⟧</span>")


def _scale_html() -> str:
    rows = "".join(f"<tr><td><b>{v}</b></td><td>{_e(ta)}<br><span class='en'>{_e(en)}</span></td></tr>"
                   for v, ta, en in SCALE_TEXT)
    return f"<table class='small'>{rows}</table>"


def rating_html(key: dict[str, Any], rater: str, rows: list[dict[str, str]]) -> str:
    n = key["meta"]["n_rating"]
    k = key["meta"]["options_per_item"]
    intro = f"""
<h1>எழுத்து: சிதைந்த கல்வெட்டுப் பகுதிகளுக்கான வாசிப்பு மதிப்பீடு
<br><span class="en">Ezhuthu: rating proposed readings for damaged inscription passages</span></h1>
<p class="small">மதிப்பீட்டாளர் / Rater: <b>{_e(rater)}</b> · {n} பகுதிகள் / passages · ஒவ்வொன்றிலும் {k} முன்மொழிவுகள் /
{k} proposals each</p>
<h2>வழிமுறை <span class="en">/ Instructions</span></h2>
<ol class="small">
<li>ஒவ்வொரு பகுதியிலும் ⟦…⟧ என்பது இழந்த எழுத்துகள்; எண் என்பது பதிப்பில் குறிக்கப்பட்ட தோராயமான எழுத்து எண்ணிக்கை
(உயிர், மெய், உயிர்மெய் ஒவ்வொன்றும் ஒரு எழுத்து).
<span class="en">⟦…⟧ marks lost text; the number is the approximate count of aksharas given in the edition. An akshara
is one Tamil letter: a vowel (uyir), a consonant with puḷḷi (mey), or a consonant with its vowel (uyirmey),
so <i>kā</i> is 1 and <i>nāḷ</i> is 2.</span></li>
<li>முன்மொழிவுகள் வெவ்வேறு மூலங்களிலிருந்து (மனிதர்களும் மென்பொருளும்) கலந்து, சீரற்ற வரிசையில் தரப்பட்டுள்ளன. எந்த மூலம் என்று ஊகிக்க வேண்டாம்;
ஒவ்வொன்றையும் தனித்தனியாக மதிப்பிடுங்கள். <span class="en">Proposals come from several sources (people and software),
mixed and in random order. Do not guess the source; rate each one on its own.</span></li>
<li>ஒவ்வொரு முன்மொழிவுக்கும் 1 முதல் 4 வரை ஒரு மதிப்பெண் தாருங்கள் (கீழே). பல முன்மொழிவுகளுக்கு ஒரே மதிப்பெண் தரலாம்.
<span class="en">Give each proposal one score from 1 to 4 (below). Several proposals may get the same score.</span></li>
<li>மூல இணைப்பை (DHARMA பதிப்பு) மதிப்பிட்ட <b>பிறகே</b> திறக்கவும். முன்பே திறந்தால் அல்லது இந்தக் கல்வெட்டை முன்பே அறிந்திருந்தால் y எனக் குறிக்கவும்.
<span class="en">Open the source link (the DHARMA edition) only <b>after</b> rating. If you opened it before, or already
know this inscription, mark y; those ratings are analysed separately, not discarded.</span></li>
<li>மின்னணு வழியில் நிரப்ப CSV கோப்பைப் பயன்படுத்துங்கள்; அச்சுப் படிவத்தில் கட்டங்களை வட்டமிடுங்கள்.
<span class="en">Fill in the CSV file, or circle the boxes on this printed form.</span></li>
</ol>
<h2>மதிப்பெண் அளவுகோல் <span class="en">/ Scale</span></h2>
{_scale_html()}
"""
    blocks: list[str] = []
    by_item: dict[str, list[dict[str, str]]] = {}
    for r in rows:
        by_item.setdefault(r["item_code"], []).append(r)
    for code, opts in by_item.items():
        first = opts[0]
        trs = "".join(
            f"<tr><td><b>{_e(o['option'])}</b></td>"
            f"<td>{_e(o['proposal_tamil'])}<br><span class='iso'>{_e(o['proposal_iso'])}</span>"
            f"<br><span class='small en'>{_ctx_html(o['line_with_proposal_tamil'])}</span></td>"
            f"<td class='box'><span>1</span><span>2</span><span>3</span><span>4</span><span>?</span></td></tr>"
            for o in opts)
        blocks.append(f"""
<section class="item" id="{_e(code)}">
<header><span>{_e(code)}</span><span class="small">⟦…⟧ ≈ {_e(first['gap_aksharas'])} எழுத்துகள் / aksharas</span></header>
<p class="ctx">{_ctx_html(first['context_tamil'])}</p>
<p class="iso small">{_ctx_html(first['context_iso'])}</p>
<table><thead><tr><th></th><th>முன்மொழிவு <span class="en">/ proposal</span></th>
<th>மதிப்பெண் <span class="en">/ score</span></th></tr></thead><tbody>{trs}</tbody></table>
<p class="small">☐ மதிப்பிடும் முன் பதிப்பைப் பார்த்தேன் / consulted the edition before rating
&nbsp; ☐ இந்தக் கல்வெட்டை முன்பே அறிவேன் / I knew this text</p>
<p class="small">மூலம் (மதிப்பிட்ட பின் மட்டும்) / Source (only after rating):
<a href="{_e(first['source_url'])}">{_e(first['source_url'])}</a></p>
<p class="small">குறிப்பு / Comment:</p><div class="answer"></div>
</section>""")
    foot = ("<p class='small en'>Text: DHARMA project editions, CC BY-SA 4.0 (see each source link). "
            "Tamil script rendered from the ISO-15919 edition text.</p>")
    return _page(f"Ezhuthu rating sheet {rater}", intro + "".join(blocks) + foot)


def reading_html(key: dict[str, Any], rater: str, form: str, rows: list[dict[str, str]]) -> str:
    intro = f"""
<h1>எழுத்து: இழந்த எழுத்துகளை மீட்டெடுத்தல் (வாசிப்பு ஆய்வு)
<br><span class="en">Ezhuthu: restoring lost letters (reading study)</span></h1>
<p class="small">மதிப்பீட்டாளர் / Rater: <b>{_e(rater)}</b> · படிவம் / Form {_e(form)}</p>
<h2>வழிமுறை <span class="en">/ Instructions</span></h2>
<ol class="small">
<li>ஒவ்வொரு பகுதியிலும் ⟦…⟧ இடத்தில் இழந்த எழுத்துகளை உங்கள் வாசிப்பாக எழுதுங்கள் (தமிழ் எழுத்து அல்லது ISO-15919).
<span class="en">Write your restoration of the lost letters ⟦…⟧ (Tamil script or ISO-15919). The number in ⟦…⟧ is the
approximate count of aksharas (one Tamil letter: uyir, mey or uyirmey). Tamil script and ISO-15919 are scored
alike: Tamil script does not mark voicing or aspiration (க = k/g, த = t/d/dh), so the scoring ignores them in both scripts.</span></li>
<li>பகுதி 1 இல் உதவி இல்லை. பகுதி 2 இல் மென்பொருள் பரிந்துரைகள் (நம்பக மதிப்புடன்) தரப்பட்டுள்ளன; அவற்றை ஏற்கலாம், மாற்றலாம், புறக்கணிக்கலாம்.
<span class="en">Block 1 is unaided. Block 2 shows software suggestions with their confidence; use, change or ignore
them.</span> பகுதி 1 ஐ முடித்த பின்னரே பகுதி 2 ஐப் பாருங்கள். <span class="en">Finish block 1 before looking at block 2.</span></li>
<li>ஒவ்வொரு பகுதிக்கும் எடுத்த நேரத்தை (வினாடிகளில்) மற்றும் உங்கள் நம்பிக்கையை (1 = ஊகம், 4 = உறுதி) எழுதுங்கள்.
<span class="en">Note the time taken (seconds) and your confidence (1 = guess, 4 = certain).</span></li>
<li>பதிலை எழுதிய பிறகே மூல இணைப்பைத் திறக்கவும். <span class="en">Open the source link only after answering.</span></li>
</ol>
"""
    blocks: list[str] = []
    current_block = None
    for r in rows:
        if r["block"] != current_block:
            current_block = r["block"]
            title = ("பகுதி 1: உதவி இல்லாமல் / Block 1: unaided" if r["condition"] == "unaided"
                     else "பகுதி 2: மென்பொருள் பரிந்துரைகளுடன் / Block 2: with software suggestions")
            blocks.append(f"<h2>{_e(title)}</h2>")
        sugg = ""
        if r["condition"] == "ai_assisted":
            sugg = (f"<p class='small'>பரிந்துரைகள் / Suggestions: {_e(r['ai_suggestions_tamil'])}"
                    f"<br><span class='iso'>{_e(r['ai_suggestions_iso'])}</span></p>")
        blocks.append(f"""
<section class="item" id="{_e(r['item_code'])}">
<header><span>{_e(r['item_code'])}</span><span class="small">⟦…⟧ ≈ {_e(r['gap_aksharas'])} எழுத்துகள் / aksharas</span></header>
<p class="ctx">{_ctx_html(r['context_tamil'])}</p>
<p class="iso small">{_ctx_html(r['context_iso'])}</p>
{sugg}
<p class="small">உங்கள் வாசிப்பு / Your restoration:</p><div class="answer"></div>
<p class="small">நம்பிக்கை / Confidence: 1 2 3 4 &nbsp; · &nbsp; நேரம் / Seconds: ______
&nbsp; ☐ முன்பே பதிப்பைப் பார்த்தேன் / consulted the edition first &nbsp; ☐ முன்பே அறிவேன் / knew this text</p>
<p class="small">மூலம் (பதிலுக்குப் பின்) / Source (after answering): <a href="{_e(r['source_url'])}">{_e(r['source_url'])}</a></p>
</section>""")
    return _page(f"Ezhuthu reading study {rater}", intro + "".join(blocks))


def find_chrome() -> str | None:
    for c in ("google-chrome", "chromium", "chromium-browser", "chrome"):
        p = shutil.which(c)
        if p:
            return p
    mac = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    return str(mac) if mac.exists() else None


def html_to_pdf(src: Path, dst: Path, *, chrome: str | None = None, timeout: int = 120) -> Path:
    """Print an HTML sheet to PDF with headless Chrome. Raises RuntimeError when Chrome is missing."""
    exe = chrome or find_chrome()
    if not exe:
        raise RuntimeError("no Chrome/Chromium found: print the HTML sheet to PDF from a browser instead")
    subprocess.run([exe, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={dst}", src.resolve().as_uri()],
                   check=True, capture_output=True, timeout=timeout)
    if not dst.exists() or dst.stat().st_size == 0:
        raise RuntimeError(f"Chrome produced no PDF for {src}")
    return dst
