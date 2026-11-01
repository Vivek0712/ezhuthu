"""End-to-end build on the fixture corpus into a temp dir (offline, deterministic)."""

import json
import shutil
from pathlib import Path

import jsonschema
from rdflib import RDF, Graph

from ezhuthu.ontology.build import build, parse_title
from ezhuthu.ontology.owl import EZ

HERE = Path(__file__).parent
REPO = HERE.parents[1]


def _run(tmp: Path) -> Path:
    out = tmp / "ontology"
    (out / "seeds").mkdir(parents=True)
    for p in (REPO / "ontology" / "seeds").glob("*.yaml"):
        shutil.copy(p, out / "seeds" / p.name)
    build(HERE / "fixtures" / "dharma", out, wikidata_snapshot=None)
    return out


def test_fixture_build_outputs_valid_lookups_and_ttl(tmp_path):
    out = _run(tmp_path)
    schema = json.loads((REPO / "contracts" / "ontology-lookup.schema.json").read_text())
    ids = {}
    for p in (out / "lookups").glob("*.json"):
        for rec in json.loads(p.read_text()):
            jsonschema.validate(rec, schema)
            ids[rec["id"]] = rec
    assert ids["ez:ruler/rajaraja-i"]["attested_in"] == ["DHARMA_INSTest00002"]
    assert "DHARMA_INSTest00001:1" in ids["ez:title/parakesarivarman"]["attested_in"]
    assert ids["ez:formula/tirumakal-pola"]["attested_in"] == ["DHARMA_INSTest00002:1"]
    kottam = ids["ez:admin_unit/kaliyur-kottam"]
    assert kottam["broader"] == "ez:admin_unit/jayankontacozha-mandalam"
    assert ids["ez:place/pazhuvur"]["source"] == "dharma-placeName"
    assert ids["ez:temple/tanjore-brhadisvara"]["deity"] is None  # Śiva deity entity not attested here
    assert "ez:ruler/kampavarman" not in ids  # seed not attested in the fixture corpus: dropped
    cov = json.loads((out / "coverage.json").read_text())
    assert "ez:ruler/kampavarman" in cov["seed_entities_dropped_unattested"]["ruler"]
    assert cov["inscriptions_per_stage"]["chola-tamil"] == 2
    g = Graph().parse(out / "ezhuthu.ttl")
    assert (EZ["inscription/DHARMA_INSTest00002"], RDF.type, EZ.Inscription) in g


def test_build_is_deterministic(tmp_path):
    a = _run(tmp_path / "a")
    b = _run(tmp_path / "b")
    for name in ("ezhuthu.ttl", "letters_by_era.json", "coverage.json", "lookups/admin_unit.json"):
        assert (a / name).read_bytes() == (b / name).read_bytes(), name


def test_parse_title_variants():
    t = parse_title("Uttiramērūr, Vaikuṇṭha-Perumāḷ, time of Parakesarivarman, year 12")
    assert t == {"place": "Uttiramērūr", "temple": "Vaikuṇṭha-Perumāḷ", "names": ["Parakesarivarman"]}
    t = parse_title("Mayidavōlu plates, time of Śiva-Skandavarman, year 10")
    assert t["place"] == "Mayidavōlu" and t["temple"] is None
    t = parse_title("Tirucceṉṉampūṇṭi, time of Nantippōttaraiyar (?)")
    assert t["names"] == ["Nantippōttaraiyar"]
