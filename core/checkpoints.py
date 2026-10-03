"""
core/checkpoints.py — SQLite Per-Article Checkpointing & Idempotency
======================================================================
Provides persistent caching and resume capabilities across all pipeline phases.
Ensures that crashes, network interruptions, or quota cooldowns resume exactly
where they left off without repeating expensive scraping, AI transforms, or image calls.
"""

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


def init_db(db_path: Union[str, Path]) -> sqlite3.Connection:
    """Initializes the SQLite database with all required checkpoint tables."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(path), timeout=30.0, check_same_thread=False)
    db.row_factory = sqlite3.Row
    
    with db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS checkpoints (
                key TEXT PRIMARY KEY,
                val TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS batches (
                batch_num INTEGER PRIMARY KEY,
                data TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS images (
                key TEXT PRIMARY KEY,
                path TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS renders (
                key TEXT PRIMARY KEY,
                path TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS quota_cooldown (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                end_time REAL
            )
        """)
    return db


def get_checkpoint(db: sqlite3.Connection, key: str) -> Optional[str]:
    """Retrieves a string checkpoint value by key."""
    cur = db.execute("SELECT val FROM checkpoints WHERE key = ?", (key,))
    row = cur.fetchone()
    return row["val"] if row else None


def save_checkpoint(db: sqlite3.Connection, key: str, val: str) -> None:
    """Upserts a checkpoint key-value pair."""
    with db:
        db.execute(
            "INSERT OR REPLACE INTO checkpoints (key, val, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
            (key, val)
        )


def get_batch(db: sqlite3.Connection, batch_num: int) -> Optional[Union[Dict, List]]:
    """Loads a JSON-encoded transform batch by index (-1: meta, 0..N: sections, -2: conclusion)."""
    cur = db.execute("SELECT data FROM batches WHERE batch_num = ?", (batch_num,))
    row = cur.fetchone()
    if row and row["data"]:
        try:
            return json.loads(row["data"])
        except Exception:
            return None
    return None


def save_batch(db: sqlite3.Connection, batch_num: int, data: Any) -> None:
    """Saves a transform batch as JSON."""
    with db:
        db.execute(
            "INSERT OR REPLACE INTO batches (batch_num, data, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
            (batch_num, json.dumps(data, ensure_ascii=False))
        )


def is_image_done(db: sqlite3.Connection, img_key: str) -> Optional[str]:
    """Checks if an image key has been generated and saved."""
    cur = db.execute("SELECT path FROM images WHERE key = ?", (img_key,))
    row = cur.fetchone()
    return row["path"] if row else None


def save_image_done(db: sqlite3.Connection, img_key: str, dest_path: Union[str, Path]) -> None:
    """Records a generated image path in the database."""
    with db:
        db.execute(
            "INSERT OR REPLACE INTO images (key, path, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
            (img_key, str(dest_path))
        )


def is_render_done(db: sqlite3.Connection, render_key: str) -> Optional[str]:
    """Checks if an image compositing/render key has been completed."""
    cur = db.execute("SELECT path FROM renders WHERE key = ?", (render_key,))
    row = cur.fetchone()
    return row["path"] if row else None


def save_render_done(db: sqlite3.Connection, render_key: str, dest_path: Union[str, Path]) -> None:
    """Records a composited render output path."""
    with db:
        db.execute(
            "INSERT OR REPLACE INTO renders (key, path, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
            (render_key, str(dest_path))
        )


def get_quota_end_time(db: sqlite3.Connection) -> Optional[float]:
    """Returns the Unix timestamp when quota cooldown expires, if active."""
    cur = db.execute("SELECT end_time FROM quota_cooldown WHERE id = 1")
    row = cur.fetchone()
    return float(row["end_time"]) if row and row["end_time"] else None


def set_quota_end_time(db: sqlite3.Connection, end_time: float) -> None:
    """Stores the active quota cooldown expiry timestamp."""
    with db:
        db.execute(
            "INSERT OR REPLACE INTO quota_cooldown (id, end_time) VALUES (1, ?)",
            (end_time,)
        )


def clear_quota_end_time(db: sqlite3.Connection) -> None:
    """Clears the active quota cooldown timestamp."""
    with db:
        db.execute("DELETE FROM quota_cooldown WHERE id = 1")


class CheckpointManager:
    """
    Object-oriented wrapper around SQLite per-article checkpoint tables.
    Provides clean thread-safe interface for app startup and pipeline orchestration.
    """
    def __init__(self, db_path: Union[str, Path] = "checkpoints/pipeline.db"):
        self.db_path = Path(db_path)
        self.db: Optional[sqlite3.Connection] = None

    def init_db(self) -> sqlite3.Connection:
        """Initializes tables and returns the connection."""
        self.db = init_db(self.db_path)
        return self.db

    def get_connection(self) -> sqlite3.Connection:
        """Ensures an active database connection is ready."""
        if self.db is None:
            self.init_db()
        return self.db

    def save_checkpoint(
        self,
        url: str,
        status: str,
        phase: int = 0,
        data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Saves a high-level checkpoint with phase and metadata."""
        conn = self.get_connection()
        payload = json.dumps({
            "status": status,
            "phase": phase,
            "data": data or {}
        }, ensure_ascii=False)
        save_checkpoint(conn, url, payload)

    def get_checkpoint(self, url: str) -> Optional[Dict[str, Any]]:
        """Retrieves and parses a structured checkpoint."""
        conn = self.get_connection()
        raw = get_checkpoint(conn, url)
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return {"status": raw, "phase": 0, "data": {}}

