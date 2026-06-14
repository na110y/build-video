"""SQLite database for story metadata, characters, terms, chapters, and API usage logs."""
import json
import sqlite3
from pathlib import Path


class Database:
    """SQLite wrapper for the translation project."""

    def __init__(self, db_path: str | Path) -> None:
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self) -> None:
        sql = """
        CREATE TABLE IF NOT EXISTS stories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            author TEXT,
            genre TEXT,
            source_file TEXT UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS characters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            story_id INTEGER,
            name_zh TEXT,
            name_vi TEXT,
            notes TEXT,
            FOREIGN KEY (story_id) REFERENCES stories(id)
        );

        CREATE TABLE IF NOT EXISTS terms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            story_id INTEGER,
            term_zh TEXT,
            term_vi TEXT,
            notes TEXT,
            FOREIGN KEY (story_id) REFERENCES stories(id)
        );

        CREATE TABLE IF NOT EXISTS chapters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            story_id INTEGER,
            chapter_num INTEGER,
            title_zh TEXT,
            title_vi TEXT,
            content_zh TEXT,
            content_vi TEXT,
            summary TEXT,
            status TEXT DEFAULT 'pending',
            FOREIGN KEY (story_id) REFERENCES stories(id),
            UNIQUE(story_id, chapter_num)
        );

        CREATE TABLE IF NOT EXISTS api_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            story_id INTEGER,
            model TEXT,
            prompt_tokens INTEGER,
            completion_tokens INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (story_id) REFERENCES stories(id)
        );
        """
        self._conn.executescript(sql)
        self._conn.commit()

    # ── Stories ───────────────────────────────────────────────────────────────

    def upsert_story(self, title: str, author: str, genre: str, source_file: str) -> int:
        cur = self._conn.execute(
            "INSERT INTO stories (title, author, genre, source_file) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(source_file) DO UPDATE SET title=excluded.title, author=excluded.author, genre=excluded.genre "
            "RETURNING id",
            (title, author, genre, source_file),
        )
        row = cur.fetchone()
        self._conn.commit()
        return row[0]

    def get_story(self, source_file: str) -> dict | None:
        cur = self._conn.execute("SELECT * FROM stories WHERE source_file=?", (source_file,))
        row = cur.fetchone()
        return dict(row) if row else None

    # ── Characters / Terms ────────────────────────────────────────────────────

    def add_character(self, story_id: int, name_zh: str, name_vi: str, notes: str = "") -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO characters (story_id, name_zh, name_vi, notes) VALUES (?, ?, ?, ?)",
            (story_id, name_zh, name_vi, notes),
        )
        self._conn.commit()

    def add_term(self, story_id: int, term_zh: str, term_vi: str, notes: str = "") -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO terms (story_id, term_zh, term_vi, notes) VALUES (?, ?, ?, ?)",
            (story_id, term_zh, term_vi, notes),
        )
        self._conn.commit()

    def get_characters(self, story_id: int) -> list[dict]:
        cur = self._conn.execute("SELECT name_zh, name_vi, notes FROM characters WHERE story_id=?", (story_id,))
        return [dict(r) for r in cur.fetchall()]

    def get_terms(self, story_id: int) -> list[dict]:
        cur = self._conn.execute("SELECT term_zh, term_vi, notes FROM terms WHERE story_id=?", (story_id,))
        return [dict(r) for r in cur.fetchall()]

    # ── Chapters ──────────────────────────────────────────────────────────────

    def upsert_chapter(self, story_id: int, chapter_num: int, title_zh: str = "", content_vi: str = "", summary: str = "", status: str = "pending") -> None:
        self._conn.execute(
            "INSERT INTO chapters (story_id, chapter_num, title_zh, content_vi, summary, status) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(story_id, chapter_num) DO UPDATE SET "
            "title_zh=excluded.title_zh, content_vi=excluded.content_vi, summary=excluded.summary, status=excluded.status",
            (story_id, chapter_num, title_zh, content_vi, summary, status),
        )
        self._conn.commit()

    def get_chapter(self, story_id: int, chapter_num: int) -> dict | None:
        cur = self._conn.execute(
            "SELECT * FROM chapters WHERE story_id=? AND chapter_num=?", (story_id, chapter_num)
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def get_all_chapters(self, story_id: int) -> list[dict]:
        cur = self._conn.execute(
            "SELECT chapter_num, title_zh, content_vi, summary, status FROM chapters WHERE story_id=? ORDER BY chapter_num",
            (story_id,),
        )
        return [dict(r) for r in cur.fetchall()]

    # ── API usage ─────────────────────────────────────────────────────────────

    def log_usage(self, story_id: int, model: str, prompt_tokens: int, completion_tokens: int) -> None:
        self._conn.execute(
            "INSERT INTO api_usage (story_id, model, prompt_tokens, completion_tokens) VALUES (?, ?, ?, ?)",
            (story_id, model, prompt_tokens, completion_tokens),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
