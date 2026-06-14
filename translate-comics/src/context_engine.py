"""Provides context such as glossary and summaries for translation."""
from typing import Optional


class ContextEngine:
    """Builds context strings from database entries."""

    def __init__(self, db, story_id: int):
        self._db = db
        self._story_id = story_id

    def build_glossary(self) -> str:
        chars = self._db.get_characters(self._story_id)
        terms = self._db.get_terms(self._story_id)
        lines: list[str] = []
        if chars:
            lines.append("── NHÂN VẬT ───")
            for c in chars:
                lines.append(f"{c['name_zh']} → {c['name_vi']}")
        if terms:
            lines.append("── THUẬT NGỮ ───")
            for t in terms:
                lines.append(f"{t['term_zh']} → {t['term_vi']}")
        return "\n".join(lines) if lines else "(không có)"

    def get_previous_summary(self, current_chapter: int, limit: int = 3) -> str:
        chapters = self._db.get_all_chapters(self._story_id)
        summaries: list[str] = []
        for ch in chapters:
            if ch["chapter_num"] < current_chapter and ch.get("summary"):
                summaries.append(f"Chương {ch['chapter_num']}: {ch['summary']}")
        return "\n".join(summaries[-limit:]) if summaries else ""
