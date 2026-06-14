"""MainWindow class orchestrating UI, file operations, API key handling, and workers."""
import json
import logging
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QLineEdit,
    QTextEdit,
    QFileDialog,
    QMessageBox,
    QProgressBar,
    QToolBar,
    QStatusBar,
    QMenuBar,
    QMenu,
)
from PySide6.QtCore import Qt, QSettings

from src.gemini_client import GeminiClient
from src.local_client import FallbackChain
from src.database import Database
from ui.settings_dialog import SettingsDialog
from ui.workers import PdfExportWorker

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"
INPUT_DIR = Path(__file__).parent.parent / "input"
OUTPUT_DIR = Path(__file__).parent.parent / "output"


def load_api_key():
    cfg_file = DATA_DIR / "config.json"
    if cfg_file.exists():
        with open(cfg_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        keys = data.get("api_keys", [])
        if isinstance(keys, str):
            keys = [keys]
        return [k for k in keys if k.strip()], data
    return [], {}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dich Truyen Trung-Viet")
        self.setMinimumSize(900, 600)
        self._settings = QSettings("TranslateComics", "App")
        self._gemini: GeminiClient | None = None
        self._fallback: FallbackChain | None = None
        self._current_story_id: int | None = None
        self._init_ui()
        self._init_engine()

    def _init_ui(self):
        # Menu
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        self._open_act = file_menu.addAction("Mo truyen")
        self._open_act.triggered.connect(self._open_file)
        self._export_pdf_act = file_menu.addAction("Xuat PDF")
        self._export_pdf_act.triggered.connect(self._export_pdf)
        self._export_pdf_act.setEnabled(False)
        file_menu.addSeparator()
        file_menu.addAction("Thoat", self.close)

        settings_menu = menubar.addMenu("Cai dat")
        settings_menu.addAction("API Key", self._open_settings)

        # Toolbar
        toolbar = QToolBar()
        self.addToolBar(toolbar)
        self._btn_open = QPushButton("Mo truyen")
        self._btn_open.clicked.connect(self._open_file)
        toolbar.addWidget(self._btn_open)
        self._btn_translate = QPushButton("Bat dau dich")
        self._btn_translate.clicked.connect(self._start_translate)
        self._btn_translate.setEnabled(False)
        toolbar.addWidget(self._btn_translate)
        self._btn_export_pdf = QPushButton("Xuat PDF")
        self._btn_export_pdf.clicked.connect(self._export_pdf)
        self._btn_export_pdf.setEnabled(False)
        toolbar.addWidget(self._btn_export_pdf)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self._title_edit = QLineEdit()
        self._title_edit.setPlaceholderText("Ten truyen")
        layout.addWidget(QLabel("Ten truyen:"))
        layout.addWidget(self._title_edit)

        self._author_edit = QLineEdit()
        self._author_edit.setPlaceholderText("Tac gia")
        layout.addWidget(QLabel("Tac gia:"))
        layout.addWidget(self._author_edit)

        self._genre_edit = QLineEdit()
        self._genre_edit.setPlaceholderText("The loai")
        layout.addWidget(QLabel("The loai:"))
        layout.addWidget(self._genre_edit)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        layout.addWidget(self._progress)

        self._log_edit = QTextEdit()
        self._log_edit.setReadOnly(True)
        layout.addWidget(self._log_edit)

        self._status = QStatusBar()
        self.setStatusBar(self._status)

    def _init_engine(self):
        api_keys, cfg_data = load_api_key()
        groq_key = cfg_data.get("groq_key", "")
        openai_key = cfg_data.get("openai_key", "")
        self._fallback = FallbackChain(groq_key=groq_key, openai_key=openai_key)
        self._gemini = GeminiClient(api_keys, local_fallback=self._fallback)
        if self._fallback.is_available():
            engine_name = type(self._fallback._active).__name__
            self._status.showMessage(f"San sang — dung {engine_name}")
        elif not self._gemini.all_keys_exhausted:
            self._status.showMessage("San sang — dung Gemini")
        else:
            self._status.showMessage("Chua co API key. Vao Cai dat → them Groq/OpenAI/Gemini key.")

    def _open_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec() == SettingsDialog.Accepted:
            self._init_engine()

    def _ensure_api_key(self) -> bool:
        key = self._settings.value("api_key", "")
        if not key:
            self._open_settings()
            key = self._settings.value("api_key", "")
        if not key:
            if self._fallback and self._fallback.is_available():
                if not self._gemini:
                    self._gemini = GeminiClient([], local_fallback=self._fallback)
                return True
            QMessageBox.warning(
                self, "Thieu API Key",
                "Can nhap it nhat mot trong:\n• Groq API Key (mien phi)\n• OpenAI API Key\n• Gemini API Key\n\nVao Cai dat → API Key de them."
            )
            return False
        if not self._gemini:
            if not self._fallback:
                self._fallback = FallbackChain()
            self._gemini = GeminiClient(key, local_fallback=self._fallback)
        return True

    def _open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Mo truyen", str(INPUT_DIR), "Text files (*.txt);;All files (*)")
        if not path:
            return
        self._source_path = Path(path)
        self._log_edit.append(f"Mo: {path}")
        self._btn_translate.setEnabled(True)
        self._status.showMessage(f"Da mo: {self._source_path.name}")

    def _start_translate(self):
        if not getattr(self, "_source_path", None):
            QMessageBox.warning(self, "Loi", "Chua chon file truyen")
            return
        if not self._ensure_api_key():
            return
        # TODO: implement threaded translation; for now just log
        self._log_edit.append("Bat dau dich... (can them worker thread)")
        self._btn_export_pdf.setEnabled(True)

    def _export_pdf(self):
        if self._current_story_id is None:
            QMessageBox.warning(self, "Loi", "Chua co du lieu de xuat PDF")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Xuat PDF", str(OUTPUT_DIR / "truyen.pdf"), "PDF (*.pdf)")
        if not path:
            return
        db_path = DATA_DIR / f"{self._source_path.stem}.db"
        self._worker = PdfExportWorker(path, self._current_story_id, str(db_path))
        self._worker.finished.connect(lambda p: QMessageBox.information(self, "Xong", f"Da xuat: {p}"))
        self._worker.error.connect(lambda e: QMessageBox.critical(self, "Loi", e))
        self._worker.start()
