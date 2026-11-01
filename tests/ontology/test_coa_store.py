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
    # COA's default EMBEDDING_INDEXES: no Serve strategy reads a statement index
    assert p["indexes"] == [f"ezhuthu.{i}-{p['tenant']}" for i in ("chunk", "topic")]
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
    # A COA run is recorded by its reconciliation report, not by wording in COA.md.
    claim = "built with AWS Context Ontology Accelerator"
    if not (ROOT / "ontology" / "coa" / "RECONCILE.md").exists():
        for path in (ROOT / "README.md", ROOT / "ontology" / "README.md", ROOT / "ontology" / "COA.md"):
            text = path.read_text().lower()
            # COA.md may quote the rule itself ("Do not use ..."); any other use is a claim.
            text = text.replace(f'do not use "{claim.lower()}"', "")
            assert claim.lower() not in text, path


class _Conflict(Exception):
    pass


class FakeS3Vectors:
    """Just enough of the boto3 s3vectors client for coa_store.create."""

    class exceptions:  # mirrors boto3 client.exceptions
        ConflictException = _Conflict

    def __init__(self, existing_index: dict | None = None, tags: dict | None = None):
        self.bucket = None
        self.indexes: dict[str, dict] = {}
        self.tags: dict[str, dict] = {}
        self.tag_calls = 0
        self._existing_index = existing_index
        self._existing_tags = tags

    def create_vector_bucket(self, vectorBucketName, encryptionConfiguration, tags):
        arn = f"arn:bucket/{vectorBucketName}"
        if self.bucket:
            raise _Conflict()
        self.bucket = {"vectorBucketName": vectorBucketName, "vectorBucketArn": arn}
        self.tags[arn] = dict(tags)

    def get_vector_bucket(self, vectorBucketName):
        return {"vectorBucket": self.bucket}

    def create_index(self, vectorBucketName, indexName, dataType, dimension, distanceMetric, metadataConfiguration, tags):
        arn = f"arn:index/{indexName}"
        if indexName in self.indexes:
            raise _Conflict()
        if self._existing_index is not None:  # simulate a pre-existing, differently built index
            self.indexes[indexName] = {"indexName": indexName, "indexArn": arn, **self._existing_index}
            self.tags[arn] = dict(self._existing_tags or {})
            raise _Conflict()
        self.indexes[indexName] = {"indexName": indexName, "indexArn": arn, "dataType": dataType,
                                   "dimension": dimension, "distanceMetric": distanceMetric}
        self.tags[arn] = dict(tags)

    def get_index(self, vectorBucketName, indexName):
        return {"index": self.indexes[indexName]}

    def list_tags_for_resource(self, resourceArn):
        return {"tags": dict(self.tags.get(resourceArn, {}))}

    def tag_resource(self, resourceArn, tags):
        self.tag_calls += 1
        self.tags.setdefault(resourceArn, {}).update(tags)


def test_create_then_rerun_verifies():
    p = coa_store.plan()
    c = FakeS3Vectors()
    first = coa_store.create(p, client=c)
    again = coa_store.create(p, client=c)  # idempotent re-run: conflicts are verified, not ignored
    assert first == again
    assert [i["indexName"] for i in first["indexes"]] == p["indexes"]
    assert all(i["dimension"] == 1024 and i["distanceMetric"] == "cosine" for i in first["indexes"])
    assert first["bucket_tags"] == p["tags"] and all(i["tags"] == p["tags"] for i in first["indexes"])
    assert c.tag_calls == 0


def test_existing_index_with_wrong_dimension_fails():
    c = FakeS3Vectors(existing_index={"dataType": "float32", "dimension": 1536, "distanceMetric": "cosine"},
                      tags=coa_store.TAGS)
    with pytest.raises(coa_store.PlanMismatch, match="1536"):
        coa_store.create(coa_store.plan(), client=c)


def test_existing_index_with_wrong_metric_fails():
    c = FakeS3Vectors(existing_index={"dataType": "float32", "dimension": 1024, "distanceMetric": "euclidean"},
                      tags=coa_store.TAGS)
    with pytest.raises(coa_store.PlanMismatch, match="euclidean"):
        coa_store.create(coa_store.plan(), client=c)


def test_missing_tags_on_existing_index_are_reapplied():
    c = FakeS3Vectors(existing_index={"dataType": "float32", "dimension": 1024, "distanceMetric": "cosine"},
                      tags={"Project": "ezhuthu"})
    out = coa_store.create(coa_store.plan(), client=c)
    assert all(i["tags"] == coa_store.TAGS for i in out["indexes"])
    assert c.tag_calls == len(out["indexes"])
