"""
SQLite-backed session persistence for web game sessions.
Stores serialized game state so sessions survive server restarts.
"""

import sqlite3
import json
import time
from pathlib import Path
from typing import Optional, Dict, Any, List

# Store DB in the same directory as file-based saves
DB_PATH = Path.home() / ".capital_markets_game" / "sessions.db"

# Sessions older than 7 days are cleaned up
SESSION_TTL_SECONDS = 7 * 24 * 60 * 60


class SessionStore:
    """SQLite-backed storage for game sessions"""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path))

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    game_id TEXT PRIMARY KEY,
                    state_json TEXT NOT NULL,
                    news_history_json TEXT NOT NULL DEFAULT '[]',
                    seed INTEGER,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            conn.commit()

    def save_session(self, game_id: str, state: Dict[str, Any],
                     news_history: List[str], seed: Optional[int] = None):
        """Persist a session to SQLite"""
        now = time.time()
        state_json = json.dumps(state)
        news_json = json.dumps(news_history[-50:])  # Keep last 50 news items

        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO sessions (game_id, state_json, news_history_json, seed, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(game_id) DO UPDATE SET
                    state_json = excluded.state_json,
                    news_history_json = excluded.news_history_json,
                    updated_at = excluded.updated_at
            """, (game_id, state_json, news_json, seed, now, now))
            conn.commit()

    def load_session(self, game_id: str) -> Optional[Dict[str, Any]]:
        """Load a single session from SQLite"""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT state_json, news_history_json, seed FROM sessions WHERE game_id = ?",
                (game_id,)
            ).fetchone()

        if not row:
            return None

        return {
            "state": json.loads(row[0]),
            "news_history": json.loads(row[1]),
            "seed": row[2],
        }

    def load_all_sessions(self) -> Dict[str, Dict[str, Any]]:
        """Load all non-expired sessions"""
        cutoff = time.time() - SESSION_TTL_SECONDS

        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT game_id, state_json, news_history_json, seed FROM sessions WHERE updated_at > ?",
                (cutoff,)
            ).fetchall()

        sessions = {}
        for game_id, state_json, news_json, seed in rows:
            sessions[game_id] = {
                "state": json.loads(state_json),
                "news_history": json.loads(news_json),
                "seed": seed,
            }
        return sessions

    def delete_session(self, game_id: str):
        """Remove a session from SQLite"""
        with self._get_conn() as conn:
            conn.execute("DELETE FROM sessions WHERE game_id = ?", (game_id,))
            conn.commit()

    def cleanup_expired(self):
        """Remove sessions older than TTL"""
        cutoff = time.time() - SESSION_TTL_SECONDS
        with self._get_conn() as conn:
            deleted = conn.execute(
                "DELETE FROM sessions WHERE updated_at < ?", (cutoff,)
            ).rowcount
            conn.commit()
        return deleted

    def session_count(self) -> int:
        with self._get_conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
