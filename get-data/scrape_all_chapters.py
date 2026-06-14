"""
Scraper cào TẤT CẢ chương từ metruyenchuvn.com (1 - 6009).

Cách dùng:
    python scrape_all_chapters.py

Sẽ cào tất cả chương bằng cách thử từng số từ 1 đến 6009.
Bỏ qua các chương đã có, loại bỏ header (Converter, Chương XX, Cập nhật...)
"""

import re
import sys
import time
import random
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# Fix Windows terminal encoding
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ─── CẤU HÌNH ────────────────────────────────────────────────────────────────
STORY_SLUG = "vo-luyen-dinh-phong"
BASE_URL = "https://metruyenchuvn.com/{slug}/chuong-{n}"
OUTPUT_DIR = Path(__file__).parent.parent / "convert-txt" / "input" / "Võ Luyện Đỉnh Phong"

START_CHAP = 1
END_CHAP = 6009

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}

DELAY_MIN = 0.5
DELAY_MAX = 1.5
# ─────────────────────────────────────────────────────────────────────────────


def get_existing_chapters(output_dir: Path) -> set[int]:
    """Trả về tập hợp các số chương đã tồn tại."""
    existing = set()
    for f in output_dir.glob("chương *.txt"):
        m = re.match(r"chương\s+(\d+)\.txt", f.name, re.IGNORECASE)
        if m:
            existing.add(int(m.group(1)))
    return existing


def clean_content(text: str) -> str:
    """Loại bỏ các dòng không cần thiết."""
    lines = text.split("\n")
    cleaned = []

    for line in lines:
        stripped = line.strip()

        # Bỏ các dòng không cần
        if stripped.startswith("Converter:"):
            continue
        if re.match(r"^Chương\s+\d+:", stripped, re.IGNORECASE):
            continue
        if re.match(r"^Cập nhật lúc", stripped, re.IGNORECASE):
            continue

        cleaned.append(line)

    # Nối lại và dọn dẹp
    result = "\n".join(cleaned).strip()
    result = re.sub(r"\n{3,}", "\n\n", result)

    return result


def fetch_chapter(chapter_num: int, session: requests.Session) -> str | None:
    """
    Tải chương từ URL tuần tự.
    Trả về nội dung sạch sẽ hoặc None nếu lỗi.
    """
    # Thử multiple URLs vì site có thể thay đổi format
    urls_to_try = [
        f"https://metruyenchuvn.com/{STORY_SLUG}/chuong-{chapter_num}",
    ]

    for url in urls_to_try:
        try:
            resp = session.get(url, headers=HEADERS, timeout=30)
            if resp.status_code != 200:
                continue

            soup = BeautifulSoup(resp.text, "lxml")
            content_div = soup.find("div", class_="truyen")

            if not content_div:
                continue

            # Lấy văn bản
            for br in content_div.find_all("br"):
                br.replace_with("\n")

            paragraphs = content_div.find_all("p")
            if paragraphs:
                lines = []
                for p in paragraphs:
                    text = p.get_text(separator="\n").strip()
                    if text:
                        lines.append(text)
                content = "\n\n".join(lines)
            else:
                content = content_div.get_text(separator="\n").strip()

            if content:
                content = re.sub(r"\n{3,}", "\n\n", content)
                content = content.strip()
                content = clean_content(content)
                return content if content else None

        except requests.RequestException:
            continue

    return None


def save_chapter(chapter_num: int, content: str, output_dir: Path) -> Path:
    """Lưu nội dung chương."""
    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / f"chương {chapter_num}.txt"
    out_file.write_text(content, encoding="utf-8")
    return out_file


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    existing = get_existing_chapters(OUTPUT_DIR)
    print(f"[INFO] Đã có {len(existing)} chương")
    print(f"[INFO] Bắt đầu cào chương {START_CHAP} - {END_CHAP}...\n")

    session = requests.Session()
    ok = skip = fail = 0
    consecutive_fail = 0

    for chap_num in range(START_CHAP, END_CHAP + 1):
        if chap_num % 100 == 0:
            print(f"\n[TIẾN ĐỘ] Chương {chap_num} / {END_CHAP} ({100*chap_num//END_CHAP}%)\n")

        if chap_num in existing:
            skip += 1
            if chap_num % 50 == 0:
                print(f"  [{chap_num:4d}] ⊘ SKIP")
            continue

        content = fetch_chapter(chap_num, session)
        if content is None:
            fail += 1
            consecutive_fail += 1
            if chap_num % 100 == 0 or consecutive_fail <= 5:
                print(f"  [{chap_num:4d}] ✗ LỖI")
        else:
            consecutive_fail = 0
            save_chapter(chap_num, content, OUTPUT_DIR)
            ok += 1
            if chap_num % 100 == 0 or chap_num <= 110:
                chars = len(content)
                print(f"  [{chap_num:4d}] ✓ OK ({chars:,} ký tự)")

        time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

    print(f"\n\n{'='*60}")
    print(f"  HOÀN TẤT - Cào từ metruyenchuvn.com")
    print(f"  Cào mới       : {ok:5d} chương")
    print(f"  Bỏ qua        : {skip:5d} chương (đã có)")
    print(f"  Lỗi           : {fail:5d} chương")
    print(f"  Tổng cộng     : {ok + skip:5d} chương")
    print(f"  Lưu tại       : {OUTPUT_DIR}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
