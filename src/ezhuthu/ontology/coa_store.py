"""S3 Vectors store for a local Context Ontology Accelerator (COA) run.

COA v0.3.8 writes chunk and topic embeddings through graphrag-toolkit. With
``VECTOR_STORE_URI=s3vectors://<bucket>/<prefix>`` (see ``ontology/coa/patches``)
the toolkit names each index ``<prefix>.<index>-<tenant>`` and the tenant is COA's
``to_graphrag_tenant_id(namespace)``. This module computes those names and, with
``--create``, provisions the tagged vector bucket + indexes ahead of time (COA's
default embedding model is Cohere Embed v4 at 1024 dimensions, cosine). Existing
resources are verified: an index whose dimension, metric or data type differs from
the plan is an error, and missing cost tags are re-applied.

Indexes follow COA's own default ``EMBEDDING_INDEXES=chunk,topic`` (kg-build and
Serve's ``READ_EMBEDDING_INDEXES``); no COA Serve strategy reads a statement index.

    python -m ezhuthu.ontology.coa_store              # print the plan (no AWS call)
    python -m ezhuthu.ontology.coa_store --create     # create/verify on profile heisenberg
"""

from __future__ import annotations

import argparse
import json
import re
import uuid

BUCKET = "ezhuthu-coa-vectors"
PREFIX = "ezhuthu"
NAMESPACE_SEED = "https://w3id.org/ezhuthu/coa"
EMBED_MODEL_ID = "us.cohere.embed-v4:0"  # coa_common.constants.DEFAULT_EMBED_MODEL_ID (v0.3.8)
DIMENSIONS = 1024  # coa_common.constants.DEFAULT_EMBED_DIMENSIONS (v0.3.8)
INDEXES = ("chunk", "topic")  # COA kg-build default EMBEDDING_INDEXES (v0.3.8)
NON_FILTERABLE = ["value", "metadata"]  # graphrag s3_vector_indexes.NON_FILTERABLE_FIELDS
TAGS = {"Project": "ezhuthu", "Owner": "vivekraja", "Env": "hackathon", "CostCenter": "hero-credits"}
_INDEX_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$")


def namespace_id(seed: str = NAMESPACE_SEED) -> str:
    """Deterministic COA namespace UUID for Ezhuthu."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, seed))


def tenant_id(namespace: str) -> str:
    """COA ``to_graphrag_tenant_id``: hyphens stripped, first 25 chars, hex only."""
    value = namespace.replace("-", "")[:25]
    if not value or not re.fullmatch(r"[0-9a-f]+", value, re.IGNORECASE):
        raise ValueError(f"namespace must be a hex UUID, got {namespace!r}")
    return value


def index_name(index: str, tenant: str, prefix: str | None = PREFIX) -> str:
    """graphrag ``S3VectorIndex.underlying_index_name`` for a tenant-scoped index."""
    name = f"{index}_{tenant}" if tenant else index
    name = name.replace("_", "-")
    name = f"{prefix}.{name}" if prefix else name
    if not _INDEX_NAME_RE.match(name):
        raise ValueError(f"invalid S3 Vectors index name: {name!r}")
    return name


def vector_store_uri(bucket: str = BUCKET, prefix: str = PREFIX) -> str:
    return f"s3vectors://{bucket}/{prefix}"


def plan(namespace: str | None = None) -> dict:
    ns = namespace or namespace_id()
    tenant = tenant_id(ns)
    return {
        "bucket": BUCKET,
        "vector_store_uri": vector_store_uri(),
        "namespace": ns,
        "tenant": tenant,
        "embed_model_id": EMBED_MODEL_ID,
        "dimension": DIMENSIONS,
        "indexes": [index_name(i, tenant) for i in INDEXES],
        "tags": TAGS,
    }


class PlanMismatch(RuntimeError):
    """An existing S3 Vectors resource does not match the plan."""


def _ensure_tags(c, arn: str, tags: dict) -> dict:
    """Re-apply any plan tag that is missing or different; return the tags now set."""
    have = c.list_tags_for_resource(resourceArn=arn).get("tags", {})
    missing = {k: v for k, v in tags.items() if have.get(k) != v}
    if missing:
        c.tag_resource(resourceArn=arn, tags=missing)
        have = c.list_tags_for_resource(resourceArn=arn).get("tags", {})
    if any(have.get(k) != v for k, v in tags.items()):
        raise PlanMismatch(f"tags on {arn} are {have}, expected {tags}")
    return {k: have[k] for k in tags}


def create(p: dict, client=None, profile: str = "heisenberg", region: str = "us-east-1") -> dict:
    """Create the bucket and indexes, or verify existing ones against the plan.

    Raises ``PlanMismatch`` when an existing index has another dimension, metric or
    data type (those cannot be changed in place), or when tags cannot be set.
    """
    if client is None:  # pragma: no cover - live AWS
        import boto3

        client = boto3.Session(profile_name=profile, region_name=region).client("s3vectors")
    c = client
    conflict = c.exceptions.ConflictException
    try:
        c.create_vector_bucket(
            vectorBucketName=p["bucket"], encryptionConfiguration={"sseType": "AES256"}, tags=p["tags"]
        )
    except conflict:
        pass
    bucket = c.get_vector_bucket(vectorBucketName=p["bucket"])["vectorBucket"]
    out = {"bucket": p["bucket"], "bucket_tags": _ensure_tags(c, bucket["vectorBucketArn"], p["tags"]), "indexes": []}
    want = {"dimension": p["dimension"], "distanceMetric": "cosine", "dataType": "float32"}
    for name in p["indexes"]:
        try:
            c.create_index(
                vectorBucketName=p["bucket"], indexName=name, dataType="float32", dimension=p["dimension"],
                distanceMetric="cosine", metadataConfiguration={"nonFilterableMetadataKeys": NON_FILTERABLE},
                tags=p["tags"],
            )
        except conflict:
            pass
        idx = c.get_index(vectorBucketName=p["bucket"], indexName=name)["index"]
        got = {k: idx.get(k) for k in want}
        if got != want:
            raise PlanMismatch(f"index {name} has {got}, plan needs {want}; delete and re-create it")
        out["indexes"].append({"indexName": name, **got, "tags": _ensure_tags(c, idx["indexArn"], p["tags"])})
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--create", action="store_true", help="create/verify the bucket and indexes (AWS)")
    ap.add_argument("--profile", default="heisenberg")
    ap.add_argument("--region", default="us-east-1")
    args = ap.parse_args(argv)
    p = plan()
    print(json.dumps(create(p, profile=args.profile, region=args.region) if args.create else p, indent=1))


if __name__ == "__main__":
    main()
