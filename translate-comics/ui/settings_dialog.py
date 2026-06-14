"""Dialog for API key settings. Priority: Groq → OpenAI → Gemini → Ollama."""
import json
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QMessageBox,
)
from PySide6.QtCore import QSettings

DATA_DIR = Path(__file__).parent.parent / "data"


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cai dat API Key")
        self.setMinimumWidth(480)
        self._settings = QSettings("TranslateComics", "App")
        self._build_ui()
        self._load_values()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(
            "Priority: Groq → OpenAI → Gemini → Ollama\n"
            "Chi can them 1 key la co the dich — Groq mien phi tai console.groq.com"
        ))

        layout.addWidget(QLabel("Groq API Key (mien phi, khuyen dung):"))
        self._groq_key_edit = QLineEdit()
        self._groq_key_edit.setPlaceholderText("gsk_...")
        layout.addWidget(self._groq_key_edit)

        layout.addWidget(QLabel("OpenAI API Key:"))
        self._openai_key_edit = QLineEdit()
        self._openai_key_edit.setPlaceholderText("sk-...")
        layout.addWidget(self._openai_key_edit)

        layout.addWidget(QLabel("Gemini API Key(s) – cach nhau bang dau phay:"))
        self._api_key_edit = QLineEdit()
        self._api_key_edit.setPlaceholderText("AIza...")
        layout.addWidget(self._api_key_edit)

        btn_layout = QHBoxLayout()
        self._test_groq_btn = QPushButton("Test Groq")
        self._test_groq_btn.clicked.connect(self._test_groq)
        self._test_gemini_btn = QPushButton("Test Gemini")
        self._test_gemini_btn.clicked.connect(self._test_gemini)
        self._save_btn = QPushButton("Luu")
        self._save_btn.clicked.connect(self._save)
        self._cancel_btn = QPushButton("Huy")
        self._cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self._test_groq_btn)
        btn_layout.addWidget(self._test_gemini_btn)
        btn_layout.addWidget(self._save_btn)
        btn_layout.addWidget(self._cancel_btn)
        layout.addLayout(btn_layout)

    def _load_values(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        cfg_file = DATA_DIR / "config.json"
        data = {}
        if cfg_file.exists():
            with open(cfg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        self._groq_key_edit.setText(data.get("groq_key", ""))
        self._openai_key_edit.setText(data.get("openai_key", ""))
        keys = data.get("api_keys", [])
        if isinstance(keys, list):
            keys = ", ".join(keys)
        self._api_key_edit.setText(keys)

    def _test_groq(self):
        key = self._groq_key_edit.text().strip()
        if not key:
            QMessageBox.warning(self, "Loi", "Chua nhap Groq API key")
            return
        try:
            from groq import Groq
            client = Groq(api_key=key)
            resp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": "Xin chao"}],
                max_tokens=20,
            )
            QMessageBox.information(self, "OK", f"Groq ket noi thanh cong:\n{resp.choices[0].message.content}")
        except Exception as exc:
            QMessageBox.critical(self, "Loi Groq", str(exc))

    def _test_gemini(self):
        key = self._api_key_edit.text().strip().split(",")[0].strip()
        if not key:
            QMessageBox.warning(self, "Loi", "Chua nhap Gemini API key")
            return
        try:
            from google import genai
            client = genai.Client(api_key=key)
            resp = client.models.generate_content(model="gemini-2.0-flash", contents="Xin chao")
            QMessageBox.information(self, "OK", f"Gemini ket noi thanh cong:\n{resp.text[:100]}")
        except Exception as exc:
            QMessageBox.critical(self, "Loi Gemini", str(exc))

    def _save(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        cfg_file = DATA_DIR / "config.json"
        data = {}
        if cfg_file.exists():
            with open(cfg_file, "r", encoding="utf-8") as f:
                data = json.load(f)

        groq_key = self._groq_key_edit.text().strip()
        openai_key = self._openai_key_edit.text().strip()
        raw_keys = self._api_key_edit.text().strip()
        api_keys = [k.strip() for k in raw_keys.split(",") if k.strip()]

        data["groq_key"] = groq_key
        data["openai_key"] = openai_key
        data["api_keys"] = api_keys

        with open(cfg_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        self._settings.setValue("api_key", raw_keys)
        self._settings.setValue("groq_key", groq_key)
        self._settings.setValue("openai_key", openai_key)
        self.accept()
