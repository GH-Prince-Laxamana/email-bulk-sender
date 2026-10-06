from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


def connect(path: str | Path) -> sqlite3.Connection:
    """Open a connection compatible with FastAPI's sync dependency cleanup.

    FastAPI may execute a synchronous dependency's cleanup in a different
    worker thread than the one that created the connection. The connection is
    still request-scoped and is not shared between concurrent requests.
    """
    conn = sqlite3.connect(
        str(path),
        timeout=5,
        isolation_level=None,
        check_same_thread=False,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = FULL")
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
