"""COA S3 Vectors naming, the COA patch artefact, and the COA branding guard."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from ezhuthu.ontology import coa_store

ROOT = Path(__file__).resolve().parents[2]
PATCH_DIR = ROOT / "ontology" / "coa" / "patches"


def test_tenant_id_matches_coa_example():
    # coa_common.constants.to_graphrag_tenant_id docstring example (v0.3.8)
    assert coa_store.tenant_id("550e8400-e29b-41d4-a716-446655440000") == "550e8400e29b41d4a71644665"


def test_tenant_id_rejects_non_hex():
    with pytest.raises(ValueError):
        coa_store.tenant_id("not-a-uuid`;")


def test_index_names_match_graphrag_docs():
    # graphrag-toolkit S3 Vectors docs: s3vectors://bucket -> chunk, chunk-admin;
    # s3vectors://bucket/app1 -> app1.chunk, app1.chunk-admin
    assert coa_store.index_name("chunk", "", None) == "chunk"
    assert coa_store.index_name("chunk", "admin", None) == "chunk-admin"
    assert coa_store.index_name("chunk", "", "app1") == "app1.chunk"
    assert coa_store.index_name("chunk", "admin", "app1") == "app1.chunk-admin"


def test_plan_is_deterministic_and_valid():
    p = coa_store.plan()
    assert p == coa_store.plan()
    assert p["vector_store_uri"] == "s3vectors://ezhuthu-coa-vectors/ezhuthu"
    assert p["tenant"] == "b0310331b8d553b7b3ebfbf51"
    assert p["dimension"] == 1024
    assert p["indexes"] == [f"ezhuthu.{i}-{p['tenant']}" for i in ("chunk", "statement", "topic")]
    assert all(3 <= len(n) <= 63 for n in p["indexes"])
    assert set(p["tags"]) == {"Project", "Owner", "Env", "CostCenter"}


def test_patch_touches_documented_files():
    patches = sorted(PATCH_DIR.glob("*.patch"))
    assert [p.name for p in patches] == ["0001-coa-v0.3.8-s3-vectors-falkordb.patch"]
    text = patches[0].read_text()
    files = re.findall(r"^diff --git a/(\S+) b/", text, re.MULTILINE)
    assert len(files) == 6
    readme = (PATCH_DIR / "README.md").read_text()
    for f in files:
        assert Path(f).name in readme, f
    # never provisions Neptune or OpenSearch resources
    added = "\n".join(line for line in text.splitlines() if line.startswith("+"))
    assert "create_collection" not in added and "create_db_cluster" not in added


def test_no_built_with_coa_claim_until_a_run_is_recorded():
    coa_md = (ROOT / "ontology" / "COA.md").read_text()
    claim = "built with AWS Context Ontology Accelerator"
    if "COA was not run" in coa_md.split("\n## ")[0]:
        for path in (ROOT / "README.md", ROOT / "ontology" / "README.md"):
            assert claim.lower() not in path.read_text().lower(), path
