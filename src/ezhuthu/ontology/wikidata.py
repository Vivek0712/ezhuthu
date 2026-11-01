"""Resolve Wikidata QIDs for dynasties, rulers, places and temples via the public SPARQL endpoint.

    python -m ezhuthu.ontology.wikidata --refresh      # network; writes ontology/wikidata/snapshot.json
    python -m ezhuthu.ontology.build                   # offline; reads the snapshot

Resolution is deliberately conservative: an entity gets a QID only when exactly one Wikidata item
matches one of its English label forms under the filter for its kind (a human for rulers; an
item located in Tamil Nadu for places and temples). Every candidate set is kept in the snapshot
so a reviewer can see why something resolved or did not. Seeds that already carry a reviewed QID
(dynasties) are kept as is.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "ezhuthu-ontology/0.1 (https://github.com/Vivek0712/ezhuthu; education project)"
TAMIL_NADU = "Q1445"
REPO = Path(__file__).resolve().parents[3]
ONTOLOGY_DIR = REPO / "ontology"


def ascii_forms(name: str) -> list[str]:
    """English label guesses for an ISO-15919 name: ``Kāñcipuram`` -> ``Kancipuram``, ``Kanchipuram``."""
    s = unicodedata.normalize("NFC", name).replace("ḻ", "zh").replace("Ḻ", "Zh")
    s = re.sub(r"\s*\(.*?\)", "", s)
    s = "".join(ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch))
    s = re.sub(r"[^A-Za-z /-]", "", s).strip()
    forms = {s, s.replace("-", ""), s.replace("-", " ")}
    more = set()
    for f in forms:
        more.add(re.sub(r"c(?!h)", "ch", f))
        more.add(f.replace("zh", "l"))
        more.add(re.sub(r"^Tiru", "Thiru", f))
        more.add(re.sub(r"^Tiru", "Thiru", re.sub(r"c(?!h)", "ch", f)))
    forms |= more
    return sorted({" ".join(w[:1].upper() + w[1:] for w in f.split()) for f in forms if len(f) > 2})


def sparql(query: str, retries: int = 3) -> list[dict]:
    url = ENDPOINT + "?" + urllib.parse.urlencode({"query": query, "format": "json"})
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/sparql-results+json"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                return json.load(resp)["results"]["bindings"]
        except Exception:  # pragma: no cover - network
            if attempt == retries - 1:
                raise
            time.sleep(5 * (attempt + 1))
    return []


def _lit(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"@en'


def label_query(labels: list[str], filter_clause: str) -> str:
    values = " ".join(_lit(x) for x in labels)
    return f"""SELECT DISTINCT ?item ?lab ?itemLabel ?itemDescription WHERE {{
  VALUES ?lab {{ {values} }}
  {{ ?item rdfs:label ?lab }} UNION {{ ?item skos:altLabel ?lab }}
  {filter_clause}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}"""


FILTERS = {
    "ruler": "?item wdt:P31 wd:Q5 .",
    "dynasty": "",
    "place": f"?item wdt:P131+ wd:{TAMIL_NADU} .",
    "temple": f"?item wdt:P131+ wd:{TAMIL_NADU} . ?item wdt:P31/wdt:P279* wd:Q44539 .",
}


def _candidates(kind: str, forms_by_eid: dict[str, list[str]], batch: int = 60) -> dict[str, list[dict]]:
    by_label: dict[str, list[str]] = {}
    for eid, forms in forms_by_eid.items():
        for f in forms:
            by_label.setdefault(f, []).append(eid)
    labels = sorted(by_label)
    out: dict[str, dict[str, dict]] = {eid: {} for eid in forms_by_eid}
    for i in range(0, len(labels), batch):
        rows = sparql(label_query(labels[i : i + batch], FILTERS[kind]))
        for r in rows:
            qid = r["item"]["value"].rsplit("/", 1)[1]
            for eid in by_label.get(r["lab"]["value"], []):
                out[eid][qid] = {
                    "qid": qid,
                    "label": r.get("itemLabel", {}).get("value"),
                    "description": r.get("itemDescription", {}).get("value"),
                    "matched": r["lab"]["value"],
                }
        time.sleep(1)
    return {eid: sorted(c.values(), key=lambda x: x["qid"]) for eid, c in out.items()}


def refresh(ontology_dir: Path = ONTOLOGY_DIR) -> dict:
    seeds = yaml.safe_load((ontology_dir / "seeds" / "dynasties_rulers.yaml").read_text(encoding="utf-8"))
    lookups = {k: json.loads((ontology_dir / "lookups" / f"{k}.json").read_text()) for k in ("place", "temple")}
    resolved: dict[str, str] = {}
    candidates: dict[str, list[dict]] = {}
    for d in seeds["dynasties"]:
        if d.get("wikidata"):
            resolved[f"ez:dynasty/{d['slug']}"] = d["wikidata"]
    dyn_forms = {f"ez:dynasty/{d['slug']}": [d["wikidata_label"]] for d in seeds["dynasties"]
                 if d.get("wikidata_label") and not d.get("wikidata")}
    ruler_forms = {f"ez:ruler/{r['slug']}": [r["wikidata_label"]] for r in seeds["rulers"] if r.get("wikidata_label")}
    place_forms = {r["id"]: sorted({f for v in r["variants"] or [r["label_iso"]] for f in ascii_forms(v)})
                   for r in lookups["place"]}
    temple_forms = {}
    for r in lookups["temple"]:
        base = re.sub(r"\s+temple$", "", r["label_iso"], flags=re.IGNORECASE)
        forms = set()
        for b in ascii_forms(base):
            forms |= {f"{b} Temple", f"{b} temple"}
            for p in ascii_forms(r.get("place") or ""):
                forms.add(f"{b} Temple, {p}")
        temple_forms[r["id"]] = sorted(forms)
    for kind, forms in (("dynasty", dyn_forms), ("ruler", ruler_forms), ("place", place_forms), ("temple", temple_forms)):
        cands = _candidates(kind, forms)
        for eid, cs in cands.items():
            candidates[eid] = cs
            if len(cs) == 1:
                resolved[eid] = cs[0]["qid"]
    snap: dict = {
        "queried_at": dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "endpoint": ENDPOINT,
        "filters": FILTERS,
        "rule": "QID assigned only when exactly one item matches an English label/alias form under the kind filter",
        "resolved": dict(sorted(resolved.items())),
        "candidates": {k: v for k, v in sorted(candidates.items()) if v},
        "unresolved_with_multiple_candidates": sorted(k for k, v in candidates.items() if len(v) > 1),
    }
    apply_review(snap, ontology_dir / "wikidata" / "review.yaml")
    path = ontology_dir / "wikidata" / "snapshot.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snap, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return snap


def apply_review(snap: dict, review_path: Path) -> dict:
    """Apply ontology/wikidata/review.yaml (manual rejects/accepts) to a snapshot, in place."""
    review = yaml.safe_load(review_path.read_text(encoding="utf-8")) if review_path.exists() else {}
    resolved = dict(snap.get("resolved") or {})
    for eid, r in (review.get("reject") or {}).items():
        if resolved.get(eid) == r["qid"]:
            del resolved[eid]
    for eid, r in (review.get("accept") or {}).items():
        resolved[eid] = r["qid"]
    snap["resolved"] = dict(sorted(resolved.items()))
    snap["review"] = review
    return snap


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--refresh", action="store_true", help="query Wikidata (network) and rewrite the snapshot")
    ap.add_argument("--review-only", action="store_true", help="re-apply review.yaml to the existing snapshot (offline)")
    args = ap.parse_args(argv)
    path = ONTOLOGY_DIR / "wikidata" / "snapshot.json"
    if args.review_only:
        snap = json.loads(path.read_text())
        snap["resolved"] = {**snap["resolved"], **{e: c[0]["qid"] for e, c in snap["candidates"].items() if len(c) == 1}}
        apply_review(snap, ONTOLOGY_DIR / "wikidata" / "review.yaml")
        path.write_text(json.dumps(snap, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    elif args.refresh:
        snap = refresh()
    else:
        ap.error("pass --refresh (network) or --review-only")
    print(json.dumps({"resolved": len(snap["resolved"]), "ambiguous": len(snap["unresolved_with_multiple_candidates"])}))


if __name__ == "__main__":
    main()
