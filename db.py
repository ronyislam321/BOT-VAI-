import sqlite3
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any


class Database:
    def __init__(self, path: str):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT,
                is_premium INTEGER DEFAULT 0,
                credits INTEGER DEFAULT 0,
                validity_expire_at TEXT,
                selected_model TEXT,
                tts_speed TEXT,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS voices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                file_path TEXT,
                created_at TEXT
            )
            """
        )

        # ✅ NEW: settings table for admin-controlled configs (default voice id, etc.)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )

        # Migration safety: if old DB exists without tts_speed, add it.
        try:
            cur.execute("ALTER TABLE users ADD COLUMN tts_speed TEXT")
        except Exception:
            pass

        self.conn.commit()

    # -----------------------
    # ✅ SETTINGS (key/value)
    # -----------------------
    def get_setting(self, key: str, default: str = "") -> str:
        cur = self.conn.cursor()
        cur.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = cur.fetchone()
        return row[0] if row else default

    def set_setting(self, key: str, value: str) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO settings(key, value) VALUES(?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """,
            (key, value),
        )
        self.conn.commit()

    # -----------------------
    # USERS
    # -----------------------
    def ensure_user(self, user_id: int, username: Optional[str]):
        cur = self.conn.cursor()
        cur.execute("SELECT id FROM users WHERE id = ?", (user_id,))
        row = cur.fetchone()
        now = datetime.utcnow().isoformat()
        if not row:
            cur.execute(
                "INSERT INTO users (id, username, is_premium, credits, tts_speed, created_at, updated_at) VALUES (?
