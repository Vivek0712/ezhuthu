#!/usr/bin/env python3
"""Generate the HTML sources for every blog figure (blog/img/*.png).

Every number here is copied from media/FACTS.md (fact IDs in comments) or read from the repo files that FACTS.md
cites (benchmark/stats.json, app/web/src/benchmark/summary.json, ontology-slice.json, hero-evolution.json).
Run: python3 blog/figures/gen.py && node blog/figures/render.cjs && python3 blog/figures/gen.py --shrink
(--shrink palette-quantises any PNG over 2 MB, the Builder Center upload limit, and writes a JPEG copy of each
photographic image in JPEG_COPIES: a photo stored as PNG is several times larger than it needs to be.)
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent  # worktree root
OUT = HERE / "html"
SHOTS = Path(os.environ.get("SHOTS_DIR", "/Users/vivekrajaps/tamil-script/ezhuthu-video/blog-shots"))
FONTDIR = os.environ.get(
    "FONTDIR", "file:///Users/vivekrajaps/tamil-script/ezhuthu/app/web/node_modules/@fontsource"
)
LOGO = (ROOT / "design/brand/logo").as_uri()

CSS = (HERE / "fig.css").read_text().replace("FONTDIR", FONTDIR)

C = dict(
    stone100="#F4EEE2", stone50="#FBF8F1", stone200="#EAE1CE", stone300="#DACDB4", stone400="#BFAE8F",
    stone500="#9A896C", stone600="#76674F", stone700="#564A3A", ink="#1D1611",
    lat600="#9B3D22", lat500="#B5502F", lat400="#D9764F", lat300="#EBA07F", lat100="#F7E0D5",
    lamp500="#D2891C", lamp400="#EAA43A", lamp300="#F5C468", lamp200="#FBDFA6", lamp700="#8A5508",
    neem700="#2C6534", neem100="#DEEBD7", neem300="#93D09C", neelam700="#3B4787", neelam100="#E3E5F4", neelam300="#AEB8EC",
    palm100="#F5EACB", palm300="#DCC07D", palm500="#B28C42",
    g950="#13100D", g900="#1B1713", g850="#231E18", g800="#2D261F", g700="#40362B",
)


def page(name: str, body: str, *, w: int = 1600, h: int | None = 900, theme: str = "light", extra_css: str = "") -> None:
    size = f"width:{w}px;" + (f"height:{h}px;" if h else "")
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{name}</title>
<style>{CSS}
{extra_css}</style></head><body><div id="fig" class="{theme}" style="{size}">{body}</div></body></html>"""
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.html").write_text(html)


def head(kicker: str, title: str, dek: str = "") -> str:
    d = f'<p class="dek">{dek}</p>' if dek else ""
    return f'<header class="fh"><div class="kicker">{kicker}</div><h1>{title}</h1>{d}</header>'


def foot(src: str, theme: str = "light") -> str:
    logo = "lockup-horizontal-reversed.svg" if theme == "dark" else "lockup-horizontal-color.svg"
    return f'<footer class="ff"><img src="{LOGO}/{logo}" alt=""><div class="src">{src}</div></footer>'


def fmt(n: int) -> str:
    return f"{n:,}"


# ---------------------------------------------------------------------------------------------------------------
# Part 1
# ---------------------------------------------------------------------------------------------------------------

def p1_01_at_a_glance() -> None:
    # P6 1,320 inscriptions; S2 1,469 practice items, P4 5 levels; A1 0.6271 = 259/413; A7 90.8% = 187/206
    tiles = [
        ("1,320", "DHARMA inscriptions parsed", "18,066 lines from 14 pinned DHARMA repositories", "lamp"),
        ("1,469", "practice items", "letters, words, gaps and formulas across five script levels, Tamil first", "lamp"),
        ("62.7%", "of held-out TEST gaps match the editors' restoration", "259 of 413 gaps, first proposal, scored once; the pre-rank version, before the switch to the fine-tuned decision model", "lat"),
        ("90.8%", "of committed fills match", "187 of 206 fills on TEST; below its calibrated threshold it abstains", "lat"),
    ]
    cards = "".join(
        f'<div class="tile {k}"><div class="big">{b}</div><div class="lab">{l}</div><div class="sub">{s}</div></div>'
        for b, l, s, k in tiles
    )
    css = """
.tiles{position:absolute;left:72px;right:72px;top:300px;display:grid;grid-template-columns:repeat(4,1fr);gap:24px}
.tile{border-radius:22px;padding:34px 30px 30px;background:linear-gradient(180deg,rgba(255,255,255,.06),rgba(255,255,255,.015));
 border:1px solid rgba(245,196,104,.22);box-shadow:0 30px 60px -30px rgba(0,0,0,.8);min-height:380px}
.tile.lat{border-color:rgba(235,160,127,.35)}
.big{font:800 92px/1 var(--serif);letter-spacing:-.02em;color:var(--lamp-300)}
.tile.lat .big{color:var(--lat-300)}
.lab{font:700 25px/1.25 var(--sans);margin-top:22px;color:#F3EADA}
.sub{font:400 18px/1.45 var(--sans);margin-top:14px;color:#C9BBA3}
.tag{position:absolute;left:72px;right:72px;top:720px;display:flex;gap:14px;flex-wrap:wrap}
.tag span{font:600 17px/1 var(--sans);padding:11px 16px;border-radius:999px;border:1px solid rgba(243,234,218,.22);color:#E9DCC6}
"""
    body = head("Ezhuthu at a glance", "A real corpus. A real benchmark. <em>Real results.</em>",
                "An apprenticeship in Tamil epigraphy, built with Strands Agents and running on Amazon Bedrock AgentCore.")
    body += f'<div class="tiles">{cards}</div>'
    body += ('<div class="tag"><span>Learn to read the stone. Help read the backlog.</span>'
             '<span>Claude Sonnet 4.6 + Claude Opus 4.6 on Amazon Bedrock</span><span>Split by inscription, TEST scored once</span></div>')
    body += foot("Sources: benchmark/DATA_CARD.md, app/web/src/practice/banks/summary.json, eval/reports/2026-11-02-deployed-config.md. "
                 "Inscription texts: DHARMA, CC BY-SA 4.0.", "dark")
    page("p1-01-at-a-glance", body, theme="dark", extra_css=css)


def p1_02_letter_evolution() -> None:
    data = json.loads((ROOT / "design/glyphs/hero-evolution.json").read_text())
    stages = {s["key"]: s for s in data["stages"]}
    order = ["modern", "chola", "pallava", "vatteluttu", "brahmi"]
    cards = []
    for i, k in enumerate(order):
        s = stages[k]
        if s["kind"] == "stroke":
            glyph = f'<path d="{s["d"]}" fill="none" stroke="{C["ink"]}" stroke-width="{data["stroke"]}" stroke-linecap="round" stroke-linejoin="round"/>'
        else:
            glyph = f'<path d="{s["d"]}" fill="{C["ink"]}"/>'
        note = ""
        if k == "vatteluttu":
            note = '<div class="note">drawn teaching shape, pending an epigrapher\'s review</div>'
        elif k == "pallava":
            note = '<div class="note">shown in the Grantha form, its closest Unicode relative</div>'
        hl = " hl" if k == "modern" else ""
        cards.append(
            f'<div class="card{hl}"><div class="lvl">{s["level"]}</div><svg viewBox="0 0 100 100" class="g">{glyph}</svg>'
            f'<div class="nm">{s["en"]}</div><div class="nmta">{s["ta"]}</div><div class="per">{s["period_en"]}</div>{note}</div>'
        )
        if i < len(order) - 1:
            cards.append('<div class="arr"><svg viewBox="0 0 40 24" width="40" height="24"><path d="M2 12H34M26 4l9 8-9 8" fill="none" stroke="#9B3D22" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg></div>')
    css = """
.row{position:absolute;left:60px;right:60px;top:300px;display:flex;align-items:stretch;justify-content:space-between}
.card{width:262px;background:var(--stone-50);border:1px solid var(--stone-300);border-radius:22px;padding:22px 20px 24px;text-align:center;
 box-shadow:0 1px 0 rgba(255,255,255,.7) inset,0 18px 36px -24px rgba(60,35,10,.5);position:relative}
.card.hl{border-color:var(--lat-600);box-shadow:0 0 0 3px rgba(155,61,34,.12),0 18px 36px -24px rgba(60,35,10,.5)}
.lvl{position:absolute;top:16px;left:16px;font:700 14px/1 var(--sans);letter-spacing:.08em;color:var(--lat-600);background:var(--lat-100);padding:6px 9px;border-radius:999px}
.g{width:190px;height:190px;margin:22px auto 8px;display:block;background:radial-gradient(circle at 50% 45%,#fff 0%,var(--stone-100) 72%);border-radius:50%}
.nm{font:700 25px/1.2 var(--serif);margin-top:10px}
.nmta{font:400 18px/1.5 'Noto Sans Tamil',var(--sans);color:var(--stone-700);margin-top:4px}
.per{font:600 16px/1.3 var(--sans);color:var(--lamp-700);margin-top:8px}
.note{font:400 14px/1.35 var(--sans);color:var(--stone-600);margin-top:10px;font-style:italic}
.arr{display:flex;align-items:center;transform:scaleX(-1)}
.time{position:absolute;left:72px;right:72px;top:770px;height:4px;background:linear-gradient(90deg,var(--lat-600),var(--lamp-500),var(--stone-400));border-radius:4px}
.tl{position:absolute;top:786px;font:600 17px/1 var(--sans);color:var(--stone-700)}
"""
    body = head("Five scripts, one letter", "One letter, <em>ka</em>, across 2,000 years of Tamil writing",
                "Ezhuthu teaches five levels, from the Tamil you read today back to Tamil-Brahmi. Read left to right to walk back in time; the arrows show the direction of change.")
    body += f'<div class="row">{"".join(cards)}</div>'
    body += '<div class="time"></div><div class="tl" style="left:72px">today</div><div class="tl" style="right:72px">c. 3rd c. BCE</div>'
    body += foot("Glyphs: Noto fonts (SIL OFL 1.1) and Ezhuthu's drawn Vatteluttu stroke; design/glyphs/hero-evolution.json. "
                 "Vatteluttu is a sibling branch, not an ancestor of modern Tamil.")
    page("p1-02-letter-evolution", body, extra_css=css)


def p1_03_gap_lengths() -> None:
    hist = json.loads((ROOT / "benchmark/stats.json").read_text())["gap_chars_hist"]  # P11
    labels = list(hist.keys())
    vals = [hist[k] for k in labels]
    total = sum(vals)
    assert total == 3289, total  # P8: 3,289 expert restorations in Tamil lines
    x0, y0, w, h = 150, 270, 1360, 470  # plot box
    bw = w / len(vals)
    vmax = 2000
    bars = []
    for i, (lab, v) in enumerate(zip(labels, vals)):
        bh = h * v / vmax
        x = x0 + i * bw + 22
        y = y0 + h - bh
        col = C["lat600"] if i == 0 else (C["lamp500"] if lab in ("11-20", "21+") else C["stone500"])
        bars.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw-44:.1f}" height="{bh:.1f}" rx="8" fill="{col}"/>')
        bars.append(f'<text x="{x+(bw-44)/2:.1f}" y="{y-14:.1f}" text-anchor="middle" class="v">{fmt(v)}</text>')
        nice = {"1": "1 letter", "21+": "21+ letters"}.get(lab, lab.replace("-", " to ") + " letters")
        bars.append(f'<text x="{x+(bw-44)/2:.1f}" y="{y0+h+38:.1f}" text-anchor="middle" class="xl">{nice}</text>')
    grid = "".join(
        f'<line x1="{x0}" x2="{x0+w}" y1="{y0+h-h*t/vmax:.1f}" y2="{y0+h-h*t/vmax:.1f}" stroke="{C["stone300"]}" stroke-width="1"/>'
        f'<text x="{x0-16}" y="{y0+h-h*t/vmax+6:.1f}" text-anchor="end" class="yl">{fmt(t)}</text>'
        for t in (0, 500, 1000, 1500, 2000)
    )
    svg = f"""<svg width="1600" height="900" style="position:absolute;left:0;top:0">
<style>.v{{font:700 24px 'Instrument Sans';fill:{C['ink']}}} .xl{{font:600 19px 'Instrument Sans';fill:{C['stone700']}}} .yl{{font:400 17px 'Instrument Sans';fill:{C['stone600']}}}
.an{{font:600 19px 'Instrument Sans';fill:{C['lat600']}}}</style>
{grid}{''.join(bars)}
<text x="{x0+bw*0.5+ (bw-44)/2 + 40}" y="{y0+40}" class="an">56% of restorations are a single letter</text>
<text x="{x0+bw*6.5}" y="{y0+h-170}" text-anchor="middle" class="an" style="fill:{C['lamp700']}">the long ones are the hard ones</text>
<path d="M{x0+bw*6.5} {y0+h-155} L{x0+bw*6.5} {y0+h-110}" stroke="{C['lamp700']}" stroke-width="2"/>
</svg>"""
    # 1833/3289 = 55.7% -> "56%" would round up; use the safe floor wording below instead.
    svg = svg.replace("56% of restorations are a single letter", "1,833 of 3,289 are a single letter")
    body = head("The damage, measured", "Most gaps are one letter. <em>The hard ones are long.</em>",
                "Every expert restoration in the Tamil lines of 1,320 DHARMA inscriptions, by the number of letters the editors supplied.")
    body += svg
    body += foot("Source: benchmark/stats.json (gap_chars_hist), 3,289 expert restorations in Tamil lines. Inscription texts: DHARMA, CC BY-SA 4.0.")
    page("p1-03-gap-lengths", body)


def crop(src: Path, box: tuple[int, int, int, int], dst: Path) -> Path:
    im = Image.open(src)
    im.crop(box).save(dst)
    return dst


def p1_04_home_hero() -> None:
    # Hero frames captured from the live home page (shots.cjs hero): card spans ~(27,25)-(1623,845) at 1.5x.
    frames = {}
    for t in (8, 10, 17, 22):
        frames[t] = crop(SHOTS / f"hero-{t}.png", (27, 25, 1623, 846), SHOTS / f"hero-{t}-card.png").as_uri()
    css = """
.grid{position:absolute;left:72px;right:72px;top:236px;display:grid;grid-template-columns:1fr 1fr;gap:30px 26px}
.cell{position:relative}
.cell img{width:100%;display:block;border-radius:22px;box-shadow:0 28px 50px -30px rgba(40,20,5,.7)}
.wide{grid-column:1 / span 2}
.cap{display:flex;gap:14px;align-items:flex-start;margin-top:14px}
.n{flex:none;width:36px;height:36px;border-radius:50%;background:var(--lat-600);color:#fff;font:700 19px/36px var(--serif);text-align:center}
.cap p{font:600 20px/1.35 var(--sans);color:var(--ink)}
.cap p span{font-weight:400;color:var(--stone-700)}
"""
    body = head("The home page hero", "A real Thanjavur stone, <em>read letter by letter</em>",
                "One recorded animation of a Chola-period inscription, four steps: Reader, Restorer, confidence check, Interpreter.")
    body += f"""<div class="grid">
<div class="cell"><img src="{frames[8]}" alt=""><div class="cap"><div class="n">1</div><p>The Reader names 46 carved letters, each with its own probability. <span>Mean 0.65, self-reported, not calibrated.</span></p></div></div>
<div class="cell"><img src="{frames[10]}" alt=""><div class="cap"><div class="n">2</div><p>The least certain letter, at 0.45, goes to the Restorer as a gap. <span>Opus 4.6 proposes fills for it.</span></p></div></div>
<div class="cell"><img src="{frames[17]}" alt=""><div class="cap"><div class="n">3</div><p>No fill clears the calibrated threshold, so it stays open. <span>The "?" waits for an expert instead of a guess.</span></p></div></div>
<div class="cell"><img src="{frames[22]}" alt=""><div class="cap"><div class="n">4</div><p>11 words, a phrase in today's Tamil and its meaning. <span>Meaning by Ezhuthu; no published edition to compare against.</span></p></div></div>
</div>"""
    body += foot("Live site, home page, captured 2026-11-03. Photo: Richard Mortel, CC BY 2.0, via Wikimedia Commons (cropped). Reading by Ezhuthu, built with Strands Agents.")
    page("p1-04-home-hero", body, h=1250, extra_css=css)


def p1_05_practice_banks() -> None:
    # S3 exact per-level counts; S2 totals
    rows = [("Letter recognition", "letters", [37, 94, 74]), ("Reading drill", "words", [230, 165, 145]),
            ("Fill the gap", "gaps", [170, 158, 66]), ("Spot the formula", "formulas", [144, 132, 54])]
    assert sum(sum(r[2]) for r in rows) == 1469
    cols = [C["palm300"], C["lamp500"], C["lat600"]]
    tcol = [C["ink"], C["ink"], "#fff"]
    x0, wmax, scale = 420, 1000, 1000 / 560
    out = []
    for i, (name, kind, lv) in enumerate(rows):
        y = 300 + i * 112
        out.append(f'<text x="{x0-28}" y="{y+30}" text-anchor="end" class="rn">{name}</text>')
        out.append(f'<text x="{x0-28}" y="{y+56}" text-anchor="end" class="rk">{kind}</text>')
        x = x0
        for j, v in enumerate(lv):
            w = v * scale
            out.append(f'<rect x="{x:.1f}" y="{y}" width="{w-3:.1f}" height="64" rx="6" fill="{cols[j]}"/>')
            if w > 60:
                out.append(f'<text x="{x+w/2-1.5:.1f}" y="{y+41}" text-anchor="middle" class="sv" style="fill:{tcol[j]}">{v}</text>')
            else:
                out.append(f'<text x="{x+w/2-1.5:.1f}" y="{y+41}" text-anchor="middle" class="sv" style="fill:{tcol[j]};font-size:18px">{v}</text>')
            x += w
        out.append(f'<text x="{x+18:.1f}" y="{y+42}" class="tot">{sum(lv)}</text>')
    leg = "".join(
        f'<rect x="{x0 + k*170}" y="250" width="22" height="22" rx="4" fill="{cols[k]}"/><text x="{x0 + k*170 + 32}" y="268" class="lg">Level {k+1}</text>'
        for k in range(3)
    )
    svg = f"""<svg width="1600" height="900" style="position:absolute;left:0;top:0">
<style>.rn{{font:700 26px 'Fraunces';fill:{C['ink']}}} .rk{{font:400 18px 'Instrument Sans';fill:{C['stone600']}}}
.sv{{font:700 22px 'Instrument Sans'}} .tot{{font:800 32px 'Fraunces';fill:{C['lat600']}}} .lg{{font:600 18px 'Instrument Sans';fill:{C['stone700']}}}</style>
{leg}{''.join(out)}</svg>"""
    body = head("Practice", "<em>1,469</em> practice items, built from real inscriptions",
                "Four kinds of drill, each at three difficulty levels, Tamil first with English letters (ISO-15919) beside them.")
    body += svg
    body += foot("Source: app/web/src/practice/banks/summary.json. Built from the train split only; Tamil strings pending a native-speaker check. Inscription texts: DHARMA, CC BY-SA 4.0.")
    page("p1-05-practice-banks", body, extra_css="")


def p1_06_practice_screens() -> None:
    desk = crop(SHOTS / "practice-desk.png", (250, 0, 1910, 1590), SHOTS / "practice-desk-crop.png").as_uri()
    mob = (SHOTS / "practice-mob.png").as_uri()
    css = """
.wrap{position:absolute;left:72px;right:72px;top:250px;display:flex;gap:56px;align-items:flex-start}
.browser{flex:1;border-radius:18px;overflow:hidden;background:#fff;box-shadow:0 30px 60px -30px rgba(40,20,5,.6);border:1px solid var(--stone-300)}
.bar{height:44px;background:var(--stone-200);display:flex;align-items:center;gap:8px;padding:0 16px}
.dot{width:13px;height:13px;border-radius:50%;background:var(--stone-400)}
.url{margin-left:16px;flex:1;height:26px;border-radius:13px;background:var(--stone-50);font:400 14px/26px var(--sans);color:var(--stone-600);padding-left:14px}
.browser img{width:100%;display:block}
.phone{flex:none;width:350px;border-radius:46px;padding:14px;background:var(--granite-900);box-shadow:0 30px 60px -26px rgba(40,20,5,.75)}
.phone img{width:100%;display:block;border-radius:34px}
.lbl{font:700 16px/1 var(--sans);letter-spacing:.12em;text-transform:uppercase;color:var(--stone-600);margin:0 0 12px 4px}
"""
    body = head("Practice, in Tamil", "Each miss shows <em>the right letter and why</em>",
                "A Level 3 Vatteluttu letter drill in the Tamil interface.")
    body += f"""<div class="wrap">
<div style="flex:1"><div class="lbl">Desktop</div><div class="browser"><div class="bar"><span class="dot"></span><span class="dot"></span><span class="dot"></span><div class="url">ezhuthu.sparrowdecider.com/practice/letters?level=3</div></div><img src="{desk}" alt=""></div></div>
<div><div class="lbl">Mobile</div><div class="phone"><img src="{mob}" alt=""></div></div>
</div>"""
    body += foot("Live site, captured 2026-11-03. Vatteluttu glyphs are Ezhuthu's drawn teaching shapes, pending an epigrapher's review.")
    page("p1-06-practice-screens", body, h=1420, extra_css=css)


def p1_07_restore() -> None:
    src = SHOTS / "restore-tiruvalisvaram-district-name-match.png"
    # Result heading -> end of the third candidate (1.5x capture; see shots.cjs restore)
    left = crop(src, (262, 1700, 1900, 2890), SHOTS / "restore-crop-top.png").as_uri()
    right = crop(src, (262, 2895, 1900, 4140), SHOTS / "restore-crop-cands.png").as_uri()
    css = """
.cols{position:absolute;left:56px;right:56px;top:236px;display:grid;grid-template-columns:1fr 1fr;gap:28px}
.panel{background:var(--stone-100);border-radius:18px;overflow:hidden;border:1px solid var(--stone-300);box-shadow:0 30px 60px -32px rgba(40,20,5,.6)}
.panel img{width:100%;display:block}
.lbl{display:flex;gap:12px;align-items:center;font:700 19px/1.2 var(--sans);margin:0 0 12px 4px}
.n{width:32px;height:32px;border-radius:50%;background:var(--lat-600);color:#fff;font:700 17px/32px var(--serif);text-align:center}
"""
    body = head("Restore, live", "Propose, score, check, <em>then fill or abstain</em>",
                "A Pandya passage from the try-it gallery, one letter hidden on purpose. Ezhuthu fills it at 72%; the edition reads the same letter.")
    body += f"""<div class="cols">
<div><div class="lbl"><span class="n">1</span>The fill, and what the published edition reads</div><div class="panel"><img src="{left}" alt=""></div></div>
<div><div class="lbl"><span class="n">2</span>Ranked candidates with calibrated confidence</div><div class="panel"><img src="{right}" alt=""></div></div>
</div>"""
    body += foot("Live site, Restore page, sample \"tiruvalisvaram-district-name\", run 2026-11-03 (one run; in the recorded gallery run 4 of 10 gaps were filled and all 4 match). "
                 "Edition: DHARMA Pandya00160, CC BY-SA 4.0.")
    page("p1-07-restore", body, h=940, extra_css=css)


def p1_09_tamil_nadu_stones() -> None:
    """P12, P13, P14 (counts of DHARMA editions, not stones)."""
    H = 900
    dyn = [("Pallava", 480), ("Chola", 312), ("Pandya", 115), ("Vijayanagara", 21), ("Rashtrakuta", 12), ("Kadava", 9), ("not stated", 371)]
    rows = [(n, "", v / 1320, C["lat600"] if i < 3 else (C["stone400"] if n == "not stated" else C["lamp500"])) for i, (n, v) in enumerate(dyn)]
    svg = f'<svg width="1600" height="{H}" style="position:absolute;left:0;top:0">{HB_STYLE}'
    svg += '<text x="72" y="290" class="pt">Dynasty, by edition (of 1,320)</text>'
    svg += hbars(rows, x0=250, y0=318, w=1100, rowh=66, barh=40, vmax=1.0, fmt_v=lambda v: f"{round(v*1320):,}")
    svg += "</svg>"
    cards = """<div style="position:absolute;left:820px;top:270px;width:720px;display:grid;gap:18px">
<div style="background:#FBF8F1;border:1px solid #DACDB4;border-radius:18px;padding:22px">
 <div style="font:700 14px/1 var(--sans);letter-spacing:.12em;text-transform:uppercase;color:#76674F">Madurai in the stones</div>
 <div style="display:flex;align-items:baseline;gap:16px;margin-top:12px"><div style="font:800 64px/1 var(--serif);color:#9B3D22">25</div>
 <div style="font:400 18px/1.4 var(--sans);color:#564A3A">editions name <b lang="ta" style="font-family:'Noto Serif Tamil',serif">&#2990;&#2980;&#3009;&#2992;&#3016;</b> (Madurai), carved as &#2990;&#2980;&#3007;&#2992;&#3016; (matirai), the inscriptions' own spelling</div></div>
 <div style="font:400 18px/1.4 var(--sans);color:#564A3A;margin-top:10px"><b>23</b> of them inside the royal title <b lang="ta" style="font-family:'Noto Serif Tamil',serif">&#2990;&#2980;&#3007;&#2992;&#3016; &#2965;&#3018;&#2979;&#3021;&#2975;</b> (matirai konta), "who took Madurai", of the Chola king Parantaka I</div></div>
<div style="display:flex;gap:18px">
 <div style="flex:1;background:#FBF8F1;border:1px solid #DACDB4;border-radius:18px;padding:22px"><div style="font:800 52px/1 var(--serif);color:#1D1611">534</div><div style="font:400 17px/1.4 var(--sans);color:#564A3A;margin-top:8px">of 1,320 editions name a temple in their title</div></div>
 <div style="flex:1;background:#FBF8F1;border:1px solid #DACDB4;border-radius:18px;padding:22px"><div style="font:800 52px/1 var(--serif);color:#1D1611">1 + 6</div><div style="font:400 17px/1.4 var(--sans);color:#564A3A;margin-top:8px">from Madurai's Minakshi temple and Thanjavur's Brihadisvara temple</div></div></div></div>"""
    b = [head("The stones behind Ezhuthu", "From Madurai to Thanjavur, <em>every great Tamil dynasty</em> is on the wall",
              "1,320 DHARMA editions from Tamil Nadu and beyond. Counts are of editions, which are not the same as stones.")]
    b.append(svg.replace('width="1600"', 'width="800"') + cards)
    b.append(foot("Source: benchmark/inscriptions.jsonl (title, dynasty, text_iso; counted 2026-11-03); ontology/seeds/dynasties_rulers.yaml. Inscription texts: DHARMA, CC BY-SA 4.0."))
    page("p1-09-tamil-nadu-stones", "".join(b), extra_css="")


# ---------------------------------------------------------------------------------------------------------------
# Part 2 diagrams
# ---------------------------------------------------------------------------------------------------------------

ARROW_DEFS = f"""<defs>
<marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="9" markerHeight="9" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="{C['lat600']}"/></marker>
<marker id="ahg" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="9" markerHeight="9" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="{C['stone600']}"/></marker>
<marker id="ahl" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="9" markerHeight="9" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="{C['lamp500']}"/></marker>
</defs>"""

BOX_CSS = """
.bx{position:absolute;border-radius:16px;background:var(--stone-50);border:1.5px solid var(--stone-300);padding:14px 16px;
 box-shadow:0 1px 0 rgba(255,255,255,.7) inset,0 14px 30px -22px rgba(60,35,10,.55)}
.bx h3{font:700 20px/1.2 var(--serif);color:var(--ink)}
.bx .st{font:700 12px/1 var(--sans);letter-spacing:.12em;text-transform:uppercase;color:var(--lat-600);margin-bottom:8px}
.bx p{font:400 15.5px/1.4 var(--sans);color:var(--stone-700);margin-top:6px}
.bx.aws{border-color:#C9B48F}
.bx.hot{border:2px solid var(--lat-600);background:#FFFDF8}
.bx.lamp{border:2px solid var(--lamp-500);background:#FFF9EC}
.bx.dk{background:var(--granite-900);border-color:var(--granite-700);color:#F3EADA}
.bx.dk h3{color:#F3EADA}.bx.dk p{color:#C9BBA3}.bx.dk .st{color:var(--lamp-300)}
.chip{display:inline-block;font:600 13.5px/1 var(--mono);padding:6px 8px;border-radius:7px;background:var(--stone-200);color:var(--ink-700);margin:6px 4px 0 0}
.dk .chip{background:var(--granite-800);color:#E9DCC6}
.zone{position:absolute;border-radius:24px;border:2px dashed var(--stone-400);}
.zl{position:absolute;font:700 14px/1 var(--sans);letter-spacing:.12em;text-transform:uppercase;color:var(--stone-600);background:var(--stone-100);padding:0 10px}
"""


def bx(x, y, w, h, title, body="", st="", cls="") -> str:
    s = f'<div class="st">{st}</div>' if st else ""
    return f'<div class="bx {cls}" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px">{s}<h3>{title}</h3>{body}</div>'


def arrows(paths: list[tuple[str, str]], w=1600, h=1000) -> str:
    out = []
    for d, kind in paths:
        col, m, dash = {"main": (C["lat600"], "ah", ""), "grey": (C["stone600"], "ahg", 'stroke-dasharray="7 6"'),
                         "lamp": (C["lamp500"], "ahl", "")}[kind]
        out.append(f'<path d="{d}" fill="none" stroke="{col}" stroke-width="2.6" {dash} marker-end="url(#{m})"/>')
    return f'<svg width="{w}" height="{h}" style="position:absolute;left:0;top:0;pointer-events:none">{ARROW_DEFS}{"".join(out)}</svg>'


def p2_01_architecture() -> None:
    H = 1060
    b = []
    b.append(head("Architecture", "Six agents. One AgentCore runtime. <em>Two Claude models.</em>",
                  "A React PWA on Amazon CloudFront, an HTTP API with a JWT authorizer, and a Strands multi-agent runtime on Amazon Bedrock AgentCore."))
    # zone for runtime
    b.append('<div class="zone" style="left:612px;top:250px;width:660px;height:690px;border-color:#B5502F;background:rgba(155,61,34,.035)"></div>')
    b.append('<div class="zl" style="left:640px;top:242px;color:#9B3D22">Amazon Bedrock AgentCore Runtime &middot; ezhuthu_tutor</div>')
    # left column
    b.append(bx(56, 268, 220, 112, "Learner or scholar", "<p>Phone or desktop, Tamil first, English optional</p>", "Browser"))
    b.append(bx(56, 430, 220, 196, "React + Vite PWA", "<p>Amazon CloudFront<br>private Amazon S3</p>", "EzhuthuWeb", "aws"))
    b.append(bx(56, 676, 220, 178, "Amazon Cognito", "<p>managed login, PKCE<br><b>experts</b> group for review</p>", "EzhuthuAuth", "aws"))
    b.append(bx(330, 268, 236, 196, "API Gateway HTTP API", "<p>JWT authorizer on signed-in routes<br>29 s limit, throttled</p>", "EzhuthuApi", "aws"))
    b.append(bx(330, 512, 236, 150, "AWS Lambda proxy", "<p>Node 22, arm64<br>gives the runtime 27 s</p>", "EzhuthuApi", "aws"))
    b.append(bx(330, 712, 236, 142, "Amazon DynamoDB", "<p>sessions, corrections, review queue; on demand, PITR</p>", "EzhuthuData", "aws"))
    # runtime internals
    b.append(bx(636, 276, 612, 196, "Strands Graph: one lesson",
                '<p style="margin-top:10px"><span class="chip">restore</span> &rarr; <span class="chip">lesson_builder</span> &rarr; '
                '<span class="chip">tutor_team</span></p><p>tutor_team is a Strands Swarm: <b>Tutor &#8644; Assessor</b>. The Tutor\'s next move '
                '(advance / repeat / hint): a policy built on Strands Decider with rule guardrails.</p>', "Lesson Builder, Tutor, Assessor", "hot"))
    b.append(bx(636, 492, 300, 252, "Restorer",
                '<p>a tool-using Strands agent</p><span class="chip">retrieve_parallels</span><span class="chip">propose_fills</span>'
                '<span class="chip">check_constraints</span><span class="chip">rank_and_decide</span><span class="chip">ontology_hints</span>',
                "Agent", "hot"))
    b.append(bx(948, 492, 300, 118, "Reader", "<p>photo or EpiDoc in, editable transcription out</p>", "Agent", "hot"))
    b.append(bx(948, 626, 300, 118, "Interpreter", "<p>letters in; words, today's Tamil, a meaning out</p>", "Agent", "hot"))
    b.append(bx(636, 764, 612, 152, "Ontology MCP server",
                '<p>OWL ontology: 27 classes, 1,958 individuals, 23,029 triples, served through a Strands MCPClient</p>'
                '<span class="chip">find_entities</span><span class="chip">valid_letters</span><span class="chip">formulas_for</span>'
                '<span class="chip">entity</span><span class="chip">hints_for_gap</span>', "Inside the bundle", "lamp"))
    # right column
    b.append(bx(1320, 300, 236, 250, "Amazon Bedrock",
                '<p style="margin-top:12px"><b style="color:#1D1611">Claude Sonnet 4.6</b><br>goes first</p>'
                '<p style="margin-top:12px"><b style="color:#1D1611">Claude Opus 4.6</b><br>when it matters: low score, long gap or no good parallel</p>', "Models", "aws"))
    b.append(bx(1320, 620, 236, 168, "AWS Secrets Manager", "<p>hosted decider key; the runtime may read that one secret only when it exists</p>", "Secrets", "aws"))
    b.append(bx(1320, 808, 236, 124, "25 s budget", "<p>every request answers inside the proxy limit</p>", "Guardrail", "lamp"))
    b.append(arrows([
        ("M166 380 L166 428", "main"),             # browser -> web
        ("M276 500 C300 500 300 366 328 366", "main"),  # web -> api
        ("M448 464 L448 510", "main"),             # api -> lambda
        ("M566 587 L634 587", "main"),             # lambda -> runtime
        ("M448 662 L448 710", "main"),             # lambda -> dynamo
        ("M276 765 C300 765 300 420 328 420", "grey"),  # cognito -> api (jwt)
        ("M1250 420 L1318 420", "main"),            # runtime -> bedrock
        ("M1274 700 L1318 700", "grey"),            # runtime border -> secrets (Tutor policy only)
        ("M786 744 L786 762", "lamp"),              # restorer -> mcp
    ], h=H))
    b.append(foot("Sources: infra/README.md, src/ezhuthu/agent/, config/models.yaml. Runtime: Python 3.12, Direct Code Deploy, linux/arm64 bundle. All five stacks are AWS CDK in TypeScript."))
    page("p2-01-architecture", "".join(b), h=H, extra_css=BOX_CSS)


def p2_02_graph_swarm() -> None:
    H = 900
    b = [head("Strands Graph + Swarm", "Deterministic where the facts are fixed, <em>a Swarm where the words are written</em>",
              "Every lesson is a three-node Strands Graph. The last node is a Strands Swarm in which the Tutor and the Assessor hand the explanation back and forth.")]
    b.append('<div class="zone" style="left:690px;top:300px;width:850px;height:330px;border-color:#9B3D22;background:rgba(155,61,34,.035)"></div>')
    b.append('<div class="zl" style="left:716px;top:292px;color:#9B3D22">tutor_team &middot; Strands Swarm</div>')
    b.append(bx(70, 360, 240, 170, "restore", "<p>function node: the Restorer's fills, confidence and parallels</p>", "Node 1", ""))
    b.append(bx(380, 360, 240, 170, "lesson_builder", "<p>function node: turns the restoration into lesson facts</p>", "Node 2", ""))
    b.append(bx(740, 350, 330, 230, "Tutor", "<p>writes the learner-facing explanation from the lesson facts, in Tamil first</p><p>next move (<b>advance / repeat / hint</b>): policy built on Strands Decider with rule guardrails</p>", "Agent", "hot"))
    b.append(bx(1170, 350, 330, 230, "Assessor", "<p>checks the explanation against the same lesson facts before it reaches the learner</p>", "Agent", "hot"))
    b.append(bx(380, 662, 320, 140, "Offline template explanation", "<p>no model available: the learner still gets feedback</p>", "Fallback", "lamp"))
    b.append('<div style="position:absolute;left:70px;top:556px;width:300px;font:600 16px/1.4 var(--sans);color:#76674F">One lesson context shared through the Graph\'s invocation state</div>')
    b.append(arrows([
        ("M310 445 L378 445", "main"),
        ("M620 445 L738 445", "main"),
        ("M1072 420 L1168 420", "main"),
        ("M1168 510 L1072 510", "main"),
        ("M500 530 L500 660", "lamp"),
    ], h=H))
    b.append('<div style="position:absolute;left:1080px;top:385px;width:84px;text-align:center;font:600 14px/1 var(--sans);color:#9B3D22">draft</div>')
    b.append('<div style="position:absolute;left:1080px;top:520px;width:84px;text-align:center;font:600 14px/1 var(--sans);color:#9B3D22">checked</div>')
    b.append(foot("Source: src/ezhuthu/agent/tutor/graph.py, src/ezhuthu/agent/tutor/policy.py. The Tutor policy's effect on learners is not yet measured."))
    page("p2-02-graph-swarm", "".join(b), h=H, extra_css=BOX_CSS)


def p2_03_restorer_pipeline() -> None:
    H = 980
    b = [head("The Restorer", "Three signals, one score, <em>one honest decision</em>",
              "A gap goes through retrieval, the 5-gram and Claude, gets filtered, fused by a noisy-OR, picked by the fine-tuned Strands Decider and calibrated. Then it fills or it abstains.")]
    b.append(bx(56, 420, 200, 150, "A gap", '<p>context left and right, gap length</p><p class="ta" style="font-size:20px;color:#1D1611">வரி<b style="color:#D2891C">[?1]</b>பாடும்</p>', "Input"))
    b.append(bx(320, 270, 300, 150, "Parallel passages", "<p>BM25 over character n-grams, re-ranked with rapidfuzz; 14,355 train lines; top 20</p>", "retrieve_parallels", ""))
    b.append(bx(320, 450, 300, 150, "Character 5-gram", "<p>its own fills plus a score for every candidate; 11 ms per gap (p50)</p>", "Train only", ""))
    b.append(bx(320, 630, 300, 150, "Claude proposes", "<p>Sonnet 4.6 first, Opus 4.6 on escalation</p>", "propose_fills", "hot"))
    b.append(bx(690, 450, 240, 150, "Constraints", "<p>gap length and the letters valid for the era</p>", "check_constraints", ""))
    b.append(bx(1000, 380, 260, 290, "Noisy-OR pre-rank",
                '<p style="font:600 17px/1.5 var(--mono);color:#1D1611;margin-top:12px">1 &minus; (1&minus;p<sub>LLM</sub>)<br>&nbsp;&nbsp;&times; (1&minus;s<sub>parallel</sub>)<br>&nbsp;&nbsp;&times; (1&minus;s<sub>5-gram</sub>)</p>'
                '<p>its top 3 go to the fine-tuned Strands Decider, which picks one or none; the pre-rank is the fallback</p>', "rank_and_decide", "lamp"))
    b.append(bx(1320, 300, 226, 170, "Platt calibration", "<p>fitted on VAL only; one key per answering model</p>", "Calibrate", ""))
    b.append(bx(1320, 520, 226, 110, "Fill", "<p>score above threshold</p>", "Decision", "hot"))
    b.append(bx(1320, 660, 226, 150, "Abstain", "<p>\"experts are unsure here too\", or the expert review queue</p>", "Decision", ""))
    b.append(arrows([
        ("M256 470 C290 470 290 345 318 345", "main"),
        ("M256 495 L318 525", "main"),
        ("M256 520 C290 520 290 705 318 705", "main"),
        ("M620 345 C660 345 960 345 1000 420", "grey"),
        ("M620 525 L688 525", "main"),
        ("M620 705 C655 705 655 560 688 560", "main"),
        ("M930 525 L998 525", "main"),
        ("M1260 470 C1290 470 1290 390 1318 390", "main"),
        ("M1433 470 L1433 518", "main"),
        ("M1546 385 C1590 385 1590 735 1548 735", "grey"),
    ], h=H))
    b.append('<div style="position:absolute;left:660px;top:322px;font:600 14px/1 var(--sans);color:#76674F">parallel support</div>')
    b.append('<div style="position:absolute;left:1320px;top:826px;width:226px;font:600 14px/1.35 var(--sans);color:#76674F">pre-rank thresholds fitted on VAL:<br>Opus 0.4887, Sonnet 0.4111</div>')
    b.append(foot("Sources: src/ezhuthu/agent/tools.py, retrieval.py, calibration.py; config/models.yaml (restorer.ngram_prerank). 5-gram timing on an Apple M4 Pro."))
    page("p2-03-restorer-pipeline", "".join(b), h=H, extra_css=BOX_CSS)


def p2_04_routing() -> None:
    # T9: 413 gaps; 291 pre-escalated to Opus, 5 after Sonnet, rest (117) Sonnet only; 122 Sonnet calls, 297 Opus calls
    n, pre, after = 413, 291, 5
    son = n - pre - after
    assert son == 117 and son + after == 122
    H = 900
    W = 1360
    x0 = 120
    def seg(x, w, col, top, lab, sub, tc="#fff"):
        return (f'<div style="position:absolute;left:{x}px;top:{top}px;width:{w}px;height:120px;background:{col};border-radius:10px"></div>'
                f'<div style="position:absolute;left:{x}px;top:{top+138}px;width:{max(w,240)}px;font:800 40px/1 var(--serif);color:#1D1611">{lab}</div>'
                f'<div style="position:absolute;left:{x}px;top:{top+186}px;width:{max(w,300)}px;font:400 18px/1.35 var(--sans);color:#564A3A">{sub}</div>')
    wpre, waft, wson = W * pre / n, W * after / n, W * son / n
    b = [head("Model routing on Amazon Bedrock", "Sonnet first. <em>Opus where it counts.</em>",
              "The router escalates to Claude Opus 4.6 when Sonnet's best score is under 0.6, the gap is over 12 letters, or no good parallel exists. 413 held-out TEST gaps:")]
    b.append(seg(x0, wpre - 4, C["lat600"], 330, "291", "straight to Opus 4.6 by the pre-escalation rules"))
    b.append(f'<div style="position:absolute;left:{x0+wpre}px;top:330px;width:{waft-2}px;height:120px;background:{C["lamp500"]};border-radius:4px"></div>')
    b.append(seg(x0 + wpre + waft + 4, wson - 4, C["stone500"], 330, "117", "answered by Sonnet 4.6 alone"))
    b.append(f'<div style="position:absolute;left:{x0+wpre-250}px;top:252px;width:500px;text-align:center;font:700 19px/1.2 var(--sans);color:{C["lamp700"]}">5 escalate after a Sonnet answer</div>')
    b.append(f'<svg width="1600" height="900" style="position:absolute;left:0;top:0">{ARROW_DEFS}<path d="M{x0+wpre+waft/2} 280 L{x0+wpre+waft/2} 326" stroke="{C["lamp500"]}" stroke-width="2.6" marker-end="url(#ahl)"/></svg>')
    stats = [("296 of 413", "gaps used Opus 4.6"), ("122", "Sonnet 4.6 calls"), ("297", "Opus 4.6 calls"), ("$0.0060", "per gap, about $2.49 for 413 gaps at list prices")]
    tiles = "".join(f'<div style="flex:1;background:#FBF8F1;border:1px solid #DACDB4;border-radius:16px;padding:20px 22px"><div style="font:800 38px/1 var(--serif);color:#9B3D22">{a}</div><div style="font:400 17px/1.35 var(--sans);color:#564A3A;margin-top:10px">{s}</div></div>' for a, s in stats)
    b.append(f'<div style="position:absolute;left:{x0}px;width:{W}px;top:620px;display:flex;gap:20px">{tiles}</div>')
    b.append(foot("Source: eval/reports/2026-11-02-deployed-config.md; routing rules in config/models.yaml. Cost is an estimate at list prices, not the bill."))
    page("p2-04-routing", "".join(b), h=H)


def p2_05_ontology_mcp() -> None:
    d = json.loads((ROOT / "app/web/src/components/how/ontology-slice.json").read_text())
    nodes = {n["id"]: n for n in d["nodes"]}
    cnt = d["counts"]
    H = 1000
    # graph positions (left 1000px)
    pos = {
        "ez:ruler/rajaraja-i": (480, 560),
        "ez:dynasty/chola": (175, 370),
        "ez:formula/kantalur-calai": (780, 370),
        "ez:place/uttiramerur": (210, 780),
        "ez:temple/uttiramerur-sundaravaradaperumal": (730, 790),
        "ez:tax/irai": (115, 560),
        "ez:measure/kalanju": (845, 560),
    }
    rel_lab = {"memberOfDynasty": "memberOfDynasty", "praiseOf": "praiseOf", "sameStone": "same stone", "locatedAt": "locatedAt"}
    kind_col = {"ruler": C["lat600"], "dynasty": C["neelam700"], "formula": C["lamp700"], "place": C["neem700"], "temple": C["neem700"],
                "tax": C["stone600"], "measure": C["stone600"]}
    edges = []
    for e in d["edges"]:
        if e["from"] in pos and e["to"] in pos:
            (x1, y1), (x2, y2) = pos[e["from"]], pos[e["to"]]
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            lab = rel_lab[e["rel"]] + (f" &middot; {e['n']}" if e.get("n") else "")
            edges.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{C["stone400"]}" stroke-width="2.4"/>'
                         f'<rect x="{mx-len(rel_lab[e["rel"]])*3.9-24}" y="{my-14}" width="{len(rel_lab[e["rel"]])*7.8+48}" height="26" rx="13" fill="{C["stone100"]}"/>'
                         f'<text x="{mx}" y="{my+5}" text-anchor="middle" class="el">{lab}</text>')
    nds = []
    for nid, (x, y) in pos.items():
        n = nodes[nid]
        big = nid == "ez:ruler/rajaraja-i"
        w = 260 if big else (200 if n["kind"] in ("tax", "measure") else (290 if n["kind"] == "temple" else 250))
        h = 108 if big else 92
        col = kind_col[n["kind"]]
        sub = n["kind"].replace("_", " ")
        wd = f' &middot; Wikidata {n["wikidata"]}' if n.get("wikidata") else ""
        ta = n.get("label_ta") or ""
        nds.append(f'<div class="nd{" big" if big else ""}" style="left:{x-w/2}px;top:{y-h/2}px;width:{w}px;height:{h}px;border-color:{col}">'
                   f'<div class="k" style="color:{col}">{sub}{wd}</div><div class="l">{n["label_iso"]}</div><div class="t">{ta}</div></div>')
    svg = f'<svg width="1600" height="{H}" style="position:absolute;left:0;top:0"><style>.el{{font:600 13.5px "Instrument Sans";fill:{C["stone600"]}}}</style>{"".join(edges)}</svg>'
    counts = [("rulers", cnt["ruler"]), ("places", cnt["place"]), ("admin units", cnt["admin_unit"]), ("temples", cnt["temple"]),
              ("formulas", cnt["formula"]), ("taxes", cnt["tax"]), ("measures", cnt["measure"]), ("letters", cnt["letter"]),
              ("script stages", cnt["script_stage"]), ("dynasties", cnt["dynasty"])]
    # T5 exact values
    assert dict(counts) == {"rulers": 42, "places": 357, "admin units": 200, "temples": 139, "formulas": 14, "taxes": 8,
                            "measures": 14, "letters": 262, "script stages": 8, "dynasties": 6}
    ctiles = "".join(f'<div class="ct"><b>{fmt(v)}</b><span>{k}</span></div>' for k, v in counts)
    tools = "".join(f'<span class="chip">{t}</span>' for t in ("find_entities", "valid_letters", "formulas_for", "entity", "hints_for_gap"))
    css = BOX_CSS + """
.nd{position:absolute;background:var(--stone-50);border:2px solid;border-radius:14px;padding:10px 14px;box-shadow:0 14px 28px -20px rgba(60,35,10,.6)}
.nd.big{background:#FFFDF8;box-shadow:0 0 0 6px rgba(155,61,34,.1),0 18px 34px -20px rgba(60,35,10,.6)}
.nd .k{font:700 12px/1.2 var(--sans);letter-spacing:.08em;text-transform:uppercase}
.nd .l{font:700 19px/1.25 var(--serif);margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.nd.big .l{font-size:23px}
.nd .t{font:400 15px/1.4 'Noto Sans Tamil',var(--sans);color:var(--stone-700);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.side{position:absolute;left:1000px;top:250px;width:540px}
.owl{font:800 64px/1 var(--serif);color:var(--lat-600)}
.owls{font:400 18px/1.45 var(--sans);color:var(--stone-700);margin-top:8px}
.cts{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-top:26px}
.ct{background:var(--stone-50);border:1px solid var(--stone-300);border-radius:12px;padding:12px 8px;text-align:center}
.ct b{display:block;font:800 26px/1 var(--serif);color:var(--ink)}
.ct span{display:block;font:400 13.5px/1.25 var(--sans);color:var(--stone-600);margin-top:6px}
.mcp{margin-top:26px;background:var(--granite-900);border-radius:18px;padding:20px 22px;color:#F3EADA}
.mcp h4{font:700 20px/1.2 var(--serif)}
.mcp p{font:400 15.5px/1.45 var(--sans);color:#C9BBA3;margin-top:6px}
.mcp .chip{background:var(--granite-800);color:#F5C468}
"""
    b = [head("Knowledge graph", "Tamil epigraphy as an OWL ontology, <em>served over MCP</em>",
              "Rulers, dynasties, temples, places and formulas, linked by the stones that mention them. Built from the train split only.")]
    b.append(svg)
    b.append("".join(nds))
    b.append(f"""<div class="side"><div class="owl">23,029 triples</div>
<div class="owls">27 classes &middot; 21 object properties &middot; 1,958 named individuals. All 6 dynasties and 19 of 42 rulers link to Wikidata.</div>
<div class="cts">{ctiles}</div>
<div class="mcp"><h4>5 MCP tools via a Strands MCPClient</h4><div>{tools}</div>
<p>Built from 862 train editions; the 229 held-out editions are excluded, and tests enforce it. If the server dies, the client restarts it, then falls back to the in-process lookup.</p></div></div>""")
    b.append(foot("Sources: ontology/README.md, ontology/coverage.json, app/web/src/components/how/ontology-slice.json. Edge numbers: train inscriptions with that link. Wikidata IDs: CC0."))
    page("p2-05-ontology-mcp", "".join(b), h=H, extra_css=css)


def p2_06_request_budget() -> None:
    # A14: before 30.8, 49.6, 58.4; after 20.9, 25.0, 25.0; proxy 27 s, API GW 29 s; n = 3 requests
    reqs = [("7 gaps", 30.8, 20.9), ("5 gaps", 49.6, 25.0), ("5 gaps", 58.4, 25.0)]
    H = 900
    x0, y0, w = 260, 300, 1100  # time axis 0..60 s
    sx = w / 60
    out = []
    for i, (lab, b4, af) in enumerate(reqs):
        y = y0 + i * 150
        out.append(f'<text x="{x0-24}" y="{y+40}" text-anchor="end" class="rl">Request {i+1}</text><text x="{x0-24}" y="{y+66}" text-anchor="end" class="rs">{lab}</text>')
        out.append(f'<rect x="{x0}" y="{y}" width="{b4*sx:.1f}" height="44" rx="6" fill="{C["stone400"]}"/>')
        out.append(f'<text x="{x0+b4*sx+12:.1f}" y="{y+31}" class="bv">{b4} s</text>')
        out.append(f'<text x="{x0+b4*sx+90:.1f}" y="{y+31}" class="to">timed out</text>')
        out.append(f'<rect x="{x0}" y="{y+56}" width="{af*sx:.1f}" height="44" rx="6" fill="{C["lat600"]}"/>')
        out.append(f'<text x="{x0+af*sx-12:.1f}" y="{y+87}" text-anchor="end" class="av">{af} s</text>')
    lines = []
    for t, lab, col, dash in ((25, "25 s budget", C["lamp700"], "6 6"), (27, "27 s proxy limit", C["lat600"], ""), (29, "29 s API Gateway", C["stone600"], "3 5")):
        x = x0 + t * sx
        lines.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{y0-30}" y2="{y0+430}" stroke="{col}" stroke-width="2.5" stroke-dasharray="{dash}"/>')
    lab_html = (f'<div style="position:absolute;left:{x0+25*sx-160:.0f}px;top:{y0-62}px;width:150px;text-align:right;font:700 16px/1.2 var(--sans);color:{C["lamp700"]}">25 s budget</div>'
                f'<div style="position:absolute;left:{x0+27*sx+8:.0f}px;top:{y0-62}px;width:200px;font:700 16px/1.2 var(--sans);color:{C["lat600"]}">27 s proxy limit</div>')
    ticks = "".join(f'<text x="{x0+t*sx:.1f}" y="{y0+462}" text-anchor="middle" class="tk">{t} s</text>' for t in (0, 10, 20, 30, 40, 50, 60))
    svg = f"""<svg width="1600" height="{H}" style="position:absolute;left:0;top:0"><style>
.rl{{font:700 22px Fraunces;fill:{C['ink']}}} .rs{{font:400 17px 'Instrument Sans';fill:{C['stone600']}}} .bv{{font:700 20px 'Instrument Sans';fill:{C['stone700']}}}
.to{{font:600 16px 'Instrument Sans';fill:{C['stone600']};font-style:italic}} .av{{font:700 20px 'Instrument Sans';fill:#fff}} .tk{{font:400 16px 'Instrument Sans';fill:{C['stone600']}}}</style>
{''.join(lines)}{''.join(out)}{ticks}</svg>"""
    leg = (f'<div style="position:absolute;left:{x0}px;top:800px;display:flex;gap:28px;font:600 17px/1 var(--sans);color:{C["stone700"]}">'
           f'<span><i style="display:inline-block;width:18px;height:18px;border-radius:4px;background:{C["stone400"]};vertical-align:-3px;margin-right:8px"></i>before the budget</span>'
           f'<span><i style="display:inline-block;width:18px;height:18px;border-radius:4px;background:{C["lat600"]};vertical-align:-3px;margin-right:8px"></i>after: 25 s clock, Opus only with 8 s left, LLM only with 6 s left, at most 8 gaps</span></div>')
    b = [head("A hard 25-second budget", "Three timeouts became <em>three answers</em>",
              "Same requests, before and after the budget. The 13 gaps the budget did not touch came out identical (13 of 13).")]
    b.append(svg + lab_html + leg)
    b.append(foot("Source: eval/reports/2026-11-02-request-budget.md. n = 3 requests: a latency check, not an accuracy estimate."))
    page("p2-06-request-budget", "".join(b), h=H + 20)


def p2_07_cdk_stacks() -> None:
    H = 900
    css = BOX_CSS + """
.stk{position:absolute;border-radius:20px;background:var(--stone-50);border:2px solid var(--stone-300);padding:20px 22px;box-shadow:0 18px 36px -24px rgba(60,35,10,.55)}
.stk .nm{font:800 26px/1 var(--serif);color:var(--lat-600)}
.stk .rs{margin-top:14px;display:flex;flex-direction:column;gap:8px}
.stk .r{font:600 17px/1.3 var(--sans);color:var(--ink);background:var(--stone-100);border-radius:10px;padding:9px 12px}
.stk .r small{display:block;font:400 14.5px/1.3 var(--sans);color:var(--stone-600);margin-top:2px}
.stk.agent{background:var(--granite-900);border-color:var(--granite-700)} .stk.agent .nm{color:var(--lamp-300)}
.stk.agent .r{background:var(--granite-800);color:#F3EADA} .stk.agent .r small{color:#C9BBA3}
"""
    def stk(x, y, w, h, name, rows, cls=""):
        rs = "".join(f'<div class="r">{a}<small>{s}</small></div>' for a, s in rows)
        return f'<div class="stk {cls}" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px"><div class="nm">{name}</div><div class="rs">{rs}</div></div>'
    b = [head("Infrastructure as code", "Five stacks, <em>all as code</em>",
              "Serverless AWS around one AgentCore runtime, written with the AWS CDK in TypeScript.")]
    top = 270
    b.append(stk(56, top, 280, 330, "EzhuthuWeb", [("Amazon CloudFront", "SPA rewrite, security headers, /api/* to the HTTP API"), ("Amazon S3", "private bucket, the React PWA")]))
    b.append(stk(360, top, 300, 330, "EzhuthuApi", [("API Gateway HTTP API", "one route per contract endpoint, throttled"), ("JWT authorizer", "on signed-in routes"), ("AWS Lambda proxy", "Node 22, arm64")]))
    b.append(stk(684, top, 300, 330, "EzhuthuAgent", [("Bedrock AgentCore Runtime", "ezhuthu_tutor, Python 3.12, Direct Code Deploy"), ("linux/arm64 bundle", "about 237 MB unpacked, 67 MB zipped, ontology MCP server inside")], "agent"))
    b.append(stk(1008, top, 260, 330, "EzhuthuAuth", [("Amazon Cognito", "managed login, PKCE"), ("experts group", "unlocks the review queue")]))
    b.append(stk(1292, top, 252, 330, "EzhuthuData", [("Amazon DynamoDB", "on demand, point-in-time recovery"), ("Review queue", "sessions, corrections")]))
    b.append(bx(684, 660, 300, 150, "AWS Secrets Manager", "<p>hosted decider key; read access for the runtime only when the secret exists</p>", "Outside the stacks", "aws"))
    b.append(arrows([("M834 600 L834 658", "grey")], h=H))
    b.append(foot("Source: infra/README.md. No Lambda Function URLs: the proxy is reached only through API Gateway."))
    page("p2-07-cdk-stacks", "".join(b), h=H, extra_css=css)


# ---------------------------------------------------------------------------------------------------------------
# Part 3 charts
# ---------------------------------------------------------------------------------------------------------------

def hbars(rows, *, x0, y0, w, rowh, vmax=1.0, label_w=360, cls_hi=0, ci=None, fmt_v=lambda v: f"{v:.4f}", barh=46, extra=None, voff=14):
    """rows: list of (label, sublabel, value, colour)."""
    out = []
    for i, (lab, sub, v, col) in enumerate(rows):
        y = y0 + i * rowh
        out.append(f'<text x="{x0-22}" y="{y+barh/2-2}" text-anchor="end" class="hl">{lab}</text>')
        if sub:
            out.append(f'<text x="{x0-22}" y="{y+barh/2+22}" text-anchor="end" class="hs">{sub}</text>')
        out.append(f'<rect x="{x0}" y="{y}" width="{w}" height="{barh}" rx="8" fill="rgba(0,0,0,.045)"/>')
        out.append(f'<rect x="{x0}" y="{y}" width="{w*v/vmax:.1f}" height="{barh}" rx="8" fill="{col}"/>')
        out.append(f'<text x="{x0+w*v/vmax+voff:.1f}" y="{y+barh/2+9}" class="hv">{fmt_v(v)}</text>')
        if extra and extra[i]:
            out.append(f'<text x="{x0+w*v/vmax+120:.1f}" y="{y+barh/2+8}" class="hx">{extra[i]}</text>')
    return "".join(out)


HB_STYLE = f"""<style>.hl{{font:700 21px Fraunces;fill:{C['ink']}}} .hs{{font:400 15px 'Instrument Sans';fill:{C['stone600']}}}
.hv{{font:800 25px Fraunces;fill:{C['ink']}}} .hx{{font:600 15px 'Instrument Sans';fill:{C['stone600']}}}
.dk .hl{{fill:#F3EADA}} .dk .hs{{fill:#A8997F}} .dk .hv{{fill:#F3EADA}} .dk .hx{{fill:#A8997F}}
.pt{{font:700 22px Fraunces;fill:{C['ink']}}} .dk .pt{{fill:#F5C468}}</style>"""


def p3_01_decider_effort() -> None:
    """D1-D7, A20: the work behind the fine-tuned Strands decision model, in order."""
    H = 1010
    b = [head("The fine-tuned Strands decision model", "Six steps from <em>train-only data</em> to one look at TEST",
              "Task: given the Restorer's top 3 candidate fills, pick the one the editors wrote, or none. Fine-tuned and tested on held-out inscriptions. Public on Hugging Face; the live app ranks with it.")]
    W, Hh, gx, gy, x0, y0 = 460, 270, 56, 50, 72, 270
    cells = [
        ("1 &middot; Data, TRAIN only", "Training rows",
         "<p>2,337 train items. 1,162 Sonnet 4.6 calls build the candidates (cap 1,200, about USD 4.8).</p>"
         "<p style='margin-top:12px;font:800 34px/1 var(--serif);color:#9B3D22'>2,334 + 6,936</p><p>choice rows + yes/no rows</p>", ""),
        ("2 &middot; Cross-fit by stone", "No answer key in the candidates",
         "<p>5 folds by stone: retrieval and the 5-gram for each train item are built without its own fold.</p>"
         "<p style='margin-top:12px;font:800 34px/1 var(--serif);color:#9B3D22'>0 of 6,996</p><p>train parallels from the item's own fold (audit)</p>", ""),
        ("3 &middot; Scrub near-duplicates", "Formulas repeat across stones",
         "<p>96 of 2,433 train items dropped: 78 matched a TEST item, 18 a VAL item.</p>"
         "<p style='margin-top:12px;font:800 34px/1 var(--serif);color:#9B3D22'>1 of 413</p><p>TEST item shares a target in the reverse audit</p>", ""),
        ("4 &middot; Three model sizes", "2B chosen",
         "<p><b>2B</b>: Strands Decider v1-2610 2B + LoRA r 48 + pointer head; 1x A100 40 GB, 74 min per variant.</p>"
         "<p><b>Sparrow tiny</b>: Ettin-32M, 21 min on an M4 Pro. <b>Sparrow nano</b>: Tamil WordPiece 8k, seconds.</p>", "lamp"),
        ("5 &middot; Pre-registered selection", "Chosen on VAL",
         "<p>Rule committed first (2c2f5b2). 8 decider variants compared on the same 280 VAL gaps.</p>"
         "<p>Calibration fitted on VAL only (n = 443 and 244).</p>", ""),
        ("6 &middot; TEST, scored once", "413 held-out gaps",
         "<p>Cached candidates replayed: 0 new Bedrock calls.</p>"
         "<p style='margin-top:12px;font:800 34px/1 var(--serif);color:#9B3D22'>92.0%</p><p>of its fills match the editors' restoration (fills 57.6% of gaps)</p>", "hot"),
    ]
    for i, (st, title, body, cls) in enumerate(cells):
        r, c = divmod(i, 3)
        b.append(bx(x0 + c * (W + gx), y0 + r * (Hh + gy), W, Hh, title, body, st, cls))
    paths = []
    for r in range(2):
        for c in range(2):
            y = y0 + r * (Hh + gy) + Hh / 2
            xa = x0 + c * (W + gx) + W
            paths.append((f"M{xa+2} {y} L{xa+gx-4} {y}", "main"))
    xr = x0 + 2 * (W + gx) + W / 2
    paths.append((f"M{xr} {y0+Hh+2} C{xr} {y0+Hh+30} {x0+W/2} {y0+Hh+20} {x0+W/2} {y0+Hh+gy-4}", "grey"))
    b.append(arrows(paths, h=H))
    b.append('<div style="position:absolute;left:72px;top:884px;font:700 22px/1.3 var(--serif);color:#1D1611">Trained for <span style="color:#9B3D22">USD 2.26</span> in total. Checkpoint 224 MB.</div>')
    b.append(foot("Sources: eval/reports/2026-11-02-finetuned-decider.md and 2026-11-02-ft-data.md."))
    page("p3-01-decider-effort", "".join(b), h=H, extra_css=BOX_CSS)


def p3_02_splits() -> None:
    H = 980
    css = BOX_CSS + """
.ins{position:absolute;display:grid;gap:7px}
.ins i{display:block;width:26px;height:34px;border-radius:13px 13px 4px 4px;background:var(--stone-400)}
.pool{position:absolute;border-radius:22px;padding:18px 20px}
.pool .t{font:800 30px/1 var(--serif)} .pool .s{font:400 16.5px/1.4 var(--sans);margin-top:8px}
"""
    import random
    rnd = random.Random(3)
    stones = []
    for r in range(6):
        for c in range(7):
            k = rnd.random()
            col = C["lat600"] if k < .1 else (C["neelam700"] if k < .2 else C["stone500"])
            stones.append(f'<i style="background:{col}"></i>')
    b = [head("Benchmark design", "Split by inscription, so <em>nothing leaks</em>",
              "Every gap, line and blank of an inscription goes to one split, and editions of the same stone travel together.")]
    b.append(bx(56, 290, 280, 430, "1,320 DHARMA inscriptions",
                f'<p>3,289 expert restorations in Tamil lines become gaps: context, gap length, the editor\'s fill as target</p>'
                f'<div class="ins" style="position:static;grid-template-columns:repeat(7,26px);margin-top:16px">{"".join(stones)}</div>', "Corpus"))
    b.append('<div class="pool" style="left:420px;top:270px;width:420px;height:200px;background:#EFE5D2;border:2px solid #9A896C"><div class="t">TRAIN</div><div class="s">the only split the restorer can read</div></div>')
    b.append('<div class="pool" style="left:420px;top:500px;width:420px;height:130px;background:var(--neelam-100);border:2px solid var(--neelam-700)"><div class="t" style="color:#3B4787">VAL</div><div class="s">280 gaps choose the configuration and fit the calibration</div></div>')
    b.append('<div class="pool" style="left:420px;top:660px;width:420px;height:170px;background:var(--lat-100);border:2px solid var(--lat-600)"><div class="t" style="color:#9B3D22">TEST</div><div class="s">131 inscriptions, 413 gaps, scored once<br><b>TEST-hard: 317 gaps</b> with no close parallel in another train inscription</div></div>')
    b.append(bx(960, 250, 270, 120, "Retrieval corpus", "<p>14,355 train lines, BM25 + rapidfuzz</p>", "Train only"))
    b.append(bx(960, 390, 270, 110, "Character 5-gram", "<p>built from the same train lines</p>", "Train only"))
    b.append(bx(960, 520, 270, 120, "OWL ontology", "<p>862 train editions; 229 held-out editions excluded</p>", "Train only"))
    b.append(bx(1280, 250, 264, 390, "make check", "<p>A corpus that contains a held-out inscription refuses to load.</p><p>Tests enforce the leakage rules and that the README numbers match the benchmark statistics.</p><p style=\"margin-top:14px;font:800 30px/1 var(--serif);color:#9B3D22\">461</p><p>Python test functions</p>", "Enforced", "hot"))
    b.append(bx(960, 680, 584, 150, "Pre-registered selection", "<p>The rule was committed (1322bdb) before any variant was scored on VAL. Nothing was re-tuned after the choice. TEST was scored once.</p>", "Then", "lamp"))
    b.append(arrows([
        ("M336 420 L418 370", "main"), ("M336 505 L418 565", "main"), ("M336 600 L418 740", "main"),
        ("M840 330 L958 310", "main"), ("M840 370 L958 445", "main"), ("M840 420 L958 575", "main"),
        ("M840 565 C900 565 900 740 958 750", "grey"), ("M840 745 L958 760", "grey"),
    ], h=H))
    b.append('<div style="position:absolute;left:56px;top:760px;width:300px;font:400 15px/1.4 var(--sans);color:#76674F">Each stone shape stands for one inscription; its colour shows its split (grey train, blue VAL, red TEST). Illustrative, not to scale.</div>')
    b.append(foot("Sources: benchmark/DATA_CARD.md, benchmark/stats.json, ontology/coverage.json, eval/reports/2026-11-02-deployed-config.md."))
    page("p3-02-splits", "".join(b), h=H, extra_css=css)


def p3_03_leaderboard() -> None:
    s = json.loads((ROOT / "app/web/src/benchmark/summary.json").read_text())["leaderboard"]
    names = {"deployed": ("Ezhuthu, pre-rank version", C["lat600"]), "ngram": ("Character 5-gram", C["stone500"]),
             "copy": ("Copy the best parallel", C["stone500"])}
    H = 900
    svg = f'<svg width="1600" height="{H}" style="position:absolute;left:0;top:0">{HB_STYLE}'
    for k, (key, title, x0) in enumerate((("full", "Full TEST: 413 gaps", 330), ("hard", "TEST-hard: 317 gaps, no close parallel", 1030))):
        rows = {r["id"]: r for r in s[key]["rows"]}
        lst = [(names[i][0], f'{rows[i]["matches"]} of {s[key]["n"]}', rows[i]["top1"], names[i][1]) for i in ("deployed", "ngram", "copy")]
        extra = [None] + [("p " if rows[i]["vs_deployed"]["p_text"][0] in "<>" else "p = ") + rows[i]["vs_deployed"]["p_text"] if rows[i]["vs_deployed"] else None for i in ("ngram", "copy")]
        svg += f'<text x="{x0-290}" y="300" class="pt">{title}</text>'
        svg += hbars(lst, x0=x0, y0=340, w=300, rowh=110, extra=None, voff=44)
        # CI whiskers
        for i, rid in enumerate(("deployed", "ngram", "copy")):
            lo, hi = rows[rid]["ci"]
            y = 340 + i * 110 + 23
            svg += f'<line x1="{x0+300*lo:.1f}" x2="{x0+300*hi:.1f}" y1="{y}" y2="{y}" stroke="{C["ink"]}" stroke-width="2"/>'
            svg += f'<line x1="{x0+300*lo:.1f}" x2="{x0+300*lo:.1f}" y1="{y-9}" y2="{y+9}" stroke="{C["ink"]}" stroke-width="2"/><line x1="{x0+300*hi:.1f}" x2="{x0+300*hi:.1f}" y1="{y-9}" y2="{y+9}" stroke="{C["ink"]}" stroke-width="2"/>'
            if extra[i]:
                svg += f'<text x="{x0+300*rows[rid]["top1"]+14:.1f}" y="{y+40}" class="hx">{extra[i]}</text>'
    svg += "</svg>"
    b = [head("Leaderboards", "Ahead of the classic methods, <em>on the hard set too</em>",
              "Top-1 match with the editors' restoration, same gaps for every system. Whiskers: 95% intervals. p: exact McNemar against the pre-rank version (what the app ran before the fine-tuned decision model).")]
    b.append(svg)
    b.append(foot("Source: app/web/src/benchmark/summary.json (from eval/reports/2026-11-02-deployed-config.md). \"Matches\" = equals the editor's supplied text after normalisation."))
    page("p3-03-leaderboard", "".join(b), h=740)


def p3_04_reliability() -> None:
    ab = json.loads((ROOT / "app/web/src/benchmark/summary.json").read_text())["abstention"]
    bins = ab["reliability"]
    H = 980
    x0, y0, S = 150, 270, 600  # square plot
    out = [f'<rect x="{x0}" y="{y0}" width="{S}" height="{S}" fill="{C["stone50"]}" stroke="{C["stone300"]}"/>']
    for t in (0, .2, .4, .6, .8, 1):
        out.append(f'<line x1="{x0}" x2="{x0+S}" y1="{y0+S-S*t}" y2="{y0+S-S*t}" stroke="{C["stone200"]}"/>')
        out.append(f'<text x="{x0-12}" y="{y0+S-S*t+6}" text-anchor="end" class="tk">{int(t*100)}%</text>')
        out.append(f'<text x="{x0+S*t}" y="{y0+S+30}" text-anchor="middle" class="tk">{t:.1f}</text>')
    out.append(f'<line x1="{x0}" y1="{y0+S}" x2="{x0+S}" y2="{y0}" stroke="{C["stone500"]}" stroke-width="2" stroke-dasharray="7 6"/>')
    nmax = max(b["n"] for b in bins)
    for b in bins:
        cx, cy = x0 + S * b["confidence"], y0 + S - S * b["accuracy"]
        r = 7 + 17 * (b["n"] / nmax) ** .5
        hi = b["lo"] == 0.9
        out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{C["lat600"] if hi else C["lamp500"]}" fill-opacity=".85" stroke="#fff" stroke-width="2"/>')
    top = [b for b in bins if b["lo"] == 0.9][0]
    assert top["n"] == 95 and round(top["accuracy"] * 100, 1) == 97.9  # A8
    out.append(f'<text x="{x0+S-18}" y="{y0+S-48}" text-anchor="end" class="an">red dot, the 0.9 to 1.0 bin:</text>')
    out.append(f'<text x="{x0+S-18}" y="{y0+S-22}" text-anchor="end" class="an">95 gaps, 97.9% match</text>')
    out.append(f'<text x="{x0+S/2}" y="{y0+S+66}" text-anchor="middle" class="ax">calibrated confidence</text>')
    out.append(f'<text transform="translate({x0-78} {y0+S/2}) rotate(-90)" text-anchor="middle" class="ax">share that match the editors</text>')
    svg = f"""<svg width="1600" height="{H}" style="position:absolute;left:0;top:0"><style>
.tk{{font:400 16px 'Instrument Sans';fill:{C['stone600']}}} .ax{{font:600 18px 'Instrument Sans';fill:{C['stone700']}}}
.an{{font:700 18px 'Instrument Sans';fill:{C['lat600']}}}</style>{''.join(out)}</svg>"""
    # coverage panel A7, A8, A9
    cov = 49.9
    panel = f"""<div style="position:absolute;left:880px;top:270px;width:660px">
<div style="font:700 15px/1 var(--sans);letter-spacing:.12em;text-transform:uppercase;color:#76674F">Held-out TEST, 413 gaps</div>
<div style="margin-top:18px;height:64px;border-radius:12px;overflow:hidden;display:flex;border:1px solid #DACDB4">
 <div style="width:{cov}%;background:#9B3D22;color:#fff;font:700 20px/64px var(--sans);padding-left:18px">fills 49.9% (206)</div>
 <div style="flex:1;background:#E3E5F4;color:#3B4787;font:700 20px/64px var(--sans);padding-left:18px">abstains: to an expert</div></div>
<div style="display:flex;gap:18px;margin-top:28px">
 <div style="flex:1;background:#FBF8F1;border:1px solid #DACDB4;border-radius:18px;padding:22px"><div style="font:800 64px/1 var(--serif);color:#9B3D22">90.8%</div><div style="font:400 18px/1.4 var(--sans);color:#564A3A;margin-top:10px">of fills match the editors' restoration (187 of 206)</div></div>
 <div style="flex:1;background:#FBF8F1;border:1px solid #DACDB4;border-radius:18px;padding:22px"><div style="font:800 64px/1 var(--serif);color:#1D1611">0.110</div><div style="font:400 18px/1.4 var(--sans);color:#564A3A;margin-top:10px">expected calibration error; 0 would be perfect</div></div></div>
<div style="margin-top:18px;background:#FBF8F1;border:1px solid #DACDB4;border-radius:18px;padding:20px 22px;font:400 18px/1.45 var(--sans);color:#564A3A">
 <b style="color:#1D1611">TEST-hard holds the line:</b> coverage 0.4101, and 0.9077 of its fills match.<br>
 <b style="color:#1D1611">Thresholds fitted on VAL only:</b> Opus 0.4887 (n = 224), Sonnet 0.4111 (n = 278).</div></div>"""
    b = [head("Calibration and abstention", "When it commits, <em>nine in ten fills match</em>",
              "Each dot is a confidence bin on held-out TEST (size = number of gaps). On the dashed line, a stated 70% would mean 70% match.")]
    b.append(svg + panel)
    b.append(foot("Source: eval/reports/2026-11-02-deployed-config.md; bins from app/web/src/benchmark/summary.json (abstention.reliability)."))
    page("p3-04-reliability", "".join(b), h=H + 30)


def p3_05_finetuned_decider() -> None:
    """A16, A17, D8/A18, L4: fine-tuned 2B on held-out TEST. No LLM-vs-decider framing (brief)."""
    H = 980
    left = [("Fine-tuned 2B", "270 of 413, CI 0.6077 to 0.6973", 0.6538, C["lat600"]),
            ("Pre-rank", "decider-free noisy-OR", 0.5908, C["stone500"]),
            ("Base 2B", "Strands Decider v1-2610 2B", 0.5811, C["stone500"])]
    lx = [None, "32 vs 6, p = 2.4e-5", "41 vs 11, p = 3.6e-5"]
    right = [("Ceiling", "target among the 3 options", 0.6029, C["neelam300"]),
             ("Fine-tuned 2B", "fine-tuned on Tamil train rows", 0.5472, C["lat600"]),
             ("Hosted v19", "general-purpose decider", 0.4310, C["stone500"]),
             ("Base 2B", "before fine-tuning", 0.4165, C["stone500"])]
    svg = f'<svg width="1600" height="{H}" style="position:absolute;left:0;top:0">{HB_STYLE}'
    svg += '<text x="72" y="300" class="pt">Inside the Restorer: same Sonnet 4.6 candidates</text>'
    svg += hbars(left, x0=330, y0=340, w=330, rowh=96)
    for i, e in enumerate(lx):
        if e:
            svg += f'<text x="{330+330*left[i][2]+14:.1f}" y="{340+i*96+70}" class="hx">{e}</text>'
    svg += '<line x1="830" x2="830" y1="270" y2="620" stroke="#DACDB4" stroke-width="2"/>'
    svg += '<text x="870" y="300" class="pt">As a pure decider: 413 recorded requests</text>'
    x0, w = 1130, 330
    svg += hbars(right, x0=x0, y0=330, w=w, rowh=74, barh=40)
    svg += "</svg>"
    panel = """<div style="position:absolute;left:72px;top:660px;width:700px;background:#FBF8F1;border:1px solid #DACDB4;border-radius:18px;padding:22px">
 <div style="font:700 15px/1 var(--sans);letter-spacing:.12em;text-transform:uppercase;color:#76674F">It knows when it knows</div>
 <div style="margin-top:16px;height:46px;border-radius:10px;overflow:hidden;display:flex;border:1px solid #DACDB4">
  <div style="width:57.6%;background:#9B3D22;color:#fff;font:700 17px/46px var(--sans);padding-left:12px">fills 57.6% of TEST gaps</div><div style="flex:1;background:#E3E5F4;color:#3B4787;font:700 17px/46px var(--sans);padding-left:12px">abstains</div></div>
 <div style="display:flex;align-items:baseline;gap:16px;margin-top:16px"><div style="font:800 58px/1 var(--serif);color:#9B3D22">92.0%</div>
 <div style="font:400 17px/1.4 var(--sans);color:#564A3A">of its 238 fills match the editors' restoration; ECE 0.070. TEST-hard: 0.5962.</div></div></div>
<div style="position:absolute;left:870px;top:660px;width:670px;background:#1B1713;border-radius:18px;padding:22px;color:#F3EADA">
 <div style="font:800 40px/1 var(--serif);color:#F5C468">90.8% of the gaps it can reach</div>
 <div style="font:400 17px/1.45 var(--sans);color:#C9BBA3;margin-top:10px">0.5472 against a ceiling of 0.6029 (target among the 3 options). +11.6 points over hosted v19, p &lt; 1e-8. Yes/no head: AUC 0.971, ECE 0.015.</div>
 <div style="font:600 15px/1.4 var(--sans);color:#F5C468;margin-top:12px">Public on Hugging Face (sparrow-decider/ezhuthu-sparrow-decider-2b); the live app ranks with it.</div></div>"""
    b = [head("The fine-tuned 2B Strands decision model", "Fine-tuned for Tamil: <em>92.0%</em> of its fills match the editors",
              "Top-1 match with the editors' restoration on held-out TEST, scored once. Left: the Restorer ranked by each option. Right: the decision alone, same requests for every decider.")]
    b.append(svg + panel)
    b.append(foot("Source: eval/reports/2026-11-02-finetuned-decider.md. p: exact McNemar on discordant gaps. Not a paired comparison with the routed pre-rank run (0.6271)."))
    page("p3-05-finetuned-decider", "".join(b), h=H)


# ---------------------------------------------------------------------------------------------------------------
# Covers: 1200x675, no text
# ---------------------------------------------------------------------------------------------------------------

# Photographic images also exported as JPEG for upload (the PNG stays the render output).
JPEG_COPIES = ["p1-00-cover", "project-00-cover"]


def covers() -> None:
    boxes = json.loads((ROOT / "design/hero/boxes.json").read_text())
    photo = (ROOT / "app/web/public/hero/thanjavur-1568.jpg").as_uri()
    # Cover 1: the real Thanjavur stone with lamp-lit letter boxes (photo: Richard Mortel, CC BY 2.0; credited in the article)
    W, Hh = 1568, 778
    rects = []
    import random
    rnd = random.Random(7)
    for row in boxes["rows"]:
        for (x1, y1, x2, y2) in row:
            lit = rnd.random()
            op = .95 if lit < .55 else .45
            col = C["lamp300"] if lit < .8 else C["lat300"]
            rects.append(f'<rect x="{x1}" y="{y1}" width="{x2-x1}" height="{y2-y1}" rx="12" fill="none" stroke="{col}" stroke-opacity="{op}" stroke-width="5"/>')
    c1 = f"""<div style="position:absolute;inset:0;background:#1B1713"></div>
<div style="position:absolute;left:-110px;top:-24px;width:1420px;height:{1420*Hh/W:.0f}px">
 <img src="{photo}" style="width:100%;height:100%;display:block;filter:saturate(1.08) contrast(1.05)">
 <svg viewBox="0 0 {W} {Hh}" style="position:absolute;inset:0;width:100%;height:100%"><defs><filter id="gl"><feGaussianBlur stdDeviation="5" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>
 <g filter="url(#gl)">{''.join(rects)}</g></svg></div>
<div style="position:absolute;inset:0;background:radial-gradient(90% 80% at 50% 45%,rgba(0,0,0,0) 40%,rgba(19,16,13,.75) 100%)"></div>"""
    page("p1-00-cover", c1, w=1200, h=675, theme="dark")

    # Cover 2: agent graph motif, lamp-lit nodes and links on granite (no text, no letters)
    nodes = [(170, 340), (390, 200), (390, 480), (620, 340), (840, 200), (840, 480), (1040, 340), (620, 110), (620, 570)]
    links = [(0, 1), (0, 2), (1, 3), (2, 3), (3, 4), (3, 5), (4, 6), (5, 6), (1, 7), (7, 4), (2, 8), (8, 5), (4, 5)]
    ls = "".join(f'<line x1="{nodes[a][0]}" y1="{nodes[a][1]}" x2="{nodes[b][0]}" y2="{nodes[b][1]}" stroke="{C["lamp400"] if (a, b) in ((0, 1), (1, 3), (3, 4), (4, 6)) else "#5A4D3E"}" stroke-width="{5 if (a, b) in ((0, 1), (1, 3), (3, 4), (4, 6)) else 3}"/>' for a, b in links)
    ns = ""
    for i, (x, y) in enumerate(nodes):
        hot = i in (0, 1, 3, 4, 6)
        ns += f'<circle cx="{x}" cy="{y}" r="{46 if i == 3 else 34}" fill="{C["g850"]}" stroke="{C["lamp300"] if hot else "#76674F"}" stroke-width="{5 if hot else 3}"/>'
        if hot:
            ns += f'<circle cx="{x}" cy="{y}" r="{14 if i != 3 else 20}" fill="{C["lamp300"]}"/>'
    tri = f'<path d="M620 300 L655 362 L585 362 Z" fill="{C["lamp500"]}" opacity=".0"/>'
    c2 = f"""<div style="position:absolute;inset:0;background:radial-gradient(70% 90% at 55% 45%,#3a2414 0%,#1B1713 55%,#13100D 100%)"></div>
<svg width="1200" height="675" style="position:absolute;inset:0"><defs><filter id="g2"><feGaussianBlur stdDeviation="9" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
<pattern id="dots" width="28" height="28" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1.4" fill="#40362B"/></pattern></defs>
<rect width="1200" height="675" fill="url(#dots)"/><g filter="url(#g2)">{ls}{ns}{tri}</g></svg>"""
    page("p2-00-cover", c2, w=1200, h=675, theme="dark")

    # Cover 3: calibration motif, rising bins of light along a diagonal on stone (no text)
    ab = json.loads((ROOT / "app/web/src/benchmark/summary.json").read_text())["abstention"]["reliability"]
    bars = ""
    for i, b in enumerate(ab):
        x = 140 + i * 94
        h = 40 + 470 * b["accuracy"]
        col = C["lat600"] if b["lo"] >= .5 else C["lamp500"]
        bars += f'<rect x="{x}" y="{600-h:.0f}" width="66" height="{h:.0f}" rx="10" fill="{col}" opacity="{.55 + .045*i:.2f}"/>'
    c3 = f"""<div style="position:absolute;inset:0;background:linear-gradient(160deg,#FBF8F1 0%,#F4EEE2 45%,#EAE1CE 100%)"></div>
<svg width="1200" height="675" style="position:absolute;inset:0">
<defs><pattern id="grain" width="6" height="6" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r=".8" fill="#DACDB4"/></pattern></defs>
<rect width="1200" height="675" fill="url(#grain)" opacity=".7"/>
<line x1="120" y1="600" x2="1080" y2="90" stroke="#76674F" stroke-width="4" stroke-dasharray="14 12"/>{bars}
<circle cx="1080" cy="90" r="20" fill="#D2891C"/><circle cx="1080" cy="90" r="38" fill="none" stroke="#D2891C" stroke-width="3" opacity=".5"/></svg>"""
    page("p3-00-cover", c3, w=1200, h=675)

    # Project cover: highlights the project. The real Thanjavur stone (photo: Richard Mortel, CC BY 2.0; credited in
    # the article) with lamp-lit letter boxes and one restored gap, the Tamil and English wordmarks, the headline,
    # the held-out result (A1, A7) and what it is built with.
    sc, ox, oy = 0.86, 395, -10
    pw, ph = W * sc, Hh * sc
    pr = []
    rnd2 = random.Random(11)
    hot = (2, 4)  # row 2, box 4: the restored gap, on the lit part of the stone
    for ri, row in enumerate(boxes["rows"]):
        for bi, (x1, y1, x2, y2) in enumerate(row):
            if (ri, bi) == hot:
                continue
            op = .9 if rnd2.random() < .6 else .4
            pr.append(f'<rect x="{x1}" y="{y1}" width="{x2-x1}" height="{y2-y1}" rx="12" fill="none" stroke="{C["lamp300"]}" stroke-opacity="{op}" stroke-width="5"/>')
    hx1, hy1, hx2, hy2 = boxes["rows"][hot[0]][hot[1]]
    pr.append(f'<rect x="{hx1-8}" y="{hy1-8}" width="{hx2-hx1+16}" height="{hy2-hy1+16}" rx="16" fill="{C["lamp300"]}" fill-opacity=".34" '
              f'stroke="{C["lamp200"]}" stroke-width="9"/>'
              f'<rect x="{hx1-22}" y="{hy1-22}" width="{hx2-hx1+44}" height="{hy2-hy1+44}" rx="24" fill="none" '
              f'stroke="{C["lamp300"]}" stroke-opacity=".55" stroke-width="3" stroke-dasharray="14 10"/>')
    tagx, tagy = ox + (hx1 + hx2) / 2 * sc, oy + hy1 * sc - 66
    chips = "".join(f'<span style="display:inline-block;margin:0 10px 0 0;padding:9px 15px;border-radius:999px;border:1.5px solid {C["lamp700"]};'
                    f'background:rgba(35,30,24,.9);font:600 17px/1 var(--sans);color:{C["stone100"]}">{t}</span>'
                    for t in ("Strands Agents", "Amazon Bedrock AgentCore", "Fine-tuned Strands Decider", "Tamil ontology over MCP"))
    tiles = "".join(f'<div style="flex:1;padding:16px 16px 14px;border-radius:16px;background:rgba(35,30,24,.92);border:1.5px solid {C["g700"]}">'
                    f'<div style="font:800 40px/1 var(--serif);color:{C["lamp300"]}">{big}</div>'
                    f'<div style="font:500 15px/1.3 var(--sans);color:{C["stone300"]};margin-top:8px">{small}</div></div>'
                    for big, small in (("62.7%", "of 413 held-out gaps match the editors' restoration"),
                                       ("9 in 10", "of the fills it commits to match"),
                                       ("1,958", "rulers, temples, places and formulas in the ontology")))
    c4 = f"""<div style="position:absolute;inset:0;background:{C["g950"]}"></div>
<div style="position:absolute;left:{ox}px;top:{oy}px;width:{pw:.0f}px;height:{ph:.0f}px">
 <img src="{photo}" style="width:100%;height:100%;display:block;filter:saturate(1.05) contrast(1.05) brightness(.92)">
 <svg viewBox="0 0 {W} {Hh}" style="position:absolute;inset:0;width:100%;height:100%"><defs><filter id="g4"><feGaussianBlur stdDeviation="5" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>
 <g filter="url(#g4)">{''.join(pr)}</g></svg></div>
<div style="position:absolute;inset:0;background:linear-gradient(90deg,{C["g950"]} 0%,{C["g950"]} 36%,rgba(19,16,13,.86) 56%,rgba(19,16,13,.15) 78%,rgba(19,16,13,.35) 100%)"></div>
<div style="position:absolute;inset:0;background:linear-gradient(0deg,rgba(19,16,13,.92) 0%,rgba(19,16,13,0) 34%)"></div>
<div style="position:absolute;left:{tagx-70:.0f}px;top:{tagy:.0f}px;width:140px;text-align:center;padding:7px 0;border-radius:10px;background:{C["lamp300"]};
 font:700 17px/1 var(--sans);color:{C["g950"]};letter-spacing:.04em;box-shadow:0 0 24px rgba(245,196,104,.6)">RESTORED</div>
<div style="position:absolute;left:56px;top:44px;width:660px">
 <div style="display:flex;align-items:flex-end;gap:20px"><img src="{LOGO}/wordmark-ta-reversed.svg" style="height:84px">
  <span style="font:700 64px/0.9 var(--serif);color:{C["stone50"]};letter-spacing:-.01em">Ezhuthu</span></div>
 <div style="font:700 21px/1 var(--sans);color:{C["lamp300"]};letter-spacing:.14em;margin-top:22px">AGENTIC AI FOR TAMIL EPIGRAPHY</div>
 <div style="font:700 38px/1.12 var(--serif);color:{C["stone50"]};margin-top:14px">Reads, restores and teaches Tamil temple inscriptions over 1,000 years old</div>
 <div style="display:flex;gap:14px;margin-top:28px">{tiles}</div>
</div>
<div style="position:absolute;left:56px;bottom:46px;width:1100px">{chips}</div>
<div style="position:absolute;right:40px;bottom:24px;font:500 14px/1 var(--sans);color:{C["stone500"]}">Vivek Raja, AWS AI Hero</div>"""
    page("project-00-cover", c4, w=1200, h=675, theme="dark")


ALL = [p1_01_at_a_glance, p1_02_letter_evolution, p1_03_gap_lengths, p1_04_home_hero, p1_05_practice_banks,
       p1_06_practice_screens, p1_07_restore, p1_09_tamil_nadu_stones, p2_01_architecture, p2_02_graph_swarm, p2_03_restorer_pipeline,
       p2_04_routing, p2_05_ontology_mcp, p2_06_request_budget, p2_07_cdk_stacks, p3_01_decider_effort,
       p3_02_splits, p3_03_leaderboard, p3_04_reliability, p3_05_finetuned_decider, covers]

if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["--shrink"]:
        for name in JPEG_COPIES:
            src = HERE.parent / "img" / f"{name}.png"
            dst = src.with_suffix(".jpg")
            Image.open(src).convert("RGB").save(dst, quality=90, optimize=True, progressive=True)
            print("jpeg", dst.name, dst.stat().st_size // 1024, "KB")
        for f in sorted((HERE.parent / "img").glob("*.png")):
            if f.stat().st_size > 2 * 1024 * 1024:
                q = Image.open(f).convert("RGB").quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.FLOYDSTEINBERG)
                q.save(f, optimize=True)
                print("shrunk", f.name, f.stat().st_size // 1024, "KB")
        sys.exit(0)
    only = sys.argv[1:]
    for f in ALL:
        if not only or any(o in f.__name__ for o in only):
            f()
    # p1-08 is a straight crop of the live Benchmark page (no HTML): leaderboard + reliability chart
    if not only or any("p1_08" in o or "benchmark" in o for o in only):
        im = Image.open(SHOTS / "benchmark-full.png")
        im.crop((0, 0, 1600, 600)).save(HERE.parent / "img" / "p1-08-benchmark-page.png", optimize=True)
    print("ok")
