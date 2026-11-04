"""SQLite persistence: projects, event log and graph checkpoints."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Iterator
from contextlib import contextmanager

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    doc_type    TEXT NOT NULL,
    language    TEXT NOT NULL,
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  TEXT NOT NULL,
    ts          REAL NOT NULL,
    kind        TEXT NOT NULL,
    stage       TEXT,
    message     TEXT NOT NULL,
    data        TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_project ON events(project_id, id);
CREATE TABLE IF NOT EXISTS checkpoints (
    thread_id   TEXT NOT NULL,
    seq         INTEGER NOT NULL,
    created_at  REAL NOT NULL,
    node        TEXT,          -- node that produced this checkpoint
    next_node   TEXT,          -- node to run next (NULL = finished)
    pending     TEXT,          -- JSON interrupt payload when waiting for a human
    state       TEXT NOT NULL, -- JSON state
    PRIMARY KEY (thread_id, seq)
);
"""


class Database:
    def __init__(self, path: Path | str = DB_PATH):
        self.path = str(path)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            try:
                yield self._conn
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def query(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            return list(self._conn.execute(sql, params).fetchall())

    # ── projects ───────────────────────────────────────────────────────────
    def create_project(self, name: str, doc_type: str, language: str) -> str:
        pid = uuid.uuid4().hex[:12]
        now = time.time()
        with self.tx() as c:
            c.execute(
                "INSERT INTO projects(id,name,doc_type,language,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                (pid, name, doc_type, language, now, now),
            )
        return pid

    def get_project(self, pid: str) -> dict[str, Any] | None:
        rows = self.query("SELECT * FROM projects WHERE id=?", (pid,))
        return dict(rows[0]) if rows else None

    def list_projects(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self.query("SELECT * FROM projects ORDER BY updated_at DESC")]

    def update_project(self, pid: str, **fields: Any) -> None:
        allowed = {k: v for k, v in fields.items() if k in {"name", "doc_type", "language"}}
        allowed["updated_at"] = time.time()
        cols = ", ".join(f"{k}=?" for k in allowed)
        with self.tx() as c:
            c.execute(f"UPDATE projects SET {cols} WHERE id=?", (*allowed.values(), pid))

    def touch_project(self, pid: str) -> None:
        with self.tx() as c:
            c.execute("UPDATE projects SET updated_at=? WHERE id=?", (time.time(), pid))

    def delete_project(self, pid: str) -> None:
        with self.tx() as c:
            c.execute("DELETE FROM projects WHERE id=?", (pid,))
            c.execute("DELETE FROM events WHERE project_id=?", (pid,))
            c.execute("DELETE FROM checkpoints WHERE thread_id=?", (pid,))

    # ── events ─────────────────────────────────────────────────────────────
    def add_event(self, pid: str, kind: str, message: str, stage: str | None = None,
                  data: dict[str, Any] | None = None) -> int:
        with self.tx() as c:
            cur = c.execute(
                "INSERT INTO events(project_id,ts,kind,stage,message,data) VALUES(?,?,?,?,?,?)",
                (pid, time.time(), kind, stage, message, json.dumps(data or {}, ensure_ascii=False)),
            )
            return int(cur.lastrowid)

    def events(self, pid: str, since_id: int = 0, limit: int = 500,
               since_ts: float | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM events WHERE project_id=? AND id>?"
        params: list[Any] = [pid, since_id]
        if since_ts is not None:
            sql += " AND ts>=?"
            params.append(since_ts)
        sql += " ORDER BY id ASC LIMIT ?"
        params.append(limit)
        out = []
        for r in self.query(sql, tuple(params)):
            d = dict(r)
            d["data"] = json.loads(d["data"] or "{}")
            out.append(d)
        return out

    # ── checkpoints ────────────────────────────────────────────────────────
    def save_checkpoint(self, thread_id: str, node: str | None, next_node: str | None,
                        state: dict[str, Any], pending: Any = None) -> int:
        with self.tx() as c:
            row = c.execute("SELECT COALESCE(MAX(seq), -1) FROM checkpoints WHERE thread_id=?",
                            (thread_id,)).fetchone()
            seq = int(row[0]) + 1
            c.execute(
                "INSERT INTO checkpoints(thread_id,seq,created_at,node,next_node,pending,state) VALUES(?,?,?,?,?,?,?)",
                (thread_id, seq, time.time(), node, next_node,
                 json.dumps(pending, ensure_ascii=False) if pending is not None else None,
                 json.dumps(state, ensure_ascii=False)),
            )
            return seq

    def latest_checkpoint(self, thread_id: str) -> dict[str, Any] | None:
        rows = self.query("SELECT * FROM checkpoints WHERE thread_id=? ORDER BY seq DESC LIMIT 1", (thread_id,))
        return self._decode_cp(rows[0]) if rows else None

    def get_checkpoint(self, thread_id: str, seq: int) -> dict[str, Any] | None:
        rows = self.query("SELECT * FROM checkpoints WHERE thread_id=? AND seq=?", (thread_id, seq))
        return self._decode_cp(rows[0]) if rows else None

    def checkpoint_history(self, thread_id: str) -> list[dict[str, Any]]:
        rows = self.query(
            "SELECT thread_id, seq, created_at, node, next_node, pending IS NOT NULL AS waiting, "
            "json_extract(state, '$.stage') AS stage FROM checkpoints WHERE thread_id=? ORDER BY seq DESC",
            (thread_id,),
        )
        return [dict(r) for r in rows]

    @staticmethod
    def _decode_cp(row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        d["state"] = json.loads(d["state"])
        d["pending"] = json.loads(d["pending"]) if d["pending"] else None
        return d


_db: Database | None = None
_db_lock = threading.Lock()


def get_db() -> Database:
    global _db
    with _db_lock:
        if _db is None:
            _db = Database()
        return _db


def set_db(db: Database) -> None:
    """Used by tests to inject a temporary database."""
    global _db
    with _db_lock:
        _db = db
