"""Persistence: LangGraph checkpointer + ticket registry + usage counters.

* `DATABASE_URL` set   -> Postgres (Neon etc.). The escalation queue survives restarts/cold starts,
                          and daily usage caps can't be reset by Render sleeping and waking.
* `DATABASE_URL` unset -> in-memory (dev and tests only; everything is lost on restart).
"""

from __future__ import annotations

import logging
import threading
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from langgraph.checkpoint.memory import MemorySaver

log = logging.getLogger("uvicorn.error")


def today() -> str:
    return datetime.now(UTC).date().isoformat()


class Store(Protocol):
    def setup(self) -> None: ...
    def add_ticket(self, ticket_id: str, status: str) -> None: ...
    def set_status(self, ticket_id: str, status: str) -> None: ...
    def ticket_ids(self, status: str) -> list[str]: ...
    def ping(self) -> bool: ...
    def hit(self, key: str, limit: int) -> bool:
        """Count one use of `key` today. Returns False once the daily `limit` is exceeded."""


class MemoryStore:
    def __init__(self) -> None:
        self._tickets: dict[str, str] = {}
        self._usage: dict[tuple[str, str], int] = defaultdict(int)
        self._lock = threading.Lock()

    def setup(self) -> None:
        pass

    def ping(self) -> bool:
        return True

    def add_ticket(self, ticket_id: str, status: str) -> None:
        with self._lock:
            self._tickets[ticket_id] = status

    def set_status(self, ticket_id: str, status: str) -> None:
        with self._lock:
            self._tickets[ticket_id] = status

    def ticket_ids(self, status: str) -> list[str]:
        with self._lock:
            return [t for t, s in self._tickets.items() if s == status]

    def hit(self, key: str, limit: int) -> bool:
        with self._lock:
            self._usage[(today(), key)] += 1
            return self._usage[(today(), key)] <= limit


class PostgresStore:
    """Expects a psycopg ConnectionPool opened with autocommit=True and row_factory=dict_row."""

    def __init__(self, pool) -> None:
        self.pool = pool

    def setup(self) -> None:
        with self.pool.connection() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS tickets (
                    ticket_id  TEXT PRIMARY KEY,
                    status     TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )"""
            )
            conn.execute("CREATE INDEX IF NOT EXISTS tickets_status_idx ON tickets (status)")
            conn.execute(
                """CREATE TABLE IF NOT EXISTS usage (
                    day   DATE NOT NULL,
                    key   TEXT NOT NULL,
                    count INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (day, key)
                )"""
            )
            conn.execute("DELETE FROM usage WHERE day < CURRENT_DATE - 7")

    def ping(self) -> bool:
        with self.pool.connection() as conn:
            return conn.execute("SELECT 1 AS ok").fetchone()["ok"] == 1

    def add_ticket(self, ticket_id: str, status: str) -> None:
        with self.pool.connection() as conn:
            conn.execute(
                """INSERT INTO tickets (ticket_id, status) VALUES (%s, %s)
                   ON CONFLICT (ticket_id)
                   DO UPDATE SET status = EXCLUDED.status, updated_at = now()""",
                (ticket_id, status),
            )

    def set_status(self, ticket_id: str, status: str) -> None:
        with self.pool.connection() as conn:
            conn.execute(
                "UPDATE tickets SET status = %s, updated_at = now() WHERE ticket_id = %s",
                (status, ticket_id),
            )

    def ticket_ids(self, status: str) -> list[str]:
        with self.pool.connection() as conn:
            rows = conn.execute(
                "SELECT ticket_id FROM tickets WHERE status = %s ORDER BY created_at", (status,)
            ).fetchall()
        return [r["ticket_id"] for r in rows]

    def hit(self, key: str, limit: int) -> bool:
        with self.pool.connection() as conn:
            row = conn.execute(
                """INSERT INTO usage (day, key, count) VALUES (CURRENT_DATE, %s, 1)
                   ON CONFLICT (day, key) DO UPDATE SET count = usage.count + 1
                   RETURNING count""",
                (key,),
            ).fetchone()
        return row["count"] <= limit


def describe_url(url: str) -> str:
    """Non-secret summary of a connection URL, for diagnosing bad env values."""
    from urllib.parse import urlparse

    try:
        u = urlparse(url)
        pw = u.password or ""
        brackets = "<" in url or ">" in url
        quotes = any(c in url for c in "\"'")
        spaces = any(c.isspace() for c in url)
        return (
            f"scheme={u.scheme!r} user={u.username!r} host={u.hostname!r} db={u.path!r} "
            f"query={u.query!r} password_len={len(pw)} password_starts={pw[:4]!r} "
            f"has_angle_brackets={brackets} has_quotes={quotes} has_spaces={spaces} "
            f"total_len={len(url)}"
        )
    except Exception as exc:  # noqa: BLE001
        return f"unparseable ({type(exc).__name__}), total_len={len(url)}"


def make_persistence(database_url: str | None) -> tuple[object, Store, Callable[[], None]]:
    """Returns (checkpointer, store, close)."""
    if not database_url:
        return MemorySaver(), MemoryStore(), lambda: None

    from langgraph.checkpoint.postgres import PostgresSaver
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool

    pool = ConnectionPool(
        conninfo=database_url,
        min_size=1,
        max_size=5,
        # Neon scales to zero and drops idle connections; validate before use and recycle often.
        check=ConnectionPool.check_connection,
        max_idle=240,
        max_lifetime=1800,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
        open=True,
    )
    try:
        pool.wait(timeout=30)
    except Exception:
        log.error("Database connection failed. Received: %s", describe_url(database_url))
        raise
    checkpointer = PostgresSaver(pool)
    checkpointer.setup()
    store = PostgresStore(pool)
    store.setup()
    return checkpointer, store, pool.close
