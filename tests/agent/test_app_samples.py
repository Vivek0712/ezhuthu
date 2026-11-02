"""Every file the web app serves under public/samples comes from a TRAIN-split inscription.

benchmark/DATA_CARD.md, leakage rule 2: text of a val/test inscription is never shown next to a restoration task
with its expert fills. The samples are public and invite the learner to restore their gaps, so they may only use
TRAIN inscriptions. app/web/public/samples/**/SOURCES.json names the inscription behind each file; this test checks
that every file is listed, that each listed inscription is TRAIN, and that the file's own content agrees.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from lxml import etree

from ezhuthu.agent.reader import Reader
from ezhuthu.agent.text import GAP_RE, tamil_to_iso
from ezhuthu.corpus.script import normalise_for_scoring

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "app" / "web" / "public" / "samples"
INS = {d["id"]: d for d in (json.loads(x) for x in
                            (ROOT / "benchmark" / "inscriptions.jsonl").read_text(encoding="utf-8").splitlines())}


def _manifests() -> list[Path]:
    return sorted(SAMPLES.rglob("SOURCES.json"))


def _entries() -> list[tuple[Path, dict]]:
    return [(m.parent, e) for m in _manifests() for e in json.loads(m.read_text(encoding="utf-8"))["files"]]


def _letters(s: str) -> str:
    return normalise_for_scoring(GAP_RE.sub(" ", s)).replace(" ", "")


def test_every_sample_file_is_listed_in_a_sources_manifest():
    assert _manifests(), "public/samples needs a SOURCES.json"
    listed = set()
    for d, e in _entries():
        listed.add(d / e["file"])
        if e.get("thumb"):
            listed.add(d / e["thumb"])
    files = {p for p in SAMPLES.rglob("*") if p.is_file() and p.name != "SOURCES.json"}
    assert files - listed == set(), f"unlisted sample files: {sorted(str(p.relative_to(SAMPLES)) for p in files - listed)}"
    assert listed - files == set(), f"listed but missing: {sorted(str(p) for p in listed - files)}"


@pytest.mark.parametrize("entry", [e for _, e in _entries()], ids=lambda e: e["file"])
def test_every_sample_resolves_to_a_train_inscription(entry):
    ins = INS.get(entry["inscription_id"])
    assert ins is not None, f"{entry['file']}: unknown inscription {entry['inscription_id']}"
    assert ins["split"] == "train", f"{entry['file']} comes from a {ins['split'].upper()} inscription"
    assert entry["split"] == "train"
    for other in ins.get("same_stone_as") or []:
        assert INS[other]["split"] == "train"
    assert entry["licence"] == ins["licence"] and entry["source_url"] == ins["source_url"]


def test_epidoc_samples_are_the_named_train_edition():
    for d, e in _entries():
        if e["kind"] != "epidoc":
            continue
        root = etree.parse(str(d / e["file"]), etree.XMLParser(resolve_entities=False, no_network=True))
        idno = root.find(".//{http://www.tei-c.org/ns/1.0}idno[@type='filename']")
        assert idno is not None and re.sub(r"\.xml$", "", idno.text.strip()) == e["inscription_id"]
        out = Reader(llm=None).read(text=(d / e["file"]).read_text(encoding="utf-8"), filename=e["file"])
        assert out["inscription_id"] == e["inscription_id"] and out["licence"] == "CC BY-SA 4.0"


def test_text_samples_quote_their_train_inscription():
    for d, e in _entries():
        if e["kind"] != "text":
            continue
        whole = _letters(INS[e["inscription_id"]]["text_iso"].replace("\n", ""))
        for line in (d / e["file"]).read_text(encoding="utf-8").splitlines():
            for chunk in GAP_RE.split(tamil_to_iso(line))[::2]:
                c = _letters(chunk)
                if len(c) >= 6:
                    # Tamil script does not mark every ISO distinction; compare a fuzzy window, not exact text.
                    from rapidfuzz import fuzz

                    assert fuzz.partial_ratio(c, whole) >= 80, f"{e['file']}: {chunk!r} not in {e['inscription_id']}"


def test_no_sample_quotes_a_val_or_test_line():
    held_out = {_letters(ln) for d in INS.values() if d["split"] != "train"
                for ln in d["text_iso"].split("\n") if len(_letters(ln)) >= 14}
    held_out -= {_letters(ln) for d in INS.values() if d["split"] == "train"
                 for ln in d["text_iso"].split("\n")}  # formulae shared with train are not a leak
    for d, e in _entries():
        if e["kind"] == "rendered-plate":
            ins = INS[e["inscription_id"]]
            a, b = (int(x) for x in e["lines"].split("-"))
            text = "\n".join(ins["text_iso"].split("\n")[a - 1:b])
        else:
            raw = (d / e["file"]).read_text(encoding="utf-8")
            text = tamil_to_iso(raw) if e["kind"] == "text" else raw
        for ln in text.split("\n"):
            assert _letters(ln) not in held_out, f"{e['file']} quotes a held-out line: {ln!r}"
