"""Contract tests: DynamoStore against the deployed EzhuthuData table schema (infra/lib/data-stack.ts).

The fake reads the key schema from the CDK source, so a change to the table (or to the store) that breaks the
other side fails here. It enforces what DynamoDB enforces: every item has the table's key attributes, get_item
names exactly the primary key, and a query on an index uses that index's partition key.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from boto3.dynamodb.conditions import ConditionBase

from ezhuthu.api.service import EzhuthuService
from ezhuthu.api.storage import DynamoStore, store_from_env

DATA_STACK = Path(__file__).resolve().parents[2] / "infra" / "lib" / "data-stack.ts"


def table_schema() -> dict:
    src = DATA_STACK.read_text()
    pk = re.search(r"partitionKey:\s*\{\s*name:\s*'(\w+)'", src).group(1)
    sk = re.search(r"\n\s*sortKey:\s*\{\s*name:\s*'(\w+)'", src).group(1)
    gsis = {m.group(1): (m.group(2), m.group(3)) for m in re.finditer(
        r"indexName:\s*'(\w+)',\s*partitionKey:\s*\{\s*name:\s*'(\w+)'[^}]*\},\s*sortKey:\s*\{\s*name:\s*'(\w+)'",
        src)}
    ttl = re.search(r"timeToLiveAttribute:\s*'(\w+)'", src).group(1)
    return {"pk": pk, "sk": sk, "gsis": gsis, "ttl": ttl}


def _eval(cond: ConditionBase, item: dict) -> bool:
    e = cond.get_expression()
    op, vals = e["operator"], e["values"]
    if op == "AND":
        return _eval(vals[0], item) and _eval(vals[1], item)
    name = vals[0].name
    if op == "attribute_exists":
        return name in item
    if op == "=":
        return item.get(name) == vals[1]
    if op == "begins_with":
        return str(item.get(name, "")).startswith(vals[1])
    raise AssertionError(f"fake does not support {op}")


class ConditionalCheckFailed(Exception):
    """What boto3 raises for a failed ConditionExpression (botocore ClientError with this error code)."""

    def __init__(self):
        super().__init__("ConditionalCheckFailedException")
        self.response = {"Error": {"Code": "ConditionalCheckFailedException"}}


class SchemaTable:
    """A DynamoDB table fake that enforces the deployed key schema; pages results 2 at a time."""

    def __init__(self):
        self.schema = table_schema()
        self.items: dict[tuple[str, str], dict] = {}
        self.calls: list[str] = []

    def _key(self, d: dict) -> tuple[str, str]:
        return d[self.schema["pk"]], d[self.schema["sk"]]

    def put_item(self, Item, ConditionExpression=None, **kw):
        assert self.schema["pk"] in Item and self.schema["sk"] in Item, "item misses the table's key attributes"
        for v in Item.values():
            assert not isinstance(v, float), "boto3 rejects float attributes (needs Decimal)"
        if ConditionExpression is not None and not _eval(ConditionExpression, self.items.get(self._key(Item), {})):
            raise ConditionalCheckFailed()
        self.calls.append("put")
        self.items[self._key(Item)] = dict(Item)

    def get_item(self, Key, ConsistentRead=False):
        assert set(Key) == {self.schema["pk"], self.schema["sk"]}, f"get_item key must be pk+sk, got {set(Key)}"
        it = self.items.get(self._key(Key))
        return {"Item": dict(it)} if it else {}

    def _page(self, rows, start):
        i = int(start or 0)
        out = {"Items": rows[i:i + 2]}
        if i + 2 < len(rows):
            out["LastEvaluatedKey"] = str(i + 2)
        return out

    def query(self, IndexName, KeyConditionExpression, ScanIndexForward=True, ExclusiveStartKey=None, **kw):
        assert IndexName in self.schema["gsis"], f"no index {IndexName} on the deployed table"
        ipk, isk = self.schema["gsis"][IndexName]
        e = KeyConditionExpression.get_expression()
        assert e["operator"] == "=" and e["values"][0].name == ipk, "query must use the index partition key"
        rows = sorted((i for i in self.items.values() if _eval(KeyConditionExpression, i) and isk in i),
                      key=lambda i: i[isk], reverse=not ScanIndexForward)
        self.calls.append(f"query:{e['values'][1]}")
        return self._page(rows, ExclusiveStartKey)

    def proxy_review(self, qid: str, status: str, reviewer: str, final_text: str | None = None) -> None:
        """What infra/lambda/proxy/queue.ts review() does: an in-place UpdateItem (SET status, gsi1pk, reviewed_*,
        final_text) conditional on status = pending. ``doc`` is not touched."""
        assert re.fullmatch(r"q-[0-9a-f-]{36}", qid), "the proxy 404s on ids not shaped q-<uuid>"
        it = self.items.get((f"QUEUE#{qid}", "ITEM"))
        if not it or it.get("status") != "pending":
            raise ConditionalCheckFailed()
        it.update({"status": status, "gsi1pk": f"STATUS#{status}", "reviewed_by": reviewer,
                   "reviewed_at": "2026-11-02T12:00:00.000Z"})
        if final_text is not None:
            it["final_text"] = final_text

    def scan(self, FilterExpression, ExclusiveStartKey=None, **kw):
        rows = [i for i in self.items.values() if _eval(FilterExpression, i)]
        self.calls.append("scan")
        return self._page(rows, ExclusiveStartKey)


def test_schema_parsed_from_cdk():
    s = table_schema()
    assert s == {"pk": "pk", "sk": "sk", "gsis": {"gsi1": ("gsi1pk", "gsi1sk")}, "ttl": "ttl"}


def test_session_round_trip_uses_pk_sk_and_ttl_and_never_touches_proxy_meta():
    t = SchemaTable()
    t.put_item(Item={"pk": "SESSION#s-1", "sk": "META", "created_at": "2026-11-02T00:00:00.000Z", "level": "L1",
                     "ttl": 1})
    s = DynamoStore(t, clock=lambda: 1000.0)
    s.put("session", "s-1", {"session_id": "s-1", "items": {"a": {"x": 0.5}}})
    assert t.items[("SESSION#s-1", "META")]["level"] == "L1"  # proxy row intact
    row = t.items[("SESSION#s-1", "STATE")]
    assert row["ttl"] == 1000 + 90 * 24 * 3600 and json.loads(row["doc"])["items"]["a"]["x"] == 0.5
    assert s.get("session", "s-1")["session_id"] == "s-1" and s.get("session", "nope") is None
    s.put("session", "s-2", {"session_id": "s-2"})
    s.put("session", "s-3", {"session_id": "s-3"})
    assert sorted(d["session_id"] for d in s.list("session")) == ["s-1", "s-2", "s-3"]  # paged scan


def test_queue_items_carry_gsi1_and_list_across_statuses_and_pages():
    t = SchemaTable()
    s = DynamoStore(t)
    for i in range(3):
        s.put("queue", f"c{i}", {"id": f"c{i}", "status": "pending", "created_at": 1_700_000_000 + i,
                                 "gap_ref": "t:0", "text": "x", "history": []})
    s.put("queue", "c9", {"id": "c9", "status": "edited", "created_at": 1_700_000_100, "text": "kōyil",
                          "history": []})
    row = t.items[("QUEUE#c0", "ITEM")]
    assert row["gsi1pk"] == "STATUS#pending" and row["gsi1sk"].endswith("Z") and row["status"] == "pending"
    assert t.items[("QUEUE#c9", "ITEM")]["gsi1pk"] == "STATUS#edited"
    assert t.items[("QUEUE#c9", "ITEM")]["final_text"] == "kōyil"
    ids = [d["id"] for d in s.list("queue")]
    assert ids[:3] == ["c0", "c1", "c2"] and "c9" in ids
    # a status change moves the item to the other gsi1 partition
    d = s.get("queue", "c1")
    d["status"] = "approved"
    s.put("queue", "c1", d)
    assert t.items[("QUEUE#c1", "ITEM")]["gsi1pk"] == "STATUS#approved"


def test_proxy_written_queue_item_is_readable_and_reviewable():
    """An item exactly as infra/lambda/proxy/queue.ts addCorrection writes it (no ``doc``)."""
    t = SchemaTable()
    t.put_item(Item={"pk": "QUEUE#q-1", "sk": "ITEM", "gsi1pk": "STATUS#pending",
                     "gsi1sk": "2026-11-02T10:00:00.000Z", "id": "q-1", "gap_ref": {"trace_id": "t", "gap_index": 0},
                     "corrected_text": "kōyil", "user": "anon (unverified)", "status": "pending",
                     "created_at": "2026-11-02T10:00:00.000Z"})
    svc = EzhuthuService(store=DynamoStore(t), llm=None, decider=None, model_factory=None, admin_token=None,
                         open_review=True, clock=lambda: 1_800_000_000.0)
    svc.add_correction("trace:1", corrected_text="nāṭu")
    q = svc.queue()
    assert q["pending"] == 2 and q["items"][0]["id"] == "q-1"  # mixed ISO / epoch created_at sort
    done = svc.review("q-1", "edit", "kōyil", "rev")
    assert done["status"] == "edited" and done["history"][0]["previous_status"] == "pending"
    assert t.items[("QUEUE#q-1", "ITEM")]["gsi1pk"] == "STATUS#edited"


def test_store_from_env_reads_table_name(monkeypatch):
    import boto3

    seen = {}

    class Res:
        def Table(self, name):
            seen["name"] = name
            return SchemaTable()

    monkeypatch.setattr(boto3, "resource", lambda *a, **k: Res())
    monkeypatch.setenv("EZHUTHU_STORE", "dynamodb")
    monkeypatch.setenv("EZHUTHU_TABLE", "EzhuthuData-AppTable")
    assert isinstance(store_from_env(), DynamoStore) and seen["name"] == "EzhuthuData-AppTable"
    monkeypatch.delenv("EZHUTHU_TABLE")
    with pytest.raises(ValueError, match="EZHUTHU_TABLE"):
        store_from_env()


# ---------------------------------------------------------------- QA on PR #25: both directions --------------
def _svc(table: SchemaTable) -> EzhuthuService:
    return EzhuthuService(store=DynamoStore(table), llm=None, decider=None, model_factory=None, admin_token=None,
                          open_review=True, clock=lambda: 1_800_000_000.0)


def test_python_queue_ids_have_the_proxy_shape():
    t = SchemaTable()
    c = _svc(t).add_correction("trace:1", corrected_text="nāṭu")
    assert re.fullmatch(r"q-[0-9a-f-]{36}", c["id"])  # infra/lambda/proxy/queue.ts review() id check
    t.proxy_review(c["id"], "approved", "rev", final_text="nāṭu")  # the proxy can review it


def test_proxy_review_of_a_python_item_reads_as_reviewed():
    t = SchemaTable()
    svc = _svc(t)
    c = svc.add_correction("trace:1", corrected_text="nāṭu")
    t.proxy_review(c["id"], "edited", "rev", final_text="nāṭṭu")
    d = DynamoStore(t).get("queue", c["id"])
    assert d["status"] == "edited" and d["final_text"] == "nāṭṭu" and d["text"] == "nāṭṭu"
    assert d["reviewed_by"] == "rev"
    q = svc.queue()
    assert q["pending"] == 0 and q["items"][0]["status"] == "edited"
    from ezhuthu.api.service import Conflict

    with pytest.raises(Conflict):  # the proxy already reviewed it
        svc.review(c["id"], "approve", reviewer="rev2")


def test_python_review_is_conditional_and_approve_sets_final_text():
    from ezhuthu.api.service import Conflict

    t = SchemaTable()
    svc = _svc(t)
    c = svc.add_correction("trace:1", accepted_candidate="kōyil")
    done = svc.review(c["id"], "approve", reviewer="rev")
    row = t.items[(f"QUEUE#{c['id']}", "ITEM")]
    assert done["status"] == "approved" and row["final_text"] == "kōyil" and row["status"] == "approved"
    assert row["reviewed_by"] == "rev" and row["gsi1pk"] == "STATUS#approved"
    with pytest.raises(Conflict):
        svc.review(c["id"], "reject", reviewer="rev2")
    assert t.items[(f"QUEUE#{c['id']}", "ITEM")]["status"] == "approved"

    # a reviewer that read the item while it was pending loses the race at the conditional write
    c2 = svc.add_correction("trace:2", corrected_text="nāṭu")
    stale = DynamoStore(t).get("queue", c2["id"])
    t.proxy_review(c2["id"], "rejected", "other")
    stale["status"] = "approved"
    assert DynamoStore(t).put_if_status("queue", c2["id"], stale, "pending") is False
    assert t.items[(f"QUEUE#{c2['id']}", "ITEM")]["status"] == "rejected"


@pytest.mark.parametrize("kind", ["memory", "sqlite"])
def test_local_stores_review_once(kind, tmp_path):
    from ezhuthu.api.service import Conflict
    from ezhuthu.api.storage import MemoryStore, SQLiteStore

    store = MemoryStore() if kind == "memory" else SQLiteStore(str(tmp_path / "s.db"))
    svc = EzhuthuService(store=store, llm=None, decider=None, model_factory=None, admin_token=None,
                         open_review=True, clock=lambda: 1_800_000_000.0)
    c = svc.add_correction("trace:1", corrected_text="nāṭu")
    assert svc.review(c["id"], "edit", "nāṭṭu", "rev")["final_text"] == "nāṭṭu"
    with pytest.raises(Conflict):
        svc.review(c["id"], "approve")
    assert store.put_if_status("queue", "missing", {}, "pending") is False


def test_reread_tokens_are_one_time_conditional_writes_with_ttl():
    from ezhuthu.agent.reader import RereadTokens

    table = SchemaTable()
    store = DynamoStore(table, clock=lambda: 1_000_000)
    tokens = RereadTokens(store, ttl_s=900, clock=lambda: 1_000_000.0)
    tok = tokens.issue("sha-of-photo")
    item = table.items[(f"READTOKEN#{tok}", "TOKEN")]
    assert item["status"] == "issued" and item["ttl"] == 1_000_000 + 24 * 3600
    assert not tokens.consume(tok, "another-photo")
    assert tokens.consume(tok, "sha-of-photo")
    assert table.items[(f"READTOKEN#{tok}", "TOKEN")]["status"] == "used"
    assert not tokens.consume(tok, "sha-of-photo")
