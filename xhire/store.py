"""SQLite storage for fetched posts and for the local spend ledger."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    id            TEXT PRIMARY KEY,
    author_id     TEXT,
    author_handle TEXT,
    author_name   TEXT,
    followers     INTEGER,
    text          TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    url           TEXT NOT NULL,
    query_name    TEXT NOT NULL,
    score         INTEGER NOT NULL DEFAULT 0,
    verdict       TEXT NOT NULL DEFAULT 'unknown',
    reasons       TEXT NOT NULL DEFAULT '',
    fetched_at    TEXT NOT NULL,
    reviewed      INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_posts_score ON posts(score DESC);
CREATE INDEX IF NOT EXISTS idx_posts_created ON posts(created_at DESC);

-- One row per billed request, so `status` can reconstruct spend without
-- trusting a running total that a crashed run might have left half-written.
CREATE TABLE IF NOT EXISTS usage (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,
    month       TEXT NOT NULL,
    query_name  TEXT NOT NULL,
    posts_read  INTEGER NOT NULL,
    cost_usd    REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_usage_month ON usage(month);

-- Highest post id seen per query, so the next poll uses since_id and never
-- re-fetches (and never re-pays for) a post it already has.
CREATE TABLE IF NOT EXISTS cursors (
    query_name TEXT PRIMARY KEY,
    since_id   TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def current_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


@contextmanager
def connect(db_path: Path) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def save_posts(conn: sqlite3.Connection, posts: list[dict]) -> int:
    """Insert posts, ignoring ones already stored. Returns the number added."""
    before = conn.total_changes
    conn.executemany(
        """
        INSERT OR IGNORE INTO posts
            (id, author_id, author_handle, author_name, followers, text,
             created_at, url, query_name, score, verdict, reasons, fetched_at)
        VALUES
            (:id, :author_id, :author_handle, :author_name, :followers, :text,
             :created_at, :url, :query_name, :score, :verdict, :reasons, :fetched_at)
        """,
        posts,
    )
    return conn.total_changes - before


def record_usage(
    conn: sqlite3.Connection, query_name: str, posts_read: int, cost_usd: float
) -> None:
    conn.execute(
        "INSERT INTO usage (ts, month, query_name, posts_read, cost_usd)"
        " VALUES (?, ?, ?, ?, ?)",
        (utcnow(), current_month(), query_name, posts_read, cost_usd),
    )
    conn.commit()


def month_spend(conn: sqlite3.Connection, month: str | None = None) -> float:
    row = conn.execute(
        "SELECT COALESCE(SUM(cost_usd), 0.0) AS total FROM usage WHERE month = ?",
        (month or current_month(),),
    ).fetchone()
    return float(row["total"])


def month_reads(conn: sqlite3.Connection, month: str | None = None) -> int:
    row = conn.execute(
        "SELECT COALESCE(SUM(posts_read), 0) AS total FROM usage WHERE month = ?",
        (month or current_month(),),
    ).fetchone()
    return int(row["total"])


def get_cursor(conn: sqlite3.Connection, query_name: str) -> str | None:
    row = conn.execute(
        "SELECT since_id FROM cursors WHERE query_name = ?", (query_name,)
    ).fetchone()
    return row["since_id"] if row else None


def set_cursor(conn: sqlite3.Connection, query_name: str, since_id: str) -> None:
    conn.execute(
        """
        INSERT INTO cursors (query_name, since_id, updated_at) VALUES (?, ?, ?)
        ON CONFLICT(query_name) DO UPDATE SET since_id = excluded.since_id,
                                              updated_at = excluded.updated_at
        """,
        (query_name, since_id, utcnow()),
    )


def top_posts(conn: sqlite3.Connection, limit: int = 100, min_score: int = 1) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT * FROM posts
        WHERE score >= ?
        ORDER BY score DESC, created_at DESC
        LIMIT ?
        """,
        (min_score, limit),
    ).fetchall()
