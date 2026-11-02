"""Storage for sessions, corrections and the expert review queue.

``EZHUTHU_STORE``: ``memory`` (default), ``sqlite:<path>``, ``dynamodb:<table>``, or ``dynamodb`` (table name from
``EZHUTHU_TABLE``, which the AgentCore stack sets). The DynamoDB layout is the deployed ``EzhuthuData`` table
(``infra/lib/data-stack.ts``): partition key ``pk``, sort key ``sk``, GSI ``gsi1`` (``gsi1pk``/``gsi1sk``),
TTL attribute ``ttl``:

    SESSION#<id>    / STATE   tutor session doc (the proxy owns SESSION#<id> / META; never overwritten here)
    CORRECTION#<id> / ITEM    correction record
    QUEUE#<id>      / ITEM    review-queue item; gsi1pk = STATUS#<status>, gsi1sk = created_at (ISO-8601 UTC),
                              the same keys and top-level fields the proxy's QueueStore writes and lists

Each item keeps the full document as JSON in ``doc``; queue items also carry the proxy's top-level fields, and
items the proxy wrote (no ``doc``) are read from those fields. The two writers interoperate both ways:

* queue ids are ``q-<uuid4>`` on both sides (the proxy's ``review`` only accepts that shape);
* on read, the review fields the proxy updates in place (``status``, ``reviewed_by``, ``reviewed_at``,
  ``final_text``) override the copy inside ``doc``, so an item the proxy reviewed reads as reviewed here;
* a review is a conditional write (``status = pending``), as in the proxy, so an item is reviewed once.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sqlite3
import threading
import time
from typing import Any, Protocol

KINDS = ("session", "correction", "queue")


class Store(Protocol):
    def put(self, kind: str, id: str, doc: dict[str, Any]) -> None: ...

    def put_if_status(self, kind: str, id: str, doc: dict[str, Any], expected: str) -> bool:
        """Write ``doc`` only if the stored item exists and its ``status`` is ``expected``; False otherwise."""
        ...

    def get(self, kind: str, id: str) -> dict[str, Any] | None: ...

    def list(self, kind: str) -> list[dict[str, Any]]: ...


def _check(kind: str) -> None:
    if kind not in KINDS:
        raise ValueError(f"unknown kind {kind!r}")


class MemoryStore:
    def __init__(self) -> None:
        self._d: dict[tuple[str, str], str] = {}
        self._lock = threading.Lock()

    def put(self, kind: str, id: str, doc: dict[str, Any]) -> None:
        _check(kind)
        with self._lock:
            self._d[(kind, id)] = json.dumps(doc, ensure_ascii=False)

    def put_if_status(self, kind: str, id: str, doc: dict[str, Any], expected: str) -> bool:
        _check(kind)
        with self._lock:
            cur = self._d.get((kind, id))
            if cur is None or json.loads(cur).get("status") != expected:
                return False
            self._d[(kind, id)] = json.dumps(doc, ensure_ascii=False)
            return True

    def get(self, kind: str, id: str) -> dict[str, Any] | None:
        _check(kind)
        v = self._d.get((kind, id))
        return json.loads(v) if v is not None else None

    def list(self, kind: str) -> list[dict[str, Any]]:
        _check(kind)
        return [json.loads(v) for (k, _), v in list(self._d.items()) if k == kind]


class SQLiteStore:
    def __init__(self, path: str):
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._conn.execute("CREATE TABLE IF NOT EXISTS docs (kind TEXT, id TEXT, doc TEXT, "
                               "seq INTEGER PRIMARY KEY AUTOINCREMENT, UNIQUE(kind, id))")
            self._conn.commit()

    def put(self, kind: str, id: str, doc: dict[str, Any]) -> None:
        _check(kind)
        with self._lock:
            self._conn.execute("INSERT INTO docs(kind, id, doc) VALUES (?, ?, ?) "
                               "ON CONFLICT(kind, id) DO UPDATE SET doc = excluded.doc",
                               (kind, id, json.dumps(doc, ensure_ascii=False)))
            self._conn.commit()

    def put_if_status(self, kind: str, id: str, doc: dict[str, Any], expected: str) -> bool:
        _check(kind)
        with self._lock:  # one connection behind a lock: read-compare-write is atomic for this process
            row = self._conn.execute("SELECT doc FROM docs WHERE kind = ? AND id = ?", (kind, id)).fetchone()
            if row is None or json.loads(row[0]).get("status") != expected:
                return False
            self._conn.execute("UPDATE docs SET doc = ? WHERE kind = ? AND id = ?",
                               (json.dumps(doc, ensure_ascii=False), kind, id))
            self._conn.commit()
            return True

    def get(self, kind: str, id: str) -> dict[str, Any] | None:
        _check(kind)
        with self._lock:
            row = self._conn.execute("SELECT doc FROM docs WHERE kind = ? AND id = ?", (kind, id)).fetchone()
        return json.loads(row[0]) if row else None

    def list(self, kind: str) -> list[dict[str, Any]]:
        _check(kind)
        with self._lock:
            rows = self._conn.execute("SELECT doc FROM docs WHERE kind = ? ORDER BY seq", (kind,)).fetchall()
        return [json.loads(r[0]) for r in rows]


SESSION_TTL_SECONDS = 90 * 24 * 3600  # same as the proxy's SESSION#<id>/META
_PREFIX = {"session": "SESSION", "correction": "CORRECTION", "queue": "QUEUE"}
_SK = {"session": "STATE", "correction": "ITEM", "queue": "ITEM"}
QUEUE_STATUSES = ("pending", "approved", "edited", "rejected")
_KEY_ATTRS = ("pk", "sk", "gsi1pk", "gsi1sk", "ttl", "doc", "kind")
# Queue fields the proxy's review() SETs in place; on read they win over the copy inside ``doc``.
_REVIEW_ATTRS = ("status", "reviewed_by", "reviewed_at", "final_text")


def _iso(ts: Any) -> str:
    """``created_at`` as the proxy writes it (ISO-8601 UTC, ms); epoch seconds from the Python service convert."""
    if isinstance(ts, (int, float)):
        return dt.datetime.fromtimestamp(float(ts), dt.UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    return str(ts) if ts else dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


class DynamoStore:
    """``table`` is a boto3 DynamoDB Table resource (or anything with put_item/get_item/query/scan)."""

    def __init__(self, table: Any, *, index: str = "gsi1", clock=time.time):
        self.table = table
        self.index = index
        self.clock = clock

    @classmethod
    def from_name(cls, name: str, region: str | None = None) -> DynamoStore:
        import boto3

        return cls(boto3.resource("dynamodb", region_name=region or os.environ.get("AWS_REGION", "us-east-1"))
                   .Table(name))

    @staticmethod
    def key(kind: str, id: str) -> dict[str, str]:
        _check(kind)
        return {"pk": f"{_PREFIX[kind]}#{id}", "sk": _SK[kind]}

    def _item(self, kind: str, id: str, doc: dict[str, Any]) -> dict[str, Any]:
        item: dict[str, Any] = {**self.key(kind, id), "kind": kind, "doc": json.dumps(doc, ensure_ascii=False)}
        if kind == "session":
            item["ttl"] = int(self.clock()) + SESSION_TTL_SECONDS
        elif kind == "queue":
            status = str(doc.get("status") or "pending")
            created = _iso(doc.get("created_at"))
            item.update({"gsi1pk": f"STATUS#{status}", "gsi1sk": created, "id": str(doc.get("id", id)),
                         "status": status, "created_at": created})
            for f in ("gap_ref", "accepted_candidate", "corrected_text", "user", "final_text", "reviewed_by",
                      "reviewed_at"):
                if isinstance(doc.get(f), str) and doc[f]:
                    item[f] = doc[f]
            if doc.get("status") in ("edited", "approved") and isinstance(doc.get("text"), str) and doc["text"]:
                item["final_text"] = doc["text"]
        return item

    def put(self, kind: str, id: str, doc: dict[str, Any]) -> None:
        self.table.put_item(Item=self._item(kind, id, doc))

    def put_if_status(self, kind: str, id: str, doc: dict[str, Any], expected: str) -> bool:
        """Conditional put (``attribute_exists(pk) AND status = expected``), the proxy's review condition."""
        from boto3.dynamodb.conditions import Attr

        try:
            self.table.put_item(Item=self._item(kind, id, doc),
                                ConditionExpression=Attr("pk").exists() & Attr("status").eq(expected))
        except Exception as exc:  # botocore ClientError: the failed condition is only visible in its error code
            if (getattr(exc, "response", None) or {}).get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                return False
            raise
        return True

    @staticmethod
    def _doc(item: dict[str, Any]) -> dict[str, Any]:
        if "doc" in item:
            d = json.loads(item["doc"])
            if str(item.get("pk", "")).startswith("QUEUE#"):
                # The proxy reviews in place (SET status, gsi1pk, reviewed_*, final_text) and leaves ``doc``
                # stale: the top-level review fields are the truth.
                for f in _REVIEW_ATTRS:
                    if f in item:
                        d[f] = item[f]
                if isinstance(item.get("final_text"), str) and item["final_text"]:
                    d["text"] = item["final_text"]
            return d
        # Written by the proxy (infra/lambda/proxy/queue.ts): the record is the top-level attributes.
        return {k: v for k, v in item.items() if k not in _KEY_ATTRS}

    def get(self, kind: str, id: str) -> dict[str, Any] | None:
        item = self.table.get_item(Key=self.key(kind, id), ConsistentRead=True).get("Item")
        return self._doc(item) if item else None

    def _paged(self, op, **kwargs: Any) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        while True:
            resp = op(**kwargs)
            out.extend(resp.get("Items", []))
            if "LastEvaluatedKey" not in resp:
                return out
            kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]

    def list(self, kind: str) -> list[dict[str, Any]]:
        """Queue: one ``gsi1`` query per status, oldest first. Sessions/corrections have no index in the deployed
        table, so they are a filtered scan (admin/debug use only; the API never lists them)."""
        _check(kind)
        from boto3.dynamodb.conditions import Attr, Key

        if kind == "queue":
            items: list[dict[str, Any]] = []
            for st in QUEUE_STATUSES:
                items += self._paged(self.table.query, IndexName=self.index,
                                     KeyConditionExpression=Key("gsi1pk").eq(f"STATUS#{st}"), ScanIndexForward=True)
            return [self._doc(i) for i in items if str(i.get("pk", "")).startswith("QUEUE#")]
        items = self._paged(self.table.scan, FilterExpression=Attr("pk").begins_with(f"{_PREFIX[kind]}#")
                            & Attr("sk").eq(_SK[kind]))
        return [self._doc(i) for i in items]


def store_from_env() -> Store:
    spec = os.environ.get("EZHUTHU_STORE", "memory")
    if spec == "memory":
        return MemoryStore()
    if spec.startswith("sqlite:"):
        return SQLiteStore(spec.split(":", 1)[1])
    if spec == "dynamodb" or spec.startswith("dynamodb:"):
        name = spec.split(":", 1)[1] if ":" in spec else os.environ.get("EZHUTHU_TABLE", "")
        if not name:
            raise ValueError("EZHUTHU_STORE=dynamodb needs a table: dynamodb:<table> or EZHUTHU_TABLE")
        return DynamoStore.from_name(name)
    raise ValueError(f"unknown EZHUTHU_STORE {spec!r}")
