"""Build the Ezhuthu ontology artefacts from DHARMA + curated seeds.

    python -m ezhuthu.ontology.build --dharma data/raw/dharma --splits train      # shipped build
    python -m ezhuthu.ontology.build --dharma data/raw/dharma --splits all        # full corpus (local only)

``--splits train`` builds only from inscriptions that ``benchmark/inscriptions.jsonl`` (one or more
``--benchmark`` files) puts in the train split. DHARMA editions keep the expert ``<supplied>``
restorations inline, so an ontology built from val/test editions would hand the restorer the
answers to held-out items (QA, PR #9). An inscription is used only when every given benchmark file
lists it and puts it in an allowed split; editions a benchmark does not list (drafts, duplicates)
are left out too, because they may be another edition of a held-out stone.

Writes, under ``ontology/``:
  * ``lookups/<kind>.json``  entity records per contracts/ontology-lookup.schema.json
  * ``letters_by_era.json``  valid base letters per script stage, with exceptions and corpus counts
  * ``coverage.json``        counts per kind, Wikidata coverage, dropped seeds, corpus commit pins
  * ``ezhuthu.ttl``          OWL ontology (TBox + individuals) built with rdflib

Everything is derived deterministically from the inputs; re-running on the same DHARMA commits
gives byte-identical output.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import warnings
from collections import Counter, defaultdict
from pathlib import Path

import yaml

from ezhuthu.ontology import letters as L
from ezhuthu.ontology.matcher import VariantIndex
from ezhuthu.ontology.normalize import fold, key, slug
from ezhuthu.ontology.tei import Inscription, iter_corpus

REPO = Path(__file__).resolve().parents[3]
ONTOLOGY_DIR = REPO / "ontology"
KINDS = [
    "script_stage", "letter", "dynasty", "ruler", "title", "formula", "place", "admin_unit",
    "temple", "deity", "grant_type", "assembly", "measure", "coin", "tax",
]  # fmt: skip
MAX_REFS = 40
DHARMA_URL = "https://dharmalekha.info/texts/{}"

COLLECTION_DEFAULT_DYNASTY = {
    "tfa-pallava-epigraphy": "pallava",
    "tfa-cempiyan-mahadevi-epigraphy": "chola",
    "tfa-pandya-epigraphy": "pandya",
}
CLASS_STAGE = {"vaṭṭeḻuttu": "vatteluttu", "grantha": "grantha"}
_TEMPLE = re.compile(
    r"temple|īśvara|ēśvara|eśvara|īcuvara|ēcuvara|perumāḷ|cave|kōvil|kōyil|nātha|maṇḍapa|svāmi|amman|"
    r"piḷḷaiyār|aiyaṉār|jinālaya|varāha|br̥hadīśvara",
    re.IGNORECASE,
)
_SIVA = re.compile(r"īśvara|ēśvara|eśvara|īcuvara|ēcuvara|nātha|śiva|civa|mahādeva|liṅga|jaṭādhara|kailāsa|naṭarāja", re.IGNORECASE)
_VISHNU = re.compile(r"perumāḷ|varāha|nārāyaṇa|viṣṇu|raṅga|varada|vaikuṇṭha|keśava|govinda", re.IGNORECASE)
_NOT_PLACE = re.compile(r"^(unknown|unidentified|provenance|no |\[|\.\.\.)", re.IGNORECASE)


def _ta(iso: str) -> str | None:
    from aksharamukha import transliterate

    src = re.sub(r"[…*\[\]()]", "", iso).strip()
    if not src:
        return None
    out = []
    for tok in src.split():
        if re.fullmatch(r"[IVX]+", tok):  # regnal numerals stay as Roman numerals
            out.append(tok)
            continue
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            ta = transliterate.process("ISO", "Tamil", tok.lower(), nativize=False, post_options=["TamilRemoveNumbers"])
            # faithful ISO mapping (n -> ந, ṉ -> ன); Tamil never ends a word in ந், so Sanskrit final n -> ன்
            out.append(re.sub(r"ந்(?=$|[-\s])", "ன்", ta))
    res = " ".join(o for o in out if o) or None
    if res and re.search(r"[A-Za-z]", re.sub(r"\b[IVX]+\b", "", res)):
        return None  # Latin residue: the label was not ISO-15919 (do not show learners a mixed-script label)
    return res


SPLITS = ("train", "val", "test")


def load_split_map(paths: list[Path]) -> list[dict[str, str]]:
    """One ``{inscription id: split}`` map per benchmark ``inscriptions.jsonl``."""
    maps = []
    for p in paths:
        m: dict[str, str] = {}
        for line in Path(p).read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                m[rec["id"]] = rec["split"]
        maps.append(m)
    return maps


def split_filter(ids: list[str], splits: set[str], maps: list[dict[str, str]]) -> tuple[set[str], dict]:
    """Inscription ids allowed under ``splits`` plus a provenance record for coverage.json."""
    if not maps:
        raise ValueError("--splits needs at least one benchmark inscriptions.jsonl")
    allowed, held_out, unlisted = set(), [], []
    for i in ids:
        got = [m.get(i) for m in maps]
        if any(g is None for g in got):
            unlisted.append(i)
        elif all(g in splits for g in got):
            allowed.add(i)
        else:
            held_out.append(i)
    return allowed, {
        "used": sorted(splits, key=SPLITS.index),
        "benchmarks": [
            {"inscriptions": len(m), "per_split": {s: sum(1 for v in m.values() if v == s) for s in SPLITS},
             "sha256": hashlib.sha256(json.dumps(sorted(m.items())).encode()).hexdigest()}
            for m in maps
        ],
        "excluded_held_out": len(held_out),
        "excluded_not_in_benchmark": len(unlisted),
        "included_inscriptions": sorted(allowed),
    }


class Registry:
    def __init__(self) -> None:
        self.entities: dict[str, dict] = {}
        self.refs: dict[str, Counter] = defaultdict(Counter)  # id -> Counter("<ins>:<line>" or "<ins>")
        self.ins: dict[str, set[str]] = defaultdict(set)
        self.seeded: set[str] = set()

    def add(self, kind: str, slug_: str, label_iso: str, *, seeded: bool = True, **fields) -> str:
        eid = f"ez:{kind}/{slug_}"
        rec = self.entities.get(eid)
        if rec is None:
            rec = {
                "id": eid,
                "kind": kind,
                "label_iso": label_iso,
                "label_ta": fields.pop("label_ta", None) or _ta(label_iso),
                "variants": [],
                "era": None,
                "dynasty": None,
                "broader": None,
                "wikidata": None,
                "attested_in": [],
            }
            self.entities[eid] = rec
            if seeded:
                self.seeded.add(eid)
        for v in fields.pop("variants", None) or []:
            if v and v not in rec["variants"]:
                rec["variants"].append(v)
        for k, v in fields.items():
            if v is not None and rec.get(k) in (None, [], ""):
                rec[k] = v
        return eid

    def attest(self, eid: str, ins_id: str, line_n: str | None = None) -> None:
        self.refs[eid][f"{ins_id}:{line_n}" if line_n else ins_id] += 1
        self.ins[eid].add(ins_id)


def _git_head(path: Path) -> str | None:
    try:
        return subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def load_seeds(seed_dir: Path) -> dict:
    out: dict = {}
    for p in sorted(seed_dir.glob("*.yaml")):
        out.update(yaml.safe_load(p.read_text(encoding="utf-8")))
    return out


def _register_seeds(reg: Registry, seeds: dict) -> dict[str, dict]:
    """Register curated entities. Returns per-entity seed metadata used later in the build."""
    meta: dict[str, dict] = {}
    for d in seeds["dynasties"]:
        eid = reg.add("dynasty", d["slug"], d["label_iso"], variants=d.get("variants"), era=d.get("era"),
                      wikidata=d.get("wikidata"))
        meta[eid] = d
    for r in seeds["rulers"]:
        eid = reg.add("ruler", r["slug"], r["label_iso"], variants=r.get("variants"), era=r.get("era"),
                      dynasty=f"ez:dynasty/{r['dynasty']}", broader=f"ez:dynasty/{r['dynasty']}", note=r.get("note"))
        meta[eid] = r
    for t in seeds["titles"]:
        dyn = f"ez:dynasty/{t['dynasty']}" if t.get("dynasty") else None
        eid = reg.add("title", t["slug"], t["label_iso"], variants=t.get("variants"), dynasty=dyn,
                      label_en=t.get("label_en"), note=t.get("note"))
        meta[eid] = t
    for f in seeds["formulas"]:
        dyn = f"ez:dynasty/{f['dynasty']}" if f.get("dynasty") else None
        ruler = f"ez:ruler/{f['ruler']}" if f.get("ruler") else None
        eid = reg.add("formula", f["slug"], f["label_iso"], variants=f.get("variants"), dynasty=dyn, ruler=ruler,
                      label_en=f.get("label_en"), note=f.get("note"))
        meta[eid] = f
    simple = {"grant_types": "grant_type", "assemblies": "assembly", "measures": "measure", "coins": "coin",
              "taxes": "tax", "deities": "deity"}
    for section, kind in simple.items():
        for g in seeds[section]:
            extra = {k: g[k] for k in ("label_en", "note", "unit_of", "deity_of") if g.get(k)}
            eid = reg.add(kind, g["slug"], g["label_iso"], variants=g.get("variants"), **extra)
            meta[eid] = g
    for u in seeds["admin_unit_types"]:
        eid = reg.add("admin_unit", u["slug"], u["label_iso"], variants=list(u.get("suffixes") or []),
                      unit_type=u["slug"], is_type=True, rank=u["rank"], label_en=u.get("label_en"))
        meta[eid] = u
    return meta


def _title_index(seeds: dict) -> list[tuple[str, str]]:
    idx = []
    for kind, section in (("ruler", "rulers"), ("title", "titles")):
        for r in seeds[section]:
            for name in [*r.get("title_names", [])]:
                idx.append((fold(name), f"ez:{kind}/{r['slug']}"))
    idx.sort(key=lambda x: -len(x[0]))
    return idx


def parse_title(title: str) -> dict:
    segs = [s.strip() for s in title.split(",") if s.strip()]
    out: dict = {"place": None, "temple": None, "names": []}
    if not segs:
        return out
    place = re.sub(r"\s*\(.*?\)\s*", " ", segs[0])
    place = re.sub(r"\s+(copper[- ])?(plates?|grant)\b.*$", "", place, flags=re.IGNORECASE)
    place = re.sub(r"\s+(inscription|bronze|label|pillar|stone|rock)\b.*$", "", place, flags=re.IGNORECASE).strip()
    if place and not _NOT_PLACE.search(place) and len(place) > 2:
        out["place"] = place
    for seg in segs[1:]:
        m = re.match(r"(?:time of|inscription of|grant of)\s+(.+)$", seg, re.IGNORECASE)
        if m:
            out["names"].append(re.sub(r"\s*\(\?\)|\bking\b", "", m.group(1)).strip())
        elif out["temple"] is None and _TEMPLE.search(seg) and not re.search(r"\byear\b|plates?|curse|label", seg, re.IGNORECASE):
            out["temple"] = seg
    m = re.search(r"(?:plates?|inscription) of (.+?)(?:,|$)", segs[0], re.IGNORECASE)
    if m:
        out["names"].append(m.group(1).strip())
    return out


def _names_to_ids(names: list[str], index: list[tuple[str, str]]) -> tuple[list[str], list[str]]:
    found, unmatched = [], []
    for name in names:
        f = fold(name)
        hit = False
        for nk, eid in index:
            if nk and nk in f:
                f = f.replace(nk, " " * len(nk))
                if eid not in found:
                    found.append(eid)
                hit = True
        if not hit and name and not re.fullmatch(r"[\W\dX]*|\[.*\]|unspecified", name):
            unmatched.append(name)
    return found, unmatched


def _stages_for(ins: Inscription, found: list[str], reg: Registry, meta: dict) -> list[str]:
    stages = []
    tamil_stage = None
    for eid in found:
        m = meta.get(eid, {})
        if m.get("tamil_stage"):
            tamil_stage = m["tamil_stage"]
            break
    if tamil_stage is None:
        dyns = [reg.entities[e]["dynasty"] for e in found if reg.entities[e].get("dynasty")]
        dyn = dyns[0] if dyns else (
            f"ez:dynasty/{COLLECTION_DEFAULT_DYNASTY[ins.collection]}" if ins.collection in COLLECTION_DEFAULT_DYNASTY else None
        )
        if dyn:
            tamil_stage = meta.get(dyn, {}).get("tamil_stage")
    for cls in ins.script_classes:
        st = tamil_stage if cls == "tamil" else CLASS_STAGE.get(cls)
        if st and st not in stages:
            stages.append(st)
    return stages


def _extract_admin_units(reg: Registry, ins: Inscription, unit_types: list[dict], votes: dict) -> None:
    sufs = sorted(
        ((key(s), s, u) for u in unit_types for s in (u.get("suffixes") or [])), key=lambda x: -len(x[0])
    )
    for line in ins.lines:
        words = line.text.split()
        mentions: list[tuple[int, int, str]] = []
        for wi, word in enumerate(words):
            if "[" in word or (wi > 0 and "[?" in words[wi - 1]):
                continue
            wk = key(word)
            for sk, suf, u in sufs:
                if not wk.endswith(sk):
                    continue
                if len(wk) < len(sk) + 3:
                    break  # the bare term (or a 1-2 letter fragment): no unit name here
                surface = re.sub(rf"{re.escape(suf)}$", "", word)
                if surface == word:  # suffix spelt differently (gemination, e/ē); strip by key length
                    surface = word[: max(0, len(word) - len(suf))]
                surface = re.sub(r"[-=\s’']*(?:(?<=-)(?:k|c|p|t|ṭ|v|y)[-=]*)?$", "", surface).strip("-=’' ")
                nk = key(surface)
                if len(nk) < 3 or nk in {"in", "ik", "im", "ip", "ic", "it", "ivv", "av", "ac"}:
                    break
                label = surface[:1].upper() + surface[1:] + "-" + u["label_iso"]
                eid = reg.add("admin_unit", f"{slug(nk)}-{u['slug']}", label, seeded=False,
                              variants=[f"{surface}-{suf}"], unit_type=u["slug"], rank=u["rank"],
                              )
                reg.attest(eid, ins.id, line.n)
                reg.attest(f"ez:admin_unit/{u['slug']}", ins.id, line.n)
                mentions.append((wi, u["rank"], eid))
                break
        for i, (wi, rank, eid) in enumerate(mentions):
            for wj, rank2, eid2 in reversed(mentions[:i]):
                if wi - wj > 4:
                    break
                if rank2 > rank:
                    votes[eid][eid2] += 1
                    break


def build(dharma_root: Path, out_dir: Path = ONTOLOGY_DIR, wikidata_snapshot: Path | None = None,
          splits: set[str] | None = None, benchmarks: list[Path] | None = None) -> dict:
    """Build the artefacts. ``splits=None`` uses every edition (fixtures, local exploration);
    ``splits={"train"}`` with ``benchmarks`` is the shipped, leakage-free build."""
    seeds = load_seeds(out_dir / "seeds")
    reg = Registry()
    meta = _register_seeds(reg, seeds)
    title_idx = _title_index(seeds)
    index = VariantIndex()
    for eid, rec in reg.entities.items():
        if rec["kind"] == "admin_unit":
            continue  # unit types are attested through instance extraction
        for v in rec["variants"]:
            index.add(eid, v)

    inscriptions = list(iter_corpus(dharma_root))
    split_info: dict = {"used": "all", "included_inscriptions": None}
    if splits is not None:
        bad = set(splits) - set(SPLITS)
        if bad:
            raise ValueError(f"unknown split(s): {sorted(bad)}")
        allowed, split_info = split_filter([i.id for i in inscriptions], set(splits),
                                           load_split_map(list(benchmarks or [])))
        inscriptions = [i for i in inscriptions if i.id in allowed]
    ins_meta: dict[str, dict] = {}
    unmatched_names: Counter = Counter()
    unmapped_classes: Counter = Counter()
    stage_texts: dict[str, list[tuple[str, str]]] = defaultdict(list)
    admin_votes: dict[str, Counter] = defaultdict(Counter)
    place_variants: dict[str, Counter] = defaultdict(Counter)

    for ins in inscriptions:
        t = parse_title(ins.title)
        found, unmatched = _names_to_ids(t["names"], title_idx)
        unmatched_names.update(unmatched)
        for eid in found:
            reg.attest(eid, ins.id)
            dyn = reg.entities[eid].get("dynasty")
            if dyn:
                reg.attest(dyn, ins.id)
        place_id = None
        if t["place"] and not _names_to_ids([t["place"]], title_idx)[0]:
            spellings = [p.strip() for p in t["place"].split("/") if p.strip()]
            place_id = reg.add("place", slug(spellings[0]), spellings[0], seeded=False, variants=spellings,
                               source="dharma-title")
            place_variants[place_id][spellings[0]] += 1
            reg.attest(place_id, ins.id)
        if t["temple"] and "*" not in t["temple"] and place_id:
            temple_label = t["temple"]
            temple_key = re.sub(r"\s+temple$", "", temple_label, flags=re.IGNORECASE)
            deity = "ez:deity/siva" if _SIVA.search(temple_label) else "ez:deity/vishnu" if _VISHNU.search(temple_label) else None
            tid = reg.add(
                "temple", slug(f"{reg.entities[place_id]['variants'][0]}-{temple_key}"), temple_label, seeded=False,
                variants=[temple_label], broader=place_id, place=reg.entities[place_id]["variants"][0], deity=deity,
                source="dharma-title",
            )
            reg.attest(tid, ins.id)
        for pn in ins.place_names:
            pn_clean = pn.strip(" .;,")
            if len(key(pn_clean)) >= 3:
                pid = reg.add("place", slug(pn_clean), pn_clean[:1].upper() + pn_clean[1:], seeded=False,
                              variants=[pn_clean], source="dharma-placeName")
                reg.attest(pid, ins.id)
        stages = _stages_for(ins, found, reg, meta)
        for cls in ins.script_classes:
            if cls != "tamil" and cls not in CLASS_STAGE:
                unmapped_classes[cls] += 1
        for st in stages:
            reg.attest(f"ez:script_stage/{st}", ins.id)
        if len(stages) == 1:
            stage_texts[stages[0]].extend((ins.id, ln.text) for ln in ins.lines)
        for line in ins.lines:
            for m in index.scan(line.text):
                reg.attest(m.entity_id, ins.id, line.n)
        _extract_admin_units(reg, ins, seeds["admin_unit_types"], admin_votes)
        ins_meta[ins.id] = {
            "collection": ins.collection,
            "title": ins.title,
            "stages": stages,
            "mentions": found,
            "place": place_id,
        }

    # script stages and letters (registered after the scan so stage attestations exist)
    letters_doc: dict = {"stages": {}, "levels": L.LEVEL_STAGES}
    for st, sm in L.STAGES.items():
        reg.add("script_stage", st, sm["label_iso"], label_ta=sm.get("label_ta"), era=sm["era"], order=sm["order"],
                aksharamukha_script=sm["script"])
        counts: Counter = Counter()
        where: dict[str, list[str]] = defaultdict(list)
        for ins_id, text in stage_texts.get(st, []):
            for letter in L.base_letters(text):
                counts[letter] += 1
                if len(where[letter]) < 10 and (not where[letter] or where[letter][-1] != ins_id):
                    where[letter].append(ins_id)
        items = []
        for item in L.letters_for(st):
            n = sum(counts.get(v, 0) for v in item["iso_values"])
            item = {**item, "corpus_count": n}
            items.append(item)
            lid = reg.add("letter", f"{st}-{L.letter_slug(item['iso'])}", item["iso"],
                          label_ta=item["glyph"] if st.endswith("tamil") else None, era=sm["era"],
                          broader=f"ez:script_stage/{st}", stage=st, glyph=item["glyph"], letter_type=item["type"],
                          iso_values=item["iso_values"], corpus_count=n, grantha=item.get("grantha", False))
            for ins_id in where.get(item["iso"], []):
                reg.attest(lid, ins_id)
        letters_doc["stages"][st] = {
            "label_iso": sm["label_iso"],
            "label_ta": sm.get("label_ta"),
            "era": sm["era"],
            "aksharamukha_script": sm["script"],
            "corpus_letters": sum(counts.values()),
            "letters": items,
            "exceptions": L.exceptions_for(st),
        }

    # admin unit hierarchy from address chains (mandalam > kottam/valanadu > nadu/kurram)
    for eid, votes in admin_votes.items():
        if eid in reg.entities and votes:
            reg.entities[eid]["broader"] = votes.most_common(1)[0][0]

    # most frequent spelling as the place label
    for pid, c in place_variants.items():
        reg.entities[pid]["label_iso"] = c.most_common(1)[0][0]
        reg.entities[pid]["label_ta"] = _ta(reg.entities[pid]["label_iso"])

    # Wikidata identifiers from the reviewed snapshot
    snapshot = json.loads(wikidata_snapshot.read_text()) if wikidata_snapshot and wikidata_snapshot.exists() else {}
    for eid, qid in (snapshot.get("resolved") or {}).items():
        if eid in reg.entities and qid:
            reg.entities[eid]["wikidata"] = qid

    # finalise: attested_in, drop unattested seeds and fragment admin units
    dropped: dict[str, list[str]] = defaultdict(list)
    final: dict[str, list[dict]] = {k: [] for k in KINDS}
    for eid, rec in sorted(reg.entities.items()):
        n_ins = len(reg.ins.get(eid, ()))
        if rec["kind"] not in ("script_stage", "letter") and n_ins == 0:
            dropped[rec["kind"]].append(eid)
            continue
        if rec["kind"] == "admin_unit" and not rec.get("is_type") and n_ins < 2 and len(key(rec["label_iso"])) < 10:
            dropped["admin_unit_fragment"].append(eid)
            continue
        refs = reg.refs.get(eid, Counter())
        ordered = sorted(refs, key=lambda r: (r.split(":")[0], _line_key(r)))
        rec["attested_in"] = ordered[:MAX_REFS]
        rec["attestation_count"] = sum(refs.values())
        rec["inscription_count"] = n_ins
        final[rec["kind"]].append(rec)
    # drop dangling references (e.g. a temple's deity that was itself unattested)
    kept = {r["id"] for recs in final.values() for r in recs}
    for recs in final.values():
        for r in recs:
            for fld in ("broader", "dynasty", "ruler", "deity"):
                if r.get(fld) and r[fld] not in kept:
                    r[fld] = None

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "lookups").mkdir(exist_ok=True)
    for kind, recs in final.items():
        _dump(out_dir / "lookups" / f"{kind}.json", recs)
    _dump(out_dir / "letters_by_era.json", letters_doc)

    pins = {c.name: _git_head(c) for c in sorted(dharma_root.iterdir()) if c.is_dir()}
    wd_kinds = ("dynasty", "ruler", "temple", "place")
    coverage = {
        "corpus": {"collections": pins, "inscriptions": len(inscriptions),
                   "lines": sum(len(i.lines) for i in inscriptions)},
        "splits": split_info,
        "entities_per_kind": {k: len(v) for k, v in final.items()},
        "wikidata": {
            k: {"with_qid": sum(1 for r in final[k] if r["wikidata"]), "total": len(final[k]),
                "pct": round(100 * sum(1 for r in final[k] if r["wikidata"]) / len(final[k]), 1) if final[k] else 0.0}
            for k in wd_kinds
        },
        "seed_entities_dropped_unattested": {k: sorted(v) for k, v in dropped.items() if k != "admin_unit_fragment"},
        "admin_unit_fragments_dropped": len(dropped.get("admin_unit_fragment", [])),
        "title_names_unmatched": dict(unmatched_names.most_common()),
        "script_classes_unmapped": dict(unmapped_classes),
        "inscriptions_per_stage": {st: len(reg.ins.get(f"ez:script_stage/{st}", ())) for st in L.STAGES},
    }
    _dump(out_dir / "coverage.json", coverage)

    from ezhuthu.ontology.owl import build_graph

    g = build_graph(final, ins_meta, DHARMA_URL, reg.ins)
    (out_dir / "ezhuthu.ttl").write_text(g.serialize(format="turtle"), encoding="utf-8")
    return coverage


def _line_key(ref: str):
    parts = ref.split(":", 1)
    if len(parts) == 1:
        return (0, 0, "")
    m = re.match(r"(\d+)", parts[1])
    return (1, int(m.group(1)) if m else 10**6, parts[1])


def _dump(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=False) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dharma", type=Path, default=REPO / "data" / "raw" / "dharma")
    ap.add_argument("--out", type=Path, default=ONTOLOGY_DIR)
    ap.add_argument("--wikidata", type=Path, default=ONTOLOGY_DIR / "wikidata" / "snapshot.json")
    ap.add_argument("--splits", default="train",
                    help="comma-separated benchmark splits to build from (default: train), or 'all'")
    ap.add_argument("--benchmark", type=Path, action="append",
                    help="benchmark inscriptions.jsonl (repeatable; default benchmark/inscriptions.jsonl). "
                         "With several files an edition must be in an allowed split in every one.")
    args = ap.parse_args(argv)
    splits = None if args.splits == "all" else {s.strip() for s in args.splits.split(",") if s.strip()}
    benchmarks = args.benchmark or [REPO / "benchmark" / "inscriptions.jsonl"]
    if splits is not None:
        missing = [str(b) for b in benchmarks if not b.exists()]
        if missing:
            ap.error(f"benchmark file(s) not found: {missing} (run the data team's benchmark build, or pass --splits all)")
    cov = build(args.dharma, args.out, args.wikidata, splits, benchmarks)
    print(json.dumps({k: cov[k] for k in ("entities_per_kind", "wikidata", "inscriptions_per_stage")}, indent=1))


if __name__ == "__main__":
    main()
