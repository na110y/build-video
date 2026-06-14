"""PDF export with cover, headers/footers, and appendix."""
import os
import tempfile
from pathlib import Path
from typing import Optional

try:
    from fpdf import FPDF
except ImportError:
    FPDF = None  # type: ignore


class NovelPDF(FPDF):
    def __init__(self, title: str, author: str, genre: str = ""):
        super().__init__(unit="mm", format="A4")
        self.novel_title = title
        self.novel_author = author
        self.novel_genre = genre
        self._setup_fonts()
        self._add_cover()
        self.set_auto_page_break(auto=True, margin=20)

    def _setup_fonts(self) -> None:
        """Detect available fonts with fallback to downloaded NotoSans."""
        font_path = self._find_font()
        if font_path:
            self.add_font("Noto", "", font_path, uni=True)
            self.add_font("Noto", "B", font_path, uni=True)
            self.set_font("Noto", "", 12)
        else:
            # fpdf2 built-in DejaVu (may lack Vietnamese)
            self.add_font("DejaVu", "", "DejaVuSans.ttf", uni=True)
            self.add_font("DejaVu", "B", "DejaVuSans-Bold.ttf", uni=True)
            self.set_font("DejaVu", "", 12)

    def _find_font(self) -> Optional[str]:
        """Find a suitable TTF font for Vietnamese."""
        candidates = [
            "C:/Windows/Fonts/times.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
        ]
        for p in candidates:
            if os.path.isfile(p):
                return p
        # Download NotoSans if not found
        return self._download_noto_font()

    def _download_noto_font(self) -> Optional[str]:
        import urllib.request
        url = "https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf"
        dest = Path(tempfile.gettempdir()) / "NotoSansCJKsc-Regular.otf"
        if not dest.exists():
            try:
                urllib.request.urlretrieve(url, str(dest))
            except Exception:
                return None
        return str(dest) if dest.exists() else None

    def _add_cover(self) -> None:
        self.add_page()
        self.set_font_size(24)
        self.set_y(80)
        self.cell(0, 15, self.novel_title, align="C", ln=True)
        if self.novel_author:
            self.set_font_size(14)
            self.cell(0, 10, f"Tac gia: {self.novel_author}", align="C", ln=True)
        if self.novel_genre:
            self.set_font_size(12)
            self.cell(0, 10, f"The loai: {self.novel_genre}", align="C", ln=True)

    def header(self) -> None:
        if self.page_no() > 1:
            self.set_font_size(10)
            self.cell(0, 10, self.novel_title, align="C", ln=True)
            self.ln(2)

    def footer(self) -> None:
        if self.page_no() > 1:
            self.set_y(-15)
            self.set_font_size(10)
            self.cell(0, 10, f"Trang {self.page_no()}", align="C")

    def add_chapter(self, title: str, body: str) -> None:
        self.add_page()
        self.set_font_size(14)
        self.cell(0, 10, title, align="C", ln=True)
        self.ln(5)
        self.set_font_size(12)
        for para in body.split("\n\n"):
            if para.strip():
                self.multi_cell(0, 6, para.strip())
                self.ln(2)

    def add_appendix(self, characters: list[dict], terms: list[dict]) -> None:
        self.add_page()
        self.set_font_size(16)
        self.cell(0, 10, "PHU LUC", align="C", ln=True)
        self.ln(5)
        if characters:
            self.set_font_size(14)
            self.cell(0, 8, "Nhan vat", ln=True)
            self.set_font_size(11)
            for c in characters:
                self.cell(0, 6, f"{c.get('name_zh', '')} → {c.get('name_vi', '')}", ln=True)
            self.ln(5)
        if terms:
            self.set_font_size(14)
            self.cell(0, 8, "Thuat ngu", ln=True)
            self.set_font_size(11)
            for t in terms:
                self.cell(0, 6, f"{t.get('term_zh', '')} → {t.get('term_vi', '')}", ln=True)


def export_pdf(
    output_path: str,
    title: str,
    author: str,
    genre: str,
    chapters: list[dict],
    characters: list[dict],
    terms: list[dict],
) -> str:
    if FPDF is None:
        raise ImportError("fpdf2 chua duoc cai dat. Chay: pip install fpdf2")
    pdf = NovelPDF(title=title, author=author, genre=genre)
    for ch in chapters:
        pdf.add_chapter(ch.get("title_vi", f"Chuong {ch['chapter_num']}"), ch.get("content_vi", ""))
    pdf.add_appendix(characters, terms)
    pdf.output(output_path)
    return output_path
