"""Append-only decision ledger. Each record carries the hash of the one before it, so edits are detectable."""
import hashlib
import json
import time
import uuid

from .config import LEDGER


def _hash(prev: str, body: dict) -> str:
    return hashlib.sha256((prev + json.dumps(body, sort_keys=True, default=str)).encode()).hexdigest()


def read(kind: str | None = None, **where) -> list:
    if not LEDGER.exists():
        return []
    out = [json.loads(l) for l in LEDGER.read_text().splitlines() if l.strip()]
    if kind:
        out = [r for r in out if r["kind"] == kind]
    for k, v in where.items():
        out = [r for r in out if r["payload"].get(k) == v]
    return out


def append(kind: str, payload: dict, author: str = "system") -> dict:
    """kind: decision | score | recalibration | review"""
    rows = read()
    prev = rows[-1]["hash"] if rows else "genesis"
    body = {"id": uuid.uuid4().hex[:12], "ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "kind": kind, "author": author, "payload": payload}
    rec = {**body, "prev": prev, "hash": _hash(prev, body)}
    with LEDGER.open("a") as f:
        f.write(json.dumps(rec, default=str) + "\n")
    return rec


def verify() -> dict:
    prev = "genesis"
    for i, r in enumerate(read()):
        body = {k: r[k] for k in ("id", "ts", "kind", "author", "payload")}
        if r["prev"] != prev or r["hash"] != _hash(prev, body):
            return {"ok": False, "broken_at": i, "id": r["id"]}
        prev = r["hash"]
    return {"ok": True, "records": len(read())}


def reset():
    if LEDGER.exists():
        LEDGER.unlink()
