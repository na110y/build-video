"""TranslationEngine orchestrating translation steps, chunking, and quality checks."""
import logging
from pathlib import Path

from src.formatter import format_novel_text
from src.quality_check import QualityChecker
from src.context_engine import ContextEngine
from src.database import Database

logger = logging.getLogger(__name__)

LogCB = callable  # type: ignore


class TranslationEngine:
    def __init__(self, gemini_client, db: Database) -> None:
        self._gemini = gemini_client
        self._db = db
        self._qc = QualityChecker()

    def translate_story(self, story_id: int, chapters: list[tuple[int, str, str]], genre: str = "", log: LogCB = print) -> None:
        """Translate a list of (chapter_num, title_zh, content_zh)."""
        ctx_engine = ContextEngine(self._db, story_id)
        prev_summary = ""
        for ch_num, title_zh, content_zh in chapters:
            # Resume: skip chapters already translated
            existing = self._db.get_chapter(story_id, ch_num)
            if existing and existing.get("status") == "done":
                log("info", f"  Chuong {ch_num} da dich xong, bo qua")
                prev_summary = existing.get("summary", "") or prev_summary
                continue
            log("info", f"  Dich chuong {ch_num}...")
            glossary = ctx_engine.build_glossary()
            chunks = _split_chunks(content_zh, size=1500)
            translated_parts: list[str] = []
            for idx, chunk in enumerate(chunks):
                polished = self._translate_chunk(
                    chunk, glossary, prev_summary, genre, ch_num, idx, log
                )
                translated_parts.append(polished)
            full_text = "\n\n".join(translated_parts)
            summary = self._gemini.summarize_chapter(full_text, ch_num)
            self._db.upsert_chapter(
                story_id, ch_num, title_zh=title_zh, content_vi=full_text, summary=summary, status="done"
            )
            prev_summary = summary
            log("info", f"  Xong chuong {ch_num}")

    def analyze_and_setup(self, story_id: int, sample_text: str, log: LogCB = print) -> dict:
        """Analyze novel and populate characters/terms."""
        log("info", "  Phan tich truyen (Gemini Flash)...")
        try:
            analysis = self._gemini.analyze_novel(sample_text)
        except Exception as exc:
            log("warning", f"  Phan tich that bai: {exc}")
            return {}
        for ch in analysis.get("characters", []):
            self._db.add_character(story_id, ch.get("name_zh", ""), ch.get("name_vi", ""))
        for t in analysis.get("terms", []):
            self._db.add_term(story_id, t.get("term_zh", ""), t.get("term_vi", ""))
        return analysis

    # ── Private ───────────────────────────────────────────────────────────────

    def _translate_chunk(
        self,
        chunk: str,
        glossary: str,
        prev_context: str,
        genre: str,
        chapter_num: int,
        chunk_idx: int,
        log: LogCB,
    ) -> str:
        # Step 1 – literal
        draft = self._gemini.translate_literal(chunk, glossary, prev_context)

        # Step 2 – editorial polish
        polished = self._gemini.translate_edit(draft, genre)

        # Step 2b – format cho chuyên nghiệp
        polished = format_novel_text(polished)

        # Step 5 – QC
        qc = self._qc.check(chunk, polished, glossary)

        if qc.has_critical:
            log(
                "warning",
                f"  Doan {chunk_idx+1} cua chuong {chapter_num}: "
                f"phat hien {len(qc.critical)} loi nghiem trong – dich lai…",
            )
            draft = self._gemini.translate_literal(chunk, glossary, prev_context)
            polished = self._gemini.translate_edit(draft, genre)
            polished = format_novel_text(polished)

            # Log remaining issues
            qc2 = self._qc.check(chunk, polished, glossary)
            if qc2.has_critical:
                log(
                    "warning",
                    f"  Van con {len(qc2.critical)} loi sau khi dich lai – giu ket qua",
                )

        return polished


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _split_chunks(text: str, size: int) -> list[str]:
    """Split text into chunks by approximate character size, respecting paragraph boundaries."""
    paragraphs = text.split("\n")
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if current_len + len(para) > size and current:
            chunks.append("\n".join(current))
            current = [para]
            current_len = len(para)
        else:
            current.append(para)
            current_len += len(para)
    if current:
        chunks.append("\n".join(current))
    return chunks if chunks else [text]
