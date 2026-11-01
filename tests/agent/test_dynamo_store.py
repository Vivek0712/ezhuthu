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
    if op == "=":
        return item.get(name) == vals[1]
    if op == "begins_with":
        return str(item.get(name, "")).startswith(vals[1])
    raise AssertionError(f"fake does not support {op}")


class SchemaTable:
    """A DynamoDB table fake that enforces the deployed key schema; pages results 2 at a time."""

    def __init__(self):
        self.schema = table_schema()
        self.items: dict[tuple[str, str], dict] = {}
        self.calls: list[str] = []

    def _key(self, d: dict) -> tuple[str, str]:
        return d[self.schema["pk"]], d[self.schema["sk"]]

    def put_item(self, Item, **kw):
        assert self.schema["pk"] in Item and self.schema["sk"] in Item, "item misses the table's key attributes"
        for v in Item.values():
            assert not isinstance(v, float), "boto3 rejects float attributes (needs Decimal)"
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
