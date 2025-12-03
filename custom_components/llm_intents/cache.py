import hashlib
import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SQLiteCache:
    _instance = None
    DEFAULT_MAX_AGE = 7200  # 2 hour

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_db()
        return cls._instance

    def _init_db(self):
        base_dir = Path(__file__).resolve().parent  # this file's directory
        db_path = base_dir / "cache.db"
        base_dir.mkdir(parents=True, exist_ok=True)  # ensure folder exists

        if db_path.exists():
            # Recreate cache file when addon is initialised
            db_path.unlink()

        self._conn = sqlite3.connect(db_path)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL UNIQUE,
                created_at INTEGER NOT NULL,
                data TEXT NOT NULL
            )
        """)
        self._conn.commit()

    def _make_key(self, tool: str, params: dict | None) -> str:
        params_str = (
            ""
            if params is None
            else json.dumps(params, sort_keys=True, separators=(",", ":"))
        )
        combined = tool + params_str
        return hashlib.sha256(combined.encode()).hexdigest()

    def _cleanup(self):
        now = int(time.time())
        cutoff = now - self.DEFAULT_MAX_AGE
        deleted = self._conn.execute(
            "DELETE FROM cache WHERE created_at < ?", (cutoff,)
        ).rowcount
        self._conn.commit()
        if deleted:
            logger.debug(f"Cache cleanup ran, deleted {deleted} expired entries")

    def get(self, tool: str, params: dict | None) -> Any | None:
        self._cleanup()
        key = self._make_key(tool, params)
        cursor = self._conn.execute("SELECT data FROM cache WHERE key = ?", (key,))
        row = cursor.fetchone()
        if row:
            logger.debug(f"Cache hit for tool: {tool} Params: {params}")
            try:
                return json.loads(row[0])
            except json.JSONDecodeError:
                logger.debug(
                    f"Failed to decode cached data for tool: {tool} Params: {params}"
                )
                return None
        else:
            logger.debug(f"Cache miss for tool: {tool} Params: {params}")
            return None

    def set(self, tool: str, params: dict | None, data: dict):
        key = self._make_key(tool, params)
        created_at = int(time.time())
        data_json = json.dumps(data)
        self._conn.execute(
            """
            INSERT INTO cache (key, created_at, data)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                created_at=excluded.created_at,
                data=excluded.data
        """,
            (key, created_at, data_json),
        )
        self._conn.commit()
