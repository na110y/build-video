"""QThread workers for background tasks."""
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from src.gemini_client import GeminiClient
from src.local_client import FallbackChain
from src.translator import TranslationEngine
from src.database import Database
from src.pdf_exporter import export_pdf


class PdfExportWorker(QThread):
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, output_path: str, story_id: int, db_path: str) -> None:
        super().__init__()
        self._output_path = output_path
        self._story_id = story_id
        self._db_path = db_path

    def run(self) -> None:
        try:
            db = Database(self._db_path)
            story = db._conn.execute("SELECT title, author, genre FROM stories WHERE id=?", (self._story_id,)).fetchone()
            if not story:
                self.error.emit("Khong tim thay truyen trong database")
                return
            title, author, genre = story
            chapters = db.get_all_chapters(self._story_id)
            characters = db.get_characters(self._story_id)
            terms = db.get_terms(self._story_id)
            db.close()
            export_pdf(
                output_path=self._output_path,
                title=title or "",
                author=author or "",
                genre=genre or "",
                chapters=chapters,
                characters=characters,
                terms=terms,
            )
            self.finished.emit(self._output_path)
        except Exception as exc:
            self.error.emit(str(exc))
