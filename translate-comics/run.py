"""Handles command-line execution, API key loading, fallback logic, and file processing."""
import io
import json
import logging
import os
import sys
from pathlib import Path

# Force UTF-8 stdout so Chinese filenames don't crash on Windows cp1252
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Ensure src/ui on path
sys.path.insert(0, str(Path(__file__).parent))

from src.gemini_client import GeminiClient
from src.local_client import FallbackChain
from src.translator import TranslationEngine
from src.database import Database
from src.formatter import format_novel_text
from src.epub_exporter import export_epub

logger = logging.getLogger(__name__)

INPUT_DIR = Path(__file__).parent / "input"
OUTPUT_DIR = Path(__file__).parent / "output"
DATA_DIR = Path(__file__).parent / "data"


def load_api_key():
    cfg_file = DATA_DIR / "config.json"
    keys_file = DATA_DIR / "keys.txt"
    data = {}
    keys: list[str] = []

    if cfg_file.exists():
        with open(cfg_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        cfg_keys = data.get("api_keys", [])
        if isinstance(cfg_keys, str):
            cfg_keys = [cfg_keys]
        keys.extend([k for k in cfg_keys if k.strip()])

    if keys_file.exists():
        with open(keys_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    keys.append(line)

    return keys, data


def detect_encoding(file_path: Path) -> str:
    """Detect file encoding, trying common Chinese encodings."""
    with open(file_path, "rb") as f:
        raw = f.read(4)
    # BOM detection
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return "utf-16"
    if raw[:3] == b"\xef\xbb\xbf":
        return "utf-8-sig"
    # Try chardet if available
    try:
        import chardet
        with open(file_path, "rb") as f:
            result = chardet.detect(f.read(10000))
        enc = result.get("encoding", "utf-8") or "utf-8"
        return enc
    except ImportError:
        pass
    # Fallback: try common encodings
    for enc in ("utf-8", "utf-16", "gbk", "gb18030", "big5"):
        try:
            with open(file_path, "r", encoding=enc) as f:
                f.read(1000)
            return enc
        except (UnicodeDecodeError, UnicodeError):
            continue
    return "utf-8"


def parse_chapters(text: str) -> list[tuple[int, str, str]]:
    """Split text into chapters, supporting multiple common formats."""
    import re

    # Format 1: 第1章 / 第 2 章 (most common)
    pattern1 = re.compile(r"(第\s*\d+\s*章[^\n]*)")
    # Format 2: 第一章 / 第二章 (Chinese numerals)
    pattern2 = re.compile(r"(第[零一二三四五六七八九十百千]+章[^\n]*)")
    # Format 3: \n1.\n or \n2.\n (bare number with period on own line)
    pattern3 = re.compile(r"\n(\d+)\.\n")

    for pattern, title_fmt in [
        (pattern1, lambda m: m.group(1).strip()),
        (pattern2, lambda m: m.group(1).strip()),
    ]:
        matches = list(pattern.finditer(text))
        if len(matches) >= 2:
            chapters = []
            for i, m in enumerate(matches):
                title = title_fmt(m)
                start = m.end()
                end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
                body = text[start:end].strip()
                num = int(re.search(r"\d+", title).group()) if re.search(r"\d+", title) else i + 1
                chapters.append((num, title, body))
            return chapters

    # Format 3: bare number chapters (1. 2. 3.)
    matches3 = list(pattern3.finditer(text))
    if len(matches3) >= 2:
        chapters = []
        for i, m in enumerate(matches3):
            num = int(m.group(1))
            start = m.end()
            end = matches3[i + 1].start() if i + 1 < len(matches3) else len(text)
            body = text[start:end].strip()
            chapters.append((num, f"Chương {num}", body))
        return chapters

    # No chapter markers — treat whole file as one chapter
    return [(1, "", text)]


def process_file(file_path: Path, gemini: GeminiClient, fallback) -> None:
    db_path = DATA_DIR / f"{file_path.stem}.db"
    db = Database(db_path)
    story_id = db.upsert_story(
        title=file_path.stem,
        author="",
        genre="",
        source_file=str(file_path),
    )

    enc = detect_encoding(file_path)
    with open(file_path, "r", encoding=enc, errors="replace") as f:
        raw = f.read()

    chapters = parse_chapters(raw)
    print(f"  Tim thay {len(chapters)} chuong")

    engine = TranslationEngine(gemini, db)

    # Analyze first chapter if not already analyzed
    analysis = engine.analyze_and_setup(story_id, chapters[0][2] if chapters else raw)
    genre = analysis.get("genre", "")
    print(f"  The loai: {genre}")

    engine.translate_story(story_id, chapters, genre=genre, log=lambda lvl, msg: print(f"  [{lvl.upper()}] {msg}"))

    # Export TXT
    txt_path = OUTPUT_DIR / f"{file_path.stem}_VI.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(f"{analysis.get('title', file_path.stem)}\n\n")
        for ch in db.get_all_chapters(story_id):
            f.write(f"Chuong {ch['chapter_num']}\n{ch['content_vi']}\n\n")
    print(f"  Xuat TXT: {txt_path}")

    # Export EPUB
    epub_path = OUTPUT_DIR / f"{file_path.stem}_VI.epub"
    try:
        export_epub(
            output_path=str(epub_path),
            title=analysis.get("title", file_path.stem),
            author=analysis.get("author", ""),
            genre=genre,
            chapters=db.get_all_chapters(story_id),
            characters=db.get_characters(story_id),
            terms=db.get_terms(story_id),
        )
        print(f"  Xuat EPUB: {epub_path}")
    except Exception as exc:
        print(f"  [WARN] Khong xuat EPUB duoc: {exc}")

    db.close()


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    files = sorted(INPUT_DIR.glob("*.txt"))
    if not files:
        print(f"  Khong co file nao trong thu muc input/")
        print(f"  Bo file TXT vao: {INPUT_DIR}\n")
        return

    print(f"  Tim thay {len(files)} file:\n")
    for f in files:
        print(f"    - {f.name}")
    print()

    _, cfg_data = load_api_key()
    api_keys = cfg_data.get("api_keys", [])
    if isinstance(api_keys, str):
        api_keys = [api_keys]
    api_keys = [k for k in api_keys if k.strip()]
    groq_key = cfg_data.get("groq_key", os.environ.get("GROQ_API_KEY", ""))
    openai_key = cfg_data.get("openai_key", os.environ.get("OPENAI_API_KEY", ""))

    # Priority: Groq → OpenAI → Gemini → Ollama  (Plan V4)
    fallback = FallbackChain(groq_key=groq_key, openai_key=openai_key)

    if fallback.is_available():
        # Use Groq/OpenAI/Ollama as primary — no Gemini key required
        gemini = GeminiClient(api_keys, local_fallback=fallback)
        print(f"  Engine chinh: {type(fallback._active).__name__}")
    elif api_keys:
        gemini = GeminiClient(api_keys, local_fallback=fallback)
        print(f"  Engine chinh: Gemini ({len(api_keys)} key(s))")
    else:
        print("  Khong co API nao kha dung.")
        print("  Can it nhat mot trong: Groq key, OpenAI key, Gemini key, hoac Ollama dang chay.")
        print("  Them key vao data/config.json:")
        print('    {"groq_key": "gsk_...", "openai_key": "sk-...", "api_keys": ["AIza..."]}')
        return

    ok = fail = 0
    for file in files:
        try:
            print(f"\n  ====================================================")
            print(f"  File  : {file.name}")
            print(f"  Output: {file.stem}_VI.txt")
            print(f"  ====================================================")
            process_file(file, gemini, fallback)
            ok += 1
        except Exception as exc:
            print(f"  [ERR ]  {file.name}: {exc}")
            fail += 1

    print(f"\n  ====================================================")
    print(f"  HOAN TAT  -  {ok} file thanh cong  |  {fail} loi")
    print(f"  Output: {OUTPUT_DIR}")
    print(f"  ====================================================")


if __name__ == "__main__":
    main()
