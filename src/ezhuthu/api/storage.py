"""Storage for sessions, corrections and the expert review queue.

``EZHUTHU_STORE``: ``memory`` (default), ``sqlite:<path>``, or ``dynamodb:<table>`` (single-table design:
``pk`` = ``<kind>#<id>``, attribute ``doc`` = JSON, attribute ``kind`` for listing). The DynamoDB table is
created by the App team's infra (issue #4).
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from typing import Any, Protocol

KINDS = ("session", "correction", "queue")


class Store(Protocol):
    def put(self, kind: str, id: str, doc: dict[str, Any]) -> None: ...

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


class DynamoStore:
    """``table`` is a boto3 DynamoDB Table resource (or anything with put_item/get_item/query)."""

    def __init__(self, table: Any, *, kind_index: str = "kind-index"):
        self.table = table
        self.kind_index = kind_index

    @classmethod
    def from_name(cls, name: str, region: str | None = None) -> DynamoStore:
        import boto3

        return cls(boto3.resource("dynamodb", region_name=region or os.environ.get("AWS_REGION", "us-east-1"))
                   .Table(name))

    def put(self, kind: str, id: str, doc: dict[str, Any]) -> None:
        _check(kind)
        self.table.put_item(Item={"pk": f"{kind}#{id}", "kind": kind, "doc": json.dumps(doc, ensure_ascii=False)})

    def get(self, kind: str, id: str) -> dict[str, Any] | None:
        _check(kind)
        item = self.table.get_item(Key={"pk": f"{kind}#{id}"}).get("Item")
        return json.loads(item["doc"]) if item else None

    def list(self, kind: str) -> list[dict[str, Any]]:
        _check(kind)
        from boto3.dynamodb.conditions import Key

        out, kwargs = [], {"IndexName": self.kind_index, "KeyConditionExpression": Key("kind").eq(kind)}
        while True:
            resp = self.table.query(**kwargs)
            out.extend(json.loads(i["doc"]) for i in resp.get("Items", []))
            if "LastEvaluatedKey" not in resp:
                return out
            kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]


def store_from_env() -> Store:
    spec = os.environ.get("EZHUTHU_STORE", "memory")
    if spec == "memory":
        return MemoryStore()
    if spec.startswith("sqlite:"):
        return SQLiteStore(spec.split(":", 1)[1])
    if spec.startswith("dynamodb:"):
        return DynamoStore.from_name(spec.split(":", 1)[1])
    raise ValueError(f"unknown EZHUTHU_STORE {spec!r}")
